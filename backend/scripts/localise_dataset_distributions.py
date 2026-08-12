"""Translate the distribution tooltips, and correct the API card to v2.

Two things Victor caught on the Open datasets cards.

The tooltips were English for every reader. Each distribution carried a single
`title`, which the UI puts in the hover text, so a Catalan user reading Catalan
cards got "v1 API: list knowledge guides" the moment they hovered. Each
distribution now carries title_i18n in all six languages and the endpoint serves
the caller's own.

The API card said "API REST v1 de Brubru". Brubru's API is v2. Measured from the
live OpenAPI document rather than from memory: /api/v2 has 994 endpoints across
92 body folders, /api/v1 has 203. The card was naming the older surface and
citing "over 120 endpoints", which matched neither.
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

LANGS = ["en", "ca", "es", "fr", "it", "nl"]
V1 = "https://brubru.beresol.eu/datasets/v1-rest-api"
V2 = "https://brubru.beresol.eu/datasets/v2-rest-api"

# The v1 entry becomes the v2 entry: same dataset, correct name and numbers.
API_TITLE = {
    "en": "Brubru REST API v2",
    "ca": "API REST v2 de Brubru",
    "es": "API REST v2 de Brubru",
    "fr": "API REST v2 de Brubru",
    "it": "API REST v2 di Brubru",
    "nl": "Brubru REST-API v2",
}
API_DESC = {
    "en": "Brubru's data, for your own software instead of the screen. 994 endpoints across 92 institutional folders: EU law, procedures, MEPs, the calendar, consultations, funding, tenders and predictions, at 60 requests a minute per key.",
    "ca": "Les dades de Brubru, per al teu propi programari en lloc de la pantalla. 994 punts d'accés repartits en 92 carpetes institucionals: legislació de la UE, procediments, eurodiputats, calendari, consultes, finançament, licitacions i prediccions, a 60 peticions per minut per clau.",
    "es": "Los datos de Brubru, para tu propio software en lugar de la pantalla. 994 puntos de acceso repartidos en 92 carpetas institucionales: legislación de la UE, procedimientos, eurodiputados, calendario, consultas, financiación, licitaciones y predicciones, a 60 peticiones por minuto por clave.",
    "fr": "Les données de Brubru, pour vos propres logiciels plutôt que pour l'écran. 994 points d'accès répartis en 92 dossiers institutionnels : droit de l'UE, procédures, députés, calendrier, consultations, financements, marchés et prévisions, à 60 requêtes par minute par clé.",
    "it": "I dati di Brubru, per il tuo software invece che per lo schermo. 994 endpoint distribuiti in 92 cartelle istituzionali: diritto dell'UE, procedure, europarlamentari, calendario, consultazioni, finanziamenti, gare e previsioni, a 60 richieste al minuto per chiave.",
    "nl": "De data van Brubru, voor je eigen software in plaats van het scherm. 994 endpoints in 92 institutionele mappen: EU-recht, procedures, Europarlementsleden, agenda, consultaties, financiering, aanbestedingen en voorspellingen, met 60 verzoeken per minuut per sleutel.",
}

# url -> tooltip in six languages. Keys are matched on access_url.
TIPS = {
"https://brubru.beresol.eu/guides/": {
 "en": "The public index of knowledge guides", "ca": "L'índex públic de guies de coneixement",
 "es": "El índice público de guías de conocimiento", "fr": "L'index public des guides de connaissance",
 "it": "L'indice pubblico delle guide di conoscenza", "nl": "De openbare index van kennisgidsen"},
"https://brubru-production.up.railway.app/api/v1/knowledge-guides": {
 "en": "API: list the knowledge guides", "ca": "API: llista les guies de coneixement",
 "es": "API: lista las guías de conocimiento", "fr": "API : lister les guides de connaissance",
 "it": "API: elenca le guide di conoscenza", "nl": "API: de kennisgidsen opvragen"},
"https://brubru-production.up.railway.app/openapi.json": {
 "en": "The machine-readable description of every endpoint",
 "ca": "La descripció llegible per màquina de tots els punts d'accés",
 "es": "La descripción legible por máquina de todos los puntos de acceso",
 "fr": "La description lisible par machine de tous les points d'accès",
 "it": "La descrizione leggibile dalle macchine di tutti gli endpoint",
 "nl": "De machineleesbare beschrijving van alle endpoints"},
"https://brubru.beresol.eu/api/docs": {
 "en": "The API documentation, written for people",
 "ca": "La documentació de l'API, escrita per a persones",
 "es": "La documentación de la API, escrita para personas",
 "fr": "La documentation de l'API, écrite pour des humains",
 "it": "La documentazione dell'API, scritta per le persone",
 "nl": "De API-documentatie, voor mensen geschreven"},
"https://brubru.beresol.eu/legislacio-ue-catala/": {
 "en": "The Catalan legislation pages, one per act",
 "ca": "Les pàgines de legislació en català, una per acte",
 "es": "Las páginas de legislación en catalán, una por acto",
 "fr": "Les pages de législation en catalan, une par acte",
 "it": "Le pagine di legislazione in catalano, una per atto",
 "nl": "De Catalaanse wetgevingspagina's, één per handeling"},
"https://brubru-production.up.railway.app/api/v1/vocabularies/corporate-bodies": {
 "en": "API: EU institutions and bodies", "ca": "API: institucions i organismes de la UE",
 "es": "API: instituciones y organismos de la UE", "fr": "API : institutions et organes de l'UE",
 "it": "API: istituzioni e organi dell'UE", "nl": "API: EU-instellingen en -organen"},
"https://brubru-production.up.railway.app/api/v1/vocabularies/procedures": {
 "en": "API: legislative procedure types", "ca": "API: tipus de procediment legislatiu",
 "es": "API: tipos de procedimiento legislativo", "fr": "API : types de procédure législative",
 "it": "API: tipi di procedura legislativa", "nl": "API: soorten wetgevingsprocedure"},
"https://brubru-production.up.railway.app/api/v1/vocabularies/directories": {
 "en": "API: the directory of EU legislation", "ca": "API: el repertori de la legislació de la UE",
 "es": "API: el repertorio de la legislación de la UE", "fr": "API : le répertoire de la législation de l'UE",
 "it": "API: il repertorio della legislazione dell'UE", "nl": "API: het register van EU-wetgeving"},
"https://brubru-production.up.railway.app/api/v1/vocabularies/modification-types": {
 "en": "API: how one act changes another", "ca": "API: com un acte modifica un altre",
 "es": "API: cómo un acto modifica otro", "fr": "API : comment un acte en modifie un autre",
 "it": "API: come un atto ne modifica un altro", "nl": "API: hoe de ene handeling de andere wijzigt"},
"https://brubru-production.up.railway.app/api/v2/dpp/legal-framework": {
 "en": "The acts that impose a passport, with their full legal text",
 "ca": "Els actes que imposen un passaport, amb el text legal complet",
 "es": "Los actos que imponen un pasaporte, con su texto legal completo",
 "fr": "Les actes qui imposent un passeport, avec leur texte légal intégral",
 "it": "Gli atti che impongono un passaporto, con il testo giuridico integrale",
 "nl": "De handelingen die een paspoort verplichten, met hun volledige wettekst"},
"https://brubru-production.up.railway.app/api/v2/dpp/sectors": {
 "en": "When each product sector's passport becomes mandatory",
 "ca": "Quan esdevé obligatori el passaport de cada sector de producte",
 "es": "Cuándo pasa a ser obligatorio el pasaporte de cada sector de producto",
 "fr": "Quand le passeport de chaque secteur devient obligatoire",
 "it": "Quando il passaporto di ciascun settore diventa obbligatorio",
 "nl": "Wanneer het paspoort per productsector verplicht wordt"},
"https://brubru-production.up.railway.app/api/v2/dpp/registry": {
 "en": "The central registry: how to register and what you get back",
 "ca": "El registre central: com registrar-s'hi i què et retorna",
 "es": "El registro central: cómo registrarse y qué devuelve",
 "fr": "Le registre central : comment s'enregistrer et ce qu'il renvoie",
 "it": "Il registro centrale: come registrarsi e cosa restituisce",
 "nl": "Het centrale register: hoe je registreert en wat je terugkrijgt"},
"https://brubru-production.up.railway.app/api/v2/dpp/standards": {
 "en": "The harmonised standards that give a presumption of conformity",
 "ca": "Les normes harmonitzades que donen presumpció de conformitat",
 "es": "Las normas armonizadas que dan presunción de conformidad",
 "fr": "Les normes harmonisées qui confèrent une présomption de conformité",
 "it": "Le norme armonizzate che conferiscono presunzione di conformità",
 "nl": "De geharmoniseerde normen die een vermoeden van conformiteit geven"},
"https://brubru-production.up.railway.app/api/v2/dpp/data-points": {
 "en": "The 71 battery passport data points, by category and battery type",
 "ca": "Els 71 punts de dades del passaport de bateries, per categoria i tipus",
 "es": "Los 71 puntos de datos del pasaporte de baterías, por categoría y tipo",
 "fr": "Les 71 points de données du passeport de batteries, par catégorie et type",
 "it": "I 71 punti dati del passaporto delle batterie, per categoria e tipo",
 "nl": "De 71 gegevenspunten van het batterijpaspoort, per categorie en type"},
"https://brubru-production.up.railway.app/api/v2/dpp/guidance": {
 "en": "Commission guidance, news and events on the passport",
 "ca": "Orientacions de la Comissió, notícies i actes sobre el passaport",
 "es": "Orientaciones de la Comisión, noticias y actos sobre el pasaporte",
 "fr": "Orientations de la Commission, actualités et événements sur le passeport",
 "it": "Orientamenti della Commissione, notizie ed eventi sul passaporto",
 "nl": "Richtsnoeren van de Commissie, nieuws en evenementen over het paspoort"},
"https://brubru-production.up.railway.app/api/mcp/dpp": {
 "en": "The Brubru DPP server for AI assistants, 11 tools",
 "ca": "El servidor Brubru DPP per a assistents d'IA, 11 eines",
 "es": "El servidor Brubru DPP para asistentes de IA, 11 herramientas",
 "fr": "Le serveur Brubru DPP pour assistants IA, 11 outils",
 "it": "Il server Brubru DPP per assistenti IA, 11 strumenti",
 "nl": "De Brubru DPP-server voor AI-assistenten, 11 tools"},
"https://brubru.beresol.eu/api/": {
 "en": "The Brubru API page, which documents these sources",
 "ca": "La pàgina de l'API de Brubru, que documenta aquestes fonts",
 "es": "La página de la API de Brubru, que documenta estas fuentes",
 "fr": "La page de l'API de Brubru, qui documente ces sources",
 "it": "La pagina dell'API di Brubru, che documenta queste fonti",
 "nl": "De Brubru API-pagina, die deze bronnen documenteert"},
"https://brubru-production.up.railway.app/api/v1/laws": {
 "en": "API: search EU legislation", "ca": "API: cerca la legislació de la UE",
 "es": "API: busca la legislación de la UE", "fr": "API : rechercher la législation de l'UE",
 "it": "API: cerca la legislazione dell'UE", "nl": "API: zoek in EU-wetgeving"},
"https://brubru-production.up.railway.app/api/v2/proprietary/textile-circularity": {
 "en": "API: the textile circularity corpus", "ca": "API: el corpus de circularitat tèxtil",
 "es": "API: el corpus de circularidad textil", "fr": "API : le corpus de circularité textile",
 "it": "API: il corpus di circolarità tessile", "nl": "API: het corpus textielcirculariteit"},
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dry-run", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = SessionLocal()
    rc = 0
    try:
        rows = db.execute(text(
            "SELECT dcat_uri, distribution FROM brubru_dataset_catalog "
            "ORDER BY dcat_uri")).fetchall()

        print("=== tooltips ===")
        untranslated = []
        for r in rows:
            dists = list(r.distribution or [])
            changed = False
            for i, d in enumerate(dists):
                url = d.get("access_url")
                tip = TIPS.get(url)
                if not tip:
                    untranslated.append(url)
                    continue
                if sorted(tip) != sorted(LANGS):
                    print(f"  [FAIL] {url}: languages {sorted(tip)}")
                    return 1
                if d.get("title_i18n") != tip:
                    dists[i] = {**d, "title_i18n": tip, "title": tip["en"]}
                    changed = True
            if changed and args.apply:
                db.execute(text(
                    "UPDATE brubru_dataset_catalog SET distribution = CAST(:d AS jsonb), "
                    "updated_at = now() WHERE dcat_uri = :u"),
                    {"d": json.dumps(dists, ensure_ascii=False), "u": r.dcat_uri})
        print(f"  translated {len(TIPS)} tooltip(s) into {len(LANGS)} languages")
        if untranslated:
            print(f"  [FAIL] no translation for: {untranslated}")
            return 1

        print("\n=== the API card: v1 -> v2 ===")
        v1row = db.execute(text(
            "SELECT title, title_i18n, description FROM brubru_dataset_catalog "
            "WHERE dcat_uri = :u"), {"u": V1}).fetchone()
        if v1row:
            print(f"  was: {v1row.title}")
            print(f"  now: {API_TITLE['en']}")
            if args.apply:
                db.execute(text(
                    "UPDATE brubru_dataset_catalog SET dcat_uri = :new, title = :t, "
                    "title_i18n = CAST(:ti AS jsonb), description = CAST(:d AS jsonb), "
                    "updated_at = now() WHERE dcat_uri = :old"),
                    {"new": V2, "t": API_TITLE["en"],
                     "ti": json.dumps(API_TITLE, ensure_ascii=False),
                     "d": json.dumps(API_DESC, ensure_ascii=False), "old": V1})
        else:
            print("  already migrated")

        if not args.apply:
            print("\n[DRY-RUN] nothing written")
            return 0
        db.commit()

        print("\n=== verification ===")
        rows = db.execute(text(
            "SELECT dcat_uri, title_i18n, description, distribution "
            "FROM brubru_dataset_catalog")).fetchall()
        missing = []
        total = 0
        for r in rows:
            for d in (r.distribution or []):
                total += 1
                t = d.get("title_i18n") or {}
                if sorted(t.keys()) != sorted(LANGS):
                    missing.append(d.get("access_url"))
        print(f"  distributions with all six tooltips: {total - len(missing)}/{total} "
              f"{'OK' if not missing else 'FAIL ' + str(missing[:3])}")
        if missing:
            rc = 1
        v2 = db.execute(text("SELECT title_i18n->>'ca' AS ca, description->>'ca' AS d "
                             "FROM brubru_dataset_catalog WHERE dcat_uri = :u"),
                        {"u": V2}).fetchone()
        ok = bool(v2) and "v2" in (v2.ca or "")
        print(f"  the API card names v2: {'OK' if ok else 'FAIL'}  {v2.ca if v2 else '-'}")
        if not ok:
            rc = 1
        gone = db.execute(text("SELECT count(*) FROM brubru_dataset_catalog "
                               "WHERE dcat_uri = :u"), {"u": V1}).scalar()
        print(f"  the old v1 entry is gone: {'OK' if not gone else 'FAIL'}")
        if gone:
            rc = 1
        n994 = "994" in (v2.d or "") if v2 else False
        print(f"  it cites the measured 994 endpoints: {'OK' if n994 else 'FAIL'}")
        if not n994:
            rc = 1
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
