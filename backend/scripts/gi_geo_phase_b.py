"""
Phase B: write real geometry for the GIs that already carry NUTS codes.

For each GI with geo_nuts:
  - non-Greek: keep only codes in the GI's own country that exist in gisco_units
    (drops cross-border false positives), then union their GISCO boundaries.
  - Greek: the document's old "GR" codes don't exist in NUTS 2021 (Greece was
    recoded GR->EL, not a prefix swap), so resolve the GI's Greek NAME against the
    gisco EL gazetteer instead, and rewrite geo_nuts to the correct EL code.

Union -> geo_shape (PostGIS) + geo_centroid + geo_area_km2 + geo_geometry (a
simplified GeoJSON Feature the map reads) + geo_geom_confidence.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from core.config import settings


def norm(s) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def resolve_greek(cur, name: str):
    """Match a Greek GI name to the most specific EL gisco unit. Returns (code, level) or None."""
    n = norm(name)
    if len(n) < 3:
        return None
    # prefer the most specific level (NUTS3 > NUTS2 > NUTS1); word-boundary-ish contains
    cur.execute("""SELECT unit_code, level FROM gisco_units
        WHERE country='EL' AND name_search LIKE %s
        ORDER BY CASE level WHEN 'NUTS3' THEN 3 WHEN 'NUTS2' THEN 2 WHEN 'NUTS1' THEN 1 ELSE 0 END DESC
        LIMIT 1""", (f"%{n}%",))
    r = cur.fetchone()
    return (r[0], r[1]) if r else None


def write_geometry(cur, fn: str, codes: list[str], nuts_value: list[str], conf: str) -> bool:
    cur.execute("""
        WITH u AS (SELECT ST_Multi(ST_Union(geometry)) AS shape
                   FROM gisco_units WHERE unit_code = ANY(%s))
        UPDATE gi_details g SET
          geo_shape = u.shape,
          geo_centroid = ST_Centroid(u.shape),
          geo_area_km2 = ST_Area(u.shape::geography)/1e6,
          geo_nuts = %s,
          geo_geom_confidence = %s,
          geo_geometry = jsonb_build_object(
            'type','Feature',
            'geometry', ST_AsGeoJSON(ST_SimplifyPreserveTopology(u.shape, 0.005))::jsonb,
            'properties', jsonb_build_object(
              'area_km2', round((ST_Area(u.shape::geography)/1e6)::numeric),
              'centroid', jsonb_build_array(round(ST_X(ST_Centroid(u.shape))::numeric,4), round(ST_Y(ST_Centroid(u.shape))::numeric,4)),
              'bbox', jsonb_build_array(round(ST_XMin(u.shape)::numeric,4), round(ST_YMin(u.shape)::numeric,4), round(ST_XMax(u.shape)::numeric,4), round(ST_YMax(u.shape)::numeric,4)),
              'unit_codes', %s, 'unit_level', 'NUTS', 'confidence', %s))
        FROM u
        WHERE g.file_number = %s AND u.shape IS NOT NULL
    """, (codes, nuts_value, conf, codes, conf, fn))
    return cur.rowcount > 0


def main():
    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    cur.execute("""SELECT file_number, protected_name, countries, geo_nuts FROM gi_details
        WHERE geo_nuts IS NOT NULL AND array_length(geo_nuts,1)>0 ORDER BY protected_name""")
    rows = cur.fetchall()
    written = greek_ok = greek_fail = filtered = 0
    for fn, nm, ctry, nuts in rows:
        ctry = ctry or []
        if "GR" in ctry or "EL" in ctry:
            # Greek: old GR codes are dead -> resolve by name to an EL unit
            res = resolve_greek(cur, nm)
            if not res:
                greek_fail += 1
                cur.execute("UPDATE gi_details SET geo_geom_confidence='unresolved' WHERE file_number=%s", (fn,))
                continue
            code, level = res
            if write_geometry(cur, fn, [code], [code], "name_nuts"):
                greek_ok += 1; written += 1
        else:
            # keep only same-country codes that exist in gisco (drops cross-border noise)
            cur.execute("SELECT unit_code FROM gisco_units WHERE unit_code = ANY(%s)", (nuts,))
            valid = {r[0] for r in cur.fetchall()}
            codes = [x for x in nuts if x[:2] in ctry and x in valid]
            if len(codes) < len(nuts):
                filtered += 1
            if not codes:
                cur.execute("UPDATE gi_details SET geo_geom_confidence='unresolved' WHERE file_number=%s", (fn,))
                continue
            conf = "exact_nuts" if len(codes) <= 3 else "union"
            if write_geometry(cur, fn, codes, codes, conf):
                written += 1

    cur.execute("SELECT count(*) FILTER (WHERE geo_geometry IS NOT NULL), count(*) FILTER (WHERE geo_shape IS NOT NULL) FROM gi_details")
    g1, g2 = cur.fetchone()
    print(f"[phaseB] written={written} | greek_ok={greek_ok} greek_fail={greek_fail} | non-greek codes filtered={filtered}")
    print(f"[phaseB] gi_details now: geo_geometry={g1} geo_shape={g2}")
    c.close()


if __name__ == "__main__":
    main()
