"""Check B of the law-drop radar: a shipped deck must count as marked.

Regression for 15 Sep 2026: `cra_article14_deck.html` existed but the Cyber
Resilience Act was reported NOTHING SHIPPED, because the filename carries
neither the act number nor a cluster-name word. The Data Act, which has no
deck, must stay unmarked.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("sqlalchemy")
from scripts import lawdrop_radar as radar  # noqa: E402


@pytest.fixture
def fake_dirs(tmp_path, monkeypatch):
    decks = tmp_path / "designs"
    canon = tmp_path / "eucanon"
    decks.mkdir()
    canon.mkdir()
    for fn in ("cra_article14_deck.html", "cra_article14_deck.pdf",
               "crash_course_deck.html", "public_procurement_act_deck.html"):
        (decks / fn).write_text("x")
    for d in ("2025-40_ppwr", "2026-405_detergents"):
        (canon / d).mkdir()
    monkeypatch.setattr(radar, "DECK_DIR", str(decks))
    monkeypatch.setattr(radar, "CANON_DIR", str(canon))
    monkeypatch.setattr(radar, "_short_names_cache", {
        "32024R2847": ["Cyber Resilience Act", "CRA"],
        "32023R2854": ["Data Act"],
    })
    return tmp_path


def test_cra_deck_found_by_acronym(fake_dirs):
    m = radar._marked("32024R2847", "SaaS & B2B Startup Compliance")
    assert m["decks"] == ["cra_article14_deck.html", "cra_article14_deck.pdf"]


def test_data_act_without_deck_stays_unmarked(fake_dirs):
    m = radar._marked("32023R2854", "SaaS & B2B Startup Compliance")
    assert m == {"decks": [], "canon": []}


def test_act_number_is_whole_token(fake_dirs):
    m = radar._marked("32025R0040", "Packaging")
    assert m["canon"] == ["2025-40_ppwr"]


def test_name_in_filename_boundaries():
    ft = radar._name_tokens("data_act_deck.html")
    assert radar._name_in_filename("Data Act", ft)
    assert radar._name_in_filename("Data Act", radar._name_tokens("dataact_deck.pdf"))
    assert not radar._name_in_filename("Data Act", radar._name_tokens("data_deck.pdf"))
    assert not radar._name_in_filename("CRA", radar._name_tokens("crash_deck.html"))
    assert not radar._name_in_filename("AI", radar._name_tokens("ai_deck.html"))


def test_real_acronym_file_maps_cra_and_data_act(monkeypatch):
    monkeypatch.setattr(radar, "_short_names_cache", None)
    assert "CRA" in radar._short_names("32024R2847")
    assert "Data Act" in radar._short_names("32023R2854")
