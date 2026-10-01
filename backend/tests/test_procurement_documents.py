"""Procurement documents: the files on a procedure page, and their text.

API audit, 30 Sep 2026 (Victor approved "Part A"). Fixtures are real Cedefop files and
the Cedefop page that lists them (the 2009 paper-and-toners tender, 13 files), saved that
day. The legacy .doc reader was checked word for word against macOS textutil.
"""
import io
import sys
import zipfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.documents.text_extract import extract, to_html  # noqa: E402
from services.scrapers import agency_procurement as ap  # noqa: E402

DOCS = Path(__file__).resolve().parent / "fixtures" / "documents"
CEDEFOP = Path(__file__).resolve().parent / "fixtures" / "cedefop"


def _one(name):
    out = extract((DOCS / name).read_bytes(), name)
    assert len(out) == 1
    return out[0]


def test_pdf_text():
    e = _one("clarification_questions_answers.pdf")
    assert e.source == "extracted:pdf"
    assert "AO/RES/SAK/Paper-Toners/003/09" in e.text


def test_legacy_word_97_doc_text():
    e = _one("label_inner_envelope.doc")
    assert e.source == "extracted:doc"
    assert e.text.startswith("OPEN INVITATION TO TENDER")
    assert "CEDEFOP No: AO/RES/SAK/Paper-Toners/003/09" in e.text
    assert "\x00" not in e.text and "\x13" not in e.text


def test_docx_text():
    e = _one("reply_form.docx")
    assert e.source == "extracted:docx"
    assert "NP/DRS/ASAIN/GardeningServices/005/17" in e.text


def test_xls_text_keeps_sheet_names():
    e = _one("order_form.xls")
    assert e.source == "extracted:xls"
    assert e.text.startswith("## BON DE COMMANDE")
    assert "ORDER FORM" in e.text


def test_bytes_beat_the_name():
    # A Word 97 file served under .docx is still read as .doc.
    e = extract((DOCS / "label_inner_envelope.doc").read_bytes(), "renamed.docx")[0]
    assert e.source == "extracted:doc"


def test_zip_gives_one_element_per_member():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Tender/annex.doc", (DOCS / "label_inner_envelope.doc").read_bytes())
        zf.writestr("Tender/form.docx", (DOCS / "reply_form.docx").read_bytes())
        zf.writestr("__MACOSX/Tender/._form.docx", b"junk")
        zf.writestr("Tender/", b"")
    out = extract(buf.getvalue(), "tender_documents.zip")
    assert [(e.name, e.source, e.inner) for e in out] == [
        ("Tender/annex.doc", "extracted:doc", True),
        ("Tender/form.docx", "extracted:docx", True),
    ]


def test_scanned_pdf_says_so_and_invents_nothing():
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(width=595, height=842)
    buf = io.BytesIO()
    w.write(buf)
    e = extract(buf.getvalue(), "scan.pdf")[0]
    assert e.text is None and e.source == "no-text:no-text-layer"


def test_unknown_format_is_named_not_guessed():
    e = extract(b"\x89PNG\r\n\x1a\n....", "logo.png")[0]
    assert e.text is None and e.source == "unsupported:png"


def test_broken_file_does_not_raise():
    e = extract(b"%PDF-1.4 truncated", "broken.pdf")[0]
    assert e.text is None and e.source.startswith("no-text:")


def test_html_escapes_and_splits_paragraphs():
    assert to_html("a < b\n\nsecond") == "<p>a &lt; b</p><p>second</p>"
    assert to_html(None) is None


def test_cedefop_downloads_block_lists_every_file():
    docs = ap._cedefop_documents((CEDEFOP / "detail_downloads_2009.html").read_text())
    assert len(docs) == 13
    first = docs[0]
    assert first == {
        "title": "Contract Award Notice",
        "file_url": "https://www.cedefop.europa.eu/files/4442-att1-1-Contract_Award_Notice.pdf",
        "file_name": "4442-att1-1-Contract_Award_Notice.pdf", "file_format": "pdf",
        "file_size": 65714, "language": "en", "document_date": None}
    assert {d["file_format"] for d in docs} >= {"pdf", "doc", "xls"}
    assert len({d["file_url"] for d in docs}) == 13


def test_cedefop_page_without_downloads_lists_none():
    assert ap._cedefop_documents("<html><h1>x</h1><p>No files</p></html>") == []


def test_documents_routes_exist_only_where_a_writer_fills_them():
    """Audit check 15: no route reads an empty table. A body gets /documents when
    scripts/sync_procurement_documents.py has a lister for it, not before."""
    import os
    os.environ.setdefault("TESTING", "1")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from sync_procurement_documents import LISTERS
    from api.v2.funding.agency_procurement import router
    served = {p.split("/")[-3].rsplit("-", 1)[0] for p in (r.path for r in router.routes)
              if p.endswith("/{item_id}/documents")}
    assert served == set(LISTERS)
    doc_routes = [r for r in router.routes if "/documents" in r.path]
    # cedefop, echa and eige tenders + calls, eea tenders, efsa tenders; list + one doc
    assert len(doc_routes) == 16


def test_cedefop_body_lists_the_files(monkeypatch):
    from datetime import datetime, timezone
    page = (CEDEFOP / "detail_downloads_2009.html").read_text()
    monkeypatch.setattr(ap, "_get_ok", lambda url: page)
    detail = ap._cedefop_detail("https://www.cedefop.europa.eu/x")
    row = {"title": "Supply of paper", "url": "https://www.cedefop.europa.eu/x",
           "reference": "AO/RES/SAK/Paper-Toners/003/09", "closing": None, "status_raw": "Closed"}
    item = ap._cedefop_item(row, detail, datetime(2026, 9, 30, tzinfo=timezone.utc))
    assert item.body_txt.count("\nDocument: ") == 13
    assert "Document: Contract Award Notice (PDF) https://www.cedefop.europa.eu/files/" \
           "4442-att1-1-Contract_Award_Notice.pdf" in item.body_txt
    assert item.body_html.count("<li><a href=\"https://www.cedefop.europa.eu/files/") == 13


def test_the_2009_migration_stamp_is_not_a_file_date():
    """Every file on the 2009 page shows 27/11/2009, five months after closing: the
    site-migration stamp found on 720 files of 110 procedures. Real dates are kept."""
    docs = ap._cedefop_documents((CEDEFOP / "detail_downloads_2009.html").read_text())
    assert all(d["document_date"] is None for d in docs)
    page = ('<div id="group-downloads"><div class="dfu-file file-pdf">'
            '<p class="dfu-file-title">Clarification</p><div class="dfu-metadata"><span>23/08/2017</span></div>'
            '<span class="file-lang"><a href="https://www.cedefop.europa.eu/files/c.pdf" lang="en" '
            'type="application/pdf; length=10">EN</a></span></div></div>')
    assert ap._cedefop_documents(page)[0]["document_date"] == date(2017, 8, 23)


def test_zip_keeps_documents_and_drops_package_internals():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("cv/fr/Pictures/icon-home.png", b"\x89PNG....")
        zf.writestr("cv/fr/META-INF/manifest.xml", b"<m/>")
        zf.writestr("cv/fr/content.mustache", b"{{x}}")
        zf.writestr("cv/fr/layout-cache", b"....")
        zf.writestr("Annex 1/Thumbs.db", (DOCS / "label_inner_envelope.doc").read_bytes())
        zf.writestr("Drawings/plan.dwg", b"AC1015....")
        zf.writestr("Samples/export.xml", b"<record/>")
    out = extract(buf.getvalue(), "dossier.zip")
    assert [(e.name, e.source) for e in out] == [
        ("Drawings/plan.dwg", "unsupported:dwg"), ("Samples/export.xml", "unsupported:xml")]


def test_zip_of_templates_only_is_one_row_saying_so():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("cv/fr/Pictures/icon-home.png", b"\x89PNG....")
        zf.writestr("cv/fr/manifest.rdf", b"<rdf/>")
    out = extract(buf.getvalue(), "europass-odt-templates.zip")
    assert [(e.name, e.source, e.inner) for e in out] == [
        ("europass-odt-templates.zip", "no-text:no-documents-in-zip", False)]


def test_ole_file_that_is_not_word_keeps_its_own_format():
    e = extract((DOCS / "label_inner_envelope.doc").read_bytes(), "slides.ppt")[0]
    assert e.source == "unsupported:ppt"


ECHA = Path(__file__).resolve().parent / "fixtures" / "echa"
FT = Path(__file__).resolve().parent / "fixtures" / "ft"


def test_echa_detail_lists_its_files():
    detail = ap._echa_detail((ECHA / "detail_with_documents.html").read_text(errors="ignore"))
    docs = detail["documents"]
    assert len(docs) == 8
    assert docs[0]["title"] == "Contract notice"
    assert docs[0]["file_name"] == "2015-ojs105-189904-en_en.pdf"
    assert docs[0]["file_url"].startswith("https://echa.europa.eu/documents/")
    assert all("?" not in d["file_url"] for d in docs)          # the ?t= cache-buster is dropped
    assert {d["file_format"] for d in docs} == {"pdf", "doc", "xlsx"}
    assert all(d["document_date"] is None for d in docs)        # ECHA shows none


def test_echa_extensionless_link_and_generic_text():
    block = ('<a href="/documents/d/guest/questionnaire_software_development_services_en">here</a>'
             '<a href="/documents/10162/1/a.pdf/0c1f2e3d-0000-1111-2222-333344445555?t=1">Notice</a>')
    docs = ap._echa_documents(block)
    assert docs[0]["file_name"] == "questionnaire_software_development_services_en"
    assert docs[0]["file_format"] is None and docs[0]["title"] == docs[0]["file_name"]
    assert docs[1]["file_name"] == "a.pdf" and docs[1]["file_url"].endswith("a.pdf/0c1f2e3d-0000-1111-2222-333344445555")


def test_docx_without_extension_is_sniffed_from_inside():
    e = extract((DOCS / "reply_form.docx").read_bytes(), "questionnaire_en")[0]
    assert e.source == "extracted:docx"


def test_portal_documents_new_and_etender_notices():
    import json
    k = json.loads((FT / "sedia_notices_with_documents.json").read_text())
    new = ap._ft_notice_documents(k["new"])
    old = ap._ft_notice_documents(k["etender_old"])
    assert len(new) == 5 and len(old) == 4
    spec = next(d for d in new if "Tender Specifications" in d["title"])
    assert spec["file_url"] == ("https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/"
                                "opportunities/tender-details/docs/74942816-d342-424e-a7b3-7398f6f2b597-CN/"
                                "EEA.CCE.R0.26.005_Annex%20I_Tender%20Specifications_V1.pdf")
    assert spec["document_date"] == date(2026, 9, 9) and spec["language"] == "en"
    assert all("/docs/etender/5689/5689_" in d["file_url"] for d in old)
    assert {d["language"] for d in old} == {"en"}               # "ENG" normalised


def test_empty_file_says_so():
    assert extract(b"", "blank.pdf")[0].source == "no-text:empty-file"


def test_encrypted_zip_member_is_listed_not_fatal():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("open.docx", (DOCS / "reply_form.docx").read_bytes())
        zf.writestr("secret.docx", b"x" * 50)
    raw = bytearray(buf.getvalue())
    # mark the second member encrypted (general-purpose flag bit 0, local + central headers)
    name = b"secret.docx"
    for sig in (b"PK\x03\x04", b"PK\x01\x02"):
        i = raw.find(sig)
        while i != -1:
            off = 6 if sig == b"PK\x03\x04" else 8
            nlen_off = 26 if sig == b"PK\x03\x04" else 28
            head = 30 if sig == b"PK\x03\x04" else 46
            nlen = int.from_bytes(raw[i + nlen_off:i + nlen_off + 2], "little")
            if raw[i + head:i + head + nlen] == name:
                raw[i + off] |= 0x1
            i = raw.find(sig, i + 4)
    out = extract(bytes(raw), "dossier.zip")
    assert [(e.name, e.source) for e in out] == [("open.docx", "extracted:docx"),
                                                 ("secret.docx", "no-text:encrypted")]


def test_echa_body_lists_the_files(monkeypatch):
    """30 Sep 2026: the list was first added to the ECDC builder (an identical block of
    code) instead of ECHA's, and 59 ECHA bodies went without it."""
    from datetime import datetime, timezone
    monkeypatch.setattr(ap, "_ft_notice_date", lambda ident: None)
    detail = ap._echa_detail((ECHA / "detail_with_documents.html").read_text(errors="ignore"))
    row = {"title": "t", "url": "https://echa.europa.eu/-/t", "reference": "ECHA/2015/1", "kind": "Open",
           "current": False, "deadline": None}
    item = ap._echa_item(row, detail, datetime(2026, 9, 30, tzinfo=timezone.utc))
    assert item.body_txt.count("\nDocument: ") == 8
    assert "<h2>Documents</h2>" in item.body_html
