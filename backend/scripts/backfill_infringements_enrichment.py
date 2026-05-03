"""
Backfill sector / related_celex / policy_areas on infringement_procedures
rows by parsing the press-release title + summary.

No upstream calls — all derivation is from the existing title/summary text
already stored in the row. The Commission infringement press releases use
predictable phrasing:

  "Directive (EU) YYYY/NNNN"   → CELEX 3YYYYLNNNN
  "Regulation (EU) YYYY/NNNN"  → CELEX 3YYYYR NNNN
  "Decision (EU) YYYY/NNNN"    → CELEX 3YYYYD NNNN
  "Directive 2009/XXX/EC"      → CELEX 32009LNNNN

Sector / policy_areas keyword map covers the recurring DG topics: ENV
(waste, air, water, biodiversity), TAXUD (VAT, customs, taxation), HOME
(migration, asylum, border), JUST (rule of law, fundamental rights),
ENER (energy, electricity), CNECT (digital, telecom, AI), MOVE
(transport, aviation, rail), EMPL (workers, social), AGRI, SANTE,
COMP, FISMA.

Run:
    python3.12 backend/scripts/backfill_infringements_enrichment.py            # dry-run
    python3.12 backend/scripts/backfill_infringements_enrichment.py --apply
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


# CELEX pattern matchers
# New form (post-2015): "(EU) YYYY/NNNN" where YYYY is 2015-2030 and NNNN is the
# sequence number. Legacy form: "(EU) No NNNN/YYYY" — number first, year second.
# Old directives use "Directive YYYY/NNN/EC|EU|EEC".
_DIR_NEW_RE = re.compile(r"Directives?\s*\(EU\)\s*(20[0-9]{2})/(\d{1,4})", re.IGNORECASE)
_DIR_OLD_RE = re.compile(r"Directives?\s*(\d{4})/(\d{1,3})/(?:EC|EU|EEC)", re.IGNORECASE)
_REG_NEW_RE = re.compile(r"Regulations?\s*\(EU\)\s*(20[0-9]{2})/(\d{1,4})", re.IGNORECASE)
_REG_OLD_RE = re.compile(
    r"Regulations?\s*\(EU\)(?:\s*No)?\s*(\d{1,4})/((?:19|20)[0-9]{2})",
    re.IGNORECASE,
)
_DEC_NEW_RE = re.compile(r"Decisions?\s*\(EU\)\s*(20[0-9]{2})/(\d{1,4})", re.IGNORECASE)


def _normalize(text: str) -> str:
    """Strip HTML/JSON escapes that block our regex matches.

    Press releases stored from the JSON scrape sometimes have backslash-
    escaped slashes (\\/) instead of plain /, which breaks the CELEX
    pattern matchers below.
    """
    return text.replace("\\/", "/").replace("&nbsp;", " ").replace(" ", " ")


def extract_related_celex(text: str) -> List[str]:
    """Pull all referenced CELEX numbers from a press-release text."""
    if not text:
        return []
    text = _normalize(text)
    out: List[str] = []
    for m in _DIR_NEW_RE.finditer(text):
        out.append(f"3{m.group(1)}L{int(m.group(2)):04d}")
    for m in _DIR_OLD_RE.finditer(text):
        out.append(f"3{m.group(1)}L{int(m.group(2)):04d}")
    for m in _REG_NEW_RE.finditer(text):
        out.append(f"3{m.group(1)}R{int(m.group(2)):04d}")
    for m in _REG_OLD_RE.finditer(text):
        # legacy form: Regulation (EU) No 952/2013 → 32013R0952
        out.append(f"3{m.group(2)}R{int(m.group(1)):04d}")
    for m in _DEC_NEW_RE.finditer(text):
        out.append(f"3{m.group(1)}D{int(m.group(2)):04d}")
    # de-dupe preserving order
    seen = set()
    return [c for c in out if not (c in seen or seen.add(c))]


# Sector keyword map. Order matters — first match wins.
_SECTOR_MAP: List[Tuple[str, List[str], str]] = [
    ("environment", ["wastewater", "waste water", "landfill", "environmental impact", "air quality", "biodiversity",
                     "habitat", "marine pollution", "drinking water", "ozone", "f-gas", "f gas",
                     "birds directive", "habitats directive", "water framework", "nature restoration",
                     "single-use plastic", "industrial emission", "noise"], "ENV"),
    ("taxation", ["vat", "value-added tax", "customs duty", "anti-tax avoidance", "exit tax", "taxation",
                  "retail tax", "tax regime", "freedom of establishment", "tax law"], "TAXUD"),
    ("home affairs", ["migration", "asylum", "border control", "visa", "schengen",
                      "trafficking in human beings", "victims' rights"], "HOME"),
    ("justice", ["rule of law", "fundamental rights", "judicial cooperation", "fight against corruption",
                 "victims of crime", "european arrest warrant", "anti-money laundering directive",
                 "data protection directive"], "JUST"),
    ("energy", ["energy efficiency", "renewable energy", "electricity market", "gas market",
                "energy performance", "internal energy market", "eu emissions trading"], "ENER"),
    ("digital", ["telecom", "audiovisual media services", "data protection", "gdpr", "digital services",
                 "artificial intelligence", "european electronic communications", "digital markets act",
                 "open internet"], "CNECT"),
    ("transport", ["road transport", "aviation", "maritime safety", "rail safety", "single european sky",
                   "interoperability of the rail system", "railway area directive", "rail regulator",
                   "driving licence", "passenger rights"], "MOVE"),
    ("employment", ["working time", "posting of workers", "occupational safety", "equal treatment in employment",
                    "work-life balance", "minimum wage directive", "transparent and predictable working"], "EMPL"),
    ("agriculture", ["common agricultural policy", "rural development", "organic production",
                     "plant health", "phytosanitary", "wine regulation"], "AGRI"),
    ("public health", ["medical devices", "tobacco products", "pharmaceutical", "patient rights",
                       "blood, tissues and cells", "human medicines", "veterinary medicines"], "SANTE"),
    ("competition", ["state aid", "merger control", "antitrust", "abuse of dominant position"], "COMP"),
    ("financial services", ["capital markets", "insurance", "banking union", "anti-money laundering",
                            "investment firms", "credit institutions", "settlement finality", "mifid"], "FISMA"),
    ("trade", ["trade defence", "anti-dumping", "trade barriers", "trade in dual-use"], "TRADE"),
    ("internal market", ["public procurement", "free movement", "services directive",
                         "size criteria for micro", "small, medium-sized and large undertakings"], "GROW"),
    ("fisheries", ["common fisheries policy", "marine fisheries", "fishing fleet"], "MARE"),
]


def derive_sector(text: str) -> Tuple[Optional[str], List[str]]:
    """Return (sector_label, policy_areas_list).

    Walks the keyword map; first matched bucket sets the canonical sector.
    Multiple buckets may match (a press release can touch several policy
    areas) — we collect them all into policy_areas.
    """
    if not text:
        return None, []
    lowered = _normalize(text).lower()
    sector = None
    policies: List[str] = []
    for label, kws, dg in _SECTOR_MAP:
        if any(kw in lowered for kw in kws):
            if sector is None:
                sector = label
            if label not in policies:
                policies.append(label)
    return sector, policies


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=200)
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id::text, inf_reference, title, summary, sector, related_celex, policy_areas
          FROM infringement_procedures
         WHERE (sector IS NULL OR
                related_celex IS NULL OR array_length(related_celex,1) IS NULL OR
                policy_areas IS NULL OR array_length(policy_areas,1) IS NULL)
         ORDER BY decision_date DESC NULLS LAST
         LIMIT %s
        """,
        (args.limit,),
    )
    rows = cur.fetchall()
    cur.close()
    print(f"[INFO] {len(rows)} rows queued (apply={args.apply})")

    updated = unchanged = 0
    for row_id, ref, title, summary, sector_in, related_in, policies_in in rows:
        text = " ".join(t for t in (title, summary) if t)
        celex_list = extract_related_celex(text)
        sector, policies = derive_sector(text)

        sets = []
        params: List[object] = []
        if sector and not sector_in:
            sets.append("sector = %s")
            params.append(sector)
        if celex_list and not (related_in or []):
            sets.append("related_celex = %s")
            params.append(celex_list)
        if policies and not (policies_in or []):
            sets.append("policy_areas = %s")
            params.append(policies)

        if not sets:
            unchanged += 1
            continue

        print(f"  [OK] {ref}: sector={sector!r} celex={celex_list[:3]} policies={policies}")
        updated += 1
        if args.apply:
            sets.append("last_updated = NOW()")
            params.append(row_id)
            cur2 = conn.cursor()
            cur2.execute(
                f"UPDATE infringement_procedures SET {', '.join(sets)} WHERE id = %s",
                params,
            )
            conn.commit()
            cur2.close()

    conn.close()
    print(f"[DONE] updated={updated} unchanged={unchanged}{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    main()
