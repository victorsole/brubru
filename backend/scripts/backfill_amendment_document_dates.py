#!/usr/bin/env python3.12
"""Read the date each amendment document states, and date its amendments from it.

/api/v2/parliament/amendments serves document_date null on 3,406 of 64,077 rows.
Those collapse to 22 source documents, each a .docx on doceo, and no date for them
exists anywhere locally: 0 of the undated rows have a dated sibling sharing their PE
reference, and 0 appear dated in amendment_documents.

The date is READ from inside the document, from the `<Date>{DD/MM/YYYY}</Date>` field
the EP puts in its header, never from file metadata. That distinction is the whole
point: ITRE-AM-788800 states 12.5.2026 in its Date field while the .docx reports
dcterms:created 2026-05-20, eight days later. Taking the file timestamp would have
written the wrong date onto 277 amendments, and it would have looked fine.

doceo sits behind a WAF, so the .docx is fetched through Playwright. A blocked fetch
is retried, never written, and a document whose Date field cannot be read is left
undated rather than dated from anything else.

    python3.12 scripts/backfill_amendment_document_dates.py --rehearse
    python3.12 scripts/backfill_amendment_document_dates.py --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import io
import pathlib
import re
import sys
import zipfile
from collections import Counter

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402

# The EP header field, and note what it is NOT: `<Date>` is not XML markup in these
# documents. It is literal text the EP's template emits, so inside word/document.xml it
# appears ESCAPED, as `&lt;Date&gt;`, in its own <w:t> run. Measured on
# ITRE-AM-788800: "<Date>" occurs 0 times, "&lt;Date&gt;" once.
#
# A first version searched for a real `<Date>` tag, matched nothing in all 22 documents
# and reported "no Date field" -- which read as "the EP states no date" while the date
# sat in plain sight. The run guard caught it by refusing to call 0 of 22 a success.
#
# Both forms follow the marker: the braces hold DD/MM/YYYY, the visible text D.M.YYYY.
# The braced one is unambiguous, so it is tried first.
_BRACED = re.compile(r"Date&gt;.{0,160}?\{(\d{2})/(\d{2})/(\d{4})\}", re.S)
_PLAIN = re.compile(r"Date&gt;.{0,240}?\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b", re.S)

DOCS = text(
    """
    SELECT pe_reference, min(source_url) AS source_url, count(*) AS n
      FROM mep_amendments
     WHERE document_date IS NULL AND coalesce(source_url, '') <> ''
     GROUP BY pe_reference
     ORDER BY pe_reference
    """
)

SET_DATE = text(
    """
    UPDATE mep_amendments SET document_date = :d, updated_at = now()
     WHERE pe_reference = :pe AND document_date IS NULL
    """
)

GAP = text("SELECT count(*) FROM mep_amendments WHERE document_date IS NULL")


def _browser():
    spec = importlib.util.spec_from_file_location(
        "waf_browser_fetcher", str(BACKEND / "services" / "scrapers" / "waf_browser_fetcher.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["waf_browser_fetcher"] = m
    spec.loader.exec_module(m)
    return m


def _database_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


def _stated_date(docx: bytes) -> dt.date | None:
    """The date the document states in its own Date field, or None."""
    if not docx or docx[:2] != b"PK":
        return None
    try:
        xml = zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml").decode("utf-8", "ignore")
    except Exception:
        return None
    # Strip the real XML markup. That leaves the escaped `&lt;Date&gt;` literal intact
    # and rejoins the value, which Word keeps in a separate <w:t> run from the marker.
    flat = re.sub(r"<[^>]+>", "", xml)
    for pattern in (_BRACED, _PLAIN):
        m = pattern.search(flat)
        if m:
            d, mth, y = (int(x) for x in m.groups())
            try:
                return dt.date(y, mth, d)
            except ValueError:
                continue
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(_database_url())
    with engine.connect() as conn:
        docs = list(conn.execute(DOCS))
        before = conn.execute(GAP).scalar_one()
    print(f"[INFO] undated amendments : {before}")
    print(f"[INFO] source documents   : {len(docs)}")
    if args.rehearse:
        for d in docs[:6]:
            print(f"   {d.pe_reference:<14} {d.n:>4} amendments  {d.source_url[-44:]}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    browser = _browser()
    dated = unread = 0
    rows_dated = 0
    why: Counter = Counter()
    for d in docs:
        try:
            got = browser.fetch_bytes_isolated([d.source_url], timeout_s=150)
            status, body, err = got[d.source_url]
        except Exception as e:
            unread += 1; why[type(e).__name__] += 1; continue
        if not body:
            unread += 1; why[f"blocked_{status}"] += 1; continue
        stated = _stated_date(body)
        if stated is None:
            # No Date field we can read. Left undated rather than dated from the file's
            # own timestamp, which is a different thing and demonstrably wrong here.
            unread += 1; why["no Date field"] += 1
            print(f"   [SKIP] {d.pe_reference}: no readable Date field")
            continue
        with engine.begin() as conn:
            n = conn.execute(SET_DATE, {"d": stated, "pe": d.pe_reference}).rowcount
        dated += 1; rows_dated += n
        print(f"   [OK]   {d.pe_reference} -> {stated}  ({n} amendments)")

    with engine.connect() as conn:
        after = conn.execute(GAP).scalar_one()
    print(f"\n[INFO] documents dated : {dated} of {len(docs)}")
    print(f"[INFO] amendments dated: {rows_dated}")
    print(f"[INFO] not read        : {unread}  {dict(why)}")
    print(f"[INFO] gap             : {before} -> {after}")
    if docs and dated == 0:
        print("[ERROR] not one document was read; this run proves nothing")
        return 1
    print("[OK] every date was read from the document's own Date field")
    return 0


if __name__ == "__main__":
    sys.exit(main())
