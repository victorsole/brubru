"""
Cleanup pypdf concatenation artifacts in eu_officials.

The Whoiswho PDF parser sometimes captures lines like
'Vice-PresidentMr Vincent CADOR' where pypdf glued the previous section
header to the next person's name without a space. Re-split such rows on
the (Mr|Ms|Mrs|Mme|Dr) boundary, putting the prefix into role (or
discarding it if role already populated) and the rest into name+title.

Run:
    python3.12 backend/scripts/cleanup_officials_glued_names.py            # dry-run
    python3.12 backend/scripts/cleanup_officials_glued_names.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

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


# Catches "<header text ending lowercase>(Mr|Ms|...)\s+<Name>"
SPLIT_RE = re.compile(r"^(.+?[a-zà-ÿ])(Mr|Ms|Mrs|Mme|Dr)\s+(.+)$")


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
        r"SELECT id::text, name, title, role FROM eu_officials WHERE name ~ '[a-z](Mr|Ms|Mrs|Mme|Dr) [A-Z]'"
    )
    rows = cur.fetchall()
    print(f"[INFO] {len(rows)} candidate rows (apply={args.apply})")

    fixed = skipped = 0
    for row_id, name, title, role in rows:
        m = SPLIT_RE.match(name)
        if not m:
            skipped += 1
            continue
        prefix, new_title, new_rest = m.group(1).strip(), m.group(2), m.group(3).strip()
        # The "name" we want is the part AFTER the title.
        new_name = new_rest
        # Don't lose the prefix — promote it to role when role is empty.
        new_role = role or prefix
        if args.apply:
            cur.execute(
                """
                UPDATE eu_officials
                   SET name = %s, title = %s, role = %s, last_updated = NOW()
                 WHERE id = %s
                """,
                (new_name[:200], new_title, new_role[:300], row_id),
            )
        fixed += 1

    if args.apply:
        conn.commit()
    conn.close()
    print(f"[DONE] fixed={fixed} skipped={skipped}{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    main()
