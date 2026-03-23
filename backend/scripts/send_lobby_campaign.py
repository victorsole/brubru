"""
Tailored Multilingual Email Campaign for EU Transparency Register Organizations

Classifies orgs by policy area, prioritises 6 countries, sends tailored emails
in the recipient's language (Spanish, Italian, French, Dutch, English).

Usage:
    # Classify orgs and preview distribution
    python3.12 scripts/send_lobby_campaign.py --classify-only

    # Classify with country filter
    python3.12 scripts/send_lobby_campaign.py --classify-only --country spain

    # Test templates in a specific language
    python3.12 scripts/send_lobby_campaign.py --test-templates --lang es

    # Dry run for specific countries
    python3.12 scripts/send_lobby_campaign.py --dry-run --country spain,italy

    # Send for real (Phase 5 - use only when ready)
    python3.12 scripts/send_lobby_campaign.py --send --country spain --cluster climate
"""

import csv
import logging
import os
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "emails"
EMAILS_CSV = DATA_DIR / "lobby_orgs_emails.csv"


# ---------------------------------------------------------------------------
# Country & Language Configuration
# ---------------------------------------------------------------------------

PRIORITY_COUNTRIES = {"SPAIN", "ITALY", "BELGIUM", "NETHERLANDS", "LUXEMBOURG", "FRANCE"}

COUNTRY_LANGUAGE_MAP = {
    "SPAIN": "es",
    "ITALY": "it",
    "FRANCE": "fr",
    "BELGIUM": "fr",
    "NETHERLANDS": "nl",
    "LUXEMBOURG": "fr",
}


# ---------------------------------------------------------------------------
# Policy Area Clusters (with multilingual keywords)
# ---------------------------------------------------------------------------

CLUSTERS = {
    "digital": {
        "name": "Digital & AI",
        "keywords": [
            # English
            "artificial intelligence", "ai act", "digital services", "digital markets",
            "dsa", "dma", "digital", "cyber", "data protection", "gdpr", "e-privacy",
            "platform regulation", "online", "algorithm", "machine learning",
            "data governance", "data act", "interoperability", "eidas",
            # French
            "numerique", "intelligence artificielle", "protection des donnees",
            "services numeriques", "marches numeriques", "cybersecurite",
            # Spanish
            "digitalizacion", "inteligencia artificial", "proteccion de datos",
            "servicios digitales", "mercados digitales", "ciberseguridad",
            # Italian
            "digitale", "intelligenza artificiale", "protezione dei dati",
            "servizi digitali", "mercati digitali", "sicurezza informatica",
            # Dutch
            "digitaal", "kunstmatige intelligentie", "gegevensbescherming",
            "digitale diensten", "digitale markten", "cyberveiligheid",
            # German
            "digitalisierung", "kuenstliche intelligenz", "datenschutz",
            "digitale dienste", "digitale maerkte",
        ],
        "files": ["AI Act", "Digital Services Act", "Digital Markets Act", "Data Act", "Cyber Resilience Act"],
        "committee": "IMCO/LIBE",
    },
    "climate": {
        "name": "Climate & Environment",
        "keywords": [
            # English
            "green deal", "cbam", "ets", "emissions trading", "fit for 55",
            "biodiversity", "pollution", "climate", "environment", "carbon",
            "deforestation", "circular economy", "waste", "nature restoration",
            "sustainability", "net zero", "renewable", "packaging",
            # French
            "changement climatique", "developpement durable", "environnement",
            "economie circulaire", "biodiversite", "pacte vert", "durable",
            # Spanish
            "cambio climatico", "sostenibilidad", "medio ambiente",
            "economia circular", "biodiversidad", "pacto verde",
            # Italian
            "cambiamento climatico", "sostenibilita", "ambiente",
            "economia circolare", "biodiversita", "patto verde",
            # Dutch
            "klimaat", "klimaatverandering", "duurzaam", "duurzaamheid", "milieu",
            "circulaire economie", "biodiversiteit",
            # German
            "klimawandel", "nachhaltigkeit", "umwelt", "kreislaufwirtschaft",
            "biodiversitaet", "gruener deal",
        ],
        "files": ["European Green Deal", "CBAM", "ETS Reform", "Nature Restoration Law"],
        "committee": "ENVI",
    },
    "finance": {
        "name": "Finance & Banking",
        "keywords": [
            # English
            "psd3", "mica", "aml", "anti-money laundering", "basel",
            "capital markets", "banking", "financial", "fintech", "payment",
            "insurance", "solvency", "securities", "investment", "prudential",
            "money laundering", "crypto", "stablecoin",
            # French
            "financier", "bancaire", "marche des capitaux", "blanchiment",
            "assurance", "investissement",
            # Spanish
            "financiero", "bancario", "mercado de capitales", "blanqueo",
            "seguro", "inversion",
            # Italian
            "finanziario", "bancario", "mercato dei capitali", "riciclaggio",
            "assicurazione", "investimento",
            # Dutch
            "financieel", "bancair", "kapitaalmarkten", "witwassen",
            "verzekering", "investering",
            # German
            "finanziell", "bankwesen", "kapitalmarkt", "geldwaesche",
            "versicherung",
        ],
        "files": ["PSD3", "MiCA", "AML Package", "Capital Markets Union"],
        "committee": "ECON",
    },
    "trade": {
        "name": "Trade, Industry & Consumer",
        "keywords": [
            # English - trade
            "trade agreement", "mercosur", "customs", "wto", "tariff",
            "trade policy", "fta", "export", "import", "trade defence",
            "supply chain", "due diligence", "csddd", "single market",
            # English - consumer (merged)
            "consumer", "product safety", "e-commerce", "market surveillance",
            "standardisation", "ce marking", "unfair practices", "advertising",
            # French
            "commerce", "marche interieur", "concurrence", "douane",
            "consommateur", "securite des produits",
            # Spanish
            "comercio", "mercado interior", "competencia", "aduana",
            "consumidor", "seguridad de productos",
            # Italian
            "commercio", "mercato interno", "concorrenza", "dogana",
            "consumatore", "sicurezza dei prodotti",
            # Dutch
            "handel", "interne markt", "mededinging", "douane",
            "consument", "productveiligheid",
            # German
            "handel", "binnenmarkt", "wettbewerb", "zoll",
            "verbraucher", "produktsicherheit",
        ],
        "files": ["EU-Mercosur Agreement", "Corporate Sustainability Due Diligence", "General Product Safety Regulation"],
        "committee": "INTA/IMCO",
    },
    "agriculture": {
        "name": "Agriculture & Food",
        "keywords": [
            # English
            "cap", "common agricultural", "farm to fork", "food safety",
            "agricultural", "pesticide", "fertiliser", "organic", "animal welfare",
            "fisheries", "aquaculture", "rural development", "gmo", "novel food",
            # French
            "agriculture", "alimentaire", "agroalimentaire", "peche",
            "pac", "pesticide", "bien-etre animal",
            # Spanish
            "agricultura", "alimentario", "agroalimentario", "pesca",
            "pac", "plaguicida", "bienestar animal",
            # Italian
            "agricoltura", "alimentare", "agroalimentare", "pesca",
            "pac", "pesticidi", "benessere animale",
            # Dutch
            "landbouw", "voedsel", "voedingsmiddelen", "visserij",
            "glb", "pesticiden", "dierenwelzijn",
            # German
            "landwirtschaft", "lebensmittel", "ernaehrung", "fischerei",
            "gap", "pflanzenschutz", "tierwohl",
        ],
        "files": ["CAP Reform", "Farm to Fork Strategy", "Sustainable Food Systems"],
        "committee": "AGRI",
    },
    "health": {
        "name": "Health & Pharma",
        "keywords": [
            # English
            "pharmaceutical", "health", "ehds", "medical", "ema",
            "clinical trial", "medicine", "vaccine", "disease", "drug",
            "patient", "healthcare", "biotech", "therapeutic", "diagnostic",
            "tobacco", "alcohol",
            # French
            "sante", "medicament", "pharmaceutique", "essai clinique",
            "patient", "soins de sante",
            # Spanish
            "salud", "medicamento", "farmaceutico", "ensayo clinico",
            "paciente", "sanidad", "sanitario",
            # Italian
            "salute", "farmaceutico", "medicinale", "sperimentazione clinica",
            "paziente", "sanitario",
            # Dutch
            "gezondheid", "geneesmiddel", "farmaceutisch", "klinische proef",
            "patient", "gezondheidszorg",
            # German
            "gesundheit", "medizin", "pharma", "arzneimittel",
            "klinische studie", "gesundheitswesen",
        ],
        "files": ["Pharmaceutical Legislation", "EHDS", "EU Health Union"],
        "committee": "ENVI/SANT",
    },
    "energy": {
        "name": "Energy",
        "keywords": [
            # English
            "renewable", "hydrogen", "repowereu", "energy", "nuclear",
            "grid", "solar", "wind", "gas", "electricity", "battery",
            "energy efficiency", "energy union", "interconnection",
            # French
            "energetique", "energie", "hydrogene", "renouvelable",
            "nucleaire", "solaire", "eolien", "electricite",
            # Spanish
            "energia", "renovable", "hidrogeno", "nuclear",
            "solar", "eolico", "electricidad",
            # Italian
            "energia", "rinnovabile", "idrogeno", "nucleare",
            "solare", "eolico", "elettricita",
            # Dutch
            "energie", "hernieuwbaar", "waterstof", "nucleair",
            "zonne-energie", "windenergie", "elektriciteit",
            # German
            "energie", "energiewende", "wasserstoff", "erneuerbar",
            "strom", "kernenergie",
        ],
        "files": ["REPowerEU", "Renewable Energy Directive", "Energy Efficiency Directive"],
        "committee": "ITRE",
    },
    "transport": {
        "name": "Transport & Mobility",
        "keywords": [
            # English
            "emission standard", "aviation", "rail", "transport", "maritime",
            "road", "mobility", "vehicle", "electric vehicle", "shipping",
            "logistics", "infrastructure", "ten-t", "clean vehicle",
            # French
            "transport", "mobilite", "ferroviaire", "aerien", "maritime",
            "vehicule electrique", "logistique",
            # Spanish
            "transporte", "movilidad", "ferroviario", "aviacion", "maritimo",
            "vehiculo electrico", "logistica",
            # Italian
            "trasporto", "mobilita", "ferroviario", "aviazione", "marittimo",
            "veicolo elettrico", "logistica",
            # Dutch
            "vervoer", "mobiliteit", "spoorweg", "luchtvaart", "maritiem",
            "elektrisch voertuig", "logistiek",
            # German
            "verkehr", "mobilitaet", "schiene", "luftfahrt", "seefahrt",
            "elektrofahrzeug", "logistik",
        ],
        "files": ["Fit for 55 Transport Package", "Alternative Fuels Infrastructure"],
        "committee": "TRAN",
    },
    "defence": {
        "name": "Defence & Security",
        "keywords": [
            # English
            "edip", "defence", "security", "csdp", "nato", "military",
            "arms", "dual-use", "space", "satellite", "border",
            "frontex", "migration", "asylum",
            # French
            "defense", "securite", "militaire", "armement", "spatial",
            "migration", "asile", "frontiere",
            # Spanish
            "defensa", "seguridad", "militar", "armamento", "espacial",
            "migracion", "asilo", "frontera",
            # Italian
            "difesa", "sicurezza", "militare", "armamento", "spaziale",
            "migrazione", "asilo", "frontiera",
            # Dutch
            "defensie", "veiligheid", "militair", "bewapening", "ruimtevaart",
            "migratie", "asiel", "grens",
            # German
            "verteidigung", "sicherheit", "militaer", "ruestung",
            "migration", "asyl", "grenze",
        ],
        "files": ["EDIP", "EU Defence Industrial Strategy"],
        "committee": "AFET/SEDE",
    },
    "social": {
        "name": "Social & Employment",
        "keywords": [
            # English
            "social", "employment", "equality", "empl", "pension",
            "labour", "worker", "minimum wage", "platform work",
            "gender", "disability", "inclusion", "education", "skill",
            # French
            "emploi", "travail", "social", "egalite", "retraite",
            "salaire minimum", "handicap", "formation",
            # Spanish
            "empleo", "trabajo", "social", "igualdad", "pension",
            "salario minimo", "discapacidad", "formacion",
            # Italian
            "occupazione", "lavoro", "sociale", "uguaglianza", "pensione",
            "salario minimo", "disabilita", "formazione",
            # Dutch
            "werkgelegenheid", "arbeid", "sociaal", "gelijkheid", "pensioen",
            "minimumloon", "handicap", "opleiding",
            # German
            "beschaeftigung", "arbeit", "sozial", "gleichstellung", "rente",
            "mindestlohn", "behinderung", "bildung",
        ],
        "files": ["Platform Workers Directive", "Pay Transparency Directive"],
        "committee": "EMPL",
    },
    "research": {
        "name": "Research & Innovation",
        "keywords": [
            # English
            "horizon", "r&d", "innovation", "quantum", "semiconductor",
            "chips act", "research", "startup", "sme", "intellectual property",
            "patent", "technology", "deep tech",
            # French
            "recherche", "innovation", "brevet", "technologie", "scientifique",
            "propriete intellectuelle",
            # Spanish
            "investigacion", "innovacion", "patente", "tecnologia", "cientifico",
            "propiedad intelectual",
            # Italian
            "ricerca", "innovazione", "brevetto", "tecnologia", "scientifico",
            "proprieta intellettuale",
            # Dutch
            "onderzoek", "innovatie", "octrooi", "technologie", "wetenschappelijk",
            "intellectueel eigendom",
            # German
            "forschung", "wissenschaft", "patent", "technologie",
            "geistiges eigentum",
        ],
        "files": ["Horizon Europe", "European Chips Act"],
        "committee": "ITRE",
    },
    "civil_society": {
        "name": "Civil Society & Human Rights",
        "keywords": [
            # English
            "human rights", "civil liberties", "democracy", "transparency",
            "rule of law", "freedom", "ngo", "civil society", "media freedom",
            "whistleblower", "anti-corruption", "fundamental rights",
            # French
            "droits de l'homme", "libertes civiles", "democratie", "transparence",
            "etat de droit", "societe civile", "liberte des medias",
            # Spanish
            "derechos humanos", "libertades civiles", "democracia", "transparencia",
            "estado de derecho", "sociedad civil", "libertad de prensa",
            # Italian
            "diritti umani", "liberta civili", "democrazia", "trasparenza",
            "stato di diritto", "societa civile", "liberta dei media",
            # Dutch
            "mensenrechten", "burgerlijke vrijheden", "democratie", "transparantie",
            "rechtsstaat", "maatschappelijk middenveld", "persvrijheid",
            # German
            "menschenrechte", "buergerliche freiheiten", "demokratie", "transparenz",
            "rechtsstaatlichkeit", "zivilgesellschaft", "pressefreiheit",
        ],
        "files": ["EU Rule of Law Framework", "Media Freedom Act"],
        "committee": "LIBE",
    },
}

# Fallback: map main_category to cluster for orgs with no keyword matches
CATEGORY_FALLBACK = {
    "Academic institutions": "research",
    "Think tanks and research institutions": "research",
    "Law firms": "civil_society",
}


# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------

TRANSLATIONS = {
    "en": {
        "subject_cluster": "Brubru - AI tools for {name} policy professionals",
        "subject_generic": "Brubru - AI-powered EU policy assistant for advocacy professionals",
        "header_subtitle": "AI-powered EU policy tools",
        "greeting": "Dear Colleague,",
        "intro_cluster": (
            "If your organisation works on <strong>{name}</strong> policy in the EU, "
            "you may find <strong>Brubru</strong> useful. It is a free AI assistant "
            "designed specifically for EU policy professionals, built by "
            "<strong>Beresol</strong>, a Brussels-based public affairs consultancy."
        ),
        "intro_generic": (
            "As an organisation active in EU affairs, you may find <strong>Brubru</strong> useful. "
            "It is a free AI assistant designed specifically for EU policy professionals, "
            "built by <strong>Beresol</strong>, a Brussels-based public affairs consultancy."
        ),
        "section_cluster": "How Brubru helps with {name}:",
        "section_generic": "What Brubru can do for you:",
        "feat_questions": "<strong>Ask policy questions</strong> &mdash; get instant answers on {topic} legislation, including {file}, with cited sources",
        "feat_questions_generic": "<strong>Answer EU policy questions</strong> &mdash; ask anything about regulations, directives, or institutional processes, with sources",
        "feat_amendments": "<strong>Draft amendments</strong> &mdash; use the Amendator to create professional legislative amendments to files like {file}",
        "feat_amendments_generic": "<strong>Draft amendments</strong> &mdash; use the Amendator to create professional legislative amendments with AI assistance",
        "feat_track": "<strong>Track {committee} work</strong> &mdash; monitor committee work in progress, RSS feeds from 15+ EU sources, and legislative developments",
        "feat_track_generic": "<strong>Track legislation</strong> &mdash; monitor committee work, RSS feeds from 15+ EU sources, and legislative developments",
        "feat_generate": "<strong>Generate documents</strong> &mdash; position papers, MEP briefings, and talking points on {topic} topics in seconds",
        "feat_generate_generic": "<strong>Generate documents</strong> &mdash; position papers, MEP briefings, and talking points in seconds",
        "key_files_heading": "Key EU files Brubru covers in {name}:",
        "cta_button": "Try Brubru for free",
        "free_notice": "Brubru is free to use. No credit card required.",
        "unsubscribe": "If you no longer wish to receive emails from us, simply reply to this message.",
    },
    "es": {
        "subject_cluster": "Brubru - Herramientas de IA para profesionales de {name}",
        "subject_generic": "Brubru - Asistente de IA para profesionales de asuntos europeos",
        "header_subtitle": "Herramientas de IA para politicas de la UE",
        "greeting": "Estimado/a colega,",
        "intro_cluster": (
            "Si su organizacion trabaja en politicas de <strong>{name}</strong> en la UE, "
            "<strong>Brubru</strong> puede resultarle util. Es un asistente de IA gratuito "
            "disenado especificamente para profesionales de politicas europeas, desarrollado por "
            "<strong>Beresol</strong>, una consultora de asuntos publicos con sede en Bruselas."
        ),
        "intro_generic": (
            "Como organizacion activa en asuntos europeos, <strong>Brubru</strong> puede resultarle util. "
            "Es un asistente de IA gratuito disenado especificamente para profesionales de politicas europeas, "
            "desarrollado por <strong>Beresol</strong>, una consultora de asuntos publicos con sede en Bruselas."
        ),
        "section_cluster": "Como Brubru le ayuda con {name}:",
        "section_generic": "Que puede hacer Brubru por usted:",
        "feat_questions": "<strong>Haga preguntas sobre politicas</strong> &mdash; obtenga respuestas instantaneas sobre legislacion de {topic}, incluida {file}, con fuentes citadas",
        "feat_questions_generic": "<strong>Responda preguntas sobre politicas de la UE</strong> &mdash; pregunte sobre reglamentos, directivas o procesos institucionales, con fuentes",
        "feat_amendments": "<strong>Redacte enmiendas</strong> &mdash; utilice el Amendator para crear enmiendas legislativas profesionales a expedientes como {file}",
        "feat_amendments_generic": "<strong>Redacte enmiendas</strong> &mdash; utilice el Amendator para crear enmiendas legislativas profesionales con asistencia de IA",
        "feat_track": "<strong>Siga el trabajo de {committee}</strong> &mdash; supervise el trabajo en curso de las comisiones, feeds RSS de mas de 15 fuentes de la UE y novedades legislativas",
        "feat_track_generic": "<strong>Siga la legislacion</strong> &mdash; supervise el trabajo de las comisiones, feeds RSS de mas de 15 fuentes de la UE y novedades legislativas",
        "feat_generate": "<strong>Genere documentos</strong> &mdash; position papers, briefings para eurodiputados y puntos de discusion sobre {topic} en segundos",
        "feat_generate_generic": "<strong>Genere documentos</strong> &mdash; position papers, briefings para eurodiputados y puntos de discusion en segundos",
        "key_files_heading": "Expedientes clave de la UE que Brubru cubre en {name}:",
        "cta_button": "Pruebe Brubru gratis",
        "free_notice": "Brubru es gratuito. No se requiere tarjeta de credito.",
        "unsubscribe": "Si ya no desea recibir correos electronicos nuestros, simplemente responda a este mensaje.",
    },
    "fr": {
        "subject_cluster": "Brubru - Outils IA pour les professionnels de {name}",
        "subject_generic": "Brubru - Assistant IA pour les professionnels des affaires europeennes",
        "header_subtitle": "Outils IA pour les politiques de l'UE",
        "greeting": "Cher/Chere collegue,",
        "intro_cluster": (
            "Si votre organisation travaille sur les politiques de <strong>{name}</strong> dans l'UE, "
            "<strong>Brubru</strong> pourrait vous etre utile. C'est un assistant IA gratuit "
            "concu specialement pour les professionnels des politiques europeennes, developpe par "
            "<strong>Beresol</strong>, un cabinet de conseil en affaires publiques base a Bruxelles."
        ),
        "intro_generic": (
            "En tant qu'organisation active dans les affaires europeennes, <strong>Brubru</strong> pourrait vous etre utile. "
            "C'est un assistant IA gratuit concu specialement pour les professionnels des politiques europeennes, "
            "developpe par <strong>Beresol</strong>, un cabinet de conseil en affaires publiques base a Bruxelles."
        ),
        "section_cluster": "Comment Brubru vous aide avec {name} :",
        "section_generic": "Ce que Brubru peut faire pour vous :",
        "feat_questions": "<strong>Posez des questions politiques</strong> &mdash; obtenez des reponses instantanees sur la legislation {topic}, y compris {file}, avec des sources citees",
        "feat_questions_generic": "<strong>Repondez aux questions sur les politiques de l'UE</strong> &mdash; posez des questions sur les reglements, directives ou processus institutionnels, avec des sources",
        "feat_amendments": "<strong>Redigez des amendements</strong> &mdash; utilisez l'Amendator pour creer des amendements legislatifs professionnels a des dossiers comme {file}",
        "feat_amendments_generic": "<strong>Redigez des amendements</strong> &mdash; utilisez l'Amendator pour creer des amendements legislatifs professionnels avec l'assistance de l'IA",
        "feat_track": "<strong>Suivez les travaux de {committee}</strong> &mdash; surveillez les travaux en cours des commissions, les flux RSS de plus de 15 sources de l'UE et les developpements legislatifs",
        "feat_track_generic": "<strong>Suivez la legislation</strong> &mdash; surveillez les travaux des commissions, les flux RSS de plus de 15 sources de l'UE et les developpements legislatifs",
        "feat_generate": "<strong>Generez des documents</strong> &mdash; notes de position, briefings pour les eurodeputes et points de discussion sur {topic} en quelques secondes",
        "feat_generate_generic": "<strong>Generez des documents</strong> &mdash; notes de position, briefings pour les eurodeputes et points de discussion en quelques secondes",
        "key_files_heading": "Dossiers cles de l'UE couverts par Brubru dans {name} :",
        "cta_button": "Essayez Brubru gratuitement",
        "free_notice": "Brubru est gratuit. Aucune carte de credit requise.",
        "unsubscribe": "Si vous ne souhaitez plus recevoir d'e-mails de notre part, repondez simplement a ce message.",
    },
    "it": {
        "subject_cluster": "Brubru - Strumenti IA per i professionisti di {name}",
        "subject_generic": "Brubru - Assistente IA per i professionisti degli affari europei",
        "header_subtitle": "Strumenti IA per le politiche dell'UE",
        "greeting": "Gentile collega,",
        "intro_cluster": (
            "Se la vostra organizzazione lavora sulle politiche di <strong>{name}</strong> nell'UE, "
            "<strong>Brubru</strong> potrebbe esservi utile. E un assistente IA gratuito "
            "progettato specificamente per i professionisti delle politiche europee, sviluppato da "
            "<strong>Beresol</strong>, una societa di consulenza in affari pubblici con sede a Bruxelles."
        ),
        "intro_generic": (
            "Come organizzazione attiva negli affari europei, <strong>Brubru</strong> potrebbe esservi utile. "
            "E un assistente IA gratuito progettato specificamente per i professionisti delle politiche europee, "
            "sviluppato da <strong>Beresol</strong>, una societa di consulenza in affari pubblici con sede a Bruxelles."
        ),
        "section_cluster": "Come Brubru vi aiuta con {name}:",
        "section_generic": "Cosa puo fare Brubru per voi:",
        "feat_questions": "<strong>Fate domande sulle politiche</strong> &mdash; ottenete risposte immediate sulla legislazione di {topic}, compresa {file}, con fonti citate",
        "feat_questions_generic": "<strong>Rispondete a domande sulle politiche dell'UE</strong> &mdash; chiedete informazioni su regolamenti, direttive o processi istituzionali, con fonti",
        "feat_amendments": "<strong>Redigete emendamenti</strong> &mdash; utilizzate l'Amendator per creare emendamenti legislativi professionali a dossier come {file}",
        "feat_amendments_generic": "<strong>Redigete emendamenti</strong> &mdash; utilizzate l'Amendator per creare emendamenti legislativi professionali con l'assistenza dell'IA",
        "feat_track": "<strong>Seguite i lavori di {committee}</strong> &mdash; monitorate i lavori in corso delle commissioni, i feed RSS di oltre 15 fonti dell'UE e gli sviluppi legislativi",
        "feat_track_generic": "<strong>Seguite la legislazione</strong> &mdash; monitorate i lavori delle commissioni, i feed RSS di oltre 15 fonti dell'UE e gli sviluppi legislativi",
        "feat_generate": "<strong>Generate documenti</strong> &mdash; position paper, briefing per gli eurodeputati e punti di discussione su {topic} in pochi secondi",
        "feat_generate_generic": "<strong>Generate documenti</strong> &mdash; position paper, briefing per gli eurodeputati e punti di discussione in pochi secondi",
        "key_files_heading": "Dossier chiave dell'UE coperti da Brubru in {name}:",
        "cta_button": "Provate Brubru gratuitamente",
        "free_notice": "Brubru e gratuito. Nessuna carta di credito richiesta.",
        "unsubscribe": "Se non desiderate piu ricevere e-mail da noi, rispondete semplicemente a questo messaggio.",
    },
    "ca": {
        "subject_cluster": "Brubru: eines d'IA per a professionals de {name}",
        "subject_generic": "Brubru: assistent d'IA per a professionals d'afers europeus",
        "header_subtitle": "Eines d'IA per a polítiques de la UE",
        "greeting": "Benvolgut/da col·lega,",
        "intro_cluster": (
            "Si la vostra organització treballa en polítiques de <strong>{name}</strong> a la UE, "
            "<strong>Brubru</strong> us pot ser útil. És un assistent d'IA gratuït "
            "dissenyat específicament per a professionals de polítiques europees, desenvolupat per "
            "<strong>Beresol</strong>, una consultora d'afers públics amb seu a Brussel·les."
        ),
        "intro_generic": (
            "Com a organització activa en afers europeus, <strong>Brubru</strong> us pot ser útil. "
            "És un assistent d'IA gratuït dissenyat específicament per a professionals de polítiques europees, "
            "desenvolupat per <strong>Beresol</strong>, una consultora d'afers públics amb seu a Brussel·les."
        ),
        "section_cluster": "Com Brubru us ajuda amb {name}:",
        "section_generic": "Què pot fer Brubru per a vosaltres:",
        "feat_questions": "<strong>Feu preguntes sobre polítiques</strong> &mdash; obteniu respostes instantànies sobre legislació de {topic}, incloent-hi {file}, amb fonts citades",
        "feat_questions_generic": "<strong>Responeu preguntes sobre polítiques de la UE</strong> &mdash; pregunteu sobre reglaments, directives o processos institucionals, amb fonts",
        "feat_amendments": "<strong>Redacteu esmenes</strong> &mdash; utilitzeu l'Amendator per crear esmenes legislatives professionals a expedients com {file}",
        "feat_amendments_generic": "<strong>Redacteu esmenes</strong> &mdash; utilitzeu l'Amendator per crear esmenes legislatives professionals amb assistència d'IA",
        "feat_track": "<strong>Seguiu el treball de {committee}</strong> &mdash; superviseu el treball en curs de les comissions, feeds RSS de més de 15 fonts de la UE i novetats legislatives",
        "feat_track_generic": "<strong>Seguiu la legislació</strong> &mdash; superviseu el treball de les comissions, feeds RSS de més de 15 fonts de la UE i novetats legislatives",
        "feat_generate": "<strong>Genereu documents</strong> &mdash; position papers, briefings per a eurodiputats i punts de discussió sobre {topic} en segons",
        "feat_generate_generic": "<strong>Genereu documents</strong> &mdash; position papers, briefings per a eurodiputats i punts de discussió en segons",
        "key_files_heading": "Expedients clau de la UE que Brubru cobreix en {name}:",
        "cta_button": "Proveu Brubru gratis",
        "free_notice": "Brubru és gratuït. No cal targeta de crèdit.",
        "unsubscribe": "Si no voleu rebre més correus electrònics nostres, simplement responeu a aquest missatge.",
    },
    "nl": {
        "subject_cluster": "Brubru - AI-tools voor {name} beleidsprofessionals",
        "subject_generic": "Brubru - AI-assistent voor professionals in Europese zaken",
        "header_subtitle": "AI-tools voor EU-beleid",
        "greeting": "Beste collega,",
        "intro_cluster": (
            "Als uw organisatie werkt aan <strong>{name}</strong> beleid in de EU, "
            "kan <strong>Brubru</strong> nuttig voor u zijn. Het is een gratis AI-assistent "
            "speciaal ontworpen voor professionals in Europees beleid, ontwikkeld door "
            "<strong>Beresol</strong>, een public affairs adviesbureau gevestigd in Brussel."
        ),
        "intro_generic": (
            "Als organisatie die actief is in Europese zaken, kan <strong>Brubru</strong> nuttig voor u zijn. "
            "Het is een gratis AI-assistent speciaal ontworpen voor professionals in Europees beleid, "
            "ontwikkeld door <strong>Beresol</strong>, een public affairs adviesbureau gevestigd in Brussel."
        ),
        "section_cluster": "Hoe Brubru u helpt met {name}:",
        "section_generic": "Wat Brubru voor u kan doen:",
        "feat_questions": "<strong>Stel beleidsvragen</strong> &mdash; krijg direct antwoord over {topic} wetgeving, waaronder {file}, met geciteerde bronnen",
        "feat_questions_generic": "<strong>Beantwoord EU-beleidsvragen</strong> &mdash; vraag alles over verordeningen, richtlijnen of institutionele processen, met bronnen",
        "feat_amendments": "<strong>Stel amendementen op</strong> &mdash; gebruik de Amendator om professionele wetgevingsamendementen te maken voor dossiers zoals {file}",
        "feat_amendments_generic": "<strong>Stel amendementen op</strong> &mdash; gebruik de Amendator om professionele wetgevingsamendementen te maken met AI-ondersteuning",
        "feat_track": "<strong>Volg het werk van {committee}</strong> &mdash; monitor lopende commissiewerkzaamheden, RSS-feeds van meer dan 15 EU-bronnen en wetgevingsontwikkelingen",
        "feat_track_generic": "<strong>Volg wetgeving</strong> &mdash; monitor commissiewerkzaamheden, RSS-feeds van meer dan 15 EU-bronnen en wetgevingsontwikkelingen",
        "feat_generate": "<strong>Genereer documenten</strong> &mdash; position papers, briefings voor Europarlementariers en gesprekspunten over {topic} in enkele seconden",
        "feat_generate_generic": "<strong>Genereer documenten</strong> &mdash; position papers, briefings voor Europarlementariers en gesprekspunten in enkele seconden",
        "key_files_heading": "Belangrijke EU-dossiers die Brubru behandelt in {name}:",
        "cta_button": "Probeer Brubru gratis",
        "free_notice": "Brubru is gratis. Geen creditcard vereist.",
        "unsubscribe": "Als u geen e-mails meer van ons wilt ontvangen, beantwoord dan simpelweg dit bericht.",
    },
}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def classify_org(org: dict) -> str:
    """
    Classify an org into a policy cluster based on goals + activity_eu_legislative.
    Returns the cluster key with highest keyword match density.
    Falls back to main_category mapping if no keywords match.
    """
    text = " ".join([
        org.get("goals", ""),
        org.get("activity_eu_legislative", ""),
        org.get("sub_category", ""),
    ]).lower()

    if not text.strip():
        # Try category fallback
        cat = org.get("main_category", "")
        return CATEGORY_FALLBACK.get(cat, "other")

    scores: dict[str, int] = {}
    for cluster_key, cluster in CLUSTERS.items():
        score = 0
        for keyword in cluster["keywords"]:
            if keyword in text:
                score += len(keyword.split())
        if score > 0:
            scores[cluster_key] = score

    if not scores:
        # Try category fallback
        cat = org.get("main_category", "")
        return CATEGORY_FALLBACK.get(cat, "other")

    return max(scores, key=scores.get)


def classify_all(orgs: list[dict]) -> dict[str, list[dict]]:
    """Classify all orgs and return grouped by cluster."""
    grouped: dict[str, list[dict]] = defaultdict(list)

    for org in orgs:
        cluster = classify_org(org)
        org["policy_cluster"] = cluster
        grouped[cluster].append(org)

    return dict(grouped)


def get_lang_for_org(org: dict) -> str:
    """Determine the email language for an org based on its country and domain.

    .cat domains and Barcelona-based orgs get Catalan (ca).
    Spanish orgs without .cat get Spanish (es).
    """
    domain = org.get("domain", "").strip().lower()
    email = org.get("contact_email", "").strip().lower()
    name = org.get("original_name", "").lower()

    # .cat TLD is the strongest Catalan signal
    if domain.endswith(".cat") or email.endswith(".cat"):
        return "ca"

    # Catalan org names or city indicators
    catalan_signals = [
        "catalunya", "catalonia", "generalitat", "barcelona",
        "associació", "fundació", "institut català",
    ]
    if any(signal in name for signal in catalan_signals):
        return "ca"

    country = org.get("head_country", "").strip().upper()
    return COUNTRY_LANGUAGE_MAP.get(country, "en")


# ---------------------------------------------------------------------------
# Email Template Builder
# ---------------------------------------------------------------------------

def _build_email_html(
    subject: str,
    header_subtitle: str,
    greeting: str,
    intro: str,
    section_heading: str,
    features: list[tuple[str, str]],  # [(color, html_text), ...]
    key_files_html: str,
    cta_text: str,
    free_notice: str,
    unsubscribe: str,
) -> str:
    """Build the HTML email from translated components."""
    colors = ["#0693e3", "#059669", "#9b51e0", "#d97706"]

    features_html = ""
    for i, (_, feat_text) in enumerate(features):
        color = colors[i % len(colors)]
        features_html += f"""
                                <tr>
                                    <td style="padding:8px 12px 8px 0;vertical-align:top;color:{color};font-size:18px;">&#9679;</td>
                                    <td style="padding:8px 0;color:#475569;font-size:15px;line-height:1.5;">
                                        {feat_text}
                                    </td>
                                </tr>"""

    files_section = ""
    if key_files_html:
        files_section = f"""
                            <p style="color:#475569;font-size:14px;line-height:1.5;margin:0 0 8px;">
                                <strong>{key_files_html}</strong>
                            </p>"""

    return f"""\
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="margin:0;padding:0;background-color:#f8fafc;font-family:'Segoe UI',Roboto,sans-serif;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f8fafc;padding:40px 20px;">
            <tr><td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">

                    <!-- Header -->
                    <tr>
                        <td style="background:linear-gradient(135deg,#003399 0%,#0055a4 100%);padding:32px 40px;text-align:center;">
                            <img src="https://brubru.beresol.eu/assets/brubru_mainlogo.png" alt="Brubru" width="120" style="margin-bottom:12px;" />
                            <p style="color:#ffffff;font-size:14px;margin:0;opacity:0.9;">{header_subtitle}</p>
                        </td>
                    </tr>

                    <!-- Body -->
                    <tr>
                        <td style="padding:40px;">
                            <h1 style="color:#1e293b;font-size:22px;margin:0 0 16px;">{greeting}</h1>
                            <p style="color:#475569;font-size:16px;line-height:1.6;margin:0 0 20px;">
                                {intro}
                            </p>

                            <h2 style="color:#1e293b;font-size:17px;margin:24px 0 12px;">{section_heading}</h2>
                            <table cellpadding="0" cellspacing="0" style="margin-bottom:24px;">
                                {features_html}
                            </table>

                            {files_section}

                            <!-- CTA Button -->
                            <table cellpadding="0" cellspacing="0" style="margin:32px 0;">
                                <tr><td align="center" style="background-color:#0693e3;border-radius:8px;">
                                    <a href="https://brubru.beresol.eu"
                                       style="display:inline-block;padding:14px 36px;color:#ffffff;font-size:16px;font-weight:600;text-decoration:none;">
                                        {cta_text}
                                    </a>
                                </td></tr>
                            </table>

                            <p style="color:#475569;font-size:14px;line-height:1.6;margin:20px 0 0;">
                                {free_notice}
                            </p>

                            <p style="color:#94a3b8;font-size:13px;line-height:1.5;margin:24px 0 0;">
                                {unsubscribe}
                            </p>
                        </td>
                    </tr>

                    <!-- Footer -->
                    <tr>
                        <td style="background-color:#f1f5f9;padding:20px 40px;text-align:center;">
                            <p style="color:#94a3b8;font-size:12px;margin:0;">
                                Beresol &middot; EU Public Affairs &middot; Brussels &middot;
                                <a href="https://beresol.eu" style="color:#0693e3;text-decoration:none;">beresol.eu</a>
                            </p>
                        </td>
                    </tr>

                </table>
            </td></tr>
        </table>
    </body>
    </html>"""


def build_cluster_email(cluster_key: str, lang: str = "en") -> dict:
    """
    Build a tailored HTML email for a specific policy cluster in the given language.
    Returns {"subject": str, "html_body": str}.
    """
    cluster = CLUSTERS.get(cluster_key)
    if not cluster:
        return build_generic_email(lang)

    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])
    name = cluster["name"]
    files = cluster["files"]
    committee = cluster["committee"]
    topic = name.lower()

    subject = t["subject_cluster"].format(name=name)
    intro = t["intro_cluster"].format(name=name)
    section = t["section_cluster"].format(name=name)

    file_0 = files[0] if files else "key EU files"
    file_1 = files[1] if len(files) > 1 else file_0

    features = [
        ("blue", t["feat_questions"].format(topic=topic, file=file_0)),
        ("green", t["feat_amendments"].format(file=file_1)),
        ("purple", t["feat_track"].format(committee=committee)),
        ("gold", t["feat_generate"].format(topic=topic)),
    ]

    # Key files list
    files_html = t["key_files_heading"].format(name=name)
    files_list = "".join(f"<li style='margin-bottom:4px;'>{f}</li>" for f in files[:3])
    files_section = f"""{files_html}</strong>
                            </p>
                            <ul style="color:#475569;font-size:14px;line-height:1.6;margin:0 0 24px;padding-left:20px;">
                                {files_list}
                            </ul"""

    html_body = _build_email_html(
        subject=subject,
        header_subtitle=t["header_subtitle"],
        greeting=t["greeting"],
        intro=intro,
        section_heading=section,
        features=features,
        key_files_html=files_section,
        cta_text=t["cta_button"],
        free_notice=t["free_notice"],
        unsubscribe=t["unsubscribe"],
    )

    return {"subject": subject, "html_body": html_body}


def build_generic_email(lang: str = "en") -> dict:
    """Build a generic email for orgs that don't fit a specific cluster."""
    t = TRANSLATIONS.get(lang, TRANSLATIONS["en"])

    subject = t["subject_generic"]
    features = [
        ("blue", t["feat_questions_generic"]),
        ("green", t["feat_amendments_generic"]),
        ("purple", t["feat_track_generic"]),
        ("gold", t["feat_generate_generic"]),
    ]

    html_body = _build_email_html(
        subject=subject,
        header_subtitle=t["header_subtitle"],
        greeting=t["greeting"],
        intro=t["intro_generic"],
        section_heading=t["section_generic"],
        features=features,
        key_files_html="",
        cta_text=t["cta_button"],
        free_notice=t["free_notice"],
        unsubscribe=t["unsubscribe"],
    )

    return {"subject": subject, "html_body": html_body}


# ---------------------------------------------------------------------------
# Campaign Sending
# ---------------------------------------------------------------------------

def send_cluster_campaign(cluster_key: str, emails: list[str], lang: str = "en", dry_run: bool = True):
    """Send tailored emails to a specific policy cluster in a given language."""
    from scripts.collect_mep_emails import send_bcc_campaign

    template = build_cluster_email(cluster_key, lang)
    cluster_name = CLUSTERS.get(cluster_key, {}).get("name", "Other")

    logger.info(f"\n[SEND] Cluster: {cluster_name} | Lang: {lang} | Recipients: {len(emails)}")
    logger.info(f"[SEND] Subject: {template['subject']}")

    result = send_bcc_campaign(
        recipients=emails,
        subject=template["subject"],
        html_body=template["html_body"],
        dry_run=dry_run,
    )

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Tailored multilingual lobby org email campaign")
    parser.add_argument("--classify-only", action="store_true", help="Only classify orgs and show distribution")
    parser.add_argument("--test-templates", action="store_true", help="Send test emails to hello@beresol.eu")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent")
    parser.add_argument("--send", action="store_true", help="Actually send emails")
    parser.add_argument("--cluster", type=str, help="Only process this cluster")
    parser.add_argument("--country", type=str, help="Comma-separated country names (e.g. spain,italy,france)")
    parser.add_argument("--lang", type=str, help="Force language (en/es/it/fr/nl)")
    args = parser.parse_args()

    if not EMAILS_CSV.exists():
        logger.error(f"[ERROR] Emails CSV not found: {EMAILS_CSV}")
        logger.error("Run collect_lobby_emails.py first")
        return

    # Load orgs with emails
    orgs = []
    with open(EMAILS_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            orgs.append(row)

    logger.info(f"[OK] Loaded {len(orgs)} orgs from {EMAILS_CSV}")

    # Filter to orgs with contact emails
    orgs_with_email = [o for o in orgs if o.get("contact_email")]
    logger.info(f"[OK] {len(orgs_with_email)} orgs have contact emails")

    # Country filter
    country_filter = None
    if args.country:
        country_filter = {c.strip().upper() for c in args.country.split(",")}
        orgs_with_email = [o for o in orgs_with_email if o.get("head_country", "").strip().upper() in country_filter]
        logger.info(f"[OK] {len(orgs_with_email)} orgs after country filter: {', '.join(sorted(country_filter))}")

    # Classify
    grouped = classify_all(orgs_with_email)

    # Show distribution
    total = len(orgs_with_email)
    logger.info(f"\n{'Cluster':<30} {'Count':>7} {'%':>6}")
    logger.info("-" * 45)
    for key in sorted(grouped.keys(), key=lambda k: len(grouped[k]), reverse=True):
        count = len(grouped[key])
        pct = (count / total * 100) if total > 0 else 0
        name = CLUSTERS.get(key, {}).get("name", "Other")
        logger.info(f"{name:<30} {count:>7} {pct:>5.1f}%")

    # Show country + language breakdown if filtering
    if country_filter or args.classify_only:
        from collections import Counter
        lang_counts = Counter(get_lang_for_org(o) for o in orgs_with_email)
        country_counts = Counter(o.get("head_country", "UNKNOWN").strip().upper() for o in orgs_with_email)
        logger.info(f"\n{'Country':<20} {'Count':>7} {'Language':>8}")
        logger.info("-" * 37)
        for country, count in country_counts.most_common():
            logger.info(f"{country:<20} {count:>7}")
        logger.info(f"\n{'Language':<20} {'Count':>7}")
        logger.info("-" * 28)
        for lang, count in lang_counts.most_common():
            logger.info(f"{lang:<20} {count:>7}")

    if args.classify_only:
        return

    # Test templates
    if args.test_templates:
        from scripts.collect_mep_emails import send_bcc_campaign

        test_recipient = "hello@beresol.eu"
        lang = args.lang or "en"
        all_keys = list(CLUSTERS.keys()) + ["other"]

        for key in all_keys:
            template = build_cluster_email(key, lang)
            logger.info(f"\n[TEST] Sending {key} [{lang}] template to {test_recipient}")
            send_bcc_campaign(
                recipients=[test_recipient],
                subject=f"[TEST-{lang.upper()}] {template['subject']}",
                html_body=template["html_body"],
                dry_run=False,
            )

        logger.info(f"\n[DONE] Sent {len(all_keys)} test emails ({lang}) to {test_recipient}")
        return

    # Dry run or send
    if args.dry_run or args.send:
        # Group by (cluster, country) for language-aware sending
        send_groups: dict[tuple[str, str, str], list[str]] = defaultdict(list)

        for key, cluster_orgs in grouped.items():
            if args.cluster and key != args.cluster:
                continue

            for org in cluster_orgs:
                email = org.get("contact_email", "")
                if not email:
                    continue

                country = org.get("head_country", "UNKNOWN").strip().upper()
                lang = args.lang or COUNTRY_LANGUAGE_MAP.get(country, "en")
                group_key = (key, country, lang)
                send_groups[group_key].append(email)

        # Deduplicate within each group
        for group_key in send_groups:
            send_groups[group_key] = list(dict.fromkeys(send_groups[group_key]))

        # Sort by (lang, cluster) for readable output
        for (cluster_key, country, lang), emails in sorted(send_groups.items(), key=lambda x: (x[0][2], x[0][0])):
            cluster_name = CLUSTERS.get(cluster_key, {}).get("name", "Other")
            if args.dry_run:
                logger.info(f"[DRY-RUN] {cluster_name:<30} {country:<15} {lang} {len(emails):>5} recipients")
            else:
                send_cluster_campaign(
                    cluster_key=cluster_key,
                    emails=emails,
                    lang=lang,
                    dry_run=False,
                )

        total_recipients = sum(len(e) for e in send_groups.values())
        total_groups = len(send_groups)
        logger.info(f"\n[SUMMARY] {total_recipients} recipients across {total_groups} groups")

    if not any([args.classify_only, args.test_templates, args.dry_run, args.send]):
        logger.info("\nUse --classify-only, --test-templates, --dry-run, or --send")


if __name__ == "__main__":
    main()
