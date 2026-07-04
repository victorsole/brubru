"""
Phase C.2: LAU recovery. For GIs still WITHOUT geometry, resolve municipality
names in the text to LAU boundaries (98k units already in gisco_units).

Conservative by design — runs ONLY on unmatched GIs, so it never regresses the
NUTS3-floor shapes from Phase C. Sharpening existing province matches down to
districts is a separate, riskier pass.

LAU precision is harder than NUTS3 (names are short, common, and REPEAT within a
country), so:
  - drop short/generic/administrative-prefix-only names,
  - an ambiguous name (>1 LAU in the country) is only used when a NUTS3 province
    context (from other unambiguous LAU hits) disambiguates it,
  - require either >=2 resolved municipalities, or 1 distinctive (>=6 char) one.

  python3.12 scripts/gi_geo_phase_c2.py --sample 40 --dry-run
  python3.12 scripts/gi_geo_phase_c2.py
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

_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
# municipality name-prefixes that are NOT distinctive on their own (multilingual)
_STOP = {
    "san", "santa", "santo", "sant", "sao", "saint", "sainte", "st", "villa", "villar",
    "castel", "castello", "monte", "val", "valle", "la", "le", "les", "el", "los", "las",
    "de", "del", "di", "da", "do", "das", "dos", "the", "and", "e", "y", "et", "of",
    "alto", "bajo", "baja", "alta", "nuova", "nuovo", "vecchio", "gran", "grande",
    "oberer", "unterer", "bad", "sankt",
    # common-word municipality/parish names that ride along on ordinary text words
    "vinhas", "vinhos", "vales", "areias", "franca", "gloria", "vila", "vinha",
    "relevant", "used", "vita", "vignes", "caves", "fins", "avril", "this", "that",
    "grand", "cru", "crus", "aceituna", "amendoa", "azeite", "azeitona", "beira",
    "madeira", "acores", "azores",  # island regions collide with distant mainland parishes
}
MIN_LEN = 4


def norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _distinctive(toks) -> bool:
    """A LAU phrase worth trusting: not all-stopwords, and either multi-word or long."""
    real = [t for t in toks if t not in _STOP]
    if not real:
        return False
    if len(toks) == 1:
        return len(toks[0]) >= MIN_LEN and toks[0] not in _STOP
    return True


def load_lau_gazetteer(cur):
    """{country: {phrase: [codes]}} — LAU names, keeping ambiguity (list of codes)."""
    cur.execute("SELECT unit_code, country, name_norm, nuts_parent FROM gisco_units WHERE level='LAU'")
    gaz = defaultdict(lambda: defaultdict(list))
    maxwords = defaultdict(lambda: 1)
    parent = {}
    for code, country, nm, np in cur.fetchall():
        parent[code] = np
        toks = _WORD.findall(nm or "")
        if not _distinctive(toks):
            continue
        phrase = " ".join(toks)
        gaz[country][phrase].append(code)
        maxwords[country] = max(maxwords[country], len(toks))
    return gaz, maxwords, parent


def resolve_lau(text, countries, gaz, maxwords, parent):
    toks = _WORD.findall(norm(text))
    unambiguous, ambiguous = [], []
    for country in countries:
        cmap = gaz.get(country)
        if not cmap:
            continue
        mw = maxwords.get(country, 1)
        i = 0
        while i < len(toks):
            hit = None
            for n in range(min(mw, len(toks) - i), 0, -1):
                codes = cmap.get(" ".join(toks[i:i + n]))
                if codes:
                    hit = (codes, n)
                    break
            if hit:
                codes, n = hit
                (unambiguous if len(codes) == 1 else ambiguous).append(codes)
                i += n
            else:
                i += 1
    resolved = {c[0] for c in unambiguous}
    # disambiguate ambiguous names by the province context of the unambiguous hits
    provinces = {parent.get(c) for c in resolved if parent.get(c)}
    for codes in ambiguous:
        same = [c for c in codes if parent.get(c) in provinces]
        resolved.update(same)
    if not resolved:
        return set()
    # GEOGRAPHIC-CLUSTERING GUARD: a real GI municipality-list concentrates in one
    # province; common-word false matches (an English word == a French commune, a
    # Portuguese "vinhas"/"vales" parish) scatter as isolated singletons across
    # distant provinces. Require >=2 resolved municipalities in a single NUTS3.
    from collections import Counter
    prov = Counter(parent.get(c) for c in resolved if parent.get(c))
    dominant_prov, dominant_n = (prov.most_common(1)[0] if prov else (None, 0))
    if dominant_n < 2:
        return set()
    # keep only municipalities in provinces that actually cluster (>=2), dropping
    # scattered singletons that rode along.
    keep_provs = {p for p, n in prov.items() if n >= 2}
    return {c for c in resolved if parent.get(c) in keep_provs}


def write_geometry(cur, fn, codes):
    cur.execute("""
        WITH u AS (SELECT ST_Multi(ST_Union(geometry)) AS shape FROM gisco_units WHERE unit_code = ANY(%s))
        UPDATE gi_details g SET
          geo_shape=u.shape, geo_centroid=ST_Centroid(u.shape),
          geo_area_km2=ST_Area(u.shape::geography)/1e6, geo_lau=%s, geo_geom_confidence='name_lau',
          geo_geometry=jsonb_build_object('type','Feature',
            'geometry', ST_AsGeoJSON(ST_SimplifyPreserveTopology(u.shape,0.003))::jsonb,
            'properties', jsonb_build_object(
              'area_km2', round((ST_Area(u.shape::geography)/1e6)::numeric),
              'centroid', jsonb_build_array(round(ST_X(ST_Centroid(u.shape))::numeric,4), round(ST_Y(ST_Centroid(u.shape))::numeric,4)),
              'bbox', jsonb_build_array(round(ST_XMin(u.shape)::numeric,4), round(ST_YMin(u.shape)::numeric,4), round(ST_XMax(u.shape)::numeric,4), round(ST_YMax(u.shape)::numeric,4)),
              'unit_codes', %s, 'unit_level', 'LAU', 'confidence', 'name_lau'))
        FROM u WHERE g.file_number=%s AND u.shape IS NOT NULL
    """, (list(codes), sorted(codes), sorted(codes), fn))
    return cur.rowcount > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    print("[phaseC2] loading LAU gazetteer...", flush=True)
    gaz, maxwords, parent = load_lau_gazetteer(cur)
    print(f"  countries: {len(gaz)} | distinctive names: {sum(len(v) for v in gaz.values())}")

    cur.execute("""SELECT file_number, protected_name, countries, geographical_area
        FROM gi_details WHERE geo_shape IS NULL AND geographical_area IS NOT NULL
          AND length(geographical_area) > 3 ORDER BY protected_name""" + (f" LIMIT {a.sample}" if a.sample else ""))
    rows = cur.fetchall()
    written = matched = 0
    for fn, nm, ctry, area in rows:
        codes = resolve_lau(area, ctry or [], gaz, maxwords, parent)
        if not codes:
            continue
        matched += 1
        if a.dry_run:
            if a.sample:
                cur2 = c.cursor()
                cur2.execute("SELECT string_agg(name,', ') FROM gisco_units WHERE unit_code=ANY(%s)", (list(codes),))
                nms = cur2.fetchone()[0]
                print(f"  {nm[:26]:26} {str(ctry):6} -> {len(codes)} LAU: {(nms or '')[:70]}")
        elif write_geometry(cur, fn, codes):
            written += 1
    print(f"\n[phaseC2] unmatched candidates={len(rows)} | matched={matched} | written={written}{' (dry-run)' if a.dry_run else ''}")
    c.close()


if __name__ == "__main__":
    main()
