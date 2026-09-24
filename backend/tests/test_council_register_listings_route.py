"""A discovery route for the Council register while its search stays walled (24 Sep 2026).

The public-register SEARCH is behind Cloudflare and stayed there under every route tried
that day: plain HTTP, our own stealth browser at 12s settle, and Scrape.do in plain,
render and super modes (502 each, uncharged). Because every date window went through the
search, the register corpus had stopped moving.

Two of the register's own listings are NOT walled and carry current, dated, referenced
documents: `/latest/` (meeting convocations) and `/oj-council/` (provisional agendas).
They are a narrower window than the search, so the point of these tests is as much what
the route must NOT claim as what it returns: a listing that finds nine documents must
never read as a register that holds nine documents, and a listing that fails must be
reported rather than counted as zero.

No network.
"""
from __future__ import annotations

import pathlib
import sys
from datetime import date

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from services.scrapers import council_register as cr  # noqa: E402

# Shaped on the live markup read on 24 September 2026: one row per document, one link
# per language, the subject codes and the meeting date in the row's text.
LISTING_HTML = """
<html><body>
 <ul>
  <li>
    <span>ST 13104 2026 INIT - PROVISIONAL AGENDA</span>
    <a href="https://data.consilium.europa.eu/doc/document/ST-13104-2026-INIT/bg/pdf">BG</a>
    <a href="https://data.consilium.europa.eu/doc/document/ST-13104-2026-INIT/en/pdf">EN</a>
    <a href="https://data.consilium.europa.eu/doc/document/ST-13104-2026-INIT/fr/pdf">FR</a>
    COUNCIL OF THE EUROPEAN UNION (Competitiveness)
    Subject matters: COMPET, RECH, ESPACE
    Date of meeting 24/09/2026
  </li>
  <li>
    <a href="https://data.consilium.europa.eu/doc/document/CM-4232-2026-INIT/en/pdf">EN</a>
    Working Party on Public Health
    Subject matters: SAN, PHARM
    Date of meeting 02/10/2026
  </li>
 </ul>
</body></html>
"""

CHALLENGE_HTML = (
    "<html><head><title>Just a moment...</title></head><body>"
    "Checking your browser before accessing a GSC Managed Website"
    + ("x" * 14000) + "</body></html>"
)


# --------------------------------------------------------------------------- parsing
def test_one_row_per_document_not_one_per_language():
    docs = cr._parse_listing(LISTING_HTML)
    assert sorted(d.external_id for d in docs) == ["CM-4232-2026-INIT", "ST-13104-2026-INIT"]


def test_english_is_preferred_whatever_order_the_languages_appear_in():
    """Bulgarian comes first in the markup; the row must still land on the English PDF."""
    docs = {d.external_id: d for d in cr._parse_listing(LISTING_HTML)}
    assert docs["ST-13104-2026-INIT"].url.endswith("/en/pdf")


def test_the_meeting_date_is_read():
    docs = {d.external_id: d for d in cr._parse_listing(LISTING_HTML)}
    assert docs["ST-13104-2026-INIT"].published == date(2026, 9, 24)
    assert docs["CM-4232-2026-INIT"].published == date(2026, 10, 2)


def test_subject_codes_are_kept_and_the_title_is_a_title():
    docs = {d.external_id: d for d in cr._parse_listing(LISTING_HTML)}
    st = docs["ST-13104-2026-INIT"]
    assert st.subject_matters == ["COMPET", "RECH", "ESPACE"]
    # Brubru's standing rule: no institutional codes in a title. The reference is
    # carried by external_id, which is where a code belongs.
    assert "ST 13104" not in st.title and st.title


def test_a_page_with_no_documents_is_simply_empty():
    assert cr._parse_listing("<html><body><p>nothing here</p></body></html>") == []


# --------------------------------------------------------------------------- honesty
def test_a_blocked_listing_is_reported_not_counted_as_zero(monkeypatch):
    """The failure this whole route exists to avoid: a block read as an empty register."""
    def _blocked(url):
        raise RuntimeError("consilium returned a BROWSER-CHALLENGE page")

    monkeypatch.setattr(cr, "_fetch_rendered", _blocked)
    docs, failed = cr.fetch_register_listings()
    assert docs == []
    assert len(failed) == 2 and all("RuntimeError" in f for f in failed)


def test_one_listing_down_does_not_hide_the_other(monkeypatch):
    def _half(url):
        if url == cr.REGISTER_OJ:
            raise RuntimeError("challenge")
        return LISTING_HTML

    monkeypatch.setattr(cr, "_fetch_rendered", _half)
    docs, failed = cr.fetch_register_listings()
    assert len(docs) == 2
    assert [f.split(":")[0] for f in failed] == ["oj-council"]


def test_the_two_listings_are_deduplicated_against_each_other(monkeypatch):
    monkeypatch.setattr(cr, "_fetch_rendered", lambda url: LISTING_HTML)
    docs, failed = cr.fetch_register_listings()
    assert failed == []
    assert len(docs) == 2  # the same two documents, not four


def test_the_search_is_still_the_search(monkeypatch):
    """The listings are a fallback, not a replacement: a caller asking for a date window
    must still get the block reported, or a narrow route would pass as a full register."""
    monkeypatch.setattr(cr, "_fetch_rendered",
                        lambda url: (_ for _ in ()).throw(RuntimeError("BROWSER-CHALLENGE")))
    with pytest.raises(RuntimeError, match="CHALLENGE"):
        cr.search_by_date(date(2026, 9, 1), date(2026, 9, 24))
