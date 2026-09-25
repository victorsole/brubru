"""EPRS: the blog post is a summary of the study, not the study.

`eprs_publications` held 920 rows averaging 53 characters of text, and the MCP `search_eprs`
tool reads that table, so the hole reached the chat as well as the API. Measured on
EPRS_BRI(2026)782664 on 25 September 2026: the epthinktank post gives 1,115 characters, the
Think Tank record page 1,388, and the PDF behind them 29,491. Storing the first would repeat
the mistake this backfill exists to correct, one level further up.
"""
import pathlib
import sys

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_BACKEND), str(_BACKEND / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import backfill_eprs_full_text as eprs  # noqa: E402

_RECORD = "https://www.europarl.europa.eu/thinktank/en/document/EPRS_BRI(2026)782664"
_EN = "https://www.europarl.europa.eu/RegData/etudes/BRIE/2026/782664/EPRS_BRI(2026)782664_EN.pdf"
_ES = "https://www.europarl.europa.eu/RegData/etudes/BRIE/2026/782664/EPRS_BRI(2026)782664_ES.pdf"


def test_the_english_pdf_wins_when_several_languages_are_listed():
    """Taking the first match stored a Spanish study for an English row."""
    html = f'<a href="{_ES}">ES</a><a href="{_EN}">EN</a><a href="x_FR.pdf">FR</a>'
    assert eprs._pick_english(html) == _EN


def test_a_single_language_publication_keeps_its_own_language():
    """Preferring EN was right; refusing everything else was over-correcting.

    A comparative-law study published only in Spanish is not served by refusing its PDF.
    """
    html = f'<a href="{_ES}">ES</a>'
    assert eprs._pick_english(html) == _ES


def test_no_pdf_at_all_is_none():
    assert eprs._pick_english("<a href='/about'>about</a>") is None


def test_the_chain_goes_blog_then_record_then_pdf(monkeypatch):
    pages = {
        "https://epthinktank.eu/2026/02/24/x/": f'<a href="{_RECORD}">Read the briefing</a>',
        _RECORD: f'<a href="{_ES}">ES</a><a href="{_EN}">EN</a>',
    }
    asked = []

    def fake_read(url, timeout, accept="*/*"):
        asked.append(url)
        return pages[url].encode()

    monkeypatch.setattr(eprs, "_read", fake_read)
    assert eprs._follow_to_the_document("https://epthinktank.eu/2026/02/24/x/") == _EN
    assert asked == ["https://epthinktank.eu/2026/02/24/x/", _RECORD]


def test_a_direct_pdf_link_short_circuits_the_record(monkeypatch):
    monkeypatch.setattr(eprs, "_read",
                        lambda url, timeout, accept="*/*": f'<a href="{_EN}">PDF</a>'.encode())
    assert eprs._follow_to_the_document("https://epthinktank.eu/2026/02/24/x/") == _EN


def test_the_page_is_the_fallback_when_no_document_is_reachable(monkeypatch):
    """1,115 characters of summary still beats the 53 characters these rows hold."""
    class Row:
        html_url = "https://epthinktank.eu/2026/02/24/x/"
        pdf_url = None
        have = 53

    monkeypatch.setattr(eprs, "_follow_to_the_document", lambda url, timeout=40: None)
    monkeypatch.setattr(eprs, "fetch",
                        lambda url, render=False: ("The summary of the study. " * 40, None, None))
    body, reason = eprs.best_body(Row(), render=False)
    assert reason is None and body.startswith("The summary")


def test_nul_and_surrogates_are_cleaned():
    assert eprs.clean("a\x00b") == "ab"
    assert eprs.clean("a\udbc0b") == "ab"
    assert eprs.clean("") is None
