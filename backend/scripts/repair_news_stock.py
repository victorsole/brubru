#!/usr/bin/env python3.12
"""Repair eu_news_items rows that cannot be dated because they are not what they claim.

Why (measured 11 September 2026)
--------------------------------
Of 473 undated rows, some were never dateable news items at all:

* **Navigation stored as news.** "Visit the Press corner" (the Press Corner home
  page), "Press releases" (a faceted listing link on the R&I site) and the EUAA's own
  listing page ("Press Releases and News"). The parsers now skip them.
* **Registry pages stored as stories.** Four geographical-indication register entries
  ("Bordeaux", "Alho da Graciosa PGI") came in on 1 June from the AGRI stories feed.
  Today's feed no longer emits them.
* **The same article stored twice.** The Ombudsman declares `<base href="/">`, so its
  links were stored as `/en/news-document/en/<id>`; 9 of those have an absolute twin,
  identical in every content field. ENISA writes `href="/news/slug "`, so 3 articles
  exist with and without a trailing space. The CoR has two Drupal `-0` alias copies
  of articles also stored under their real slug; the `-0` pages 404.

What it does
------------
* deletes the junk rows and the non-canonical twin of each duplicate, first copying a
  date onto the survivor if only the twin had one;
* rewrites a non-canonical URL and entry_key (relative, or with whitespace) to the
  canonical form when no twin exists;
* writes every row it deletes or rewrites to a JSON backup BEFORE touching the table.

Why some of it waits for the deploy
-----------------------------------
Production still runs the parser that writes these forms. A row the cron saw in the
last two days is on a live listing, so deleting its twin or rewriting its key now
would simply be recreated within hours. Those rows are reported as DEFERRED; run
again with `--post-deploy` once the parser fix (bespoke_news_scraper, 11 Sep 2026) is
live. The script is idempotent, so running it twice is the design.

Nothing references eu_news_items by foreign key (checked in pg_constraint, 11 Sep).

Usage
-----
    python3.12 scripts/repair_news_stock.py --dry-run
    python3.12 scripts/repair_news_stock.py --apply
    python3.12 scripts/repair_news_stock.py --apply --post-deploy
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BACKEND = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

RECENT = timedelta(days=2)

_JUNK_RULES = (
    ("presscorner_home_navigation", lambda r, u: bool(re.search(r"/presscorner/home(?:/|$)", u))),
    # Only when undated: SANTE announces a real, dated item with a faceted link.
    ("faceted_listing_navigation",
     lambda r, u: r.get("news_date") is None and bool(re.search(r"[?&]f(?:%5B|\[)\d+(?:%5D|\])=", u))),
    ("euaa_listing_page",
     lambda r, u: r.get("source_key") == "EUAA" and bool(re.search(r"/news-events/press-releases/?$", u))),
    ("gi_registry_page_not_news", lambda r, u: "/geographical-indications-food-and-drink/" in u),
    ("cor_stories_hub_navigation",
     lambda r, u: r.get("source_key") == "COR" and bool(re.search(r"/en/news/all-stories/?$", u))),
)


def junk_reason(row: dict):
    u = row.get("source_url") or ""
    for name, rule in _JUNK_RULES:
        if rule(row, u):
            return name
    return None


def canonical_url(row: dict, listing_urls: dict) -> str:
    u = (row.get("source_url") or "").strip()
    if u and not u.startswith("http"):
        base = listing_urls.get(row.get("source_key"))
        if base:
            u = urljoin(base, u)
    return u


def plan(rows: list, *, listing_urls: dict, canon_key, now: datetime, post_deploy: bool) -> dict:
    """Decide, without touching the database, what to delete, merge, rewrite or defer.

    `canon_key` is the writers' own entry_key function, so a rewritten key is exactly
    the key the fixed parser will look up.
    """
    by_url = {r["source_url"]: r for r in rows if r.get("source_url")}
    by_key = {r["entry_key"]: r for r in rows}
    out = {"delete": [], "set_date": [], "rewrite": [], "deferred": []}
    gone = set()

    def recent(r):
        f = r.get("fetched_at")
        if f is not None and f.tzinfo is None:
            f = f.replace(tzinfo=timezone.utc)
        return f is not None and f > now - RECENT

    def act(r, kind, why, **extra):
        if recent(r) and not post_deploy:
            out["deferred"].append({"id": r["id"], "why": why, "url": r.get("source_url")})
            return False
        out[kind].append(dict({"id": r["id"], "why": why, "url": r.get("source_url")}, **extra))
        return True

    for r in rows:
        if r["id"] in gone:
            continue
        why = junk_reason(r)
        if why:
            if act(r, "delete", why):
                gone.add(r["id"])
            continue
        url = r.get("source_url") or ""
        twin = None
        # CoR ONLY, and only when the titles match. Verified on the CoR pairs (same
        # title, the `-0` page 404s). The first dry run also matched `-0` URLs on EESC,
        # SRB, FRA and data.europa.eu, where a `-0` slug can be a DIFFERENT item that
        # happens to share a title -- deleting those would destroy news.
        alias_base = by_url.get(url[:-2]) if re.search(r"-0$", url) else None
        if (alias_base is not None and r.get("source_key") == "COR"
                and alias_base.get("source_key") == "COR"
                and (alias_base.get("title") or "").strip() == (r.get("title") or "").strip()):
            twin, why = alias_base, "cor_drupal_alias_of_real_slug"
        else:
            canon = canonical_url(r, listing_urls)
            if canon and canon != url:
                twin = by_url.get(canon) or by_key.get(canon_key(canon))
                why = "duplicate_of_canonical_url" if twin else None
                if twin is None:
                    if act(r, "rewrite", "non_canonical_url", new_url=canon, new_key=canon_key(canon)):
                        pass
                    continue
        if twin is not None and twin["id"] != r["id"] and twin["id"] not in gone:
            if act(r, "delete", why, survivor=twin["id"]):
                gone.add(r["id"])
                if twin.get("news_date") is None and r.get("news_date") is not None:
                    out["set_date"].append({"id": twin["id"], "news_date": r["news_date"],
                                            "why": "date_carried_from_deleted_twin"})
    return out


def _listing_urls() -> dict:
    from services.scrapers.bespoke_news_scraper import BESPOKE_SOURCES
    from services.scrapers.dg_news_sources import DG_NEWS_SOURCES, EU_BODY_FEEDS, OUTLET_FEEDS
    urls: dict = {}
    for s in list(BESPOKE_SOURCES) + DG_NEWS_SOURCES + EU_BODY_FEEDS + OUTLET_FEEDS:
        for k in (s.get("source_key"), s.get("dg"), s.get("institution")):
            if k:
                urls.setdefault(k, s["url"])
    return urls


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    ap.add_argument("--post-deploy", action="store_true",
                    help="The parser fix is live: act on rows a live listing still shows.")
    args = ap.parse_args()

    from sqlalchemy import text
    from core.database import SessionLocal
    from services.scrapers.dg_news_scraper import _canon_url

    db = SessionLocal()
    try:
        cols = [c[0] for c in db.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name='eu_news_items' "
            "ORDER BY ordinal_position")).all()]
        rows = [dict(r) for r in db.execute(text("SELECT * FROM eu_news_items")).mappings().all()]
        undated_before = sum(1 for r in rows if r["news_date"] is None)
        p = plan(rows, listing_urls=_listing_urls(), canon_key=_canon_url,
                 now=datetime.now(timezone.utc), post_deploy=args.post_deploy)

        for kind in ("delete", "set_date", "rewrite", "deferred"):
            print(f"[INFO] {kind}: {len(p[kind])}")
            for a in p[kind]:
                extra = a.get("new_url") or a.get("survivor") or a.get("news_date") or ""
                print(f"         {a['why']:<32} {str(a.get('url'))[:90]} {str(extra)[:60]}")

        if args.dry_run:
            print(f"[DRY-RUN] nothing written. undated rows now: {undated_before}")
            return 0
        if not (p["delete"] or p["set_date"] or p["rewrite"]):
            print("[OK] nothing to do")
            return 0

        touched = {a["id"] for k in ("delete", "rewrite") for a in p[k]}
        backup_rows = [{k: (v.isoformat() if hasattr(v, "isoformat") else (str(v) if k == "id" else v))
                        for k, v in r.items() if k in cols} for r in rows if r["id"] in touched]
        bdir = _REPO_ROOT / "docs" / "backups"
        bdir.mkdir(parents=True, exist_ok=True)
        bfile = bdir / f"eu_news_items_repair_{datetime.now():%Y-%m-%d_%H%M%S}.json"
        bfile.write_text(json.dumps({"plan": p, "rows": backup_rows}, default=str, ensure_ascii=False, indent=1))
        if len(json.loads(bfile.read_text())["rows"]) != len(touched):
            print(f"[ERROR] backup {bfile} does not hold all {len(touched)} rows; nothing written",
                  file=sys.stderr)
            return 1
        print(f"[OK] backup of {len(touched)} row(s): {bfile}")

        for a in p["set_date"]:
            db.execute(text("UPDATE eu_news_items SET news_date = :d WHERE id = :i AND news_date IS NULL"),
                       {"d": a["news_date"], "i": a["id"]})
        for a in p["delete"]:
            db.execute(text("DELETE FROM eu_news_items WHERE id = :i"), {"i": a["id"]})
        for a in p["rewrite"]:
            db.execute(text("UPDATE eu_news_items SET source_url = :u, entry_key = :k WHERE id = :i"),
                       {"u": a["new_url"], "k": a["new_key"], "i": a["id"]})
        db.commit()

        after = db.execute(text("SELECT count(*) AS n, count(*) FILTER (WHERE news_date IS NULL) AS u "
                                "FROM eu_news_items")).mappings().one()
        left = db.execute(text("SELECT count(*) FROM eu_news_items WHERE id = ANY(CAST(:i AS uuid[]))"),
                          {"i": [str(a["id"]) for a in p["delete"]]}).scalar()
        print(f"[INFO] undated {undated_before} -> {after['u']}; rows {len(rows)} -> {after['n']}; "
              f"deleted ids still present: {left}")
        if left:
            print("[ERROR] some deletes did not persist", file=sys.stderr)
            return 1
        if p["deferred"]:
            print(f"[INFO] {len(p['deferred'])} deferred until the parser fix is deployed: "
                  "re-run with --apply --post-deploy")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
