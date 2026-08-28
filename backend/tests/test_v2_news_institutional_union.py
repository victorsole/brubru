"""`/api/v2/news/*` must cover the Commission, Parliament and Council.

The defect (found 25 Aug 2026): `economy_items` held 12,021 news rows across 72
bodies and ZERO for those three, ever. The 72 that do produce news are the
agencies, so an endpoint named `/news/all` was an AGENCY-news aggregator, and
MEUB News consumed a feed missing the three institutions that generate most EU
news. A direct scrape found 62 Commission items in 24 hours while
`/api/v2/news/all?days=1` returned 4.

The news was never missing: it lives in `eu_news_items`, written by a different
pipeline. The endpoints now union the two stores at read time rather than copying
rows, which would create a second source of truth for the same fact.

The most important test here is `test_no_body_is_served_from_both_stores` -- it is
what stops the union silently double-counting if an ingestor is ever added.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v1._deps import api_user_with_rate_limit
from api.v2.news import _INSTITUTIONAL_NEWS, _coerce_id
from main import app
from models.user import User

INSTITUTIONS = sorted(_INSTITUTIONAL_NEWS)


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(
        email="test@example.com", role="admin"
    )
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


# ---------------------------------------------------------------------------
# The invariant that keeps the union honest
# ---------------------------------------------------------------------------

def test_no_body_is_served_from_both_stores(db):
    """A body in _INSTITUTIONAL_NEWS must have ZERO news rows in economy_items.

    The union does not deduplicate -- it cannot, because the two stores share no
    key. Safety comes entirely from the two halves being disjoint. If someone
    adds a Commission news ingestor to sync_economy.py, every Commission item
    starts appearing twice, and this test is the thing that says so.

    Fix by REMOVING the body from _INSTITUTIONAL_NEWS, not by weakening this.
    """
    rows = db.execute(text(
        "SELECT body_code, count(*) n FROM economy_items "
        "WHERE item_type IN ('news','press_release') AND body_code = ANY(:c) "
        "GROUP BY body_code"), {"c": INSTITUTIONS}).fetchall()
    assert rows == [], (
        f"{[(r.body_code, r.n) for r in rows]} now have news in economy_items AND are "
        "unioned in from eu_news_items, so those items are served twice. Remove them "
        "from _INSTITUTIONAL_NEWS."
    )


def test_the_institutions_are_registered_bodies(db):
    """They must resolve to a real body so `body_name` is not null in the feed."""
    known = {r.code for r in db.execute(
        text("SELECT code FROM economy_bodies WHERE code = ANY(:c)"), {"c": INSTITUTIONS}
    ).fetchall()}
    assert known == set(INSTITUTIONS), f"unregistered body codes: {set(INSTITUTIONS) - known}"


# ---------------------------------------------------------------------------
# The gap itself
# ---------------------------------------------------------------------------

def test_commission_news_is_reachable(client):
    """The headline regression: this returned nothing, ever."""
    body = client.get("/api/v2/news/all?body=commission&days=365&limit=5").json()
    assert body["total"] > 0, "the Commission still contributes no news"
    assert all(i["body_code"] == "commission" for i in body["data"])
    assert all(i["body_name"] for i in body["data"]), "institutional items have no body_name"


@pytest.mark.parametrize("code", INSTITUTIONS)
def test_each_institution_is_reachable(client, code):
    body = client.get(f"/api/v2/news/all?body={code}&days=3650&limit=3").json()
    assert body["total"] > 0, f"{code} contributes no news to /news/all"


def test_the_unified_feed_actually_mixes_both_stores(client):
    """A feed that returns only one store is not a union."""
    body = client.get("/api/v2/news/all?days=365&limit=100").json()
    codes = {i["body_code"] for i in body["data"]}
    assert codes & set(INSTITUTIONS), "no institutional item in the unified feed"
    assert codes - set(INSTITUTIONS), "no agency item -- the union dropped the economy half"


def test_pick_list_offers_the_institutions(client):
    """A body the picker cannot show is a body nobody can filter to."""
    bodies = {b["code"]: b["item_count"] for b in client.get("/api/v2/news/bodies").json()["bodies"]}
    for code in INSTITUTIONS:
        assert bodies.get(code, 0) > 0, f"{code} missing from the /bodies pick-list"


def test_freshness_probe_covers_both_stores(client):
    """`/latest` is the staleness guard the /news skill trusts before declaring a
    quiet day. Reading only the agency store made it report the agency feed's
    freshness while presenting it as the whole corpus."""
    lat = client.get("/api/v2/news/latest").json()
    assert lat["total_items"] > 12_021, (
        "total_items still looks like the agency-only corpus; /latest is not unioned"
    )
    assert lat["latest_date"] is not None


# ---------------------------------------------------------------------------
# Two id spaces, one endpoint
# ---------------------------------------------------------------------------

def test_agency_ids_are_still_integers(client):
    """Contract preservation: existing consumers must not start seeing strings.

    The union casts both halves to text so the column types match; `_coerce_id`
    turns the agency half back into an int on the way out.
    """
    body = client.get("/api/v2/news/all?body=cedefop&days=3650&limit=1").json()
    if not body["data"]:
        pytest.skip("no cedefop items to check")
    assert isinstance(body["data"][0]["id"], int)


def test_institutional_ids_are_uuid_strings(client):
    body = client.get("/api/v2/news/all?body=commission&days=365&limit=1").json()
    assert body["data"], "no commission item to check"
    ident = body["data"][0]["id"]
    assert isinstance(ident, str) and "-" in ident, f"expected a UUID string, got {ident!r}"


@pytest.mark.parametrize("raw,expected", [
    ("12345", 12345),
    ("0", 0),
    ("e8f7f326-3614-4f09-8abc-000000000000", "e8f7f326-3614-4f09-8abc-000000000000"),
])
def test_coerce_id(raw, expected):
    assert _coerce_id(raw) == expected


@pytest.mark.parametrize("scope", ["commission", "cedefop"])
def test_detail_endpoint_round_trips_both_id_spaces(client, scope):
    """Whatever id the list hands out must work unchanged on the detail route."""
    lst = client.get(f"/api/v2/news/all?body={scope}&days=3650&limit=1").json()
    if not lst["data"]:
        pytest.skip(f"no {scope} items")
    item = lst["data"][0]
    r = client.get(f"/api/v2/news/{item['id']}")
    assert r.status_code == 200, f"id {item['id']!r} from the list 404s on the detail route"
    assert r.json()["title"] == item["title"]
    assert r.json()["body_code"] == item["body_code"]


def test_a_malformed_id_is_a_404_not_a_500(client):
    """A bad UUID must not reach psycopg as a cast error."""
    r = client.get("/api/v2/news/not-a-real-id")
    assert r.status_code == 404, f"expected 404, got {r.status_code}"


def test_literal_routes_still_win_over_the_id_route(client):
    """`item_id` is now a string, so `/latest` and `/bodies` would happily match
    it. They are declared first and must stay that way."""
    for path in ("/api/v2/news/latest", "/api/v2/news/bodies"):
        assert client.get(path).status_code == 200, f"{path} was swallowed by /{{item_id}}"


# ---------------------------------------------------------------------------
# Filters must apply to BOTH halves, or the union leaks
# ---------------------------------------------------------------------------

def test_date_window_applies_to_the_institutional_half(client):
    """A filter honoured on one half only would return unfiltered institutional rows."""
    narrow = client.get("/api/v2/news/all?body=commission&days=2").json()["total"]
    wide = client.get("/api/v2/news/all?body=commission&days=365").json()["total"]
    assert narrow < wide, "the date window does not narrow the institutional half"


def test_kind_filter_applies_to_the_institutional_half(client):
    news = client.get("/api/v2/news/all?body=commission&kind=news&days=3650").json()
    press = client.get("/api/v2/news/all?body=commission&kind=press_release&days=3650").json()
    both = client.get("/api/v2/news/all?body=commission&kind=all&days=3650").json()
    assert {i["kind"] for i in news["data"]} <= {"news"}
    assert {i["kind"] for i in press["data"]} <= {"press_release"}
    assert both["total"] == news["total"] + press["total"], (
        "kind=all is not the sum of its parts; a source item_type is unmapped"
    )


def test_scoping_to_an_agency_excludes_the_institutional_half(client):
    """`body=cedefop` must not drag in the whole institutional store."""
    body = client.get("/api/v2/news/all?body=cedefop&days=3650&limit=50").json()
    assert all(i["body_code"] == "cedefop" for i in body["data"])


def test_free_text_search_applies_to_both_halves(client):
    """`q` uses FTS on the agency half and ILIKE on the institutional half; the
    filter must still NARROW both, not pass one through unfiltered."""
    unfiltered = client.get("/api/v2/news/all?body=commission&days=3650").json()["total"]
    filtered = client.get("/api/v2/news/all?body=commission&days=3650&q=zzzznotaword").json()["total"]
    assert filtered < unfiltered, "q does not filter the institutional half"


def test_pagination_is_stable_across_the_union(client):
    """Page 2 must not repeat page 1 -- a union without a deterministic ORDER BY
    tiebreak can interleave differently on each call."""
    p1 = client.get("/api/v2/news/all?days=365&limit=10&page=1").json()["data"]
    p2 = client.get("/api/v2/news/all?days=365&limit=10&page=2").json()["data"]
    ids1 = {str(i["id"]) for i in p1}
    ids2 = {str(i["id"]) for i in p2}
    assert not (ids1 & ids2), f"{len(ids1 & ids2)} item(s) appear on both pages"


def test_the_description_matches_the_shipped_id_contract():
    """The published description must not describe an id scheme that was replaced.

    Caught in the second audit pass. The first implementation disambiguated the
    two stores by NEGATING the id, and the endpoint description said so. That
    scheme was then abandoned -- eu_news_items is keyed by UUID, and
    `-uuid` is not an operation Postgres has -- but the description still told
    partners to expect a negative integer. A wrong contract on a paid endpoint is
    worse than an undocumented one.
    """
    from main import app
    desc = next(
        r.description for r in app.routes
        if getattr(r, "path", "") == "/api/v2/news/all"
    )
    assert "NEGATIVE" not in desc.upper(), "description still promises negative ids"
    assert "UUID" in desc.upper(), "description does not mention the institutional id type"


@pytest.mark.parametrize("order", ["recent", "oldest", "title"])
def test_every_order_has_a_deterministic_tiebreak(order):
    """LIMIT/OFFSET pagination over a UNION needs a total order.

    Two rows with equal sort keys may come back in a different relative order on
    each call, so a page boundary that falls inside a tie repeats or skips rows.
    `title` shipped with no tiebreak and was stable only by luck on current data.
    """
    from api.v2.news import _ORDERS
    assert "id" in _ORDERS[order], f"order={order} has no id tiebreak: {_ORDERS[order]!r}"


@pytest.mark.parametrize("order", ["recent", "oldest", "title"])
def test_pages_do_not_overlap_under_any_order(client, order):
    p1 = client.get(f"/api/v2/news/all?days=365&limit=25&page=1&order={order}").json()["data"]
    p2 = client.get(f"/api/v2/news/all?days=365&limit=25&page=2&order={order}").json()["data"]
    overlap = {str(i["id"]) for i in p1} & {str(i["id"]) for i in p2}
    assert not overlap, f"order={order}: {len(overlap)} item(s) on both pages"


# ---------------------------------------------------------------------------
# body_txt / body_html — reported by a partner, missed by my own audit
# ---------------------------------------------------------------------------
# A v2 integrator found `/api/v2/news/all` returning body_txt and body_html NULL
# with no way to force content. Three separate causes, all in the API layer while
# the DATA was there all along (11,752 of 12,375 economy news rows have body_txt):
#
#   1. the union SELECT did not carry the body columns at all;
#   2. the list hardcoded `with_body=False` and exposed no parameter;
#   3. the detail route hardcoded `NULL AS body_txt` for institutional items, so
#      a Commission item could not return a body from ANY route.
#
# My audit of v2 checked envelopes, ids, filters and pagination and never asked
# for the body. Hence the standing rule these tests enforce.

def test_the_union_carries_the_body_columns(db):
    """If the SELECT does not project them, no parameter can ever surface them."""
    from api.v2.news import _news_source_sql, _NEWS_TYPES
    src, params = _news_source_sql(None, _NEWS_TYPES, None, None, None)
    row = db.execute(text(f"SELECT * FROM {src} u LIMIT 1"), params).fetchone()
    assert row is not None, "no news rows at all"
    cols = set(row._mapping.keys())
    assert {"body_txt", "body_html"} <= cols, f"union drops the body columns: {sorted(cols)}"


def test_include_body_returns_real_content(client):
    """The parameter the partner could not find. Without it there is no bulk route
    to the body at all."""
    off = client.get("/api/v2/news/all?days=30&limit=10").json()["data"]
    on = client.get("/api/v2/news/all?days=30&limit=10&include_body=true").json()["data"]
    assert on, "no items returned"
    with_body = sum(1 for i in on if (i.get("body_txt") or "").strip())
    assert with_body > 0, "include_body=true still returns no body_txt"
    assert all(not (i.get("body_txt") or "") for i in off), (
        "the default list now ships full articles; that is a payload-size change"
    )


def test_agency_items_serve_the_full_article(client):
    body = client.get(
        "/api/v2/news/all?body=cedefop&days=3650&limit=5&include_body=true").json()["data"]
    if not body:
        pytest.skip("no cedefop items")
    assert any((i.get("body_txt") or "").strip() for i in body)


def test_institutional_items_are_not_hardcoded_null(client):
    """A Commission item used to return NULL from the list AND the detail route."""
    lst = client.get(
        "/api/v2/news/all?body=commission&days=365&limit=5&include_body=true").json()["data"]
    assert lst, "no commission items"
    assert any((i.get("body_txt") or "").strip() for i in lst), (
        "commission items still return no body_txt"
    )
    detail = client.get(f"/api/v2/news/{lst[0]['id']}").json()
    assert (detail.get("body_txt") or "").strip(), (
        "the detail route still hardcodes NULL for institutional items"
    )


@pytest.mark.parametrize("scope", ["commission", "cedefop"])
def test_the_detail_route_always_serves_a_body(client, scope):
    lst = client.get(f"/api/v2/news/all?body={scope}&days=3650&limit=1").json()["data"]
    if not lst:
        pytest.skip(f"no {scope} items")
    d = client.get(f"/api/v2/news/{lst[0]['id']}").json()
    assert (d.get("body_txt") or "").strip(), f"{scope} detail returns no body_txt"


def test_the_description_tells_callers_how_to_get_the_body():
    """The partner's actual complaint was 'no parameter forces these fields'. A
    switch nobody can find is the same as no switch."""
    from main import app
    desc = next(r.description for r in app.routes
                if getattr(r, "path", "") == "/api/v2/news/all")
    assert "include_body" in desc, "the description does not mention include_body"
