"""Defined terms come from the law as it stands, and say which text they came from.

The defect (15 Sep 2026): the endpoint parsed each act's ORIGINAL text and cached it for
ever, so the AI Act served 65 definitions and no "SME" or "small mid-cap enterprise",
although Regulation (EU) 2026/1744 added both (consolidated 02024R1689-20260727). Its
description said definitions "don't change after adoption". The extractor also missed
real definitions in the original shape: GDPR Art 4 gave 23 of 26.
"""
from types import SimpleNamespace

import pytest

from services.parsers import definition_store as store
from services.parsers.consolidated_xhtml import parse_consolidated_law
from services.parsers.definition_extractor import extract_definitions_map

AI_ACT_ART3 = """<div class="eli-subdivision" id="art_3">
 <p class="title-article-norm">Article 3</p>
 <div class="eli-title" id="art_3.tit_1"><p class="stitle-article-norm">Definitions</p></div>
 <p class="norm">For the purposes of this Regulation, the following definitions apply:</p>
 <div class="grid-list"><span>(14) </span><p>&#8216;safety component&#8217; means a component of a product or of an AI system which fulfils a safety function;</p></div>
 <p class="modref"><a>&#9660;M1</a></p>
 <div class="grid-list"><span>(14a) </span><p>&#8216;micro, small and medium-sized enterprise&#8217; or &#8216;SME&#8217; means a micro, small or medium-sized enterprise as defined in Article 2 of the Annex to Recommendation 2003/361/EC;</p></div>
 <div class="grid-list"><span>(14b) </span><p>&#8216;small mid-cap enterprise&#8217; or &#8216;SMC&#8217; means a small mid-cap enterprise as defined in point (2) of the Annex to Recommendation (EU) 2025/1099;</p></div>
 <div class="grid-list"><span>(58) </span><p>&#8216;subject&#8217;, for the purpose of real-world testing, means a natural person who participates in testing in real-world conditions;</p></div>
</div>"""

GDPR_ART4 = """<div class="eli-subdivision" id="art_4">
 <p class="title-article-norm">Article 4</p><div class="eli-title"><p class="stitle-article-norm">Definitions</p></div>
 <div><span>(11) </span><p>&#8216;consent&#8217; of the data subject means any freely given, specific, informed and unambiguous indication of the data subject's wishes;</p></div>
 <div><span>(16) </span><p>&#8216;main establishment&#8217; means:</p><div><span>(a)</span><p>as regards a controller, the place of its central administration in the Union;</p></div><div><span>(b)</span><p>as regards a processor, the place of its central administration in the Union;</p></div></div>
 <div><span>(26) </span><p>&#8216;international organisation&#8217; means an organisation and its subordinate bodies governed by public international law.</p></div>
</div>"""


def test_a_long_form_and_its_abbreviation_are_both_defined_with_their_point():
    terms = extract_definitions_map(parse_consolidated_law(AI_ACT_ART3))
    assert terms["sme"]["point"] == terms["micro, small and medium-sized enterprise"]["point"] == "14a"
    assert terms["smc"]["point"] == terms["small mid-cap enterprise"]["point"] == "14b"
    assert terms["subject"]["definition"].startswith("a natural person who participates")
    assert "▼" not in terms["safety component"]["definition"]


def test_qualified_listed_and_final_points_are_read_whole():
    terms = extract_definitions_map(parse_consolidated_law(GDPR_ART4))
    assert set(terms) == {"consent", "main establishment", "international organisation"}
    assert "(b) as regards a processor" in terms["main establishment"]["definition"]
    assert terms["international organisation"]["definition"].endswith("public international law")


@pytest.fixture
def no_db_writes(monkeypatch):
    monkeypatch.setattr(store, "_read_consolidated", lambda db, c, cc: None)
    monkeypatch.setattr(store, "_write_consolidated", lambda *a, **k: None)
    monkeypatch.setattr(store, "get_or_compute_map", lambda db, c, force_recompute=False: {"risk": {"term": "risk"}})

    class _DB:
        def execute(self, *a, **k):
            return SimpleNamespace(first=lambda: None)
    return _DB()


def test_latest_reads_the_newest_consolidation_and_names_it(monkeypatch, no_db_writes):
    monkeypatch.setattr(store, "latest_consolidated_version",
                        lambda c: {"consolidatedCelex": "02024R1689-20260727", "date": "2026-07-27"})
    monkeypatch.setattr(store, "fetch_consolidated_xhtml", lambda cc: AI_ACT_ART3)
    r = store.get_defined_terms(no_db_writes, "32024R1689")
    assert (r["version_used"], r["source_celex"], r["version_date"], r["fallback_reason"]) == (
        "latest", "02024R1689-20260727", "2026-07-27", None)
    assert "sme" in r["terms"]


@pytest.mark.parametrize("latest,xhtml,reason", [
    (None, None, "no_consolidated_version"),
    ({"consolidatedCelex": "02022R2065-20221027", "date": "2022-10-27"}, None, "consolidated_text_unavailable"),
])
def test_latest_falls_back_to_the_original_and_says_why(monkeypatch, no_db_writes, latest, xhtml, reason):
    monkeypatch.setattr(store, "latest_consolidated_version", lambda c: latest)
    monkeypatch.setattr(store, "fetch_consolidated_xhtml", lambda cc: xhtml)
    r = store.get_defined_terms(no_db_writes, "32022R2065")
    assert (r["version_used"], r["source_celex"], r["fallback_reason"]) == ("original", "32022R2065", reason)


def test_original_never_looks_up_a_consolidation(monkeypatch, no_db_writes):
    def _boom(c):
        raise AssertionError("original must not query Cellar")
    monkeypatch.setattr(store, "latest_consolidated_version", _boom)
    r = store.get_defined_terms(no_db_writes, "32024R1689", version="original")
    assert (r["version_requested"], r["version_used"]) == ("original", "original")


def test_the_description_no_longer_claims_definitions_never_change():
    from main import app
    for path in ("/api/v1/legal-text/{celex}/defined-terms", "/api/v2/legislative/eur-lex/laws/{celex}/defined-terms"):
        op = app.openapi()["paths"][path]["get"]
        assert "don't change after adoption" not in op["description"]
        assert any(p["name"] == "version" for p in op["parameters"])
