"""
Fill gi_details.competent_authority from the GIView "Country authorities" card.

Every GI profile on GIView (EUIPO) carries a Country-authorities card. It is served by two
backend API calls (both work server-side, no browser needed):

  1. GET  /giview/api/geographical-indications/{EUGI-guid}?language=EN
         -> extendedData.countryAuthorities = [{id, representative}]
  2. POST /giview/api/country-authorities/search   body {"countryAuthorityIds": [...]}
         -> records = [{id, name, ...}]     (name = the competent authority)

Idempotent: only fills NULL competent_authority rows; self-resuming. competent_authority
is jsonb (a scalar string).

  python3.12 scripts/gi_fill_competent_authority.py --dry-run --limit 20
  python3.12 scripts/gi_fill_competent_authority.py            # full (background)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
import requests
from core.config import settings

GIVIEW = "https://www.tmdn.org/giview/api"
HDR = {"User-Agent": "Mozilla/5.0", "Accept": "application/json", "Content-Type": "application/json"}


def gi_authority_ids(s, guid):
    """[(id, representative)] for a GI, or None on failure."""
    try:
        r = s.get(f"{GIVIEW}/geographical-indications/{guid}?language=EN", headers=HDR, timeout=30)
    except Exception:
        return None
    if r.status_code != 200:
        return None
    ed = (r.json() or {}).get("extendedData") or {}
    return [(x.get("id"), x.get("representative")) for x in (ed.get("countryAuthorities") or []) if x.get("id")]


def resolve_names(s, ids):
    """id -> name, resolved in batches via the search endpoint."""
    out = {}
    ids = list(ids)
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        try:
            r = s.post(f"{GIVIEW}/country-authorities/search", headers=HDR,
                       data=json.dumps({"countryAuthorityIds": chunk}), timeout=30)
        except Exception:
            continue
        if r.status_code == 200:
            for rec in (r.json() or {}).get("records") or []:
                nm = " ".join((rec.get("name") or "").split()).strip()
                if rec.get("id") and nm:
                    out[rec["id"]] = nm[:400]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()

    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    cur.execute("""SELECT file_number, protected_name, gi_identifier FROM gi_details
        WHERE competent_authority IS NULL AND gi_identifier IS NOT NULL
        ORDER BY protected_name""" + (f" LIMIT {a.limit}" if a.limit else ""))
    rows = cur.fetchall()
    print(f"[ca] targets: {len(rows)}", flush=True)

    s = requests.Session()
    # pass 1: per-GI authority id refs
    per_gi = {}
    all_ids = set()
    stats = {"no_detail": 0, "no_authority": 0}
    for n, (fn, nm, guid) in enumerate(rows, 1):
        refs = gi_authority_ids(s, guid)
        if refs is None:
            stats["no_detail"] += 1; continue
        if not refs:
            stats["no_authority"] += 1; continue
        per_gi[fn] = refs
        all_ids.update(i for i, _ in refs)
        if n % 200 == 0:
            print(f"  ...scanned {n}/{len(rows)}", flush=True)
        time.sleep(0.12)

    # pass 2: resolve ids -> names
    names = resolve_names(s, all_ids)
    print(f"[ca] resolved {len(names)} authority names for {len(all_ids)} ids", flush=True)

    # pass 3: write (prefer the representative authority)
    filled = 0
    for fn, refs in per_gi.items():
        rep = [i for i, r in refs if r] or [i for i, _ in refs]
        chosen = next((names[i] for i in rep if i in names), None) \
            or next((names[i] for i, _ in refs if i in names), None)
        if not chosen:
            continue
        filled += 1
        if a.dry_run:
            print(f"  {fn:16} -> {chosen[:70]}")
        else:
            cur.execute("UPDATE gi_details SET competent_authority=%s::jsonb WHERE file_number=%s",
                        (json.dumps(chosen), fn))
    print(f"[ca] filled: {filled} | {stats}")
    c.close()


if __name__ == "__main__":
    main()
