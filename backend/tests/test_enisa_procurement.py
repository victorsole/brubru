"""ENISA procurement (API audit, 1 Oct 2026, "Walk · ENISA").

The old reader took page 0 of 26 (15 of 254 procedures), stored the deadline as
document_date and filled no procurement field. Fixtures: the first list page and the
page of ENISA/2026/RP/0012, saved that day.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "enisa"
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def test_list_row_fields():
    rows = ap._enisa_rows((FIX / "list_page0.html").read_text())
    r = next(x for x in rows if x["reference"] == "ENISA/2026/RP/0012")
    # 26 Oct 2026 10:00 Europe/Athens (EET after the clock change) = 08:00 UTC
    assert r["deadline"] == datetime(2026, 10, 26, 8, 0, tzinfo=timezone.utc)
    assert r["status_raw"] == "Open" and r["call_type"] == "Restricted call"


def test_detail_description_downloads_and_portal_link():
    d = ap._enisa_detail((FIX / "detail_enisa_2026_rp_0012.html").read_text())
    assert d["blocks"][0] == ("h", "Maximum budget: € 2.000.000,00 over 4 years")
    assert [f["url"].rsplit("/", 1)[-1] for f in d["files"]] == ["Tender%20ENISA_2026_RP_0012.docx"]
    assert d["portal"] == ["daf1d26a-0a1d-47f3-acf2-23b5b9ed395e-CN"]
    assert d["facts"]["Procedure type"] == "Restricted call - Service"


def test_status_vocabulary():
    future = datetime(2026, 12, 1, tzinfo=timezone.utc)
    assert ap._enisa_status("Open", "Restricted call", future, NOW) == "open"
    assert ap._enisa_status("Open", "Pre Information Notice", future, NOW) == "forthcoming"
    assert ap._enisa_status("In progress", "Open call", future, NOW) == "closed"
    assert ap._enisa_status("Open", "Open call", datetime(2026, 9, 1, tzinfo=timezone.utc), NOW) == "closed"


def test_item_publication_date_is_the_portal_notice():
    rows = ap._enisa_rows((FIX / "list_page0.html").read_text())
    r = next(x for x in rows if x["reference"] == "ENISA/2026/RP/0012")
    d = ap._enisa_detail((FIX / "detail_enisa_2026_rp_0012.html").read_text())
    it = ap._enisa_item(dict(r, related=[]), d, datetime(2026, 9, 18, tzinfo=timezone.utc), NOW)
    assert it.extras["tender_reference"] == "ENISA/2026/RP/0012" and it.extras["status"] == "open"
    assert it.document_date == datetime(2026, 9, 18, tzinfo=timezone.utc)
    assert "Status on ENISA's site: Open" in it.body_txt


def test_old_copy_of_a_page_is_one_procedure():
    live = {"url": "u/Provision-of-a-CRM-product", "title": "CRM", "reference": "P.16.11.TCD",
            "deadline": datetime(2011, 9, 1, tzinfo=timezone.utc)}
    old = dict(live, url="u/Provision-of-a-CRM-product_old")
    out = ap._enisa_one_row_per_reference([old, live])
    assert len(out) == 1 and out[0]["url"] == live["url"] and out[0]["related"][0]["url"] == old["url"]


def test_reference_keys_join_either_code():
    keys = ap._enisa_ref_keys("ENISA F-EDO-23-T18 (ENISA/2023/OP/0010)")
    assert "2023OP0010" in keys and "FEDO23T18" in keys
    assert ap._enisa_ref_keys("ENISA D-COD-16-T05.") == {"DCOD16T05"}
    by_key = {"2023OP0010": ["n1-CN"]}
    assert ap._enisa_linked_notices("ENISA F-EDO-23-T18 (ENISA/2023/OP/0010)", [], by_key) == ["n1-CN"]
    assert ap._enisa_linked_notices("x", ["linked-CN"], by_key) == ["linked-CN"]   # the page's link wins
