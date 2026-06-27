"""Phase 3, step 3.3 — the daily procedure-snapshot writer.

Iterates the legislative carriages, builds each one's canonical snapshot via
services.snapshots.snapshot_builder.build_snapshot (pure read), and UPSERTs one row
per (carriage_id, snapshot_date) into `procedure_snapshots`.

Idempotent: re-running for the same `on` date refreshes the existing row (ON CONFLICT
DO UPDATE) and bumps updated_at — so a cron retry or a same-day re-run never duplicates.
ALL carriages are snapshotted, not only OEIL-linked ones: build_snapshot flags the
ref-less rows `is_estimated=True` (lobby/EPRS counts 0) rather than fabricating, so the
time-series stays complete and honest.
"""
from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from models.legislative_train import LegislativeCarriage
from models.procedure_snapshot import ProcedureSnapshot
from services.snapshots.snapshot_builder import build_snapshot

logger = logging.getLogger("snapshot-writer")

# columns the upsert refreshes on conflict (everything except identity + created_at)
_REFRESH_COLS = [
    "oeil_procedure_ref", "current_status", "days_in_current_status", "lead_committee",
    "rapporteur_mep_id", "text_type", "policy_areas", "celex_numbers",
    "num_opinion_committees", "num_status_changes", "num_amendments", "num_documents",
    "num_committee_work", "num_lobby_meetings", "num_eprs_briefings",
    "ref_linked", "is_estimated", "snapshot_source",
]


def write_daily_snapshots(
    db: Session,
    *,
    on: date | None = None,
    only: str | None = None,
    limit: int | None = None,
    batch_size: int = 200,
    dry_run: bool = False,
) -> dict:
    """Build + upsert a snapshot for every carriage for `on` (default today).

    Returns {"total", "written", "errors", "estimated", "dry_run"}.
    """
    on = on or date.today()
    q = db.query(LegislativeCarriage)
    if only:
        q = q.filter(LegislativeCarriage.oeil_procedure_ref == only)
    if limit:
        q = q.limit(limit)
    carriages = q.all()

    total = len(carriages)
    written = errors = estimated = 0
    pending = 0
    logger.info("snapshotting %d carriages for %s%s", total, on, " (dry-run)" if dry_run else "")

    for c in carriages:
        try:
            snap = build_snapshot(c, db, on=on)
        except Exception:  # one bad carriage must not abort the whole run
            errors += 1
            logger.exception("build_snapshot failed for carriage %s", c.id)
            continue

        if snap["is_estimated"]:
            estimated += 1
        if dry_run:
            written += 1
            continue

        stmt = pg_insert(ProcedureSnapshot).values(**snap)
        stmt = stmt.on_conflict_do_update(
            constraint="procedure_snapshots_carriage_date_uq",
            set_={col: getattr(stmt.excluded, col) for col in _REFRESH_COLS} | {"updated_at": func.now()},
        )
        db.execute(stmt)
        written += 1
        pending += 1
        if pending >= batch_size:
            db.commit()
            pending = 0

    if not dry_run and pending:
        db.commit()

    result = {"total": total, "written": written, "errors": errors,
              "estimated": estimated, "dry_run": dry_run, "on": on.isoformat()}
    logger.info("snapshot run done: %s", result)
    return result
