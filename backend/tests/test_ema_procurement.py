"""EMA procurement from the Funding & Tenders portal (API audit, 1 Oct 2026, "Walk · EMA").

The old reader parsed EMA's procurement page, which shows only current notices: 7 rows,
every link EMA's home page plus a fragment, the deadline stored as the publication date
and every row "Open". EMA sends readers to the portal (buyer 47352428) for everything
else, so the whole archive is read there. Fixture: three EMA notices saved that day.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "ema"
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _items(monkeypatch, split=True):
    results = json.loads((FIX / "sedia_notices.json").read_text())
    monkeypatch.setattr(ap, "_ft_buyer_results", lambda body, buyer: results)
    return ap._ft_buyer_notices(body_code="ema", buyer_id="47352428", source_kind="ema_ft_notice",
                                now=NOW, split_eoi=split)


def test_expert_calls_split_by_the_portal_procedure_type(monkeypatch):
    items = {i.extras["tender_reference"]: i for i in _items(monkeypatch)}
    eoi = next(i for r, i in items.items() if r.startswith("e0b036c6"))
    cn = next(i for r, i in items.items() if r.startswith("35671487") and r.endswith("-CN"))
    assert eoi.item_type == "eoi_call" and "call for expression of interest" in eoi.body_txt
    assert cn.item_type == "tender"


def test_buyer_reference_is_in_body_and_summary(monkeypatch):
    cn = next(i for i in _items(monkeypatch) if i.extras["tender_reference"].startswith("35671487")
              and i.extras["tender_reference"].endswith("-CN"))
    assert "Buyer's reference: EMA/2026/OP/0015" in cn.body_txt
    assert "EMA/2026/OP/0015" in cn.summary
    assert cn.public_url.startswith("https://ec.europa.eu/info/funding-tenders/")
    assert cn.document_date is not None and cn.extras["deadline"] is not None


def test_without_split_everything_stays_a_tender(monkeypatch):
    assert {i.item_type for i in _items(monkeypatch, split=False)} == {"tender"}
