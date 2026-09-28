"""Remember, per process, that Scrape.do has run out of monthly requests.

The account is a 1,000-request monthly plan (measured 28 Sep 2026 via
`api.scrape.do/info`: MaxMonthlyRequest 1000, RemainingMonthlyRequest 0), not
the 250,000 the scraper docstrings assumed. Once it is spent, every call answers
HTTP 401 "Monthly request limit exceeded" until the period resets. Asking again
for every document costs a round trip each and, worse, reads in the logs as a
string of separate failures. So the first 401 of that kind trips this flag and
callers go straight to the free browser fallback.

The flag expires after ``_HOLD_S`` so a long-running worker notices a reset or
a top-up without a restart.
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)

_HOLD_S = 6 * 3600
_exhausted_until = 0.0


def is_exhausted() -> bool:
    """True while a recent response said the monthly quota is spent."""
    return time.monotonic() < _exhausted_until


def looks_exhausted(status: int | None, body: bytes | str | None) -> bool:
    """Whether a Scrape.do response is the quota refusal (not a target failure)."""
    if status != 401:
        return False
    text = body.decode("utf-8", "replace") if isinstance(body, bytes) else (body or "")
    return "limit exceeded" in text.lower()


def note(status: int | None, body: bytes | str | None) -> bool:
    """Record a response; trips the flag on a quota refusal. Returns True if it did."""
    global _exhausted_until
    if looks_exhausted(status, body):
        if not is_exhausted():
            logger.warning("[scrapedo] monthly request limit exceeded; using the free "
                           "browser fallback for the next %d h", _HOLD_S // 3600)
        _exhausted_until = time.monotonic() + _HOLD_S
        return True
    return False


def reset() -> None:
    """For tests."""
    global _exhausted_until
    _exhausted_until = 0.0
