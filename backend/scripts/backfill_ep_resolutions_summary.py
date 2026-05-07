"""
Backfill ep_resolutions.summary by scraping the OEIL document-summary page.

Strategy:
  1. From oeil_url, fetch the procedure-file HTML.
  2. Find the latest "Summary" link (pattern:
     ``/oeil/en/document-summary?id=<NUMERIC>``).
  3. Fetch that page; strip HTML to plain text; extract the substantive
     summary paragraphs (heuristic: text starting from "European Parliament"
     or "The Committee on" up to the next section break).
  4. Write to ``summary``.

72 ep_resolutions rows have ``oeil_url`` set; ``text_url`` is null on all.
This is the only source we have for the resolution text without
re-implementing the doceo scrape pipeline.

Run:
    python3.12 backend/scripts/backfill_ep_resolutions_summary.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_ep_resolutions_summary.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
THROTTLE_S = 0.7
MIN_BODY_LEN = 300  # OEIL summaries can be short; lower than the default 500


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_html(url: str) -> Optional[str]:
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)",
            "Accept": "text/html",
            "Accept-Language": "en",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except (urllib_error.HTTPError, urllib_error.URLError):
        return None
    except Exception:
        return None


_SUMMARY_LINK_RE = re.compile(r'href="(/oeil/en/document-summary\?id=\d+)"')


def find_summary_url(procedure_html: str) -> Optional[str]:
    """OEIL procedure file lists 1+ summary links in the Documentation Gateway.
    Pick the LAST one (= most recent vote, e.g. plenary adoption).
    """
    matches = _SUMMARY_LINK_RE.findall(procedure_html or "")
    if not matches:
        return None
    return "https://oeil.europarl.europa.eu" + matches[-1]


def strip_to_text(html: str) -> str:
    body = re.sub(r"<(script|style|nav|footer|header|aside|form)[^>]*>.*?</\1>", " ",
                  html, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r"</(p|div|li|h[1-6]|article|section)>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"<[^>]+>", " ", body)
    body = (body.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n[ \t]*\n+", "\n\n", body).strip()
    # Trim header boilerplate before "European Parliament" / "The Committee" /
    # "The European" — the substantive summary starts there.
    for marker in ("European Parliament adopted", "The European Parliament", "The Committee on"):
        idx = body.find(marker)
        if idx > 0:
            body = body[idx:]
            break
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--throttle", type=float, default=THROTTLE_S)
    args = ap.parse_args()

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)
    conn = psycopg2.connect(db)
    cur = conn.cursor()
    cur.execute(
        "SELECT id::text, procedure_ref, oeil_url FROM ep_resolutions "
        "WHERE oeil_url IS NOT NULL AND (summary IS NULL OR LENGTH(summary) < %s) "
        "ORDER BY adoption_date DESC NULLS LAST LIMIT %s",
        (MIN_BODY_LEN, args.limit if args.limit else 100_000),
    )
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply})")

    fetched = extracted = persisted = errors = 0
    for i, (rid, ref, oeil) in enumerate(rows, 1):
        time.sleep(args.throttle if i > 1 else 0)
        proc_html = fetch_html(oeil)
        if not proc_html:
            errors += 1
            if i <= 5 or i % 20 == 0:
                print(f"  [{i:3}/{len(rows)}] {ref}: OEIL fetch failed", flush=True)
            continue
        sum_url = find_summary_url(proc_html)
        if not sum_url:
            if i <= 5:
                print(f"  [{i:3}/{len(rows)}] {ref}: no summary link in OEIL page", flush=True)
            continue
        time.sleep(args.throttle)
        sum_html = fetch_html(sum_url)
        if not sum_html:
            errors += 1
            if i <= 5:
                print(f"  [{i:3}/{len(rows)}] {ref}: summary fetch failed for {sum_url}", flush=True)
            continue
        fetched += 1
        text = strip_to_text(sum_html)
        if not text or len(text) < MIN_BODY_LEN:
            if i <= 5:
                print(f"  [{i:3}/{len(rows)}] {ref}: text too short ({len(text or '')}c)", flush=True)
            continue
        extracted += 1
        if args.apply:
            try:
                cur.execute(
                    "UPDATE ep_resolutions SET summary = %s, updated_at = NOW() WHERE id = %s::uuid",
                    (text[:500_000], rid),
                )
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                errors += 1
                print(f"  [{i:3}] DB error {ref}: {exc}", flush=True)
        if i % 20 == 0 or i <= 5:
            print(f"  [{i:3}/{len(rows)}] {ref}: text {len(text):,}{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print(f"[DONE] candidates={len(rows)} fetched={fetched} extracted={extracted} written={persisted} errors={errors}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
