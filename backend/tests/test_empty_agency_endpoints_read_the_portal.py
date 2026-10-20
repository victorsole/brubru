"""Four agency endpoints answered total 0 since they were published (20 Oct 2026).

/funding/eurofound-tenders, eurofound-calls, fra-tenders and eu-osha-calls: Eurofound's page was
parsed with EU-OSHA's markup, FRA's page (behind a bot challenge) said "no open procedures" while
the Funding & Tenders portal held two open FRA tenders, and EU-OSHA's calls page gave nothing
while the portal listed an open call for experts. They now read the portal by buyer id, as EMA,
EEA, EFSA, ENISA and ECDC do (Victor, 30 Sep 2026).
"""
import importlib
import pathlib
import sys
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
ap = importlib.import_module("services.scrapers.agency_procurement")


def _fake_portal(monkeypatch):
    calls = []

    def notices(*, body_code, buyer_id, source_kind, now, split_eoi=False):
        calls.append((body_code, buyer_id, split_eoi))
        return [SimpleNamespace(item_type="tender", title=f"{body_code} tender", extras={}),
                SimpleNamespace(item_type="eoi_call", title=f"{body_code} experts", extras={})]
    monkeypatch.setattr(ap, "_ft_buyer_notices", notices)
    monkeypatch.setattr(ap, "_FT_AGENCY_CACHE", {})
    return calls


def test_each_agency_reads_its_own_buyer_id_once(monkeypatch):
    calls = _fake_portal(monkeypatch)
    assert [i.title for i in ap.ingest_eurofound_tenders()] == ["eurofound tender"]
    assert [i.title for i in ap.ingest_eurofound_calls()] == ["eurofound experts"]
    assert [i.title for i in ap.ingest_eu_osha_calls()] == ["eu_osha experts"]
    assert calls == [("eurofound", "47352392", True), ("eu_osha", "47352424", True)]   # cached per agency


def test_fra_serves_its_calls_for_interest_as_tenders(monkeypatch):
    _fake_portal(monkeypatch)
    items = ap.ingest_fra_tenders()
    assert {i.item_type for i in items} == {"tender"} and len(items) == 2


def test_eu_osha_tenders_come_from_the_portal(monkeypatch):
    # 20 Oct 2026: its own pages gave 11 tenders with 155-313-character bodies; the portal 96.
    calls = _fake_portal(monkeypatch)
    assert [i.title for i in ap.ingest_eu_osha_tenders()] == ["eu_osha tender"]
    assert calls == [("eu_osha", "47352424", True)]


def test_a_body_selling_its_own_assets_is_not_a_tender():
    # 20 Oct 2026: nine auctions, disposals and giveaways were served as tenders and calls.
    se = importlib.import_module("scripts.sync_economy")
    def it(title, item_type="tender"):
        return SimpleNamespace(item_type=item_type, title=title)
    for t in ("Notice of public auction - furniture", "Auction Sale of Agency Vehicle",
              "Disposal of furniture and ICT equipment", "AUCTION – SALE OF USED VEHICLES",
              "Διατίθεται δωρεάν ο παλιός εξοπλισμός του Cedefop"):
        assert se._is_asset_disposal(it(t)), t
    for t in ("Provision of auction platform services", "Sale of publications service"):
        assert not se._is_asset_disposal(it(t)), t
    assert not se._is_asset_disposal(it("Fixed Premium Auction for RFNBO hydrogen", "grant"))
