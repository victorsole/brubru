"""ECDC procurement: full archive, derived status, published_time as document_date.

API audit, 30 Sep 2026 ("Walk · ECDC"): the reader took pages 0-3 only (29 of 174),
looked for a status ECDC never prints, stored the deadline as document_date and
composed a 3-line body. Fixtures are the live pages saved that day.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "ecdc"
NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def _serve(monkeypatch, name):
    monkeypatch.setattr(ap, "_ecdc_get", lambda url: (FIX / name).read_text())


def test_listing_cards_carry_reference_kind_and_deadline():
    rows = ap._ecdc_cards((FIX / "listing_page0.html").read_text())
    assert len(rows) == 5
    assert all(r["reference"] and r["kind"] and r["deadline"] for r in rows)
    assert {r["kind"] for r in rows} <= {"ex-ante publicity", "call for tender", "call for proposal"}


def test_published_time_is_the_document_date_even_without_last_updated(monkeypatch):
    """OP/0018 has no 'Page last updated' line: the old parser lost its whole body."""
    _serve(monkeypatch, "detail_op0018_no_last_updated.html")
    d = ap._ecdc_detail("https://example.invalid/op0018")
    assert d["published"] == datetime.fromisoformat("2026-09-10T10:14:16+02:00")
    assert d["updated"] is None
    assert len(d["description"]) >= 3
    row = {"title": "OP/0018", "url": "https://example.invalid/op0018",
           "reference": "ECDC/2026/OP/0018 SPR/260834", "kind": "call for tender",
           "deadline": datetime(2026, 10, 26, 15, tzinfo=timezone.utc)}
    item = ap._ecdc_item(row, d, NOW)
    assert item.document_date == d["published"]
    assert item.extras["status"] == "open"
    assert item.extras["deadline"] == row["deadline"]
    assert "Procurement type: call for tender" in item.body_txt and len(item.body_txt) > 1000


def test_a_migration_date_after_the_deadline_is_not_a_publication_date(monkeypatch):
    """27 pages carry published_time 2017-07-27 (site migration) on procedures that
    closed in 2016-2017. A notice cannot be published after its deadline."""
    _serve(monkeypatch, "detail_np2016_migrated.html")
    d = ap._ecdc_detail("https://example.invalid/np2016")
    assert d["published"].date().isoformat() == "2017-07-27"
    row = {"title": "NP/2016", "url": "https://example.invalid/np2016",
           "reference": "NP/2016/RMC/5979", "kind": "ex-ante publicity",
           "deadline": datetime(2016, 12, 12, tzinfo=timezone.utc)}
    assert ap._ecdc_item(row, d, NOW).document_date is None


@pytest.mark.parametrize("deadline,expected", [
    (datetime(2026, 10, 5, tzinfo=timezone.utc), "open"),
    (datetime(2026, 9, 1, tzinfo=timezone.utc), "closed"),
    (None, "closed"),
])
def test_status_is_derived_from_the_deadline(deadline, expected):
    row = {"title": "t", "url": "u", "reference": "r", "kind": "call for tender", "deadline": deadline}
    assert ap._ecdc_item(row, None, NOW).extras["status"] == expected


def test_a_row_not_reread_sends_no_date_or_body():
    row = {"title": "t", "url": "u", "reference": "r", "kind": "ex-ante publicity",
           "deadline": datetime(2019, 1, 1, tzinfo=timezone.utc)}
    item = ap._ecdc_item(row, None, NOW)
    assert item.document_date is None and item.body_txt is None


def test_429_is_retried_then_succeeds(monkeypatch):
    calls = []

    class _R:
        def __init__(self, code):
            self.status_code, self.text = code, "<html>ok</html>"

        def raise_for_status(self):
            if self.status_code >= 400:
                import requests
                raise requests.HTTPError(str(self.status_code))

    responses = iter([_R(429), _R(429), _R(200)])
    monkeypatch.setattr(ap.requests, "get", lambda *a, **k: calls.append(1) or next(responses))
    monkeypatch.setattr(ap, "_ECDC_BACKOFF", (0, 0, 0))
    monkeypatch.setattr(ap, "_ECDC_PAUSE", 0)
    assert ap._ecdc_get("https://example.invalid") == "<html>ok</html>"
    assert len(calls) == 3
