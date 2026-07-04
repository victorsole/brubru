"""
Phase C: resolve GI geographical_area TEXT to geometry by name-matching against the
GISCO gazetteer. NUTS3 floor (this file); LAU refinement is Phase C.2.

Matching is EXACT n-gram, not fuzzy substring: a unit matches only when its full
name appears as consecutive real words in the normalised text (country-scoped,
accent-insensitive, every published name variant considered). This avoids the
substring false-positives that plague naive `text LIKE %name%`.

  python3.12 scripts/gi_geo_phase_c.py --sample 30 --dry-run   # inspect precision
  python3.12 scripts/gi_geo_phase_c.py                         # write all
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from core.config import settings

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)  # unicode letters only (drops digits/punct)
# Compass/administrative generic tokens (multilingual). A unit whose name is made
# up ENTIRELY of these is an unreliable gazetteer entry (Ireland's NUTS3 are all
# "South-East"/"West"/"Border"/"Midland", which match directional words in any
# text). Such names are dropped; those GIs resolve precisely at LAU instead.
_GENERIC_TOKENS = {
    "north", "south", "east", "west", "northern", "southern", "eastern", "western",
    "northeast", "northwest", "southeast", "southwest", "central", "centre", "center",
    "border", "midland", "midlands", "region", "mid", "isole", "isles", "islands", "continent",
    "nord", "sud", "est", "ouest", "ovest", "centro", "centrale",              # FR/IT
    "sur", "norte", "este", "oeste",                                           # ES
    "ost", "westen", "osten", "norden", "sueden", "mitte",                     # DE
    "noord", "zuid", "oost", "midden",                                         # NL
}
MIN_LEN = 4  # a single-token name must be >= this to match alone


def _all_generic(toks) -> bool:
    return bool(toks) and all(t in _GENERIC_TOKENS for t in toks)


def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def load_gazetteer(cur, level: str):
    """{country: {name_norm_phrase: (code, nwords)}} for one level, incl. name variants."""
    cur.execute("SELECT unit_code, country, name_search FROM gisco_units WHERE level=%s", (level,))
    gaz = defaultdict(dict)
    maxwords = defaultdict(lambda: 1)
    for code, country, search in cur.fetchall():
        for variant in (search or "").split(" | "):
            toks = _WORD.findall(variant)
            phrase = " ".join(toks)
            if not phrase or _all_generic(toks) or (len(toks) == 1 and len(phrase) < MIN_LEN):
                continue
            gaz[country].setdefault(phrase, (code, len(toks)))
            maxwords[country] = max(maxwords[country], len(toks))
    return gaz, maxwords


def match_units(text: str, countries: list[str], gaz, maxwords) -> set[str]:
    toks = _WORD.findall(norm(text))
    found = set()
    for country in countries:
        cmap = gaz.get(country)
        if not cmap:
            continue
        mw = maxwords.get(country, 1)
        for i in range(len(toks)):
            for n in range(min(mw, len(toks) - i), 0, -1):
                phrase = " ".join(toks[i:i + n])
                hit = cmap.get(phrase)
                if hit:
                    found.add(hit[0])
                    break  # longest match at this position wins
    return found


def write_geometry(cur, fn, codes, conf):
    cur.execute("""
        WITH u AS (SELECT ST_Multi(ST_Union(geometry)) AS shape FROM gisco_units WHERE unit_code = ANY(%s))
        UPDATE gi_details g SET
          geo_shape=u.shape, geo_centroid=ST_Centroid(u.shape),
          geo_area_km2=ST_Area(u.shape::geography)/1e6, geo_nuts=%s, geo_geom_confidence=%s,
          geo_geometry=jsonb_build_object('type','Feature',
            'geometry', ST_AsGeoJSON(ST_SimplifyPreserveTopology(u.shape,0.005))::jsonb,
            'properties', jsonb_build_object(
              'area_km2', round((ST_Area(u.shape::geography)/1e6)::numeric),
              'centroid', jsonb_build_array(round(ST_X(ST_Centroid(u.shape))::numeric,4), round(ST_Y(ST_Centroid(u.shape))::numeric,4)),
              'bbox', jsonb_build_array(round(ST_XMin(u.shape)::numeric,4), round(ST_YMin(u.shape)::numeric,4), round(ST_XMax(u.shape)::numeric,4), round(ST_YMax(u.shape)::numeric,4)),
              'unit_codes', %s, 'unit_level', 'NUTS3', 'confidence', %s))
        FROM u WHERE g.file_number=%s AND u.shape IS NOT NULL
    """, (codes, codes, conf, codes, conf, fn))
    return cur.rowcount > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0, help="only N GIs (for inspection)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    print("[phaseC] loading NUTS3 gazetteer...", flush=True)
    gaz, maxwords = load_gazetteer(cur, "NUTS3")
    print(f"  countries: {len(gaz)} | names: {sum(len(v) for v in gaz.values())}")

    # target: GIs with clean text but no geometry yet
    cur.execute("""SELECT file_number, protected_name, countries, geographical_area
        FROM gi_details WHERE geo_shape IS NULL AND geographical_area IS NOT NULL
          AND length(geographical_area) > 3 ORDER BY protected_name""" + (f" LIMIT {a.sample}" if a.sample else ""))
    rows = cur.fetchall()

    written = matched = 0
    for fn, nm, ctry, area in rows:
        codes = match_units(area, ctry or [], gaz, maxwords)
        if not codes:
            continue
        matched += 1
        conf = "name_nuts3" if len(codes) <= 6 else "name_nuts3_broad"
        if a.dry_run:
            if a.sample:
                cur2 = c.cursor()
                cur2.execute("SELECT string_agg(name,', ') FROM gisco_units WHERE unit_code=ANY(%s)", (list(codes),))
                names = cur2.fetchone()[0]
                print(f"  {nm[:26]:26} {str(ctry):7} -> {sorted(codes)} ({names})")
        else:
            if write_geometry(cur, fn, sorted(codes), conf):
                written += 1

    print(f"\n[phaseC] candidates={len(rows)} | matched={matched} | written={written}{' (dry-run)' if a.dry_run else ''}")
    c.close()


if __name__ == "__main__":
    main()
