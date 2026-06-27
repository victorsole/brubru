"""Phase 3, step 3.1 — deterministic procedure snapshot builder.

Given ONE LegislativeCarriage, produce its canonical daily-snapshot record:
  - SLOW state (read straight off the carriage row, which the sync services already keep
    as the merged canonical state): status, days-in-status, lead committee, rapporteur,
    text type, policy areas, celex, opinion-committee count, status-change count.
  - FAST-SIGNAL counts (the value the predictors are blind to), each COUNTed from its own
    source table via the join that is ACTUALLY populated (verified against the live DB —
    the obvious FK joins for documents/amendments are unpopulated and silently return 0):
      num_amendments       mep_amendments.procedure_reference == oeil_procedure_ref  (58k rows)
      num_documents        commission_documents.celex IN carriage.celex_numbers
      num_committee_work   committee_work_items.legislative_carriage_id == id        (FK ok)
      num_lobby_meetings   mep_lobby_meetings.procedure_ref == oeil_procedure_ref    (no FK)
      num_eprs_briefings   eprs_publications.related_procedures @> [ref]  (empty estate-wide -> 0)

PURE READ — no writes, no DB schema, no cron. This is the single unit the Phase 3.2 daily
writer will persist into `procedure_snapshots`. Deterministic: same DB state -> identical
output (no LLM, no time-of-day dependence except the explicit `on` date).

Caveat surfaced by the data map: lobby + EPRS link by the OEIL ref string/array, not a
foreign key — so when a carriage has no `oeil_procedure_ref` those two counts are 0 and
the row is flagged `ref_linked=False` / `is_estimated=True` (honest, not fabricated).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import func

from models.commission_document import CommissionDocument
from models.committee_work import CommitteeWorkItem
from models.eprs_publication import EPRSPublication
from models.legislative_train import LegislativeCarriage
from models.mep_amendment import MEPAmendment
from models.mep_lobby_meeting import MepLobbyMeeting


def _enum_val(v):
    return getattr(v, "value", v)


def _last_event_date(events) -> date | None:
    """Most recent parseable date in oeil_key_events (the latest procedural milestone)."""
    best = None
    for ev in events or []:
        raw = (ev or {}).get("date")
        if not raw:
            continue
        try:
            d = datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        if best is None or d > best:
            best = d
    return best


def build_snapshot(carriage: LegislativeCarriage, db, *, on: date | None = None) -> dict:
    """Return the canonical snapshot dict for one carriage. Pure read."""
    cid = carriage.id
    ref = carriage.oeil_procedure_ref
    snap_date = on or date.today()

    def _count(model, *crit):
        return db.query(func.count(model.id)).filter(*crit).scalar() or 0

    # committee work links by the populated FK.
    num_committee_work = _count(CommitteeWorkItem, CommitteeWorkItem.legislative_carriage_id == cid)

    # Commission documents link by CELEX, NOT by legislative_carriage_id (that FK is
    # unpopulated estate-wide — joining it silently returns 0). Verified: the celex join
    # lights up 334 carriages, the FK join 0.
    celex = list(carriage.celex_numbers or [])
    num_documents = _count(CommissionDocument, CommissionDocument.celex.in_(celex)) if celex else 0

    # amendments + lobby + EPRS link by the OEIL procedure ref string (no FK); 0 + flagged
    # when the carriage has no ref. Amendments live in mep_amendments (58k rows keyed by
    # procedure_reference) — NOT the 68-row internal `amendments` table the FK pointed at.
    num_amendments = num_lobby_meetings = num_eprs_briefings = 0
    if ref:
        num_amendments = _count(MEPAmendment, MEPAmendment.procedure_reference == ref)
        num_lobby_meetings = _count(MepLobbyMeeting, MepLobbyMeeting.procedure_ref == ref)
        # `ref = ANY(related_procedures)` — element-vs-array, avoids the text[] @> varchar[]
        # mismatch. NOTE: related_procedures is empty across all 429 EPRS rows today, so this
        # is an honest 0 (known data gap) until the EPRS→procedure linkage is populated.
        num_eprs_briefings = _count(EPRSPublication, EPRSPublication.related_procedures.any(ref))

    # carriage.days_in_current_status is unpopulated estate-wide (0/2237); derive the
    # timing signal from the latest OEIL milestone instead (days since last event).
    last_ev = _last_event_date(carriage.oeil_key_events)
    days_in_status = (snap_date - last_ev).days if last_ev else (carriage.days_in_current_status or 0)

    return {
        "carriage_id": str(cid),
        "snapshot_date": snap_date.isoformat(),
        "oeil_procedure_ref": ref,
        # --- slow state ---
        "current_status": _enum_val(carriage.current_status),
        "days_in_current_status": max(days_in_status, 0),
        "lead_committee": carriage.lead_committee,
        "rapporteur_mep_id": carriage.rapporteur_mep_id,
        "text_type": _enum_val(carriage.text_type),
        "policy_areas": list(carriage.policy_areas or []),
        "celex_numbers": list(carriage.celex_numbers or []),
        "num_opinion_committees": len(carriage.opinion_committees or []),
        # real procedural-event count: oeil_key_events is the populated source
        # (status_history exists but is empty across the whole table).
        "num_status_changes": len(carriage.oeil_key_events or carriage.status_history or []),
        # --- fast-signal counts ---
        "num_amendments": num_amendments,
        "num_documents": num_documents,
        "num_committee_work": num_committee_work,
        "num_lobby_meetings": num_lobby_meetings,
        "num_eprs_briefings": num_eprs_briefings,
        # --- reconciliation flags (honest) ---
        "ref_linked": ref is not None,   # lobby/eprs counts only meaningful with a ref
        "is_estimated": ref is None,     # ref-linked counts are 0/estimated without a ref
        "snapshot_source": "daily",      # fully measured live (vs reconstructed 'bootstrap')
    }
