"""A body that can be synced and is in no batch is manually syncable and never refreshed.

This has now happened twice. In June 2026 `rail` and `sesar` were in sync_economy's INGESTORS
and absent from every window in `api/cron.py::_ECONOMY_BATCHES`. On 28 September 2026
`interoperable` and `eugovtech` were found the same way, last fetched 17 August, six weeks
stale, while their scrapers worked perfectly the moment they were run by hand.

The remedy was written down after the first time, as an audit to remember to run. It was not
run. So it is a test.
"""
import pathlib
import sys

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from api.cron import _ECONOMY_BATCHES  # noqa: E402
from scripts.sync_economy import INGESTORS  # noqa: E402

# `commission` is deliberately excluded from the batches: its sources run on the daily and
# weekly tiers through their own backfill scripts.
_NOT_BATCHED_BY_DESIGN = {"commission"}


def _scheduled() -> set[str]:
    return {code for batch in _ECONOMY_BATCHES for code in batch}


def _ingestable() -> set[str]:
    return {code for code, _ in INGESTORS}


def test_every_ingestable_body_runs_in_some_batch():
    missing = sorted(_ingestable() - _scheduled() - _NOT_BATCHED_BY_DESIGN)
    assert not missing, (
        f"{len(missing)} body/bodies can be synced but are in no cron batch, so nothing ever "
        f"refreshes them: {missing}. Add each to a window in api/cron.py::_ECONOMY_BATCHES.")


def test_no_batch_schedules_a_body_that_cannot_be_synced():
    """The other direction: a typo in a batch is a body that silently never runs."""
    orphans = sorted(_scheduled() - _ingestable() - _NOT_BATCHED_BY_DESIGN)
    assert not orphans, f"scheduled but not in INGESTORS (typo?): {orphans}"


def test_the_windows_stay_balanced():
    """Three windows exist to spread the scraper load; one must not become the dumping ground."""
    sizes = [len(batch) for batch in _ECONOMY_BATCHES]
    assert len(sizes) == 3, f"expected 3 windows, found {len(sizes)}"
    assert max(sizes) - min(sizes) <= 6, f"windows are lopsided: {sizes}"
