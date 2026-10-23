"""The status of an EU-funded project, in one vocabulary (23 Oct 2026).

Two writers filled ft_funded_projects.status with two vocabularies (CORDIS: closed, signed,
terminated; F&T Portal: Ended, Ongoing, Forthcoming, Suspended), and neither word was revisited:
"signed" spans projects not started, running and ended, and the F&T words were four months old.
The source word is kept in `source_status` (migration 311); the served status is set here.

    terminated (source)                          -> terminated  facts the dates cannot show
    Suspended (source)                           -> suspended   (all 9 on 23 Oct are past their end date)
    closed / Ended (source)                      -> ended       an early end (141 before their end date)
    start date ahead                             -> planned
    end date passed                              -> ended
    started, not ended                           -> ongoing
    no dates: Forthcoming -> planned, signed / Ongoing -> ongoing, otherwise unknown

`refresh` applies it in chunks by id, like the TED status pass; a status change is a real change,
so the row's last_updated moves.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import text

VOCABULARY = ("planned", "ongoing", "ended", "terminated", "suspended", "unknown")

STATUS_SQL = """CASE
    WHEN lower(source_status) = 'terminated' THEN 'terminated'
    WHEN lower(source_status) = 'suspended' THEN 'suspended'
    WHEN lower(source_status) IN ('closed', 'ended') THEN 'ended'
    WHEN start_date > CURRENT_DATE THEN 'planned'
    WHEN end_date < CURRENT_DATE THEN 'ended'
    WHEN start_date IS NOT NULL THEN 'ongoing'
    WHEN lower(source_status) = 'forthcoming' THEN 'planned'
    WHEN lower(source_status) IN ('signed', 'ongoing') THEN 'ongoing'
    ELSE 'unknown'
END"""


def refresh(db, *, apply: bool, chunk: int = 2000) -> Counter:
    """Set every project's status by the rule; returns (old, new) -> count."""
    stale = db.execute(text(
        f"SELECT id, status, {STATUS_SQL} AS derived FROM ft_funded_projects "
        f"WHERE status IS DISTINCT FROM ({STATUS_SQL}) ORDER BY id")).fetchall()
    moves = Counter((r.status, r.derived) for r in stale)
    if apply:
        ids = [str(r.id) for r in stale]          # uuid primary keys, cast back in SQL
        for i in range(0, len(ids), chunk):
            db.execute(text(
                f"UPDATE ft_funded_projects SET status = {STATUS_SQL} "
                f"WHERE id = ANY(CAST(:ids AS uuid[])) AND status IS DISTINCT FROM ({STATUS_SQL})"),
                {"ids": ids[i:i + chunk]})
            db.commit()
    return moves
