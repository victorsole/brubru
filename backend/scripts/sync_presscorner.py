#!/usr/bin/env python3.12
"""Every Commission press-corner item into eu_news_items, from its own API (15 Oct 2026).

Why: /api/v2/news/all held 285 Commission press releases since 15 July 2024 and about 190
items from the press corner at all, picked up only where a DG's RSS feed repeated one.
The press corner publishes 15 to 25 items a day (press releases, statements, speeches,
questions and answers, daily news) and its search API pages them newest first:
GET /commission/presscorner/api/search?language=en&pagesize=100&pagenumber=N gives each
item's refCode ("IP/26/2165"), docutype, eventDate, title and leadText. GovClipping's
backfill asks for everything since 15 July 2024.

Each item becomes one row keyed by its detail page, the key the DG feeds already use, so
an item held from a feed is never duplicated (ON CONFLICT DO NOTHING keeps the held row).
A press release (IP) is kind press_release; the other types are news. The row starts with
the standard placeholder body; the news text job (fetch_institutional_news_bodies.py,
warm tier) reads the article, which the press corner also serves as a print PDF.

    python3.12 scripts/sync_presscorner.py                       # dry run, last 3 days
    python3.12 scripts/sync_presscorner.py --since 2024-07-15 --apply   # backfill
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import create_engine, text  # noqa: E402

from services.news.body_composer import compose_news_body  # noqa: E402

API = "https://ec.europa.eu/commission/presscorner/api/search?language=en&pagesize={size}&pagenumber={page}"
DETAIL = "https://ec.europa.eu/commission/presscorner/detail/en/{slug}"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/141.0 Safari/537.36", "Accept": "application/json"}
# The press corner's document types. Only a press release is kind press_release.
KIND = {"IP": ("press", "press_release"), "STATEMENT": ("statement", "news"),
        "SPEECH": ("speech", "news")}

# A DG's own site carries some press releases under its own address (competition-policy,
# energy, trade): the same item with the same title on the same day is not added again.
INSERT = text("""
    INSERT INTO eu_news_items (entry_key, title, summary, news_date, institution, item_type,
                               news_kind, source_key, source_url, body_txt, body_html, body_source)
    SELECT :key, :title, :summary, :day, 'COMMISSION', :item_type, :kind, 'PRESSCORNER', :key,
           :txt, :html, :src
     WHERE NOT EXISTS (SELECT 1 FROM eu_news_items e
                        WHERE e.institution = 'COMMISSION' AND e.news_date = :day
                          AND lower(btrim(e.title)) = lower(:title))
    ON CONFLICT (entry_key) DO NOTHING
    RETURNING id""")


def slug_of(ref: str) -> str | None:
    """'IP/26/2165' -> 'ip_26_2165'; None for anything not of that shape."""
    parts = (ref or "").strip().split("/")
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return None
    return "_".join(p.lower() for p in parts)


def to_row(item: dict) -> dict | None:
    slug = slug_of(item.get("refCode"))
    title = " ".join((item.get("title") or "").split())
    if not slug or not title or not item.get("eventDate"):
        return None
    day = date.fromisoformat(item["eventDate"][:10])
    code = ((item.get("docutype") or {}).get("code") or "").upper()
    item_type, kind = KIND.get(code, ("news", "news"))
    summary = " ".join((item.get("leadText") or "").split()) or None
    url = DETAIL.format(slug=slug)
    txt, html, src = compose_news_body(title, summary, "COMMISSION", day, url)
    return {"key": url, "title": title, "summary": summary, "day": day, "item_type": item_type,
            "kind": kind, "txt": txt, "html": html, "src": src}


def fetch_page(page: int, size: int, attempts: int = 4) -> list[dict]:
    for n in range(attempts):
        try:
            req = urllib.request.Request(API.format(size=size, page=page), headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r).get("docuLanguageListResources") or []
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if n == attempts - 1:
                raise
            time.sleep(5 * (n + 1))
    return []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", type=date.fromisoformat, default=date.today() - timedelta(days=3))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-pages", type=int, default=300)
    ap.add_argument("--page-size", type=int, default=100)
    ap.add_argument("--pause", type=float, default=0.5)
    args = ap.parse_args(argv)

    rows, seen, oldest = [], set(), None
    for page in range(1, args.max_pages + 1):
        items = fetch_page(page, args.page_size)
        if not items:
            break
        for it in items:
            row = to_row(it)
            if row and row["key"] not in seen and row["day"] >= args.since:
                seen.add(row["key"])
                rows.append(row)
        oldest = min(date.fromisoformat(i["eventDate"][:10]) for i in items if i.get("eventDate"))
        if oldest < args.since:
            break
        time.sleep(args.pause)
    else:
        print(f"[SYNC_STATUS] degraded: stopped at --max-pages {args.max_pages} before {args.since}")
    kinds = {}
    for r in rows:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"[INFO] press corner since {args.since}: {len(rows)} item(s) {kinds}; oldest page date {oldest}")
    if not rows:
        print("[ERROR] the press corner gave no item in the window")
        return 1
    if not args.apply:
        for r in rows[:5]:
            print(f"   {r['day']} {r['kind']:13} {r['title'][:80]}")
        print("[INFO] dry run: nothing written")
        return 0
    url = os.environ.get("DATABASE_URL", "")
    engine = create_engine(url.replace("postgres://", "postgresql://", 1), pool_pre_ping=True)
    added = 0
    with engine.begin() as conn:
        for r in rows:
            added += conn.execute(INSERT, r).rowcount
    print(f"[OK] added {added}; {len(rows) - added} already held (kept as they were)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
