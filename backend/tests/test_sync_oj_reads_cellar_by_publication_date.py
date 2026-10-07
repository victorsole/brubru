"""My OJ (oj_entries) is filled from Cellar by OJ publication date (7 Oct 2026).

sync_oj scraped EUR-Lex's English daily view and DERIVED the CELEX: for 7 Oct 2026 it
missed the 4 corrigenda with no English version and stored 3 L rows without a CELEX.
It now takes the CELEX from Cellar and stores one-language acts with their language,
which the Catalan pipelines (translating from English) skip.
"""
import importlib.util
import pathlib
import sys
from datetime import date

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
W = "http://publications.europa.eu/resource/cellar/"
LANG = "http://publications.europa.eu/resource/authority/language/"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _BACKEND / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_acts_carry_cellars_celex_and_their_language(monkeypatch):
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient
    rows = {
        "L": [
            {"work": W + "a", "celex": "32026D2255", "ref": "2026/2255", "num": "2255", "year": "2026",
             "lang": LANG + "ENG", "title": "Council Decision (EU) 2026/2255 amending the position", "fmt": "xhtml",
             "manif": W + "a.1"},
            {"work": W + "b", "celex": "32008L0115R(05)", "ref": "2026/90851", "num": "90851", "year": "2026",
             "lang": LANG + "HUN", "title": "Helyesbítés a 2008/115/EK irányelvhez", "fmt": "xhtml", "manif": W + "b.1"},
        ],
        "C": [{"work": W + "c", "ref": "C/2026/5167", "num": "5167", "year": "2026", "lang": LANG + "ENG",
               "title": "Authorisation for State aid", "fmt": "pdfa2a", "manif": W + "c.1"}],
    }

    async def fake(self, day, series):
        return rows[series]

    monkeypatch.setattr(CellarSPARQLClient, "oj_acts_published_on", fake)
    sync = _load("sync_oj")
    L = {a.oj_id: a for a in sync.acts_from_cellar(date(2026, 10, 7), "L")}
    dec, hu = L["L_202602255"], L["L_202690851"]
    assert dec.celex == "32026D2255" and dec.language == "en" and dec.oj_number == "2026/2255"
    assert hu.celex == "32008L0115R(05)" and hu.language == "hu"
    assert hu.act_type == "Directive" and hu.change_kind == "corrects"
    assert hu.url == "https://eur-lex.europa.eu/legal-content/HU/TXT/?uri=CELEX:32008L0115R(05)"
    (c,) = sync.acts_from_cellar(date(2026, 10, 7), "C")
    assert c.celex is None and c.oj_id == "C_202605167" and c.oj_number == "C/2026/5167"
    assert c.url.endswith("?uri=OJ:C_202605167")


def test_the_catalan_pipelines_translate_english_acts_only():
    for name in ("translate_oj_daily_acts", "translate_oj_c_series"):
        src = (_BACKEND / "scripts" / f"{name}.py").read_text()
        assert "e.language = 'en'" in src, name
    daily = (_BACKEND / "scripts" / "translate_oj_daily_acts.py").read_text()
    assert "ct.celex IN (e.celex, e.oj_id)" in daily  # an act translated under its OJ id stays done
