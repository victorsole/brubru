"""A name on the alias list must lead to a law (register O209, 5 Nov 2026).

REACH had no row, so the common name found nothing. Three more names led nowhere or somewhere false: SIS II pointed at a 1987
regulation on aid for peas, and TDI and PACT Act at CELEX numbers that do not exist. Each was opened at Cellar on 5 Nov 2026.
The list is a target list: anything on it becomes a link Brubru states as fact.
"""
import importlib.util
import json
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[1]
LISTS = BACKEND / "knowledge_base/institutions"


def _load_sync():
    spec = importlib.util.spec_from_file_location("sync_eu_laws_from_cellar", BACKEND / "scripts/sync_eu_laws_from_cellar.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _names():
    names = {}
    for f in ("legislation_acronyms.json", "legislation_acronyms_manual.json"):
        names.update(json.loads((LISTS / f).read_text())["acronyms"])
    return names


def test_the_list_no_longer_states_what_cellar_refuted():
    names = _names()
    assert names["SIS II"]["celex"] == "32006R1987"
    assert "TDI" not in names and "PACT Act" not in names
    assert not [n for n, v in names.items() if isinstance(v, dict) and v.get("celex") in ("31987R2006", "32024L0900", "32024R1828")]


def test_a_named_act_with_no_oj_date_builds_a_row_without_a_reference():
    sync = _load_sync()
    r = {"celex": "32006R1907", "work": "http://example.invalid/w", "title": "Regulation (EC) No 1907/2006 of the European Parliament and of the Council of 18 December 2006 concerning REACH", "docdate": "2006-12-18"}
    row = sync.build_row(r, {}, lambda title, related: "chemicals")
    assert row["oj"] is None
    assert row["date"] == "2006-12-18"
    assert row["year"] == 2006 and row["letter"] == "R" and row["number"] == 1907
    assert json.loads(row["meta"])["ingested_by"] == "sync_eu_laws_from_cellar"


def test_a_dated_act_still_gets_its_reference():
    sync = _load_sync()
    r = {"celex": "32025R0040", "work": "http://example.invalid/w", "title": "Regulation (EU) 2025/40 of the European Parliament and of the Council of 19 December 2024 on packaging", "docdate": "2024-12-19", "pub": "2025-01-22"}
    row = sync.build_row(r, {}, lambda title, related: None)
    assert row["oj"] == "OJ L, 2025/40, 22.1.2025"


def test_discover_celex_keeps_the_row_with_a_title_and_says_when_cellar_knows_nothing(monkeypatch):
    sync = _load_sync()
    warned = []
    monkeypatch.setattr(sync.log, "warning", warned.append)
    answers = {"32006R1907": [{"work": "w1"}, {"work": "w1", "title": "REACH"}], "32024L0900": []}
    monkeypatch.setattr(sync, "_sparql", lambda q: answers["32006R1907" if "32006R1907" in q else "32024L0900"])
    found = sync.discover_celex(["32006R1907", "32024L0900"])
    assert [(r["celex"], r.get("title")) for r in found] == [("32006R1907", "REACH")]
    assert any("32024L0900" in m for m in warned)
