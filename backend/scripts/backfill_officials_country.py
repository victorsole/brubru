"""
Derive country (ISO-3) on eu_officials rows whose `role` field is a country
name in caps. The Council scraper writes country names directly to role
(e.g., role='GERMANY'). This script normalises that to the canonical
country column.

No upstream calls — pure data hygiene from the existing scrape.

Run:
    python3.12 backend/scripts/backfill_officials_country.py            # dry-run
    python3.12 backend/scripts/backfill_officials_country.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


# EU-27 + UK + a few common partner countries.
COUNTRY_MAP: Dict[str, str] = {
    "AUSTRIA": "AUT",
    "BELGIUM": "BEL",
    "BULGARIA": "BGR",
    "CROATIA": "HRV",
    "CYPRUS": "CYP",
    "CZECHIA": "CZE",
    "CZECH REPUBLIC": "CZE",
    "DENMARK": "DNK",
    "ESTONIA": "EST",
    "FINLAND": "FIN",
    "FRANCE": "FRA",
    "GERMANY": "DEU",
    "GREECE": "GRC",
    "HUNGARY": "HUN",
    "IRELAND": "IRL",
    "ITALY": "ITA",
    "LATVIA": "LVA",
    "LITHUANIA": "LTU",
    "LUXEMBOURG": "LUX",
    "MALTA": "MLT",
    "NETHERLANDS": "NLD",
    "THE NETHERLANDS": "NLD",
    "POLAND": "POL",
    "PORTUGAL": "PRT",
    "ROMANIA": "ROU",
    "SLOVAKIA": "SVK",
    "SLOVENIA": "SVN",
    "SPAIN": "ESP",
    "SWEDEN": "SWE",
    "UNITED KINGDOM": "GBR",
    "NORWAY": "NOR",
    "SWITZERLAND": "CHE",
    "UKRAINE": "UKR",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id::text, role, country
          FROM eu_officials
         WHERE country IS NULL AND role IS NOT NULL
        """
    )
    rows = cur.fetchall()
    cur.close()

    matched = 0
    by_country = {}
    for row_id, role, _ in rows:
        iso = COUNTRY_MAP.get((role or "").strip().upper())
        if not iso:
            continue
        matched += 1
        by_country[iso] = by_country.get(iso, 0) + 1
        if args.apply:
            cur2 = conn.cursor()
            cur2.execute(
                "UPDATE eu_officials SET country = %s, last_updated = NOW() WHERE id = %s",
                (iso, row_id),
            )
            cur2.close()

    if args.apply:
        conn.commit()
    conn.close()

    print(f"[INFO] {len(rows)} candidate rows; {matched} matched a country name")
    for iso, n in sorted(by_country.items(), key=lambda kv: -kv[1]):
        print(f"  {iso}: {n}")
    print(f"[DONE]{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    main()
