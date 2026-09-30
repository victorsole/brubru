"""EEA procurement: SEDIA notices by EEA's buyer id, plus EEA's own calls for interest.

API audit, 30 Sep 2026 ("Walk · EEA"): the writer was a stub returning [], so
/eea-tenders had never held a row while the Funding & Tenders portal holds 212 EEA
notices. Fixtures are a SEDIA result and EEA's Plone JSON saved that day.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "eea"
NOW = datetime(2026, 9, 30, tzinfo=timezone.utc)


def test_notices_come_from_eea_buyer_id_and_are_deduplicated(monkeypatch):
    sedia = ap._sedia_helpers()
    seen = {}
    payload = json.loads((FIX / "sedia_one_notice.json").read_text())

    def fake_page(page, page_size=100, query=None, **k):
        seen["query"] = query
        return payload if page == 1 else {"results": []}
    monkeypatch.setattr(sedia, "fetch_sedia_page", fake_page)
    items = ap._eea_ft_notices(NOW)
    assert {"terms": {"cftPartyLegalEntityId": ["47352390"]}} in seen["query"]["bool"]["must"]
    assert len(items) == 1                                   # the same notice twice -> one row
    it = items[0]
    assert it.extras["tender_reference"] == "2bf63f5b-712c-4567-9976-a15faa197af0-CN"
    assert it.extras["status"] == "closed"
    assert it.document_date.date().isoformat() == "2023-11-17"
    assert it.extras["deadline"].date().isoformat() == "2023-12-18"
    assert it.public_url.startswith("https://ec.europa.eu/info/funding-tenders/")


def test_eea_own_call_reads_published_date_and_deadline(monkeypatch):
    class _R:
        def raise_for_status(self):
            pass

        def json(self):
            return json.loads((FIX / "plone_experts.json").read_text())
    monkeypatch.setattr(ap, "_EEA_CALLS", ("remunerated-scientific-experts",))
    monkeypatch.setattr(ap.requests, "get", lambda *a, **k: _R())
    items = ap._eea_own_calls(NOW)
    assert len(items) == 1
    it = items[0]
    assert it.document_date.date().isoformat() == "2024-05-14"
    assert it.extras["deadline"].date().isoformat() == "2026-11-10"
    assert it.extras["status"] == "open" and it.extras["tender_reference"] is None
    assert "call for expression of interest" in it.body_txt


def test_no_notices_is_an_error_not_an_empty_route(monkeypatch):
    sedia = ap._sedia_helpers()
    monkeypatch.setattr(sedia, "fetch_sedia_page", lambda *a, **k: {"results": []})
    import pytest
    with pytest.raises(RuntimeError):
        ap._eea_ft_notices(NOW)
