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


# The TED notices the F&T Portal also lists sit in ft_calls_for_tenders under their TED number,
# with a TED link, the portal's flag and no deadline: on 28 Oct 2026 all 386 said "open" while the
# TED table held 205 of them closed (O96). The TED row owns their deadline and status (the ingester
# leaves both alone on such rows); ft_calls_for_tenders.deadline is UTC without a time zone.
_FT_COPY_DEADLINE = "(t.submission_deadline AT TIME ZONE 'UTC')"
_FT_COPIES = f"""t.publication_number = f.tender_reference AND f.source_url LIKE '%ted.europa.eu%'
      AND (f.status IS DISTINCT FROM t.status OR f.deadline IS DISTINCT FROM {_FT_COPY_DEADLINE})"""


def sync_ft_copies(db, *, apply: bool) -> Counter:
    """Give each TED notice in ft_calls_for_tenders the TED row's deadline and status; returns
    (old status, new status) -> count. A change is a real change, so content_updated_at moves."""
    stale = db.execute(text(
        f"SELECT f.id, f.status AS old, t.status AS new FROM ft_calls_for_tenders f, tenders t WHERE {_FT_COPIES}")).fetchall()
    if apply and stale:
        db.execute(text(
            f"UPDATE ft_calls_for_tenders f SET status = t.status, deadline = {_FT_COPY_DEADLINE}, "
            f"last_updated = now() FROM tenders t WHERE {_FT_COPIES}"))
        db.commit()
    return Counter((r.old, r.new) for r in stale)
