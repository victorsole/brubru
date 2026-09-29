"""
Sync decentralised EU agency consultations into public_consultations (MEUB hub).

Mirrors the agency public consultations already ingested into economy_items
(item_type='consultation', via the API v2 /api/v2/consultations/all layer:
EIOPA, BEREC, ACER, EASA, EMA, AMLA, ECHA, SRB, ERA, ECB-SSM) into the
public_consultations table, tagged source='agency' + source_body=<CODE>, so the
EC Public Consultations tab becomes an all-EU hub where agency consultations are
uniform and trackable alongside the Commission's Have Your Say. Idempotent
(upsert on initiative_id='agency-<body>-<id>'). NO Anthropic.

Status is derived from the closing date (economy_items.document_date): a closing
date in the future is 'open', otherwise 'closed'.

Usage:
    python3.12 -m scripts.sync_agency_consultations
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import logging
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text

from core.database import SessionLocal
from models.public_consultation import (
    PublicConsultation, ConsultationTypeEnum, ConsultationStatusEnum,
)
from services.scrapers.agency_consultations import parse_body_facts
from services.tracking.policy_area_classifier import classify


def _as_date(v):
    """The ISO date `_build` wrote, or None. A value we cannot read is not a date."""
    if not v:
        return None
    try:
        return date.fromisoformat(str(v).strip()[:10])
    except ValueError:
        return None


def _rows(db):
    return db.execute(text(
        "SELECT id, body_code, title, summary, public_url, document_date, body_txt "
        "FROM economy_items "
        "WHERE item_type = 'consultation' AND title IS NOT NULL "
        "ORDER BY document_date DESC NULLS LAST, id DESC"
    )).mappings().all()


_SOURCE_STATUS = {"open": ConsultationStatusEnum.OPEN,
                  "closed": ConsultationStatusEnum.CLOSED,
                  "upcoming": ConsultationStatusEnum.UPCOMING,
                  "forthcoming": ConsultationStatusEnum.UPCOMING}


def _status(closing, stated: str | None) -> ConsultationStatusEnum:
    """The status the AGENCY publishes, reconciled against the deadline it publishes.

    Deriving the status from the closing date alone was wrong twice over: the closing
    date itself was read from the neighbouring card (see agency_consultations), and a
    derived value cannot be checked against anything. The agency states a status on its
    own listing, so that is the authority. A stated 'open' whose deadline has passed is
    the agency being slow to flip its own label, and the deadline it publishes wins:
    AMLA and EIOPA both still showed rows we served as open on 29 Sep 2026, eight days
    and seven weeks after those consultations closed.
    """
    said = _SOURCE_STATUS.get((stated or "").strip().lower())
    live = closing is not None and closing.date() >= date.today()

    # OPEN is a claim that needs evidence, and the evidence is a deadline that has not
    # passed. Trusting a stated "Open" without one turned 100+ ACER rows open on
    # 29 Sep 2026: their mirrored text still said Open from an earlier crawl, they
    # carry no deadline, so nothing could ever contradict it and the row would have
    # stayed open for ever. A status we cannot check against a date is not served as
    # open.
    if said is ConsultationStatusEnum.UPCOMING:
        return said
    if said is ConsultationStatusEnum.CLOSED:
        return said
    return ConsultationStatusEnum.OPEN if live else ConsultationStatusEnum.CLOSED


def _best_title(title: str, summary: str):
    """Recover full titles: the agency ingestion caps economy_items.title at 120
    chars, but the full title is often the summary. Prefer the summary only when
    it is a clean expansion of the (truncated) title, never a 'status . date'
    blurb. Returns (title, description) where description is None when the chosen
    title already is the summary."""
    t = (title or "").strip()
    s = (summary or "").strip()
    looks_truncated = len(t) >= 118
    if s and len(s) > len(t) and looks_truncated and len(t) >= 40 \
            and s.lower().startswith(t[:60].lower()):
        return s, None
    description = s if s and s != t else None
    return t, description


def _upsert(db, r) -> str:
    body = (r["body_code"] or "").upper()
    # public_consultations.initiative_id has a numeric-only CHECK constraint
    # (Have Your Say ids are numeric). Agency rows get a deterministic numeric id
    # well above the Commission id range (5 digits) to avoid any collision; the
    # responsible agency is carried in source_body, not the id.
    initiative_id = f"99{r['id']}"
    closing = r.get("document_date")
    end_date = closing.date() if closing else None
    facts = parse_body_facts(r.get("body_txt") or "")
    status = _status(closing, facts.get("status"))
    start_date = _as_date(facts.get("start"))
    title, description = _best_title(r["title"], r.get("summary") or "")
    areas = classify(title, r.get("summary") or "")

    existing = db.query(PublicConsultation).filter(
        PublicConsultation.initiative_id == initiative_id).first()
    if existing:
        changed = False
        for f, v in (("title", title), ("end_date", end_date), ("status", status),
                     ("start_date", start_date), ("portal_url", r.get("public_url"))):
            if v is not None and getattr(existing, f) != v:
                setattr(existing, f, v); changed = True
        # description may legitimately become None (when the title now IS the
        # former summary), so set it unconditionally rather than skipping None.
        if existing.description != description:
            existing.description = description; changed = True
        if areas and existing.policy_areas != areas:
            existing.policy_areas = areas; changed = True
        if existing.source != "agency" or existing.source_body != body:
            existing.source = "agency"; existing.source_body = body; changed = True
        return "updated" if changed else "skipped"

    db.add(PublicConsultation(
        initiative_id=initiative_id,
        title=title,
        description=description,
        consultation_type=ConsultationTypeEnum.PUBLIC_CONSULTATION,
        status=status,
        dg_responsible=None,
        policy_areas=areas,
        start_date=start_date,
        end_date=end_date,
        feedback_count=0,
        portal_url=r.get("public_url"),
        feedback_url=r.get("public_url"),
        source="agency",
        source_body=body,
    ))
    return "added"


def main():
    db = SessionLocal()
    counts = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}
    try:
        rows = _rows(db)
        print(f"[agency_consultations] {len(rows)} agency consultation rows in economy_items")
        for r in rows:
            try:
                counts[_upsert(db, r)] += 1
            except Exception as e:
                db.rollback(); print(f"  upsert failed {r['id']}: {e}"); counts["errors"] += 1
        db.commit()
    finally:
        db.close()
    print("[agency_consultations]", " ".join(f"{k}={v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
