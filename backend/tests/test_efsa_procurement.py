"""EFSA procurement: portal notices by buyer id + EFSA's own archive of small procedures.

API audit, 30 Sep 2026 ("Walk · EFSA"). Fixture: EFSA's archive page saved that day.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402
from services.scrapers.economy_common import Item  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "efsa"
NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def test_archive_cards_carry_reference_budget_launch_deadline():
    rows = ap._efsa_negotiated_cards((FIX / "negotiated_page0.html").read_text())
    assert len(rows) == 10
    first = rows[0]
    assert first["reference"] == "NP/EFSA/KNOW/2025/01"
    assert first["budget"] == "25000" and first["launch"] == "October 2025"
    assert first["deadline"].date().isoformat() == "2025-10-08"
    assert first["url"].startswith("https://www.efsa.europa.eu/en/call/")


def _item(ref, title, kind="efsa_ft_notice", status="closed"):
    return Item(body_code="efsa", item_type="tender", title=title, public_url=f"https://x/{ref}",
                source_kind=kind, extras={"tender_reference": ref, "status": status, "deadline": None})


def test_an_archive_procedure_also_on_the_portal_is_dropped():
    portal = [_item("abc-EXA", "Further development of EFSA's TKPlate Platform for toxicokinetic modelling")]
    archive = [_item("NP/EFSA/ED/2025/01", "NP/EFSA/ED/2025/01 - Further development of EFSA's TKPlate Platform for toxicokinetic modelling", "efsa_negotiated"),
               _item("NP/EFSA/COM/2025/01", "NP/EFSA/COM/2025/01 - Acquisition of consumer panel data", "efsa_negotiated")]
    kept = ap._efsa_drop_portal_duplicates(portal, archive)
    assert [k.extras["tender_reference"] for k in kept] == ["NP/EFSA/COM/2025/01"]


def test_a_prior_notice_is_closed_once_its_contract_notice_exists(monkeypatch):
    sedia = ap._sedia_helpers()

    def res(ident, status):
        return {"metadata": {"identifier": [ident], "title": ["Emerging risk"], "status": [status],
                             "startDate": ["2026-04-16T00:00:00.000+0000"], "type": ["0"]}}
    monkeypatch.setattr(sedia, "fetch_sedia_page", lambda p, **k: {"results": [
        res("53fb5f38-b55a-46eb-b90b-d77951370687-PIN", "31094502"),
        res("53fb5f38-b55a-46eb-b90b-d77951370687-CN", "31094502"),
        res("11111111-1111-1111-1111-111111111111-PIN", "31094501")]} if p == 1 else {"results": []})
    items = {i.extras["tender_reference"]: i.extras["status"] for i in
             ap._ft_buyer_notices(body_code="efsa", buyer_id="47352394", source_kind="efsa_ft_notice", now=NOW)}
    assert items["53fb5f38-b55a-46eb-b90b-d77951370687-PIN"] == "closed"
    assert items["11111111-1111-1111-1111-111111111111-PIN"] == "forthcoming"   # SEDIA's label kept


# --- Part B (30 Sep 2026): each archive procedure's own page ------------------------ #
_CALLS = Path(__file__).resolve().parent / "fixtures" / "efsa"


def _call(name):
    return ap._efsa_call_detail((_CALLS / name).read_text())


def test_call_page_gives_the_publication_date():
    assert _call("call_np_prev_2024_02.html")["published"] == datetime(2024, 5, 16, tzinfo=timezone.utc)


def test_efsa_deadline_is_parma_wall_time_not_utc():
    """<time datetime="...18:00:00Z"> is shown as "18:00 (CEST)": 16:00 UTC, not 18:00."""
    assert _call("call_np_know_2025_01_cob.html")["deadline"] == datetime(2025, 10, 8, 16, 0, tzinfo=timezone.utc)
    assert _call("call_np_prev_2024_02.html")["deadline"] == datetime(2024, 6, 14, 21, 59, 59, tzinfo=timezone.utc)
    # winter: CET, one hour
    assert _call("call_strategy_no_ref_in_title.html")["deadline"] == datetime(2023, 1, 13, 22, 59, 59, tzinfo=timezone.utc)
    assert ap._efsa_wall_time("2025-07-31T23:59:59Z") == datetime(2025, 7, 31, 21, 59, 59, tzinfo=timezone.utc)


def test_reference_only_from_a_labelled_line():
    assert _call("call_strategy_no_ref_in_title.html")["reference"] == "NP/EFSA/GPS/2022/01"
    assert _call("call_np_know_2025_01_cob.html")["reference"] == ""   # only in the title
    # a description citing an earlier procedure does not become the reference
    page = '<p>In 2019 EFSA launched a negotiated procedure (NP/EFSA/DATA/2019/01).</p>'
    assert ap._efsa_call_detail(page)["reference"] == ""


def test_call_page_description_keeps_its_structure():
    blocks = _call("call_np_prev_2024_02.html")["blocks"]
    assert ("h", "Background") in blocks
    assert sum(len(t) for _k, t in blocks) > 2000
    html = ap._efsa_blocks_html([("h", "Tasks"), ("li", "a"), ("li", "b"), ("p", "c")])
    assert html == "<h2>Tasks</h2><ul><li>a</li><li>b</li></ul><p>c</p>"
