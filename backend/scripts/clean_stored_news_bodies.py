"""Remove share widgets, newsletter links and scripts from stored news bodies (16 Oct 2026).

Applies services/news/page_widgets.py (what the page readers now apply before storing) to
the rows already stored in eu_news_items and economy_items: 509 Parliament press releases
carried "Share this page: Facebook X LinkedIn WhatsApp", 167 body_html held a <script> or
an onclick. Only rows the cleaner changes are written.

    python3.12 scripts/clean_stored_news_bodies.py            # dry run
    python3.12 scripts/clean_stored_news_bodies.py --apply
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from services.news.page_widgets import clean_html, clean_text  # noqa: E402

PICK = """SELECT id, {code} AS code, body_txt, body_html FROM {table}
          WHERE body_txt ~* '(^|\\n)(share this page|sign up for mail updates|pdf version|whatsapp|\\d+ (hours|minutes|days) ago)\\s*:?\\s*(\\n|$)'
             OR body_html ~* '(<script|\\sonclick=|share\\.php\\?u=|x\\.com/intent|class="[^"]*share)'"""
# The id in its own type: "id::text = :id" cannot use the key and timed out on economy_items.
STORE = "UPDATE {table} SET body_txt = :t, body_html = :h, updated_at = now() WHERE id = :id"
TABLES = (("eu_news_items", "institution"), ("economy_items", "body_code"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    total = 0
    for table, code in TABLES:
        with engine.connect() as c:
            # A regex over every body of economy_items outlasts the default statement timeout.
            c.execute(text("SET statement_timeout = 0"))
            rows = list(c.execute(text(PICK.format(table=table, code=code))))
        plan = []
        for r in rows:
            t, h = clean_text(r.body_txt), clean_html(r.body_html)
            if (t, h) != (r.body_txt, r.body_html) and (t or "").strip():
                plan.append((r.id, r.code, t, h, len(r.body_txt or "") - len(t or "")))
        by = collections.Counter(p[1] for p in plan)
        print(f"[INFO] {table}: {len(rows)} candidate(s), {len(plan)} changed: {dict(by.most_common(10))}")
        if args.apply and plan:
            with engine.begin() as c:
                c.execute(text("SET LOCAL statement_timeout = 0"))
                for rid, _, t, h, _ in plan:
                    c.execute(text(STORE.format(table=table)), {"id": rid, "t": t, "h": h})
        total += len(plan)
    print(("[DONE] cleaned " if args.apply else "[DRY RUN] would clean ") + str(total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
