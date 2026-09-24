"""Only 800 of 1,931 EP documents could be reached (GovClipping, 24 September 2026).

Two defects, both of which answer with a 200 and a plausible envelope.

**The page cap was arithmetic.** /ep-documents is a union of two tables merged and sorted
in Python, and each branch fetched `limit * 4` rows. Two branches means the merged list
never held more than `8 * limit` items, so the slice at the end went empty from page 9 at
EVERY page size, while `total` still said 1,931 and `has_more` stayed true. "Stops after
page 8, whatever the page size" is the signature of a fixed multiple of `limit`. The same
bug was found and fixed in /council-documents on 27 August 2026 (`depth = page * limit`);
this endpoint never got the fix, which is why a per-endpoint bug is worth grepping for
across every endpoint of the same shape.

**The type filter was applied to one branch of two.** `document_type` filtered the
amendment-documents branch only when the value was one it knew, and the committee-work
branch never at all. So `draft_report` returned 1,136 matching amendment documents PLUS
all 575 work items (1,711), and an unknown value like `report` filtered neither branch and
returned the whole corpus. The per-type totals summed to 8,858 against a corpus of 1,931,
which is the arithmetic that gives it away: a filter that only ever ADDS rows is not a
filter.

Needs the database.
"""
from __future__ import annotations

import pathlib
import sys

import pytest
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

ROUTE = "/api/v2/parliament/ep-documents"


@pytest.fixture(scope="module")
def api():
    from api.v1._deps import api_user_with_rate_limit
    from main import app
    from models.user import User

    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(
        email="test@example.com", role="admin"
    )
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


def _page(api, **params):
    r = api.get(ROUTE, params=params)
    assert r.status_code == 200, r.text
    return r.json()


# --------------------------------------------------------------- the page cap
def test_the_last_page_carries_records(api):
    """Page 20 of 20 was empty. If the envelope says the page exists, it has rows."""
    first = _page(api, page=1, limit=100)
    last = first["pages"]
    assert last > 8, "fewer than 9 pages: this test cannot see the bug it exists for"
    d = _page(api, page=last, limit=100)
    assert d["returned"] > 0, f"page {last} of {last} is empty while total says {d['total']}"


def test_no_page_before_the_last_is_empty(api):
    """Walks the whole envelope. Every page the envelope promises must deliver."""
    first = _page(api, page=1, limit=100)
    empty = [p for p in range(1, first["pages"] + 1)
             if _page(api, page=p, limit=100)["returned"] == 0]
    assert not empty, f"empty page(s) inside a {first['pages']}-page envelope: {empty}"


def test_every_record_is_reachable_by_paging(api):
    """The sum of the pages is the total. This is the claim the envelope makes."""
    first = _page(api, page=1, limit=100)
    got = sum(_page(api, page=p, limit=100)["returned"] for p in range(1, first["pages"] + 1))
    assert got == first["total"], f"paged {got} of {first['total']} records"


@pytest.mark.parametrize("limit", [10, 50, 100])
def test_the_reachable_count_does_not_depend_on_page_size(api, limit):
    """The cap was 8*limit, so it moved with the page size and looked like a data limit."""
    first = _page(api, page=1, limit=limit)
    ninth = _page(api, page=9, limit=limit)
    if first["pages"] >= 9:
        assert ninth["returned"] > 0, f"page 9 empty at limit={limit}"


def test_has_more_is_false_only_on_the_last_page(api):
    first = _page(api, page=1, limit=100)
    last = _page(api, page=first["pages"], limit=100)
    assert last["has_more"] is False
    assert _page(api, page=1, limit=100)["has_more"] is True


# --------------------------------------------------------------- the type filter
def test_a_filtered_total_is_never_the_whole_corpus(api):
    """`report`, `minutes` and `resolution` each returned all 1,931 records."""
    everything = _page(api, limit=1)["total"]
    for value in ("draft_report", "amendments", "opinion"):
        t = _page(api, limit=1, document_type=value)["total"]
        assert t < everything, f"document_type={value} returned the whole corpus ({t})"


def test_the_per_type_totals_do_not_exceed_the_corpus(api):
    """They summed to 8,858 against 1,931, because each type added the 575 unfiltered
    work items. A partition cannot be larger than the set."""
    everything = _page(api, limit=1)["total"]
    total = sum(_page(api, limit=1, document_type=v)["total"]
                for v in ("draft_report", "amendments", "draft_recommendation",
                          "opinion", "draft_opinion"))
    assert total <= everything, (
        f"the amendment-document types alone sum to {total} of a {everything}-record corpus")


def test_every_row_returned_is_of_the_type_asked_for(api):
    for value in ("draft_report", "amendments"):
        rows = _page(api, limit=50, document_type=value)["data"]
        assert rows, f"no rows at all for document_type={value}"
        wrong = {r["document_type"] for r in rows} - {value}
        assert not wrong, f"document_type={value} returned rows typed {wrong}"


def test_an_unserved_type_is_refused_rather_than_answered_with_everything(api):
    """The failure that started this: a value with no source filtered nothing."""
    r = api.get(ROUTE, params={"document_type": "report"})
    assert r.status_code == 422, f"got {r.status_code}: {r.text[:160]}"
    # The app's error handler flattens the detail dict to the top level and adds a
    # request_id, so the valid values sit on the body itself.
    body = r.json()
    assert body.get("reason_code") == "unknown_document_type", body
    assert "draft_report" in body.get("valid_values", []), body


@pytest.mark.parametrize("value", ["nonsense_type", "minutes", "resolution", "REPORT"])
def test_no_typo_can_silently_mean_no_filter(api, value):
    r = api.get(ROUTE, params={"document_type": value})
    assert r.status_code == 422, f"{value!r} was accepted and answered with {r.json().get('total')}"


def test_a_served_type_is_accepted_case_insensitively(api):
    assert api.get(ROUTE, params={"document_type": "DRAFT_REPORT"}).status_code == 200
