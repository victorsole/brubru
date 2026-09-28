"""A drain that restarts at page 0 never reaches the backlog.

`backfill_eu_comitology.py` walked the Commission register from page 0 on every run and the
900-second timeout killed it around page 120. It therefore re-read the same ~12,000 documents
three times a day, and the ~19,700 documents on later pages (95,461 of 115,206 stored) were
never visited once. Raising the timeout does not fix a job that always starts at the
beginning, which is why the fix is a cursor and a BUDGET rather than a bigger limit.

Measured 28 September 2026: run one read pages 0..8 and saved cursor 9; run two started at
page 9, read 9..16 and saved 17.
"""
import pathlib
import sys

import pytest

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_BACKEND), str(_BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

_SOURCE = pathlib.Path(_BACKEND, "scripts", "backfill_eu_comitology.py").read_text(encoding="utf-8")
_CRON = pathlib.Path(_BACKEND, "api", "cron.py").read_text(encoding="utf-8")


def test_the_drain_starts_from_its_cursor_not_from_zero():
    assert "read_cursor(db)" in _SOURCE, "the run must resume where the last one stopped"
    assert "page = 0 if dry_run else read_cursor(db)" in _SOURCE


def test_it_stops_on_its_own_budget():
    """A process killed by the timeout writes no cursor, so the next run starts over."""
    assert "max_seconds" in _SOURCE
    assert "budget" in _SOURCE.lower()
    budget_block = _SOURCE.split("if max_seconds and")[1][:400]
    assert "write_cursor" in budget_block, "stopping on the budget must SAVE the cursor"


def test_reaching_the_end_wraps_to_the_head():
    """Otherwise the drain finishes once and never picks up new documents."""
    last_block = _SOURCE.split('if payload.get("last", True):')[1][:300]
    assert "write_cursor(db, 0" in last_block, "the end of the register must wrap to page 0"


def test_the_budget_is_reported_as_degraded():
    assert "[SYNC_STATUS] degraded:" in _SOURCE, "a partial drain must reach the run ledger"


def test_the_scheduled_run_passes_a_budget_inside_its_timeout():
    """A budget larger than the timeout is the same bug with extra steps."""
    import re
    call = re.search(r'backfill_eu_comitology\.py".*?timeout=(\d+)', _CRON, re.S)
    assert call, "the scheduled call was not found"
    timeout = int(call.group(1))
    budget = re.search(r'"--max-seconds", "(\d+)"', call.group(0))
    assert budget, "the scheduled run must pass --max-seconds"
    assert int(budget.group(1)) < timeout, (
        f"budget {budget.group(1)}s must leave headroom inside the {timeout}s timeout")


def test_the_cursor_table_exists_and_is_granted():
    migration = pathlib.Path(_BACKEND, "migrations", "244_job_cursors.sql").read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "GRANT ALL ON public.job_cursors TO service_role" in migration, (
        "explicit grants are mandatory on new public.* tables; a replay breaks without them")


def test_the_cursor_is_checkpointed_periodically_not_only_at_the_end():
    """Saving only on the budget means a HARD stop loses everything since the last run.

    Observed while the catch-up drain ran: it had reached page 23 while the stored cursor
    still read 17, because the cursor was written only when the budget was hit. A machine
    sleeping or an OOM at minute 49 of a 50-minute run would have rewound ~500 pages. That is
    the same defect this fix exists to remove, one level down.
    """
    assert "CHECKPOINT_EVERY_PAGES" in _SOURCE
    assert "% CHECKPOINT_EVERY_PAGES == 0" in _SOURCE, "no periodic checkpoint"
    checkpoint = _SOURCE.split("% CHECKPOINT_EVERY_PAGES == 0")[1][:200]
    assert "write_cursor" in checkpoint


def test_the_checkpoint_saves_the_NEXT_page_not_the_one_just_read():
    """Saving the page just finished would re-read it on every resume."""
    checkpoint = _SOURCE.split("% CHECKPOINT_EVERY_PAGES == 0")[1][:200]
    assert "write_cursor(db, page + 1" in checkpoint, (
        "the cursor must point at the next page to read, or each resume repeats a page")
