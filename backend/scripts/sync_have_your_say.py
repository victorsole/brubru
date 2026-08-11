"""Sync every Commission initiative from Have Your Say into public_consultations.

Have Your Say carries ~4,100 initiatives. Brubru held 362 of them, so a user tracking
a file could ask "is there a consultation on this?" and be told no when there was one.
The gap was found on 11 August 2026 looking for initiative 16116, the ESPR delegated
act on ecodesign requirements for apparel textiles: the single most relevant pipeline
item for a textile client, absent from a table holding 1,059 rows.

Source: the portal's own JSON API, /brpapi/searchInitiatives, paged. It returns the
id, reference, short title, foreseen act type, topics (which carry the lead DG code
and the policy area label) and currentStatuses (stage, feedback status and dates).

Mapping notes, all grounded in a survey of the live vocabulary rather than guessed:

  receivingFeedbackStatus  OPEN -> open, UPCOMING -> upcoming, CLOSED -> closed.
    DISABLED means the stage has no feedback period at all; such an initiative is
    reported as `upcoming` while it is still only planned (INIT_PLANNED) and `closed`
    once it has moved past that. The raw upstream stage and status are written into
    `description` so nothing is lost in the flattening.

  frontEndStage  OPC_LAUNCHED -> public_consultation, PLANNING_WORKFLOW ->
    call_for_evidence, everything else -> initiative.

Idempotent: public_consultations is UNIQUE on initiative_id, so every write upserts.
Rows sourced from agencies are keyed on a different id space and are never touched.

Usage:
    python3.12 -m backend.scripts.sync_have_your_say --dry-run
    python3.12 -m backend.scripts.sync_have_your_say --apply
    python3.12 -m backend.scripts.sync_have_your_say --apply --initiative 16116
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import requests
from sqlalchemy import text

from core.database import SessionLocal

API = "https://ec.europa.eu/info/law/better-regulation/brpapi/searchInitiatives"
DETAIL = "https://ec.europa.eu/info/law/better-regulation/brpapi/groupInitiatives/{id}"
PORTAL = ("https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/"
          "{id}-{slug}_en")
HEADERS = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/124.0.0.0 Safari/537.36"),
           "Accept": "application/json"}

_STATUS = {"OPEN": "open", "UPCOMING": "upcoming", "CLOSED": "closed"}
_TYPE = {"OPC_LAUNCHED": "public_consultation", "PLANNING_WORKFLOW": "call_for_evidence"}


def slugify(s: str, limit: int = 60) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", (s or "").lower()).strip("-")
    return s[:limit].rstrip("-")


def _parse_dt(v: Optional[str]) -> Optional[date]:
    if not v:
        return None
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, fmt).date()
        except ValueError:
            continue
    return None


def map_initiative(it: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    raw_id = it.get("id")
    if raw_id is None:
        return None
    iid = str(int(float(raw_id)))
    title = (it.get("shortTitle") or "").strip()
    if not title:
        return None

    statuses = it.get("currentStatuses") or []
    current = next((s for s in statuses if s.get("isCurrent")), statuses[0] if statuses else {})
    feedback = [s.get("receivingFeedbackStatus") for s in statuses]
    stage = current.get("frontEndStage") or ""

    if "OPEN" in feedback:
        status = "open"
    elif "UPCOMING" in feedback:
        status = "upcoming"
    elif "CLOSED" in feedback:
        status = "closed"
    else:
        # every stage DISABLED: still only planned, or already past feedback
        status = "upcoming" if stage == "INIT_PLANNED" else "closed"

    ctype = _TYPE.get(stage, "initiative")

    start = end = None
    for s in statuses:
        if s.get("receivingFeedbackStatus") in ("OPEN", "CLOSED", "UPCOMING"):
            start = start or _parse_dt(s.get("feedbackStartDate"))
            end = end or _parse_dt(s.get("feedbackEndDate"))

    topics = it.get("topics") or []
    dg = (topics[0].get("code") if topics else None) or None
    areas = [t.get("label") for t in topics if t.get("label")]

    desc = (f"Have Your Say initiative {iid}. Foreseen act type: "
            f"{it.get('foreseenActType') or 'not stated'}. Stage: {stage or 'not stated'}. "
            f"Feedback status upstream: {', '.join(x for x in feedback if x) or 'none'}. "
            f"Initiative status: {it.get('initiativeStatus') or 'not stated'}.")

    return {
        "initiative_id": iid,
        "title": title[:500],
        "short_title": title[:255],
        "description": desc,
        "consultation_type": ctype,
        "status": status,
        "dg_responsible": dg,
        "policy_areas": areas,
        "start_date": start,
        "end_date": end,
        "portal_url": PORTAL.format(id=iid, slug=slugify(title)),
        "source": "commission",
        "source_body": "European Commission",
        "relevance_score": 50,
    }


_UPSERT = text("""
    INSERT INTO public_consultations (
        initiative_id, title, short_title, description, consultation_type, status,
        dg_responsible, policy_areas, start_date, end_date, portal_url,
        source, source_body, relevance_score,
        created_at, updated_at, first_seen, last_updated, scraped_at
    ) VALUES (
        :initiative_id, :title, :short_title, :description,
        CAST(:consultation_type AS consultation_type_enum),
        CAST(:status AS consultation_status_enum),
        :dg_responsible, :policy_areas, :start_date, :end_date, :portal_url,
        :source, :source_body, :relevance_score,
        :now, :now, :now, :now, :now
    )
    ON CONFLICT (initiative_id) DO UPDATE SET
        title = EXCLUDED.title,
        short_title = EXCLUDED.short_title,
        description = EXCLUDED.description,
        consultation_type = EXCLUDED.consultation_type,
        status = EXCLUDED.status,
        dg_responsible = COALESCE(EXCLUDED.dg_responsible, public_consultations.dg_responsible),
        policy_areas = EXCLUDED.policy_areas,
        start_date = COALESCE(EXCLUDED.start_date, public_consultations.start_date),
        end_date = COALESCE(EXCLUDED.end_date, public_consultations.end_date),
        portal_url = EXCLUDED.portal_url,
        updated_at = EXCLUDED.updated_at,
        last_updated = EXCLUDED.last_updated,
        scraped_at = EXCLUDED.scraped_at
""")


def _fetch_page(page: int, page_size: int, attempts: int = 4) -> Optional[Dict[str, Any]]:
    """One page, retried. The portal returns a transient 500 now and then."""
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(API, params={"text": "*", "size": page_size, "page": page,
                                          "language": "EN"},
                             headers=HEADERS, timeout=60)
            r.raise_for_status()
            return r.json()["initiativeResultDtoPage"]
        except Exception as exc:  # noqa: BLE001
            if attempt == attempts:
                print(f"  [WARN] page {page} failed after {attempts} attempts: "
                      f"{type(exc).__name__}: {exc}")
                return None
            time.sleep(1.5 * attempt)
    return None


def fetch_all(page_size: int = 100, delay: float = 0.4) -> List[Dict[str, Any]]:
    """Page through every initiative.

    A failed page is skipped, never treated as the end of the run: the portal throws
    an intermittent 500 that succeeds on retry, and breaking out of the loop on it
    silently truncated the sweep to 700 of 4,091 records with no error.
    """
    out: List[Dict[str, Any]] = []
    failed: List[int] = []

    first = _fetch_page(0, page_size)
    if first is None:
        print("  [ERROR] could not fetch the first page; aborting")
        return []
    total_pages = first.get("totalPages") or 1
    print(f"  upstream: {first.get('totalElements')} initiatives across "
          f"{total_pages} pages of {page_size}")
    out.extend(first.get("content") or [])

    for page in range(1, total_pages):
        pg = _fetch_page(page, page_size)
        if pg is None:
            failed.append(page)
            continue
        out.extend(pg.get("content") or [])
        if (page + 1) % 10 == 0:
            print(f"    fetched {len(out)} ...")
        time.sleep(delay)

    if failed:
        print(f"  [WARN] {len(failed)} page(s) never returned: {failed}. "
              f"Coverage is incomplete; re-run to pick them up.")
    return out


def fetch_one(initiative_id: str) -> List[Dict[str, Any]]:
    """Fetch a single initiative via the detail endpoint, shaped like a search hit."""
    r = requests.get(DETAIL.format(id=initiative_id), headers=HEADERS, timeout=60)
    r.raise_for_status()
    d = r.json()
    pubs = d.get("publications") or []
    statuses = [{
        "frontEndStage": p.get("frontEndStage"),
        "receivingFeedbackStatus": p.get("receivingFeedbackStatus"),
        "feedbackStartDate": p.get("feedbackStartDate"),
        "feedbackEndDate": p.get("feedbackEndDate"),
        "isCurrent": p.get("frontEndStage") == d.get("stage"),
    } for p in pubs]
    return [{
        "id": float(initiative_id),
        "shortTitle": d.get("shortTitle"),
        "reference": d.get("reference"),
        "foreseenActType": d.get("foreseenActType"),
        "initiativeStatus": d.get("initiativeStatus"),
        "currentStatuses": statuses or [{
            "frontEndStage": d.get("stage"),
            "receivingFeedbackStatus": d.get("receivingFeedbackStatus"),
            "isCurrent": True,
        }],
        "topics": d.get("topics") or [],
    }]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--initiative", help="sync a single initiative id via the detail API")
    args = ap.parse_args()

    # Fetch BEFORE opening the database session. The full sweep spends minutes on
    # HTTP, and a session opened first is closed by the server underneath us: the
    # next statement then fails on a dead connection, which looks like a query bug
    # and rolls back the whole run before a single row is written.
    print("=== fetching Have Your Say ===")
    raw = fetch_one(args.initiative) if args.initiative else fetch_all()
    print(f"  fetched {len(raw)} initiative record(s)")

    db = SessionLocal()
    try:
        before = db.execute(
            text("SELECT count(*) FROM public_consultations WHERE source = 'commission'")
        ).scalar()
        print(f"\n=== before: {before} commission-sourced rows ===")

        rows, skipped = [], 0
        for it in raw:
            m = map_initiative(it)
            if m:
                rows.append(m)
            else:
                skipped += 1
        print(f"  mapped {len(rows)}, skipped {skipped} (no id or no title)")

        ids = [r["initiative_id"] for r in rows]
        dupes = len(ids) - len(set(ids))
        if dupes:
            print(f"  [WARN] {dupes} duplicate initiative_id in the fetch; last wins")
            dedup = {r["initiative_id"]: r for r in rows}
            rows = list(dedup.values())

        existing = set()
        if ids:
            existing = {
                r[0] for r in db.execute(
                    text("SELECT initiative_id FROM public_consultations "
                         "WHERE initiative_id = ANY(:ids)"), {"ids": ids}
                ).fetchall()
            }
        print(f"  already present: {len(existing)}   new: {len(rows) - len(existing)}")

        by_status: Dict[str, int] = {}
        for r in rows:
            by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        print(f"  status split: {by_status}")

        if args.dry_run:
            print("\n[DRY-RUN] nothing written")
            for r in rows[:3]:
                print(f"    {r['initiative_id']}: {r['title'][:60]} "
                      f"[{r['consultation_type']}/{r['status']}] dg={r['dg_responsible']}")
            return 0

        now = datetime.now(timezone.utc)
        written = 0
        for r in rows:
            db.execute(_UPSERT, {**r, "now": now})
            written += 1
            if written % 500 == 0:
                db.commit()
                print(f"    committed {written} ...")
        db.commit()
        print(f"\n[OK] upserted {written} rows")

        # ---- verification ----
        after = db.execute(
            text("SELECT count(*) FROM public_consultations WHERE source = 'commission'")
        ).scalar()
        total = db.execute(text("SELECT count(*) FROM public_consultations")).scalar()
        print("\n=== verification ===")
        print(f"  commission rows: {before} -> {after}   (+{after - before})")
        print(f"  table total    : {total}")
        missing = [i for i in ids if i not in {
            r[0] for r in db.execute(
                text("SELECT initiative_id FROM public_consultations "
                     "WHERE initiative_id = ANY(:ids)"), {"ids": ids}).fetchall()}]
        print(f"  fetched ids not stored: {len(missing)}   "
              f"{'OK' if not missing else 'FAIL ' + str(missing[:5])}")
        return 0 if not missing else 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
