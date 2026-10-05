"""Seed updated_at where it is null on economy_items and eu_news_items (needs migration 272).

Victor's rule (5 Oct 2026): every API item carries updated_date. A null row has not
changed since we stored it as far as the trigger knows, so its first known bound is
fetched_at, else its creation time (the same seed migration 271 described).
Batched by id; one worker (the pooler is shared with production). Exits non-zero if
any null remains.

    python3.12 scripts/seed_updated_at_nulls.py [--batch 5000]
"""
import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from sqlalchemy import text  # noqa: E402
from core.database import engine  # noqa: E402

TABLES = {"economy_items": "creation_date", "eu_news_items": "created_at"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=5000)
    a = ap.parse_args()
    with engine.connect() as c:
        default = c.execute(text(
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'economy_items' AND column_name = 'updated_at'")).scalar()
    if not default:
        # Without 272 the trigger restores the null, and this loop would never end.
        sys.exit("[ERROR] migration 272 not applied; nothing seeded")
    left = 0
    for table, created in TABLES.items():
        done = 0
        while True:
            with engine.begin() as c:
                n = c.execute(text(
                    f"UPDATE {table} SET updated_at = coalesce(fetched_at, {created}, now()) "
                    f"WHERE id IN (SELECT id FROM {table} WHERE updated_at IS NULL LIMIT :b)"),
                    {"b": a.batch}).rowcount
            done += n
            print(f"[INFO] {table}: {done} seeded", flush=True)
            if n == 0:
                break
        with engine.connect() as c:
            rest = c.execute(text(f"SELECT count(*) FROM {table} WHERE updated_at IS NULL")).scalar()
        print(f"[OK] {table}: {rest} null left")
        left += rest
    sys.exit(1 if left else 0)


if __name__ == "__main__":
    main()
