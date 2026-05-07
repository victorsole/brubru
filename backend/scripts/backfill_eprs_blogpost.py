"""
Backfill eprs_publications.full_text from the EPRS blog post HTML.

The stored ``pdf_url`` ends in ``/document.pdf`` which 404s — that's a
template artefact from the old scraper. The blog post itself
(``epthinktank.eu/YYYY/MM/DD/<slug>/``) IS the published article and
returns 200 with full content.

Strategy: strip ``/document.pdf`` from each pdf_url, fetch the resulting
blog page, extract article body via HTML strip.

Run:
    python3.12 backend/scripts/backfill_eprs_blogpost.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_eprs_blogpost.py --apply
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

THROTTLE_S = 0.6
MIN_BODY_LEN = 500


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def derive_blog_url(pdf_url: str) -> Optional[str]:
    """epthinktank.eu/.../slug/document.pdf → epthinktank.eu/.../slug/"""
    if not pdf_url:
        return None
    if pdf_url.endswith("/document.pdf"):
        return pdf_url[: -len("document.pdf")]  # keep trailing /
    return None


def fetch_html(url: str) -> Optional[str]:
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)",
            "Accept": "text/html",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace")
    except (urllib_error.HTTPError, urllib_error.URLError):
        return None
    except Exception:
        return None


def strip_to_text(html: str) -> str:
    # Restrict to the WordPress entry-content div if present (most epthinktank.eu
    # posts wrap article body in <div class="entry-content">…</div>); fall back
    # to the whole document.
    m = re.search(r'<div\s+class="[^"]*entry-content[^"]*"[^>]*>(.*?)</article>', html, re.DOTALL | re.IGNORECASE)
    body = m.group(1) if m else html
    body = re.sub(r"<(script|style|nav|footer|header|aside|form)[^>]*>.*?</\1>", " ",
                  body, flags=re.DOTALL | re.IGNORECASE)
    body = re.sub(r"</(p|div|li|h[1-6]|article|section|tr)>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"<br\s*/?>", "\n", body, flags=re.IGNORECASE)
    body = re.sub(r"<[^>]+>", " ", body)
    body = (body.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    body = re.sub(r"[ \t]+", " ", body)
    body = re.sub(r"\n[ \t]*\n+", "\n\n", body).strip()
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
        "SELECT id::text, publication_id, pdf_url FROM eprs_publications "
        "WHERE pdf_url IS NOT NULL AND (full_text IS NULL OR LENGTH(full_text) < %s) "
        "ORDER BY publication_date DESC NULLS LAST LIMIT %s",
        (MIN_BODY_LEN, args.limit if args.limit else 100_000),
    )
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply})")

    fetched = extracted = persisted = errors = 0
    for i, (rid, pid, pdf_url) in enumerate(rows, 1):
        time.sleep(args.throttle if i > 1 else 0)
        blog_url = derive_blog_url(pdf_url)
        if not blog_url:
            errors += 1
            continue
        html = fetch_html(blog_url)
        if not html:
            errors += 1
            if i <= 5 or i % 50 == 0:
                print(f"  [{i:4}/{len(rows)}] {pid[:12]}: no HTML", flush=True)
            continue
        fetched += 1
        text = strip_to_text(html)
        if not text or len(text) < MIN_BODY_LEN:
            if i <= 5:
                print(f"  [{i:4}/{len(rows)}] {pid[:12]}: text too short ({len(text or '')}c)", flush=True)
            continue
        extracted += 1
        if args.apply:
            try:
                cur.execute(
                    "UPDATE eprs_publications SET full_text = %s, has_full_text = true, updated_at = NOW() WHERE id = %s::uuid",
                    (text[:500_000], rid),
                )
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                errors += 1
                print(f"  [{i:4}] DB error {pid}: {exc}", flush=True)
        if i % 50 == 0 or i <= 10:
            print(f"  [{i:4}/{len(rows)}] {pid[:12]} {blog_url[:55]}: text {len(text):,}{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print(f"[DONE] candidates={len(rows)} fetched={fetched} extracted={extracted} written={persisted} errors={errors}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
