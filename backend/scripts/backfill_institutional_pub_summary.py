"""
Backfill ``institutional_publications.summary`` (and ``html_content`` when
worth it) from the ``url`` column. 114 rows missing summary; 140 missing
html_content. Same generic HTML scrape pattern used by rss_entries.

Skips rows whose URL is an external link roll (bit.ly, etc.) — for the
``ec_jrc_ghslsys`` source the rows are link-list stubs and have no body
at the linked target. We only attempt rows whose URL hostname matches an
EU institutional domain.

Run:
    python3.12 backend/scripts/backfill_institutional_pub_summary.py
    python3.12 backend/scripts/backfill_institutional_pub_summary.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
THROTTLE_S = 0.7
MIN_BODY_LEN = 500

EU_INST_HOSTS = (
    "europa.eu",
    "europarl.europa.eu",
    "consilium.europa.eu",
    "ec.europa.eu",
    "eea.europa.eu",
    "acer.europa.eu",
    "esma.europa.eu",
    "eba.europa.eu",
    "eiopa.europa.eu",
    "ema.europa.eu",
    "efsa.europa.eu",
    "ecdc.europa.eu",
    "frontex.europa.eu",
    "europol.europa.eu",
    "edps.europa.eu",
    "edpb.europa.eu",
    "esa.europa.eu",
    "euspa.europa.eu",
    "osha.europa.eu",
    "cedefop.europa.eu",
    "eurofound.europa.eu",
)


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def is_eu_url(url: str) -> bool:
    try:
        host = urllib_parse.urlparse(url).hostname or ""
    except Exception:
        return False
    return any(host == h or host.endswith("." + h) for h in EU_INST_HOSTS)


def fetch_html(url: str) -> Tuple[Optional[str], Optional[str]]:
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en",
        },
    )
    try:
        with urllib_request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8", errors="replace"), None
    except urllib_error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib_error.URLError as e:
        return None, f"URL {e.reason}"
    except Exception as e:
        return None, str(e)[:80]


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
    text = re.sub(r"\n[ \t]*\n+", "\n\n", text).strip()
    return text


def extract_summary(text: str, max_chars: int = 2000) -> str:
    """First substantive paragraph chunk (~2k chars)."""
    if not text:
        return ""
    return text[:max_chars]


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
        "SELECT id::text, source_slug, url FROM institutional_publications "
        "WHERE url IS NOT NULL AND url LIKE 'http%%' "
        "AND (LENGTH(summary) < %s OR summary IS NULL) "
        "AND (LENGTH(html_content) < %s OR html_content IS NULL) "
        "ORDER BY published_date DESC NULLS LAST LIMIT %s",
        (200, MIN_BODY_LEN, args.limit if args.limit else 100_000),
    )
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply})")

    fetched = extracted = persisted = errors = skipped = 0
    for i, (rid, source, url) in enumerate(rows, 1):
        if not is_eu_url(url):
            skipped += 1
            continue
        time.sleep(args.throttle if i > 1 else 0)
        html, err = fetch_html(url)
        if html is None:
            errors += 1
            if i <= 5 or i % 50 == 0:
                print(f"  [{i:4}/{len(rows)}] {source} {url[:50]}: {err}", flush=True)
            continue
        fetched += 1
        text = strip_to_text(html)
        if not text or len(text) < MIN_BODY_LEN:
            if i <= 5:
                print(f"  [{i:4}/{len(rows)}] {source}: text too short ({len(text)}c)", flush=True)
            continue
        extracted += 1
        summary = extract_summary(text).replace("\x00", "")
        html_save = html[:1_000_000].replace("\x00", "")
        if args.apply:
            try:
                # Selection already restricts to rows where summary < 200 AND
                # html_content < 500, so unconditional write is safe.
                cur.execute(
                    "UPDATE institutional_publications SET "
                    "summary = %s, html_content = %s "
                    "WHERE id = %s::uuid",
                    (summary, html_save, rid),
                )
                conn.commit()
                persisted += 1
            except Exception as exc:
                conn.rollback()
                errors += 1
                print(f"  [{i:4}] DB error {rid}: {exc}", flush=True)
        if i % 50 == 0 or i <= 5:
            print(f"  [{i:4}/{len(rows)}] {source} {url[:50]}: text {len(text):,}{' [WRITTEN]' if args.apply else ' [DRY]'}", flush=True)

    print()
    print(f"[DONE] candidates={len(rows)} fetched={fetched} extracted={extracted} written={persisted} skipped_external={skipped} errors={errors}{' (DRY)' if not args.apply else ''}")
    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
