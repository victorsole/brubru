"""
Fill fts_commitments from the EU Financial Transparency System files (migration 313).

Each FTS row is stored as an economy_items row (/funding/eu-funding-recipients) whose text lists
a few of its values; the file states many more (coordinator flag, registration and VAT numbers,
city, NUTS2, the beneficiary's own amount, call and project IDs...). This reads the file again,
for every year held, and writes those values as columns beside the stored row (same id), keyed
the way the loader keys the row (services/scrapers/commission_funding.fts_records). Nothing is
parsed from our own text.

Runs in the weekly commission-heavy tier right after the FTS rows are loaded (api/cron.py). A
stored row the file no longer lists (the Commission revised its amount, so the loader stored the
revised one as a new row) gets no columns and is counted.

Run: python3.12 scripts/sync_fts_commitments.py [--apply] [--year 2025 --year 2024]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingest_funding_sedia import get_env  # noqa: E402
from services.funding.countries import country_code, vat_key  # noqa: E402
from services.scrapers.commission_funding import fts_records, read_fts_file  # noqa: E402

COLUMNS = (
    "year", "budget", "lc_reference", "budget_reference", "beneficiary", "registration_number",
    "vat_number", "vat_key", "is_nfpo", "is_ngo", "is_coordinator", "city", "country", "country_code", "nuts2",
    "beneficiary_amount_eur", "beneficiary_estimated_amount_eur", "beneficiary_estimated_consumed_eur",
    "commitment_contracted_eur", "commitment_adjustment_eur", "commitment_total_eur",
    "commitment_consumed_eur", "amount_source", "expense_type", "call_id", "project_id",
    "project_acronym", "subject", "dg", "budget_line_number", "budget_line_name", "programme",
    "beneficiary_type", "project_start", "project_end", "funding_type", "management_type",
    "benefiting_country",
)
UPSERT = (
    f"INSERT INTO fts_commitments (economy_item_id, {', '.join(COLUMNS)}) VALUES %s "
    f"ON CONFLICT (economy_item_id) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in COLUMNS) + ", scraped_at = now()"
)
_URL = "https://ec.europa.eu/budget/financial-transparency-system/index.html#"
BATCH = 1000


def held_years(cur) -> list[int]:
    cur.execute("SELECT DISTINCT substring(public_url from '#(\\d{4})-')::int FROM economy_items "
                "WHERE body_code = 'commission' AND item_type = 'funding_recipient'")
    return sorted((y for (y,) in cur.fetchall() if y), reverse=True)


def stored_ids(cur, year: int) -> dict:
    cur.execute("SELECT guid, id FROM economy_items WHERE body_code = 'commission' "
                "AND item_type = 'funding_recipient' AND public_url LIKE %s", (f"{_URL}{year}-%",))
    return dict(cur.fetchall())


def sync_year(conn, year: int, *, apply: bool) -> tuple[int, int, int]:
    """(written, file rows with no stored row, stored rows the file no longer lists)."""
    found = read_fts_file(year)
    if not found:
        raise RuntimeError(f"the {year} FTS file could not be read")
    _, raw = found
    with conn.cursor() as cur:
        ids = stored_ids(cur, year)
    rows, unstored, seen = [], 0, set()
    for rec in fts_records(raw, year):
        item_id = ids.get(rec["key"])
        if item_id is None:
            unstored += 1
            continue
        seen.add(rec["key"])
        rec["vat_key"] = vat_key(rec["vat_number"])
        rec["country_code"] = country_code(rec["country"])
        rows.append((item_id, *(rec[c] for c in COLUMNS)))
    if apply:
        with conn.cursor() as cur:
            for i in range(0, len(rows), BATCH):
                psycopg2.extras.execute_values(cur, UPSERT, rows[i:i + BATCH], page_size=BATCH)
                conn.commit()
    return len(rows), unstored, len(set(ids) - seen)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true", help="Write (default: dry run).")
    ap.add_argument("--year", type=int, action="append", help="A year to read (repeatable); default every year held.")
    args = ap.parse_args(argv)
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        return 1
    conn = psycopg2.connect(db.replace("postgresql+psycopg2://", "postgresql://"))
    try:
        with conn.cursor() as cur:
            years = args.year or held_years(cur)
        total, problems = 0, []
        for year in years:
            try:
                written, unstored, stale = sync_year(conn, year, apply=args.apply)
            except Exception as exc:  # noqa: BLE001 -- one year's file never stops the other
                conn.rollback()
                problems.append(f"{year}: {type(exc).__name__}: {exc}"[:200])
                continue
            total += written
            print(f"[{'OK' if args.apply else 'DRY-RUN'}] {year}: {written} row(s) "
                  f"{'written' if args.apply else 'to write'}; {unstored} in the file but not stored "
                  f"(the FTS rows are loaded before this job); {stale} stored but no longer in the file")
    finally:
        conn.close()
    if problems:
        print(f"[SYNC_STATUS] degraded: {'; '.join(problems)}")
    if not total:
        print("[ERROR] no FTS row matched a stored one")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
