#!/usr/bin/env python3.12
"""Read /tmp/trans_batch_*.json files (sub-agent output from the bulk
translation workflow) and upsert into the matching sidecar tables.

Each batch file is a JSON list of objects:
    {"table": "...", "id": "<pk>", "en_title": "...", "en_description": "..."}

Idempotent (ON CONFLICT DO UPDATE).
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SIDECARS = {
    "tenders": {
        "table": "tenders_translations", "fk": "tender_id", "pk_cast": "integer",
    },
    "ft_calls_for_proposals": {
        "table": "ft_calls_for_proposals_translations", "fk": "call_id",
        "pk_cast": "uuid",
    },
    "ft_calls_for_tenders": {
        "table": "ft_calls_for_tenders_translations", "fk": "tender_uuid",
        "pk_cast": "uuid",
    },
}

ENGINE = "claude-haiku-4-5-subagent"


def _db():
    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    url = get_database_url()
    return psycopg2.connect(url)


def main(pattern: str = "/tmp/trans_batch_*.json"):
    files = sorted(glob.glob(pattern))
    if not files:
        print(f"no files matched {pattern}", file=sys.stderr)
        return 1

    rows = []
    for fp in files:
        try:
            data = json.loads(Path(fp).read_text())
            if isinstance(data, list):
                rows.extend(data)
        except Exception as e:
            print(f"[warn] could not parse {fp}: {e}", file=sys.stderr)
    print(f"loaded {len(rows)} translated rows from {len(files)} batch files")

    conn = _db()
    cur = conn.cursor()
    ok = 0
    err = 0
    for r in rows:
        table = r.get("table")
        spec = SIDECARS.get(table)
        if not spec:
            err += 1
            continue
        en_title = (r.get("en_title") or "").strip()
        en_desc = (r.get("en_description") or "").strip()
        if not en_title:
            err += 1
            continue
        try:
            cur.execute(
                f"INSERT INTO {spec['table']} ({spec['fk']}, lang, title, summary, engine) "
                f"VALUES (%s::{spec['pk_cast']}, 'en', %s, %s, %s) "
                f"ON CONFLICT ({spec['fk']}, lang) DO UPDATE SET "
                f"  title=EXCLUDED.title, summary=EXCLUDED.summary, "
                f"  engine=EXCLUDED.engine, translated_at=now()",
                (r["id"], en_title[:500], (en_desc or en_title)[:1800], ENGINE),
            )
            ok += 1
        except Exception as e:
            err += 1
            print(f"[warn] {table}/{r.get('id')}: {str(e)[:120]}")
            conn.rollback()
            continue
    conn.commit()
    conn.close()
    print(f"upserted ok={ok} err={err}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
