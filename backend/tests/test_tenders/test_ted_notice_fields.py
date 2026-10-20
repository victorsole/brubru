"""What a TED notice says about itself reaches the row and the API (20 Oct 2026).

A partner session reading /api/v2/funding/tenders found: Swedish notices of "EUR 10m" (SEK in
the notice), form_type empty on every notice, no buyer level, and values missing where the
lots carry them. The two fixtures are real notices from the table: 726269-2026 (a Swedish
local authority, SEK 10,000,000) and 726130-2026 (a Polish local authority, no notice-level
value, two lots in PLN).
"""
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

from services.tenders.eforms_parser import EFormsParser, buyer_level, form_type_of, lots_total  # noqa: E402

FIX = BACKEND / "tests" / "fixtures" / "ted"
SEK = (FIX / "sek_local_726269-2026.xml").read_text()
LOTS = (FIX / "lots_only_726130-2026.xml").read_text()


def test_the_parser_reads_type_buyer_level_and_currency():
    d = EFormsParser().parse_to_tender_dict(SEK, "726269-2026")
    assert d["form_type"] == "competition" and d["notice_subtype"] == "cn-standard"
    assert d["buyer_legal_type"] == "la" and d["buyer_level"] == "local"
    assert d["estimated_value"] == 10_000_000 and d["estimated_value_currency"] == "SEK"


def test_a_notice_valued_only_on_its_lots_gets_their_sum():
    d = EFormsParser().parse_to_tender_dict(LOTS, "726130-2026")
    assert d["estimated_value"] == 927_189.67 + 585_600
    assert d["estimated_value_currency"] == "PLN"


def test_lots_are_summed_only_when_every_lot_has_a_value_in_one_currency():
    assert lots_total([{"estimated_value": 1.0, "currency": "SEK"}, {"estimated_value": 2.0, "currency": "SEK"}]) == (3.0, "SEK")
    assert lots_total([{"estimated_value": 1.0, "currency": "SEK"}, {"title": "no value"}]) is None
    assert lots_total([{"estimated_value": 1.0, "currency": "SEK"}, {"estimated_value": 2.0, "currency": "EUR"}]) is None
    assert lots_total([]) is None


def test_form_type_comes_from_the_sdk_and_levels_from_the_code_list():
    assert form_type_of("pin-only") == "planning" and form_type_of("pin-rtl") == "planning"
    assert form_type_of("pin-cfc-standard") == "competition"   # a PIN that calls for competition
    assert form_type_of("can-modif") == "cont-modif" and form_type_of("nonsense") is None
    assert [buyer_level(c) for c in ("la", "body-pl-ra", "pub-undert-cga", "eu-ins-bod-ag", "int-org")] == \
        ["local", "regional", "national", "eu", "international"]
    assert buyer_level("body-pl") is None and buyer_level(None) is None   # the code does not say


def test_the_daily_import_stores_them(monkeypatch):
    import fetch_tenders as ft
    f = ft.TenderFetcher.__new__(ft.TenderFetcher)
    f.parser = EFormsParser()
    monkeypatch.setattr(ft.TenderFetcher, "_calculate_sme_score", lambda self, t, p: {"sme_suitability_score": 0.5})
    notice = {"publication-number": "726269-2026", "PD": "2026-10-16+02:00", "CY": ["SWE"]}
    t = f._create_tender(notice, SEK)
    # Until 20 Oct the import read the parser's currency under the wrong key: "EUR".
    assert (t.estimated_value, t.estimated_value_currency) == (10_000_000, "SEK")
    assert (t.form_type, t.notice_subtype) == ("competition", "cn-standard")
    assert (t.buyer_legal_type, t.buyer_level) == ("la", "local")
    # The notice's own id (cbc:ID schemeName="notice-id"), not its first cbc:ID ("ORG-0001").
    assert t.notice_id == "5bcd089d-3060-4868-84f4-6d2cdef05576"


def test_the_api_serves_and_filters_them():
    import inspect
    from api.v1 import w5_endpoints as w5
    fields = w5.TenderItem.model_fields
    for name in ("notice_subtype", "buyer_legal_type", "buyer_level"):
        assert name in fields
    params = inspect.signature(w5.list_tenders).parameters
    for name in ("notice_subtype", "buyer_level", "buyer_legal_type", "currency"):
        assert name in params
