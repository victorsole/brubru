"""eu_laws holds legal acts only, CELEX sector 3 (17 Oct 2026).

The LEG_2026-10 export carries two corrigenda of Council notices (sector 5); the importer stored them and /laws
served them as laws. They were removed, and no importer writes a document of another sector again.

The importers import the models as `backend.models`, the API tests as `models`: loading both in one process breaks
the mapping, so the importers run in a child process here, against a fake export and a fake session.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

from backend.scripts.leg_folder import is_legal_act

_REPO_ROOT = str(Path(__file__).resolve().parents[2])
ACT = "32016R0679"
NOTICE = "52010XG0729(01)R(01)"


def _child(code):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([_REPO_ROOT, str(Path(_REPO_ROOT) / "backend")])}
    out = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=_REPO_ROOT, env=env,
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-3000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_is_legal_act():
    assert is_legal_act(ACT) and is_legal_act("32024R1689R(02)")
    assert not is_legal_act(NOTICE)
    assert not is_legal_act("22016A0505(01)") and not is_legal_act("02016R0679-20160504")
    assert not is_legal_act(None) and not is_legal_act("")


FAKE_SESSION = '''
class Q:
    def filter(self, *a, **k): return self
    def all(self): return []
    def first(self): return None
class R:
    def scalar(self): return 0
class Session:
    added = []
    def query(self, *a): return Q()
    def execute(self, *a, **k): return R()
    def add(self, o): Session.added.append(getattr(o, "celex", None))
    def bulk_save_objects(self, objs): Session.added.extend(getattr(o, "celex", None) for o in objs)
    def commit(self): pass
    def refresh(self, o): pass
    def rollback(self): pass
    def close(self): pass
'''


def test_the_delta_import_never_reads_a_new_folder_of_another_sector(tmp_path):
    for uuid, celex in (("u-act", ACT), ("u-notice", NOTICE)):
        (tmp_path / uuid / "fmx4").mkdir(parents=True)
        (tmp_path / uuid / "tree_non_inferred.rdf").write_text(
            f"<rdf:RDF><j.0:resource_legal_id_celex>{celex}</j.0:resource_legal_id_celex></rdf:RDF>")
    got = _child(FAKE_SESSION + f'''
import json
from pathlib import Path
import backend.scripts.import_corpus_update as icu
read = []
icu.SessionLocal = Session
icu.PROJECT_ROOT = Path({str(tmp_path)!r})
icu.cellar_in_force = lambda celexes: {{}}
icu.main_file = lambda corpus, uuid, celex, *a, **k: (read.append(celex), (None, None))[1]
stats = icu.process_corpus(Path({str(tmp_path)!r}), "LEG_TEST")
print(json.dumps({{"read": read, "skipped": stats["skipped_not_legal_act"], "added": Session.added}}))
''')
    assert got == {"read": [ACT], "skipped": 1, "added": []}


def test_the_first_import_skips_a_document_of_another_sector(tmp_path):
    got = _child(FAKE_SESSION + '''
import json
from types import SimpleNamespace
import backend.scripts.import_leg_archive as ila
def parsed(celex):
    return SimpleNamespace(celex=celex, title="T", doc_type="Regulation", date=None, oj_reference=None,
                           legal_basis=[], citations=[], short_title=None, language="EN", page_count=1,
                           eea_relevance=False, articles=[], recitals=[], annexes=[])
ila.determine_policy_area = lambda p: None
ila.is_primary_legislation = lambda p: True
out = {}
for celex in ("%s", "%s"):
    Session.added = []
    parser = SimpleNamespace(parse_file=lambda path, c=celex: parsed(c))
    row = ila.import_document(Session(), "u", "x.xml", parser)
    out[celex] = [row is not None, Session.added]
print(json.dumps(out))
''' % (ACT, NOTICE))
    assert got == {ACT: [True, [ACT]], NOTICE: [False, []]}


def test_the_old_indexer_skips_a_document_of_another_sector(tmp_path):
    for uuid in ("u-act", "u-notice"):
        (tmp_path / uuid).mkdir()
    got = _child(FAKE_SESSION + f'''
import asyncio, json
from pathlib import Path
import services.law_database.law_indexer as li
li.SessionLocal = Session
ix = object.__new__(li.EULawIndexer)
ix.leg_directory, ix.batch_size, ix.enable_policy_classification = Path({str(tmp_path)!r}), 100, False
celex_of = {{"u-act": "{ACT}", "u-notice": "{NOTICE}"}}
ix._find_primary_xml = lambda d: d / "x.xml"
ix.xml_parser = type("P", (), {{"parse_file": lambda self, f: {{
    "uuid": Path(f).parent.name, "celex": celex_of[Path(f).parent.name], "title": "T", "doc_type": "Regulation",
    "xml_path": str(f)}}}})()
stats = asyncio.run(ix.index_all_laws())
print(json.dumps({{"added": Session.added, "skipped": stats["skipped"]}}))
''')
    assert got == {"added": [ACT], "skipped": 1}
