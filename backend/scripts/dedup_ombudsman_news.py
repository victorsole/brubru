#!/usr/bin/env python3.12
"""Collapse the duplicated Ombudsman news rows, keeping the canonical URL and the
best REAL body.

Why (measured 8 September 2026)
-------------------------------
`economy_items` held 21 ombudsman news rows for 16 real items. The SPA listing emits
the same item under two locale-prefix variants (`/en/news-document/en/<id>` and
`/news-document/en/<id>`) and the scraper deduped on the URL string, so both
survived. The non-prefixed variant **404s**, and `extract_html` turned that 404 page
into a `body_txt` -- so the duplicate row carried a body reading "Oops! 404 Not
Found" while satisfying every "body is not null" check.

Both variants declare the same `<link rel="canonical">`, so which form to keep is the
site's own statement, not a guess.

What it does, and why it is not a plain DELETE
----------------------------------------------
For each duplicated item id it keeps ONE row and merges fields rather than picking a
winner outright, because the canonical-URL row is the WORSE one in 4 of 5 pairs (its
render had not settled, leaving body_txt NULL, while the duplicate held the 404
text). Keeping "the canonical row" naively would have looked right and thrown away
the only real body in the one case where the duplicate had it.

Rules:
  * survivor  = the row whose URL is already canonical; if neither is, the oldest.
  * URL       = rewritten to the canonical form.
  * body      = the best body across the pair that is NOT an error page, judged by
                `error_body_reason`. If neither has a valid body, the survivor's
                body is set to NULL, which is the honest state and is what
                `/news/latest` reports as a real gap.
  * loser     = deleted.

FK safety: `pg_constraint` says one child references `economy_items`,
`economy_items_translations.item_id` with **ON DELETE CASCADE**. Translation counts
are printed per pair BEFORE deleting, and the script refuses to delete a loser that
has translations the survivor lacks. Never a hardcoded child-table list; see
feedback_merge_rows_read_fk_catalogue_not_a_list.

Usage
-----
    python3.12 -m backend.scripts.dedup_ombudsman_news --dry-run
    python3.12 -m backend.scripts.dedup_ombudsman_news --apply
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from collections import defaultdict

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
_BACKEND = str(pathlib.Path(__file__).resolve().parents[1])
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.scrapers.economy_common import error_body_reason  # noqa: E402
from services.scrapers.economy_ombudsman import (  # noqa: E402
    canonical_news_url, chrome_only_reason,
)

SELECT = """
SELECT e.id, e.public_url, e.title, e.body_txt, e.body_html, e.document_date,
       e.creation_date,
       (SELECT count(*) FROM economy_items_translations t WHERE t.item_id = e.id) AS translations
FROM economy_items e
WHERE e.body_code = 'ombudsman' AND e.item_type IN ('news','press_release')
ORDER BY e.creation_date, e.id
"""


def invariants(db):
    r = db.execute(text(
        "SELECT count(*) AS rows, "
        "count(DISTINCT substring(public_url from '/news-document/[a-z]{2}/(\\d+)')) AS distinct_ids, "
        "count(*) FILTER (WHERE public_url NOT LIKE '%/en/news-document/%') AS non_canonical, "
        "count(*) FILTER (WHERE body_txt ILIKE '%404 Not Found%') AS body_is_404, "
        "count(*) FILTER (WHERE body_txt IS NOT NULL) AS with_body, "
        "(SELECT count(*) FROM economy_items_translations t JOIN economy_items e2 ON e2.id=t.item_id "
        " WHERE e2.body_code='ombudsman') AS translations "
        "FROM economy_items WHERE body_code='ombudsman' AND item_type IN ('news','press_release')"
    )).mappings().one()
    return dict(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        before = invariants(db)
        print(f"[INFO] before: {before}")

        rows = db.execute(text(SELECT)).mappings().all()
        groups = defaultdict(list)
        for r in rows:
            _, key = canonical_news_url(r["public_url"] or "")
            groups[key or f"UNPARSED:{r['id']}"].append(dict(r))

        dupes = {k: v for k, v in groups.items() if len(v) > 1}
        print(f"[INFO] {len(rows)} rows -> {len(groups)} distinct items, {len(dupes)} duplicated")

        deletes, updates, refused = [], [], []
        for key, members in sorted(dupes.items()):
            canon = [m for m in members
                     if "/en/news-document/" in (m["public_url"] or "")]
            survivor = (canon or sorted(members, key=lambda m: m["creation_date"]))[0]
            losers = [m for m in members if m["id"] != survivor["id"]]

            # Never let a CASCADE take translations the survivor does not have.
            lost_tr = sum(m["translations"] for m in losers)
            if lost_tr and survivor["translations"] == 0:
                refused.append((key, lost_tr))
                continue

            best_url, _ = canonical_news_url(survivor["public_url"])
            valid = [m for m in members
                     if m["body_txt"] is not None
                     and error_body_reason(m["body_txt"]) is None
                     and chrome_only_reason(m["body_txt"]) is None]
            best = max(valid, key=lambda m: len(m["body_txt"])) if valid else None

            reasons = {m["id"]: (error_body_reason(m["body_txt"])
                                 or chrome_only_reason(m["body_txt"])) for m in members}
            print(f"  item {key}: keep {survivor['id']}, drop {[m['id'] for m in losers]}"
                  f"  body_reasons={reasons}"
                  f"  -> body from {best['id'] if best else 'NONE (set NULL)'}")

            updates.append({"id": survivor["id"], "url": best_url,
                            "t": best["body_txt"] if best else None,
                            "h": best["body_html"] if best else None})
            deletes.extend(m["id"] for m in losers)

        # Canonicalise the URL on non-duplicated rows too.
        for key, members in groups.items():
            if len(members) == 1 and not key.startswith("UNPARSED:"):
                m = members[0]
                cu, _ = canonical_news_url(m["public_url"])
                if cu and cu != m["public_url"]:
                    updates.append({"id": m["id"], "url": cu,
                                    "t": m["body_txt"], "h": m["body_html"]})

        print(f"[INFO] {len(updates)} rows to update, {len(deletes)} to delete"
              + (f", {len(refused)} REFUSED (would cascade translations): {refused}" if refused else ""))

        if args.dry_run:
            print("[DRY-RUN] nothing written")
            return 0

        for u in updates:
            db.execute(text("UPDATE economy_items SET public_url=:url, body_txt=:t, body_html=:h "
                            "WHERE id=:id"), u)
        if deletes:
            db.execute(text("DELETE FROM economy_items WHERE id = ANY(:ids)"), {"ids": deletes})
        db.commit()

        after = invariants(db)
        print(f"[INFO] after : {after}")
        ok = True
        if after["rows"] != before["rows"] - len(deletes):
            print(f"[ERROR] row delta wrong: {before['rows']} -> {after['rows']}, expected -{len(deletes)}")
            ok = False
        if after["distinct_ids"] != before["distinct_ids"]:
            print(f"[ERROR] LOST AN ITEM: distinct ids {before['distinct_ids']} -> {after['distinct_ids']}")
            ok = False
        if after["rows"] != after["distinct_ids"]:
            print(f"[ERROR] duplicates remain: {after['rows']} rows for {after['distinct_ids']} items")
            ok = False
        if after["non_canonical"]:
            print(f"[ERROR] {after['non_canonical']} rows still non-canonical")
            ok = False
        if after["body_is_404"]:
            print(f"[ERROR] {after['body_is_404']} rows still hold a 404 body")
            ok = False
        if after["translations"] != before["translations"]:
            print(f"[ERROR] translations changed: {before['translations']} -> {after['translations']}")
            ok = False
        if not ok:
            return 1
        print(f"[OK] {after['rows']} rows for {after['distinct_ids']} items, all canonical, "
              f"0 error bodies, translations intact ({after['translations']})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
