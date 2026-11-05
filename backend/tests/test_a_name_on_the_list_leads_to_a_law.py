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


def _load_fetcher():
    spec = importlib.util.spec_from_file_location("fetch_eu_law_bodies", BACKEND / "scripts/fetch_eu_law_bodies.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _Page:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self.body.encode()


PAGE = "<html><body><p>" + "Article 1 of the act. " * 60 + "</p><p>ANNEX Correlation table &gt;TABLE&gt;</p></body></html>"
CLEAN = "<html><body><p>" + "Article 1 of the act. " * 60 + "</p></body></html>"


def test_a_page_that_lost_its_tables_gives_way_to_the_pdf(monkeypatch):
    fetcher = _load_fetcher()
    monkeypatch.setattr(fetcher.urllib.request, "urlopen", lambda *a, **k: _Page(PAGE))
    monkeypatch.setattr(fetcher, "_fetch_pdf", lambda c, ctx: ("<p>from the pdf</p>", "x" * 5000))
    assert fetcher._fetch("32004R0139", None)[0] == "<p>from the pdf</p>"


def test_the_page_stays_if_the_pdf_is_missing_or_clearly_shorter(monkeypatch):
    fetcher = _load_fetcher()
    monkeypatch.setattr(fetcher.urllib.request, "urlopen", lambda *a, **k: _Page(PAGE))
    monkeypatch.setattr(fetcher, "_fetch_pdf", lambda c, ctx: "http_404")
    assert "TABLE" in fetcher._fetch("32004R0139", None)[1]
    monkeypatch.setattr(fetcher, "_fetch_pdf", lambda c, ctx: ("<p>short</p>", "too short"))
    assert "TABLE" in fetcher._fetch("32004R0139", None)[1]


def test_a_page_with_its_tables_never_asks_for_the_pdf(monkeypatch):
    fetcher = _load_fetcher()
    monkeypatch.setattr(fetcher.urllib.request, "urlopen", lambda *a, **k: _Page(CLEAN))

    def no_pdf(c, ctx):
        raise AssertionError("the PDF was asked for")

    monkeypatch.setattr(fetcher, "_fetch_pdf", no_pdf)
    assert "Article 1" in fetcher._fetch("32016R0679", None)[1]


class _Done:
    def __init__(self, out, code=0):
        self.stdout, self.returncode = out, code


def test_a_pdf_is_read_with_pdftotext_where_the_machine_has_it(monkeypatch):
    fetcher = _load_fetcher()
    monkeypatch.setattr(fetcher.shutil, "which", lambda name: "/usr/bin/pdftotext")
    seen = []
    monkeypatch.setattr(fetcher.subprocess, "run", lambda cmd, **k: seen.append(cmd) or _Done("the substance shall".encode()))
    assert fetcher._pdf_text(b"%PDF-") == "the substance shall"
    assert seen[0][0] == "pdftotext"


def test_pypdf_is_the_fallback_when_pdftotext_is_missing_or_fails(monkeypatch):
    fetcher = _load_fetcher()
    import pypdf

    class _Reader:
        def __init__(self, stream):
            self.pages = [type("P", (), {"extract_text": lambda self: "from pypdf"})()]

    monkeypatch.setattr(pypdf, "PdfReader", _Reader)
    monkeypatch.setattr(fetcher.shutil, "which", lambda name: None)
    assert fetcher._pdf_text(b"%PDF-") == "from pypdf"
    monkeypatch.setattr(fetcher.shutil, "which", lambda name: "/usr/bin/pdftotext")
    monkeypatch.setattr(fetcher.subprocess, "run", lambda cmd, **k: _Done(b"", 1))
    assert fetcher._pdf_text(b"%PDF-") == "from pypdf"


def test_the_image_installs_pdftotext():
    assert "poppler-utils" in (BACKEND / "Dockerfile").read_text()

