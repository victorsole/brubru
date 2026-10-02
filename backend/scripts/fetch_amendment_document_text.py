#!/usr/bin/env python3.12
"""Read each amendment document's own text from its doceo .docx.

/api/v2/parliament/ep-documents served no body on any of its 1,945 rows, and
amendment_documents.text_body is empty on all 1,370 of its rows. The older fetcher
(backfill_amendment_documents_body.py) records that doceo's WAF answers a plain GET with
HTTP 202 and a challenge page, and gives up. A real browser passes it: the browser fetcher
returned the .docx for all 22 documents tried while dating amendments, so this uses it.

The text is the .docx body (word/document.xml), paragraph by paragraph. The EP's template
markers appear in it as literal escaped text (`<Commission>`, `<Date>`), so they are
dropped from the stored text rather than shown to a reader.

Documents with no stated date are also dated here from their own `<Date>` field, never from
file metadata (dcterms:created was eight days off on the one document checked).

    python3.12 scripts/fetch_amendment_document_text.py --limit 10 --rehearse
    python3.12 scripts/fetch_amendment_document_text.py --limit 1400 --apply
"""
from __future__ import annotations

import argparse, datetime as dt, html, importlib.util, io, pathlib, re, sys, time, zipfile
from collections import Counter

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)
from sqlalchemy import create_engine, text  # noqa: E402

MIN_CHARS = 200
BATCH = 15

PICK = text("""SELECT id, doceo_url, document_date FROM amendment_documents
                WHERE coalesce(text_body,'')='' AND coalesce(doceo_url,'')<>''
                ORDER BY document_date DESC NULLS LAST, id LIMIT :lim""")
STORE = text("""UPDATE amendment_documents
                   SET text_body=:t, body_html=:h, body_fetched_at=now(),
                       document_date=coalesce(document_date,:d)
                 WHERE id=:i AND coalesce(text_body,'')=''""")
GAP = text("SELECT count(*) FROM amendment_documents WHERE coalesce(text_body,'')=''")
UNDATED = text("SELECT count(*) FROM amendment_documents WHERE document_date IS NULL")

_BRACED = re.compile(r"Date&gt;.{0,160}?\{(\d{2})/(\d{2})/(\d{4})\}", re.S)
_PLAIN = re.compile(r"Date&gt;.{0,240}?\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", re.S)


def _browser():
    spec = importlib.util.spec_from_file_location(
        "waf_browser_fetcher", str(BACKEND / "services" / "scrapers" / "waf_browser_fetcher.py"))
    m = importlib.util.module_from_spec(spec); sys.modules["waf_browser_fetcher"] = m
    spec.loader.exec_module(m)
    return m


def _db() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL missing")
    return m.group(1).strip()


def _parse(docx: bytes):
    """(text, html, stated_date) from a .docx, or None when it is not one."""
    if not docx or docx[:2] != b"PK":
        return None
    try:
        xml = zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return None
    flat = re.sub(r"<[^>]+>", "", xml)
    stated = None
    for pat in (_BRACED, _PLAIN):
        m = pat.search(flat)
        if m:
            d, mo, y = (int(x) for x in m.groups())
            try:
                stated = dt.date(y, mo, d); break
            except ValueError:
                pass
    paras = []
    for chunk in re.split(r"</w:p>", xml):
        t = html.unescape(re.sub(r"<[^>]+>", "", chunk)).strip()
        # drop the EP template markers (<Commission>, <RefProc>, <Date> ...) and braces tags
        t = re.sub(r"</?[A-Za-z][A-Za-z0-9]*>", "", t).strip()
        if t:
            paras.append(t)
    body = "\n\n".join(paras)
    return body, "".join(f"<p>{html.escape(p)}</p>" for p in paras), stated


def _parse_pdf(data: bytes):
    """(text, html, stated_date) from the PDF edition; the date is read off its cover."""
    if not data or data[:4] != b"%PDF":
        return None
    from pypdf import PdfReader
    try:
        pages = [(pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages]
    except Exception:
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true"); g.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=30)
    a = ap.parse_args()
    eng = create_engine(_db(), pool_pre_ping=True)
    with eng.connect() as c:
        before = c.execute(GAP).scalar_one(); ud0 = c.execute(UNDATED).scalar_one()
        rows = list(c.execute(PICK, {"lim": a.limit}))
    print(f"[INFO] amendment documents with no text: {before} | undated: {ud0} | this run: {len(rows)}")
    if a.rehearse:
        print("[INFO] rehearsal only"); return 0
    br = _browser(); stored = chars = 0; why: Counter = Counter()
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        try:
            got = br.fetch_bytes_isolated([r.doceo_url for r in chunk], timeout_s=900)
        except Exception as e:  # noqa: BLE001
            why[type(e).__name__] += len(chunk); continue
        # Older documents (2016-2019) serve a legacy binary .doc under the .docx name
        # (REGI-PR-587442: OLE header, not a zip), which read as "empty body" for 37
        # rows. The same document is published as PDF; read that instead.
        # Some have no .docx at all (BUDG-PR-770003: 404) but do have the PDF.
        legacy = [r for r in chunk if (got.get(r.doceo_url, (None, b"", None))[1] or b"")[:2] != b"PK"]
        pdfs = {}
        if legacy:
            try:
                pdfs = br.fetch_bytes_isolated([r.doceo_url.replace("_EN.docx", "_EN.pdf") for r in legacy], timeout_s=900)
            except Exception:  # noqa: BLE001
                pdfs = {}
        for r in chunk:
            status, body, err = got.get(r.doceo_url, (None, b"", "missing"))
            parsed = _parse(body)
            if parsed is None and r in legacy:
                pst, pbody, _ = pdfs.get(r.doceo_url.replace("_EN.docx", "_EN.pdf"), (None, b"", None))
                parsed = _parse_pdf(pbody) if pst == 200 else None
            if parsed is None:
                why[f"no_docx_{status}"] += 1; continue          # blocked or not a .docx: retry, not absence
            txt, h, stated = parsed
            if len(txt) < MIN_CHARS:
                why["too_short"] += 1; continue
            for n in range(4):
                try:
                    with eng.begin() as c:
                        c.execute(STORE, {"t": txt, "h": h, "d": stated, "i": r.id}); break
                except Exception:  # noqa: BLE001
                    eng.dispose(); time.sleep(2 * (n + 1))
            stored += 1; chars += len(txt)
        print(f"   ...{min(i + BATCH, len(rows))}/{len(rows)} stored={stored} {dict(why)}", flush=True)
    with eng.connect() as c:
        after = c.execute(GAP).scalar_one(); ud1 = c.execute(UNDATED).scalar_one()
    print(f"[INFO] stored {stored}" + (f" (avg {chars // stored} chars)" if stored else "")
          + f" | not stored {dict(why)} | no-text {before} -> {after} | undated {ud0} -> {ud1}")
    if rows and stored == 0:
        print("[ERROR] nothing stored; this run proves nothing"); return 1
    print("[OK] every body came from the document's own .docx, or its PDF edition"); return 0


if __name__ == "__main__":
    sys.exit(main())
