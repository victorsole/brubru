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


def test_celex_shape_excludes_corrigenda_and_proposals():
    assert mod.CELEX_RE.match("32026R1744")
    assert not mod.CELEX_RE.match("32026R1744(01)")
    assert not mod.CELEX_RE.match("52025PC0836")
    assert not mod.CELEX_RE.match("32026H0001")


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
