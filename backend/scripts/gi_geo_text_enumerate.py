"""
1.1 residual — TEXT-FIRST enumeration recovery. Many enumerable_todo GIs already carry
the delimited area in the stored geographical_area column, in many languages. Resolve it
straight from the DB text, no browser, no PDF.

Two honest tiers, because "the following departments of X, Y" and "commune of A, B, C"
need different resolution:

  COMMUNE tier: genuine municipality enumeration -> resolve_lau (>=2 cluster guard) and a
    COMPACTNESS guard (reject a resolved set whose bbox diagonal exceeds 220 km, which
    catches department-name-as-commune collisions and cross-region scatter, e.g. Emmental
    "6 departments: Doubs, ..." mis-hitting the communes Doubs + Saône, or the central-
    Apennine Vitellone spreading across Italy). Written as 'text_lau'.
  DEPARTMENT tier: when the text is whole-unit ("all municipalities", "in its entirety",
    "whole departments of", "following departments/regions/counties"), do NOT scatter it
    to communes; resolve the NUTS unit names instead (NUTS3 then NUTS2). Written as the
    corresponding 'name_nuts*' if it improves on the current geometry.

Portugal is a known granularity gap: GISCO LAU is freguesia (parish) but PT GI lists name
concelhos (municipalities), so PT commune lists will not match and are left for the
concelho crosswalk (1.3-adjacent). Re-run gi_geo_classify.py afterwards to re-bucket.

  python3.12 scripts/gi_geo_text_enumerate.py --dry-run
  python3.12 scripts/gi_geo_text_enumerate.py
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
from gi_geo_annex_fetch import _PROVINCE_COUNT
from gi_geo_phase_c2 import load_lau_gazetteer, resolve_lau, write_geometry as write_lau_geom
from gi_geo_phase_c import load_gazetteer, match_units, write_geometry as write_nuts_geom

# whole-unit phrasing => resolve at NUTS, never scatter to same-named communes
_WHOLE_DEPT = re.compile(
    r"(?:all\s+(?:the\s+)?municipalities|in\s+(?:its|their)\s+entirety|"
    r"whole\s+(?:department|region|province|of\s+the\s+department)s?\s+of|"
    r"entire\s+(?:department|region|province)|"
    r"following\s+(?:departments|regions|counties|provinces)|"
    r"(?:reduced\s+to\s+)?\d+\s+(?:departments|regions|provinces|counties)\b|"  # "6 departments"
    r"toute[s]?\s+(?:le|la|les)\s+(?:commune|d[ée]partement)|totalit[ée])", re.I)

MAX_DIAG_KM = 220.0


def bbox_diag_km(cur, codes) -> float:
    cur.execute("""SELECT ST_Distance(
          ST_SetSRID(ST_MakePoint(ST_XMin(u),ST_YMin(u)),4326)::geography,
          ST_SetSRID(ST_MakePoint(ST_XMax(u),ST_YMax(u)),4326)::geography)/1000
        FROM (SELECT ST_Extent(geometry) u FROM gisco_units WHERE unit_code=ANY(%s)) q""",
                (list(codes),))
    r = cur.fetchone()
    return float(r[0]) if r and r[0] is not None else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    print("[text-enum] loading gazetteers...", flush=True)
    gaz, mw, parent = load_lau_gazetteer(cur)
    nuts3, mw3 = load_gazetteer(cur, "NUTS3")

    cur.execute("""SELECT file_number, protected_name, countries, geographical_area, geo_geom_confidence
        FROM gi_details WHERE geo_refine_track='enumerable_todo' AND geographical_area IS NOT NULL
        ORDER BY countries, protected_name""")
    rows = cur.fetchall()
    print(f"[text-enum] targets: {len(rows)}")

    # GIs already flagged as spanning many NUTS3 (broad / NUTS2 / NUTS1) are known multi-
    # region: never shrink them to a commune subset (Val de Loire, 14 departments, would
    # collapse to a truncated 17-commune list). They may only be refined at NUTS.
    _BROAD = {"name_nuts3_broad", "name_nuts2", "name_nuts1", "name_nuts"}

    stats = {"commune": 0, "department": 0, "scatter_rejected": 0, "broad_skip": 0, "skip": 0}
    for fn, nm, ctry, area, conf in rows:
        ctry = ctry or []
        # DEPARTMENT tier: whole-unit -> resolve NUTS3 names, do not scatter to communes
        if _WHOLE_DEPT.search(area) or _PROVINCE_COUNT.search(area):
            codes = sorted(match_units(area, ctry, nuts3, mw3))
            if codes:
                stats["department"] += 1
                if a.dry_run:
                    cur2 = c.cursor(); cur2.execute("SELECT string_agg(name,', ') FROM gisco_units WHERE unit_code=ANY(%s)", (codes,))
                    print(f"  DEPT [{','.join(ctry)}] {nm[:26]:26} {len(codes)}: {(cur2.fetchone()[0] or '')[:52]}")
                else:
                    write_nuts_geom(cur, fn, codes, "name_nuts3")
                    cur.execute("UPDATE gi_details SET geo_refine_track='region_exact' WHERE file_number=%s", (fn,))
            else:
                stats["skip"] += 1
            continue
        # broad multi-region GI: do not commune-shrink; leave for NUTS-level refinement
        if conf in _BROAD:
            stats["broad_skip"] += 1; continue
        # COMMUNE tier: genuine enumeration -> LAU cluster, then compactness guard
        codes = resolve_lau(area, ctry, gaz, mw, parent)
        if not codes:
            stats["skip"] += 1; continue
        diag = bbox_diag_km(cur, codes)
        if diag > MAX_DIAG_KM:
            stats["scatter_rejected"] += 1
            if a.dry_run:
                print(f"  REJECT(scatter {diag:.0f}km) [{','.join(ctry)}] {nm[:24]}")
            continue
        stats["commune"] += 1
        if a.dry_run:
            cur2 = c.cursor(); cur2.execute("SELECT string_agg(name,', ') FROM gisco_units WHERE unit_code=ANY(%s)", (list(codes),))
            print(f"  LAU  [{','.join(ctry)}] {nm[:26]:26} {len(codes):3} ({diag:.0f}km): {(cur2.fetchone()[0] or '')[:44]}")
        else:
            write_lau_geom(cur, fn, codes)
            cur.execute("UPDATE gi_details SET geo_geom_confidence='text_lau', geo_refine_track='precise' WHERE file_number=%s", (fn,))
    print(f"[text-enum] {stats}")
    c.close()


if __name__ == "__main__":
    main()
