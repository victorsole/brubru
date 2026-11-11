"""O242 (11 Nov 2026): committee documents were served without their text.

/parliament/ep-documents answered a line of metadata as the body of every document stored
after 2 Oct 2026: the nightly sync downloaded each .docx, parsed its amendments and threw
the file away, and the only reader of the text was a script nothing ran. 541 documents had no
text (the 515 amendment documents backfilled that morning among them). The same rows showed
two more faults: a row stored before its English record existed kept an empty procedure for
ever (21 of October's 24 draft reports), and the procedure was read from the record's title
only, never from the document's own cover.

Now: the file comes from the open data portal's own link (no browser; doceo's front refused
a whole address that day), its text is stored in the same pass, the cover names the procedure,
a PDF-only document is stored with its PDF text, and the nightly run fills the documents held
without text and writes how many are left on the run row.
"""
import asyncio
import datetime as dt
import importlib.util
import io
import pathlib
import zipfile
from types import SimpleNamespace

import pytest
from sqlalchemy.dialects import postgresql

import services.api_clients.ep_open_data_client as ep_mod
from services.api_clients.ep_open_data_client import EPOpenDataClient, RE_PROCEDURE_REF
from services.scrapers import amendment_document_text as text_mod
from services.scrapers import bulk_amendment_sync_service as svc
from services.schedulers import amendment_sync_scheduler as sched
from tests.test_amendment_documents_are_listed_not_guessed import _scheduled

PROC, OTHER = "2099/0001(COD)", "2099/0002(INI)"


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    async def _sleep(seconds):
        return None
    monkeypatch.setattr(ep_mod.asyncio, "sleep", _sleep)
    monkeypatch.setattr(svc.asyncio, "sleep", _sleep)


def _docx(*paragraphs):
    xml = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body>{xml}</w:body></w:document>")
    return buf.getvalue()


def _cover(procedure=PROC, filler=40):
    return _docx("\ufeffEuropean Parliament", "&lt;Commission&gt;{TEST}Committee on Tests&lt;/Commission&gt;",
                 procedure, "&lt;Date&gt;{08/10/2026}8.10.2026&lt;/Date&gt;", "AMENDMENTS", "1 - 3",
                 *[f"Amendment text line {i} with enough words to count as a document." for i in range(filler)])


# ---- the reader ----------------------------------------------------------------------

def test_the_text_of_a_docx_is_its_paragraphs_without_the_template_markers():
    text, html, stated = text_mod.text_from_docx(_cover())
    lines = text.split("\n\n")
    assert lines[0] == "European Parliament" and lines[1] == "{TEST}Committee on Tests"   # no BOM, no <Commission>
    assert lines[2] == PROC and stated == dt.date(2026, 10, 8)
    assert html.startswith("<p>European Parliament</p><p>{TEST}Committee on Tests</p>") and "&lt;Date" not in html
    assert len(text) >= text_mod.MIN_CHARS


@pytest.mark.parametrize("not_a_docx", [b"", b"<html>challenge</html>", b"PK-not-a-zip", b"%PDF-1.7"])
def test_bytes_that_are_not_a_docx_give_no_text(not_a_docx):
    assert text_mod.text_from_docx(not_a_docx) is None


def test_a_zip_without_a_word_document_gives_no_text():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("other.xml", "<a/>")
    assert text_mod.text_from_docx(buf.getvalue()) is None


def test_bytes_that_are_not_a_pdf_give_no_text():
    assert text_mod.text_from_pdf(b"PK") is None and text_mod.text_from_pdf(b"") is None


def test_the_cover_names_the_procedure_only_when_it_names_exactly_one():
    assert text_mod.procedure_from_cover(f"European Parliament\n\n{PROC}\n\nDraft report\n\n({PROC})") == PROC
    assert text_mod.procedure_from_cover("Committee\n\n2099/0902R(NLE)\n\n8.10.2026") == "2099/0902R(NLE)"
    assert text_mod.procedure_from_cover(f"{PROC}\n\n{OTHER}") == ""                       # two: no guess
    assert text_mod.procedure_from_cover("x" * text_mod._COVER_CHARS + "\n\n" + PROC) == ""   # in the body, not the cover
    assert text_mod.procedure_from_cover("x" * 100 + "\n\n" + PROC) == PROC
    assert text_mod.procedure_from_cover("no reference here") == "" and text_mod.procedure_from_cover(None) == ""
    assert text_mod.procedure_from_cover("2024/20 19(DEC )") == ""                          # a PDF's broken reference


def test_the_title_pattern_reads_the_repeated_consent_form():
    assert RE_PROCEDURE_REF.search("Draft report - (2099/0902R(NLE)) - Committee").group(1) == "2099/0902R(NLE)"
    assert RE_PROCEDURE_REF.search(f"({PROC})").group(1) == PROC


# ---- the record ----------------------------------------------------------------------

def _record(identifier, formats=("pdf", "docx"), language="ENG", title=""):
    folder = "reds_test"
    files = [{"is_exemplified_by": f"distribution/{folder}/{identifier}/{identifier}_en.{f}",
              "format": f"http://publications.europa.eu/resource/authority/file-type/{f.upper()}"} for f in formats]
    return {"data": [{"identifier": identifier, "document_date": "2026-10-28", "is_realized_by": [
        {"language": "http://publications.europa.eu/resource/authority/language/EST",
         "is_embodied_by": [{"is_exemplified_by": f"distribution/{folder}/{identifier}/{identifier}_et.docx",
                             "format": "http://publications.europa.eu/resource/authority/file-type/DOCX"}]},
        {"language": f"http://publications.europa.eu/resource/authority/language/{language}",
         "is_embodied_by": files, "title_alternative": {"en": title}}]}]}


def test_the_record_gives_the_english_files_by_format():
    d = EPOpenDataClient()._parse_document_detail(_record("TEST-PR-796480"), "TEST-PR-796480")
    base = "https://data.europarl.europa.eu/distribution/reds_test/TEST-PR-796480/TEST-PR-796480_en"
    assert d["files"] == {"pdf": base + ".pdf", "docx": base + ".docx"}


def test_a_record_with_a_pdf_only_lists_no_docx_and_another_language_is_never_taken_for_english():
    c = EPOpenDataClient()
    assert list(c._parse_document_detail(_record("TEST-AM-768235", formats=("pdf",)), "TEST-AM-768235")["files"]) == ["pdf"]
    assert c._parse_document_detail(_record("TEST-AM-768236", language="FRA"), "TEST-AM-768236")["files"] == {}
    assert c._parse_document_detail({"data": [{}]}, "TEST-AM-768237")["files"] == {}


# ---- the sync ------------------------------------------------------------------------

def _svc(details, downloads):
    s = svc.BulkAmendmentSyncService.__new__(svc.BulkAmendmentSyncService)
    s._docx_cache, s._fetch_facts, s._details, s._pdf_urls = {}, {}, {}, {}
    asked = {"detail": [], "download": []}

    async def _detail(ep_id, endpoint="documents"):
        asked["detail"].append((ep_id, endpoint))
        if ep_id not in details:
            raise RuntimeError("404")
        return details[ep_id]

    async def _download(url):
        asked["download"].append(url)
        return downloads.get(url)
    s.client, s._download = SimpleNamespace(get_document_detail=_detail), _download
    return s, asked


def _stub(identifier):
    return EPOpenDataClient()._stub_to_doc(identifier)


def test_the_portal_is_asked_first_and_the_browser_only_for_what_it_could_not_supply():
    docs = [_stub("TEST-AM-790001"), _stub("TEST-AM-790002"), _stub("TEST-AM-790003"), _stub("TEST-AM-790004")]
    s, asked = _svc({"TEST-AM-790001": {"files": {"docx": "u1"}}, "TEST-AM-790002": {"files": {"pdf": "u2"}},
                     "TEST-AM-790003": {"files": {"docx": "u3"}}}, {"u1": _cover(), "u3": b"<html>error</html>"})
    read, warmed = [], []

    async def _enum(**k):
        return docs

    async def _close():
        return None

    async def _walled(urls):
        warmed.extend(urls)

    async def _fetch(doc):
        read.append(doc["identifier"])
        return 0
    s.client.enumerate_all_documents, s.client.close = _enum, _close
    s._is_settled = lambda ep_id: False
    s._prefetch_walled_documents, s._fetch_and_parse_document = _walled, _fetch
    asyncio.run(s.sync_all(years=[2026]))
    assert list(s._docx_cache) == [docs[0]["doceo_url"]]                          # only a real .docx is kept
    assert s._fetch_facts[docs[1]["doceo_url"]] == (200, "pdf_only") and s._pdf_urls[docs[1]["doceo_url"]] == "u2"
    assert warmed == [docs[2]["doceo_url"], docs[3]["doceo_url"]]                 # a bad file and a missing record
    assert asked["download"] == ["u1", "u3"] and len(read) == 4                   # a PDF is not downloaded as a docx
    assert ("TEST-AM-790001", "documents") in asked["detail"]


def _parse_one(s, doc, amendments=()):
    recorded, parsed = {}, {}
    s.parser = SimpleNamespace(parse_docx=lambda **k: parsed.update(k) or list(amendments))
    s._procedure_of = lambda ep_id: {"TEST-PR-780000": OTHER}.get(ep_id, "")
    s._upsert_document_record = lambda d, **k: recorded.update(doc=dict(d), **k)
    s._upsert_amendment = lambda pa, url, date: None
    s.db = SimpleNamespace(commit=lambda: None)
    try:
        count = asyncio.run(s._fetch_and_parse_document(doc))
    except Exception as e:  # noqa: BLE001
        return e, recorded, parsed
    return count, recorded, parsed


def test_the_text_is_stored_in_the_pass_that_parses_and_the_cover_names_the_procedure():
    doc = _stub("TEST-AM-790001")
    s, asked = _svc({"TEST-AM-790001": {"date": "2026-10-08", "procedure_reference": OTHER,
                                        "parent_identifier": "TEST-PR-780000"}}, {})
    s._docx_cache[doc["doceo_url"]] = _cover()
    count, recorded, parsed = _parse_one(s, doc)
    stored = recorded["doc"]
    assert count == 0 and recorded["status"] == "parsed"
    assert stored["_text_body"].startswith("European Parliament") and stored["_body_html"].startswith("<p>European")
    assert stored["procedure_reference"] == PROC == parsed["procedure_ref"]       # the cover, not the record's title
    assert stored["date"] == "2026-10-08" and asked["detail"] == [("TEST-AM-790001", "documents")]


def test_a_cover_that_names_no_procedure_leaves_the_record_then_the_parent():
    for detail, expected in (({"procedure_reference": OTHER}, OTHER),
                             ({"procedure_reference": "", "parent_identifier": "TEST-PR-780000"}, OTHER),
                             ({}, "")):
        doc = _stub("TEST-AM-790001")
        s, _ = _svc({"TEST-AM-790001": detail}, {})
        s._docx_cache[doc["doceo_url"]] = _cover(procedure="0000/0000(INI)")      # the template's placeholder
        _, recorded, parsed = _parse_one(s, doc)
        assert parsed["procedure_ref"] == expected and recorded["doc"].get("procedure_reference", "") == expected


def test_a_document_too_short_to_be_a_text_is_parsed_without_one():
    doc = _stub("TEST-AM-790001")
    s, _ = _svc({"TEST-AM-790001": {}}, {})
    s._docx_cache[doc["doceo_url"]] = _docx("European Parliament", PROC)
    _, recorded, _ = _parse_one(s, doc)
    assert "_text_body" not in recorded["doc"] and recorded["doc"]["procedure_reference"] == PROC


def test_a_pdf_only_document_is_stored_with_its_pdf_text_date_and_procedure(monkeypatch):
    doc = _stub("TEST-AM-768235")
    s, asked = _svc({"TEST-AM-768235": {"date": "2025-02-10", "procedure_reference": PROC, "files": {"pdf": "p1"}}},
                    {"p1": b"%PDF-bytes"})
    s._fetch_facts[doc["doceo_url"]], s._pdf_urls[doc["doceo_url"]] = (200, "pdf_only"), "p1"
    monkeypatch.setattr(svc, "text_from_pdf", lambda b: ("T" * 500, "<p>T</p>", None) if b == b"%PDF-bytes" else None)
    error, recorded, _ = _parse_one(s, doc)
    assert isinstance(error, svc.UnsupportedDocumentFormat) and "PDF only" in str(error)
    assert doc["_text_body"] == "T" * 500 and doc["date"] == "2025-02-10" and doc["procedure_reference"] == PROC
    assert asked["download"] == ["p1"] and recorded == {}                          # the caller records it, as unsupported
    assert doc["doceo_url"] == "https://www.europarl.europa.eu/doceo/document/TEST-AM-768235_EN.pdf"   # not the 404


def test_a_pdf_only_document_with_no_procedure_in_its_record_takes_its_parents(monkeypatch):
    doc = _stub("TEST-AM-768236")
    s, _ = _svc({"TEST-AM-768236": {"procedure_reference": "", "parent_identifier": "TEST-PR-780000",
                                    "files": {"pdf": "p1"}}}, {})
    s._fetch_facts[doc["doceo_url"]], s._pdf_urls[doc["doceo_url"]] = (200, "pdf_only"), "p1"
    monkeypatch.setattr(svc, "text_from_pdf", lambda b: None)
    error, _, _ = _parse_one(s, doc)
    assert isinstance(error, svc.UnsupportedDocumentFormat) and doc["procedure_reference"] == OTHER
    assert "_text_body" not in doc                                                 # a PDF that does not read stores no text


def test_a_document_missing_at_doceo_with_no_record_is_still_not_found():
    doc = _stub("TEST-AM-790009")
    s, _ = _svc({}, {})
    s._fetch_facts[doc["doceo_url"]] = (404, "not_found")
    error, _, _ = _parse_one(s, doc)
    assert isinstance(error, svc.DocumentNotFound)


def _upsert_sql(doc):
    s, seen = svc.BulkAmendmentSyncService.__new__(svc.BulkAmendmentSyncService), []
    s.db = SimpleNamespace(execute=seen.append)
    s._upsert_document_record(doc, status="parsed", error_message=None, total_amendments=2)
    compiled = seen[0].compile(dialect=postgresql.dialect())
    return str(compiled), compiled.params


def test_a_later_run_never_blanks_a_text_and_fills_an_empty_procedure():
    sql, params = _upsert_sql({**_stub("TEST-AM-790001"), "procedure_reference": PROC,
                               "_text_body": "the text", "_body_html": "<p>the text</p>"})
    update = sql.split("DO UPDATE SET", 1)[1]
    assert "text_body = coalesce(" in update and "amendment_documents.text_body" in update
    assert "body_html = coalesce(" in update and "body_fetched_at = coalesce(" in update
    assert "procedure_reference = coalesce(nullif(" in update and "amendment_documents.procedure_reference" in update
    assert "doceo_url = " in update
    assert params["text_body"] == "the text" and params["body_fetched_at"] is not None and PROC in params.values()


def test_a_run_that_read_no_text_writes_none_and_stamps_nothing():
    _, params = _upsert_sql(_stub("TEST-AM-790001"))
    assert params["text_body"] is None and params["body_html"] is None and params["body_fetched_at"] is None


# ---- the documents already held without text ------------------------------------------

class _Query:
    def __init__(self, session, entities):
        self.s, self.entities, self.criteria = session, entities, []

    def filter(self, *criteria):
        self.criteria.extend(criteria)
        return self

    def order_by(self, *a):
        return self

    def limit(self, n):
        self.s.limit = n
        return self

    def _sql(self):
        return " AND ".join(str(c.compile(dialect=postgresql.dialect())) for c in self.criteria)

    def all(self):
        sql = self._sql()
        if "text_body, %(coalesce_1)s) !=" in sql or "!= " in sql.split(" AND ")[0]:
            self.s.procedure_sql = sql                       # the rows held with text and no procedure
            return list(self.s.held_with_text)
        self.s.candidate_sql = sql
        return list(self.s.rows)

    def scalar(self):
        return self.s.remaining

    def update(self, values, synchronize_session=False):
        params = [c.compile(dialect=postgresql.dialect()).params for c in self.criteria]
        self.s.amendment_updates.append((values, [v for p in params for v in p.values()]))


class _Session:
    def __init__(self, rows, remaining=0):
        self.rows, self.remaining, self.commits, self.amendment_updates = rows, remaining, 0, []
        self.held_with_text = []

    def query(self, *entities):
        return _Query(self, entities)

    def commit(self):
        self.commits += 1


def _row(identifier, status="parsed", procedure="", date=dt.date(2026, 10, 1), kind="AM"):
    pe = "PE" + identifier[-6:-3] + "." + identifier[-3:]
    return SimpleNamespace(ep_identifier=identifier, pe_reference=pe, document_type=kind, status=status,
                           procedure_reference=procedure, document_date=date, text_body=None, body_html=None,
                           body_fetched_at=None, error_message=None,
                           doceo_url=f"https://www.europarl.europa.eu/doceo/document/{identifier}_EN.docx")


def _fill(rows, details, downloads, monkeypatch, remaining=0, parents=None):
    s, asked = _svc(details, downloads)
    s.db = _Session(rows, remaining)
    s._procedure_of = lambda ep_id: (parents or {}).get(ep_id, "")
    monkeypatch.setattr(svc, "text_from_pdf", lambda b: (f"Committee on Tests\n\n{OTHER}\n\n" + "P" * 400, "<p>P</p>", dt.date(2025, 2, 10))
                        if b == b"%PDF-bytes" else None)
    return asyncio.run(s.fill_missing_text(limit=7)), s, asked


def test_documents_held_without_text_are_read_from_the_portal(monkeypatch):
    a, b, c, d = (_row("TEST-AM-790001"), _row("TEST-AM-768235", status="not_found", date=None),
                  _row("TEST-PR-796480", procedure=OTHER, kind="PR"), _row("TEST-AM-790004"))
    out, s, asked = _fill([a, b, c, d], {
        "TEST-AM-790001": {"files": {"docx": "u1", "pdf": "p0"}, "procedure_reference": OTHER},
        "TEST-AM-768235": {"files": {"pdf": "p1"}, "date": "2025-02-10", "procedure_reference": ""},
        "TEST-PR-796480": {"files": {"docx": "u3"}}}, {"u1": _cover(), "p1": b"%PDF-bytes", "u3": _cover()},
        monkeypatch, remaining=1, parents={})
    assert out == {"filled": 3, "unread": 1, "remaining": 1} and s.db.limit == 7
    # a .docx: text, and the cover's procedure on the document and on its amendments that have none
    assert a.text_body.startswith("European Parliament") and a.body_html and a.body_fetched_at
    assert a.procedure_reference == PROC and a.status == "parsed"
    (values, params), = s.db.amendment_updates                                   # one UPDATE, this document only
    assert values == {"procedure_reference": PROC} and params[0] == "PE790.001" and set(params[1:]) == {""}
    # a PDF-only document stored as 'not found': its PDF text, its date, and never a procedure repaired from a PDF
    assert b.text_body.endswith("PPP") and b.status == "unsupported" and "PDF only" in b.error_message
    assert b.document_date == dt.date(2025, 2, 10) and b.procedure_reference == ""
    assert b.doceo_url.endswith("TEST-AM-768235_EN.pdf") and a.doceo_url.endswith("TEST-AM-790001_EN.docx")
    # a procedure already stored is not rewritten here, a date already stored is kept
    assert c.procedure_reference == OTHER and c.text_body and c.document_date == dt.date(2026, 10, 1)
    # no record: nothing invented, stamped so it waits its turn
    assert d.text_body is None and d.body_fetched_at is not None and d.status == "parsed"
    assert asked["download"] == ["u1", "p1", "u3"]                                 # the PDF is not asked when the docx reads
    assert ("TEST-PR-796480", "committee-documents") in asked["detail"] and ("TEST-AM-790001", "documents") in asked["detail"]


def test_a_docx_that_does_not_read_falls_back_to_the_pdf(monkeypatch):
    row = _row("TEST-AM-790001")
    out, _, asked = _fill([row], {"TEST-AM-790001": {"files": {"docx": "u1", "pdf": "p1"}}},
                          {"u1": b"\xd0\xcf\x11\xe0legacy", "p1": b"%PDF-bytes"}, monkeypatch)
    assert out["filled"] == 1 and row.text_body.endswith("PPP") and row.status == "parsed"
    assert asked["download"] == ["u1", "p1"] and row.procedure_reference == ""


def test_a_pdf_only_document_held_without_procedure_takes_its_parents(monkeypatch):
    row = _row("TEST-AM-768235", status="not_found")
    out, s, _ = _fill([row], {"TEST-AM-768235": {"files": {"pdf": "p1"}, "parent_identifier": "TEST-PR-780000"}},
                      {"p1": b"%PDF-bytes"}, monkeypatch, parents={"TEST-PR-780000": PROC})
    assert out["filled"] == 1 and row.procedure_reference == PROC and len(s.db.amendment_updates) == 1


def test_a_document_held_with_its_text_and_no_procedure_takes_its_covers(monkeypatch):
    def held(identifier, text):
        r = _row(identifier)
        r.text_body = text
        return r
    cover = text_mod.text_from_docx(_cover())[0]
    a, b, c, d = (held("TEST-PR-796160", cover), held("TEST-AM-757208", "AM\\1297712EN.docx PE758.950 " + PROC),
                  held("TEST-PR-796161", f"{PROC}\n\n{OTHER}"), held("TEST-PR-796162", "0000/0000(INI)"))
    s, _ = _svc({}, {})
    s.db = _Session([])
    s.db.held_with_text = [a, b, c, d]
    assert s.fill_missing_procedures() == 1 and s.db.commits == 1
    assert a.procedure_reference == PROC                                           # its own cover
    assert (b.procedure_reference, c.procedure_reference, d.procedure_reference) == ("", "", "")   # a PDF, two named, a placeholder
    (values, params), = s.db.amendment_updates
    assert values == {"procedure_reference": PROC} and params[0] == "PE796.160"
    sql = s.db.procedure_sql
    assert "text_body" in sql and "procedure_reference" in sql and "status =" in sql


def test_the_fill_also_names_procedures_from_held_text(monkeypatch):
    out, s, _ = _fill([], {}, {}, monkeypatch)
    assert hasattr(s.db, "procedure_sql") and out == {"filled": 0, "unread": 0, "remaining": 0}


def test_the_documents_asked_are_those_without_text_not_asked_in_the_last_week(monkeypatch):
    _, s, _ = _fill([], {}, {}, monkeypatch)
    sql = s.db.candidate_sql
    assert "coalesce(amendment_documents.text_body" in sql and "ep_identifier IS NOT NULL" in sql
    assert "status IN" in sql and "body_fetched_at IS NULL OR amendment_documents.body_fetched_at <" in sql
    assert svc.TEXT_RETRY_DAYS == 7 and svc.NIGHTLY_TEXT_LIMIT == 150


# ---- the nightly run and what it says -------------------------------------------------

def _incremental(fill):
    s = svc.BulkAmendmentSyncService.__new__(svc.BulkAmendmentSyncService)
    closed = []

    async def _sync_all(**k):
        return svc.BulkSyncResult(documents_discovered=5, amendments_stored=9)

    async def _close():
        closed.append(1)
    s.sync_all, s.fill_missing_text = _sync_all, fill
    s.client, s.db = SimpleNamespace(close=_close), SimpleNamespace(rollback=lambda: closed.append("rollback"))
    return asyncio.run(s.sync_incremental()), closed


def test_the_nightly_run_fills_texts_after_the_sync_and_carries_the_counts():
    async def _fill(limit):
        return {"filled": 12, "unread": 2, "remaining": 30}
    r, closed = _incremental(_fill)
    assert (r.texts_filled, r.texts_unread, r.texts_remaining, r.amendments_stored) == (12, 2, 30, 9) and closed == [1]


def test_a_text_fill_that_breaks_is_said_and_does_not_lose_the_sync():
    async def _fill(limit):
        raise RuntimeError("portal down")
    r, closed = _incremental(_fill)
    assert r.amendments_stored == 9 and r.document_errors == ["text fill stopped: RuntimeError: portal down"]
    assert closed == ["rollback", 1]


def test_the_backlog_of_documents_without_text_is_written_on_the_run_row(monkeypatch):
    row = _scheduled(monkeypatch, svc.BulkSyncResult(
        documents_discovered=10, documents_listed_by_type={"AM": 8, "PR": 2}, amendments_stored=4,
        texts_filled=150, texts_unread=3, texts_remaining=391))
    assert row["status"] == "success" and row["error"].startswith(
        "391 document(s) held without their text (150 read this run, 3 not readable)")


def test_a_run_with_no_backlog_writes_no_note(monkeypatch):
    row = _scheduled(monkeypatch, svc.BulkSyncResult(
        documents_discovered=10, documents_listed_by_type={"AM": 8, "PR": 2}, texts_filled=4))
    assert row["status"] == "success" and row["error"] is None


def test_the_hand_script_reads_with_the_same_reader():
    path = pathlib.Path(svc.__file__).resolve().parents[2] / "scripts" / "fetch_amendment_document_text.py"
    spec = importlib.util.spec_from_file_location("fetch_amendment_document_text_under_test", str(path))
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    assert script._parse is text_mod.text_from_docx and script._parse_pdf is text_mod.text_from_pdf
