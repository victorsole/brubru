"""The opinions of the two EU advisory committees, served.

Brubru has held the EESC and CoR opinion registers since migrations 064 and 065 and filled
their full text on 25 September 2026. No route read either table, so 4,708 opinions averaging
over 20,000 characters were stored and served to nobody, including the paying API partner who
had asked for whole bodies everywhere. These tests hold the new routes to the contracts the
rest of the v2 surface is held to.
"""
import pathlib
import sys

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_BACKEND = str(pathlib.Path(__file__).resolve().parents[1])
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def headers():
    env = pathlib.Path(_BACKEND, ".env")
    key = next((l.split("=", 1)[1].strip() for l in env.read_text().splitlines()
                if l.startswith("BRUBRU_API_KEY=")), None)
    if not key:
        pytest.skip("no BRUBRU_API_KEY")
    return {"X-API-Key": key, "X-Brubru-Probe": "opinions-tests"}


def _get(client, headers, path):
    response = client.get(path, headers=headers)
    assert response.status_code == 200, f"{path} -> {response.status_code} {response.text[:200]}"
    return response.json()


def test_both_committees_are_served(client, headers):
    """The whole point: these tables were reachable by nobody."""
    everything = _get(client, headers, "/api/v2/opinions/all?limit=1")
    eesc = _get(client, headers, "/api/v2/opinions/eesc?limit=1")
    cor = _get(client, headers, "/api/v2/opinions/cor?limit=1")
    assert eesc["total"] > 3_000, f"only {eesc['total']} EESC opinions"
    assert cor["total"] > 1_000, f"only {cor['total']} CoR opinions"
    assert everything["total"] == eesc["total"] + cor["total"], "the union must count both"


def test_the_list_withholds_bodies_until_asked(client, headers):
    """20,000 characters an item: a page of 100 with bodies is megabytes."""
    without = _get(client, headers, "/api/v2/opinions/all?limit=3")
    assert all(not item.get("body_txt") for item in without["data"])

    with_body = _get(client, headers, "/api/v2/opinions/all?limit=3&include_body=true&has_body=true")
    assert with_body["data"], "no opinions with a body"
    longest = max(len(item.get("body_txt") or "") for item in with_body["data"])
    assert longest > 1_200, f"longest body on the list was {longest} characters"


def test_the_item_route_always_carries_the_whole_opinion(client, headers):
    listed = _get(client, headers, "/api/v2/opinions/eesc?limit=1&has_body=true")
    assert listed["data"], "no EESC opinion with a body"
    item = _get(client, headers, f"/api/v2/opinions/eesc/{listed['data'][0]['id']}")
    assert len(item.get("body_txt") or "") > 1_200, "the item route must not need include_body"
    assert item.get("body_html"), "body_html must be served too"


def test_every_listed_item_carries_a_self_link_that_resolves(client, headers):
    listed = _get(client, headers, "/api/v2/opinions/all?limit=5")
    for item in listed["data"]:
        assert item.get("self"), f"no self link on {item.get('body_code')}/{item.get('id')}"
        assert f"/opinions/{item['body_code']}/{item['id']}" in item["self"]
    one = listed["data"][0]
    followed = _get(client, headers, f"/api/v2/opinions/{one['body_code']}/{one['id']}")
    assert followed["id"] == one["id"] and followed["body_code"] == one["body_code"]


def test_the_envelope_can_serve_every_page_it_promises(client, headers):
    """The defect GovClipping reported on another endpoint: total said 1,931, page 9 was empty.

    Here the union is sliced in SQL on a TOTAL order (document_date, body_code, id), so the
    last page holds exactly the remainder and nothing repeats.
    """
    limit = 100
    total = _get(client, headers, f"/api/v2/opinions/all?limit={limit}")["total"]
    last_page = (total + limit - 1) // limit
    remainder = total - (last_page - 1) * limit

    seen = set()
    for page in (1, 2, last_page - 1, last_page):
        payload = _get(client, headers, f"/api/v2/opinions/all?limit={limit}&page={page}")
        keys = {(i["body_code"], i["id"]) for i in payload["data"]}
        assert not (keys & seen), f"page {page} repeated {len(keys & seen)} rows"
        seen |= keys
        if page == last_page:
            assert len(payload["data"]) == remainder, (
                f"total promises {total}, so the last page must hold {remainder}, "
                f"got {len(payload['data'])}")
        else:
            assert len(payload["data"]) == limit, f"page {page} was short at {len(payload['data'])}"

    beyond = _get(client, headers, f"/api/v2/opinions/all?limit={limit}&page={last_page + 1}")
    assert beyond["data"] == [], "a page past the end must be empty, not wrap around"


def test_the_body_filter_partitions_the_union(client, headers):
    everything = _get(client, headers, "/api/v2/opinions/all?limit=1")["total"]
    eesc = _get(client, headers, "/api/v2/opinions/all?body=eesc&limit=1")["total"]
    cor = _get(client, headers, "/api/v2/opinions/all?body=cor&limit=1")["total"]
    assert eesc + cor == everything, "a filter whose parts do not sum to the whole is applied wrong"


def test_a_missing_opinion_is_a_404_with_a_reason_code(client, headers):
    response = client.get("/api/v2/opinions/cor/999999999", headers=headers)
    assert response.status_code == 404
    assert response.json().get("reason_code") == "not_found"


def test_the_five_datapoints_are_present(client, headers):
    """public_url, body_txt, body_html, document_date, creation_date."""
    listed = _get(client, headers, "/api/v2/opinions/all?limit=50&has_body=true&include_body=true")
    rows = listed["data"]
    assert len(rows) >= 40, f"only {len(rows)} opinions to check"

    # Real floors, measured 25 September 2026 across both tables: public_url, document_date
    # and creation_date are on 100% of rows, body_txt on 99.3% and body_html on 98.4%.
    # "at least one of fifty" would pass on a corpus that is 98% empty.
    floors = {"public_url": 1.0, "document_date": 1.0, "creation_date": 1.0,
              "body_txt": 0.95, "body_html": 0.90}
    for field, floor in floors.items():
        filled = sum(1 for item in rows if item.get(field))
        share = filled / len(rows)
        assert share >= floor, f"{field} on {share:.0%} of rows, floor is {floor:.0%}"


def test_document_date_is_the_committees_date_not_our_capture_date(client, headers):
    """A date filter must select on the publisher's date, or it answers about our ingest."""
    listed = _get(client, headers, "/api/v2/opinions/all?limit=50&to=2020-12-31")
    for item in listed["data"]:
        if item.get("document_date"):
            assert item["document_date"] <= "2020-12-31", (
                f"{item['body_code']}/{item['id']} dated {item['document_date']} passed a to= filter")


def test_every_declared_filter_actually_filters(client, headers):
    """A declared parameter that changes nothing is worse than an absent one.

    `?q=` on /parliament/meps returned 200 and the first page unfiltered because only `name`
    was declared, and nothing in the response said so. Measured here 25 September 2026:
    q="artificial intelligence" 11, q=nonsense 0, from=2026-01-01 20, has_body=false 33,
    against 4,708 unfiltered.
    """
    unfiltered = _get(client, headers, "/api/v2/opinions/all?limit=1")["total"]

    cases = {
        "q=artificial+intelligence": lambda t: 0 < t < unfiltered,
        "q=zzzzznotathing": lambda t: t == 0,
        "from=2026-01-01": lambda t: 0 < t < unfiltered,
        "has_body=false": lambda t: 0 <= t < unfiltered,
        "body=eesc": lambda t: 0 < t < unfiltered,
    }
    for query, ok in cases.items():
        total = _get(client, headers, f"/api/v2/opinions/all?limit=1&{query}")["total"]
        assert ok(total), f"{query} returned {total} against {unfiltered} unfiltered"


def test_q_matches_the_title_it_claims_to_match(client, headers):
    """A filter that returns FEWER rows can still be matching the wrong thing."""
    listed = _get(client, headers, "/api/v2/opinions/all?q=artificial+intelligence&limit=5")
    assert listed["data"], "no opinions matched"
    for item in listed["data"]:
        assert "artificial intelligence" in (item.get("title") or "").lower(), (
            f"q matched an opinion whose title does not contain it: {item.get('title')!r}")
