"""ECDC procedure files are listed from the page and served under /ecdc-tenders/{id}/documents
(16 Oct 2026).

API audit, step 2 (ECDC): 141 of 174 procedures are ex-ante publicity notices whose text is
a PDF behind a "Download" link; 86 bodies pointed at one and no writer read it, so the API
served 300-character stubs. The fixture is ECDC's page for NP/2016/RMC/7913, saved 16 Oct.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "ecdc"


def test_download_block_is_read_with_name_size_and_language():
    docs = ap._ecdc_documents((FIX / "detail_np2016_files.html").read_text())
    assert len(docs) == 1
    d = docs[0]
    assert d["file_name"] == "Ex_ante_Publicity_NP_7913_final.pdf"
    assert d["title"] == "Ex_ante_Publicity_NP_7913_final.pdf"
    assert d["file_url"].startswith("https://www.ecdc.europa.eu/sites/default/files/")
    assert d["file_format"] == "pdf" and d["language"] == "en"
    assert d["file_size"] == int(253.54 * 1024)
    assert d["document_date"] is None


def test_a_page_without_downloads_lists_none():
    page = ('<html><body><article><h1>ECDC/2026/OP/0028</h1><ul></ul><p>See the portal: '
            '<a href="https://ec.europa.eu/info/funding-tenders/x">notice</a></p></article></body></html>')
    assert ap._ecdc_documents(page) == []


def test_two_files_are_two_entries_and_a_repeated_link_one():
    block = ('<div><p class="fw-medium mb-0">{name}</p><small class="text-muted">English ({size} KB - PDF)'
             '</small><p><a class="btn" href="/sites/default/files/{name}">Download</a></p></div>')
    page = ("<html><body><article><h1>t</h1><ul></ul>" + block.format(name="a.pdf", size="10")
            + block.format(name="b.docx", size="20").replace("PDF", "DOCX")
            + block.format(name="a.pdf", size="10") + "</article></body></html>")
    docs = ap._ecdc_documents(page)
    assert [d["file_name"] for d in docs] == ["a.pdf", "b.docx"]
    assert docs[1]["file_format"] == "docx" and docs[1]["file_size"] == 20 * 1024


def test_ecdc_has_a_documents_lister_and_route():
    import os
    os.environ.setdefault("TESTING", "1")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from sync_procurement_documents import LISTERS
    from api.v2.funding.agency_procurement import router
    assert "ecdc" in LISTERS
    assert "/ecdc-tenders/{item_id}/documents" in {r.path for r in router.routes}
