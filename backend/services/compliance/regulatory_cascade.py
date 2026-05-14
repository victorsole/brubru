"""
Regulatory cascade for an EU primary act.

Given a legislative carriage or CELEX, surfaces the *tree* of regulatory work
that hangs off it:
  - Secondary acts (implementing + delegated) authored under the parent act
  - Related in-flight files in the same policy areas (proxy for "regulatory
    neighbourhood")
  - Member State transposition deadlines, only when we have them in the data

The cascade never fabricates branches: if we have no secondary acts, we say
so; if we have no transposition data, we omit that section honestly rather
than inventing the standard 24-month default. Honest empty states beat
plausible-looking nothing.

Built for the EU Law Comply "P3 regulatory cascade" workstream (May 2026).
See memory/project_resilinc_eu_law_comply_assessment.md for the design
brief.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Iterable, List, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.legislative_train import LegislativeCarriage


logger = logging.getLogger(__name__)


RELATED_LOOKBACK_DAYS = 365 * 3  # 3 years
RELATED_LIMIT = 8
SECONDARY_ACT_LIMIT = 20


@dataclass
class SecondaryActItem:
    secondary_act_id: str
    act_type: str  # 'implementing' | 'delegated'
    reference: Optional[str]
    title: str
    status: Optional[str]  # 'adopted' | 'draft'
    publication_date: Optional[date]
    objection_deadline: Optional[date]
    pdf_url: Optional[str]
    source_url: Optional[str]
    proposing_dg: Optional[str]


@dataclass
class RelatedFileItem:
    carriage_id: str
    title: str
    procedure_ref: Optional[str]
    current_status: Optional[str]
    lead_committee: Optional[str]
    shared_policy_areas: List[str] = field(default_factory=list)
    first_seen: Optional[datetime] = None


@dataclass
class CascadeCounts:
    implementing_adopted: int = 0
    implementing_draft: int = 0
    delegated_adopted: int = 0
    delegated_draft: int = 0
    related_in_flight: int = 0


@dataclass
class RegulatoryCascade:
    procedure_ref: Optional[str]
    title: str
    celex_numbers: List[str] = field(default_factory=list)
    counts: CascadeCounts = field(default_factory=CascadeCounts)
    implementing_acts: List[SecondaryActItem] = field(default_factory=list)
    delegated_acts: List[SecondaryActItem] = field(default_factory=list)
    related_files: List[RelatedFileItem] = field(default_factory=list)
    # Honest absence flags — frontend renders explicit "no data yet"
    # sections instead of fabricating placeholders.
    transposition_data_available: bool = False
    cen_standards_data_available: bool = False

    def to_dict(self) -> dict:
        return {
            "procedure_ref": self.procedure_ref,
            "title": self.title,
            "celex_numbers": self.celex_numbers,
            "counts": {
                "implementing_adopted": self.counts.implementing_adopted,
                "implementing_draft": self.counts.implementing_draft,
                "delegated_adopted": self.counts.delegated_adopted,
                "delegated_draft": self.counts.delegated_draft,
                "related_in_flight": self.counts.related_in_flight,
            },
            "implementing_acts": [
                {
                    "id": s.secondary_act_id,
                    "act_type": s.act_type,
                    "reference": s.reference,
                    "title": s.title,
                    "status": s.status,
                    "publication_date": (
                        s.publication_date.isoformat() if s.publication_date else None
                    ),
                    "objection_deadline": (
                        s.objection_deadline.isoformat() if s.objection_deadline else None
                    ),
                    "pdf_url": s.pdf_url,
                    "source_url": s.source_url,
                    "proposing_dg": s.proposing_dg,
                }
                for s in self.implementing_acts
            ],
            "delegated_acts": [
                {
                    "id": s.secondary_act_id,
                    "act_type": s.act_type,
                    "reference": s.reference,
                    "title": s.title,
                    "status": s.status,
                    "publication_date": (
                        s.publication_date.isoformat() if s.publication_date else None
                    ),
                    "objection_deadline": (
                        s.objection_deadline.isoformat() if s.objection_deadline else None
                    ),
                    "pdf_url": s.pdf_url,
                    "source_url": s.source_url,
                    "proposing_dg": s.proposing_dg,
                }
                for s in self.delegated_acts
            ],
            "related_files": [
                {
                    "carriage_id": r.carriage_id,
                    "title": r.title,
                    "procedure_ref": r.procedure_ref,
                    "current_status": r.current_status,
                    "lead_committee": r.lead_committee,
                    "shared_policy_areas": r.shared_policy_areas,
                    "first_seen": r.first_seen.isoformat() if r.first_seen else None,
                }
                for r in self.related_files
            ],
            "transposition_data_available": self.transposition_data_available,
            "cen_standards_data_available": self.cen_standards_data_available,
        }


def _enum_str(value) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "value"):
        return str(value.value)
    return str(value)


def _normalise_celex_numbers(carriage: LegislativeCarriage) -> List[str]:
    raw = carriage.celex_numbers or []
    if isinstance(raw, str):
        raw = [raw]
    return [str(c).strip() for c in raw if c and str(c).strip()]


def _fetch_secondary_acts(
    db: Session, celex_numbers: Iterable[str]
) -> List[SecondaryActItem]:
    celex_list = [c for c in celex_numbers if c]
    if not celex_list:
        return []
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    id::text          AS secondary_act_id,
                    act_type,
                    reference,
                    title,
                    status,
                    publication_date,
                    objection_deadline,
                    pdf_url,
                    source_url,
                    proposing_dg
                FROM secondary_acts
                WHERE parent_celex = ANY(CAST(:celex_list AS text[]))
                ORDER BY
                    CASE WHEN status = 'draft' THEN 0 ELSE 1 END,
                    publication_date DESC NULLS LAST,
                    objection_deadline DESC NULLS LAST
                LIMIT :limit
                """
            ),
            {"celex_list": celex_list, "limit": SECONDARY_ACT_LIMIT * 2},
        ).mappings().all()
    except Exception as exc:
        logger.warning("secondary_acts fetch failed: %s", exc)
        db.rollback()
        return []

    out: List[SecondaryActItem] = []
    for row in rows:
        out.append(
            SecondaryActItem(
                secondary_act_id=row["secondary_act_id"],
                act_type=_enum_str(row["act_type"]) or "unknown",
                reference=row.get("reference"),
                title=row.get("title") or "",
                status=_enum_str(row.get("status")),
                publication_date=row.get("publication_date"),
                objection_deadline=row.get("objection_deadline"),
                pdf_url=row.get("pdf_url"),
                source_url=row.get("source_url"),
                proposing_dg=row.get("proposing_dg"),
            )
        )
    return out


def _fetch_related_files(
    db: Session,
    carriage_id: str,
    policy_areas: Iterable[str],
) -> List[RelatedFileItem]:
    pa_list = [str(p).strip() for p in policy_areas if p and str(p).strip()]
    if not pa_list:
        return []
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    id::text                AS carriage_id,
                    title,
                    oeil_procedure_ref      AS procedure_ref,
                    current_status,
                    lead_committee,
                    policy_areas,
                    first_seen
                FROM legislative_carriages
                WHERE id::text != :exclude_id
                  AND first_seen >= CURRENT_DATE - (INTERVAL '1 day' * :lookback)
                  AND policy_areas::text[] && CAST(:policy_areas AS text[])
                ORDER BY first_seen DESC
                LIMIT :limit
                """
            ),
            {
                "exclude_id": carriage_id,
                "lookback": RELATED_LOOKBACK_DAYS,
                "policy_areas": pa_list,
                "limit": RELATED_LIMIT,
            },
        ).mappings().all()
    except Exception as exc:
        logger.warning("related files fetch failed: %s", exc)
        db.rollback()
        return []

    out: List[RelatedFileItem] = []
    pa_set = {p.lower() for p in pa_list}
    for row in rows:
        their_areas = [str(p) for p in (row.get("policy_areas") or [])]
        shared = [a for a in their_areas if a.lower() in pa_set]
        out.append(
            RelatedFileItem(
                carriage_id=row["carriage_id"],
                title=row.get("title") or "",
                procedure_ref=row.get("procedure_ref"),
                current_status=_enum_str(row.get("current_status")),
                lead_committee=row.get("lead_committee"),
                shared_policy_areas=shared,
                first_seen=row.get("first_seen"),
            )
        )
    return out


def compose_regulatory_cascade(
    db: Session, carriage: LegislativeCarriage
) -> RegulatoryCascade:
    celex_numbers = _normalise_celex_numbers(carriage)

    secondary_acts = _fetch_secondary_acts(db, celex_numbers)
    implementing = [s for s in secondary_acts if s.act_type == "implementing"]
    delegated = [s for s in secondary_acts if s.act_type == "delegated"]

    # Cap at SECONDARY_ACT_LIMIT each (we fetched 2× the limit; the
    # split between implementing / delegated determines real counts)
    implementing = implementing[:SECONDARY_ACT_LIMIT]
    delegated = delegated[:SECONDARY_ACT_LIMIT]

    counts = CascadeCounts(
        implementing_adopted=sum(1 for s in implementing if s.status == "adopted"),
        implementing_draft=sum(1 for s in implementing if s.status == "draft"),
        delegated_adopted=sum(1 for s in delegated if s.status == "adopted"),
        delegated_draft=sum(1 for s in delegated if s.status == "draft"),
    )

    related = _fetch_related_files(
        db,
        carriage_id=str(carriage.id),
        policy_areas=carriage.policy_areas or [],
    )
    counts.related_in_flight = sum(
        1
        for r in related
        if (r.current_status or "").lower()
        not in {"adopted", "completed", "withdrawn"}
    )

    return RegulatoryCascade(
        procedure_ref=carriage.oeil_procedure_ref,
        title=carriage.title,
        celex_numbers=celex_numbers,
        counts=counts,
        implementing_acts=implementing,
        delegated_acts=delegated,
        related_files=related,
        # We don't yet ingest Member State transposition deadlines or
        # CEN/CENELEC standard revisions. Surface these flags so the
        # frontend can render an honest "data coming soon" pane rather
        # than fabricating defaults.
        transposition_data_available=False,
        cen_standards_data_available=False,
    )
