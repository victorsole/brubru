"""/council-documents serves the whole text in `body_txt`, not its first 900 characters.

14 October 2026: on 524 of 615 Council register documents `body_txt` was exactly 900
characters long while `body_html` carried the whole document. The ingest stores the
text's first 900 characters as `summary`, and the endpoint put the summary first. The
stored text is the PDF's text (4 of 4 checked against the PDF that day), so nothing had
to be fetched again: the endpoint only had to serve what it held."""
from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from api.v1 import council_documents as cd  # noqa: E402

TEXT = ("ST 14398/26 Council of the European Union Brussels, 13 October 2026 "
        + "Proposal for a COUNCIL IMPLEMENTING DECISION amending Implementing Decision. " * 60
        + "Done at Brussels. For the Council The President")


def _row(html_content=TEXT, summary=TEXT[:900]):
    return SimpleNamespace(
        id="00000000-0000-0000-0000-000000000001", category="document", title="Proposal",
        summary=summary, url="https://data.consilium.europa.eu/doc/document/ST-14398-2026-INIT/en/pdf",
        language="en", published_date=datetime(2026, 10, 13, tzinfo=timezone.utc),
        policy_areas=[], tags=[], html_content=html_content,
        fetched_at=datetime(2026, 10, 13, 13, 9, tzinfo=timezone.utc),
        created_at=datetime(2026, 10, 13, 13, 9, tzinfo=timezone.utc))


def test_body_txt_is_the_whole_text_not_the_summary():
    txt, html = cd._pub_body(_row())
    assert len(TEXT) > 900
    assert txt == TEXT
    assert txt.endswith("For the Council The President")
    assert "For the Council The President" in html


def test_the_item_carries_the_whole_text_in_both_forms():
    item = cd._pub_to_item(_row())
    assert item.body_txt == TEXT
    assert item.body_html.startswith("<article>") and "The President" in item.body_html


def test_the_summary_is_the_fallback_for_a_row_without_text():
    txt, html = cd._pub_body(_row(html_content=None, summary="Media advisory - Foreign Affairs Council"))
    assert txt == "Media advisory - Foreign Affairs Council"
    assert html == "<article><p>Media advisory - Foreign Affairs Council</p></article>"
    assert cd._pub_body(_row(html_content="  ", summary=None)) == (None, None)


def test_real_html_is_served_as_its_text_and_its_markup():
    page = "<article><h1>Council conclusions</h1>" + "<p>The Council calls on the Member States.</p>" * 40 + "</article>"
    txt, html = cd._pub_body(_row(html_content=page, summary="The Council calls"))
    assert txt.count("The Council calls on the Member States.") == 40
    assert "<h1>Council conclusions</h1>" in html
