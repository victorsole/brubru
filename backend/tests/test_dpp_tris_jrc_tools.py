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
    out = handle_dpp_tris(limit=50)
    rows = out["notifications"]
    assert out["feed"]["total"] > 0
    opens = [r["standstill_open"] for r in rows]
    assert opens == sorted(opens, key=lambda x: (x is not True))       # open ones first
    for r in rows:
        blob = " ".join(str(r.get(k) or "") for k in ("title", "main_content", "products")).lower()
        assert any(w in blob for w in ("textil", "footwear", "packag", "waste", "recycl", "ecodesign",
                                       "passport", "traceab", "producer", "unsold", "batter",
                                       "circular", "repair", "durab", "apparel", "garment", "clothing"))


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
