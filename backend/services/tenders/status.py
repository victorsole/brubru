"""The status of a TED notice, from its notice type and its own deadline (23 Oct 2026).

TED publishes no status. Every notice was stored "open" at insert and never revisited, so on
23 Oct 28,032 notices still said "open" after their deadline (27,937 calls for competition,
growing every day), and all 104 contract-award notices said "open" though an award ends the
competition. One rule, as for the F&T calls: the dates decide.

    award (result) and contract-modification notices  -> closed
    no deadline: prior information (planning)          -> forthcoming; any other type keeps its status
    deadline passed                                    -> closed
    deadline ahead                                     -> open (a prior information notice with a
                                                          deadline is used as the call itself)

`refresh` applies it in chunks by id, so a backlog never holds one long transaction on a table
the API reads; a status change is a real change, so the row's updated_at moves.
"""
from __future__ import annotations

from collections import Counter

from sqlalchemy import text

STATUS_SQL = """CASE
    WHEN form_type IN ('result', 'cont-modif') THEN 'closed'
    WHEN submission_deadline IS NULL THEN
        CASE WHEN form_type = 'planning' THEN 'forthcoming' ELSE status END
    WHEN submission_deadline < now() THEN 'closed'
    ELSE 'open'
END"""


def refresh(db, *, apply: bool, chunk: int = 1000) -> Counter:
    """Set every notice's status by the rule; returns (old, new) -> count."""
    stale = db.execute(text(
        f"SELECT id, status, {STATUS_SQL} AS derived FROM tenders "
        f"WHERE status IS DISTINCT FROM ({STATUS_SQL}) ORDER BY id")).fetchall()
    moves = Counter((r.status, r.derived) for r in stale)
    if apply:
        ids = [r.id for r in stale]
        for i in range(0, len(ids), chunk):
            db.execute(text(
                f"UPDATE tenders SET status = {STATUS_SQL} "
                f"WHERE id = ANY(:ids) AND status IS DISTINCT FROM ({STATUS_SQL})"),
                {"ids": ids[i:i + chunk]})
            db.commit()
    return moves
