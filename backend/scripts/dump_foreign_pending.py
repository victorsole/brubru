#!/usr/bin/env python3.12
"""Dump every foreign-language F&T/TED row that still lacks an English
translation sidecar entry. Output: /tmp/foreign_pending.json — a list of
{table, id, lang, title, description}. Description truncated to 1500 chars
to keep the batch prompts bounded.

Used by the Claude Code subagent translation workflow (15 Jun 2026):
Victor's Anthropic API key is unfunded, so bulk translation runs through
his Claude Code "usage" via batched Haiku subagents instead of direct
client.messages.create calls.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SOURCES = {
    "tenders": {
        "pk": "id", "title_col": "title", "desc_col": "description",
        "sidecar": "tenders_translations", "fk": "tender_id",
    },
    "ft_calls_for_proposals": {
        "pk": "id", "title_col": "title", "desc_col": "description",
        "sidecar": "ft_calls_for_proposals_translations", "fk": "call_id",
        "extra_where": "AND is_test IS NOT TRUE",
    },
    "ft_calls_for_tenders": {
        "pk": "id", "title_col": "title", "desc_col": "description",
        "sidecar": "ft_calls_for_tenders_translations", "fk": "tender_uuid",
        "extra_where": "AND is_test IS NOT TRUE",
    },
}


def _db():
    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    url = get_database_url()
    return psycopg2.connect(url)


def main():
    out = []
    for table, spec in SOURCES.items():
        where = (
            f"detected_lang IS NOT NULL "
            f"AND detected_lang NOT IN ('en','es','ca','fr','it','nl','und') "
            f"{spec.get('extra_where','')} "
            f"AND NOT EXISTS ("
            f"  SELECT 1 FROM {spec['sidecar']} s "
            f"  WHERE s.{spec['fk']} = {table}.{spec['pk']} AND s.lang='en'"
            f")"
        )
        sql = (
            f"SELECT {spec['pk']}::text AS id, {spec['title_col']} AS title, "
            f"  COALESCE({spec['desc_col']},'') AS description, detected_lang AS lang "
            f"FROM {table} WHERE {where}"
        )
        conn = _db()
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(sql)
            rows = cur.fetchall()
        finally:
            conn.close()
        for r in rows:
            out.append({
                "table": table,
                "id": r["id"],
                "lang": r["lang"],
                "title": (r["title"] or "").strip()[:300],
                "description": (r["description"] or "").strip()[:1500],
            })
        print(f"[{table}] {len(rows)} foreign rows pending", file=sys.stderr)

    Path("/tmp/foreign_pending.json").write_text(json.dumps(out, ensure_ascii=False))
    print(f"\nTotal pending: {len(out)} -> /tmp/foreign_pending.json", file=sys.stderr)


if __name__ == "__main__":
    main()
