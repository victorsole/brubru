"""Brubru DPP connector: TRIS and JRC Product Bureau tools (23 Sep 2026).

Reads the database (read-only). Joana Castella's connector could not see TRIS
or the Product Bureau; both were promised to her in writing.
"""
from __future__ import annotations

import datetime as dt

from services.mcp.dpp_tools import (
    DPP_TOOLS, handle_ask_dpp, handle_dpp_jrc, handle_dpp_tris,
)

EXPECTED = {"ask_dpp", "dpp_law", "dpp_when", "dpp_data_points", "dpp_standards",
            "dpp_registry", "dpp_updates", "dpp_consultations", "dpp_forum",
            "dpp_tris", "dpp_jrc", "search", "fetch"}


def test_tool_surface_by_name():
    assert {t.name for t in DPP_TOOLS} == EXPECTED


def test_instructions_name_the_new_sources():
    from api.mcp_http import _dpp_instructions
    txt = _dpp_instructions("")
    assert "TRIS" in txt and "Product Bureau" in txt and f"{len(DPP_TOOLS)} tools" in txt


def test_tris_rows_are_in_domain_and_open_first():
    import re
    from sqlalchemy import text
    from core.database import SessionLocal
    from services.mcp.dpp_tools import _TRIS_DPP_RX
    out = handle_dpp_tris(limit=50)
    rows = out["notifications"]
    assert out["feed"]["total"] > 0
    opens = [r["standstill_open"] for r in rows]
    assert opens == sorted(opens, key=lambda x: (x is not True))       # open ones first
    db = SessionLocal()
    try:
        for r in rows:   # judged on the FULL stored text, the same text SQL matched
            full = " ".join(x or "" for x in db.execute(text(
                "SELECT title, products_or_services, main_content, full_text_summary "
                "FROM tris_notifications WHERE notification_number = :n"),
                {"n": r["reference"]}).one())
            assert re.search(_TRIS_DPP_RX, full, re.I), r["reference"]
    finally:
        db.close()


def test_animal_traceability_is_not_in_domain():
    import re
    from services.mcp.dpp_tools import _TRIS_DPP_RX
    assert not re.search(_TRIS_DPP_RX, "welfare of dogs and cats and their traceability", re.I)
    assert re.search(_TRIS_DPP_RX, "product traceability in the textile supply chain", re.I)


def test_open_only_really_filters():
    for r in handle_dpp_tris(open_only=True, limit=50)["notifications"]:
        assert r["standstill_until"] >= dt.date.today()


def test_country_filter():
    for r in handle_dpp_tris(country="es", limit=50)["notifications"]:
        assert r["country"] == "ES"


def test_jrc_groups_and_per_kind_limit():
    res = handle_dpp_jrc(limit=5)["results"]
    assert set(res) == {"workshops", "reports", "textiles"}
    assert all(len(v) <= 5 for v in res.values())
    ws = [r["document_date"] for r in res["workshops"]]
    assert ws == sorted(ws)                                              # soonest workshop first


def test_jrc_finds_the_dpp_method_and_textile_study():
    rep = handle_dpp_jrc(kind="reports", query="Digital Product Passport")["results"]["reports"]
    assert any("Digital Product Passport" in r["title"] for r in rep)
    tex = handle_dpp_jrc(kind="textiles", query="DPP content")["results"]["textiles"]
    assert tex and "textile apparel" in tex[0]["title"]


def test_ask_dpp_carries_tris_and_answers_catalan_jrc_question():
    out = handle_ask_dpp("Quan és el taller del JRC sobre el passaport digital?")
    assert out["found"] and "national_draft_rules_tris" in out
    assert any("JRC" in r["title"] for r in out["matches"].get("event", []))


def test_updates_list_upcoming_events_soonest_first():
    from services.mcp.dpp_tools import handle_dpp_updates
    ev = handle_dpp_updates(10)["events"]
    up = [e["document_date"] for e in ev if e["upcoming"]]
    assert up == sorted(up)
    flags = [e["upcoming"] for e in ev]
    assert flags == sorted(flags, reverse=True)       # all upcoming before any past


def test_tris_query_maps_six_languages_and_countries():
    from services.mcp.dpp_tools import _tris_query
    assert _tris_query("Reial Decret espanyol de productes tèxtils i calçat") == (["textile", "footwear", "decree"], "ES")
    assert _tris_query("décret français sur les emballages") == (["packaging", "decree"], "FR")
    assert _tris_query("imballaggi e rifiuti in Italia")[1] == "IT"


def test_tris_query_substring_traps():
    from services.mcp.dpp_tools import _tris_query
    # "representative", "rapporteur", "franchise" must not add terms or a country
    assert _tris_query("the rapporteur's representative on franchise rules") == ([], None)


def test_catalan_question_finds_the_spanish_textile_decree():
    out = handle_ask_dpp("Quin és l'estat del Reial Decret espanyol de productes tèxtils i calçat?")
    assert out["national_draft_rules_tris"][0]["reference"] == "2026/0266/ES"
