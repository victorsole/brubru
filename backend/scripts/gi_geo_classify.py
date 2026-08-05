"""
Task 1.#3 — refinement-track classifier. Partition every GI that is still coarser than
commune level (geo_geom_confidence in the NUTS tiers, or no geometry) into an HONEST
refinement track, so the supervised member-state workstream (1.2) and the comarca
crosswalk (1.3) get a clean, reviewable worklist instead of a mixed bucket.

Tracks:
  enumerable_todo — the delimited-area text still carries a plural commune-list we have
                    not captured (belongs back in 1.1, the annex/enumeration pass).
  part_of         — DESCRIPTIVE / partitive area: a slice of a unit ("north-west of
                    Salamanca province", "parte del territorio", "fascia collinare del
                    Molise"). Not annex-enumerable; needs member-state geodata -> 1.2.
  comarca         — Spanish / Catalan comarca-defined zone -> 1.3 (Idescat-style crosswalk).
  region_exact    — the area genuinely IS a whole province / region. Correctly coarse and
                    DONE; not a defect, do not spend refinement effort here.
  no_text         — geographical_area is empty/near-empty; needs re-extraction first.
  unknown         — no signal matched; leave for manual review.

This is a CLASSIFIER, not a geometry writer. It never fabricates a shape. Dry-run by
default (prints the partition + samples); --write persists the track to geo_refine_track.

  python3.12 scripts/gi_geo_classify.py                 # dry-run report
  python3.12 scripts/gi_geo_classify.py --sample part_of --n 30
  python3.12 scripts/gi_geo_classify.py --write         # persist tags (needs migration 202)
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg2
from core.config import settings

# --- signal vocabularies (multilingual: en/fr/it/es/pt/de/nl/el-transliterated) ---
# Classification ORDER is significant (see classify()): the most specific, least
# ambiguous signals are tested first so that a partitive slice never loses to a broad
# region phrase and a whole-province "all municipalities" never reads as a list.

# GENUINE enumeration still in the stored text => 1.1 residual. Must name specific
# places (a "following ...:" header, a "comuni di X" head with a capitalised name, or a
# comma-separated proper-noun run). A whole-unit "all/todos ... della provincia" is NOT
# a list and is screened out first by _WHOLE_UNIT below.
_ENUMERABLE = re.compile(
    r"(?:following\s+(?:municipalities|communes?|departments?|cantons?|comuni|concelhos)|"
    r"seguent[ei]s?\s+(?:municipi|concelhos|comuni)|"
    r"(?:comuni|communes?|municipios|municipis|concelhos)\s+d[ei]\s+[A-ZÀ-Ú]|"
    r":\s*[A-ZÀ-Ú][\wà-ÿ'’\-]+\s*,\s*[A-ZÀ-Ú])", re.I)

# whole-unit language => region_exact. "all municipalities OF THE province/department"
# is a WHOLE unit, not an enumeration, so this is also used to veto _ENUMERABLE.
_WHOLE_UNIT = re.compile(
    r"\b(?:whole\s+(?:of\s+)?(?:the\s+)?(?:province|region|island|department|land|municipalit)|"
    r"entire\s+(?:province|region|island|territory|municipalit)|"
    r"all\s+(?:the\s+)?municipalities\s+of\s+the\s+(?:province|department)|"
    r"tod[ao]s?\s+(?:los\s+municipios\s+de\s+la\s+provincia|la\s+(?:provincia|regi[óo]n|isla|comunidad))|"
    r"tutt[oi]\s+il\s+territorio|intera\s+regione|intero\s+territorio|"
    r"tout[e]?\s+(?:le|la)\s+(?:d[ée]partement|r[ée]gion|province)|"
    r"corresponds?\s+to\s+(?:that\s+of\s+|the\s+(?:department|region|province|area|territory))|"
    r"(?:the\s+)?(?:region|province|department)\s+of\s+\w+|"
    r"(?:r[ée]gion|regi[óo]n|regione)\s+d[ei']|d[ée]partement\s+d[e']|provincia\s+di\s+\w+|"
    r"island\s+of|city\s+of|town\s+of|administrative\s+(?:area|territory)\s+of\s+the|"
    r"comunidad\s+aut[óo]noma|gesamte[ns]?\s+(?:land|gebiet)|"
    # trailing-unit forms: "Jaén province", "Limousin region", "et sa province",
    # "largest island", "County Mayo" (reached only after enumerable + part_of fail)
    r"[A-ZÀ-Ú][\wà-ÿ'’\-]+\s+(?:province|region)\b|et\s+sa\s+province|and\s+its\s+province|"
    r"(?:largest\s+|the\s+)island\b|[îi]le\s+d[e']|county\s+(?:of\s+)?[A-ZÀ-Ú])\b", re.I)

# EXPLICIT partitive: a slice of a unit => 1.2 (member-state supervised). Requires either
# a "part of" phrase or a compass direction bound TO a named administrative unit
# ("al Noroeste de la provincia de X"). Bare locational directions ("located in the
# south-east") are excluded because they do not attach to a unit.
_PART_OF = re.compile(
    r"\b(?:part\s+of\b|a\s+part\s+of\b|parte?\s+(?:del|della|dei|de\s+la|du|des)\b|partie\s+(?:de|du|des)\b|"
    r"(?:al\s+|au\s+|en\s+el\s+|nel\s+|im\s+)?"
    r"(?:nord|sud|est|ovest|ouest|noroeste|noreste|suroeste|sureste|"
    r"nord[\-\s]?ouest|nord[\-\s]?est|sud[\-\s]?ouest|sud[\-\s]?est|"
    r"north[\-\s]?west|north[\-\s]?east|south[\-\s]?west|south[\-\s]?east|"
    r"settentrional\w*|meridional\w*|orientale|occidentale)\s+"
    r"(?:de|del|della|du|des|of|di)\s+(?:la\s+|the\s+)?(?:provincia|province|d[ée]partement|"
    r"regi[óo]n|region|regione|comarca|zona|isla|land)\b|"
    r"\bfascia\b|\bversante\b|\bpedemontan|compresa?\s+tra\b|comprsa?\s+tra\b)", re.I)

# comarca-defined (ES/CA) => 1.3
_COMARCA = re.compile(r"\bcomarc(?:a|as|ues|a\s+de)\b", re.I)


def classify(name: str, area: str | None) -> str:
    txt = f"{name or ''}. {area or ''}"
    if not area or len(area.strip()) < 8:
        return "no_text"
    whole = _WHOLE_UNIT.search(txt)
    # a genuine named enumeration that is NOT a "whole unit" phrasing -> 1.1 residual
    if _ENUMERABLE.search(txt) and not whole:
        return "enumerable_todo"
    # explicit partitive slice wins over a broad region phrase (Arribes: NW of a province)
    if _PART_OF.search(txt):
        return "part_of"
    if _COMARCA.search(txt):
        return "comarca"
    if whole:
        return "region_exact"
    return "unknown"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="persist geo_refine_track (needs migration 202)")
    ap.add_argument("--sample", help="print sample rows for one track")
    ap.add_argument("--n", type=int, default=25)
    a = ap.parse_args()

    c = psycopg2.connect(settings.DATABASE_URL, connect_timeout=20); c.autocommit = True
    cur = c.cursor()
    # coarse target: anything not already at commune precision
    cur.execute("""SELECT file_number, protected_name, countries, geographical_area, geo_geom_confidence
        FROM gi_details
        WHERE (geo_geom_confidence IS NULL
           OR geo_geom_confidence NOT IN ('name_lau','annex_lau','text_lau','union','exact_nuts'))
          AND COALESCE(geo_refine_track,'') <> 'crosswalk'
        ORDER BY protected_name""")
    rows = cur.fetchall()

    buckets = Counter()
    by_ms = defaultdict(Counter)
    samples = defaultdict(list)
    tagged = []
    for fn, nm, ctry, area, conf in rows:
        track = classify(nm, area)
        buckets[track] += 1
        for ct in (ctry or ["??"]):
            by_ms[ct][track] += 1
        if len(samples[track]) < a.n:
            samples[track].append((nm, (area or "")[:90], ctry))
        tagged.append((fn, track))

    print(f"[classify] coarse target rows: {len(rows)}\n")
    print("=== refinement-track partition:")
    for tr, n in buckets.most_common():
        print(f"  {tr:16} {n}")
    print("\n=== part_of + comarca + enumerable_todo by member state (the refinement worklist):")
    focus = {"part_of", "comarca", "enumerable_todo"}
    ms_tot = sorted(by_ms.items(), key=lambda kv: -sum(v for t, v in kv[1].items() if t in focus))
    for ct, cnt in ms_tot[:14]:
        parts = " ".join(f"{t}={cnt[t]}" for t in ("part_of", "comarca", "enumerable_todo") if cnt[t])
        if parts:
            print(f"  {ct}: {parts}")

    if a.sample:
        print(f"\n=== sample: {a.sample}")
        for nm, area, ctry in samples.get(a.sample, []):
            print(f"  [{','.join(ctry or [])}] {nm[:34]:34} | {area}")

    if a.write:
        for fn, track in tagged:
            cur.execute("UPDATE gi_details SET geo_refine_track=%s WHERE file_number=%s", (track, fn))
        # precise rows get an explicit 'precise' marker for a complete picture
        cur.execute("""UPDATE gi_details SET geo_refine_track='precise'
            WHERE geo_geom_confidence IN ('name_lau','annex_lau','text_lau','union','exact_nuts')""")
        print(f"\n[classify] wrote geo_refine_track for {len(tagged)} coarse + precise rows")
    c.close()


if __name__ == "__main__":
    main()
