"""ECHA procurement: current + closed calls, own pages, F&T notice date.

API audit, 30 Sep 2026 ("Walk · ECHA"): the reader took the current page only (4 of
113), pointed every row at the listing (#reference), wrote "Open" on every body,
stored the deadline as document_date and dropped rows without a reference.
Fixtures are the live pages saved that day.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "echa"
NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def test_current_page_keeps_rows_without_a_reference():
    rows = ap._echa_rows((FIX / "current.html").read_text(), current=True)
    assert len(rows) == 4
    adv = next(r for r in rows if "Advertisement" in r["title"])
    assert adv["reference"] == "" and adv["deadline"] is None
    assert all(r["url"].startswith("https://echa.europa.eu/-/") for r in rows)


def test_closed_page_is_read():
    rows = ap._echa_rows((FIX / "closed_calls.html").read_text(), current=False)
    assert len(rows) >= 100
    assert all(not r["current"] for r in rows)


def test_status_open_only_on_the_current_page_with_the_deadline_ahead():
    base = {"title": "t", "url": "u", "reference": "R", "kind": "Open"}
    assert ap._echa_item({**base, "current": True, "deadline": datetime(2026, 10, 22, tzinfo=timezone.utc)}, None, NOW).extras["status"] == "open"
    assert ap._echa_item({**base, "current": True, "deadline": datetime(2026, 9, 21, tzinfo=timezone.utc)}, None, NOW).extras["status"] == "closed"
    assert ap._echa_item({**base, "current": False, "deadline": datetime(2026, 12, 1, tzinfo=timezone.utc)}, None, NOW).extras["status"] == "closed"


def test_calls_for_interest_are_calls_and_the_rest_tenders():
    base = {"title": "t", "url": "u", "reference": "", "current": True, "deadline": None}
    assert ap._echa_item({**base, "kind": "Call for interest"}, None, NOW).item_type == "eoi_call"
    assert ap._echa_item({**base, "kind": "Market consultation"}, None, NOW).item_type == "tender"


def test_document_date_is_the_ft_notice_publication_date(monkeypatch):
    monkeypatch.setattr(ap, "_ft_notice_date",
                        lambda ident: datetime(2026, 9, 24, tzinfo=timezone.utc)
                        if ident == "7831c09c-9e13-4e9c-8c7c-f4286b985a39-PIN" else None)
    detail = ap._echa_detail((FIX / "detail_op0012_pin.html").read_text())
    assert detail["notices"] == ["7831c09c-9e13-4e9c-8c7c-f4286b985a39-PIN"]
    assert len(detail["description"]) >= 2
    row = {"title": "Market consultation", "url": "https://echa.europa.eu/-/x", "reference": "ECHA/2026/OP/0012",
           "kind": "Market consultation", "current": True, "deadline": datetime(2026, 10, 22, tzinfo=timezone.utc)}
    item = ap._echa_item(row, detail, NOW)
    assert item.document_date == datetime(2026, 9, 24, tzinfo=timezone.utc)
    assert "Procedure type: Market consultation" in item.body_txt


def test_no_notice_means_no_document_date(monkeypatch):
    monkeypatch.setattr(ap, "_ft_notice_date", lambda ident: (_ for _ in ()).throw(AssertionError("not called")))
    row = {"title": "t", "url": "u", "reference": "R", "kind": "Open", "current": False,
           "deadline": datetime(2012, 1, 1, tzinfo=timezone.utc)}
    item = ap._echa_item(row, {"description": ["d"], "links": [], "notices": []}, NOW)
    assert item.document_date is None
