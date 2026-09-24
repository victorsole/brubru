"""The four fetch tiers must escalate on a wall and never pass an interstitial on.

Context (22 September 2026). Scrape.do was added as a paid fourth tier behind
aiohttp, Scrapling's fingerprint fetcher and Scrapling's stealthy browser. While
wiring it, the reason the escalation was needed turned out to be a latent bug in
the tiers that already existed:

    walltest: Stealthy fetch OK (14692 bytes)

That "OK" was 14,692 bytes of Cloudflare's "Just a moment..." page. Every tier
returned the interstitial as a successful string, so a caller parsed zero items
and the run read as "the publisher was quiet" instead of "we were blocked".
Those are opposite conclusions and they were indistinguishable.

These tests are offline. Nothing here touches the network or spends a credit.
"""

import os
import pathlib
import sys

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from services.scrapers.base_scraper import BaseScraper, ScraperError  # noqa: E402


class _T(BaseScraper):
    def __init__(self):
        super().__init__("https://example.invalid", "test", use_coordinator=False)

    async def scrape(self, *a, **k): ...
    async def search(self, *a, **k): ...
    async def get_document(self, *a, **k): ...
    async def get_latest_updates(self, *a, **k): ...


# Captured from the real responses on 22 September 2026.
CLOUDFLARE = "<html><head><title>Just a moment...</title></head><body>cf_chl_opt</body></html>"
CONSILIUM_403 = "<html><head><title>Browser check - Consilium</title></head>" \
                "<body>Checking your browser before accessing</body></html>"
SITEGROUND = "<html><head><title>Robot Challenge Screen</title></head><body>sgcaptcha</body></html>"

# A real Council press release. It contains the word "challenges", which is why
# a loose /challenge/ marker false-positived during testing and would have made
# every genuine page look walled.
REAL_PROSE = (
    "<html><head><title>Press releases and statements - Consilium</title></head><body>"
    "The Council today discussed the challenges facing European industry, and the "
    "checking of compliance with the new framework. Ministers agreed to keep the "
    "matter under review." + ("x" * 4000) + "</body></html>"
)


@pytest.mark.parametrize("body,name", [
    (CLOUDFLARE, "cloudflare 'Just a moment'"),
    (CONSILIUM_403, "consilium 'Browser check'"),
    (SITEGROUND, "siteground sgcaptcha"),
])
def test_an_interstitial_is_recognised_as_a_wall(body, name):
    assert BaseScraper._is_walled(body), name


def test_ordinary_eu_prose_is_not_a_wall():
    """'challenges' and 'checking' are normal policy words.

    A loose marker would flag every real page and send every fetch to the paid
    tier, which is both wrong and expensive.
    """
    assert not BaseScraper._is_walled(REAL_PROSE)
    assert not BaseScraper._is_walled("")
    assert not BaseScraper._is_walled("The challenge of enlargement is significant.")


def test_a_marker_far_below_the_fold_does_not_trigger():
    """Only the first 20KB is examined, where interstitials actually live."""
    assert not BaseScraper._is_walled("y" * 25000 + "Just a moment...")


def test_the_chain_escalates_past_a_tier_that_returns_an_interstitial(monkeypatch):
    """This is the bug that prompted the work: tier 3 said OK and handed back junk."""
    t = _T()
    calls = []
    monkeypatch.setattr(t, "_fetch_with_fingerprint",
                        lambda u: (calls.append("fingerprint"), CLOUDFLARE)[1])
    monkeypatch.setattr(t, "_fetch_stealthy",
                        lambda u: (calls.append("stealthy"), CONSILIUM_403)[1])
    monkeypatch.setattr(t, "_fetch_scrapedo",
                        lambda u, **k: (calls.append("scrapedo"), REAL_PROSE)[1])

    got = t._fetch_resilient("https://example.invalid/x")
    assert got == REAL_PROSE
    assert calls == ["fingerprint", "stealthy", "scrapedo"], calls


def test_the_chain_stops_at_the_first_tier_that_returns_a_real_page(monkeypatch):
    """The paid tier must not be reached when a free one worked. This is the
    money guard: on a live run the fingerprint tier served a 91KB Council page
    and scrape.do was never called."""
    t = _T()
    calls = []
    monkeypatch.setattr(t, "_fetch_with_fingerprint",
                        lambda u: (calls.append("fingerprint"), REAL_PROSE)[1])
    monkeypatch.setattr(t, "_fetch_stealthy",
                        lambda u: (calls.append("stealthy"), REAL_PROSE)[1])

    def _boom(u, **k):
        calls.append("scrapedo")
        raise AssertionError("the paid tier must not be reached")

    monkeypatch.setattr(t, "_fetch_scrapedo", _boom)
    t._fetch_resilient("https://example.invalid/x")
    assert calls == ["fingerprint"], calls


def test_when_everything_fails_it_raises_and_names_every_tier(monkeypatch):
    """A caller must be able to tell WALLED from "nothing published"."""
    t = _T()
    monkeypatch.setattr(t, "_fetch_with_fingerprint", lambda u: CLOUDFLARE)
    monkeypatch.setattr(t, "_fetch_stealthy", lambda u: CLOUDFLARE)

    def _fail(u, **k):
        raise ScraperError("rotation failed")

    monkeypatch.setattr(t, "_fetch_scrapedo", _fail)
    with pytest.raises(ScraperError) as e:
        t._fetch_resilient("https://example.invalid/x")
    msg = str(e.value)
    assert "WALLED" in msg
    for tier in ("fingerprint", "stealthy", "scrapedo"):
        assert tier in msg, msg


def test_allow_paid_false_never_reaches_the_paid_tier(monkeypatch):
    t = _T()
    monkeypatch.setattr(t, "_fetch_with_fingerprint", lambda u: CLOUDFLARE)
    monkeypatch.setattr(t, "_fetch_stealthy", lambda u: CLOUDFLARE)

    def _boom(u, **k):
        raise AssertionError("paid tier reached despite allow_paid=False")

    monkeypatch.setattr(t, "_fetch_scrapedo", _boom)
    with pytest.raises(ScraperError, match="free tiers only"):
        t._fetch_resilient("https://example.invalid/x", allow_paid=False)


def test_scrapedo_without_a_key_says_so_rather_than_returning_empty(monkeypatch):
    """Silence is not success: a missing key must surface, not look like no data.

    The .env fallback has to be blocked here, or this machine's real key is found and the
    test makes a live call instead of exercising the missing-key path.
    """
    import dotenv

    monkeypatch.delenv("SCRAPEDO_API_KEY", raising=False)
    monkeypatch.setattr(dotenv, "load_dotenv", lambda *a, **k: False)
    t = _T()
    with pytest.raises(ScraperError, match="SCRAPEDO_API_KEY"):
        t._fetch_scrapedo("https://example.invalid/x")


def test_the_broken_render_mode_is_never_requested(monkeypatch):
    """`render=true` returned 502 on a URL that succeeds plain, so it is broken
    on this account. It must not appear in any request we build."""
    monkeypatch.setenv("SCRAPEDO_API_KEY", "dummy")
    t = _T()
    seen = {}

    class _Resp:
        headers = {"scrape.do-request-cost": "1", "scrape.do-remaining-credits": "9"}

        def read(self): return REAL_PROSE.encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    import urllib.request

    def _urlopen(req, timeout=None):
        seen["url"] = req.full_url
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)
    t._fetch_scrapedo("https://example.invalid/x")
    assert "render" not in seen["url"], seen["url"]
    # and super is opt-in, because it is a 10x credit multiplier
    assert "super" not in seen["url"], seen["url"]


def test_super_is_sent_only_when_explicitly_asked_for(monkeypatch):
    monkeypatch.setenv("SCRAPEDO_API_KEY", "dummy")
    t = _T()
    seen = {}

    class _Resp:
        headers = {}

        def read(self): return REAL_PROSE.encode()
        def __enter__(self): return self
        def __exit__(self, *a): return False

    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda req, timeout=None: (seen.__setitem__("url", req.full_url), _Resp())[1])
    t._fetch_scrapedo("https://example.invalid/x", super_proxy=True)
    assert "super=true" in seen["url"]


# --- the plain aiohttp tier (23 Sep 2026) ------------------------------------
# It returned a 200 challenge page as the page AND cached it, so every caller of
# BaseScraper._fetch read "no items" for a block. 49 call sites use this tier.

class _Resp:
    def __init__(self, body):
        self._body = body

    def raise_for_status(self):
        return None

    async def text(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _Session:
    def __init__(self, body):
        self._body = body

    def get(self, *a, **k):
        return _Resp(self._body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _plain_fetch(monkeypatch, body):
    import asyncio
    import aiohttp

    monkeypatch.setattr(aiohttp, "ClientSession", lambda *a, **k: _Session(body))
    t = _T()
    t._rate_limit = lambda: asyncio.sleep(0)
    saved = []
    t._save_to_cache = lambda key, data: saved.append(data)
    t._get_from_cache = lambda key: None
    return t, saved, asyncio.run


@pytest.mark.parametrize("body", [CLOUDFLARE, CONSILIUM_403, SITEGROUND])
def test_plain_fetch_refuses_an_interstitial_and_does_not_cache_it(monkeypatch, body):
    t, saved, run = _plain_fetch(monkeypatch, body)
    with pytest.raises(ScraperError, match="interstitial"):
        run(t._fetch("https://example.invalid/page"))
    assert saved == []


def test_plain_fetch_still_returns_and_caches_a_real_page(monkeypatch):
    page = "<html><body><h1>Council press release</h1><p>New challenges for the Union.</p></body></html>"
    t, saved, run = _plain_fetch(monkeypatch, page)
    assert run(t._fetch("https://example.invalid/page")) == page
    assert saved == [page]


# --------------------------------------------------------------------------- a tier called on its own
# The queued item said "migrate _fetch_stealthy callers to _fetch_resilient, because
# interstitials still pass as success". There were no direct callers to migrate, but the
# reason they would have been unsafe was real: only the CHAIN looked at the body, so any
# future caller of a single tier would be handed a challenge page as if it were the page.
# Renaming or migrating callers cannot hold that line; the tier refusing does.
from services.scrapers.base_scraper import WalledError  # noqa: E402


@pytest.mark.parametrize("wall", [CLOUDFLARE, CONSILIUM_403, SITEGROUND])
def test_the_fingerprint_tier_refuses_an_interstitial_on_its_own(monkeypatch, wall):
    t = _T()
    monkeypatch.setattr("services.scrapers.base_scraper.SCRAPLING_AVAILABLE", True)
    monkeypatch.setattr("services.scrapers.base_scraper.ScraplingFetcher",
                        lambda **k: type("F", (), {"get": lambda self, u: type(
                            "R", (), {"body": wall.encode()})()})(), raising=False)
    with pytest.raises(WalledError):
        t._fetch_with_fingerprint("https://example.invalid/x")


def test_a_real_page_still_comes_back_from_the_tier(monkeypatch):
    t = _T()
    monkeypatch.setattr("services.scrapers.base_scraper.SCRAPLING_AVAILABLE", True)
    monkeypatch.setattr("services.scrapers.base_scraper.ScraplingFetcher",
                        lambda **k: type("F", (), {"get": lambda self, u: type(
                            "R", (), {"body": REAL_PROSE.encode()})()})(), raising=False)
    assert t._fetch_with_fingerprint("https://example.invalid/x") == REAL_PROSE


def test_a_wall_is_not_reported_as_a_fetch_failure():
    """`WalledError` is a ScraperError, so existing handlers still catch it, but the two
    can be told apart: 'we were blocked' and 'the fetch broke' need different answers."""
    assert issubclass(WalledError, ScraperError)


def test_the_chain_still_names_a_walled_tier_as_an_interstitial(monkeypatch):
    """The escalation message has to keep saying which tier was WALLED rather than which
    raised, or the operator cannot tell a block from a broken dependency."""
    t = _T()

    def walled(u):
        raise WalledError("interstitial")

    monkeypatch.setattr(t, "_fetch_with_fingerprint", walled)
    monkeypatch.setattr(t, "_fetch_stealthy", walled)
    with pytest.raises(ScraperError, match="fingerprint: interstitial; stealthy: interstitial"):
        t._fetch_resilient("https://example.invalid/x", allow_paid=False)


# --------------------------------------------------------------------------- the key itself
def test_the_paid_tier_finds_its_key_in_the_repo_env(monkeypatch):
    """A wall we never actually tried to climb (24 Sep 2026).

    The Council calendar reported "no meetings scraped (fetch blocked)" while its paid
    fallback was refusing to start with "SCRAPEDO_API_KEY is not set" -- and the key was
    sitting in the repo's .env all along. Nothing loads .env when a scraper runs as a
    library, so a laptop run had no key and reported a block instead of a missing config.
    """
    import dotenv

    from services.scrapers import base_scraper as bs

    monkeypatch.delenv("SCRAPEDO_API_KEY", raising=False)
    loaded = []

    def fake_load(path=None, override=False):
        loaded.append(str(path))
        os.environ["SCRAPEDO_API_KEY"] = "from-the-env-file"
        return True

    monkeypatch.setattr(dotenv, "load_dotenv", fake_load)
    assert bs._scrapedo_token() == "from-the-env-file"
    assert loaded and loaded[0].endswith(".env")


def test_the_environment_wins_over_the_file(monkeypatch):
    """A container gets its key from the service config and must not read a stale file."""
    import dotenv

    from services.scrapers import base_scraper as bs

    monkeypatch.setenv("SCRAPEDO_API_KEY", "from-the-container")

    def _boom(*a, **k):
        raise AssertionError("the .env file was read although the environment had the key")

    monkeypatch.setattr(dotenv, "load_dotenv", _boom)
    assert bs._scrapedo_token() == "from-the-container"
