"""
Ingest /officials from existing organigramme JSONs.

Source: backend/knowledge_base/ec_organigrammes/json/{INSTITUTION,DG}.json
Target: eu_officials table.

Each JSON has the shape:
{
    "institution": "COMMISSION",
    "source": "euwhoiswho_commission.pdf",
    "units": {
        "UNIT NAME": {
            "name": "UNIT NAME",
            "persons": [
                {"name": "...", "title": "...", "email": "...", "phone": "..."}
            ]
        }
    }
}
"""

import json
import os
import re
import sys
import uuid
from pathlib import Path

import psycopg2

ROOT = Path(__file__).resolve().parents[2]
JSON_DIR = ROOT / "backend" / "knowledge_base" / "ec_organigrammes" / "json"


# Map JSON institution code to canonical institution_slug used by /api/v1/institutions
INSTITUTION_MAP = {
    "COMMISSION": "european-commission",
    "EP": "european-parliament",
    "COUNCIL_EU": "council-of-the-eu",
    "EUROPEAN_COUNCIL": "european-council",
    "ECB": "european-central-bank",
    "ECJ": "court-of-justice",
    "ECA": "european-court-of-auditors",
    "EEAS": "eeas",
    "COR": "committee-of-the-regions",
    "EESC": "european-economic-and-social-committee",
    "EIB": "european-investment-bank",
    "EIF": "european-investment-fund",
    "EDPS": "edps",
    "OMBUDSMAN": "european-ombudsman",
    "EURCOU": "european-council",
    "GSC": "council-of-the-eu",
    "EPSO": "european-commission",
    "DGT": "european-commission",
    "ESTAT": "european-commission",
    "EP_MEPS": "european-parliament",
    "EP_GROUP_SEC": "european-parliament",
    "EP_SG": "european-parliament",
    "COREPER": "council-of-the-eu",
    # AGENCIES is intentionally NOT mapped here — handled separately by the
    # agency-specific routing below so each agency gets its own slug.
}

# When the JSON stem is "AGENCIES", the unit name often starts with the
# agency code/name. Map known agencies to their canonical slug.
AGENCY_BY_UNIT_PREFIX = {
    "FRONTEX": "frontex",
    "EUROPEAN BORDER": "frontex",
    "EEA": "eea",
    "ENVIRONMENT AGENCY": "eea",
    "EMA": "ema",
    "MEDICINES": "ema",
    "ECHA": "echa",
    "CHEMICALS": "echa",
    "EFSA": "efsa",
    "FOOD SAFETY": "efsa",
    "EASA": "easa",
    "AVIATION": "easa",
    "ERA": "era",
    "RAILWAYS": "era",
    "ENISA": "enisa",
    "CYBERSECURITY": "enisa",
    "ESMA": "esma",
    "SECURITIES": "esma",
    "EBA": "eba",
    "BANKING": "eba",
    "EIOPA": "eiopa",
    "INSURANCE": "eiopa",
    "FRA": "fra",
    "FUNDAMENTAL RIGHTS": "fra",
    "EUROPOL": "europol",
    "EUROJUST": "eurojust",
    "CEDEFOP": "cedefop",
    "EIGE": "eige",
    "GENDER": "eige",
    "ECDC": "ecdc",
    "DISEASE": "ecdc",
    "ETF": "etf",
    "TRAINING FOUNDATION": "etf",
    "EU-OSHA": "eu-osha",
    "EUROFOUND": "eufound",
    "EUIPO": "euipo",
    "INTELLECTUAL PROPERTY": "euipo",
    "CPVO": "cpvo",
    "PLANT VARIETY": "cpvo",
    "EUDA": "euda",
    "DRUGS AGENCY": "euda",
}


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = s.strip("-")
    return s[:100] if s else "unknown"


def main():
    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    db_url = get_database_url()
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    seen_slugs = set()

    files = sorted(JSON_DIR.glob("*.json"))
    print(f"Found {len(files)} organigramme JSONs")

    for f in files:
        stem = f.stem  # e.g. "COMMISSION", "AGRI"
        institution_slug = INSTITUTION_MAP.get(stem)
        is_agencies_dump = stem == "AGENCIES"
        # If not in the institution map, treat as a Commission DG (unless it's
        # the agencies dump, which is handled per-unit below)
        if institution_slug is None and not is_agencies_dump:
            institution_slug = "european-commission"
            dg = stem.upper()
        else:
            dg = None

        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  [SKIP] {f.name}: {e}")
            continue

        units = data.get("units")
        if not isinstance(units, dict):
            continue

        for unit_name, unit in units.items():
            if not isinstance(unit, dict):
                continue
            # If we're inside AGENCIES.json, route each unit to its agency slug.
            row_institution = institution_slug
            if is_agencies_dump:
                row_institution = "frontex"  # default
                upper_unit = unit_name.upper()
                for prefix, slug in AGENCY_BY_UNIT_PREFIX.items():
                    if prefix in upper_unit:
                        row_institution = slug
                        break
            persons = unit.get("persons", [])
            for p in persons:
                if not isinstance(p, dict):
                    continue
                name = (p.get("name") or "").strip()
                if not name or len(name) < 3:
                    skipped += 1
                    continue
                title = (p.get("title") or "").strip()[:255] or None
                email = (p.get("email") or "").strip()[:255] or None
                phone = (p.get("phone") or "").strip()[:50] or None

                # Build slug. Prefer email's local part for uniqueness, else name+unit.
                if email:
                    base = email.split("@")[0]
                    slug = slugify(f"{base}-{stem.lower()}")
                else:
                    slug = slugify(f"{name}-{unit_name[:30]}-{stem.lower()}")

                if slug in seen_slugs:
                    skipped += 1
                    continue
                seen_slugs.add(slug)

                role = unit_name[:255]
                official_id = uuid.uuid4()
                try:
                    cur.execute("""
                        INSERT INTO eu_officials (
                            id, slug, name, title, role,
                            institution_slug, dg, cabinet,
                            email, phone, is_active
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (slug) DO NOTHING
                    """, (
                        str(official_id), slug, name[:255], title, role,
                        row_institution, dg, None,
                        email, phone, True,
                    ))
                    if cur.rowcount > 0:
                        inserted += 1
                except Exception as e:
                    skipped += 1
                    if "duplicate key" not in str(e).lower():
                        print(f"  [ERR] {name}: {str(e)[:100]}")
                    conn.rollback()
                    continue

        conn.commit()
        print(f"  [OK] {f.name}: running total inserted={inserted}")

    cur.execute("SELECT COUNT(*) FROM eu_officials")
    total = cur.fetchone()[0]
    cur.close()
    conn.close()
    print(f"\n=== DONE ===")
    print(f"Inserted this run: {inserted}")
    print(f"Skipped: {skipped}")
    print(f"Total in eu_officials: {total}")


if __name__ == "__main__":
    main()
