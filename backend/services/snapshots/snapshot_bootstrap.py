"""Phase 3, step 3.4 — bootstrap the historical snapshot cube from OEIL events.

The daily writer only accumulates from today forward, so the count/timing trajectories
would cold-start. This seeds the *procedural-event* timeline from `oeil_key_events`
(populated for ~815 carriages), which carries genuine dated milestones
`[{date, event_type, description}]`.

What is reconstructed TRUTHFULLY (per historical event date):
  - num_status_changes  = cumulative count of events on/before that date
  - days_in_current_status = days since the previous event (timing between milestones)
  - snapshot_date       = the event date itself

What is NOT historically knowable, so deliberately NOT fabricated:
  - the five fast-signal counts (amendments/documents/committee_work/lobby/eprs). These are
    left 0 and the row is tagged snapshot_source='bootstrap' + is_estimated=True so a
    count-trajectory consumer filters to snapshot_source='daily', while a status/timing
    consumer can use every row. (See feedback_backfill_no_hallucination.)

Slow metadata (lead_committee, rapporteur, policy_areas, celex, text_type) is carried from
the CURRENT carriage row — we have no historical version of it — so it is a best-effort
label on the historical row, never invented. current_status is the exception: it is set to
NULL on bootstrap rows because the carriage's present status (often terminal, e.g. 'adopted')
would be a false assertion on a past date.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models.legislative_train import LegislativeCarriage
from models.procedure_snapshot import ProcedureSnapshot
from services.snapshots.snapshot_writer import _REFRESH_COLS

logger = logging.getLogger("snapshot-bootstrap")


def _enum_val(v):
    return getattr(v, "value", v)


def _event_date(ev) -> date | None:
    raw = (ev or {}).get("date")
    if not raw:
        return None
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _carriage_bootstrap_rows(c: LegislativeCarriage) -> list[dict]:
    """One snapshot dict per distinct OEIL-event date for this carriage (chronological)."""
    events = c.oeil_key_events or []
    dated = sorted(
        ((d, ev) for ev in events if (d := _event_date(ev)) is not None),
        key=lambda t: t[0],
    )
    if not dated:
        return []

    ref = c.oeil_procedure_ref
    rows: list[dict] = []
    prev_date: date | None = None
    cum = 0
    last_for_date: dict[date, dict] = {}
    for d, _ev in dated:
        cum += 1
        days_since_prev = (d - prev_date).days if prev_date else 0
        last_for_date[d] = {
            "carriage_id": str(c.id),
            "snapshot_date": d.isoformat(),
            "oeil_procedure_ref": ref,
            # historical status is NOT known from the event list — do NOT assert the
            # carriage's CURRENT (often terminal, e.g. 'adopted') status on a past date.
            "current_status": None,
            # for bootstrap rows this is days SINCE THE PREVIOUS MILESTONE (a real timing
            # signal), not "days in status" — disambiguated by snapshot_source='bootstrap'.
            "days_in_current_status": max(days_since_prev, 0),
            "lead_committee": c.lead_committee,
            "rapporteur_mep_id": c.rapporteur_mep_id,
            "text_type": _enum_val(c.text_type),
            "policy_areas": list(c.policy_areas or []),
            "celex_numbers": list(c.celex_numbers or []),
            "num_opinion_committees": len(c.opinion_committees or []),
            "num_status_changes": cum,          # REAL cumulative event count to this date
            # fast counts NOT historically knowable -> 0, flagged below (no fabrication)
            "num_amendments": 0,
            "num_documents": 0,
            "num_committee_work": 0,
            "num_lobby_meetings": 0,
            "num_eprs_briefings": 0,
            "ref_linked": ref is not None,
            "is_estimated": True,               # counts unmeasured at this historical date
            "snapshot_source": "bootstrap",
        }
        prev_date = d
    # collapse to one row per date (last event wins -> highest cumulative count that day)
    rows = [last_for_date[d] for d in sorted(last_for_date)]
    return rows


def bootstrap_from_oeil_events(
    db: Session,
    *,
    only: str | None = None,
    limit: int | None = None,
    batch_size: int = 200,
    dry_run: bool = False,
) -> dict:
    """Seed historical 'bootstrap' snapshots from oeil_key_events. Idempotent.

    Never overwrites a 'daily' (measured) row for the same (carriage, date): the upsert
    only refreshes when the existing row is itself a bootstrap row.
    """
    q = db.query(LegislativeCarriage).filter(LegislativeCarriage.oeil_key_events.isnot(None))
    if only:
        q = q.filter(LegislativeCarriage.oeil_procedure_ref == only)
    if limit:
        q = q.limit(limit)
    carriages = q.all()

    carriages_with_events = rows_written = 0
    pending = 0
    for c in carriages:
        rows = _carriage_bootstrap_rows(c)
        if not rows:
            continue
        carriages_with_events += 1
        if dry_run:
            rows_written += len(rows)
            continue
        for snap in rows:
            stmt = pg_insert(ProcedureSnapshot).values(**snap)
            stmt = stmt.on_conflict_do_update(
                constraint="procedure_snapshots_carriage_date_uq",
                set_={col: getattr(stmt.excluded, col) for col in _REFRESH_COLS},
                # only refresh if the existing row is a bootstrap row -> never clobber a
                # measured daily snapshot that happens to share a date
                where=(ProcedureSnapshot.snapshot_source == "bootstrap"),
            )
            db.execute(stmt)
            rows_written += 1
            pending += 1
            if pending >= batch_size:
                db.commit()
                pending = 0

    if not dry_run and pending:
        db.commit()

    result = {
        "carriages_scanned": len(carriages),
        "carriages_with_events": carriages_with_events,
        "rows_written": rows_written,
        "dry_run": dry_run,
    }
    logger.info("oeil bootstrap done: %s", result)
    return result
