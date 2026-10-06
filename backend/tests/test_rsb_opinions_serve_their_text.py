"""The Regulatory Scrutiny Board's opinions were stored and not served.

`rsb_opinions.full_text` has held the opinions all along (34 of 44 rows, averaging 5,170
characters) and the endpoint returned title, summary and a PDF link. It carried two of the
five mandatory datapoints: no `public_url`, no `body_txt`, no `body_html`.

Found on 28 September 2026 by asking, of every table with a body column, WHO SERVES IT --
the check that should precede filling one, not follow it.
"""
import pathlib
import sys

import pytest

# Reads production data: runs locally, never in CI (6 Oct 2026).
pytestmark = pytest.mark.live

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)


@pytest.fixture(scope="module")
def headers():
    key = next((l.split("=", 1)[1].strip() for l in pathlib.Path(_BACKEND, ".env").read_text().splitlines()
                if l.startswith("BRUBRU_API_KEY=")), None)
    if not key:
        pytest.skip("no BRUBRU_API_KEY")
    return {"X-API-Key": key, "X-Brubru-Probe": "rsb-tests"}


def test_the_five_datapoints_are_present(client, headers):
    r = client.get("/api/v2/commission/rsb-opinions?limit=10", headers=headers)
    assert r.status_code == 200, r.text[:200]
    items = r.json().get("data") or []
    assert items, "no opinions returned"
    # These three are derivable for every row, so they must be on every row.
    for field in ("public_url", "document_date", "creation_date"):
        filled = sum(1 for i in items if i.get(field))
        assert filled == len(items), f"{field} on only {filled} of {len(items)} opinions"

    # body_txt cannot be demanded of a row that has neither full text nor a summary: 10 of
    # the 44 opinions have no stored text, and asserting 100% here would be asserting that
    # the corpus is complete rather than that the endpoint serves what it holds. What the
    # endpoint must not do is WITHHOLD text it has.
    served = sum(1 for i in items if i.get("body_txt"))
    assert served >= len(items) // 2, f"body_txt on only {served} of {len(items)}"


def test_the_body_is_the_opinion_not_its_summary(client, headers):
    """34 of 44 rows hold the text. A summary-length body means it is not being served."""
    r = client.get("/api/v2/commission/rsb-opinions?limit=10", headers=headers)
    items = r.json().get("data") or []
    whole = [i for i in items if len(i.get("body_txt") or "") >= 1200]
    assert len(whole) >= len(items) // 2, (
        f"only {len(whole)} of {len(items)} carried a whole opinion; "
        "full_text is probably not reaching the response")


def test_document_date_is_the_boards_date(client, headers):
    """Never the date Brubru captured it: the two are different fields for a reason."""
    r = client.get("/api/v2/commission/rsb-opinions?limit=10", headers=headers)
    for item in r.json().get("data") or []:
        assert item["document_date"] == item["opinion_date"], (
            "document_date must be the opinion date the Board states")
