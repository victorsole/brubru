#!/usr/bin/env python3.12
"""Find the opinion PDF the RSB ingest missed, and extract its text.

GovClipping reported on 1 October 2026 that rsb-opinions returned only 500
characters of body text. Measured, body_txt is not capped: 34 of 44 rows serve
4,800 to 14,200 characters. Two separate things produced what they saw.

  * `summary` is a different field and IS stored truncated to exactly 500 characters
    on 30 rows, left by an older writer. The current ingest writes NULL there.
  * 10 rows have no full_text at all, so body_txt falls through to that summary or to
    nothing.

Nine of those ten carry no pdf_url, which read as "the Board published no PDF". It
did. The publication page for each lists several PDFs -- the report, the executive
summary, and the Board's own opinion -- and the ingest took none of them. The opinion
is the one whose link filename or label marks it as the opinion, not the first PDF on
the page: taking the first would store the Commission's report as the Board's opinion,
which is a different document by a different author.

A page where no link identifies itself as the opinion is left alone. Storing the
wrong PDF would be worse than storing none, because its text would then be served as
the Board's opinion and quoted as such.

    python3.12 scripts/recover_rsb_opinion_pdfs.py --rehearse
    python3.12 scripts/recover_rsb_opinion_pdfs.py --apply
"""
from __future__ import annotations

import argparse
import html as _html
import importlib.util
import pathlib
import re
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
_REPO_ROOT = str(BACKEND.parent)
for p in (_REPO_ROOT, str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402


def _browser():
    """The Playwright fetcher, imported by path (the scrapers package is not a module
    path these scripts can rely on)."""
    spec = importlib.util.spec_from_file_location(
        "waf_browser_fetcher", str(BACKEND / "services" / "scrapers" / "waf_browser_fetcher.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules["waf_browser_fetcher"] = m
    spec.loader.exec_module(m)
    return m


PICK = text(
    """
    SELECT opinion_reference, source_url
      FROM rsb_opinions
     WHERE coalesce(full_text, '') = '' AND coalesce(pdf_url, '') = ''
       AND coalesce(source_url, '') <> ''
     ORDER BY opinion_reference
    """
)

SET_PDF = text(
    "UPDATE rsb_opinions SET pdf_url = :u, last_updated = now() "
    "WHERE opinion_reference = :ref AND coalesce(pdf_url, '') = ''"
)

# The Board's own opinion, not the report or the executive summary that sit beside it.
_OPINION_FILE = re.compile(r"opinion", re.I)
_LINK = re.compile(r'href="([^"]*\.pdf[^"]*)"', re.I)


def _opinion_pdf(page_html: str) -> str | None:
    """The link that identifies itself as the opinion, or None."""
    seen: list[str] = []
    for m in _LINK.finditer(page_html):
        href = _html.unescape(m.group(1))
        if href.startswith("/"):
            href = "https://commission.europa.eu" + href
        if href not in seen:
            seen.append(href)
    for href in seen:
        # The filename is the reliable marker: ...?filename=opinion_horizon_2020.pdf
        tail = href.split("filename=")[-1]
        if _OPINION_FILE.search(tail):
            return href
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    engine = create_engine(m.group(1).strip())

    with engine.connect() as conn:
        rows = list(conn.execute(PICK))
    print(f"[INFO] opinions with no text and no PDF: {len(rows)}")
    if args.rehearse:
        for r in rows[:10]:
            print(f"   would read {r.source_url}")
        print("[INFO] rehearsal only, nothing written")
        return 0

    browser = _browser()
    found = 0
    none_identified = 0
    failed = 0
    for r in rows:
        try:
            res = browser.fetch_one(r.source_url)
            page = res.html or ""
        except Exception as exc:
            print(f"  [ERROR] {r.opinion_reference}: {type(exc).__name__} {exc}")
            failed += 1
            continue
        if not page:
            print(f"  [ERROR] {r.opinion_reference}: empty page, not an absence of PDFs")
            failed += 1
            continue
        href = _opinion_pdf(page)
        if not href:
            # No link calls itself the opinion. Left alone deliberately.
            none_identified += 1
            print(f"  [SKIP]  {r.opinion_reference}: no link identifies itself as the opinion")
            continue
        with engine.begin() as conn:
            conn.execute(SET_PDF, {"u": href, "ref": r.opinion_reference})
        found += 1
        print(f"  [OK]    {r.opinion_reference} -> {href[-58:]}")

    print(f"\n[INFO] pdf_url recovered : {found}")
    print(f"[INFO] no opinion link   : {none_identified}  (left empty, never guessed)")
    print(f"[INFO] fetch failed      : {failed}  (retry; not an absence)")
    if rows and found == 0 and failed >= len(rows):
        print("[ERROR] every page failed to load; this run proves nothing")
        return 1
    print("[OK] run complete. Extract the text next with backfill_pdf_text_generic.py --table rsb_opinions")
    return 0


if __name__ == "__main__":
    sys.exit(main())
