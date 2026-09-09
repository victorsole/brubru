#!/usr/bin/env python3.12
"""Remove the Plone attachment rows that `eea` news ingested as if they were articles.

Why
---
`/en/newsroom/news/@search` returns EVERY content object under that path, and Plone
keeps an article's attachments as CHILD objects of the article. Walking it without
`portal_type` therefore returned 466 rows for 194 articles:

    News Item  194   the actual articles
    Image      223   all carrying Plone's 1969-12-30 null-date sentinel
    File        47   ONE press release published as 47 language PDFs
    Document     1   the "Press releases" folder itself
    Link         1

Those 223 images were the whole of the "eea has 223 undated items" reading in
`/api/v2/news/latest` -- an item-quality bug wearing a date-parser's clothes. The
scraper fix (portal_type + a client-side re-check) stops new ones; this removes the
rows already stored.

How rows are identified
-----------------------
By `@type` from the live API, never by URL shape. A URL pattern is what produced the
bug in the first place, and it is measurably wrong here: one File is published at
`.../belgium-eea25-press-release-dutch` with no extension at all, so an
extension regex silently keeps it.

The script therefore deletes only rows whose URL the API positively reports as a
NON-article type. A stored row that appears in neither the keep-set nor the drop-set
is left alone and reported -- deleting "everything not currently returned" would
destroy any legitimately archived article the API has stopped listing.

`economy_items_translations.item_id` is ON DELETE CASCADE (read from pg_constraint,
not assumed), so translations attached to a deleted row would go with it. Measured
before writing this: zero junk rows carry a translation. The script re-checks and
refuses any row that has acquired one.

Usage
-----
    python3.12 -m backend.scripts.cleanup_eea_asset_rows --dry-run
    python3.12 -m backend.scripts.cleanup_eea_asset_rows --apply
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from collections import Counter

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_BACKEND = str(pathlib.Path(__file__).resolve().parents[1])
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import requests  # noqa: E402
from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.scrapers.eea_content import _HEADERS, _NEWS, _NEWS_TYPE  # noqa: E402

ARTICLE = _NEWS_TYPE


def api_rows() -> list[dict]:
    """Every object under the news path, with its @type. Unfiltered on purpose."""
    s = requests.Session()
    s.headers.update(_HEADERS)
    out: list[dict] = []
    b = 0
    while True:
        r = s.get(_NEWS, params={"b_size": 100, "b_start": b,
                                 "metadata_fields": ["Description", "effective",
                                                     "effective"]}, timeout=40)
        r.raise_for_status()
        j = r.json()
        page = j.get("items") or []
        if not page:
            break
        out += page
        b += len(page)
        if b >= int(j.get("items_total") or 0):
            break
    return out


def counts(db):
    r = db.execute(text(
        "SELECT count(*) AS rows, count(document_date) AS dated, "
        "       count(*) - count(document_date) AS undated "
        "FROM economy_items "
        "WHERE body_code = 'eea' AND item_type IN ('news','press_release')"
    )).mappings().one()
    return dict(r)


def fk_children(db) -> list[str]:
    """Read the FK catalogue rather than trusting a hardcoded list."""
    rows = db.execute(text(
        "SELECT src.relname AS t, c.confdeltype AS d "
        "FROM pg_constraint c "
        "JOIN pg_class src ON src.oid = c.conrelid "
        "JOIN pg_class tgt ON tgt.oid = c.confrelid "
        "WHERE c.contype = 'f' AND tgt.relname = 'economy_items'"
    )).mappings().all()
    return [f"{r['t']} (on_delete={r['d']})" for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        print(f"[INFO] FK children of economy_items: {fk_children(db)}")
        before = counts(db)
        print(f"[INFO] before: {before}")

        rows = api_rows()
        by_type = Counter(r.get("@type") for r in rows)
        print(f"[INFO] live API @type distribution: {dict(by_type)}")

        keep = {r.get("@id") for r in rows if r.get("@type") == ARTICLE}
        drop = {r.get("@id") for r in rows if r.get("@type") != ARTICLE}
        keep.discard(None)
        drop.discard(None)
        print(f"[INFO] API says {len(keep)} article(s), {len(drop)} non-article object(s)")
        if not keep:
            print("[ERROR] the API returned zero articles; refusing to delete anything "
                  "on the strength of an empty keep-set")
            return 1

        stored = db.execute(text(
            "SELECT id, public_url FROM economy_items "
            "WHERE body_code = 'eea' AND item_type IN ('news','press_release')"
        )).mappings().all()

        to_delete = [s for s in stored if s["public_url"] in drop]
        unknown = [s for s in stored
                   if s["public_url"] not in drop and s["public_url"] not in keep]

        print(f"[INFO] stored rows: {len(stored)} | positively non-article: {len(to_delete)} "
              f"| in neither set: {len(unknown)}")
        for s in unknown[:10]:
            print(f"       LEFT ALONE (not in either set): {s['public_url']}")
        if unknown:
            print(f"[INFO] {len(unknown)} row(s) left alone. They are neither a current "
                  "article nor a known attachment -- possibly archived. Not deleting.")

        if not to_delete:
            print("[OK] nothing to delete")
            return 0

        ids = [s["id"] for s in to_delete]
        held = db.execute(text(
            "SELECT count(*) AS n FROM economy_items_translations WHERE item_id = ANY(:ids)"
        ), {"ids": ids}).scalar_one()
        if held:
            print(f"[ERROR] {held} translation(s) hang off these rows and the FK is "
                  "ON DELETE CASCADE; refusing. Repoint or export them first.")
            return 1
        print("[INFO] 0 translations attached; cascade takes nothing")

        if args.dry_run:
            print(f"[DRY-RUN] would delete {len(ids)} row(s); nothing written")
            return 0

        db.execute(text("DELETE FROM economy_items WHERE id = ANY(:ids)"), {"ids": ids})
        db.commit()

        after = counts(db)
        print(f"[INFO] after : {after}")
        deleted = before["rows"] - after["rows"]
        print(f"[INFO] deleted {deleted} row(s) (expected {len(ids)})")

        ok = True
        if deleted != len(ids):
            print(f"[ERROR] deleted {deleted}, expected {len(ids)}")
            ok = False
        if after["undated"]:
            print(f"[ERROR] {after['undated']} eea row(s) still undated")
            ok = False
        if after["rows"] != len(keep):
            gap = len(keep) - after["rows"]
            print(f"[INFO] {after['rows']} rows remain, API lists {len(keep)} articles "
                  f"({gap:+d}). Not a defect by itself: the API can list an article the "
                  "cron has not ingested yet, and can drop one we archived. The delete "
                  "set was computed from @type, so this gap is unrelated to it.")
        print("[OK] eea news carries a date on every row" if ok else "[FAIL] see errors")
        return 0 if ok else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
