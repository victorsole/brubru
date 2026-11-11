"""The text of a Parliament committee document, read from its own file.

One reader for every caller: the nightly amendments sync stores the text of each document
in the same pass that parses its amendments, and scripts/fetch_amendment_document_text.py
uses the same functions for hand runs. Until 11 Nov 2026 only the script could do it and
nothing ran the script: the newest text was of 2 Oct, and /parliament/ep-documents served a
line of metadata as the body of every document stored after that.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import re
import zipfile
from typing import Optional, Tuple

# A document shorter than this is a cover with nothing behind it, not a text.
MIN_CHARS = 200

_BRACED = re.compile(r"Date&gt;.{0,160}?\{(\d{2})/(\d{2})/(\d{4})\}", re.S)
_PLAIN = re.compile(r"Date&gt;.{0,240}?\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", re.S)
# 2025/0045(COD), and the repeated-consent form 2018/0902R(NLE).
_PROCEDURE = re.compile(r"\b(\d{4}/\d{4}[A-Z]?\([A-Z]{3}\))")
# The cover: Parliament, term, committee, procedure, date, title. A procedure named further
# down is one the text talks about, not the document's own.
_COVER_CHARS = 1500

Parsed = Tuple[str, str, Optional[dt.date]]


def text_from_docx(docx: bytes) -> Optional[Parsed]:
    """(text, html, stated date) of a .docx, or None when the bytes are not one."""
    if not docx or docx[:2] != b"PK":
        return None
    try:
        xml = zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml").decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001  a zip that is not a Word document
        return None
    flat = re.sub(r"<[^>]+>", "", xml)
    stated = None
    for pat in (_BRACED, _PLAIN):
        m = pat.search(flat)
        if m:
            d, mo, y = (int(x) for x in m.groups())
            try:
                stated = dt.date(y, mo, d)
                break
            except ValueError:
                pass
    paras = []
    for chunk in re.split(r"</w:p>", xml):
        t = html.unescape(re.sub(r"<[^>]+>", "", chunk)).strip()
        # The EP template markers (<Commission>, <RefProc>, <Date> ...) are literal text
        # in the file; a reader should not see them.
        t = re.sub(r"</?[A-Za-z][A-Za-z0-9]*>", "", t).strip()
        if t:
            paras.append(t.lstrip("\ufeff"))
    body = "\n\n".join(paras)
    return body, "".join(f"<p>{html.escape(p)}</p>" for p in paras), stated


def text_from_pdf(data: bytes) -> Optional[Parsed]:
    """(text, html, stated date) of the PDF edition; the date is read off its cover."""
    if not data or data[:4] != b"%PDF":
        return None
    from pypdf import PdfReader
    try:
        pages = [(pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages]
    except Exception:  # noqa: BLE001
        return None
    paras = [re.sub(r"\s+", " ", x).strip() for x in "\n".join(pages).split("\n")]
    paras = [x for x in paras if x]
    stated = None
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", "\n".join(pages)[:3000])
    if m:
        try:
            stated = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return "\n\n".join(paras), "".join(f"<p>{html.escape(x)}</p>" for x in paras), stated


def procedure_from_cover(text: Optional[str]) -> str:
    """The procedure a document's own cover names, or '' when it names none or several.

    Only for text read from a .docx: a PDF's extracted text breaks the reference with stray
    spaces ('2024/20 19(DEC )'), and a repaired reference would be a guess.
    """
    found = {m.group(1) for m in _PROCEDURE.finditer((text or "")[:_COVER_CHARS])}
    return found.pop() if len(found) == 1 else ""
