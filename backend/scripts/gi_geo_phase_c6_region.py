"""
Phase C.6: region-level recovery. The earlier passes only used NUTS3, so GIs whose
area is a whole region never matched — "Grappa lombarda" (Lombardy = NUTS2),
"Hessischer Handkäse" (Hessen = NUTS1), "Schwäbische Maultaschen" (Baden-
Württemberg = NUTS1).

Match name+text against the NUTS2 gazetteer, then NUTS1 (prefer the finer level).
The adjectival title often won't match ("Schwäbischer" != "Schwaben") but the area
text usually names the region outright ("all of Baden-Württemberg", "Region of
Lombardy"). Generic compass NUTS1 names (Italy's "Sud"/"Isole") are already dropped
by the gazetteer's all-generic filter. Runs only on still-unmatched GIs.

  python3.12 scripts/gi_geo_phase_c6_region.py --dry-run
  python3.12 scripts/gi_geo_phase_c6_region.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg2
from core.config import settings
from gi_geo_phase_c import load_gazetteer, match_units, write_geometry as write_nuts_geom


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    print("[phaseC6] loading NUTS2 + NUTS1 gazetteers...", flush=True)
    gaz2, mw2 = load_gazetteer(cur, "NUTS2")
    gaz1, mw1 = load_gazetteer(cur, "NUTS1")
    # NUTS1 that is the SOLE NUTS1 of its country == the whole country (Ireland,
    # Denmark ...). Matching a specific-place GI to a country-sized unit is wrong
    # (Achill Island -> all of Ireland); drop those.
    cur.execute("SELECT unit_code FROM gisco_units WHERE level='NUTS1' AND country IN (SELECT country FROM gisco_units WHERE level='NUTS1' GROUP BY country HAVING count(*)=1)")
    whole_country = {r[0] for r in cur.fetchall()}

    cur.execute("""SELECT file_number, protected_name, countries, geographical_area
        FROM gi_details WHERE geo_shape IS NULL AND geographical_area IS NOT NULL
          AND length(geographical_area) > 3 ORDER BY protected_name""")
    rows = cur.fetchall()
    by = {"nuts2": 0, "nuts1": 0}; shown = 0
    for fn, nm, ctry, area in rows:
        ctry = ctry or []
        combined = f"{nm}. {area}"
        codes = match_units(combined, ctry, gaz2, mw2)
        level = "nuts2"
        if not codes:
            codes = {x for x in match_units(combined, ctry, gaz1, mw1) if x not in whole_country}
            level = "nuts1"
        if not codes:
            continue
        by[level] += 1
        codes = sorted(codes)
        if a.dry_run:
            if shown < 22:
                cur2 = c.cursor(); cur2.execute("SELECT string_agg(name,', ') FROM gisco_units WHERE unit_code=ANY(%s)", (codes,))
                print(f"  {nm[:30]:30} [{level}] {(cur2.fetchone()[0] or '')[:44]}"); shown += 1
        else:
            write_nuts_geom(cur, fn, codes, "name_" + level)
    print(f"\n[phaseC6] unmatched={len(rows)} | recovered={sum(by.values())} {by}{' (dry-run)' if a.dry_run else ''}")
    c.close()


if __name__ == "__main__":
    main()
