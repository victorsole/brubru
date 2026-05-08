"""
Backfill ``eu_sanctions`` from the official CSV consolidated list.

Source: webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/content
        (token=dG9rZW4tMjAxNw — embedded in the public download URL on the
        FSD portal; the token is publicly documented for harvesters)

The CSV is "long": ~42k rows, but every sanctioned entity (person /
company / vessel) appears MULTIPLE times — once per name variant +
once per address + once per birth detail + once per ID document + once
per citizenship. Rows for the same entity share the same
``Entity_logical_id``.

This script:
  1. Downloads the CSV.
  2. Groups rows by (Entity_logical_id, Programme) → one canonical record.
  3. Aggregates aliases / addresses / birth_details / IDs / citizenships
     into JSONB / TEXT[] columns.
  4. UPSERTs into ``eu_sanctions``.

Re-running is idempotent — every row is overwritten with the latest
upstream content. New entities are added; entities removed upstream are
left in place (we never delete rows in a backfill — that's the
delisting scraper's job, future work).

Run:
    python3.12 backend/scripts/backfill_eu_sanctions.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_eu_sanctions.py --apply
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

import psycopg2
from psycopg2.extras import Json

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
SOURCE_URL = (
    "https://webgate.ec.europa.eu/fsd/fsf/public/files/csvFullSanctionsList/"
    "content?token=dG9rZW4tMjAxNw"
)


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_csv() -> bytes:
    req = urllib_request.Request(
        SOURCE_URL,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)",
            "Accept": "text/csv,application/octet-stream",
        },
    )
    print("[INFO] Downloading EU Sanctions CSV...", flush=True)
    with urllib_request.urlopen(req, timeout=60) as r:
        body = r.read()
    print(f"[INFO] Downloaded {len(body):,} bytes", flush=True)
    return body


def parse_date(value: Optional[str]) -> Optional[str]:
    """CSV uses 'YYYY-MM-DD' for some columns and 'DD/MM/YYYY' for Date_file."""
    if not value:
        return None
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def aggregate(rows: list[dict[str, str]]) -> dict[str, Any]:
    """Collapse all CSV rows for one (entity, programme) into one record."""
    first = rows[0]
    canonical_name = ""
    canonical_first = canonical_middle = canonical_last = ""
    canonical_gender = canonical_title = canonical_function = ""

    aliases: list[dict[str, Any]] = []
    seen_aliases: set[tuple] = set()

    addresses: list[dict[str, Any]] = []
    seen_addr: set[tuple] = set()

    birth_details: list[dict[str, Any]] = []
    seen_birth: set[tuple] = set()

    identification_documents: list[dict[str, Any]] = []
    seen_id: set[tuple] = set()

    citizenships: list[str] = []
    seen_citi: set[str] = set()

    for row in rows:
        # Names / aliases
        whole = (row.get("Naal_wholename") or "").strip()
        if whole:
            tup = (
                whole,
                row.get("Naal_lastname") or "",
                row.get("Naal_firstname") or "",
                row.get("Naal_gender") or "",
                row.get("Naal_language") or "",
            )
            if tup not in seen_aliases:
                seen_aliases.add(tup)
                aliases.append({
                    "whole_name": whole,
                    "first_name": row.get("Naal_firstname") or None,
                    "middle_name": row.get("Naal_middlename") or None,
                    "last_name": row.get("Naal_lastname") or None,
                    "gender": row.get("Naal_gender") or None,
                    "title": row.get("Naal_title") or None,
                    "function": row.get("Naal_function") or None,
                    "language": row.get("Naal_language") or None,
                })
            # Take first non-empty as canonical
            if not canonical_name:
                canonical_name = whole
                canonical_first = row.get("Naal_firstname") or ""
                canonical_middle = row.get("Naal_middlename") or ""
                canonical_last = row.get("Naal_lastname") or ""
                canonical_gender = row.get("Naal_gender") or ""
                canonical_title = row.get("Naal_title") or ""
                canonical_function = row.get("Naal_function") or ""

        # Addresses
        street = (row.get("Addr_street") or "").strip()
        city = (row.get("Addr_city") or "").strip()
        country = (row.get("Addr_country") or "").strip()
        if street or city or country:
            tup = (street, city, row.get("Addr_zipcode") or "", country)
            if tup not in seen_addr:
                seen_addr.add(tup)
                addresses.append({
                    "number": row.get("Addr_number") or None,
                    "street": street or None,
                    "zipcode": row.get("Addr_zipcode") or None,
                    "city": city or None,
                    "country": country or None,
                    "other": row.get("Addr_other") or None,
                })

        # Birth
        b_date = parse_date(row.get("Birt_date"))
        b_place = (row.get("Birt_place") or "").strip()
        b_country = (row.get("Birt_country") or "").strip()
        if b_date or b_place or b_country:
            tup = (b_date, b_place, b_country)
            if tup not in seen_birth:
                seen_birth.add(tup)
                birth_details.append({
                    "date": b_date,
                    "place": b_place or None,
                    "country": b_country or None,
                })

        # Identification documents
        i_number = (row.get("Iden_number") or "").strip()
        i_country = (row.get("Iden_country") or "").strip()
        if i_number or i_country:
            tup = (i_number, i_country)
            if tup not in seen_id:
                seen_id.add(tup)
                identification_documents.append({
                    "number": i_number or None,
                    "country": i_country or None,
                })

        # Citizenship
        c_country = (row.get("Citi_country") or "").strip()
        if c_country and c_country not in seen_citi:
            seen_citi.add(c_country)
            citizenships.append(c_country)

    return {
        "entity_logical_id": int(first["Entity_logical_id"]),
        "subject_type": first["Subject_type"],
        "programme": first["Programme"],
        "legal_basis_title": first.get("Leba_numtitle") or None,
        "legal_basis_publication_date": parse_date(first.get("Leba_publication_date")),
        "legal_basis_url": first.get("Leba_url") or None,
        "full_name": canonical_name or None,
        "first_name": canonical_first or None,
        "middle_name": canonical_middle or None,
        "last_name": canonical_last or None,
        "gender": canonical_gender or None,
        "title": canonical_title or None,
        "function": canonical_function or None,
        "aliases": aliases,
        "addresses": addresses,
        "birth_details": birth_details,
        "identification_documents": identification_documents,
        "citizenships": citizenships,
        "remark": first.get("Entity_remark") or None,
        "date_file": parse_date(first.get("Date_file")),
        "eu_ref_num": first.get("EU_ref_num") or None,
    }


UPSERT_SQL = """
INSERT INTO eu_sanctions (
    entity_logical_id, subject_type, programme,
    legal_basis_title, legal_basis_publication_date, legal_basis_url,
    full_name, first_name, middle_name, last_name,
    gender, title, function,
    aliases, addresses, birth_details, identification_documents, citizenships,
    remark, date_file, eu_ref_num,
    updated_at
) VALUES (
    %(entity_logical_id)s, %(subject_type)s, %(programme)s,
    %(legal_basis_title)s, %(legal_basis_publication_date)s, %(legal_basis_url)s,
    %(full_name)s, %(first_name)s, %(middle_name)s, %(last_name)s,
    %(gender)s, %(title)s, %(function)s,
    %(aliases)s, %(addresses)s, %(birth_details)s, %(identification_documents)s, %(citizenships)s,
    %(remark)s, %(date_file)s, %(eu_ref_num)s,
    NOW()
)
ON CONFLICT (entity_logical_id, programme) DO UPDATE SET
    subject_type = EXCLUDED.subject_type,
    legal_basis_title = EXCLUDED.legal_basis_title,
    legal_basis_publication_date = EXCLUDED.legal_basis_publication_date,
    legal_basis_url = EXCLUDED.legal_basis_url,
    full_name = EXCLUDED.full_name,
    first_name = EXCLUDED.first_name,
    middle_name = EXCLUDED.middle_name,
    last_name = EXCLUDED.last_name,
    gender = EXCLUDED.gender,
    title = EXCLUDED.title,
    function = EXCLUDED.function,
    aliases = EXCLUDED.aliases,
    addresses = EXCLUDED.addresses,
    birth_details = EXCLUDED.birth_details,
    identification_documents = EXCLUDED.identification_documents,
    citizenships = EXCLUDED.citizenships,
    remark = EXCLUDED.remark,
    date_file = EXCLUDED.date_file,
    eu_ref_num = EXCLUDED.eu_ref_num,
    updated_at = NOW();
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5, help="Dry-run limit (apply mode ignores)")
    ap.add_argument("--source", type=str, default=None, help="Optional local CSV path (skip download)")
    args = ap.parse_args()

    # Source bytes
    if args.source:
        body = Path(args.source).read_bytes()
        print(f"[INFO] Read {len(body):,} bytes from {args.source}")
    else:
        body = fetch_csv()

    text = body.decode("utf-8-sig", errors="replace")
    raw_reader = csv.reader(io.StringIO(text), delimiter=";")
    header = next(raw_reader)
    # The CSV repeats some column names (Entity_logical_id appears 6 times,
    # once per sub-record block). DictReader collapses duplicates → unusable.
    # We index by position and pick the FIRST instance for ambiguous keys.
    seen_pos: dict[str, int] = {}
    for i, name in enumerate(header):
        if name not in seen_pos:
            seen_pos[name] = i

    def col(row: list[str], name: str) -> str:
        idx = seen_pos.get(name, -1)
        if idx < 0 or idx >= len(row):
            return ""
        return row[idx] or ""

    # For sub-record fields (Naal_*, Addr_*, etc.) the first-seen index IS the
    # correct one (each appears only once in the header). The aggregator below
    # works off the row dict shape, so we still need a per-row dict — we build
    # one using the first-seen indexing rule.
    def row_to_dict(row: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for k, idx in seen_pos.items():
            if idx < len(row):
                out[k] = row[idx]
        return out

    by_entity: dict[tuple[int, str], list[dict[str, str]]] = defaultdict(list)
    for raw in raw_reader:
        if not raw:
            continue
        eid_str = col(raw, "Entity_logical_id")
        try:
            eid = int(eid_str)
        except ValueError:
            continue
        prog = col(raw, "Programme").strip()
        if not prog:
            continue
        by_entity[(eid, prog)].append(row_to_dict(raw))

    print(f"[INFO] Grouped {sum(len(v) for v in by_entity.values()):,} rows into "
          f"{len(by_entity):,} (entity, programme) keys")

    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing", file=sys.stderr)
        sys.exit(1)
    conn = psycopg2.connect(db)
    cur = conn.cursor()

    upserted = 0
    skipped = 0
    seen_keys = list(by_entity.keys())
    if not args.apply:
        seen_keys = seen_keys[: args.limit]

    for i, key in enumerate(seen_keys, 1):
        rows = by_entity[key]
        record = aggregate(rows)
        if not record["full_name"] and record["subject_type"] == "P":
            # Person without any Naal name? Skip — likely a malformed row.
            skipped += 1
            continue

        # JSON-encode the structured columns for psycopg2.
        params = dict(record)
        params["aliases"] = Json(record["aliases"])
        params["addresses"] = Json(record["addresses"])
        params["birth_details"] = Json(record["birth_details"])
        params["identification_documents"] = Json(record["identification_documents"])
        params["citizenships"] = record["citizenships"]  # text[] is fine as Python list

        if args.apply:
            try:
                cur.execute(UPSERT_SQL, params)
                upserted += 1
                if upserted % 500 == 0:
                    conn.commit()
                    print(f"  [{upserted:,}] committed", flush=True)
            except Exception as exc:
                conn.rollback()
                skipped += 1
                print(f"  [{i}] error on {key}: {exc}", flush=True)
        else:
            print(f"  [{i:3}] (entity={key[0]} programme={key[1]}) "
                  f"name={record['full_name'][:60] if record['full_name'] else '—'} "
                  f"aliases={len(record['aliases'])} addr={len(record['addresses'])} "
                  f"birth={len(record['birth_details'])} ids={len(record['identification_documents'])} "
                  f"citi={len(record['citizenships'])}", flush=True)

    if args.apply:
        conn.commit()

    print()
    print(f"[DONE] upserted={upserted:,} skipped={skipped:,}{' (DRY)' if not args.apply else ''}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
