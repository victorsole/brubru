"""
Phase C.5 (Greek): recover the 268 Greek GIs the country-scoped matcher skipped.

Three stacked Greek problems, handled here:
  1. COUNTRY CODE — GI `countries` says "GR" but GISCO codes Greece "EL".
  2. PREFIXES — EL LAU names are "Κοινότητα/Δήμος <place>" (Community/Municipality
     of ...); strip the prefix to get the bare place name.
  3. NUTS3 island-lists — EL NUTS3 names are comma-lists ("Άνδρος, ..., Πάρος,
     ..."); split them so each island is matchable.

Exact matching after (2)+(3) recovers ~177/268. The declension tail (nominative
GI "Αρχάνες" vs genitive LAU "Αρχανών") is left for a fuzzy pass.

Same precision guards as the Latin-script passes: LAU geographic-clustering (>=2
in one NUTS3), single-LAU only when corroborated in title AND text, distinctive
names only.

  python3.12 scripts/gi_geo_phase_c5_greek.py --dry-run
  python3.12 scripts/gi_geo_phase_c5_greek.py
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg2
from core.config import settings
from gi_geo_phase_c import write_geometry as write_nuts_geom
from gi_geo_phase_c2 import write_geometry as write_lau_geom

_W = re.compile(r"[^\W\d_]+", re.UNICODE)
_PFX = ["κοινοτητα", "δημοτικη ενοτητα", "τοπικη κοινοτητα", "δημοτικη κοινοτητα",
        "δημος", "περιφερειακη ενοτητα"]
# Greek generic place-words (saint / new / old / upper-lower / big-small)
_STOP = {"αγιος", "αγια", "αγιοι", "αγιου", "αγιων", "νεα", "νεο", "νεος", "νεας",
         "ανω", "κατω", "μεγαλη", "μεγαλο", "μικρη", "μικρο", "παλαια", "παλαιο", "μεσα", "εξω"}
MIN_LEN = 4


def norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


def strip_pfx(nm):
    for p in _PFX:
        if nm.startswith(p + " "):
            return nm[len(p) + 1:].strip()
    return nm


def build_el_gaz(cur):
    cur.execute("SELECT unit_code, level, name, nuts_parent FROM gisco_units WHERE country='EL'")
    gaz = defaultdict(list)   # name_part -> [(code, level)]
    parent = {}
    for code, lvl, name, np in cur.fetchall():
        parent[code] = np
        if lvl == "LAU":
            keys = [strip_pfx(norm(name))]
        elif lvl == "NUTS3":
            keys = [p.strip() for p in norm(name).split(",")]
        else:
            continue
        for key in keys:
            toks = key.split()
            if not key or len(key) < MIN_LEN or (len(toks) == 1 and key in _STOP):
                continue
            gaz[key].append((code, lvl))
    maxw = max((len(k.split()) for k in gaz), default=1)
    return gaz, parent, maxw


def _hits(s, gaz, maxw):
    toks = _W.findall(norm(s))
    out = []
    i = 0
    while i < len(toks):
        got = None
        for n in range(min(maxw, len(toks) - i), 0, -1):
            key = " ".join(toks[i:i + n])
            if key in gaz:
                got = (key, gaz[key]); break
        if got:
            out.append(got); i += len(got[0].split())
        else:
            i += 1
    return out


def resolve(name, text, gaz, parent, maxw):
    """TITLE-ANCHORED: only match when the GI's own title hits a unit. Greek
    declension makes the primary name miss often (nominative "Αρχάνες" vs genitive
    "Αρχανών"); when it does, ordinary text tokens form false clusters (Αρκαδία ->
    two random "Ελληνικού" villages). So the title is the anchor; the text only
    EXPANDS a title-anchored LAU cluster within the anchor's province(s)."""
    title = _hits(name, gaz, maxw)
    title_lau = [c for _k, lst in title for c, lv in lst if lv == "LAU"]
    title_nuts = [c for _k, lst in title for c, lv in lst if lv == "NUTS3"]

    if title_lau:
        anchor_provs = {parent.get(c) for c in title_lau if parent.get(c)}
        text_lau = [c for _k, lst in _hits(text, gaz, maxw) for c, lv in lst if lv == "LAU"]
        cluster = set(title_lau) | {c for c in text_lau if parent.get(c) in anchor_provs}
        return sorted(cluster), "lau"
    if title_nuts:
        return sorted(set(title_nuts)), "nuts3"
    return [], None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    gaz, parent, maxw = build_el_gaz(cur)
    print(f"[greek] EL gazetteer keys: {len(gaz)}")
    cur.execute("""SELECT file_number, protected_name, geographical_area FROM gi_details
        WHERE geo_shape IS NULL AND 'GR'=ANY(countries) AND geographical_area IS NOT NULL
        ORDER BY protected_name""" + (f" LIMIT {a.limit}" if a.limit else ""))
    rows = cur.fetchall()
    by = Counter(); shown = 0
    for fn, nm, area in rows:
        codes, kind = resolve(nm, area, gaz, parent, maxw)
        if not codes:
            continue
        by[kind] += 1
        if a.dry_run:
            if shown < 20:
                cur2 = c.cursor(); cur2.execute("SELECT string_agg(name,', ') FROM gisco_units WHERE unit_code=ANY(%s)", (codes,))
                print(f"  {nm[:24]:24} [{kind:5}] {len(codes)}u: {(cur2.fetchone()[0] or '')[:55]}"); shown += 1
        else:
            if kind == "nuts3":
                write_nuts_geom(cur, fn, codes, "name_nuts3")
            else:
                write_lau_geom(cur, fn, set(codes))
    print(f"[greek] candidates={len(rows)} | recovered={sum(by.values())} {dict(by)}{' (dry-run)' if a.dry_run else ''}")
    c.close()


if __name__ == "__main__":
    main()
