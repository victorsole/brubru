#!/usr/bin/env python3.12
"""How much of the API's text actually exists, per corpus slice.

Why this exists
---------------
On 28 August 2026 a partner reported that `/api/v2/news/all` returned
`body_txt: null` on every item. Days earlier I had audited that endpoint and
called it fine, because I checked that the FIELD was present, not that a VALUE
ever came back.

Sweeping all 451 param-free v2 list endpoints then found 350 returning a null
body on every item. Most were an API defect -- the handler read the body and
discarded it -- and those are fixed, with `include_body` and a regression test.

What is left is the other half, and it cannot be fixed in the API at all: slices
where the scraper stored a title and a URL and never fetched the document. EFSA
publications hold 1 body in 189. SRB publications, 5 in 255. Eleven slices hold
none at all. The endpoints are correct; the corpus is thin.

That distinction is the whole point of this script. A null body is either
    - a defect  (the data exists and the API hides it)      -> test_v2_body_contract
    - a gap     (the data was never fetched)                -> here
and the two look identical from outside. Reporting coverage per slice makes the
second kind countable instead of invisible, and gives a scraper fix a number to
move.

Exit codes:
    0  no slice is fully empty (a partially-covered slice is reported, not failed)
    1  at least one slice holds rows and not one body

Usage:
    python3.12 scripts/api_body_coverage.py
    python3.12 scripts/api_body_coverage.py --json
    python3.12 scripts/api_body_coverage.py --min-rows 20
"""
import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")

# Item types that are reference data rather than documents: a "topic" is a
# taxonomy label and a "dataset" is a numeric series, so neither has a body to
# be missing. Counting them as gaps would make the report permanently red.
NO_BODY_TYPES = {"topic", "dataset", "country", "product", "programme", "account"}


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


# A body this short is a headline and a teaser, not a document. Measured 25 Sep 2026
# across the corpora GovClipping reads: real press releases average 5,519 characters and
# reach 12,475, while every one of the 11,387 eu_news_items rows is composed from the
# title and the RSS summary and averages 379.
THIN_BODY_CHARS = 1200

# Item types that ARE a document and therefore owe a full body. Everything else in
# economy_items is a register or data row -- a trademark, a financial instrument, a
# funding recipient, a tariff code -- where a composed one-line description is the right
# content and a "thin body" is not a gap. Reporting those as gaps would drown the real
# ones: 68 thin slices drops to the handful that actually owe text.
DOCUMENT_TYPES = {
    "news", "publication", "press_release", "opinion", "report", "study",
    "consultation", "speech", "statement", "legal", "case_law", "tender",
}


def coverage(conn, min_rows: int = 10) -> list[dict]:
    """Per slice: how many rows hold a body, and how many hold a WHOLE one.

    Counting non-null was the blind spot that let this sit. The docstring above already
    warns about checking that the field exists rather than that a value comes back; the
    same mistake repeats one level up, because a value came back and it still is not the
    document. GovClipping needs the whole text in body_txt and the whole HTML in
    body_html, so the number that matters is how many bodies are of document LENGTH.
    """
    rows = conn.execute(text("""
        SELECT body_code, item_type, count(*) AS n, count(body_txt) AS txt,
               count(body_html) AS html,
               count(*) FILTER (WHERE length(body_txt) >= :thin) AS full_txt,
               coalesce(round(avg(nullif(length(body_txt), 0))), 0) AS avg_len
        FROM economy_items
        GROUP BY 1, 2
        HAVING count(*) >= :min
        ORDER BY count(*) - count(*) FILTER (WHERE length(body_txt) >= :thin) DESC
    """), {"min": min_rows, "thin": THIN_BODY_CHARS}).fetchall()
    out = []
    for r in rows:
        if r.item_type in NO_BODY_TYPES:
            continue
        out.append({
            "slice": f"{r.body_code}/{r.item_type}",
            "rows": r.n, "with_txt": r.txt, "with_html": r.html,
            "full_txt": r.full_txt, "avg_len": int(r.avg_len),
            "pct": round(100.0 * r.txt / r.n, 1),
            "pct_full": round(100.0 * r.full_txt / r.n, 1),
            "empty": r.txt == 0,
            "thin": (r.txt > 0 and r.full_txt == 0
                     and r.item_type in DOCUMENT_TYPES),
            "is_document": r.item_type in DOCUMENT_TYPES,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-rows", type=int, default=10,
                    help="Ignore slices smaller than this (default 10)")
    ap.add_argument("--worst", type=int, default=25, help="How many rows to print")
    args = ap.parse_args()

    with _engine().connect() as conn:
        cov = coverage(conn, args.min_rows)
        total, txt, full = conn.execute(text(
            "SELECT count(*), count(body_txt), "
            "count(*) FILTER (WHERE length(body_txt) >= :thin) FROM economy_items"),
            {"thin": THIN_BODY_CHARS}).fetchone()

    empty = [c for c in cov if c["empty"]]
    thin = [c for c in cov if c["thin"]]
    if args.json:
        print(json.dumps({"overall_pct": round(100.0 * txt / total, 2),
                          "overall_full_pct": round(100.0 * full / total, 2),
                          "thin_body_chars": THIN_BODY_CHARS,
                          "slices": len(cov), "empty_slices": len(empty),
                          "thin_slices": len(thin),
                          "coverage": cov[:args.worst]}, default=str))
        return 1 if (empty or thin) else 0

    docs = [c for c in cov if c["is_document"]]
    doc_rows = sum(c["rows"] for c in docs)
    doc_full = sum(c["full_txt"] for c in docs)
    print(f"economy_items: {txt}/{total} = {100.0*txt/total:.1f}% hold a body, but only "
          f"{full}/{total} = {100.0*full/total:.1f}% hold a WHOLE one "
          f"(>= {THIN_BODY_CHARS} chars)")
    if doc_rows:
        print(f"of the DOCUMENT slices (news, publications, opinions, reports and the "
              f"like): {doc_full}/{doc_rows} = {100.0*doc_full/doc_rows:.1f}% whole\n")
    print(f"{'slice':32} {'rows':>7} {'bodies':>7} {'whole':>7} {'avg len':>8}")
    for c in cov[:args.worst]:
        mark = "  <-- NONE" if c["empty"] else ("  <-- all thin" if c["thin"] else "")
        print(f"{c['slice']:32} {c['rows']:7} {c['with_txt']:7} {c['full_txt']:7} "
              f"{c['avg_len']:8}{mark}")
    if empty:
        print(f"\n{len(empty)} slice(s) hold rows and not one body: "
              + ", ".join(c["slice"] for c in empty))
    if thin:
        print(f"\n{len(thin)} slice(s) hold a body for every row and not one of document "
              f"length: " + ", ".join(c["slice"] for c in thin))
    print("\nBoth are SCRAPER gaps, not API defects. A body assembled from a title and a "
          "summary is not a body: GovClipping needs the whole text in body_txt and the "
          "whole HTML in body_html (25 Sep 2026).")
    return 1 if (empty or thin) else 0


if __name__ == "__main__":
    sys.exit(main())
