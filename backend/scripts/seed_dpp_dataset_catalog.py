"""Register the Digital Product Passport corpus in Brubru Databases.

MEUB's Brubru Databases tab reads brubru_dataset_catalog, a DCAT catalogue. The
DPP folder was live at /api/v2/dpp and answering questions, but it was not
discoverable as a dataset: nothing in the product told a user it existed.

Every EuroVoc theme here was LOOKED UP in eurovoc_concepts, not invented. That
matters: searching "recycling" returns c_2946 "recycling of capital", a
financial concept, which would have mis-filed a waste-law dataset under
corporate finance. The waste sense is 2947.

Descriptions are in all six Brubru languages. The client this was built for
works in Catalan, and a catalogue entry a user cannot read is not a catalogue
entry.

Idempotent on dcat_uri.
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

URI = "https://brubru.beresol.eu/datasets/eu-digital-product-passport"
TITLE = "EU Digital Product Passport regime (ESPR, registry, standards, sectors)"

DESCRIPTION = {
    "en": ("The EU Digital Product Passport as one queryable corpus: the acts that "
           "create passport obligations with their full legal text, when each product "
           "sector's passport becomes mandatory, how registration in the central "
           "registry works, the six harmonised standards carrying a presumption of "
           "conformity, and the 71 battery passport data points with their legal "
           "source and applicability by battery type. Built from Regulation (EU) "
           "2024/1781 (ESPR) and Commission Implementing Regulation (EU) 2026/1778."),
    "ca": ("El passaport digital de producte de la UE com un sol corpus consultable: "
           "els actes que creen les obligacions de passaport amb el text legal "
           "complet, quan esdevé obligatori per a cada sector de producte, com "
           "funciona el registre central, les sis normes harmonitzades que donen "
           "presumpció de conformitat, i els 71 punts de dades del passaport de "
           "bateries amb la seva base legal i aplicabilitat per tipus de bateria."),
    "es": ("El pasaporte digital de producto de la UE como un corpus consultable: los "
           "actos que crean las obligaciones de pasaporte con su texto legal "
           "completo, cuándo pasa a ser obligatorio en cada sector de producto, cómo "
           "funciona el registro central, las seis normas armonizadas que otorgan "
           "presunción de conformidad, y los 71 puntos de datos del pasaporte de "
           "baterías con su base legal y aplicabilidad por tipo de batería."),
    "fr": ("Le passeport numérique de produit de l'UE en un seul corpus interrogeable: "
           "les actes qui créent les obligations de passeport avec leur texte légal "
           "intégral, la date à laquelle il devient obligatoire pour chaque secteur, "
           "le fonctionnement du registre central, les six normes harmonisées "
           "conférant une présomption de conformité, et les 71 points de données du "
           "passeport de batteries."),
    "it": ("Il passaporto digitale di prodotto dell'UE come un unico corpus "
           "consultabile: gli atti che creano gli obblighi di passaporto con il testo "
           "giuridico integrale, quando diventa obbligatorio per ciascun settore, come "
           "funziona il registro centrale, le sei norme armonizzate che conferiscono "
           "presunzione di conformità, e i 71 punti dati del passaporto delle batterie."),
    "nl": ("Het digitale productpaspoort van de EU als één doorzoekbaar corpus: de "
           "handelingen die paspoortverplichtingen scheppen met hun volledige "
           "wettekst, wanneer het per productsector verplicht wordt, hoe het centrale "
           "register werkt, de zes geharmoniseerde normen die een vermoeden van "
           "conformiteit geven, en de 71 gegevenspunten van het batterijpaspoort."),
}

# All verified against eurovoc_concepts. 2947 is "waste recycling"; 2946 is
# "recycling of capital" and would file this under corporate finance.
THEMES = [
    "http://eurovoc.europa.eu/c_18802d13",   # ecodesign
    "http://eurovoc.europa.eu/c_1138d9d2",   # circular economy
    "http://eurovoc.europa.eu/71",           # product design
    "http://eurovoc.europa.eu/1158",         # waste management
    "http://eurovoc.europa.eu/2947",         # waste recycling
    "http://eurovoc.europa.eu/1418",         # textile industry
    "http://eurovoc.europa.eu/5235",         # technical standard
    "http://eurovoc.europa.eu/4036",         # product safety
    "http://eurovoc.europa.eu/1425",         # consumer information
    "http://eurovoc.europa.eu/7219",         # digital technology
]

API = "https://brubru-production.up.railway.app/api/v2/dpp"
DISTRIBUTION = [
    {"title": "Legal framework: the acts that create passport obligations, with full text",
     "format": "JSON", "access_url": f"{API}/legal-framework", "media_type": "application/json"},
    {"title": "Sector rollout: when each product group's passport becomes mandatory",
     "format": "JSON", "access_url": f"{API}/sectors", "media_type": "application/json"},
    {"title": "Registry: environments, registration pathways, the unique registration identifier",
     "format": "JSON", "access_url": f"{API}/registry", "media_type": "application/json"},
    {"title": "Harmonised standards carrying a presumption of conformity",
     "format": "JSON", "access_url": f"{API}/standards", "media_type": "application/json"},
    {"title": "Battery passport data points, by category and battery type",
     "format": "JSON", "access_url": f"{API}/data-points", "media_type": "application/json"},
    {"title": "Commission guidance, audience guides, news and events",
     "format": "JSON", "access_url": f"{API}/guidance", "media_type": "application/json"},
    {"title": "Model Context Protocol server (Brubru DPP), 11 tools",
     "format": "JSON-RPC", "access_url": "https://brubru-production.up.railway.app/api/mcp/dpp",
     "media_type": "application/json"},
]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        # the themes must exist; a dangling EuroVoc URI is worse than none
        missing = []
        for uri in THEMES:
            n = db.execute(
                text("SELECT count(*) FROM eurovoc_concepts WHERE concept_uri = :u"),
                {"u": uri},
            ).scalar()
            if not n:
                missing.append(uri)
        print(f"=== EuroVoc themes: {len(THEMES) - len(missing)}/{len(THEMES)} resolve ===")
        if missing:
            print(f"  [FAIL] not in eurovoc_concepts: {missing}")
            return 1

        exists = db.execute(
            text("SELECT count(*) FROM brubru_dataset_catalog WHERE dcat_uri = :u"),
            {"u": URI},
        ).scalar()
        print(f"=== catalogue entry {'exists, updating' if exists else 'is new'} ===")
        print(f"  title        : {TITLE}")
        print(f"  languages    : {sorted(DESCRIPTION)}")
        print(f"  themes       : {len(THEMES)}")
        print(f"  distributions: {len(DISTRIBUTION)}")

        if args.apply:
            if exists:
                db.execute(
                    text("""UPDATE brubru_dataset_catalog SET
                            title = :t, description = CAST(:d AS jsonb),
                            dcat_theme = :th, distribution = CAST(:di AS jsonb),
                            license = :l, accrual_periodicity = :p,
                            last_validated_at = now(), updated_at = now()
                        WHERE dcat_uri = :u"""),
                    {"t": TITLE, "d": json.dumps(DESCRIPTION, ensure_ascii=False),
                     "th": THEMES, "di": json.dumps(DISTRIBUTION, ensure_ascii=False),
                     "l": "http://creativecommons.org/licenses/by/4.0/",
                     "p": "P1D", "u": URI},
                )
            else:
                db.execute(
                    text("""INSERT INTO brubru_dataset_catalog
                            (dcat_uri, title, description, dcat_theme, distribution,
                             license, accrual_periodicity, last_validated_at,
                             created_at, updated_at)
                            VALUES (:u, :t, CAST(:d AS jsonb), :th, CAST(:di AS jsonb),
                                    :l, :p, now(), now(), now())"""),
                    {"u": URI, "t": TITLE,
                     "d": json.dumps(DESCRIPTION, ensure_ascii=False),
                     "th": THEMES, "di": json.dumps(DISTRIBUTION, ensure_ascii=False),
                     "l": "http://creativecommons.org/licenses/by/4.0/", "p": "P1D"},
                )
            db.commit()

            print("\n=== verification ===")
            r = db.execute(
                text("SELECT title, description, dcat_theme, distribution "
                     "FROM brubru_dataset_catalog WHERE dcat_uri = :u"), {"u": URI}
            ).fetchone()
            langs = sorted(r.description.keys())
            print(f"  stored title : {r.title[:60]}")
            print(f"  languages    : {langs} "
                  f"{'OK' if set(langs) == {'en','ca','es','fr','it','nl'} else 'FAIL'}")
            print(f"  themes       : {len(r.dcat_theme)} "
                  f"{'OK' if len(r.dcat_theme) == len(THEMES) else 'FAIL'}")
            print(f"  distributions: {len(r.distribution)} "
                  f"{'OK' if len(r.distribution) == len(DISTRIBUTION) else 'FAIL'}")
            total = db.execute(text("SELECT count(*) FROM brubru_dataset_catalog")).scalar()
            print(f"  catalogue now: {total} datasets")
            if set(langs) != {"en", "ca", "es", "fr", "it", "nl"}:
                rc = 1
        else:
            print("\n[DRY-RUN] nothing written")
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
