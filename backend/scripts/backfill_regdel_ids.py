"""
backfill_regdel_ids — one-shot fetch of the regdel record corpus, then map
each secondary_acts row to its regdel internal id (so the v1 endpoint can
emit the specific record URL instead of the search URL).

Side effect: also backfills missing CELEX values from regdel's celexNumber
field — adopted DAs in regdel carry the CELEX once published.

Run modes:
  python3.12 backend/scripts/backfill_regdel_ids.py            # fetch + apply
  python3.12 backend/scripts/backfill_regdel_ids.py --dry-run  # show diff only

The regdel API requires a CSRF dance:
  1. GET https://webgate.ec.europa.eu/regdel/ → sets cookies (JSESSIONID + XSRF-TOKEN)
  2. POST /regdel/web/delegatedActs with X-XSRF-TOKEN header from the cookie
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import logging
import os
import sys
import urllib.request
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("backfill-regdel-ids")

REGDEL_HOME = "https://webgate.ec.europa.eu/regdel/"
REGDEL_DA_SEARCH = "https://webgate.ec.europa.eu/regdel/web/delegatedActs"


def fetch_all_regdel_acts() -> list[dict]:
    """Two-step CSRF dance to fetch the full regdel corpus (~2000+ records)."""
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    opener.addheaders = [("User-Agent", "Mozilla/5.0 Brubru/1.0")]
    log.info("GET %s (seed cookies)", REGDEL_HOME)
    opener.open(REGDEL_HOME, timeout=30).read()
    csrf = next((c.value for c in cj if "xsrf" in c.name.lower()), None)
    if not csrf:
        raise RuntimeError("regdel did not set an XSRF-TOKEN cookie")
    log.info("CSRF token acquired: %s…", csrf[:16])
    body = json.dumps({"language": "en"}).encode()
    req = urllib.request.Request(
        REGDEL_DA_SEARCH, data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-XSRF-TOKEN": csrf,
            "User-Agent": "Mozilla/5.0 Brubru/1.0",
        },
    )
    r = opener.open(req, timeout=120)
    payload = json.loads(r.read())
    items = payload.get("list") or []
    log.info("regdel returned %d records", len(items))
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    eng = create_engine(os.environ["DATABASE_URL"])

    items = fetch_all_regdel_acts()
    # Map cCode → (id, celexNumber, status)
    cmap: dict[str, dict] = {}
    for it in items:
        c = it.get("cCode")
        if c:
            cmap[c.strip()] = {
                "id": it.get("id"),
                "celex": it.get("celexNumber"),
                "status": it.get("delegatedActStatus"),
            }
    log.info("cCode → regdel-id map: %d entries", len(cmap))

    # Update secondary_acts rows whose reference matches a cCode and whose
    # regdel_id is currently NULL or whose celex is currently NULL.
    with eng.begin() as c:
        rows = c.execute(text("""
            SELECT id, reference, celex, regdel_id
            FROM secondary_acts
            WHERE act_type = 'delegated' AND reference IS NOT NULL
        """)).fetchall()
        n_match = n_id_set = n_celex_set = 0
        for row in rows:
            ref = (row[1] or "").strip()
            rec = cmap.get(ref)
            if not rec:
                continue
            n_match += 1
            updates = {}
            if rec["id"] is not None and row[3] is None:
                updates["regdel_id"] = int(rec["id"])
                n_id_set += 1
            if rec["celex"] and not (row[2] or "").strip():
                updates["celex"] = rec["celex"].strip()
                n_celex_set += 1
            if updates and not args.dry_run:
                set_clause = ", ".join(f"{k} = :{k}" for k in updates)
                c.execute(text(f"UPDATE secondary_acts SET {set_clause} WHERE id = :id"),
                          {**updates, "id": row[0]})
        log.info("matched %d/%d rows by cCode; %sset regdel_id on %d; backfilled celex on %d",
                 n_match, len(rows), "[DRY] would " if args.dry_run else "", n_id_set, n_celex_set)


if __name__ == "__main__":
    main()
