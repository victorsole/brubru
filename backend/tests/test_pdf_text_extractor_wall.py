"""meetdocs PDFs sit behind a WAF (202, 0 bytes): extraction must get through it.

Live test (network + Scrape.do credit + real DB). On 25 Sep 2026 1,017 of 2,120
cache rows held the WAF's empty body and every new document extracted to nothing.
"""
import os

import pytest
from sqlalchemy import text

from core.database import SessionLocal
from services.analysis.pdf_text_extractor import _fetch_pdf_bytes, get_pdf_text

PUBLISHED = ("https://www.europarl.europa.eu/meetdocs/2024_2029/plmrep/COMMITTEES/"
             "ENVI/AM/2025/10-20/1327340EN.pdf")
NOT_YET_PUBLISHED = ("https://www.europarl.europa.eu/meetdocs/2024_2029/plmrep/COMMITTEES/"
                     "CJ80/PR/2026/09-28/1350557EN.pdf")

pytestmark = pytest.mark.skipif(not os.environ.get("SCRAPEDO_API_KEY"),
                                reason="needs SCRAPEDO_API_KEY")


def test_published_pdf_comes_through_the_wall():
    raw = _fetch_pdf_bytes(PUBLISHED)
    assert raw is not None and raw[:4] == b"%PDF"


def test_unpublished_document_is_none_and_not_cached_empty():
    db = SessionLocal()
    try:
        db.execute(text("DELETE FROM emeeting_doc_text_cache WHERE pdf_url = :u AND coalesce(char_count,0) = 0"),
                   {"u": NOT_YET_PUBLISHED})
        db.commit()
        assert get_pdf_text(db, NOT_YET_PUBLISHED) is None
        n = db.execute(text("SELECT count(*) FROM emeeting_doc_text_cache WHERE pdf_url = :u"),
                       {"u": NOT_YET_PUBLISHED}).scalar()
        assert n == 0
    finally:
        db.close()
