"""
Ingest the RegDel basic-acts export and use it to enrich eu_laws.policy_area
on rows that already exist in our corpus.

Source:
  https://webgate.ec.europa.eu/regdel/web/basicActs/excel?lang=en&filter=...

Each row has: Complete title, Celex number, Policy area, Type of act, Status.

We don't import these as new eu_laws (the corpus is already populated from
LEG_2025-11). Instead, we update the `policy_area` column on existing rows
when RegDel has a real DG-level classification (e.g. "SANTE", "TAXUD",
"AGRI") and our row's policy_area is null.

Run:
    python3.12 backend/scripts/ingest_regdel_basic_acts.py            # dry-run
    python3.12 backend/scripts/ingest_regdel_basic_acts.py --apply
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict

import pandas as pd
import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0) Chrome/126.0.0.0"

URL = (
    "https://webgate.ec.europa.eu/regdel/web/basicActs/excel?lang=en&filter="
    + urllib.parse.quote('{"rowsPerPage":6,"firstRowOffset":0,"language":"en"}')
)


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    print(f"[INFO] fetching RegDel basic-acts export...")
    req = urllib.request.Request(URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        bytes_ = r.read()
    df = pd.read_excel(io.BytesIO(bytes_), engine="xlrd")
    print(f"  {len(df)} rows in Excel")

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    matched = updated = unchanged = 0
    for _, row in df.iterrows():
        celex = row.get("Celex number")
        policy = row.get("Policy area")
        if not isinstance(celex, str) or not celex.strip():
            continue
        if not isinstance(policy, str) or not policy.strip():
            continue
        celex = celex.strip()
        policy = policy.strip()

        cur.execute(
            "SELECT policy_area FROM eu_laws WHERE celex = %s LIMIT 1",
            (celex,),
        )
        existing = cur.fetchone()
        if not existing:
            continue
        matched += 1

        if existing[0] and existing[0].strip():
            unchanged += 1
            continue

        if args.apply:
            cur.execute(
                "UPDATE eu_laws SET policy_area = %s, updated_at = NOW() WHERE celex = %s",
                (policy, celex),
            )
        updated += 1

    if args.apply:
        conn.commit()
    conn.close()

    print(
        f"[DONE] matched={matched} updated={updated} unchanged={unchanged}"
        f"{' (applied)' if args.apply else ' (dry-run)'}"
    )


if __name__ == "__main__":
    main()
