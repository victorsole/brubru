"""The Brussels lobby corpus aged 108 days and nothing said so (24 September 2026).

`brussels_lobby_news_items` held 20,615 rows whose newest write was 8 June. The cause was
not a broken crawler: the crawler works (measured that morning, 20 organisations in 35
seconds, 214 items). The cause was that `sync_brussels_lobbies.py` had **no schedule** and
wrote **no run row**, so:

  * nothing ran it after the hand-seed on 8 June, and
  * /api/sync/health could not report it, because that endpoint can only speak about
    sources that record runs.

A source that records nothing is invisible whether it is healthy or dead, which is the
same shape as the guides that were on disk but untracked by git: the check that would
have caught it was never asked.

These tests hold the two halves in place: the job is registered on a tier, and a crawl
that checks nothing is recorded as a failure rather than a quiet day.
"""
from __future__ import annotations

import ast
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

BACKEND = pathlib.Path(__file__).resolve().parents[1]
CRON = (BACKEND / "api" / "cron.py").read_text(encoding="utf-8")
SCRIPT_PATH = BACKEND / "scripts" / "sync_brussels_lobbies.py"
SCRIPT = SCRIPT_PATH.read_text(encoding="utf-8")


def test_the_crawl_is_on_a_tier():
    assert "scripts/sync_brussels_lobbies.py" in CRON, (
        "the lobby crawl is not registered in api/cron.py: it will be run by hand, once, "
        "and the corpus will age silently again"
    )


def test_it_is_scheduled_to_refresh_not_only_to_fill_gaps():
    """Every crawlable profile was already checked, so a run without --recheck selects
    nothing: the first attempt that morning reported `checked=0` and stored nothing."""
    block = CRON[CRON.index("sync_brussels_lobbies.py"):][:400]
    assert "--recheck" in block, "without --recheck the nightly crawl selects 0 organisations"


def test_the_run_is_recorded_so_freshness_can_see_it():
    assert "record_run" in SCRIPT and "brussels_lobbies" in SCRIPT, (
        "the script must write a sync_runs row, or its silence stays unreadable"
    )


def test_a_crawl_that_checked_nothing_is_a_failure():
    """`checked=0` means the selection or the network is broken, never a quiet day: every
    crawlable profile can be re-checked. Recording it as success is how a dead job keeps
    a green light."""
    tree = ast.parse(SCRIPT)
    main = next(n for n in tree.body
                if isinstance(n, ast.FunctionDef) and n.name == "main")
    src = ast.get_source_segment(SCRIPT, main) or ""
    assert '"failed" if (error or not checked)' in src.replace("'", '"'), (
        "main() must mark a zero-check crawl as failed"
    )


def test_the_script_exits_non_zero_on_failure():
    """The cron reads the exit code; a script that always exits 0 reports success even
    when it recorded a failure."""
    assert "sys.exit(main())" in SCRIPT
    assert "return 1 if error else 0" in SCRIPT
