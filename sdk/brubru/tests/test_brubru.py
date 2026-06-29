"""brubru SDK tests.

Offline tests use a fake transport (no network): they prove parsing, the
5-datapoint mapping, pagination and the typed-error mapping deterministically.
The live tests hit production read-only and are skipped unless BRUBRU_API_KEY
is set; run them with:  BRUBRU_API_KEY=brubru_live_... pytest -m live
"""
import os

import pytest

import brubru
from brubru import (AuthError, NotFoundError, PaymentRequiredError, RateLimitError,
                    ScopeError, ServerError, ValidationError)


# --------------------------------------------------------------------------- #
# Fake transport
# --------------------------------------------------------------------------- #
class FakeResp:
    def __init__(self, status, body):
        self.status_code = status
        self._body = body
        self.ok = 200 <= status < 300
        self.text = "" if isinstance(body, (dict, list)) else str(body)

    def json(self):
        if isinstance(self._body, (dict, list)):
            return self._body
        raise ValueError("not json")


class FakeSession:
    """Programmable: set .handler = fn(url, params) -> FakeResp."""

    def __init__(self):
        self.headers = {}
        self.handler = None
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params or {}))
        return self.handler(url, params or {})

    def close(self):
        pass


def make_client(handler):
    s = FakeSession()
    s.handler = handler
    return brubru.Client("brubru_live_test", session=s), s


# --------------------------------------------------------------------------- #
# Fixtures of real-shaped payloads
# --------------------------------------------------------------------------- #
EXTRACT_BODY = {
    "url": "https://cinea.ec.europa.eu/news_en", "platform": "drupal",
    "fetched_via": "requests", "item_count": 1, "body_code": "200",
    "items": [{
        "title": "CINEA launches call", "item_type": "news", "summary": "A summary.",
        "public_url": "https://cinea.ec.europa.eu/news/x_en",
        "body_txt": "Full text here.", "body_html": "<p>Full text here.</p>",
        "document_date": "2026-06-20T00:00:00", "creation_date": "2026-06-29T10:00:00Z",
        "source_kind": "drupal", "guid": "x", "eurovoc_descriptors": [{"id": "100", "label": "energy policy"}],
    }],
}


def _envelope(data, *, total, page, limit):
    pages = (total + limit - 1) // limit if total else 0
    return {"total": total, "returned": len(data), "pages": pages, "page": page,
            "limit": limit, "has_more": page < pages,
            "next_page": page + 1 if page < pages else None, "data": data}


def _post(i):
    return {"id": i, "account_id": 10, "entity_type": "commissioner", "entity_key": "x",
            "entity_name": "A Person", "platform": "x", "handle": "aperson",
            "like_count": 5, "title": f"A Person on x #{i}", "summary": "hi",
            "public_url": f"https://x.com/aperson/status/{i}", "body_txt": None, "body_html": None,
            "document_date": "2026-06-29T08:00:00Z", "creation_date": "2026-06-29T09:00:00Z"}


# --------------------------------------------------------------------------- #
# Offline tests
# --------------------------------------------------------------------------- #
def test_auth_header_set():
    c, s = make_client(lambda u, p: FakeResp(200, {"status": "ok"}))
    assert s.headers["X-API-Key"] == "brubru_live_test"
    assert "brubru-python" in s.headers["User-Agent"]


def test_missing_key_raises():
    with pytest.raises(ValueError):
        brubru.Client("")


def test_extract_parsing_and_5_datapoints():
    c, s = make_client(lambda u, p: FakeResp(200, EXTRACT_BODY))
    res = c.extract("https://cinea.ec.europa.eu/news_en", classify=True)
    assert res.platform == "drupal" and res.item_count == 1 and len(res) == 1
    it = res.items[0]
    # the five datapoints
    assert it.public_url.endswith("/x_en")
    assert it.body_txt == "Full text here." and it.body_html.startswith("<p>")
    assert it.document_date.year == 2026 and it.document_date.month == 6
    assert it.creation_date.year == 2026
    assert it.eurovoc_descriptors[0]["label"] == "energy policy"
    # classify passed through as a lowercased string param
    assert s.calls[-1][1]["classify"] == "true"
    assert s.calls[-1][1]["url"].endswith("news_en")


def test_none_params_dropped():
    c, s = make_client(lambda u, p: FakeResp(200, _envelope([], total=0, page=1, limit=50)))
    c.social.posts(platform=None, entity_type="mep")
    sent = s.calls[-1][1]
    assert "platform" not in sent and sent["entity_type"] == "mep"


def test_posts_page_parsing():
    c, s = make_client(lambda u, p: FakeResp(200, _envelope([_post(1), _post(2)], total=2, page=1, limit=50)))
    page = c.social.posts(entity_type="commissioner")
    assert page.total == 2 and len(page) == 2 and page.has_more is False
    assert page.items[0].platform == "x" and page.items[0].like_count == 5
    assert page.items[0].document_date.hour == 8


def test_pagination_streams_all_pages():
    def handler(u, p):
        pg = int(p.get("page", 1))
        if pg == 1:
            return FakeResp(200, _envelope([_post(1), _post(2)], total=3, page=1, limit=2))
        return FakeResp(200, _envelope([_post(3)], total=3, page=2, limit=2))
    c, s = make_client(handler)
    ids = [post.id for post in c.social.iter_posts(limit=2)]
    assert ids == [1, 2, 3]


def test_pagination_respects_max_items():
    def handler(u, p):
        pg = int(p.get("page", 1))
        return FakeResp(200, _envelope([_post(pg * 10), _post(pg * 10 + 1)],
                                       total=100, page=pg, limit=2))
    c, s = make_client(handler)
    got = list(c.social.iter_posts(limit=2, max_items=3))
    assert len(got) == 3  # stops mid-stream, does not fetch forever


@pytest.mark.parametrize("status,exc", [
    (401, AuthError), (402, PaymentRequiredError), (403, ScopeError),
    (404, NotFoundError), (422, ValidationError), (429, RateLimitError),
    (500, ServerError), (502, ServerError),
])
def test_error_mapping(status, exc):
    c, s = make_client(lambda u, p: FakeResp(status, {"detail": "boom"}))
    with pytest.raises(exc) as ei:
        c.social.directory()
    assert ei.value.status == status
    assert "boom" in str(ei.value)


def test_platforms_and_verified_bool_serialised():
    captured = {}

    def handler(u, p):
        captured.update(p)
        if u.endswith("/platforms"):
            return FakeResp(200, [{"code": "bluesky", "name": "Bluesky", "fetch_tier": "open",
                                   "account_count": 100, "post_count": 900}])
        return FakeResp(200, _envelope([], total=0, page=1, limit=50))
    c, s = make_client(handler)
    pls = c.social.platforms()
    assert pls[0].code == "bluesky" and pls[0].fetch_tier == "open"
    c.social.accounts(verified=True)
    assert captured["verified"] == "true"  # bool serialised for the query string


def test_non_json_2xx_fails_loudly():
    # Simulates pointing base_url at the brand domain's SPA fallback: 200 text/html.
    class HtmlResp(FakeResp):
        def __init__(self):
            super().__init__(200, "<!doctype html><html></html>")
            self.headers = {"Content-Type": "text/html"}
            self.url = "https://brubru.beresol.eu/api/v2/social"
    c, s = make_client(lambda u, p: HtmlResp())
    with pytest.raises(brubru.BrubruError) as ei:
        c.social.directory()
    assert "expected JSON" in str(ei.value)


def test_default_base_is_backend_host():
    c, s = make_client(lambda u, p: FakeResp(200, {"status": "ok"}))
    assert c.base_url == "https://brubru-production.up.railway.app"


def test_entity_footprint_typed():
    body = {"entity_type": "commissioner", "entity_key": "x", "entity_name": "A Person",
            "accounts": [{"id": 1, "platform": "x", "public_url": "https://x.com/a", "verified": True}],
            "recent_posts": [_post(7)]}
    c, s = make_client(lambda u, p: FakeResp(200, body))
    foot = c.social.entity("commissioner", "x")
    assert foot["entity_name"] == "A Person"
    assert foot["accounts"][0].verified is True
    assert foot["recent_posts"][0].id == 7


# --------------------------------------------------------------------------- #
# Live tests (read-only; need a real key)
# --------------------------------------------------------------------------- #
LIVE_KEY = os.environ.get("BRUBRU_API_KEY")
LIVE_BASE = os.environ.get("BRUBRU_BASE_URL", "https://brubru-production.up.railway.app")
live = pytest.mark.skipif(not LIVE_KEY, reason="set BRUBRU_API_KEY to run live tests")


@pytest.fixture
def live_client():
    c = brubru.Client(LIVE_KEY, base_url=LIVE_BASE)
    yield c
    c.close()


@pytest.mark.live
@live
def test_live_directory(live_client):
    d = live_client.social.directory()
    assert d["total_accounts"] > 0 and "accounts_by_entity_type" in d


@pytest.mark.live
@live
def test_live_platforms(live_client):
    pls = live_client.social.platforms()
    assert any(p.code == "bluesky" for p in pls)
    assert all(p.fetch_tier in ("open", "gated", "hard", "none") for p in pls)


@pytest.mark.live
@live
def test_live_posts_page_and_detail(live_client):
    page = live_client.social.posts(limit=3)
    assert page.total >= 0 and len(page) <= 3
    if page.items:
        p = page.items[0]
        assert p.public_url  # URL always set, even on list
        assert p.body_txt is None  # body null on list
        full = live_client.social.post(p.id)
        assert full.body_txt is not None and full.public_url  # full on detail


@pytest.mark.live
@live
def test_live_accounts_verified_filter(live_client):
    page = live_client.social.accounts(entity_type="mep", verified=True, limit=5)
    assert all(a.verified for a in page.items)


@pytest.mark.live
@live
def test_live_auth_error_on_bad_key():
    bad = brubru.Client("brubru_live_definitely_wrong_key", base_url=LIVE_BASE)
    with pytest.raises((AuthError, ScopeError, PaymentRequiredError)):
        bad.social.directory()
    bad.close()
