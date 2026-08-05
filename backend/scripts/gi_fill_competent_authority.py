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
CACHE = Path("/private/tmp/claude-501/-Users-victorsole-Documents-GitHub-brubru/"
             "467dde5d-b102-4717-9258-3805a4ea37f8/scratchpad/ca_per_gi.json")


def new_session():
    """A PLAIN fresh session. Do NOT warm on the SPA home: that GET returns a TSPD challenge
    that poisons the cookie jar and makes the API POST fail (0-resolve bug). A bare session
    hits the API fine; recreate it periodically only to shed any accumulated TSPD throttle."""
    return requests.Session()


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


def resolve_names(ids):
    """id -> name via the search endpoint, with a fresh warmed session + retries/backoff
    (the resolve is tiny — a few dozen unique authority ids — so it must not fail)."""
    out = {}
    ids = list(ids)
    s = new_session()
    for i in range(0, len(ids), 10):        # public-user search cap is 10 ids per request
        chunk = ids[i:i + 10]
        for attempt in range(4):
            try:
                r = s.post(f"{GIVIEW}/country-authorities/search", headers=HDR,
                           data=json.dumps({"countryAuthorityIds": chunk}), timeout=30)
            except Exception:
                r = None
            if r is not None and r.status_code == 200:
                for rec in (r.json() or {}).get("records") or []:
                    nm = " ".join((rec.get("name") or "").split()).strip()
                    if rec.get("id") and nm:
                        out[rec["id"]] = nm[:400]
                break
            time.sleep(2 * (attempt + 1))
            s = new_session()   # re-warm on failure (TSPD throttle)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--resolve-cache", action="store_true",
                    help="skip the GET crawl; use the cached pass-1 scan (fn -> authority ids)")
    ap.add_argument("--refresh-all", action="store_true",
                    help="target EVERY row (not only NULL) and OVERWRITE with the GIView "
                         "Country-authorities value, so the column is uniformly that card")
    a = ap.parse_args()

    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    stats = {"no_detail": 0, "no_authority": 0}

    if a.resolve_cache and CACHE.exists():
        per_gi = {k: v for k, v in json.loads(CACHE.read_text()).items()}
        print(f"[ca] loaded {len(per_gi)} GIs from cache", flush=True)
    else:
        cur.execute("""SELECT file_number, protected_name, gi_identifier FROM gi_details
            WHERE competent_authority IS NULL AND gi_identifier IS NOT NULL
            ORDER BY protected_name""" + (f" LIMIT {a.limit}" if a.limit else ""))
        rows = cur.fetchall()
        print(f"[ca] targets: {len(rows)}", flush=True)
        # pass 1: per-GI authority id refs; re-warm session periodically vs TSPD throttle
        per_gi = {}
        s = new_session()
        for n, (fn, nm, guid) in enumerate(rows, 1):
            refs = gi_authority_ids(s, guid)
            if refs is None:
                stats["no_detail"] += 1
            elif not refs:
                stats["no_authority"] += 1
            else:
                per_gi[fn] = refs
            if n % 400 == 0:
                print(f"  ...scanned {n}/{len(rows)} (kept {len(per_gi)})", flush=True)
                s = new_session()
            time.sleep(0.1)
        CACHE.write_text(json.dumps(per_gi))
        print(f"[ca] scan done, cached {len(per_gi)} GIs", flush=True)

    all_ids = {i for refs in per_gi.values() for i, _ in refs}
    # pass 2: resolve ids -> names (own fresh session + retries)
    names = resolve_names(all_ids)
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
