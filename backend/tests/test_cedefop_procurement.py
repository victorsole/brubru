"""Cedefop procurement: full archive, publication date, extended deadline, own fields.

API audit, 30 Sep 2026 ("Walk · cedefop"): the old reader took page 0 only, dropped
the status column, stored the closing date as document_date and never saw an
extended closing date, so the open cleaning tender CEDEFOP/2026/OP/0012 read as
closed. Fixtures are the live pages saved that day.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "cedefop"
NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def _rows():
    return ap._cedefop_listing_rows((FIX / "listing_page0.html").read_text())


def test_listing_keeps_the_status_column():
    rows = _rows()
    assert len(rows) == 24
    assert all(r["status_raw"] for r in rows), "every row carries Cedefop's own status"
    op12 = next(r for r in rows if r["reference"] == "CEDEFOP/2026/OP/0012")
    assert op12["status_raw"] == "Open"


def test_detail_reads_publication_date_and_extended_deadline(monkeypatch):
    monkeypatch.setattr(ap, "_get_ok", lambda url: (FIX / "detail_op0012_extended.html").read_text())
    detail = ap._cedefop_detail("https://example.invalid/x")
    assert detail["Official Publication Date"] == "24/07/2026"
    assert detail["Closing date"] == "28/09/2026"
    assert detail["Extended closing date"] == "05/10/2026"
    assert detail["Procurement type"] == "Call for tenders"
    assert any("ted.europa.eu" in u for u in detail["links"])


def test_item_uses_publication_date_and_extended_deadline(monkeypatch):
    monkeypatch.setattr(ap, "_get_ok", lambda url: (FIX / "detail_op0012_extended.html").read_text())
    row = next(r for r in _rows() if r["reference"] == "CEDEFOP/2026/OP/0012")
    item = ap._cedefop_item(row, ap._cedefop_detail(row["url"]), NOW)
    assert item.item_type == "tender"
    assert item.document_date == datetime(2026, 7, 24, tzinfo=timezone.utc)
    assert item.extras["deadline"] == datetime(2026, 10, 5, tzinfo=timezone.utc)
    assert item.extras["status"] == "open"
    assert item.extras["tender_reference"] == "CEDEFOP/2026/OP/0012"
    assert len(item.body_txt) > 500 and "Extended closing date: 2026-10-05" in item.body_txt


def test_row_not_reread_sends_no_date_deadline_or_body():
    """The upsert keeps stored values when these are NULL; a listing-only row must
    not overwrite a detail-read publication date with nothing, or a deadline with
    the unextended closing date."""
    row = _rows()[-1]
    item = ap._cedefop_item(row, None, NOW)
    assert item.document_date is None and item.body_txt is None
    assert "deadline" not in item.extras
    assert item.extras["status"] == "closed"


@pytest.mark.parametrize("raw,deadline,expected", [
    ("Open", datetime(2026, 10, 5, tzinfo=timezone.utc), "open"),
    ("Open", datetime(2026, 9, 1, tzinfo=timezone.utc), "closed"),   # passed deadline
    ("Open", None, "closed"),                                       # open needs evidence
    ("In progress", datetime(2026, 10, 5, tzinfo=timezone.utc), "closed"),
    ("Completed", None, "closed"),
])
def test_status_uses_the_funding_vocabulary(raw, deadline, expected):
    assert ap._cedefop_status(raw, deadline, NOW) == expected


def test_a_failed_listing_fetch_is_an_error_not_zero_rows(monkeypatch):
    ap._CEDEFOP_CACHE.clear()

    class _Resp:
        status_code = 503
        text = "<html>maintenance</html>"

        def raise_for_status(self):
            import requests
            raise requests.HTTPError("503")

    monkeypatch.setattr(ap.requests, "get", lambda *a, **k: _Resp())
    with pytest.raises(Exception):
        ap._cedefop_all(fetch_bodies=False)


def test_upsert_carries_the_procurement_columns():
    from sync_economy import _UPSERT, _UPSERT_BATCH
    for sql in (_UPSERT, _UPSERT_BATCH):
        for col in ("tender_reference", "status", "deadline"):
            assert f"{col}" in sql.split("VALUES")[0], col
            assert f"economy_items.{col}" in sql, f"{col} must never regress to NULL"


# Bodies walked in the API audit and moved onto the procurement fields. A body is
# added here in the same commit that switches its routes to procurement=True.
_PROCUREMENT_BODIES = ("cedefop", "ecdc", "echa", "eea", "efca", "efsa")


def test_only_walked_bodies_expose_the_procurement_fields():
    os.environ.setdefault("TESTING", "1")
    from api.v2.funding.agency_procurement import router
    models = {r.path: r.response_model for r in router.routes if hasattr(r, "response_model")}
    walked = [p for p in models if any(f"/{b}-" in p for b in _PROCUREMENT_BODIES)]
    other = [p for p in models if p not in walked]
    assert walked and all("tender_reference" in _fields(models[p]) for p in walked)
    assert other and not any("tender_reference" in _fields(models[p]) for p in other)


def _fields(model) -> set:
    fields = getattr(model, "model_fields", {})
    if "data" in fields:  # PaginatedResponse[Item]
        inner = fields["data"].annotation.__args__[0]
        return set(inner.model_fields)
    return set(fields)


def test_undated_procedures_sort_by_deadline_not_ingest_time():
    """70 Cedefop procedures (2010-2014) publish no publication date; with the
    ingest-time fallback they topped the newest-first list. The shared order must
    stay deadline-free: /funding/all reuses it on a UNION with no deadline column."""
    from api.v2.economy_endpoints import _ORDER_SQL, _PROC_ORDER_SQL
    assert "deadline" in _PROC_ORDER_SQL["recent"]
    assert "document_date, deadline" in _PROC_ORDER_SQL["recent"]
    assert "deadline" not in _ORDER_SQL["recent"]


def test_a_listing_only_read_keeps_the_stored_type(monkeypatch):
    """30 Sep 2026, first daily run: 9 archived calls whose page was not re-read were
    guessed as tenders from their reference; 7 were duplicated, 2 moved."""
    import sync_economy
    from services.scrapers.economy_common import Item

    class _S:
        def execute(self, *a, **k):
            class _R:
                def all(self_inner):
                    return [("cedefop", "https://x/greek-donation", None, "eoi_call"),
                            ("cedefop", "https://x/eacea-07", "EACEA/07", "eoi_call")]
            return _R()

        def close(self):
            pass

    monkeypatch.setattr("core.database.SessionLocal", lambda: _S())
    guess = [Item(body_code="cedefop", item_type="tender", title="t", public_url="https://x/greek-donation",
                  extras={"tender_reference": None, "type_from_page": False}),
             Item(body_code="cedefop", item_type="tender", title="t", public_url="https://x/eacea-07-renamed",
                  extras={"tender_reference": "EACEA/07", "type_from_page": False}),
             Item(body_code="cedefop", item_type="tender", title="t", public_url="https://x/read",
                  extras={"tender_reference": "R/1", "type_from_page": True})]
    sync_economy._keep_stored_type(guess)
    assert [i.item_type for i in guess] == ["eoi_call", "eoi_call", "tender"]
