"""
Backfill policy_areas + description on eu_calendar_events rows for Council
of the EU + European Council meetings whose council_configuration is set
but the policy/description is missing.

No upstream calls — derivation is fully deterministic from the council
formation code, which IS the authoritative classification (the Council's
own taxonomy).

Mapping based on the Council's official "configurations" page:
  https://www.consilium.europa.eu/en/council-eu/configurations/

Run:
    python3.12 backend/scripts/backfill_council_meetings_metadata.py            # dry-run
    python3.12 backend/scripts/backfill_council_meetings_metadata.py --apply
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Tuple

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


# Council formation → (full name, policy_areas, short description)
# Source: consilium.europa.eu/en/council-eu/configurations/
FORMATION_MAP: Dict[str, Tuple[str, List[str], str]] = {
    "GAC": (
        "General Affairs Council",
        ["general_affairs", "cohesion", "institutional_affairs"],
        "Coordinates Council positions on horizontal files (multiannual financial framework, "
        "enlargement, rule of law) and prepares European Council meetings.",
    ),
    "FAC": (
        "Foreign Affairs Council",
        ["foreign_affairs", "defence", "trade", "international_cooperation"],
        "EU's foreign policy, common security and defence policy, common commercial policy, "
        "and humanitarian aid. Chaired by the High Representative.",
    ),
    "ECOFIN": (
        "Economic and Financial Affairs Council",
        ["economic", "financial_services", "taxation", "budget"],
        "EU economic policy coordination, financial markets, capital movements, taxation, "
        "and macroeconomic surveillance.",
    ),
    "EUROGROUP": (
        "Eurogroup",
        ["economic", "financial_services", "budget"],
        "Informal meeting of the finance ministers of the euro-area Member States. "
        "Coordinates economic and fiscal policy in the eurozone.",
    ),
    "JHA": (
        "Justice and Home Affairs Council",
        ["justice", "home_affairs", "fundamental_rights", "migration"],
        "Internal security, civil protection, judicial cooperation, migration, asylum, "
        "external borders, and police cooperation.",
    ),
    "EPSCO": (
        "Employment, Social Policy, Health and Consumer Affairs Council",
        ["employment", "social_affairs", "public_health", "consumer_protection"],
        "Employment, social affairs, equal opportunities, health policy, and consumer "
        "protection at EU level.",
    ),
    "COMPET": (
        "Competitiveness Council",
        ["internal_market", "industrial_policy", "research_and_innovation", "space"],
        "Internal market, industry, research and innovation, and space policy. Aims to "
        "boost the EU's competitiveness and growth.",
    ),
    "TTE": (
        "Transport, Telecommunications and Energy Council",
        ["transport", "digital_society", "telecommunications", "energy"],
        "Three policy areas under one configuration: transport infrastructure and rules, "
        "telecoms and digital single market, energy security and climate-energy package.",
    ),
    "EDUC": (
        "Education, Youth, Culture and Sport Council",
        ["education_and_training", "youth", "culture", "sport", "audiovisual_media"],
        "Education, vocational training, youth policy, culture, audiovisual policy, sport, "
        "and multilingualism.",
    ),
    "EYCS": (
        "Education, Youth, Culture and Sport Council",
        ["education_and_training", "youth", "culture", "sport", "audiovisual_media"],
        "Education, vocational training, youth policy, culture, audiovisual policy, sport, "
        "and multilingualism.",
    ),
    "AGRIFISH": (
        "Agriculture and Fisheries Council",
        ["agriculture", "rural_development", "maritime_affairs_and_fisheries", "food_safety"],
        "Common Agricultural Policy, Common Fisheries Policy, food safety, animal welfare, "
        "and rural development.",
    ),
    "ENV": (
        "Environment Council",
        ["environment", "climate_action", "biodiversity", "circular_economy"],
        "EU environmental policy: pollution prevention, conservation, climate action, and "
        "international environmental agreements.",
    ),
    "ENVI": (
        "Environment Council",
        ["environment", "climate_action", "biodiversity", "circular_economy"],
        "EU environmental policy: pollution prevention, conservation, climate action, and "
        "international environmental agreements.",
    ),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id::text, council_configuration, policy_areas, description, title, institution
          FROM eu_calendar_events
         WHERE institution IN ('COUNCIL','EUROPEAN_COUNCIL')
        """
    )
    rows = cur.fetchall()
    cur.close()
    print(f"[INFO] {len(rows)} council/european-council rows queued (apply={args.apply})")

    updated = unchanged = unmapped = 0
    for row_id, cfg, pa, desc, title, institution in rows:
        # European Council (heads of state) — no formation code, fixed scope.
        if institution == "EUROPEAN_COUNCIL":
            policies = ["general_affairs", "institutional_affairs", "foreign_affairs", "economic"]
            short_desc = (
                "Heads of state or government of the EU Member States, the President of the "
                "European Council, and the President of the European Commission. Sets the "
                "Union's general political direction and priorities."
            )
        else:
            mapping = FORMATION_MAP.get(cfg)
            if not mapping:
                unmapped += 1
                print(f"  [unmapped formation] {cfg}: {title}")
                continue
            _, policies, short_desc = mapping

        sets = []
        params: List[object] = []
        if not pa or len(pa) == 0:
            sets.append("policy_areas = %s")
            params.append(policies)
        if not desc:
            sets.append("description = %s")
            params.append(short_desc)

        if not sets:
            unchanged += 1
            continue

        updated += 1
        if args.apply:
            sets.append("last_updated = NOW()")
            params.append(row_id)
            cur2 = conn.cursor()
            cur2.execute(
                f"UPDATE eu_calendar_events SET {', '.join(sets)} WHERE id = %s",
                params,
            )
            conn.commit()
            cur2.close()

    conn.close()
    print(
        f"[DONE] updated={updated} unchanged={unchanged} unmapped={unmapped}"
        f"{' (applied)' if args.apply else ' (dry-run)'}"
    )


if __name__ == "__main__":
    main()
