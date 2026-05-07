"""
Backfill rss_entries.content from each entry's `link`.

Fetches the article HTML, strips boilerplate (nav/header/footer/scripts),
collapses whitespace. 563 rows missing content; many sources are
paywalled (EU Observer, Euractiv, Politico) so expect significant failure
rate — that's fine.

Run:
    python3.12 backend/scripts/backfill_rss_entries_content.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_rss_entries_content.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
THROTTLE_S = 0.7
MIN_BODY_LEN = 500


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_html(url: str, timeout: int = 20) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (html, content_type, error_msg)."""
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en,fr,nl,es,ca,it",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="replace"), r.headers.get("Content-Type", ""), None
    except urllib_error.HTTPError as e:
        return None, None, f"HTTP {e.code}"
    except urllib_error.URLError as e:
        return None, None, f"URL {e.reason}"
    except Exception as e:
        return None, None, str(e)[:80]


def strip_to_text(html: str) -> str:
    text = re.sub(r"<(script|style|nav|footer|header|aside|form)[^>]*>.*?</\1>", " ",
                  html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"</(p|div|li|h[1-6]|article|section|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'"))
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text)
    return text.strip()


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
        "SELECT id::text, link FROM rss_entries "
        "WHERE link IS NOT NULL AND (content IS NULL OR LENGTH(content) < %s) "
        "ORDER BY published_at DESC NULLS LAST LIMIT %s",
        (MIN_BODY_LEN, args.limit if args.limit else 100_000),
    )
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply})")

    fetched = extracted = persisted = errors = 0
    for i, (rid, link) in enumerate(rows, 1):
        time.sleep(args.throttle if i > 1 else 0)
        html, ct, err = fetch_html(link)
        if html is None:
            errors += 1
            if i % 50 == 0 or i <= 5:
                print(f"  [{i:4}/{len(rows)}] {link[:60]}: {err}", flush=True)
            continue
        fetched += 1
        text = strip_to_text(html)
        if not text or len(text) < MIN_BODY_LEN:
            if i <= 5:
                print(f"  [{i:4}/{len(rows)}] {link[:60]}: text too short ({len(text)}c)", flush=True)
            continue
        extracted += 1
        if args.apply:
            try:
                cur.execute(
                    "UPDATE rss_entries SET content = %s, content_html = %s, "
                    "has_full_content = true, content_length = %s, updated_at = NOW() "
                    "WHERE id = %s::uuid",
                    (text[:500_000], html[:1_000_000], len(text), rid),
                )
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                errors += 1
                print(f"  [{i:4}] DB error {rid}: {exc}", flush=True)
                continue
        if i % 50 == 0 or i <= 5:
            print(f"  [{i:4}/{len(rows)}] {link[:50]:50}: text {len(text):,}{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print(f"[DONE] candidates={len(rows)} fetched={fetched} extracted={extracted} written={persisted} errors={errors}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
