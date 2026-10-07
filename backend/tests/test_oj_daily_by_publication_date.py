"""/oj/daily lists the day's Official Journal by OJ publication date (7 Oct 2026).

It keyed on the DOCUMENT date and returned, for 7 Oct 2026, 6 L-series corrigenda and none
of the 4 Council decisions published that day; 4 titles were null, no body, no updated_date.
Cellar's publication date gives 10 L acts and 17 C notices. Acts with no English version
(corrigenda of one language version) are served in their own language, never invented.
"""
from fastapi.testclient import TestClient

import pytest

from api.v1._deps import api_user_with_rate_limit
from api.v2.legislative import eur_lex
from main import app
from models.user import User

W = "http://publications.europa.eu/resource/cellar/"
ENG = "http://publications.europa.eu/resource/authority/language/ENG"
HUN = "http://publications.europa.eu/resource/authority/language/HUN"


def _rows(series):
    if series == "L":
        return [
            {"work": W + "a", "celex": "32026D2251", "ref": "2026/2251", "num": "2251", "year": "2026",
             "docdate": "2026-10-01", "modified": "2026-10-07T09:00:18.326+02:00",
             "created": "2026-10-07T02:38:24.579+02:00", "lang": ENG, "title": "Council Decision (EU) 2026/2251",
             "manif": W + "a.0006.03", "fmt": "xhtml"},
            {"work": W + "a", "celex": "32026D2251", "num": "2251", "year": "2026", "lang": HUN,
             "title": "A Tanács (EU) 2026/2251 határozata", "manif": W + "a.0001.03", "fmt": "xhtml"},
            {"work": W + "b", "celex": "32008L0115R(05)", "ref": "2026/90851", "num": "90851", "year": "2026",
             "docdate": "2026-10-07", "modified": "2026-10-07T08:00:00+02:00", "lang": HUN,
             "title": "Helyesbítés a 2008/115/EK irányelvhez", "manif": W + "b.0001.03", "fmt": "xhtml"},
        ]
    return [{"work": W + "c", "ref": "C/2026/5167", "num": "5167", "year": "2026", "docdate": "2026-10-07",
             "modified": "2026-10-07T08:03:24+02:00", "lang": ENG, "title": "Authorisation for State aid",
             "manif": W + "c.0006.01", "fmt": "pdfa2a"}]


@pytest.fixture
def client(monkeypatch):
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient

    async def fake_rows(self, day, series):
        return _rows(series)

    async def fake_body(http, work, lang3, fmts):
        return f"<p>text of {work} in {lang3}</p>", f"text of {work} in {lang3}"

    monkeypatch.setattr(CellarSPARQLClient, "oj_acts_published_on", fake_rows)
    monkeypatch.setattr(eur_lex, "_oj_body", fake_body)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="t@example.com", role="admin")
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


def test_every_act_of_the_day_with_its_body_and_change_date(client):
    j = client.get("/api/v2/legislative/eur-lex/oj/daily?date=2026-10-07&series=L").json()
    assert j["total"] == 2 and j["coverage_complete"] is True
    assert j["op_core"]["dct:title"] == "Official Journal of the EU, series L, 2026-10-07"
    for item in j["data"]:
        assert item["title"] and item["body_txt"] and item["body_html"] and item["updated_date"]
        assert item["publication_date"] == "2026-10-07"


def test_an_act_without_english_is_served_in_its_own_language(client):
    data = client.get("/api/v2/legislative/eur-lex/oj/daily?date=2026-10-07&series=L").json()["data"]
    by_id = {d["id"]: d for d in data}
    assert by_id["L/2026/2251"]["language"] == "en"
    assert by_id["L/2026/2251"]["public_url"].endswith("/EN/TXT/?uri=CELEX:32026D2251")
    hu = by_id["L/2026/90851"]
    assert hu["language"] == "hu" and hu["title"].startswith("Helyesbítés")
    assert hu["public_url"] == "https://eur-lex.europa.eu/legal-content/HU/TXT/?uri=CELEX:32008L0115R(05)"


def test_a_notice_without_celex_links_its_oj_reference(client):
    item = client.get("/api/v2/legislative/eur-lex/oj/daily?date=2026-10-07&series=C").json()["data"][0]
    assert item["celex"] is None and item["id"] == "C/2026/5167"
    assert item["public_url"] == "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=OJ:C_202605167"


@pytest.mark.live
def test_live_cellar_returns_the_whole_official_journal_of_7_october():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="t@example.com", role="admin")
    try:
        c = TestClient(app)
        L = c.get("/api/v2/legislative/eur-lex/oj/daily?date=2026-10-07&series=L").json()
        C = c.get("/api/v2/legislative/eur-lex/oj/daily?date=2026-10-07&series=C&limit=100").json()
    finally:
        app.dependency_overrides.pop(api_user_with_rate_limit, None)
    assert (L["total"], C["total"]) == (10, 17)
    assert all(d["body_txt"] and d["title"] and d["updated_date"] for d in L["data"] + C["data"])


def test_bodies_are_a_clean_fragment_and_tidy_text():
    xhtml = ('<?xml version="1.0"?><!DOCTYPE html><html><!-- CONVEX --><head><link rel="stylesheet" '
             'href="oj-convex-act.css"/><title>L_2026.fmx.xml</title></head><body><table><tr><td>'
             '<img alt="European flag" src="europeanflag.gif"/></td></tr></table>'
             '<p>COUNCIL DECISION</p><p>   </p><p>Article 1</p></body></html>')
    frag = eur_lex._oj_fragment(xhtml)
    assert frag.startswith("<article>") and frag.endswith("</article>")
    for gone in ("<?xml", "DOCTYPE", "<head", "oj-convex-act.css", "europeanflag", "CONVEX"):
        assert gone not in frag
    assert "COUNCIL DECISION" in frag and "Article 1" in frag
    assert eur_lex._oj_clean_text("A \n\n \n\n \n B\n   C  ") == "A\n\nB\nC"
