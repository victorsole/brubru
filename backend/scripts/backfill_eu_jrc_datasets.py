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
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
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


def _to_iso(value):
    if not value:
        return None
    s = str(value).split(".")[0]
    return s


_HTML_TEMPLATE = """<article>
<section><h2>{title}</h2><p>{desc}</p></section>
{kw_section}
{dist_section}
</article>"""


def backfill_via_dpe(dry_run: bool, limit_total: int = 0) -> None:
    """Federated path: data.europa.eu publishes the full JRC catalogue
    (~4,215 datasets) as DCAT-AP — REST-accessible without WAF.

    Two-phase:
      1. GET /api/hub/repo/catalogues/jrc/datasets?limit=N&offset=N — list of
         dataset URIs (http://data.europa.eu/88u/dataset/<uuid>).
      2. For each, GET /api/hub/search/datasets/<uuid> — full DCAT-AP.
    Body fields composed from title + description + keywords + distributions.
    """
    import json
    import urllib.request as ureq
    from html import escape as html_escape

    UA = "Brubru/1.0 backfill"
    UA_HEADERS = {"User-Agent": UA, "Accept": "application/json"}
    CAT_URL = "https://data.europa.eu/api/hub/repo/catalogues/jrc/datasets"
    DETAIL_URL = "https://data.europa.eu/api/hub/search/datasets/{uuid}"
    PUBLIC_TPL = "https://data.jrc.ec.europa.eu/dataset/{uuid}"

    def fetch_json(url):
        req = ureq.Request(url, headers=UA_HEADERS)
        with ureq.urlopen(req, timeout=60) as r:
            return json.loads(r.read())

    # Phase 1: page through dataset URIs
    print("[INFO] Phase 1 — enumerating JRC catalogue via data.europa.eu...", flush=True)
    uuids: list[str] = []
    offset = 0
    PAGE = 500
    while True:
        try:
            chunk = fetch_json(f"{CAT_URL}?limit={PAGE}&offset={offset}")
        except Exception as exc:
            print(f"[warn]   offset={offset}: {exc!s}", flush=True)
            break
        if not chunk:
            break
        for uri in chunk:
            # URI format: http://data.europa.eu/88u/dataset/<uuid>
            uuid = uri.rsplit("/", 1)[-1]
            if len(uuid) >= 20:
                uuids.append(uuid)
        print(f"[INFO]   offset={offset:5d}: +{len(chunk)} (running {len(uuids)})", flush=True)
        if len(chunk) < PAGE:
            break
        offset += PAGE
        if limit_total and len(uuids) >= limit_total:
            uuids = uuids[:limit_total]
            break

    print(f"[INFO] {len(uuids):,} JRC datasets discovered", flush=True)
    if dry_run:
        uuids = uuids[:5]

    # Phase 2: per-dataset detail
    db = ChunkedDb() if not dry_run else None
    counts = {"upserted": 0, "with_body": 0, "errors": 0}

    for i, uuid in enumerate(uuids, 1):
        try:
            payload = fetch_json(DETAIL_URL.format(uuid=uuid))
        except Exception as exc:
            counts["errors"] += 1
            if i <= 5 or i % 200 == 0:
                print(f"  [{i:5}] {uuid}: detail err {exc!s}", flush=True)
            continue

        r = payload.get("result", {})
        title = (r.get("title", {}) or {}).get("en")
        desc = (r.get("description", {}) or {}).get("en")
        publisher = (r.get("publisher", {}) or {}).get("name") if isinstance(r.get("publisher"), dict) else None
        keywords = []
        for kw in (r.get("keywords") or []):
            label = kw.get("label") if isinstance(kw, dict) else kw
            if label:
                keywords.append(label)
        issued = _to_iso(r.get("issued"))
        modified = _to_iso(r.get("modified"))
        dists = r.get("distributions") or []

        # Compose body from structured fields
        body_text_parts = []
        if title: body_text_parts.append(f"Title\n\n{title}")
        if desc: body_text_parts.append(f"Description\n\n{desc}")
        if publisher: body_text_parts.append(f"Publisher\n\n{publisher}")
        if keywords: body_text_parts.append(f"Keywords\n\n{', '.join(keywords)}")
        if dists:
            dist_lines = []
            for d_ in dists[:30]:
                fmt = (d_.get("format", {}) or {}).get("id") if isinstance(d_.get("format"), dict) else d_.get("format")
                urls = d_.get("access_url") or d_.get("download_url") or []
                if isinstance(urls, list) and urls:
                    dist_lines.append(f"  - {fmt or '?'}: {urls[0]}")
            if dist_lines:
                body_text_parts.append("Distributions\n\n" + "\n".join(dist_lines))
        body_text = "\n\n".join(body_text_parts) if body_text_parts else None
        body_html = None
        if body_text and len(body_text) >= 200:
            # Quick HTML wrapping
            html_parts = []
            for part in body_text_parts:
                head, _, rest = part.partition("\n\n")
                html_parts.append(f"<section><h2>{html_escape(head)}</h2><p>{html_escape(rest).replace(chr(10), '<br/>')}</p></section>")
            body_html = f"<article>{''.join(html_parts)}</article>"

        has_body = bool(body_text and len(body_text) >= 200)
        if has_body:
            counts["with_body"] += 1

        params = {
            "uuid": uuid,
            "title": title,
            "description": desc,
            "publisher": publisher,
            "keywords": keywords,
            "issued": issued,
            "modified": modified,
            "distributions_json": json.dumps(dists) if dists else None,
            "public_url": PUBLIC_TPL.format(uuid=uuid),
            "has_body": has_body,
            "body_html": body_html,
            "body_text": body_text,
            "body_source": "dpe_composed" if has_body else None,
        }

        if dry_run:
            print(f"  [{i:3}] {uuid} | {(title or '')[:60]} | body={'+' if has_body else '—'} | dists={len(dists)}", flush=True)
            continue

        try:
            db.execute(
                """
                INSERT INTO eu_jrc_datasets
                    (uuid, title, description, publisher, keywords, issued, modified,
                     distributions, public_url, has_body, body_html, body_text, body_source,
                     fetched_at, updated_at)
                VALUES (%(uuid)s, %(title)s, %(description)s, %(publisher)s, %(keywords)s,
                        %(issued)s, %(modified)s,
                        %(distributions_json)s::jsonb, %(public_url)s,
                        %(has_body)s, %(body_html)s, %(body_text)s, %(body_source)s,
                        NOW(), NOW())
                ON CONFLICT (uuid) DO UPDATE SET
                    title = COALESCE(EXCLUDED.title, eu_jrc_datasets.title),
                    description = EXCLUDED.description,
                    publisher = EXCLUDED.publisher,
                    keywords = EXCLUDED.keywords,
                    issued = EXCLUDED.issued,
                    modified = EXCLUDED.modified,
                    distributions = EXCLUDED.distributions,
                    public_url = EXCLUDED.public_url,
                    has_body = EXCLUDED.has_body,
                    body_html = EXCLUDED.body_html,
                    body_text = EXCLUDED.body_text,
                    body_source = EXCLUDED.body_source,
                    fetched_at = NOW(),
                    updated_at = NOW();
                """,
                params,
            )
            counts["upserted"] += 1
            if counts["upserted"] % 200 == 0:
                db.commit()
                print(f"  [{i:5}/{len(uuids)}] {uuid} | upserted={counts['upserted']:,} "
                      f"with_body={counts['with_body']:,}", flush=True)
        except Exception as exc:
            db.rollback()
            counts["errors"] += 1
            print(f"  [{i:5}] DB err {uuid}: {exc!s}", flush=True)

    if not dry_run:
        db.commit()
        db.close()
    print()
    print(f"[DONE] {counts}{' (DRY)' if dry_run else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--source", choices=("playwright", "dpe"), default="dpe",
                    help="'dpe' = data.europa.eu federation (REST, fast, full). "
                         "'playwright' = scrape data.jrc.ec.europa.eu (slow, partial).")
    ap.add_argument("--max-pages", type=int, default=200,
                    help="Playwright-mode only — cap pagination depth.")
    ap.add_argument("--limit", type=int, default=0,
                    help="DPE-mode only — cap total datasets fetched (0 = all).")
    args = ap.parse_args()

    if args.source == "playwright":
        scrape_listing(dry_run=not args.apply, max_pages=args.max_pages)
    else:
        backfill_via_dpe(dry_run=not args.apply, limit_total=args.limit)


if __name__ == "__main__":
    main()
