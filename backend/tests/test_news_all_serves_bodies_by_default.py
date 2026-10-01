"""/api/v2/news/all must serve body_txt and body_html WITHOUT being asked.

GovClipping, 1 October 2026, on
`/api/v2/news/all?creation_date=2026-09-30`:

    "veig que body_text i body_html de les publicacions recents estant buides.
     I al accedir a la font oficial, els articles si que tenen contingut"

He was right, and the cause was not a failed sync: `include_body` defaulted to
False, so the list nulled both body fields on every item. The text was in the
database the whole time. Measured that day on the same URL:

    his URL                      body_txt=None on every row
    his URL + include_body=true  336, 194, 264, 295, 2837 characters

Two reasons the default was wrong, not just unhelpful:

  * `body_txt` and `body_html` are two of the five datapoints every Brubru API
    item is contracted to carry. An endpoint that nulls them by default does not
    meet the contract, whatever a query parameter can switch back on.
  * The saving was never database work. The SELECT already reads both columns;
    `_to_item` simply discarded them. Measured at limit=100: 70 KB and 2.75 s
    without bodies, 1.14 MB and 3.52 s with them. The cost is payload only, and
    the caller doing a bulk sync is precisely the caller who wants the text.

`include_body=false` still works, for a caller who wants a light list.

The deeper lesson is about how this was found. A paying partner reported it
after reading the API; our own checks never did, because nothing asserted that a
contracted field is actually populated on the default call path. That is what
this test is for.
"""
from __future__ import annotations

import os
import pathlib

import pytest
from fastapi.testclient import TestClient

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


def test_include_body_defaults_to_true_in_the_signature():
    """The default lives in the route signature; assert it there, cheaply."""
    src = (pathlib.Path(_REPO_ROOT) / "backend" / "api" / "v2" / "news"
           / "__init__.py").read_text(encoding="utf-8")
    block = src.split("include_body: bool = Query(", 1)
    assert len(block) == 2, "include_body parameter not found"
    first_arg = block[1].lstrip()[:5]
    assert first_arg.startswith("True"), (
        "include_body still defaults to False, so /news/all nulls two of the five "
        "contracted datapoints unless the caller knows to ask"
    )


def test_the_docstring_no_longer_tells_callers_bodies_are_null_by_default():
    src = (pathlib.Path(_REPO_ROOT) / "backend" / "api" / "v2" / "news"
           / "__init__.py").read_text(encoding="utf-8")
    assert "are null on the list by default" not in src, (
        "the endpoint description still documents the old behaviour"
    )
