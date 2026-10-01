"""EIGE procurement: its own register (API audit, 1 Oct 2026, "Walk · EIGE").

The old reader parsed only the open-procedures page as a Views table EIGE does not use:
/eige-tenders read an empty table while every run reported success. Fixtures are EIGE
pages saved that day: the first closed-procedures page, one procedure page
(EIGE/2026/OPER/04) and the External Experts' Database page.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "eige"
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_archive_cards_carry_type_reference_and_closing_date():
    cards = ap._eige_cards((FIX / "closed_page0.html").read_text())
    assert len(cards) == 12
    c = cards[0]
    assert c["reference"] == "EIGE/2026/OPER/04" and c["type"] == "Ex-ante publicity notice"
    # 23:59 Europe/Vilnius is 20:59:59 UTC: the timestamp is a true instant
    assert c["closing"] == datetime(2026, 9, 16, 20, 59, 59, tzinfo=timezone.utc)
    assert c["url"] == "https://eige.europa.eu/about/procurement/eige-2026-oper-04"


def test_procedure_page_gives_publication_date_description_and_portal_link():
    d = ap._eige_detail((FIX / "detail_eige_2026_oper_04.html").read_text())
    assert d["published"].date().isoformat() == "2026-09-02"
    assert d["portal"] == ["09573b38-92fd-46c8-a106-47c6cb9bc29e-EXA"]
    assert ("h", "Contract") in d["blocks"]
    assert not any("receive alerts" in t.lower() for _k, t in d["blocks"])


def test_item_fields_and_status():
    row = ap._eige_cards((FIX / "closed_page0.html").read_text())[0]
    d = ap._eige_detail((FIX / "detail_eige_2026_oper_04.html").read_text())
    it = ap._eige_item(dict(row, related=[]), d, NOW)
    assert it.item_type == "tender" and it.extras["tender_reference"] == "EIGE/2026/OPER/04"
    assert it.extras["status"] == "closed"                      # closed 16 Sep
    assert it.document_date.date().isoformat() == "2026-09-02"
    open_it = ap._eige_item(dict(row, related=[]), d, datetime(2026, 9, 10, tzinfo=timezone.utc))
    assert open_it.extras["status"] == "open"


def test_one_row_per_reference_keeps_the_call_and_links_the_companion():
    """EIGE/2024/ADM/04: the call and its site-visit notice, two pages, one procedure."""
    site = {"url": "u/eige-2024-adm-04-0", "title": "Site visit for Provision of Cleaning Services",
            "type": "Call for tender", "reference": "EIGE/2024/ADM/04",
            "closing": datetime(2024, 7, 19, tzinfo=timezone.utc)}
    call = {"url": "u/eige-2024-adm-04", "title": "Provision of Cleaning Services",
            "type": "Call for tender", "reference": "EIGE/2024/ADM/04",
            "closing": datetime(2024, 7, 26, tzinfo=timezone.utc)}
    out = ap._eige_one_row_per_reference([site, call])
    assert len(out) == 1 and out[0]["url"] == "u/eige-2024-adm-04"
    assert out[0]["related"] == [{"title": site["title"], "url": site["url"]}]


def test_experts_call_is_a_standing_open_call_with_its_files():
    d = ap._eige_experts_detail((FIX / "external_experts.html").read_text())
    assert [f["title"] for f in d["files"]][:2] == ["EIGE’s Notice", "Draft Expert contract"]
    row = {"url": ap._EIGE_EXPERTS, "title": "External Experts' Database", "reference": "",
           "type": "Call for expression of interest", "closing": None, "standing": True, "related": []}
    it = ap._eige_item(row, d, NOW)
    assert it.item_type == "eoi_call" and it.extras["status"] == "open"
    assert it.extras["tender_reference"] is None and it.document_date is None   # none on the page
