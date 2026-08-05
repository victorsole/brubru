"""
Phase C.7: single-commune recovery. Many wine/food GIs ARE a commune name
(Menetou-Salon, Savennières, Ribeiro, Barolo). C.4 required the town to be
corroborated in the area text, but these GIs have procedural texts (amendment
notes, file numbers) with no geography — so the only signal is the TITLE.

Relax the corroboration but keep it safe with strong distinctiveness guards:
the title must contain an UNAMBIGUOUS (one LAU in the country) name that is either
multi-word or >=6 chars and not a stopword. Longest match wins. Runs only on
still-unmatched GIs.

  python3.12 scripts/gi_geo_phase_c7_commune.py --dry-run
  python3.12 scripts/gi_geo_phase_c7_commune.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import psycopg2
from core.config import settings
from gi_geo_phase_c2 import load_lau_gazetteer, write_geometry as write_lau_geom, norm, _WORD, _STOP


def title_commune(name, countries, gaz):
    """Longest unambiguous distinctive LAU name inside the title."""
    toks = _WORD.findall(norm(name))
    best = None
    for country in countries:
        cmap = gaz.get(country)
        if not cmap:
            continue
        for n in range(min(4, len(toks)), 0, -1):
            for i in range(len(toks) - n + 1):
                phrase = " ".join(toks[i:i + n])
                codes = cmap.get(phrase)
                if not codes or len(codes) != 1:
                    continue
                distinctive = n >= 2 or (len(phrase) >= 6 and phrase not in _STOP)
                if distinctive and (best is None or n > best[1]):
                    best = (set(codes), n)
    return best[0] if best else set()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    print("[phaseC7] loading LAU gazetteer...", flush=True)
    gaz, _mw, _parent = load_lau_gazetteer(cur)

    cur.execute("""SELECT file_number, protected_name, countries FROM gi_details
        WHERE geo_shape IS NULL AND geographical_area IS NOT NULL AND length(geographical_area) > 3
        ORDER BY protected_name""")
    rows = cur.fetchall()
    rec = 0; shown = 0
    for fn, nm, ctry in rows:
        codes = title_commune(nm, ctry or [], gaz)
        if not codes:
            continue
        rec += 1
        if a.dry_run:
            if shown < 26:
                cur2 = c.cursor(); cur2.execute("SELECT string_agg(name,', ') FROM gisco_units WHERE unit_code=ANY(%s)", (list(codes),))
                print(f"  {nm[:32]:32} -> {cur2.fetchone()[0]}"); shown += 1
        else:
            write_lau_geom(cur, fn, codes)
    print(f"\n[phaseC7] unmatched={len(rows)} | recovered={rec}{' (dry-run)' if a.dry_run else ''}")
    c.close()


if __name__ == "__main__":
    main()
