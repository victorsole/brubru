#!/usr/bin/env python3.12
"""Seed the news stores' updated_at in batches, without rewriting a 3.5 GB table at once.

Migration 271 gave economy_items and eu_news_items an updated_at column so
GovClipping's incremental news sync has something to filter on. Existing rows need a
starting value, and a single UPDATE over 601,949 rows rewrites the whole table and
holds a long transaction against production.

The seed value is the best bound we actually hold for when the row last changed:
fetched_at, falling back to the row's creation timestamp. That is an initial value,
not a policy -- from here the brubru_touch_if_changed trigger maintains the column
truthfully, and a re-scrape that finds an identical article leaves it alone. A fetch
time is never served as the change signal for a row that has since really changed.

Only NULL updated_at values are written, so this is re-runnable and can never move a
timestamp the trigger has already set.

The trigger has to be switched off for the write itself. brubru_touch_if_changed
treats updated_at as the signal column: seeing that nothing ELSE in the row changed,
it concludes the row did not change and restores updated_at to its old value. A first
attempt at this seed therefore reported 20,000 rows updated per batch while leaving
every one of them NULL, and looped forever because the backlog never shrank. Proven on
a single row before being worked around, not assumed. Triggers are suppressed per CONNECTION (session_replication_role), never per table:
ALTER TABLE ... DISABLE TRIGGER takes an ACCESS EXCLUSIVE lock, and taking that on a
3.5 GB table shared with production, once per batch, would block every live writer.

    python3.12 scripts/seed_news_updated_at.py --rehearse
    python3.12 scripts/seed_news_updated_at.py --apply
"""
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import time

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from sqlalchemy import create_engine, text  # noqa: E402

TABLES = {
    "economy_items": "coalesce(fetched_at, creation_date)",
    "eu_news_items": "coalesce(fetched_at, created_at, scraped_at)",
}
BATCH = 20000


def _database_url() -> str:
    m = re.search(r"^DATABASE_URL=(.*)$", (BACKEND / ".env").read_text(), re.M)
    if not m:
        raise SystemExit("[ERROR] DATABASE_URL not found in backend/.env")
    return m.group(1).strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rehearse", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    engine = create_engine(_database_url())
    rc = 0
    for table, src in TABLES.items():
        with engine.connect() as conn:
            todo = conn.execute(text(
                f"SELECT count(*) FROM {table} WHERE updated_at IS NULL")).scalar_one()
            total = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
        print(f"[INFO] {table}: {todo} of {total} rows need a seed value")
        if args.rehearse or todo == 0:
            continue

        done = 0
        t0 = time.time()
        while True:
            # Batched by primary key so each statement is short and the table is never
            # locked for the whole run.
            with engine.begin() as conn:
                # Switch triggers off for THIS SESSION, not on the table. An
                # ALTER TABLE ... DISABLE TRIGGER takes an ACCESS EXCLUSIVE lock, and
                # economy_items is 3.5 GB and shared with production: taking that lock
                # once per batch would block every live writer, which is worse than the
                # bug being fixed. session_replication_role is scoped to this
                # connection and takes no lock at all.
                conn.execute(text("SET session_replication_role = replica"))
                n = conn.execute(text(f"""
                    UPDATE {table} SET updated_at = {src}
                     WHERE id IN (SELECT id FROM {table}
                                   WHERE updated_at IS NULL
                                   ORDER BY id LIMIT :b)
                       AND updated_at IS NULL
                """), {"b": BATCH}).rowcount
                conn.execute(text("SET session_replication_role = origin"))
            if n == 0:
                break
            done += n
            with engine.connect() as conn:
                still = conn.execute(text(
                    f"SELECT count(*) FROM {table} WHERE updated_at IS NULL")).scalar_one()
            if still >= todo - done + BATCH:
                # Rows reported as written are still NULL: something is undoing the
                # write. Stop rather than loop on a backlog that never shrinks.
                print(f"[ERROR] {table}: {n} rows written but {still} still NULL; "
                      f"a writer is reverting the value")
                return 1
            print(f"   ...{done}/{todo} ({time.time()-t0:.0f}s)", flush=True)

        with engine.connect() as conn:
            left = conn.execute(text(
                f"SELECT count(*) FROM {table} WHERE updated_at IS NULL")).scalar_one()
        print(f"[INFO] {table}: seeded {done}, still NULL {left}")
        if left and done == 0:
            print(f"[ERROR] {table}: {left} rows need a value and none was written")
            rc = 1

    if args.rehearse:
        print("[INFO] rehearsal only, nothing written")
    return rc


if __name__ == "__main__":
    sys.exit(main())
