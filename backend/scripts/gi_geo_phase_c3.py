"""
Phase C.3: SHARPEN NUTS3 province matches down to their municipality (LAU) union
where the text actually enumerates municipalities.

Risky pass — it REPLACES existing good NUTS3 geometry, so the bar is higher than
C.2 recovery. Only sharpen when the text is clearly listing municipalities, not
mentioning a couple as examples inside a province-wide area:
  - a DEFINING PHRASE ("municipalities of / comuni di / términos municipales…")
    together with >=2 clustered municipalities, OR
  - >=4 clustered municipalities (prose rarely names 4+ example towns).

Reuses the C.2 LAU resolver (incl. the geographic-clustering guard).

  python3.12 scripts/gi_geo_phase_c3.py --sample 40 --dry-run
  python3.12 scripts/gi_geo_phase_c3.py
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg2
from core.config import settings
from gi_geo_phase_c2 import load_lau_gazetteer, resolve_lau, norm, write_geometry

# defining enumeration markers, normalised (accent-stripped), multilingual
_DEFINING = re.compile(
    r"municip|comune|comuni|comarch|commune|concelho|freguesia|gemeind|"
    r"termino municipal|terme municipal|territorio dei|abrange|δημ|koinot|"
    r"following localities|localities of|villages of|parishes of"
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    print("[phaseC3] loading LAU gazetteer...", flush=True)
    gaz, maxwords, parent = load_lau_gazetteer(cur)

    cur.execute("""SELECT file_number, protected_name, countries, geographical_area, geo_area_km2, geo_nuts
        FROM gi_details WHERE geo_geom_confidence IN ('name_nuts3','name_nuts3_broad')
          AND geographical_area IS NOT NULL ORDER BY protected_name"""
        + (f" LIMIT {a.sample}" if a.sample else ""))
    rows = cur.fetchall()

    sharpened = considered = skipped_broad = 0
    for fn, nm, ctry, area, nuts_area, nuts in rows:
        # BREADTH GUARD: a match spanning >2 NUTS3 is a genuinely broad region
        # (Limousin/Poitou-Charentes lamb) whose named communes are examples, not
        # the definition — never sharpen it. Sharpen only 1-2 province over-matches.
        if nuts and len(nuts) > 2:
            skipped_broad += 1
            continue
        codes = resolve_lau(area, ctry or [], gaz, maxwords, parent)
        if not codes:
            continue
        defining = bool(_DEFINING.search(norm(area)))
        if not ((defining and len(codes) >= 2) or len(codes) >= 4):
            continue
        # RATIO FLOOR: a sharpened area that is a tiny sliver (<3%) of the matched
        # province is likely example-communes inside a province-wide area, not the
        # definition. When in doubt keep the coarse-but-correct province.
        cur2 = c.cursor()
        cur2.execute("SELECT ST_Area(ST_Union(geometry)::geography)/1e6 FROM gisco_units WHERE unit_code=ANY(%s)", (list(codes),))
        new_area = cur2.fetchone()[0] or 0
        if nuts_area and new_area < 0.03 * nuts_area:
            continue
        considered += 1
        if a.dry_run:
            if a.sample:
                print(f"  {nm[:26]:26} {round(nuts_area):>7} -> {round(new_area):>6} km2 | {len(codes)} LAU {'[phrase]' if defining else '[>=4]'} ({round(100*new_area/nuts_area)}%)")
        elif write_geometry(cur, fn, codes):
            sharpened += 1

    print(f"\n[phaseC3] NUTS3-matched={len(rows)} | qualified={considered} | sharpened={sharpened}{' (dry-run)' if a.dry_run else ''}")
    c.close()


if __name__ == "__main__":
    main()
