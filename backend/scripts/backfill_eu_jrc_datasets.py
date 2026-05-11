"""
Backfill ``eu_jrc_datasets`` from data.jrc.ec.europa.eu via Playwright.

Site is a Blazor Server SPA behind Imperva. All /api/* and machine-
readable distribution formats (RDF/XML/TTL/JSON-LD) are WAF-blocked
(HTTP 200 with 245-byte "Request Rejected" body). Only the rendered HTML
is accessible.

This script:
  1. Loads the catalogue list page (10 datasets per page).
  2. Extracts dataset UUID + title from every visible card.
  3. Clicks the next pagination button (Blazor SPA — no URL state).
  4. UPSERTs each (uuid, title, public_url) row.
  5. Stops when the click no longer reveals new UUIDs (end of list).

Body content (description, distributions, publisher, dates) is left for
a slower per-dataset detail scrape (deferred — 1000+ datasets at ~5s
each = ~1.5 hours, run as a separate cron-style job).

Run:
    python3.12 backend/scripts/backfill_eu_jrc_datasets.py            # dry-run
    python3.12 backend/scripts/backfill_eu_jrc_datasets.py --apply
    python3.12 backend/scripts/backfill_eu_jrc_datasets.py --apply --max-pages 200
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _specialised_helpers import ChunkedDb  # noqa: E402

BASE = "https://data.jrc.ec.europa.eu"
LIST_URL = f"{BASE}/dataset"
PUBLIC_DATASET_URL_TPL = f"{BASE}/dataset/{{uuid}}"

UPSERT_SQL = """
INSERT INTO eu_jrc_datasets (uuid, title, public_url, listing_page, fetched_at, updated_at)
VALUES (%(uuid)s, %(title)s, %(public_url)s, %(listing_page)s, NOW(), NOW())
ON CONFLICT (uuid) DO UPDATE SET
    title = COALESCE(EXCLUDED.title, eu_jrc_datasets.title),
    public_url = EXCLUDED.public_url,
    listing_page = COALESCE(EXCLUDED.listing_page, eu_jrc_datasets.listing_page),
    fetched_at = NOW(),
    updated_at = NOW();
"""


def scrape_listing(dry_run: bool, max_pages: int = 200) -> None:
    from playwright.sync_api import sync_playwright  # local import

    db = ChunkedDb() if not dry_run else None
    counts = {"upserted": 0, "pages": 0, "duplicates": 0}
    seen: set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800},
        )
        page = ctx.new_page()
        # Blazor never settles networkidle — use domcontentloaded then wait for cards
        print(f"[INFO] Loading {LIST_URL}...", flush=True)
        page.goto(LIST_URL, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_selector('a[href*="/dataset/"]', timeout=30000)
        page.wait_for_timeout(3000)

        current_page = 1
        while current_page <= max_pages:
            # Extract uuid + title pairs from current page
            items = page.evaluate("""() => {
              return Array.from(document.querySelectorAll('a[href*="/dataset/"]')).map(a => {
                const href = a.getAttribute('href') || '';
                const m = href.match(/\\/dataset\\/([a-f0-9-]{20,})/i);
                return m ? {uuid: m[1], title: (a.textContent || '').trim().slice(0, 500), href} : null;
              }).filter(Boolean);
            }""")
            new_this_page = 0
            for item in items:
                uuid = item["uuid"]
                if uuid in seen:
                    continue
                seen.add(uuid)
                new_this_page += 1
                params = {
                    "uuid": uuid,
                    "title": item["title"] or None,
                    "public_url": PUBLIC_DATASET_URL_TPL.format(uuid=uuid),
                    "listing_page": current_page,
                }
                if dry_run:
                    if counts["upserted"] < 5:
                        print(f"  [p{current_page} #{counts['upserted']+1}] {uuid} | {item['title'][:60]}", flush=True)
                    counts["upserted"] += 1
                else:
                    try:
                        db.execute(UPSERT_SQL, params)
                        counts["upserted"] += 1
                    except Exception as exc:
                        print(f"  [p{current_page}] DB err {uuid}: {exc!s}", flush=True)

            counts["pages"] = current_page
            if not dry_run and counts["upserted"] % 100 < 10:
                db.commit()
            if new_this_page == 0:
                # No new UUIDs on this page → end of list (or duplicate page)
                counts["duplicates"] += 1
                if counts["duplicates"] >= 2:
                    print(f"[INFO] No new UUIDs on page {current_page} — stopping.", flush=True)
                    break
            else:
                counts["duplicates"] = 0
            if current_page % 5 == 0 or current_page <= 3:
                print(f"  [page {current_page:3}] +{new_this_page:2} new, total={counts['upserted']:,}", flush=True)

            # Snapshot one UUID before clicking — wait until first card UUID changes.
            sentinel = items[0]["uuid"] if items else None
            clicked = False
            for sel in [
                f"a[aria-label='Go to page {current_page + 1}']",
                "a[aria-label='Go to next page']",
                "button[aria-label='Next']",
                "a[aria-label='Next']",
            ]:
                try:
                    btn = page.locator(sel)
                    if btn.count() > 0:
                        btn.first.click(timeout=8000)
                        clicked = True
                        break
                except Exception:
                    continue
            if not clicked:
                print(f"[INFO] No next-page button at page {current_page} — stopping.", flush=True)
                break
            # Wait until the first card's UUID changes from sentinel (Blazor SignalR roundtrip)
            try:
                page.wait_for_function(
                    """([sentinel]) => {
                        const a = document.querySelector('a[href*=\"/dataset/\"]');
                        if (!a) return false;
                        const m = (a.getAttribute('href') || '').match(/\\/dataset\\/([a-f0-9-]{20,})/i);
                        return m && m[1] !== sentinel;
                    }""",
                    arg=[sentinel],
                    timeout=15000,
                )
            except Exception:
                # Even if sentinel didn't change, dwell a bit longer and try the next loop
                page.wait_for_timeout(2500)
            current_page += 1

        if not dry_run:
            db.commit()
            db.close()
        browser.close()

    print()
    print(f"[DONE] {counts}{' (DRY)' if dry_run else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-pages", type=int, default=200,
                    help="Cap pagination depth (each page = 10 datasets).")
    args = ap.parse_args()
    scrape_listing(dry_run=not args.apply, max_pages=args.max_pages)


if __name__ == "__main__":
    main()
