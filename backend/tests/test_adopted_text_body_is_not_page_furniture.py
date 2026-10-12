"""doceo's header box is never the text of an adopted act (12 Oct 2026).

doceo publishes an adopted text's page before its text. Fetched in that gap, the only
candidate container was the header box ("Select a document : ... Texts tabled : ..."), so
it won "most text wins", passed the 250-character minimum, and six resolutions were stored
and served with 260 characters of navigation as their full text. The job never looked
again, because the row had a body."""
import pathlib

from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper, is_page_furniture

BACKEND = pathlib.Path(__file__).resolve().parents[1]

HEADER = """<table class="doc_box_header"><tr><td>Select a document : Select... RC-B10-0398/2026
B10-0398/2026 B10-0399/2026 B10-0401/2026 B10-0405/2026 B10-0407/2026 Texts tabled : RC-B10-0398/2026
Debates : PV 16/09/2026 - 15.1 CRE 16/09/2026 - 15.1 Votes : PV 17/09/2026 - 9.1 Texts adopted :
P10_TA(2026)0309</td></tr></table>"""
BODY = "<table><tr class='contents'><td><p>The European Parliament,</p><p>" + ("having regard to its previous resolutions on Hong Kong and China, " * 12) + "</p></td></tr></table>"
URL = "https://www.europarl.europa.eu/doceo/document/TA-10-2026-0309_EN.html"


def _parse(html):
    return TextsAdoptedScraper()._parse_detail_page(f"<html><body>{html}</body></html>", "P10_TA(2026)0309", URL)


def test_a_page_with_only_its_header_box_has_no_text_yet():
    assert _parse(HEADER).full_text is None


def test_once_the_text_is_published_it_is_the_body_and_the_header_is_not_in_it():
    text = _parse(HEADER + BODY).full_text
    assert text.startswith("The European Parliament,")
    assert "Select a document" not in text


def test_furniture_is_recognised_by_what_it_says_not_by_its_length():
    assert is_page_furniture("Select a document : Select... RC-B10-0398/2026 Texts tabled : RC-B10-0398/2026")
    assert is_page_furniture("  select a document: x")
    # A real consent resolution is two short paragraphs; length must not condemn it.
    assert not is_page_furniture("(Consent) The European Parliament, 1. Gives its consent to the draft Council decision;")
    assert not is_page_furniture(None) and not is_page_furniture("")


def test_the_job_refuses_furniture_and_re_reads_a_row_that_stores_it():
    src = (BACKEND / "scripts" / "backfill_texts_adopted_bodies.py").read_text()
    assert "is_page_furniture(body)" in src
    assert "full_text IS NULL OR full_text ~* '^\\\\s*Select a document\\\\s*:'" in src
