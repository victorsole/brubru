"""
Populate gi_details with the geographical area (demarcation) for EU geographical
indications, one country set at a time.

Usage:
  python3.12 scripts/extract_gi_geo.py --countries ES,BE,IT           # full
  python3.12 scripts/extract_gi_geo.py --countries IT --limit 60      # sample
  python3.12 scripts/extract_gi_geo.py --countries BE --dry-run       # no DB write

Roster = eAmbrosia (authoritative superset, includes pending 'applied' files).
Documents = merged GIView detail API + eAmbrosia, English rendition preferred.
Extraction = precise multilingual demarcation heading (see gi_geo_extractor).
Cached to gi_details; the /giview endpoint and the GI maps read from there.

Prints an honest coverage report: resolved / approximate / no_source / pending.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from psycopg2.extras import Json

from core.config import settings
from services.gi.gi_geo_extractor import GiGeoExtractor, roster

_UPSERT = """
INSERT INTO gi_details (
    file_number, gi_identifier, protected_name, gi_type, product_type, countries,
    status, eu_protection_date, classification, legal_instrument, publications,
    competent_authority, geographical_area, geo_nuts, geo_heading, geo_source_url,
    geo_source_type, geo_confidence, geo_status, extracted_at
) VALUES (
    %(file_number)s, %(gi_identifier)s, %(protected_name)s, %(gi_type)s, %(product_type)s,
    %(countries)s, %(status)s, %(eu_protection_date)s, %(classification)s,
    %(legal_instrument)s, %(publications)s, %(competent_authority)s, %(geographical_area)s,
    %(geo_nuts)s, %(geo_heading)s, %(geo_source_url)s, %(geo_source_type)s, %(geo_confidence)s,
    %(geo_status)s, NOW()
)
ON CONFLICT (file_number) DO UPDATE SET
    gi_identifier=EXCLUDED.gi_identifier, protected_name=EXCLUDED.protected_name,
    gi_type=EXCLUDED.gi_type, product_type=EXCLUDED.product_type, countries=EXCLUDED.countries,
    status=EXCLUDED.status, eu_protection_date=EXCLUDED.eu_protection_date,
    classification=EXCLUDED.classification, legal_instrument=EXCLUDED.legal_instrument,
    publications=EXCLUDED.publications, competent_authority=EXCLUDED.competent_authority,
    geographical_area=EXCLUDED.geographical_area, geo_nuts=EXCLUDED.geo_nuts,
    geo_heading=EXCLUDED.geo_heading,
    geo_source_url=EXCLUDED.geo_source_url, geo_source_type=EXCLUDED.geo_source_type,
    geo_confidence=EXCLUDED.geo_confidence, geo_status=EXCLUDED.geo_status,
    extracted_at=NOW(), updated_at=NOW();
"""


def _jsonify(row: dict) -> dict:
    r = dict(row)
    # Wrap every JSONB-bound value in Json() unconditionally: Json("a string") -> a
    # valid JSON string literal, so producer-group names (bare strings) no longer
    # break the JSONB columns the way an unwrapped str would.
    for k in ("classification", "legal_instrument", "publications", "competent_authority"):
        if r.get(k) is not None:
            r[k] = Json(r[k])
    ed = r.get("eu_protection_date")
    r["eu_protection_date"] = (ed[:10] if isinstance(ed, str) and ed else None)
    return r


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--countries", required=True, help="comma list, e.g. ES,BE,IT")
    ap.add_argument("--limit", type=int, default=0, help="sample first N (0 = all)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--resume", action="store_true", help="skip GIs already in gi_details")
    ap.add_argument("--restatus", default="", help="re-process only GIs at these geo_status values, e.g. pending,none")
    ap.add_argument("--jsonl", default="", help="also append each result to this JSONL file")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds to pause between GIs (polite throttle for EUR-Lex)")
    ap.add_argument("--log", default="")
    a = ap.parse_args()
    countries = [c.strip().upper() for c in a.countries.split(",") if c.strip()]

    logf = open(a.log, "w") if a.log else sys.stdout
    def log(m): print(m, file=logf, flush=True)

    # DB writer with reconnect-on-drop (cloud Postgres drops idle/long connections).
    class Writer:
        def __init__(self):
            self.conn = None; self._open()
        def _open(self):
            self.conn = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20)
            self.conn.autocommit = True; self.cur = self.conn.cursor()
        def upsert(self, params):
            for attempt in (1, 2):
                try:
                    self.cur.execute(_UPSERT, params); return True
                except (psycopg2.OperationalError, psycopg2.InterfaceError):
                    try: self.conn.close()
                    except Exception: pass
                    self._open()                         # reconnect and retry once
                except Exception as e:
                    log(f"  ! upsert {params.get('file_number')}: {type(e).__name__} {str(e)[:70]}")
                    return False
            return False
        def done_set(self):
            self.cur.execute("SELECT file_number FROM gi_details")
            return {r[0] for r in self.cur.fetchall()}
        def status_map(self):
            self.cur.execute("SELECT file_number, geo_status FROM gi_details")
            return dict(self.cur.fetchall())

    writer = None if a.dry_run else Writer()

    gis = roster(countries)
    if a.restatus and writer:
        want = {s.strip() for s in a.restatus.split(",") if s.strip()}
        smap = writer.status_map()
        gis = [g for g in gis if smap.get(g.get("fileNumber")) in want]
        log(f"[restatus] re-processing {len(gis)} GIs currently at status {want}")
    elif a.resume and writer:
        done = writer.done_set()
        gis = [g for g in gis if g.get("fileNumber") not in done]
        log(f"[resume] skipping {len(done)} already in gi_details")
    if a.limit:
        gis = gis[:a.limit]
    log(f"[extract_gi_geo] {countries}: {len(gis)} GIs "
        f"({'dry-run' if a.dry_run else 'writing gi_details'})")

    jsonlf = open(a.jsonl, "a") if a.jsonl else None
    rows, t0 = [], time.time()
    with GiGeoExtractor() as ex:
        for n, amb in enumerate(gis, 1):
            try:
                row = ex.extract(amb)
            except Exception as e:                       # never let one GI kill the run
                row = {"file_number": amb.get("fileNumber"),
                       "protected_name": (amb.get("protectedNames") or ["?"])[0],
                       "geo_status": "pending", "geo_confidence": "none"}
                log(f"  ! {row['file_number']}: {type(e).__name__} {str(e)[:80]}")
            rows.append(row)
            if jsonlf:
                jsonlf.write(json.dumps(row, ensure_ascii=False, default=str) + "\n"); jsonlf.flush()
            if writer:
                writer.upsert(_jsonify({**{k: None for k in _COLS}, **row}))
            if n % 20 == 0:
                res = sum(1 for x in rows if x.get("geo_status") == "resolved")
                log(f"  ...{n}/{len(gis)} | resolved {res} | {time.time()-t0:.0f}s")
            if a.delay:
                time.sleep(a.delay)

    by_status = Counter(x.get("geo_status") for x in rows)
    by_conf = Counter(x.get("geo_confidence") for x in rows)
    log(f"DONE {len(rows)} GIs | status={dict(by_status)} | confidence={dict(by_conf)}")
    clean = by_status.get("resolved", 0)
    log(f"  CLEAN (resolved): {clean}/{len(rows)} = {100*clean//max(len(rows),1)}%")
    if jsonlf:
        jsonlf.close()
    if writer:
        writer.conn.close()


_COLS = ["file_number", "gi_identifier", "protected_name", "gi_type", "product_type",
         "countries", "status", "eu_protection_date", "classification", "legal_instrument",
         "publications", "competent_authority", "geographical_area", "geo_nuts", "geo_heading",
         "geo_source_url", "geo_source_type", "geo_confidence", "geo_status"]

if __name__ == "__main__":
    main()
