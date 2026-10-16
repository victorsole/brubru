"""An adopted text carries every part of its page, Parliament's position included (16 Oct 2026).

A TA page is one table per part: the legislative resolution, then Parliament's position
(the act). The parser kept the first tr.contents only, so 90 texts stopped at "Adopts its
position at first reading hereinafter set out" (AGILE: 1,671 of ~92,000 characters)."""
from __future__ import annotations

from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper

PAGE = """<html><body>
<table class="doc_box_header"><tr><td>Select a document : Texts adopted</td></tr></table>
<table><tr class="doc_title"><td>European Parliament legislative resolution of 6 October 2026 on the proposal for a
regulation establishing the Programme for agile and rapid defence innovation (AGILE)</td></tr>
<tr class="contents"><td><p>(Ordinary legislative procedure: first reading)</p><p>The European Parliament,</p>
<p>1. Adopts its position at first reading hereinafter set out;</p></td></tr></table>
<table><tr class="doc_title"><td>Position of the European Parliament adopted at first reading on 6 October 2026</td></tr>
<tr class="contents"><td><p>THE EUROPEAN PARLIAMENT AND THE COUNCIL OF THE EUROPEAN UNION,</p>
<p>Article 1 Subject matter</p><p>This Regulation establishes the Programme for agile and rapid defence innovation.</p>
</td></tr></table></body></html>"""


def test_both_parts_and_their_headings_are_read():
    got = TextsAdoptedScraper()._parse_detail_page(PAGE, "P10_TA(2026)0320", "https://example.invalid/TA")
    text = got.full_text
    assert text.index("European Parliament legislative resolution") < text.index("hereinafter set out")
    assert text.index("hereinafter set out") < text.index("Position of the European Parliament adopted")
    assert "Article 1 Subject matter" in text and "This Regulation establishes" in text
    assert "Select a document" not in text
