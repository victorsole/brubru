"""Pure-function tests for scripts/sync_eu_laws_from_cellar.py (no network, no DB)."""

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_eu_laws_from_cellar.py"
_spec = importlib.util.spec_from_file_location("sync_eu_laws_from_cellar", _PATH)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


@pytest.mark.parametrize("title,letter,expected", [
    ("Commission Implementing Regulation (EU) 2026/123 of 4 June 2026 on x", "R", "Commission Implementing Regulation"),
    ("Council Decision (CFSP) 2026/45 of 1 July 2026 concerning y", "D", "Council Decision (CFSP)"),
    ("Regulation (EU) 2026/1744 of the European Parliament and of the Council", "R", "Regulation"),
    ("Commission Decision (Euratom) 2026/1691 of 8 July 2026", "D", "Commission Decision"),
    ("Something without a number", "L", "Directive"),
])
def test_doc_type_from_title(title, letter, expected):
    assert mod.doc_type_from_title(title, letter) == expected


def test_oj_reference_format():
    assert mod.oj_reference("32026R1744", "2026-07-24") == "OJ L, 2026/1744, 24.7.2026"
    assert mod.oj_reference("32025D0007", "2025-11-03T00:00:00") == "OJ L, 2025/7, 3.11.2025"


def test_document_date_guards_cellar_errors():
    title = "Commission Implementing Regulation (EU) 2026/2053 of 10\xa0September 2026 granting"
    # Cellar held 2029-09-10: later than publication, so the title date wins
    assert mod.document_date("2029-09-10", "2026-09-14", title) == "2026-09-10"
    assert mod.document_date("2026-07-08", "2026-07-24", "x") == "2026-07-08"
    assert mod.document_date(None, "2026-07-24", "no date in title") == "2026-07-24"
    assert mod.document_date("2030-01-01", "2026-07-24", "no date in title") == "2026-07-24"


# 17 Oct 2026: every sector-3 legal act the corpus holds, not only 3YYYY[RLD]NNNN; 150 acts with an English text
# published since 1 Nov 2025 never arrived (budget acts, recommendations, corrigenda). Sector 2 stays out.
SHAPES = {"32026R1744": True, "32026R1744(01)": True, "32026D1106R(01)": True, "32005Q0520(01)R(01)": True,
          "32026H0311": True, "32026B0060": True, "32026Q00997": True, "32026C00268": True,
          "52025PC0836": False, "22026D1980": False, "22012A0727(01)R(01)": False, "C/2025/03118": False, "32026R": False}


@pytest.mark.parametrize("celex,ok", SHAPES.items())
def test_celex_shape_is_every_sector3_legal_act(celex, ok):
    assert bool(mod.CELEX_RE.match(celex)) is ok


@pytest.mark.parametrize("celex,ok", SHAPES.items())
def test_the_sparql_filter_says_the_same(celex, ok):
    import re
    # SPARQL unescapes "\\(" to "\(" inside its string literal before the regex sees it
    assert bool(re.search(mod.SPARQL_CELEX.replace("\\\\", "\\"), celex)) is ok


@pytest.mark.parametrize("celex,title,expected", [
    ("32026R1753R(01)", "Corrigendum to Commission Delegated Regulation (EU) 2026/1753 of 13 July 2026", "Regulation"),
    ("32017L2397R(03)", "Corrigendum to Directive (EU) 2017/2397", "Directive"),
    ("32015O0027R(01)", "Corrigendum to Guideline (EU) 2015/27 of the European Central Bank", "Corrigendum"),
    ("32026H0311", "Commission Recommendation (EU) 2026/311 of 29 January 2026", "Recommendation"),
    ("32026B0060", "Decision (EU) 2026/60 of the European Parliament of 22 October 2025 on discharge", "Decision"),
    ("32025B2238", "Definitive adoption (EU, Euratom) 2025/2238 of Amending budget No 2", "Other"),
    ("32026C00268", "Statement from the European Commission on future action regarding Russian oil", "Other"),
])
def test_normalized_type_spells_each_kind_as_the_corpus_does(celex, title, expected):
    assert mod.normalized_type(celex, title) == expected


def test_a_title_without_a_number_still_gets_a_type():
    assert mod.doc_type_from_title("Statement from the European Commission", "C", "32026C00268") == "Other"
    assert mod.doc_type_from_title("Something", "H", "32026H0311") == "Recommendation"


def test_a_corrigendum_takes_its_own_official_journal_number():
    assert mod.oj_reference("32026D1106R(01)", "2026-10-13", "90858", "2026") == "OJ L, 2026/90858, 13.10.2026"
    assert mod.oj_reference("32026R1744", "2026-07-24", "1744", "2026") == "OJ L, 2026/1744, 24.7.2026"


ROW = {"celex": "32026H0311", "work": "w", "pub": "2026-02-10", "ojn": "311", "ojy": "2026", "docdate": "2026-01-29",
       "title": "Commission Recommendation (EU) 2026/311 of 29 January 2026 on attracting talent for innovation",
       "eea": "0", "dg": "http://publications.europa.eu/resource/authority/corporate-body/RTD"}
FACTS = {"authors": ["COM", "RTD"], "in_force": None, "eli": "http://data.europa.eu/eli/reco/2026/311/oj",
         "entry_into_force": None, "application_dates": None, "effect_dates": None, "procedures": ["2025/0001"], "seen": True}


def test_a_new_row_carries_the_metadata_columns_and_no_side_copies():
    import json
    row = mod.build_row(ROW, {}, lambda t, l: None, FACTS, {"2025/0002"})
    assert (row["authors"], row["eli"], row["in_force"]) == (["COM", "RTD"], FACTS["eli"], None)
    assert row["procedures"] == ["2025/0001", "2025/0002"]  # Cellar and OEIL, together
    assert row["doc_type_normalized"] == "Recommendation" and row["oj"] == "OJ L, 2026/311, 10.2.2026"
    assert not {"in_force", "eli", "entry_into_force"} & set(json.loads(row["meta"]))
    bare = mod.build_row(ROW, {}, lambda t, l: None)  # Cellar's metadata unavailable: unknown, never false
    assert all(bare[c] is None for c in mod.META_COLS)


def test_the_insert_writes_every_metadata_column():
    sql = str(mod.INSERT_SQL)
    assert all(f":{c}" in sql for c in mod.META_COLS) and "in_force" in sql.split("SELECT")[0]


def test_the_catch_up_fills_empty_columns_only_and_never_in_force():
    rows = [{"id": 1, "celex": "32026H0311", "authors": None, "eli": "kept", "entry_into_force": None,
             "application_dates": None, "effect_dates": None, "procedures": None},
            {"id": 2, "celex": "32026B0060", "authors": ["EP"], "eli": "x", "entry_into_force": None,
             "application_dates": None, "effect_dates": None, "procedures": None}]
    fills = mod.catch_up_fills(rows, {"32026H0311": FACTS, "32026B0060": {"authors": ["EP"], "eli": "y"}}, {})
    assert fills == [(1, {"authors": ["COM", "RTD"], "eli": None, "entry_into_force": None, "application_dates": None,
                          "effect_dates": None, "procedures": ["2025/0001"]})]
    assert "in_force" not in mod.FILL_COLS and "in_force" not in mod.FILL_SQL
    assert all(f"{c} = coalesce(e.{c}, v.{c})" in mod.FILL_SQL for c in mod.FILL_COLS)


def test_the_catch_up_rereads_any_empty_field_for_a_week_and_authors_or_eli_for_a_month():
    """The docs promise that a field published later is filled (audit of 17 Oct 2026: only authors/ELI were re-read)."""
    sql = str(mod.CATCH_UP_SQL)
    month, week = sql.split(" OR (created_at")
    assert ":days" in month and "authors IS NULL OR eli IS NULL" in month
    assert ":any_days" in week and all(f"{c} IS NULL" in week for c in mod.FILL_COLS)
    assert mod.CATCH_UP_ANY_DAYS < mod.CATCH_UP_DAYS


def test_an_act_cellar_did_not_answer_for_makes_the_run_degraded():
    todo = [{"celex": "32026R0001"}, {"celex": "32026H0002"}]
    assert mod.unread_gap(todo, {"32026R0001": FACTS, "32026H0002": FACTS}) is None
    gap = mod.unread_gap(todo, {"32026R0001": FACTS})
    assert gap.startswith("Cellar gave no metadata for 1 of 2 acts inserted (32026H0002)")
    assert mod.unread_gap([], {}) is None


class _FakeDB:
    def __init__(self, areas):
        self.areas = areas

    def execute(self, _stmt, params):
        return [(c, self.areas[c]) for c in params["c"] if c in self.areas]


KEYWORDS = {
    "Climate Action": [("ets", 3.0), ("emission", 3.0)],
    "Economic and Financial Affairs": [("euro", 3.0), ("markets", 1.0)],
}


def test_classifier_inherits_from_amended_act():
    rel = {"w": {"amends": ["32016R0679"], "based_on": []}}
    classify = mod.make_classifier(_FakeDB({"32016R0679": "Digital Policy and Digital Economy"}), rel, KEYWORDS)
    assert classify("Commission Implementing Regulation on emissions", ["32016R0679"]) == "Digital Policy and Digital Economy"


def test_classifier_matches_whole_words_only():
    classify = mod.make_classifier(_FakeDB({}), {}, KEYWORDS)
    # substring matching would fire "ets" inside "markets" and "euro" inside "European"
    assert classify("Decision of the European Parliament on markets", []) is None
    assert classify("Amending the EU ETS and emission rules", []) == "Climate Action"
