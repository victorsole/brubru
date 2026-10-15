#!/usr/bin/env python3.12
"""Authors, policy areas and the English PDF of each EPRS publication, from its Think Tank record (15 Oct 2026).

Why: /api/v2/parliament/eprs served authors empty on 870 of 871 Think Tank publications,
policy_areas empty on the same 870 and pdf_url null on most of them. The sync reads the
portal's RSS, which carries title, date, type and summary only, and stored `authors=[]`
and `pdf_url=None` on every new row; nothing read the record page, which lists them:

    <h5 class="es_title-h5 ...">Author</h5> ... <span class="t-x">VALLEDOR DE VICENTE Victoria</span>
    <h5 class="es_title-h5 ...">Policy area</h5> ... <span class="t-x">Public Health</span>
    href=".../RegData/etudes/ATAG/2026/795728/ECTI_ATA(2026)795728_EN.pdf"

A blog post (epthinktank.eu) links its Think Tank record; that record is read the same way.
Only an empty field is written, so a value another writer set is never replaced, and
last_updated moves only when something was written.

    python3.12 scripts/enrich_eprs_records.py --limit 5            # dry run
    python3.12 scripts/enrich_eprs_records.py --apply --max-seconds 900
"""
from __future__ import annotations

import argparse
import html as html_lib
import os
import re
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import create_engine, text  # noqa: E402

HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/141.0 Safari/537.36",
           "Accept": "text/html,*/*"}
_SECTION = re.compile(r'<h5 class="es_title-h5[^"]*"[^>]*>\s*([^<]+?)\s*</h5>(.*?)(?=<h5 class="es_title-h5|</main>)',
                      re.S)
_VALUE = re.compile(r'<span class="t-x">\s*([^<]+?)\s*</span>')
_RECORD = re.compile(r'href="(https?://www\.europarl\.europa\.eu/thinktank/[a-z]{2}/document/[^"]+)"', re.I)
# A record in one language links its PDF; a record in several offers them in a language
# picker (<option data-auto-open-link="..._EN.pdf">), with no href at all.
_PDF = re.compile(r'(?:href|data-auto-open-link)="([^"]*RegData/etudes/[^"]+\.pdf)"', re.I)

TODO = text("""
    SELECT id, html_url FROM eprs_publications
     WHERE html_url IS NOT NULL
       AND (html_url LIKE 'https://www.europarl.europa.eu/thinktank/%' OR html_url LIKE 'https://epthinktank.eu/%')
       AND (pdf_url IS NULL OR coalesce(cardinality(policy_areas), 0) = 0
            -- A record that names no author (an external study) would be read again every run:
            -- after its first two weeks only a missing PDF or policy area brings it back.
            OR (coalesce(cardinality(authors), 0) = 0
                AND (:everything OR first_seen > now() - interval '14 days')))
     ORDER BY publication_date DESC NULLS LAST""")
STORE = text("""
    UPDATE eprs_publications SET
        authors = CASE WHEN coalesce(cardinality(authors), 0) = 0 AND cardinality(CAST(:authors AS text[])) > 0
                       THEN CAST(:authors AS text[]) ELSE authors END,
        policy_areas = CASE WHEN coalesce(cardinality(policy_areas), 0) = 0
                                 AND cardinality(CAST(:areas AS text[])) > 0
                            THEN CAST(:areas AS text[]) ELSE policy_areas END,
        pdf_url = coalesce(pdf_url, :pdf),
        last_updated = now()
     WHERE id = :id
       AND ((coalesce(cardinality(authors), 0) = 0 AND cardinality(CAST(:authors AS text[])) > 0)
            OR (coalesce(cardinality(policy_areas), 0) = 0 AND cardinality(CAST(:areas AS text[])) > 0)
            OR (pdf_url IS NULL AND :pdf IS NOT NULL))""")


def _read(url: str, attempts: int = 3) -> str | None:
    for n in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(3 * (n + 1))
    return None


def parse_record(page: str) -> dict:
    """{'authors': [...], 'areas': [...], 'pdf': url|None} from a Think Tank record page."""
    sections: dict[str, list[str]] = {}
    for label, body in _SECTION.findall(page):
        values = [" ".join(html_lib.unescape(v).split()) for v in _VALUE.findall(body)]
        sections.setdefault(label.strip().lower(), []).extend(v for v in values if v)
    authors = [a for k, v in sections.items() if k in ("author", "authors", "external author",
                                                          "external authors") for a in v]
    areas = [a for k, v in sections.items() if k in ("policy area", "policy areas") for a in v]
    pdfs = _PDF.findall(page)
    english = [p for p in pdfs if p.upper().endswith("_EN.PDF")]
    pdf = (english or pdfs or [None])[0]
    if pdf and pdf.startswith("/"):
        pdf = "https://www.europarl.europa.eu" + pdf
    return {"authors": list(dict.fromkeys(authors)), "areas": list(dict.fromkeys(areas)), "pdf": pdf}


def read_one(url: str) -> dict | None:
    page = _read(url)
    if page is None or "<title>Error 404" in page:
        return None
    if "epthinktank.eu/" in url:
        record = _RECORD.search(page)
        if not record:
            return None
        page = _read(html_lib.unescape(record.group(1)))
        if page is None or "<title>Error 404" in page:
            return None
    return parse_record(page)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--max-seconds", type=float, default=0)
    ap.add_argument("--all", action="store_true", help="also re-read old records that named no author")
    args = ap.parse_args(argv)
    deadline = time.monotonic() + args.max_seconds if args.max_seconds else None

    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    with engine.connect() as c:
        rows = c.execute(TODO, {"everything": args.all}).fetchall()
    if args.limit:
        rows = rows[:args.limit]
    print(f"[INFO] {len(rows)} EPRS publication(s) missing authors, policy areas or PDF")
    written = unread = 0
    batch = max(args.workers * 5, 10)
    with ThreadPoolExecutor(args.workers) as pool:
        for i in range(0, len(rows), batch):
            if deadline and time.monotonic() > deadline:
                print(f"[INFO] time budget reached; {len(rows) - i} left for the next run")
                break
            chunk = rows[i:i + batch]
            for row, found in zip(chunk, pool.map(lambda r: read_one(r.html_url), chunk)):
                if not found:
                    unread += 1
                    continue
                if not args.apply:
                    if written < 5:
                        print(f"  {row.html_url}\n    {found}")
                    written += 1
                    continue
                with engine.begin() as c:
                    written += c.execute(STORE, {"id": row.id, **found}).rowcount
    print(f"[DONE] {written} row(s) {'filled' if args.apply else 'would be filled (DRY RUN)'}; "
          f"{unread} record(s) unreadable")
    if rows and unread == len(rows):
        print("[ERROR] no Think Tank record could be read")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
