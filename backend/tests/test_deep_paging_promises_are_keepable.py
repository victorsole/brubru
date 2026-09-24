"""An envelope must not promise a page it cannot serve (GovClipping, 24 September 2026).

Jordi at GovClipping reported /ep-documents going empty after page 8 while `total` said
1,927 and `has_more` stayed true, and asked the right question: does this happen on the
other endpoints too? Probing all 444 v2 list endpoints for the SYMPTOM (fetch page 1, then
fetch the last page the envelope promises) found two, with two different causes:

  * /parliament/ep-documents merged two tables in Python after fetching `limit * 4` from
    each, so the merged list never held more than 8 pages' worth at any page size;
  * /commission/competition-cases passes through to DG COMP's search API, which serves a
    10,000-result window and nothing beyond it, while reporting `totalResults` of
    1,048,187 for the default query. The envelope advertised 10,482 pages.

Both answered with HTTP 200 and a well-formed envelope, which is why neither had been
noticed. The rule this file defends is the promise itself: `pages` and `has_more` are
commitments, and an endpoint that cannot serve page N must not claim N pages.

No network for the source checks; the constant is asserted against the measured boundary.
"""
from __future__ import annotations

import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def test_the_union_endpoint_fetches_as_deep_as_the_page_asked_for():
    """`limit * 4` per branch is a fixed number of pages, whatever the page size."""
    src = (BACKEND / "api" / "v1" / "ep_entities.py").read_text(encoding="utf-8")
    body = src.split("async def list_ep_documents(")[1]
    assert "depth = page * limit" in body, "the branches are not fetched to the requested page"
    # Code only: the comment above the fix quotes the old expression on purpose.
    code = "\n".join(l.split("#")[0] for l in body.splitlines())
    assert "limit * 4" not in code, "a fixed multiple of limit still caps the union"


def test_the_upstream_window_is_declared_not_discovered_by_the_caller():
    from api.v1.specialised_competition import _UPSTREAM_RESULT_WINDOW

    # Measured against production: offset 9,900 returned 100 rows, offset 10,000 returned 0.
    assert _UPSTREAM_RESULT_WINDOW == 10_000


def test_the_advertised_total_cannot_exceed_what_can_be_served():
    src = (BACKEND / "api" / "v1" / "specialised_competition.py").read_text(encoding="utf-8")
    body = src.split("async def list_cases(")[1]
    assert "min(matched, _UPSTREAM_RESULT_WINDOW)" in body, (
        "total is still the upstream match count, so `pages` promises unreachable pages")
    assert "coverage_note" in body, "the caller is not told why the corpus is larger than the total"


def test_no_endpoint_reintroduces_a_fixed_multiple_of_limit():
    """The whole class, not the one instance: a fetch bounded by a constant times `limit`
    is a page cap by construction."""
    offenders = []
    for path in (BACKEND / "api").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\.limit\(\s*limit\s*\*\s*\d+\s*\)", line):
                offenders.append(f"{path.relative_to(BACKEND)}:{n}")
    assert not offenders, f"fetch bounded by a multiple of limit: {offenders}"


def test_a_python_side_slice_and_its_total_come_from_the_same_list():
    """Slicing a merged list in Python is fine. The bug is a `total` that counts something
    LARGER than the list being sliced: /ep-documents took `total` from two DB `.count()`
    calls (1,931) while slicing a list that had been fetched only `limit * 4` deep per
    branch. So either the list is fully materialised and `total = len(it)`, or the fetch
    goes as deep as the page asked for.

    Four other endpoints slice in Python (consultations, programmes, events, funding
    programmes) and are correct by the first route: they build the whole list, then count
    it, then slice it."""
    bad = []
    for path in (BACKEND / "api").rglob("*.py"):
        if "__pycache__" in str(path):
            continue
        text = path.read_text(encoding="utf-8")
        if "(page - 1) * limit" not in text or "build_envelope" not in text:
            continue
        slices_in_python = "(page - 1) * limit :" in text or "(page - 1) * limit:" in text
        if not slices_in_python:
            continue          # SQL OFFSET: the database does the paging
        materialised = "total = len(" in text
        deep_enough = "page * limit" in text
        if not (materialised or deep_enough):
            bad.append(str(path.relative_to(BACKEND)))
    assert not bad, (
        f"slices a list whose `total` counts more than was fetched: {bad}")
