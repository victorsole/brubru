"""An Office file is read as a document, never stored as its bytes.

18 Oct 2026: 84 economy publications (ESMA 60 reply forms, EBA 16 and AMLA 7 spreadsheets,
EISMEA 1 slide deck) held "PK... [Content_Types].xml ..." as their body. The economy detail
fetch let anything whose content type mentioned html or xml through as a page, and a .docx is
served as application/vnd.openxmlformats-officedocument.wordprocessingml.document, which
contains "xml". The file is now judged by its first bytes and parsed with the parser the body
fetcher already had (moved to economy_common, one copy for both paths); the sync refuses a
body that is a file's bytes.
"""
import importlib
import io
import pathlib
import sys
import zipfile
from types import SimpleNamespace

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
common = importlib.import_module("services.scrapers.economy_common")

PARA = "ESMA invites comments on all matters in this Consultation Paper and on the questions in Annex 1."


def _docx(paragraphs) -> bytes:
    body = "".join(f'<w:p><w:r><w:t>{p}</w:t></w:r></w:p>' for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/'
                                        f'wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


DOCX = _docx(["Reply Form", "to the CCP collateral tokenisation"] + [PARA] * 4)
URL = "https://www.esma.europa.eu/sites/default/files/2026-10/ESMA91-Reply_Form.docx"
OOXML = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _resp(raw, ctype):
    return SimpleNamespace(url=URL, content=raw, text=raw.decode("utf-8", "replace"), headers={"content-type": ctype})


def test_a_docx_served_with_an_xml_type_is_read_as_a_document(monkeypatch):
    monkeypatch.setattr(common, "stored_complete", lambda url: False)
    monkeypatch.setattr(common, "http_get", lambda url: _resp(DOCX, OOXML))
    txt, html, kind = common.fetch_detail(URL)
    assert kind == "docx" and txt.startswith("Reply Form\nto the CCP collateral tokenisation")
    assert not common.looks_like_file_bytes(txt) and URL in html


def test_a_pdf_served_as_octet_stream_is_read_as_a_pdf(monkeypatch):
    monkeypatch.setattr(common, "stored_complete", lambda url: False)
    monkeypatch.setattr(common, "http_get", lambda url: _resp(b"%PDF-1.7 fake", "application/octet-stream"))
    monkeypatch.setattr(common, "extract_pdf", lambda raw: "Annual report text. " * 20)
    txt, _, kind = common.fetch_detail("https://agency.europa.eu/document/download/123")
    assert kind == "pdf" and txt.startswith("Annual report")


def test_file_bytes_are_recognised():
    assert common.looks_like_file_bytes(DOCX.decode("utf-8", "replace"))
    assert common.looks_like_file_bytes("%PDF-1.7\n%�� 1 0 obj")
    assert not common.looks_like_file_bytes("PKK Party congress opens in Ankara. " * 10)
    assert not common.looks_like_file_bytes(PARA)


def test_the_sync_sends_file_bytes_as_null():
    sync = importlib.import_module("scripts.sync_economy")
    it = SimpleNamespace(body_txt=DOCX.decode("utf-8", "replace"), body_html="<p>x</p>")
    sync._drop_furniture_bodies(it)
    assert it.body_txt is None and it.body_html is None


def test_the_body_fetcher_uses_the_same_parser():
    fetcher = importlib.import_module("scripts.fetch_institutional_news_bodies")
    assert fetcher._office_text(DOCX) == common.extract_office(DOCX)
