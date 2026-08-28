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


def coverage(conn, min_rows: int = 10) -> list[dict]:
    rows = conn.execute(text("""
        SELECT body_code, item_type, count(*) AS n, count(body_txt) AS txt,
               count(body_html) AS html
        FROM economy_items
        GROUP BY 1, 2
        HAVING count(*) >= :min
        ORDER BY count(*) - count(body_txt) DESC
    """), {"min": min_rows}).fetchall()
    out = []
    for r in rows:
        if r.item_type in NO_BODY_TYPES:
            continue
        out.append({
            "slice": f"{r.body_code}/{r.item_type}",
            "rows": r.n, "with_txt": r.txt, "with_html": r.html,
            "pct": round(100.0 * r.txt / r.n, 1),
            "empty": r.txt == 0,
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
        total, txt = conn.execute(text(
            "SELECT count(*), count(body_txt) FROM economy_items")).fetchone()

    empty = [c for c in cov if c["empty"]]
    if args.json:
        print(json.dumps({"overall_pct": round(100.0 * txt / total, 2),
                          "slices": len(cov), "empty_slices": len(empty),
                          "coverage": cov[:args.worst]}, default=str))
        return 1 if empty else 0

    print(f"economy_items overall: {txt}/{total} = {100.0*txt/total:.1f}% hold a body\n")
    print(f"{'slice':32} {'rows':>7} {'bodies':>7} {'%':>7}")
    for c in cov[:args.worst]:
        mark = "  <-- NONE" if c["empty"] else ""
        print(f"{c['slice']:32} {c['rows']:7} {c['with_txt']:7} {c['pct']:6.1f}%{mark}")
    print(f"\n{len(empty)} slice(s) hold rows and not one body: "
          + ", ".join(c["slice"] for c in empty))
    print("These are SCRAPER gaps, not API defects: the endpoint would serve the "
          "text the moment it is fetched.")
    return 1 if empty else 0


if __name__ == "__main__":
    sys.exit(main())
