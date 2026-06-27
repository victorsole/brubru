"""Phase 3, step 3.1 — deterministic procedure snapshot builder.

Given ONE LegislativeCarriage, produce its canonical daily-snapshot record:
  - SLOW state (read straight off the carriage row, which the sync services already keep
    as the merged canonical state): status, days-in-status, lead committee, rapporteur,
    text type, policy areas, celex, opinion-committee count, status-change count.
  - FAST-SIGNAL counts (the value the predictors are blind to), each COUNTed from its own
    source table via the documented join:
      num_amendments       amendments.carriage_id == id
      num_documents        commission_documents.legislative_carriage_id == id
      num_committee_work   committee_work_items.legislative_carriage_id == id
      num_lobby_meetings   mep_lobby_meetings.procedure_ref == oeil_procedure_ref   (no FK)
      num_eprs_briefings   eprs_publications.related_procedures @> [oeil_procedure_ref]

PURE READ — no writes, no DB schema, no cron. This is the single unit the Phase 3.2 daily
writer will persist into `procedure_snapshots`. Deterministic: same DB state -> identical
output (no LLM, no time-of-day dependence except the explicit `on` date).

Caveat surfaced by the data map: lobby + EPRS link by the OEIL ref string/array, not a
foreign key — so when a carriage has no `oeil_procedure_ref` those two counts are 0 and
the row is flagged `ref_linked=False` / `is_estimated=True` (honest, not fabricated).
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import func

from models.amendment import Amendment
from models.commission_document import CommissionDocument
from models.committee_work import CommitteeWorkItem
from models.eprs_publication import EPRSPublication
from models.legislative_train import LegislativeCarriage
from models.mep_lobby_meeting import MepLobbyMeeting


def _enum_val(v):
    return getattr(v, "value", v)


def build_snapshot(carriage: LegislativeCarriage, db, *, on: date | None = None) -> dict:
    """Return the canonical snapshot dict for one carriage. Pure read."""
    cid = carriage.id
    ref = carriage.oeil_procedure_ref

    def _count(model, *crit):
        return db.query(func.count(model.id)).filter(*crit).scalar() or 0

    num_amendments = _count(Amendment, Amendment.carriage_id == cid)
    num_documents = _count(CommissionDocument, CommissionDocument.legislative_carriage_id == cid)
    num_committee_work = _count(CommitteeWorkItem, CommitteeWorkItem.legislative_carriage_id == cid)

    # lobby + EPRS are linked only by the OEIL ref (no FK); 0 + flagged when absent.
    num_lobby_meetings = 0
    num_eprs_briefings = 0
    if ref:
        num_lobby_meetings = _count(MepLobbyMeeting, MepLobbyMeeting.procedure_ref == ref)
        # `ref = ANY(related_procedures)` — element-vs-array, avoids the text[] @> varchar[]
        # operator-type mismatch that `.contains([ref])` produces.
        num_eprs_briefings = _count(EPRSPublication, EPRSPublication.related_procedures.any(ref))

    return {
        "carriage_id": str(cid),
        "snapshot_date": (on or date.today()).isoformat(),
        "oeil_procedure_ref": ref,
        # --- slow state ---
        "current_status": _enum_val(carriage.current_status),
        "days_in_current_status": carriage.days_in_current_status or 0,
        "lead_committee": carriage.lead_committee,
        "rapporteur_mep_id": carriage.rapporteur_mep_id,
        "text_type": _enum_val(carriage.text_type),
        "policy_areas": list(carriage.policy_areas or []),
        "celex_numbers": list(carriage.celex_numbers or []),
        "num_opinion_committees": len(carriage.opinion_committees or []),
        "num_status_changes": len(carriage.status_history or []),
        # --- fast-signal counts ---
        "num_amendments": num_amendments,
        "num_documents": num_documents,
        "num_committee_work": num_committee_work,
        "num_lobby_meetings": num_lobby_meetings,
        "num_eprs_briefings": num_eprs_briefings,
        # --- reconciliation flags (honest) ---
        "ref_linked": ref is not None,   # lobby/eprs counts only meaningful with a ref
        "is_estimated": ref is None,     # ref-linked counts are 0/estimated without a ref
    }
