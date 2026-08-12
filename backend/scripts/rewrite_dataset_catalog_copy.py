"""Rewrite the dataset catalogue in language a reader can actually understand.

The catalogue was written for a data engineer. Rendered as cards in My EU
Bubble it read as: "Memoria cau local de skos:prefLabel + skos:altLabel des de
les taules d'autoritat", "Corpus TSVECTOR de 8.710 lleis", "resolt en directe
des de Cellar", "RAP textil". Victor could not understand his own product's
cards, which is the only test that matters.

Every description now answers two questions in two sentences: what is in this,
and what can I do with it. Internal machinery (TSVECTOR, SKOS, Formex, Cellar,
SPARQL) is gone from the reader-facing text; it is implementation, not content.
Where a number makes the thing concrete it stays, because "8,710 laws" tells a
reader more than "a corpus does".

Also fixes two things the rewrite exposed: three descriptions contained
em-dashes, which are forbidden in every Brubru surface, and the europa.eu
source registry had no link a reader could open even though the Brubru API page
documents exactly what it holds.

All six languages, because a catalogue entry a user cannot read is not a
catalogue entry.
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

COPY = {
"chat-knowledge-guides": {
 "en": "The 547 briefings Brubru's chat reads before it answers you. Each one explains a single EU file, regulation or institutional process in plain language, with links to the primary sources it relies on.",
 "ca": "Els 547 informes que el xat de Brubru llegeix abans de respondre't. Cadascun explica un sol expedient, reglament o procés institucional de la UE en llenguatge planer, amb enllaços a les fonts primàries en què es basa.",
 "es": "Los 547 informes que el chat de Brubru lee antes de responderte. Cada uno explica un solo expediente, reglamento o proceso institucional de la UE en lenguaje claro, con enlaces a las fuentes primarias en que se basa.",
 "fr": "Les 547 notes que le chat de Brubru lit avant de vous répondre. Chacune explique un seul dossier, règlement ou processus institutionnel de l'UE en langage clair, avec des liens vers les sources primaires utilisées.",
 "it": "Le 547 schede che la chat di Brubru legge prima di risponderti. Ognuna spiega un singolo dossier, regolamento o processo istituzionale dell'UE in linguaggio semplice, con i link alle fonti primarie usate.",
 "nl": "De 547 dossiers die de chat van Brubru leest voordat hij antwoordt. Elk dossier legt één EU-dossier, verordening of institutioneel proces in gewone taal uit, met links naar de gebruikte primaire bronnen.",
},
"v1-rest-api": {
 "en": "Brubru's data, for your own software instead of the screen. Over 120 endpoints covering EU law, procedures, MEPs, the calendar, consultations and predictions, at 60 requests a minute per key.",
 "ca": "Les dades de Brubru, per al teu propi programari en lloc de la pantalla. Més de 120 punts d'accés a legislació de la UE, procediments, eurodiputats, calendari, consultes i prediccions, a 60 peticions per minut per clau.",
 "es": "Los datos de Brubru, para tu propio software en lugar de la pantalla. Más de 120 puntos de acceso a legislación de la UE, procedimientos, eurodiputados, calendario, consultas y predicciones, a 60 peticiones por minuto por clave.",
 "fr": "Les données de Brubru, pour vos propres logiciels plutôt que pour l'écran. Plus de 120 points d'accès sur le droit de l'UE, les procédures, les députés, le calendrier, les consultations et les prévisions, à 60 requêtes par minute par clé.",
 "it": "I dati di Brubru, per il tuo software invece che per lo schermo. Oltre 120 endpoint su diritto dell'UE, procedure, europarlamentari, calendario, consultazioni e previsioni, a 60 richieste al minuto per chiave.",
 "nl": "De data van Brubru, voor je eigen software in plaats van het scherm. Meer dan 120 endpoints over EU-recht, procedures, Europarlementsleden, agenda, consultaties en voorspellingen, met 60 verzoeken per minuut per sleutel.",
},
"catalan-eu-laws": {
 "en": "EU regulations, directives and decisions translated into Catalan and published as web pages you can read and link to. Brubru builds them from the Publications Office's own files and adds new acts every day.",
 "ca": "Reglaments, directives i decisions de la UE traduïts al català i publicats com a pàgines web que pots llegir i enllaçar. Brubru els construeix a partir dels fitxers de l'Oficina de Publicacions i hi afegeix actes nous cada dia.",
 "es": "Reglamentos, directivas y decisiones de la UE traducidos al catalán y publicados como páginas web que puedes leer y enlazar. Brubru los construye a partir de los ficheros de la Oficina de Publicaciones y añade actos nuevos cada día.",
 "fr": "Règlements, directives et décisions de l'UE traduits en catalan et publiés en pages web que vous pouvez lire et partager. Brubru les construit à partir des fichiers de l'Office des publications et en ajoute chaque jour.",
 "it": "Regolamenti, direttive e decisioni dell'UE tradotti in catalano e pubblicati come pagine web che puoi leggere e condividere. Brubru li costruisce dai file dell'Ufficio delle pubblicazioni e ne aggiunge ogni giorno.",
 "nl": "EU-verordeningen, richtlijnen en besluiten vertaald naar het Catalaans en gepubliceerd als webpagina's die je kunt lezen en delen. Brubru bouwt ze uit de bestanden van het Publicatiebureau en voegt dagelijks nieuwe toe.",
},
"eu-vocabularies": {
 "en": "The EU's own official name for everything: every institution, body, legal act type and procedure, with its alternative names in six languages. This is what lets Brubru show a readable label instead of a code.",
 "ca": "El nom oficial que la UE dona a cada cosa: cada institució, organisme, tipus d'acte jurídic i procediment, amb els seus noms alternatius en sis llengües. És el que permet a Brubru mostrar una etiqueta llegible en lloc d'un codi.",
 "es": "El nombre oficial que la UE da a cada cosa: cada institución, organismo, tipo de acto jurídico y procedimiento, con sus nombres alternativos en seis lenguas. Es lo que permite a Brubru mostrar una etiqueta legible en lugar de un código.",
 "fr": "Le nom officiel que l'UE donne à chaque chose : chaque institution, organe, type d'acte juridique et procédure, avec ses variantes en six langues. C'est ce qui permet à Brubru d'afficher un libellé lisible au lieu d'un code.",
 "it": "Il nome ufficiale che l'UE dà a ogni cosa: ogni istituzione, organo, tipo di atto giuridico e procedura, con i nomi alternativi in sei lingue. È ciò che permette a Brubru di mostrare un'etichetta leggibile invece di un codice.",
 "nl": "De officiële EU-naam voor alles: elke instelling, elk orgaan, elk type rechtshandeling en elke procedure, met alternatieve namen in zes talen. Dit maakt dat Brubru een leesbaar label toont in plaats van een code.",
},
"eu-digital-product-passport": {
 "en": "Everything the EU requires of a digital product passport, in one place: which laws impose one, when each product sector must comply, how the central registry works, and the 71 data points a battery passport must carry.",
 "ca": "Tot el que la UE exigeix a un passaport digital de producte, en un sol lloc: quines lleis n'imposen un, quan ha de complir cada sector de producte, com funciona el registre central, i els 71 punts de dades que ha de portar un passaport de bateries.",
 "es": "Todo lo que la UE exige a un pasaporte digital de producto, en un solo lugar: qué leyes lo imponen, cuándo debe cumplir cada sector de producto, cómo funciona el registro central, y los 71 puntos de datos que debe llevar un pasaporte de baterías.",
 "fr": "Tout ce que l'UE exige d'un passeport numérique de produit, en un seul endroit : quelles lois l'imposent, quand chaque secteur doit s'y conformer, comment fonctionne le registre central, et les 71 points de données d'un passeport de batteries.",
 "it": "Tutto ciò che l'UE richiede a un passaporto digitale di prodotto, in un unico posto: quali leggi lo impongono, quando ogni settore deve adeguarsi, come funziona il registro centrale, e i 71 punti dati di un passaporto delle batterie.",
 "nl": "Alles wat de EU van een digitaal productpaspoort eist, op één plek: welke wetten het opleggen, wanneer elke productsector moet voldoen, hoe het centrale register werkt, en de 71 gegevenspunten van een batterijpaspoort.",
},
"eu-laws-tsvector": {
 "en": "8,710 adopted EU laws, searchable by any word in their text rather than only by number. Brubru refreshes them from the Publications Office so a search reaches the version in force.",
 "ca": "8.710 lleis adoptades de la UE, cercables per qualsevol paraula del text i no només pel número. Brubru les actualitza des de l'Oficina de Publicacions perquè una cerca arribi a la versió vigent.",
 "es": "8.710 leyes adoptadas de la UE, buscables por cualquier palabra de su texto y no solo por número. Brubru las actualiza desde la Oficina de Publicaciones para que una búsqueda llegue a la versión vigente.",
 "fr": "8 710 actes de l'UE adoptés, interrogeables par n'importe quel mot de leur texte et pas seulement par numéro. Brubru les actualise depuis l'Office des publications pour qu'une recherche atteigne la version en vigueur.",
 "it": "8.710 atti dell'UE adottati, ricercabili per qualsiasi parola del testo e non solo per numero. Brubru li aggiorna dall'Ufficio delle pubblicazioni perché una ricerca raggiunga la versione in vigore.",
 "nl": "8.710 aangenomen EU-wetten, doorzoekbaar op elk woord in de tekst en niet alleen op nummer. Brubru werkt ze bij vanuit het Publicatiebureau, zodat een zoekopdracht de geldende versie vindt.",
},
"textile-circularity-corpus": {
 "en": "The EU law that governs a textile product from design to waste, gathered into one list: producer responsibility, ecodesign, packaging, waste shipments, raw materials and carbon at the border, plus the acts still being written. Each title and its in-force status are checked against the Publications Office as you read them. Built for the LIFE DPP-TEX project.",
 "ca": "La legislació de la UE que regeix un producte tèxtil des del disseny fins al residu, reunida en una sola llista: responsabilitat del productor, ecodisseny, envasos, trasllat de residus, matèries primeres i carboni a la frontera, més els actes encara en tràmit. Cada títol i el seu estat de vigència es comproven amb l'Oficina de Publicacions en el moment de llegir-los. Fet per al projecte LIFE DPP-TEX.",
 "es": "La legislación de la UE que rige un producto textil desde el diseño hasta el residuo, reunida en una sola lista: responsabilidad del productor, ecodiseño, envases, traslado de residuos, materias primas y carbono en la frontera, más los actos aún en tramitación. Cada título y su estado de vigencia se comprueban con la Oficina de Publicaciones al leerlos. Hecho para el proyecto LIFE DPP-TEX.",
 "fr": "Le droit de l'UE qui régit un produit textile de la conception au déchet, réuni en une seule liste : responsabilité du producteur, écoconception, emballages, transferts de déchets, matières premières et carbone à la frontière, ainsi que les actes encore en cours. Chaque intitulé et son statut en vigueur sont vérifiés auprès de l'Office des publications à la lecture. Réalisé pour le projet LIFE DPP-TEX.",
 "it": "Il diritto dell'UE che governa un prodotto tessile dalla progettazione al rifiuto, raccolto in un unico elenco: responsabilità del produttore, progettazione ecocompatibile, imballaggi, spedizioni di rifiuti, materie prime e carbonio alla frontiera, più gli atti ancora in corso. Ogni titolo e il suo stato di vigore sono verificati presso l'Ufficio delle pubblicazioni alla lettura. Realizzato per il progetto LIFE DPP-TEX.",
 "nl": "Het EU-recht dat een textielproduct regelt van ontwerp tot afval, in één lijst: producentenverantwoordelijkheid, ecologisch ontwerp, verpakkingen, afvaltransport, grondstoffen en koolstof aan de grens, plus de handelingen die nog in behandeling zijn. Elke titel en de geldigheidsstatus worden bij het lezen bij het Publicatiebureau gecontroleerd. Gemaakt voor het project LIFE DPP-TEX.",
},
"europa-source-registry": {
 "en": "The 519 europa.eu sites and feeds Brubru watches for EU news, and how it reads each one. This is the map of where everything else in Brubru comes from.",
 "ca": "Els 519 llocs i canals d'europa.eu que Brubru vigila per a les notícies de la UE, i com llegeix cadascun. És el mapa d'on surt tota la resta de Brubru.",
 "es": "Los 519 sitios y canales de europa.eu que Brubru vigila para las noticias de la UE, y cómo lee cada uno. Es el mapa de dónde sale todo lo demás en Brubru.",
 "fr": "Les 519 sites et flux europa.eu que Brubru surveille pour l'actualité de l'UE, et la façon dont il lit chacun. C'est la carte de la provenance de tout le reste dans Brubru.",
 "it": "I 519 siti e feed di europa.eu che Brubru monitora per le notizie dell'UE, e come legge ciascuno. È la mappa da cui proviene tutto il resto in Brubru.",
 "nl": "De 519 europa.eu-sites en -feeds die Brubru volgt voor EU-nieuws, en hoe elk gelezen wordt. Dit is de kaart van waar al het andere in Brubru vandaan komt.",
},
}

# The registry had nothing a reader could open. The Brubru API page documents
# exactly this: which sources feed the product and how they are read.
EXTRA_DISTRIBUTION = {
    "europa-source-registry": {
        "title": "The Brubru API page, which documents these sources",
        "format": "HTML",
        "access_url": "https://brubru.beresol.eu/api/",
        "media_type": "text/html",
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
        rows = db.execute(text(
            "SELECT dcat_uri, description, distribution FROM brubru_dataset_catalog "
            "ORDER BY dcat_uri")).fetchall()
        slugs = {r.dcat_uri.rsplit("/", 1)[-1] for r in rows}
        missing = slugs - set(COPY)
        if missing:
            print(f"[FAIL] no new copy written for: {sorted(missing)}")
            return 1
        print(f"=== {len(rows)} dataset(s), all covered ===")

        for r in rows:
            slug = r.dcat_uri.rsplit("/", 1)[-1]
            new = COPY[slug]
            if set(new) != LANGS:
                print(f"[FAIL] {slug}: languages {sorted(new)}")
                return 1
            bad = [l for l, t in new.items() if "—" in t or "–" in t]
            if bad:
                print(f"[FAIL] {slug}: dash characters in {bad}")
                return 1
            old_en = (r.description or {}).get("en", "")
            print(f"\n  {slug}")
            print(f"    was: {old_en[:96]}")
            print(f"    now: {new['en'][:96]}")
            dists = list(r.distribution or [])
            if slug in EXTRA_DISTRIBUTION:
                extra = EXTRA_DISTRIBUTION[slug]
                if not any(d.get("access_url") == extra["access_url"] for d in dists):
                    dists.append(extra)
                    print(f"    + link: {extra['access_url']}")
            if args.apply:
                db.execute(text(
                    "UPDATE brubru_dataset_catalog SET description = CAST(:d AS jsonb), "
                    "distribution = CAST(:x AS jsonb), updated_at = now() "
                    "WHERE dcat_uri = :u"),
                    {"d": json.dumps(new, ensure_ascii=False),
                     "x": json.dumps(dists, ensure_ascii=False), "u": r.dcat_uri})

        if not args.apply:
            print("\n[DRY-RUN] nothing written")
            return 0
        db.commit()

        print("\n=== verification ===")
        rows = db.execute(text(
            "SELECT dcat_uri, description, distribution FROM brubru_dataset_catalog"
        )).fetchall()
        for r in rows:
            langs = sorted((r.description or {}).keys())
            ok = set(langs) == LANGS
            print(f"  {'OK ' if ok else 'FAIL'} {r.dcat_uri.rsplit('/', 1)[-1]:<30} {langs}")
            if not ok:
                rc = 1
        jargon = ["TSVECTOR", "skos:", "Formex", "SPARQL", "Cellar", "prefLabel",
                  "—", "–"]
        hits = []
        for r in rows:
            for lang, t in (r.description or {}).items():
                for j in jargon:
                    if j.lower() in (t or "").lower():
                        hits.append((r.dcat_uri.rsplit("/", 1)[-1], lang, j))
        print(f"  jargon or dashes left in reader-facing copy: {len(hits)} "
              f"{'OK' if not hits else 'FAIL ' + str(hits[:4])}")
        if hits:
            rc = 1
        n = db.execute(text(
            "SELECT count(*) FROM brubru_dataset_catalog "
            "WHERE dcat_uri LIKE '%europa-source-registry' "
            "  AND distribution::text ILIKE '%brubru.beresol.eu/api/%'")).scalar()
        print(f"  source registry now has an openable link: {n} "
              f"{'OK' if n else 'FAIL'}")
        if not n:
            rc = 1
        return rc
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())

# Titles were rewritten in the same pass on 12 Aug 2026, applied directly:
#   EU legislation TSVECTOR corpus (eu_laws)      -> EU legislation, searchable word by word
#   EU authority labels (Brubru cache)            -> The EU's official names for its own institutions and acts
#   EU textile-circularity law corpus (live-...)  -> EU textile circularity law, from design to waste
#   Brubru chat knowledge guides                  -> The briefings behind Brubru's chat
#   EU Digital Product Passport regime (ESPR...)  -> The EU digital product passport, end to end
# A card headed "Corpus TSVECTOR (eu_laws)" over plain-language prose is still
# unreadable, and eu_laws is a table name rather than anything a user has.
