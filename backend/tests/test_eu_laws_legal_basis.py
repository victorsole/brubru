"""eu_laws.legal_basis: one form, read from Cellar by scripts/fill_eu_laws_legal_basis.py, its only writer.

18 Oct 2026: four shapes from three writers ("Having regard to the Treaty ..., and in particular Article 43(3)
thereof,", "Regulation 1151/2012", whole recitals, "Article 114 TFEU") and 13,505 laws without one, GDPR among them.
Titles below are Cellar's own (read 20 Oct 2026). No network, no DB.
"""
import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("fill_eu_laws_legal_basis", BACKEND / "scripts" / "fill_eu_laws_legal_basis.py")
f = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(f)

GDPR_BASIS_TITLE = ("Consolidated version of the Treaty on the Functioning of the European Union#PART ONE - PRINCIPLES"
                    "#TITLE II - PROVISIONS HAVING GENERAL APPLICATION#Article 16 (ex Article 286 TEC)")


@pytest.mark.parametrize("celex,title,want", [
    ("12012E016", GDPR_BASIS_TITLE, "Article 16 TFEU"),      # the title also names the old article 286
    ("12016E114", None, "Article 114 TFEU"),
    ("12016M029", None, "Article 29 TEU"),
    ("11957E100A", "TREATY ESTABLISHING THE EUROPEAN ECONOMIC COMMUNITY, ..., ARTICLE 100 A", "Article 100a EEC Treaty"),
    ("12006E011A", None, "Article 11a EC Treaty"),
    ("11992MK03", "Treaty on European Union - Title VI - Article K.3", "Article K.3 TEU"),
    ("11957A203", None, "Article 203 Euratom Treaty"),
    ("11951K095", None, "Article 95 ECSC Treaty"),
    ("12010P041", None, "Article 41 of the Charter of Fundamental Rights"),
])
def test_a_treaty_article_is_read_from_its_celex(celex, title, want):
    assert f.label(celex, title) == want


@pytest.mark.parametrize("celex,title,want", [
    ("32025L2205", "Directive (EU) 2025/2205 of the European Parliament and of the Council of 19 November 2025 on driving "
                   "licences", "Directive (EU) 2025/2205 of the European Parliament and of the Council"),
    ("32021R0405", "Commission Implementing Regulation (EU) 2021/405 of 24 March 2021 laying down the lists of third "
                   "countries", "Commission Implementing Regulation (EU) 2021/405"),
    ("31967R0359", "Regulation No 359/67/EEC of the Council of 25 July 1967 on the common organisation of the market in "
                   "rice", "Regulation No 359/67/EEC of the Council"),
    ("32008D0721", "2008/721/EC: Commission Decision of 23 June 2008 setting up an advisory structure",
     "Commission Decision 2008/721/EC"),
    ("32002D0309", "2002/309/EC, Euratom: Decision of the Council, and of the Commission as regards the Agreement on "
                   "Scientific and Technological Cooperation, of 4 April 2002 on the conclusion of seven Agreements",
     "Decision 2002/309/EC, Euratom of the Council, and of the Commission as regards the Agreement on Scientific and "
     "Technological Cooperation"),
    ("31975L0442", "Council Directive of 15 July 1975 on waste", "Council Directive of 15 July 1975"),
    ("21990D1231(01)", "Decision No 3/90 of the ACP-EEC Council of Ministers of 29 March 1990 adopting the general "
                       "regulations", "Decision No 3/90 of the ACP-EEC Council of Ministers"),
    ("31974Q1228(01)", "Court of Justice - Rules of Procedure", "Court of Justice - Rules of Procedure"),
    ("32099R9999", None, "32099R9999"),
])
def test_an_act_is_cited_by_its_title_up_to_its_date(celex, title, want):
    assert f.label(celex, title) == want


def test_treaty_articles_come_first_and_a_label_appears_once():
    labels, cx = f.basis({"32025L2205": "Directive (EU) 2025/2205 of the European Parliament and of the Council of 19 "
                                        "November 2025 on driving licences",
                          "12016E114": None, "12012E114": None, "12016E016": None})
    assert labels == ["Article 114 TFEU", "Article 16 TFEU",
                      "Directive (EU) 2025/2205 of the European Parliament and of the Council"]
    assert cx == ["12012E114", "12016E016", "12016E114", "32025L2205"]  # every CELEX kept, in the same order


def test_cellar_silent_none_and_unchanged_are_three_different_things():
    bases = f.parse([{"c": {"value": "32016R0679"}, "tc": {"value": "12012E016"}, "tt": {"value": GDPR_BASIS_TITLE}},
                     {"c": {"value": "32024R1861R(01)"}}])        # known to Cellar, no legal basis
    assert bases == {"32016R0679": {"12012E016": GDPR_BASIS_TITLE}, "32024R1861R(01)": {}}
    rows = [(1, "32016R0679", ["Having regard to the Treaty on the Functioning of the European Union,"], None),
            (2, "32024R1861R(01)", None, None),
            (3, "32099R0001", ["kept"], None),                     # Cellar silent: never written
            (4, "32016R0679", ["Article 16 TFEU"], "2026-10-20")]  # already right and read: not written again
    got = f.changes_for(rows, bases, "2026-10-20")
    assert [(c[0], c[2], json.loads(c[3])) for c in got] == [(1, ["Article 16 TFEU"], ["12012E016"]), (2, [], [])]


def test_a_call_counts_only_when_both_control_laws_come_back(monkeypatch):
    class Budget:
        def __init__(self): self.results = []
        def check(self): pass
        def result(self, ok): self.results.append(ok)

    gdpr = {"c": {"value": "32016R0679"}, "tc": {"value": "12012E016"}}
    impl = {"c": {"value": "32026R2266"}, "tc": {"value": "32025L2205"},
            "tt": {"value": "Directive (EU) 2025/2205 of the European Parliament and of the Council of 19 November 2025 on x"}}
    law = {"c": {"value": "32026R0001"}, "tc": {"value": "12016E114"}}
    b = Budget()
    monkeypatch.setattr(f.urllib.request, "urlopen", lambda req, timeout=0: _Resp([gdpr, law]))
    assert f._ask(["32026R0001"], b) is None and b.results == [False]  # one control missing: the call does not count
    monkeypatch.setattr(f.urllib.request, "urlopen", lambda req, timeout=0: _Resp([gdpr, impl, law]))
    assert f._ask(["32026R0001"], b) == {"32026R0001": {"12016E114": None}} and b.results[-1] is True


class _Resp:
    def __init__(self, rows): self.rows = rows
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return json.dumps({"results": {"bindings": self.rows}}).encode()


def _calls_with_keyword(path, func, kw):
    tree = ast.parse(path.read_text())
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call) and getattr(n.func, "id", None) == func
            and any(k.arg == kw for k in n.keywords)]


def test_the_script_is_the_columns_only_writer():
    upd = (BACKEND / "scripts" / "import_corpus_update.py").read_text()
    assert '"legal_basis"' not in upd[upd.index("def parsed_fields"):upd.index("def process_corpus")]
    assert not _calls_with_keyword(BACKEND / "scripts" / "import_leg_archive.py", "EULaw", "legal_basis")
    assert not _calls_with_keyword(BACKEND / "services" / "law_database" / "law_indexer.py", "EULaw", "legal_basis")
    rep = (BACKEND / "scripts" / "repair_eu_laws_wrong_file.py").read_text()
    writes = re.search(r"\nWRITES = \((.*?)\)\n", rep, re.S).group(1)
    template = re.search(r'\nTEMPLATE = "(.*?)"', rep).group(1)
    assert "legal_basis" not in writes and "legal_basis =" not in rep
    assert template.count("%s") == len(re.findall(r'"\w+"', writes)) + 1  # id + one per written column


def test_the_daily_tier_runs_it():
    cron = (BACKEND / "api" / "cron.py").read_text()
    assert re.search(r'results\["eu_laws_legal_basis"\] = await _run_script_async\("eu_laws_legal_basis", '
                     r'"scripts/fill_eu_laws_legal_basis.py", \["--apply"\]', cron)
    recorded = re.search(r"_DAILY_TIER_RECORDED = \((.*?)\)", cron, re.S).group(1)
    assert '"eu_laws_legal_basis"' in recorded
    assert "sync_runs" not in (BACKEND / "scripts" / "fill_eu_laws_legal_basis.py").read_text()  # the tier records it
