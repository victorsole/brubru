"""Fill tenders.contract_folder_id from each TED notice's stored XML (migration 322, 30 Oct 2026; O104 c).

The root cbc:ContractFolderID of an eForms notice, as the parser now reads it. Chunked by id (5,000 a
transaction, a pause between), and without moving updated_at: the procedure id is a fact the notice always
had, so each chunk sets brubru.keep_change_signal (brubru_touch_if_changed keeps the signal columns). Only
rows still empty are written; a re-run writes nothing. Prints counts; --apply writes.

Run: DATABASE_URL=... python3.12 scripts/backfill_tender_contract_folder_id.py [--apply]
"""
from __future__ import annotations

import argparse
import os
import time

import psycopg2

FOLDER = r"(regexp_match(xml_content, '<cbc:ContractFolderID>([^<]+)</cbc:ContractFolderID>'))[1]"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--chunk", type=int, default=5000)
    args = ap.parse_args()
    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://")
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute(f"SELECT count(*), count({FOLDER}) FROM tenders WHERE contract_folder_id IS NULL AND xml_content IS NOT NULL")
    todo, with_id = cur.fetchone()
    cur.execute("SELECT min(id), max(id) FROM tenders")
    lo, hi = cur.fetchone()
    print(f"[INFO] empty with XML: {todo}, of which a procedure id: {with_id}; ids {lo}..{hi}")
    conn.rollback()
    if not args.apply or not with_id:
        return 0
    written = 0
    for start in range(lo, hi + 1, args.chunk):
        cur.execute("SELECT set_config('brubru.keep_change_signal', txid_current()::text, true)")
        cur.execute(f"UPDATE tenders SET contract_folder_id = {FOLDER} WHERE id >= %s AND id < %s "
                    f"AND contract_folder_id IS NULL AND xml_content IS NOT NULL AND {FOLDER} IS NOT NULL",
                    (start, start + args.chunk))
        written += cur.rowcount
        conn.commit()
        time.sleep(0.5)
    cur.execute("SELECT count(contract_folder_id) FROM tenders")
    print(f"[OK] written {written}; tenders with a procedure id now {cur.fetchone()[0]}")
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
