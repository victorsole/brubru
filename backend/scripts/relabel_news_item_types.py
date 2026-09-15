#!/usr/bin/env python3.12
"""Give eu_news_items rows from site-wide feeds the type of what they are.

Why (measured 15 September 2026)
--------------------------------
The RSS parser stamped every entry of a site-wide feed as `news`, so the news store
held events, videos, podcasts, consultations, publications, e-mail alert digests, job
vacancies and procurement notices as news, and /api/v2/news served them. The rules,
the counts and the registry changes are in services/news/feed_item_types.py; this
script applies the SAME rules to the stock, so a sync cannot flip a row back.

What it does
------------
* for every institution with rules: sets item_type from the URL rule, or from the
  item's own page (Drupal node type) when the rule says PAGE;
* deletes the rows the rules call SKIP (not content);
* leaves UNKNOWN rows untouched and reports each one, rather than guess;
* writes every row it changes or deletes to a JSON backup BEFORE touching the table.

Idempotent. Until the registry change is deployed, production still reads the old
feeds and re-stamps their newest rows as news on each sync: run it again after deploy.

Nothing references eu_news_items by foreign key (pg_constraint, 15 Sep 2026).

Usage
-----
    python3.12 scripts/relabel_news_item_types.py                  # dry run, all bodies
    python3.12 scripts/relabel_news_item_types.py --institution SRB
    python3.12 scripts/relabel_news_item_types.py --apply
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
import time
from datetime import datetime, timezone

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_BACKEND = pathlib.Path(__file__).resolve().parents[1]
for _p in (str(_REPO_ROOT), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="write the changes (default: dry run)")
    ap.add_argument("--institution", action="append",
                    help="limit to this institution (repeatable); default every body with rules")
    args = ap.parse_args()

    from sqlalchemy import text
    from core.database import SessionLocal
    from services.news.feed_item_types import RULES, SKIP, UNKNOWN, item_type_for
    from services.scrapers.dg_news_scraper import _fetch_page_text

    institutions = [i.upper() for i in (args.institution or sorted(RULES))]
    bad = [i for i in institutions if i not in RULES]
    if bad:
        print(f"[ERROR] no rules for {bad}")
        return 2

    def fetch(url):  # paced: one site, sequential, polite
        time.sleep(0.3)
        return _fetch_page_text(url)

    db = SessionLocal()
    try:
        rows = db.execute(text(
            "SELECT id, institution, entry_key, source_url, item_type FROM eu_news_items "
            "WHERE institution = ANY(:i)"), {"i": institutions}).fetchall()
        # Read everything (page fetches included) before writing, then close the read
        # session: a Session held across network work can lose its connection.
        db.close()

        relabel, delete, unknown = [], [], []
        moves = collections.Counter()
        for r in rows:
            outcome, how = item_type_for(r.institution, r.source_url, fetch=fetch)
            if outcome == UNKNOWN:
                unknown.append((r, how))
            elif outcome == SKIP:
                delete.append(r)
                moves[(r.institution, r.item_type, "DELETE")] += 1
            elif outcome != r.item_type:
                relabel.append((r, outcome))
                moves[(r.institution, r.item_type, outcome)] += 1

        print(f"[INFO] rows under rules: {len(rows)} ({', '.join(institutions)})")
        for (inst, old, new), n in sorted(moves.items()):
            print(f"[INFO]   {inst:7s} {old} -> {new}: {n}")
        print(f"[INFO]   unchanged: {len(rows) - len(relabel) - len(delete) - len(unknown)}")
        for r, how in unknown:
            print(f"[WARN]   untyped ({how}), left as {r.item_type}: {r.institution} {r.source_url}")

        if not args.apply:
            print("[INFO] dry run: nothing written. Re-run with --apply.")
            return 0
        if not relabel and not delete:
            print("[OK] nothing to change")
            return 0

        db = SessionLocal()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        backup = _REPO_ROOT / "docs" / "backups" / f"eu_news_items_item_type_relabel_{stamp}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_text(json.dumps({
            "relabelled": [{"id": str(r.id), "institution": r.institution, "entry_key": r.entry_key,
                            "old_item_type": r.item_type, "new_item_type": t} for r, t in relabel],
            "deleted": [dict(db.execute(text("SELECT * FROM eu_news_items WHERE id = :id"),
                                        {"id": r.id}).mappings().one()) for r in delete],
        }, default=str, indent=1))
        print(f"[OK] backup written: {backup}")

        changed = sum(db.execute(text(
            "UPDATE eu_news_items SET item_type = :t WHERE id = :id AND item_type = :old"),
            {"t": t, "id": r.id, "old": r.item_type}).rowcount for r, t in relabel)
        deleted = sum(db.execute(text("DELETE FROM eu_news_items WHERE id = :id"),
                                 {"id": r.id}).rowcount for r in delete)
        db.commit()
        print(f"[OK] relabelled {changed} of {len(relabel)}, deleted {deleted} of {len(delete)}")
        if changed != len(relabel) or deleted != len(delete):
            print("[ERROR] fewer rows changed than planned (a concurrent sync?); re-run to converge")
            return 1
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
