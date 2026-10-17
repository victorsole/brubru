"""eu_laws.oj_reference: one citation form (services/oj_citation.py), written from Cellar by
scripts/fill_eu_laws_oj_reference.py, and found by the v2 /eur-lex/oj lookup.

17 Oct 2026: the column held five shapes from three writers; /eur-lex/oj/L/2025/40 (PPWR) and
/oj/L/2023/2854 (the Data Act) returned nothing, /oj/L/2025/2025 returned 1,252 unrelated acts.
No network, no DB.
"""
import ast
import importlib.util
import re
from datetime import date
from pathlib import Path

import pytest

from services.oj_citation import (OFFICIAL, OFFICIAL_SQL, act_citation, export_issue_parts, issue_citation,
                                  parse_oj_id)

BACKEND = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fill_eu_laws_oj_reference",
                                               BACKEND / "scripts" / "fill_eu_laws_oj_reference.py")
fill = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fill)


# --- the form, as the acts' own texts print it -------------------------------------------------

def test_act_by_act_citation():
    assert act_citation("L", 2025, 40, date(2025, 1, 22)) == "OJ L, 2025/40, 22.1.2025"         # PPWR
    assert act_citation("C", "2026", "02634", date(2026, 5, 5)) == "OJ C, 2026/2634, 5.5.2026"


def test_issue_citation():
    assert issue_citation("L", 119, date(2016, 5, 4), "0001") == "OJ L 119, 4.5.2016, p. 1"      # GDPR
    assert issue_citation("L", "056", date(1968, 3, 4), 8) == "OJ L 56, 4.3.1968, p. 8"
    assert issue_citation("L", 445, date(2021, 12, 13), 1, "I") == "OJ L 445 I, 13.12.2021, p. 1"
    assert issue_citation("", 56, date(1964, 4, 4), 850) == "OJ 56, 4.4.1964, p. 850"            # before 1968
    assert issue_citation("C", 52, date(2021, 2, 15)) == "OJ C 52, 15.2.2021"                    # no page known


def test_parse_oj_id():
    assert parse_oj_id("oj:JOL_2016_119_R") == ("L", 2016, 119, "")
    assert parse_oj_id("oj:JOL_2022_322_I") == ("L", 2022, 322, "I")
    assert parse_oj_id("oj:JOC_2021_052_I") == ("C", 2021, 52, "I")
    assert parse_oj_id("oj:JOP_1962_013_R") == ("", 1962, 13, "")
    assert parse_oj_id("oj:JOX_2016_119_R") is None
    assert parse_oj_id("") is None


def test_export_issue_parts():
    assert export_issue_parts("L 119/1") == ("L", 119, "", 1)
    assert export_issue_parts("L 322I/614") == ("L", 322, "I", 614)
    assert export_issue_parts("P 065/1173") == ("", 65, "", 1173)
    assert export_issue_parts("L 2025/40, p. 1") is None
    assert export_issue_parts(None) is None


WRITTEN = ["OJ L, 2025/40, 22.1.2025", "OJ C, 2026/2634, 5.5.2026", "OJ L 119, 4.5.2016, p. 1",
           "OJ L 445 I, 13.12.2021, p. 1", "OJ 56, 4.4.1964, p. 850", "OJ C 52, 15.2.2021"]
OLD = ["L 119/1", "L 2025/40, p. 1", "P 065/1173", "L 322I/614", "OJ L 130/52, 16.5.2023",
       "OJ R 272, 2011-10-18", "OJ L, 2026/1778, 2026", ""]


@pytest.mark.parametrize("ref", WRITTEN)
def test_the_official_test_accepts_what_is_written(ref):
    assert OFFICIAL.match(ref) and re.match(OFFICIAL_SQL, ref)


@pytest.mark.parametrize("ref", OLD)
def test_the_official_test_rejects_the_old_shapes(ref):
    # the daily fill re-reads exactly these, so a shape it accepts by mistake is never corrected
    assert not OFFICIAL.match(ref) and not re.match(OFFICIAL_SQL, ref)


# --- reading Cellar --------------------------------------------------------------------------

def _b(**kw):
    return {k: {"value": v} for k, v in kw.items()}


LANG = "http://publications.europa.eu/resource/authority/language/"
COLL = "http://publications.europa.eu/resource/authority/document-collection/"
GDPR = [_b(c="32016R0679", k="issue", id="oj:JOL_2016_119_R", pub="2016-05-04"),
        _b(c="32016R0679", k="page", pg="0001", lang=LANG + "ENG"),
        _b(c="32016R0679", k="page", pg="0001", lang=LANG + "FRA")]
PPWR = [_b(c="32025R0040", k="act", coll=COLL + "OJ-L", num="40", yr="2025-01-01", pub="2025-01-22")]


def test_cellar_rows_become_the_controls_citations():
    got = fill.parse(GDPR + PPWR)
    for celex, want in fill.CONTROLS.items():
        assert fill.citation(got[celex], None)[0] == want


def test_a_law_cellar_does_not_know_keeps_its_value():
    assert fill.citation(None, "L 119/1") == (None, "not at Cellar")
    got = fill.parse([_b(c="32016R0679", k="page", pg="1", lang=LANG + "ENG")])
    assert fill.citation(got["32016R0679"], "L 119/1")[0] is None


def test_the_maltese_special_edition_is_not_the_original():
    got = fill.parse([_b(c="32004D0927", k="issue", id="oj:JOL_2006_153_M", pub="2006-06-07"),
                      _b(c="32004D0927", k="issue", id="oj:JOL_2004_396_R", pub="2004-12-31"),
                      _b(c="32004D0927", k="page", pg="0045", lang=LANG + "ENG")])
    assert fill.citation(got["32004D0927"], "L 396/45")[0] == "OJ L 396, 31.12.2004, p. 45"


def test_two_issues_on_the_same_day_are_not_guessed():
    got = fill.parse([_b(c="3X", k="issue", id="oj:JOL_2004_396_R", pub="2004-12-31"),
                      _b(c="3X", k="issue", id="oj:JOL_2004_397_R", pub="2004-12-31")])
    assert fill.citation(got["3X"], None)[0] is None


def test_the_page_is_the_english_editions():
    rows = [_b(c="31972R2840", k="issue", id="oj:JOL_1972_300_R", pub="1972-12-31"),
            _b(c="31972R2840", k="page", pg="0188", lang=LANG + "FRA")]
    got = fill.parse(rows)["31972R2840"]
    # the English text prints L 300/190; the French and German editions start at p. 188
    assert fill.citation(got, "L 300/190")[0] == "OJ L 300, 31.12.1972, p. 190"
    assert fill.citation(got, None) == ("OJ L 300, 31.12.1972, p. 188", "issue, page from FRA")
    bare = fill.parse(rows[:1])["31972R2840"]
    assert fill.citation(bare, None) == ("OJ L 300, 31.12.1972", "issue, no page known")


def test_a_page_disagreement_is_settled_by_the_acts_own_text():
    rows = [_b(c="31995D0308", k="issue", id="oj:JOL_1995_186_R", pub="1995-08-05"),
            _b(c="31995D0308", k="page", pg="0044", lang=LANG + "ENG")]
    got = fill.parse(rows)["31995D0308"]
    assert fill.citation(got, "L 186/42") == (None, fill.NEEDS_TEXT)
    head = "5.8.1995 EN Official Journal of the European Communities L 186/42 COUNCIL DECISION of 24 July 1995"
    assert fill.citation(got, "L 186/42", head)[0] == "OJ L 186, 5.8.1995, p. 42"
    assert fill.citation(got, "L 186/42", "")[0] is None                       # no text: left, never guessed
    other = "Official Journal of the European Communities L 187/42"            # a header naming another issue
    assert fill.citation(got, "L 186/42", other)[0] is None
    assert fill.citation(got, "L 186/44")[0] == "OJ L 186, 5.8.1995, p. 44"    # agreeing sources need no text


def test_a_stored_issue_that_is_not_cellars_is_left():
    # 32014R1322 holds a corrigendum's file (L 127/44): its citation is not rewritten under another act's fields
    got = fill.parse(GDPR)["32016R0679"]
    assert fill.citation(got, "L 118/1")[0] is None
    assert fill.citation(got, "L 119/1")[0] == "OJ L 119, 4.5.2016, p. 1"


# --- the lookup route finds what is written, and only that -------------------------------------

def _found(series, year, number, ref):
    from api.v2.legislative.eur_lex import oj_reference_patterns
    act, dated, issue = oj_reference_patterns(series, year, number)
    return any(re.search(p, ref) for p in (act, dated)) or bool(re.search(issue, ref))


@pytest.mark.parametrize("args,ref", [
    (("L", 2025, "40"), "OJ L, 2025/40, 22.1.2025"),
    (("L", 2025, "40"), "L 2025/40, p. 1"),                  # a row the fill could not resolve
    (("L", 2023, "2854"), "L 2023/2854, p. 1"),              # the Data Act, missed 13-17 Oct 2026
    (("L", 2016, "119"), "OJ L 119, 4.5.2016, p. 1"),
    (("L", 2021, "445I"), "OJ L 445 I, 13.12.2021, p. 1"),
    (("L", 2022, "322I"), "L 322I/614"),
    (("P", 1964, "56"), "OJ 56, 4.4.1964, p. 850"),
    (("C", 2026, "2634"), "OJ C, 2026/2634, 5.5.2026"),
])
def test_the_lookup_finds_each_form(args, ref):
    assert _found(*args, ref)


@pytest.mark.parametrize("args,ref", [
    (("L", 2025, "2025"), "L 2025/40, p. 1"),                # was read as issue 2025: 1,252 wrong acts
    (("L", 2025, "2025"), "OJ L, 2025/40, 22.1.2025"),
    (("L", 2016, "11"), "OJ L 119, 4.5.2016, p. 1"),
    (("L", 2021, "445"), "OJ L 445 I, 13.12.2021, p. 1"),    # L 445 is not L 445 I
    (("L", 1964, "56"), "OJ 56, 4.4.1964, p. 850"),          # the P series has no L
    (("L", 2017, "119"), "OJ L 119, 4.5.2016, p. 1"),
])
def test_the_lookup_does_not_find_another_act(args, ref):
    assert not _found(*args, ref)


# --- one writer: the importers and the one-shot repair leave the column to the fill ----------

def _calls_with_keyword(path, func, kw):
    tree = ast.parse(path.read_text())
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == func
            and any(k.arg == kw for k in n.keywords)]


def test_the_importers_do_not_write_oj_reference():
    upd = (BACKEND / "scripts" / "import_corpus_update.py").read_text()
    body = upd[upd.index("def parsed_fields"):upd.index("def process_corpus")]
    assert '"oj_reference"' not in body
    assert not _calls_with_keyword(BACKEND / "scripts" / "import_leg_archive.py", "EULaw", "oj_reference")
    rep = (BACKEND / "scripts" / "repair_eu_laws_wrong_file.py").read_text()
    writes = re.search(r"\nWRITES = \((.*?)\)\n", rep, re.S).group(1)
    assert "oj_reference" not in writes and "oj_reference =" not in rep


def test_the_daily_sync_writes_the_same_form():
    spec = importlib.util.spec_from_file_location("sync_eu_laws_from_cellar",
                                                  BACKEND / "scripts" / "sync_eu_laws_from_cellar.py")
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    ref = sync.oj_reference("32025R0040", "2025-01-22T00:00:00", "40", "2025-01-01")
    assert ref == "OJ L, 2025/40, 22.1.2025" and OFFICIAL.match(ref)


def test_the_fill_runs_nightly_and_keeps_updated_at():
    cron = (BACKEND / "api" / "cron.py").read_text()
    assert '"eu_laws_oj_reference", "scripts/fill_eu_laws_oj_reference.py", ["--apply"]' in cron
    src = (BACKEND / "scripts" / "fill_eu_laws_oj_reference.py").read_text()
    assert "brubru.keep_change_signal" in src and "IS NOT DISTINCT FROM v.old" in src


def test_a_cached_xref_serves_the_laws_own_citation(monkeypatch):
    """/laws/{celex}/xref serves law_xref rows for ever: GDPR's cache said "L 119/1" after the rewrite."""
    from fastapi.testclient import TestClient
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db
    from main import app
    from models.user import User

    class Q:
        def filter(self, *a): return self
        def first(self): return ("OJ L 119, 4.5.2016, p. 1",)

    monkeypatch.setattr("api.v2.legislative.eur_lex._law_created_at", lambda db, c: None)
    monkeypatch.setattr("api.v2.legislative.eur_lex._read_law_xref",
                        lambda db, c: {"eli": "http://data.europa.eu/eli/reg/2016/679/oj", "oj_reference": "L 119/1"})
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="t@example.com", role="admin")
    app.dependency_overrides[get_db] = lambda: type("DB", (), {"query": lambda self, m: Q()})()
    try:
        r = TestClient(app).get("/api/v2/legislative/eur-lex/laws/32016R0679/xref")
    finally:
        app.dependency_overrides.pop(api_user_with_rate_limit, None)
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200, r.text
    body = r.json()
    item = body.get("data", body)
    assert body["cached"] if "cached" in body else item["cached"]
    assert item["oj_reference"] == "OJ L 119, 4.5.2016, p. 1"
