"""A stale browser User-Agent is a time bomb, so fail the build before a host does.

On 26 August 2026 the `/news` scrape logged
`[ERROR] Publications Office: Client error '403 Forbidden'` on op.europa.eu. The
site had not changed. We were announcing **Chrome/124**, a build from April 2024,
and the host applies a minimum-browser-version rule. Measured against the live
host that morning: Chrome/124 and Edg/124 were refused, while Chrome/133+,
Firefox, Safari, curl, httpx, no UA at all and an honest BrubruBot UA were all
served. Only the STALE DISGUISE was punished.

At that moment the codebase carried 108 hardcoded Chrome versions across 106
files (71x Chrome/124, 19x Chrome/120, 15x Chrome/126, 1x Chrome/121). Every one
of them was the same 403 waiting for another host to add the same rule.
Publications Office was simply the first to fire, and nothing in the codebase
would have told us about the second.

This test converts "remember to bump the User-Agent" into a failing build.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from services.scrapers.user_agent import (
    BOT_UA,
    BROWSER_UA,
    CHROME_MAJOR,
    MIN_SUPPORTED_CHROME,
)

BACKEND = Path(__file__).resolve().parent.parent

# `user_agent.py` documents the incident and therefore quotes the old versions on
# purpose. Worktrees are other agents' checkouts, not our code.
EXCLUDED_PARTS = (".claude", "node_modules", "site-packages", "__pycache__")
EXCLUDED_FILES = {"user_agent.py", "test_user_agent_freshness.py"}

_CHROME_RE = re.compile(r"Chrome/(\d+)")


def _python_files():
    for p in BACKEND.rglob("*.py"):
        if any(part in EXCLUDED_PARTS for part in p.parts):
            continue
        if p.name in EXCLUDED_FILES:
            continue
        yield p


def _stale_string_literals(path: Path) -> list[str]:
    """Stale Chrome versions in real STRING LITERALS, ignoring comments.

    The first version of this scanned raw lines and immediately flagged its own
    fix: the comments in `scrape_eu_news.py` and `waf_browser_fetcher.py` that
    EXPLAIN the op.europa.eu 403 both quote "Chrome/124", while the code beside
    them correctly uses BROWSER_UA. A guard that fails on the explanation of the
    bug teaches people to delete the explanation, which is worse than the bug.
    Tokenising drops COMMENT tokens and keeps STRING tokens, so only a UA a
    request could actually send is reported.
    """
    import io
    import tokenize

    found: list[str] = []
    try:
        with path.open("rb") as fh:
            tokens = list(tokenize.tokenize(fh.readline))
    except (OSError, tokenize.TokenError, SyntaxError, UnicodeDecodeError):
        return found
    for tok in tokens:
        if tok.type != tokenize.STRING:
            continue
        for m in _CHROME_RE.finditer(tok.string):
            version = int(m.group(1))
            if version < MIN_SUPPORTED_CHROME:
                found.append(
                    f"{path.relative_to(BACKEND)}:{tok.start[0]} "
                    f"claims Chrome/{version}"
                )
    return found


def test_no_stale_chrome_user_agent_anywhere():
    stale: list[str] = []
    for p in _python_files():
        try:
            if "Chrome/" not in p.read_text():
                continue
        except (OSError, UnicodeDecodeError):
            continue
        stale.extend(_stale_string_literals(p))

    assert not stale, (
        f"{len(stale)} hardcoded User-Agent(s) below Chrome/{MIN_SUPPORTED_CHROME}.\n"
        "A host with a minimum-browser-version rule will answer 403, and the "
        "scraper will log it as the site being broken rather than us.\n"
        "Bump them, or better, import BROWSER_UA / BOT_UA from "
        "services.scrapers.user_agent.\n  " + "\n  ".join(stale[:25])
    )


def test_the_shared_constant_is_itself_current():
    assert CHROME_MAJOR >= MIN_SUPPORTED_CHROME, (
        f"BROWSER_UA claims Chrome/{CHROME_MAJOR} but the floor is "
        f"{MIN_SUPPORTED_CHROME}. The constant that exists to prevent staleness "
        "has itself gone stale."
    )


def test_browser_ua_is_well_formed():
    assert BROWSER_UA.startswith("Mozilla/5.0 ")
    assert f"Chrome/{CHROME_MAJOR}." in BROWSER_UA
    assert "Safari/537.36" in BROWSER_UA


def test_bot_ua_identifies_us_and_cannot_go_stale():
    """The honest UA is the better default precisely because it has no version
    to rot, and op.europa.eu served it fine."""
    assert "BrubruBot" in BOT_UA
    assert "brubru.beresol.eu" in BOT_UA
    assert "Chrome" not in BOT_UA
    assert not _CHROME_RE.search(BOT_UA)


@pytest.mark.parametrize("ua,expected_blocked", [
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", True),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
     "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0", True),
    (BROWSER_UA, False),
    (BOT_UA, False),
])
def test_documented_field_measurements_still_encoded(ua, expected_blocked):
    """Encodes what was actually measured against op.europa.eu, so the reasoning
    survives in the suite rather than only in a commit message."""
    m = _CHROME_RE.search(ua)
    version = int(m.group(1)) if m else None
    is_stale = version is not None and version < MIN_SUPPORTED_CHROME
    assert is_stale == expected_blocked
