"""Give every dataset in the catalogue a title in all six Brubru languages.

Runs migration 216 if title_i18n is not there yet, then backfills the eight
rows. Titles are translated, not transliterated: "EU authority labels" is the
Publications Office notion of an authority table, so Catalan gets "etiquetes
d'autoritat", not a literal rendering of "labels".

Names that are proper nouns stay put: Brubru, ESPR, DCAT, TSVECTOR, europa.eu,
and the acronyms inside parentheses.

Idempotent.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from core.database import SessionLocal

BASE = "https://brubru.beresol.eu/datasets/"

TITLES = {
    "chat-knowledge-guides": {
        "en": "Brubru chat knowledge guides",
        "ca": "Guies de coneixement del xat de Brubru",
        "es": "Guías de conocimiento del chat de Brubru",
        "fr": "Guides de connaissance du chat Brubru",
        "it": "Guide di conoscenza della chat di Brubru",
        "nl": "Kennisgidsen van de Brubru-chat",
    },
    "v1-rest-api": {
        "en": "Brubru v1 REST API",
        "ca": "API REST v1 de Brubru",
        "es": "API REST v1 de Brubru",
        "fr": "API REST v1 de Brubru",
        "it": "API REST v1 di Brubru",
        "nl": "Brubru v1 REST-API",
    },
    "catalan-eu-laws": {
        "en": "Catalan translations of EU legislation",
        "ca": "Traduccions al català de la legislació de la UE",
        "es": "Traducciones al catalán de la legislación de la UE",
        "fr": "Traductions en catalan de la législation de l'UE",
        "it": "Traduzioni in catalano della legislazione dell'UE",
        "nl": "Catalaanse vertalingen van EU-wetgeving",
    },
    "eu-vocabularies": {
        "en": "EU authority labels (Brubru cache)",
        "ca": "Etiquetes d'autoritat de la UE (memòria cau de Brubru)",
        "es": "Etiquetas de autoridad de la UE (caché de Brubru)",
        "fr": "Libellés d'autorité de l'UE (cache Brubru)",
        "it": "Etichette di autorità dell'UE (cache di Brubru)",
        "nl": "EU-autoriteitslabels (Brubru-cache)",
    },
    "eu-digital-product-passport": {
        "en": "EU Digital Product Passport regime (ESPR, registry, standards, sectors)",
        "ca": "Règim del passaport digital de producte de la UE (ESPR, registre, normes, sectors)",
        "es": "Régimen del pasaporte digital de producto de la UE (ESPR, registro, normas, sectores)",
        "fr": "Régime du passeport numérique de produit de l'UE (ESPR, registre, normes, secteurs)",
        "it": "Regime del passaporto digitale di prodotto dell'UE (ESPR, registro, norme, settori)",
        "nl": "Regeling digitaal productpaspoort van de EU (ESPR, register, normen, sectoren)",
    },
    "eu-laws-tsvector": {
        "en": "EU legislation TSVECTOR corpus (eu_laws)",
        "ca": "Corpus TSVECTOR de la legislació de la UE (eu_laws)",
        "es": "Corpus TSVECTOR de la legislación de la UE (eu_laws)",
        "fr": "Corpus TSVECTOR de la législation de l'UE (eu_laws)",
        "it": "Corpus TSVECTOR della legislazione dell'UE (eu_laws)",
        "nl": "TSVECTOR-corpus van EU-wetgeving (eu_laws)",
    },
    "textile-circularity-corpus": {
        "en": "EU textile-circularity law corpus (live-resolved)",
        "ca": "Corpus normatiu de circularitat tèxtil de la UE (resolt en directe)",
        "es": "Corpus normativo de circularidad textil de la UE (resuelto en directo)",
        "fr": "Corpus juridique de la circularité textile de l'UE (résolu en direct)",
        "it": "Corpus normativo della circolarità tessile dell'UE (risolto in tempo reale)",
        "nl": "Corpus EU-wetgeving textielcirculariteit (live opgehaald)",
    },
    "europa-source-registry": {
        "en": "europa.eu source registry",
        "ca": "Registre de fonts d'europa.eu",
        "es": "Registro de fuentes de europa.eu",
        "fr": "Registre des sources europa.eu",
        "it": "Registro delle fonti di europa.eu",
        "nl": "Bronregister van europa.eu",
    },
}

LANGS = {"en", "ca", "es", "fr", "it", "nl"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        has_col = db.execute(text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'brubru_dataset_catalog' AND column_name = 'title_i18n'"
        )).scalar()
        print(f"=== title_i18n column: {'present' if has_col else 'MISSING'} ===")
        if not has_col:
            sql = (project_root / "backend/migrations/216_dataset_catalog_title_i18n.sql").read_text()
            if args.apply:
                db.execute(text(sql))
                db.commit()
                print("  migration 216 applied")
            else:
                print("  [DRY-RUN] would apply migration 216")

        rows = db.execute(text(
            "SELECT dcat_uri, title FROM brubru_dataset_catalog ORDER BY title")).fetchall()

        # a slug in the DB with no translation here would be silently skipped
        db_slugs = {r.dcat_uri.rsplit("/", 1)[-1] for r in rows}
        missing = db_slugs - set(TITLES)
        extra = set(TITLES) - db_slugs
        print(f"\n=== coverage: {len(db_slugs)} dataset(s) in the catalogue ===")
        print(f"  without a translation here: {sorted(missing) if missing else 'none'}")
        print(f"  translated but not in the DB: {sorted(extra) if extra else 'none'}")
        if missing:
            print("  [FAIL] every dataset must be covered")
            return 1

        print("\n=== writing ===")
        for r in rows:
            slug = r.dcat_uri.rsplit("/", 1)[-1]
            t = TITLES[slug]
            if set(t) != LANGS:
                print(f"  [FAIL] {slug}: languages {sorted(t)}")
                return 1
            if t["en"] != r.title:
                # the English title is the existing row; a mismatch means the
                # translation was written against a different dataset
                print(f"  [FAIL] {slug}: English title does not match the row\n"
                      f"         row: {r.title}\n        here: {t['en']}")
                return 1
            print(f"  [OK] {slug:<30} ca={t['ca'][:44]}")
            if args.apply:
                db.execute(text(
                    "UPDATE brubru_dataset_catalog SET title_i18n = CAST(:t AS jsonb), "
                    "updated_at = now() WHERE dcat_uri = :u"),
                    {"t": json.dumps(t, ensure_ascii=False), "u": r.dcat_uri})

        if not args.apply:
            print("\n[DRY-RUN] nothing written")
            return 0

        db.commit()
        print("\n=== verification ===")
        bad = db.execute(text(
            "SELECT count(*) FROM brubru_dataset_catalog "
            "WHERE title_i18n IS NULL "
            "   OR NOT (title_i18n ?& array['en','ca','es','fr','it','nl'])")).scalar()
        total = db.execute(text("SELECT count(*) FROM brubru_dataset_catalog")).scalar()
        print(f"  datasets with all six titles: {total - bad}/{total} "
              f"{'OK' if not bad else 'FAIL'}")
        sample = db.execute(text(
            "SELECT title_i18n->>'ca' AS ca, title_i18n->>'nl' AS nl "
            "FROM brubru_dataset_catalog WHERE dcat_uri = :u"),
            {"u": BASE + "eu-digital-product-passport"}).fetchone()
        print(f"  DPP ca: {sample.ca}")
        print(f"  DPP nl: {sample.nl}")
        if bad:
            rc = 1
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
