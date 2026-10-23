"""eu_laws.date is the date the act's title gives it, Cellar's date otherwise; a corrigendum keeps Cellar's (20 Oct 2026).

Cellar's work_date_document is wrong for some acts: 32026R0144 "of 14 January 2026" held 2025-01-14, 32013D0719
"of 16 November 2012" held 2013-11-16, 32024D2955 "of 21 November 2024" held 2021-11-21. The importer, the repair
script and the daily Cellar sync wrote it as it stood. A corrigendum's title names the corrected act's date, so a
corrigendum keeps Cellar's date (its own publication).

The importer runs in a child process (see test_eu_laws_legal_acts_only.py: the models load under two module names).
"""
import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from backend.scripts.leg_folder import act_date, title_date

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
_PATH = Path(__file__).resolve().parents[1] / "scripts" / "sync_eu_laws_from_cellar.py"


@pytest.mark.parametrize("title,expected", [
    ("Commission Implementing Regulation (EU) 2026/144 of 14 January 2026 on the approval", "2026-01-14"),
    ("Commission Decision of 16 November 2012 State aid SA.33305 (2012/C)", "2012-11-16"),
    ("Decision (EU) 2016/407 of the European Parliament and of the Council of 9 March 2016 on", "2016-03-09"),
    ("Decision of the Management Board of the European Union Agency for Railways of 5 May 2020", "2020-05-05"),
    ("DIRECTIVE 2004/41/EC OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL OF 21 APRIL 2004 repealing", "2004-04-21"),
    ("Commission Implementing Regulation (EU) 2026/2053 of 10\xa0September 2026 granting", "2026-09-10"),
    # another act's date, or none
    ("Corrigendum to Commission Implementing Regulation (EU) 2021/1832 of 12 October 2021 amending", None),
    ("Addendum to Regulation (EC) No 1922/2006 of the European Parliament and of the Council of 20 December 2006", None),
    ("Consolidated version of Council Decision of 22 December 2004 on the putting into effect", None),
    ("Decision of the Supply Agency of the European Atomic Energy Community adopting the Agency Rules (Rules of 5 May 1960)", None),
    ("Rules Governing Public Access To European Parliament documents Bureau decision of 28 November 2001OJ C 374", None),
    ("Rules of Procedure of Eurojust", None),
    ("Commission Regulation of 31 February 2020 on", None),
    (None, None),
])
def test_title_date(title, expected):
    assert title_date(title) == expected


def test_act_date():
    assert act_date("32026R0144", "Commission Implementing Regulation (EU) 2026/144 of 14 January 2026", "2025-01-14") == "2026-01-14"
    assert act_date("32020Q0224(01)", "Rules of Procedure of Eurojust", "2019-12-20") == "2019-12-20"
    # a corrigendum keeps the recorded date, even when its title repeats the act's own
    assert act_date("32021R1832R(01)", "Corrigendum to Commission Implementing Regulation (EU) 2021/1832 of 12 October 2021",
                    "2021-11-19") == "2021-11-19"
    assert act_date("32017R2330R(01)", "COMMISSION IMPLEMENTING REGULATION (EU) 2017/2330 of 14 December 2017",
                    "2017-12-30") == "2017-12-30"
    assert act_date("32016R0679", "no date here", None) is None


EURATOM = "Commission Decision 2006/635/Euratom of 4 April 2006 on the conclusion, by way of signature, of an Agreement"


def test_a_corrigendum_that_corrects_the_title_date_wins_with_cellar():
    """Register O65 (23 Oct 2026): 32006D0635R(01) reads "for: 4 April 2006, read: 4 April 2005"; Cellar holds 2005-04-04."""
    fixed = [("2006-04-04", "2005-04-04")]
    assert act_date("32006D0635", EURATOM, "2005-04-04", fixed) == "2005-04-04"
    # without the corrigendum the title wins, as before
    assert act_date("32006D0635", EURATOM, "2005-04-04") == "2006-04-04"
    # Cellar holds neither date: the title wins (two witnesses or none)
    assert act_date("32006D0635", EURATOM, "2006-05-01", fixed) == "2006-04-04"
    # the corrigendum corrects another date: the title wins
    assert act_date("32006D0635", EURATOM, "2005-04-04", [("2006-03-01", "2005-04-04")]) == "2006-04-04"
    # a corrigendum's own date is never moved by its pairs
    assert act_date("32006D0635R(01)", "Corrigendum to " + EURATOM, "2007-04-03", fixed) == "2007-04-03"


def test_the_daily_sync_takes_the_title_date():
    spec = importlib.util.spec_from_file_location("sync_eu_laws_from_cellar_act_date", _PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    title = "Council Decision (EU) 2024/2955 of 21 November 2024 on the position"
    assert mod.document_date("2021-11-21", "2024-11-29", title, "32024D2955") == "2024-11-21"
    corr = "Corrigendum to Council Regulation (EU) 2026/266 of 26 January 2026 fixing"
    assert mod.document_date("2026-02-20", "2026-02-24", corr, "32026R0266R(01)") == "2026-02-20"
    # Cellar's date later than publication and no title date: the publication date
    assert mod.document_date("2030-01-01", "2026-02-24", corr, "32026R0266R(01)") == "2026-02-24"


FAKE = '''
import json
from pathlib import Path
from types import SimpleNamespace
import backend.scripts.import_corpus_update as icu
class Q:
    def filter(self, *a, **k): return self
    def all(self): return []
    def first(self): return None
class R:
    rowcount = 0
    def scalar(self): return 0
    def fetchall(self): return []
class Session:
    added = []
    def query(self, *a): return Q()
    def execute(self, *a, **k): return R()
    def add(self, o): Session.added.append(o)
    def bulk_save_objects(self, objs): Session.added.extend(objs)
    def commit(self): pass
    def refresh(self, o): pass
    def rollback(self): pass
    def close(self): pass
icu.SessionLocal = Session
icu.cellar_in_force = lambda celexes: {}
icu.main_file = lambda corpus, uuid, *a, **k: (corpus / uuid / "fmx4" / "act.xml", None)
icu.act_confirmed = lambda *a: None
icu.export_metadata = lambda *a: {}
icu.parsed_fields = lambda p, rel, h, v: {"title": p.title, "date": None, "content_hash": h, "xml_path": rel,
                                          "corpus_version": v, "extra_metadata": {}}
class Parser:
    def parse_file(self, path): return SimpleNamespace(title="parsed title", celex=None, date=None)
icu.FormexParser = Parser
import backend.scripts.fix_eu_laws_dates as fx
CALLS = []
fx.recheck_acts = lambda db, acts, dump: CALLS.append(sorted(acts)) or 0
'''

RDF = ('<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns:j.0="http://publications.europa.eu/ontology/cdm#">'
       '<rdf:Description><j.0:resource_legal_id_celex>{celex}</j.0:resource_legal_id_celex>'
       '<j.0:work_date_document>{date}</j.0:work_date_document></rdf:Description>'
       '<rdf:Description><j.0:expression_uses_language rdf:resource="http://publications.europa.eu/resource/authority/language/ENG"/>'
       '<j.0:expression_title>{title}</j.0:expression_title></rdf:Description></rdf:RDF>')


def test_the_importer_writes_the_title_date(tmp_path):
    folders = {
        "u-act": ("32026R0144", "2025-01-14", "Commission Implementing Regulation (EU) 2026/144 of 14 January 2026 on x"),
        "u-corr": ("32021R1832R(01)", "2021-11-19", "Corrigendum to Commission Implementing Regulation (EU) 2021/1832 of 12 October 2021"),
        "u-rules": ("32020Q0224(01)", "2019-12-20", "Rules of Procedure of Eurojust"),
    }
    for uuid, (celex, d, title) in folders.items():
        (tmp_path / uuid / "fmx4").mkdir(parents=True)
        (tmp_path / uuid / "fmx4" / "act.xml").write_text("<ACT><TITLE><TI><P>x 1</P></TI></TITLE></ACT>")
        (tmp_path / uuid / "tree_non_inferred.rdf").write_text(RDF.format(celex=celex, date=d, title=title))
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([_REPO_ROOT, str(Path(_REPO_ROOT) / "backend")])}
    code = FAKE + f'''
icu.PROJECT_ROOT = Path({str(tmp_path)!r})
icu.process_corpus(Path({str(tmp_path)!r}), "LEG_TEST")
print(json.dumps({{"added": {{o.celex: str(o.date) for o in Session.added}}, "rechecked": CALLS}}))
'''
    out = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=_REPO_ROOT, env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-3000:]
    got = json.loads(out.stdout.strip().splitlines()[-1])
    assert got["added"] == {"32026R0144": "2026-01-14", "32021R1832R(01)": "2021-11-19", "32020Q0224(01)": "2019-12-20"}
    # the run ends by re-checking the act of the corrigendum it wrote and the act whose title and Cellar disagree
    assert got["rechecked"] == [["32021R1832", "32026R0144"]]


def test_the_repair_changes_only_what_the_rule_changes():
    from backend.scripts.fix_eu_laws_dates import changes_for
    rows = [
        (1, "32026R0144", "u1", "2025-01-14", "Commission Implementing Regulation (EU) 2026/144 of 14 January 2026", "LEG_2026-10"),
        (2, "32021R1832R(01)", "u2", "2021-10-12", "Corrigendum to Commission Implementing Regulation (EU) 2021/1832 "
            "of 12 October 2021", "LEG_2026-10"),
        (3, "32013D0719", "u3", "2012-11-16", "Commission Decision of 16 November 2012 State aid", "LEG_2026-10"),
        (4, "32020Q0224(01)", "u4", "2020-02-24", "Rules of Procedure of Eurojust", "LEG_2026-10"),
        (5, "32024D2955", None, "2021-11-21", "Council Decision (EU) 2024/2955 of 21 November 2024 on", "OJ_2026-10"),
        (6, "32016R0679", "u6", "2016-04-27", "Regulation (EU) 2016/679 of the European Parliament and of the Council "
            "of 27 April 2016", "LEG_2026-10"),
    ]
    cellar = {"u1": "2025-01-14", "u2": "2021-11-19", "u3": "2013-11-16", "u4": "2019-12-20", "u6": "2016-04-27"}
    changes, cellar_wrong = changes_for(rows, lambda uuid, version: cellar.get(uuid))
    assert changes == [(1, "32026R0144", "2025-01-14", "2026-01-14", "act"),
                       (2, "32021R1832R(01)", "2021-10-12", "2021-11-19", "corrigendum"),
                       (4, "32020Q0224(01)", "2020-02-24", "2019-12-20", "act"),
                       (5, "32024D2955", "2021-11-21", "2024-11-21", "act")]
    assert cellar_wrong == [(3, "32013D0719", "2012-11-16", "2013-11-16")]


def test_the_repair_takes_a_corrigendums_date_when_cellar_agrees():
    from backend.scripts.fix_eu_laws_dates import changes_for
    rows = [(1, "32006D0635", "u1", "2006-04-04", EURATOM, "LEG_2026-10"),
            (3, "32013D0719", "u3", "2012-11-16", "Commission Decision of 16 November 2012 State aid", "LEG_2026-10")]
    cellar = {"u1": "2005-04-04", "u3": "2013-11-16"}
    corr = {"32006D0635": [("2006-04-04", "2005-04-04")]}
    changes, cellar_wrong = changes_for(rows, lambda uuid, version: cellar.get(uuid), lambda c: corr.get(c, ()))
    assert changes == [(1, "32006D0635", "2006-04-04", "2005-04-04", "act")]
    assert cellar_wrong == [(3, "32013D0719", "2012-11-16", "2013-11-16")]


class _Rows:
    def __init__(self, rows):
        self.rows, self.rowcount = rows, len(rows)

    def fetchall(self):
        return self.rows


class _Db:
    """Answers the statements recheck_acts and corrigendum_corrections send; records the UPDATEs."""
    def __init__(self, laws):
        self.laws, self.updates = laws, []

    def execute(self, sql, params):
        import re
        q = " ".join(str(sql).split())
        if q.startswith("SELECT id, celex"):
            return _Rows([r for r in self.laws if r[1] in params["a"]])
        if "regexp_replace" in q:
            return _Rows([(r[1], r[2]) for r in self.laws
                          if r[1].endswith(")") and re.sub(r"R\(\d\d\)$", "", r[1]) in params["a"] and "R(" in r[1]])
        if q.startswith("SELECT celex, body_txt"):
            return _Rows([])
        if q.startswith("UPDATE"):
            self.updates.append((params["i"], params["new"]))
            return _Rows([params["i"]])
        raise AssertionError(q)

    def commit(self):
        pass


def test_recheck_reads_the_corrigendum_and_writes_the_corrected_date(tmp_path):
    """End to end on a folder dump: the act's Cellar date from its RDF, the correction from the corrigendum's Formex."""
    from backend.scripts.fix_eu_laws_dates import recheck_acts
    for uuid, celex, d, title in (("u-act", "32006D0635", "2005-04-04", EURATOM),
                                  ("u-3", "32013D0719", "2013-11-16", "Commission Decision of 16 November 2012 State aid")):
        (tmp_path / uuid).mkdir()
        (tmp_path / uuid / "tree_non_inferred.rdf").write_text(RDF.format(celex=celex, date=d, title=title))
    (tmp_path / "u-corr" / "fmx4").mkdir(parents=True)
    (tmp_path / "u-corr" / "fmx4" / "corr.xml").write_text(
        "<CORR><P>On the cover in the contents and on page 26 in the title and the signature: for: 4 April 2006 , "
        "read: 4 April 2005 .</P></CORR>")
    db = _Db([(1, "32006D0635", "u-act", "2006-04-04", EURATOM, "LEG_2026-10"),
              (2, "32006D0635R(01)", "u-corr", "2007-04-03", "Corrigendum to " + EURATOM, "LEG_2026-10"),
              (3, "32013D0719", "u-3", "2012-11-16", "Commission Decision of 16 November 2012 State aid", "LEG_2026-10")])
    assert recheck_acts(db, {"32006D0635", "32013D0719"}, tmp_path) == 1
    # 32013D0719: Cellar's error and no corrigendum, so the title's date stays
    assert db.updates == [(1, "2005-04-04")]


def test_recheck_reads_cellar_again_when_the_export_date_is_stale(tmp_path, monkeypatch):
    """32022R0363: the export (11 Oct) held 2022-01-02; the corrigendum reads 2 March 2022, and so does Cellar since the
    helpdesk's fix of 23 Oct. The stale export date alone would put the title's 24 January back."""
    import backend.scripts.fix_eu_laws_dates as fx
    monkeypatch.setattr(fx, "cellar_dates", lambda celexes: {"32022R0363": "2022-03-02"} if "32022R0363" in celexes else {})
    title = "Commission Delegated Regulation (EU) 2022/363 of 24 January 2022 amending"
    (tmp_path / "u-act").mkdir()
    (tmp_path / "u-act" / "tree_non_inferred.rdf").write_text(RDF.format(celex="32022R0363", date="2022-01-02", title=title))
    (tmp_path / "u-corr" / "fmx4").mkdir(parents=True)
    (tmp_path / "u-corr" / "fmx4" / "corr.xml").write_text(
        "<CORR><P>On page 40, title, date of adoption, and on page 42, in the signature: for: 24 January 2022 , "
        "read: 2 March 2022 .</P></CORR>")
    db = _Db([(1, "32022R0363", "u-act", "2022-01-24", title, "LEG_2026-10"),
              (2, "32022R0363R(01)", "u-corr", "2022-03-08", "Corrigendum to " + title, "LEG_2026-10")])
    assert fx.recheck_acts(db, {"32022R0363"}, tmp_path) == 1
    assert db.updates == [(1, "2022-03-02")]

