"""A partial listing is a partial run, not a dead one.

`parl_questions` failed on every run from 27 September: EP Open Data listed 3,090 questions
for 2026 while 3,603 were already stored, and the guard refused the read. Refusing was right
(a short listing must never pass as "0 new"), but the job then stored NOTHING, so genuinely
new questions went unread for days.

Measured on 28 September: the same listing returned 3,590. The truncation is transient, which
is exactly why aborting is the wrong response to it.

Three states now: a catastrophic read (under half of what is held) still fails, a shortfall
ingests what WAS listed and reports degraded, and a clean read succeeds.
"""
import pathlib
import re
import sys

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

_SOURCE = pathlib.Path(_BACKEND, "scripts", "ingest_parl_questions.py").read_text(encoding="utf-8")


def test_a_catastrophic_read_still_fails():
    """Under half of what is held is a broken read, not a partial one."""
    assert "0.5 * held_years" in _SOURCE, "the hard floor is gone"
    floor = _SOURCE.split("0.5 * held_years")[1][:400]
    assert "return 1" in floor, "a catastrophic read must still exit non-zero"


def test_a_shortfall_degrades_instead_of_aborting():
    block = _SOURCE.split("0.95 * held_years")[1][:500]
    assert "return 1" not in block.split("shortfall")[0], (
        "a shortfall must no longer abort: that is what stored nothing for days")
    assert "shortfall" in block


def test_the_shortfall_is_reported_as_degraded():
    """It must reach the run ledger, or the gap is invisible again."""
    assert re.search(r'\[SYNC_STATUS\] degraded: \{shortfall\}', _SOURCE), (
        "the shortfall must be emitted as [SYNC_STATUS] degraded, which api/cron.py reads")


def test_the_listing_walk_advances_by_what_it_received():
    """Measured 28 September: advancing by the RECEIVED length gives 3,090 unique ids;
    advancing by the requested limit gives 2,490 and skips items. The server loses rows under
    offset paging either way, so the safer of the two stays, and the listed count is not
    treated as ground truth."""
    assert "offset += len(page)" in _SOURCE, (
        "advancing by the requested limit was measured to skip ~600 questions")
