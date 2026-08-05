"""
Phase C.4: recovery tail for GIs still without geometry.

Adds two signals Phase C/C.2 didn't use:
  1. Match the GI's PROTECTED_NAME, not just the area text — the title usually
     names the origin ("Aceto Balsamico di Modena" IS Modena), which recovers GIs
     whose area text is descriptive.
  2. SINGLE-municipality recovery — C.2 required >=2 clustered towns for safety;
     here a single LAU is allowed when it is named in the TITLE and is a distinctive,
     unambiguous name (the GI is literally named after the town).

Priority per GI: LAU cluster (>=2) > single-LAU-from-title > NUTS3. Runs only on
unmatched GIs, so it never regresses existing shapes.

  python3.12 scripts/gi_geo_phase_c4.py --sample 60 --dry-run
  python3.12 scripts/gi_geo_phase_c4.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg2
from core.config import settings
from gi_geo_phase_c import load_gazetteer as load_nuts_gaz, match_units, write_geometry as write_nuts_geom
from gi_geo_phase_c2 import load_lau_gazetteer, resolve_lau, write_geometry as write_lau_geom, norm, _WORD


def single_lau_corroborated(name, text, countries, gaz, parent):
    """One distinctive, unambiguous LAU named in the TITLE *and* corroborated in the
    area text. The both-places requirement rejects a product word in the title that
    happens to be a town name ("Aceituna"/olive, "Amêndoa"/almond): a product word is
    not described as a place in the area text, so it won't corroborate."""
    toks = _WORD.findall(norm(name))
    text_norm = norm(text)
    for country in countries:
        cmap = gaz.get(country)
        if not cmap:
            continue
        for n in range(min(4, len(toks)), 0, -1):
            for i in range(len(toks) - n + 1):
                phrase = " ".join(toks[i:i + n])
                codes = cmap.get(phrase)
                if codes and len(codes) == 1 and len(phrase) >= 5 and phrase in text_norm:
                    return set(codes), phrase
    return set(), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    print("[phaseC4] loading gazetteers...", flush=True)
    nuts_gaz, nuts_mw = load_nuts_gaz(cur, "NUTS3")
    lau_gaz, lau_mw, parent = load_lau_gazetteer(cur)

    cur.execute("""SELECT file_number, protected_name, countries, geographical_area
        FROM gi_details WHERE geo_shape IS NULL AND geographical_area IS NOT NULL
          AND length(geographical_area) > 3 ORDER BY protected_name"""
        + (f" LIMIT {a.sample}" if a.sample else ""))
    rows = cur.fetchall()

    by = {"lau": 0, "single": 0, "nuts3": 0}
    for fn, nm, ctry, area in rows:
        ctry = ctry or []
        combined = f"{nm}. {area}"
        lau_codes = resolve_lau(combined, ctry, lau_gaz, lau_mw, parent)
        single, phrase = (set(), None) if lau_codes else single_lau_corroborated(nm, area, ctry, lau_gaz, parent)
        nuts_codes = set() if (lau_codes or single) else match_units(combined, ctry, nuts_gaz, nuts_mw)

        kind = codes = None
        if lau_codes:
            kind, codes = "lau", sorted(lau_codes)
        elif single:
            kind, codes = "single", sorted(single)
        elif nuts_codes:
            kind, codes = "nuts3", sorted(nuts_codes)
        else:
            continue
        by[kind] += 1
        if a.dry_run:
            if a.sample:
                cur2 = c.cursor()
                cur2.execute("SELECT string_agg(name,', ') FROM gisco_units WHERE unit_code=ANY(%s)", (codes,))
                names = (cur2.fetchone()[0] or "")[:60]
                print(f"  {nm[:26]:26} [{kind:6}] {len(codes)}u: {names}")
        else:
            if kind == "nuts3":
                write_nuts_geom(cur, fn, codes, "name_nuts3")
            else:
                write_lau_geom(cur, fn, set(codes))

    tot = sum(by.values())
    print(f"\n[phaseC4] unmatched={len(rows)} | recovered={tot} {by}{' (dry-run)' if a.dry_run else ''}")
    c.close()


if __name__ == "__main__":
    main()
