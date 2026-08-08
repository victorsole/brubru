"""
Proactive Chat trigger engine.

Given an authenticated user, computes a small list of briefings Brubru should
proactively surface in Chat. Each briefing is grounded in real DB rows; if no
real signal exists, the engine returns an empty list — never invents content.

Triggers
--------
- ``morning_brief``           First session of the day, summarises 1–3 events
                              relevant to the user (new files matching profile
                              + calendar today + tracked-file movement).
- ``new_file_match``          A legislative file appeared in the last 7 days
                              matching the user's policy interests.
- ``tracked_file_movement``   A file the user tracks moved status in the last
                              7 days.
- ``amendment_surge``         > 5 new amendments on a tracked file in 24h.

Hard cap: 3 briefings per user per request (and per day, enforced upstream
once we persist the deliveries — see migration 074 ``is_proactive`` flag).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.user import User
from services.personalization.greeting_service import resolve_greeting_language


logger = logging.getLogger(__name__)


TriggerSource = Literal[
    "morning_brief",
    "new_file_match",
    "tracked_file_movement",
    "amendment_surge",
    "learn_about_you",
    "conversation_recall",
    "weekly_digest",
]


MAX_BRIEFINGS_PER_REQUEST = 3
AMENDMENT_SURGE_THRESHOLD = 5
NEW_FILE_WINDOW_DAYS = 7
TRACKED_MOVEMENT_WINDOW_DAYS = 7
AMENDMENT_SURGE_WINDOW_HOURS = 24


# Human-readable labels for the raw institution enum values stored in
# eu_calendar_events.institution. Anything not in this map falls back to
# a sentence-cased version of the enum.
INSTITUTION_LABELS = {
    "EP": "The European Parliament",
    "COMMISSION": "The European Commission",
    "COUNCIL": "The Council of the EU",
    "EUROPEAN_COUNCIL": "The European Council",
    "ECB": "The European Central Bank",
    "COR": "The Committee of the Regions",
    "EESC": "The European Economic and Social Committee",
    "CJEU": "The Court of Justice of the EU",
    "THIRD_PARTY": "A Brussels policy event",
    # Agencies. Without these the acronym fallback title-cased them into
    # nonsense ("EMA" -> "Ema has on its agenda today").
    "EMA": "The European Medicines Agency",
    "EFSA": "The European Food Safety Authority",
    "ECHA": "The European Chemicals Agency",
    "EEA": "The European Environment Agency",
    "EASA": "The EU Aviation Safety Agency",
    "ENISA": "The EU Agency for Cybersecurity",
    "EBA": "The European Banking Authority",
    "EIOPA": "The European Insurance and Occupational Pensions Authority",
    "ESMA": "The European Securities and Markets Authority",
    "FRONTEX": "Frontex",
    "EUROPOL": "Europol",
    "EUIPO": "The EU Intellectual Property Office",
    "ACER": "The EU Agency for the Cooperation of Energy Regulators",
    "AMLA": "The Anti-Money Laundering Authority",
    "EPSO": "The European Personnel Selection Office",
    "CEPOL": "CEPOL",
    "EEAS": "The European External Action Service",
    "REA": "The European Research Executive Agency",
    "ERC": "The European Research Council",
}


# ---------------------------------------------------------------------------
# Briefing strings in Brubru's 6 languages (EN, ES, CA, FR, IT, NL).
# users.language drives the choice via resolve_greeting_language(); unknown
# or missing languages fall back to EN. The composed message STRUCTURE is
# identical in every language (same sentences, same data slots): only the
# language varies. EN templates reproduce the historical hardcoded strings
# byte for byte, with one deliberate exception: nf_summary_* / tm_summary_*
# no longer interpolate file titles. Official EU legal titles run 150-400
# characters each, so three of them joined into one sentence produced a
# ~1,200-character paragraph on the briefing card. Those titles now travel in
# ProactiveBriefing.items, one openable line per file, and these four strings
# are the short lead-in to that list.
#
# Keys use .format()-style placeholders. Placeholder data (DB titles, refs)
# is always passed as format arguments, never substituted into the template
# string itself, so braces inside DB titles cannot break formatting.
# ---------------------------------------------------------------------------

TRIGGER_I18N: Dict[str, Dict[str, Any]] = {
    "en": {
        "institutions": INSTITUTION_LABELS,
        "institution_fallback": "An EU institution",
        # EN has no status map: raw lowercased English statuses pass through.
        "status": {},
        "weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                     "Saturday", "Sunday"],
        "months": ["January", "February", "March", "April", "May", "June",
                   "July", "August", "September", "October", "November",
                   "December"],
        # new_file_match
        "nf_title_one": "A new legislative file landed in your policy areas",
        "nf_title_many": "{count} new legislative files landed in your policy areas this week",
        "nf_summary_one": "The file that matched:",
        "nf_summary_many": "The most recent matches:",
        "nf_query": (
            "Brief me on the EU legislative files added in the last week "
            "that match my policy interests."
        ),
        # tracked_file_movement
        "tm_status_unknown": "an unknown status",
        "tm_title_one": "One of your tracked files moved to {status}",
        "tm_summary_one": "The file that moved:",
        "tm_title_many": "{count} of your tracked files moved this week",
        "tm_summary_many": "The files that moved:",
        "tm_query": (
            "Summarise the status changes on the files I track in the last "
            "week and what they mean for the procedure timeline."
        ),
        # amendment_surge
        "as_title": "{count} new amendments tabled on a file you track",
        "as_summary": (
            "{title} received {count} amendments in the "
            "last 24 hours. The centre of gravity may have moved."
        ),
        "as_query": (
            "Summarise the new amendments tabled in the last 24 hours on "
            "procedure {ref}, and tell me "
            "which articles are most affected."
        ),
        # morning_brief
        "mb_title": "Your EU briefing for today",
        "mb_summary": "{institution} has on its agenda today: {event_title}.",
        "mb_query": (
            "Brief me on today's {event_title}: agenda, who is meeting, "
            "and what to watch."
        ),
        # weekly_digest
        "wd_title": "Your week on Brubru",
        "wd_since_weekday": "since {weekday}",
        "wd_since_date": "since {day} {month}",
        "wd_moves_one": "1 of your tracked files moved ({title})",
        "wd_moves_many": "{count} of your tracked files moved",
        "wd_new_one": "1 new file appeared in your interests ({title})",
        "wd_new_many": "{count} new files appeared in your interests",
        "wd_surge_one": "1 tracked file saw an amendment surge",
        "wd_surge_many": "{count} tracked files saw an amendment surge",
        "wd_summary": "While you were away ({since}): {body}",
        "wd_query": (
            "Walk me through what moved on my watch {since}: "
            "the file status changes, new matches, and any amendment surges. "
            "Group them by topic and tell me what to read first."
        ),
        # conversation_recall
        "cr_title": "Pick up where we left off",
        "cr_summary": (
            "Last time you asked about: {topic}. "
            "Want to pick up where we left off?"
        ),
        "cr_query": (
            "Where did we leave off on '{topic}'? Walk me through what "
            "we discussed and what to do next."
        ),
        # learn_about_you
        "lay_title": "Tell me what you follow",
        "lay_summary": (
            "I do not know your portfolio yet. Tell me one EU file or topic "
            "you care about and I will keep an eye on it for you."
        ),
        "lay_query": "I follow the following EU files and topics: ",
    },
    "ca": {
        "institutions": {
            "EP": "El Parlament Europeu",
            "COMMISSION": "La Comissió Europea",
            "COUNCIL": "El Consell de la UE",
            "EUROPEAN_COUNCIL": "El Consell Europeu",
            "ECB": "El Banc Central Europeu",
            "COR": "El Comitè de les Regions",
            "EESC": "El Comitè Econòmic i Social Europeu",
            "CJEU": "El Tribunal de Justícia de la UE",
            "THIRD_PARTY": "Un esdeveniment polític de Brussel·les",
            "EMA": "L'Agència Europea de Medicaments",
            "EFSA": "L'Autoritat Europea de Seguretat Alimentària",
            "ECHA": "L'Agència Europea de Substàncies Químiques",
            "EEA": "L'Agència Europea de Medi Ambient",
            "EASA": "L'Agència de Seguretat Aèria de la UE",
            "ENISA": "L'Agència de Ciberseguretat de la UE",
            "EBA": "L'Autoritat Bancària Europea",
            "EIOPA": "L'Autoritat Europea d'Assegurances i Pensions de Jubilació",
            "ESMA": "L'Autoritat Europea de Valors i Mercats",
            "FRONTEX": "Frontex",
            "EUROPOL": "Europol",
            "EUIPO": "L'Oficina de Propietat Intel·lectual de la UE",
            "ACER": "L'Agència de la UE per a la Cooperació dels Reguladors de l'Energia",
            "AMLA": "L'Autoritat de Lluita contra el Blanqueig de Capitals",
            "EPSO": "L'Oficina Europea de Selecció de Personal",
            "CEPOL": "CEPOL",
            "EEAS": "El Servei Europeu d'Acció Exterior",
            "REA": "L'Agència Executiva Europea de Recerca",
            "ERC": "El Consell Europeu de Recerca",
        },
        "institution_fallback": "Una institució de la UE",
        "status": {
            "announced": "anunciat", "tabled": "presentat",
            "in committee": "en comissió",
            "close to adoption": "a prop de l'adopció", "adopted": "adoptat",
            "completed": "completat", "rejected": "rebutjat",
            "withdrawn": "retirat",
        },
        "weekdays": ["dilluns", "dimarts", "dimecres", "dijous", "divendres",
                     "dissabte", "diumenge"],
        "months": ["de gener", "de febrer", "de març", "d'abril", "de maig",
                   "de juny", "de juliol", "d'agost", "de setembre",
                   "d'octubre", "de novembre", "de desembre"],
        "nf_title_one": "Ha arribat un nou expedient legislatiu a les teves àrees polítiques",
        "nf_title_many": "{count} nous expedients legislatius han arribat a les teves àrees polítiques aquesta setmana",
        "nf_summary_one": "L'expedient que ha coincidit:",
        "nf_summary_many": "Les coincidències més recents:",
        "nf_query": (
            "Fes-me un resum dels expedients legislatius de la UE afegits "
            "la darrera setmana que coincideixen amb els meus interessos polítics."
        ),
        "tm_status_unknown": "un estat desconegut",
        "tm_title_one": "Un dels expedients que segueixes ha canviat d'estat: {status}",
        "tm_summary_one": "L'expedient que s'ha mogut:",
        "tm_title_many": "{count} dels expedients que segueixes s'han mogut aquesta setmana",
        "tm_summary_many": "Els expedients que s'han mogut:",
        "tm_query": (
            "Resumeix els canvis d'estat dels expedients que segueixo durant "
            "la darrera setmana i què impliquen per al calendari del procediment."
        ),
        "as_title": "{count} noves esmenes presentades a un expedient que segueixes",
        "as_summary": (
            "{title} ha rebut {count} esmenes en les darreres 24 hores. "
            "El centre de gravetat pot haver-se desplaçat."
        ),
        "as_query": (
            "Resumeix les noves esmenes presentades en les darreres 24 hores "
            "al procediment {ref}, i digue'm quins articles es veuen més afectats."
        ),
        "mb_title": "El teu resum de la UE per avui",
        "mb_summary": "{institution} té avui a l'agenda: {event_title}.",
        "mb_query": (
            "Fes-me un resum de {event_title} d'avui: agenda, qui es reuneix "
            "i què cal vigilar."
        ),
        "wd_title": "La teva setmana a Brubru",
        "wd_since_weekday": "des de {weekday}",
        "wd_since_date": "des del {day} {month}",
        "wd_moves_one": "1 dels expedients que segueixes s'ha mogut ({title})",
        "wd_moves_many": "{count} dels expedients que segueixes s'han mogut",
        "wd_new_one": "1 nou expedient ha aparegut en els teus interessos ({title})",
        "wd_new_many": "{count} nous expedients han aparegut en els teus interessos",
        "wd_surge_one": "1 expedient seguit ha registrat una allau d'esmenes",
        "wd_surge_many": "{count} expedients seguits han registrat una allau d'esmenes",
        "wd_summary": "Mentre eres fora ({since}): {body}",
        "wd_query": (
            "Explica'm què s'ha mogut en el meu seguiment {since}: "
            "els canvis d'estat dels expedients, les noves coincidències i "
            "qualsevol allau d'esmenes. Agrupa-ho per temes i digue'm què he "
            "de llegir primer."
        ),
        "cr_title": "Reprenem on ho vam deixar",
        "cr_summary": (
            "L'última vegada em vas preguntar sobre: {topic}. "
            "Vols reprendre-ho on ho vam deixar?"
        ),
        "cr_query": (
            "On ho vam deixar sobre '{topic}'? Explica'm què vam comentar "
            "i què cal fer a continuació."
        ),
        "lay_title": "Explica'm què segueixes",
        "lay_summary": (
            "Encara no conec la teva cartera. Digue'm un expedient o tema de "
            "la UE que t'interessi i te'n faré el seguiment."
        ),
        "lay_query": "Segueixo els següents expedients i temes de la UE: ",
    },
    "es": {
        "institutions": {
            "EP": "El Parlamento Europeo",
            "COMMISSION": "La Comisión Europea",
            "COUNCIL": "El Consejo de la UE",
            "EUROPEAN_COUNCIL": "El Consejo Europeo",
            "ECB": "El Banco Central Europeo",
            "COR": "El Comité de las Regiones",
            "EESC": "El Comité Económico y Social Europeo",
            "CJEU": "El Tribunal de Justicia de la UE",
            "THIRD_PARTY": "Un evento político de Bruselas",
            "EMA": "La Agencia Europea de Medicamentos",
            "EFSA": "La Autoridad Europea de Seguridad Alimentaria",
            "ECHA": "La Agencia Europea de Sustancias y Mezclas Químicas",
            "EEA": "La Agencia Europea de Medio Ambiente",
            "EASA": "La Agencia de Seguridad Aérea de la UE",
            "ENISA": "La Agencia de Ciberseguridad de la UE",
            "EBA": "La Autoridad Bancaria Europea",
            "EIOPA": "La Autoridad Europea de Seguros y Pensiones de Jubilación",
            "ESMA": "La Autoridad Europea de Valores y Mercados",
            "FRONTEX": "Frontex",
            "EUROPOL": "Europol",
            "EUIPO": "La Oficina de Propiedad Intelectual de la UE",
            "ACER": "La Agencia de la UE para la Cooperación de los Reguladores de la Energía",
            "AMLA": "La Autoridad de Lucha contra el Blanqueo de Capitales",
            "EPSO": "La Oficina Europea de Selección de Personal",
            "CEPOL": "CEPOL",
            "EEAS": "El Servicio Europeo de Acción Exterior",
            "REA": "La Agencia Ejecutiva Europea de Investigación",
            "ERC": "El Consejo Europeo de Investigación",
        },
        "institution_fallback": "Una institución de la UE",
        "status": {
            "announced": "anunciado", "tabled": "presentado",
            "in committee": "en comisión",
            "close to adoption": "cerca de la adopción", "adopted": "adoptado",
            "completed": "completado", "rejected": "rechazado",
            "withdrawn": "retirado",
        },
        "weekdays": ["lunes", "martes", "miércoles", "jueves", "viernes",
                     "sábado", "domingo"],
        "months": ["de enero", "de febrero", "de marzo", "de abril",
                   "de mayo", "de junio", "de julio", "de agosto",
                   "de septiembre", "de octubre", "de noviembre",
                   "de diciembre"],
        "nf_title_one": "Ha llegado un nuevo expediente legislativo a tus áreas políticas",
        "nf_title_many": "{count} nuevos expedientes legislativos han llegado a tus áreas políticas esta semana",
        "nf_summary_one": "El expediente que ha coincidido:",
        "nf_summary_many": "Las coincidencias más recientes:",
        "nf_query": (
            "Hazme un resumen de los expedientes legislativos de la UE "
            "añadidos en la última semana que coinciden con mis intereses políticos."
        ),
        "tm_status_unknown": "un estado desconocido",
        "tm_title_one": "Uno de los expedientes que sigues ha cambiado de estado: {status}",
        "tm_summary_one": "El expediente que se ha movido:",
        "tm_title_many": "{count} de los expedientes que sigues se han movido esta semana",
        "tm_summary_many": "Los expedientes que se han movido:",
        "tm_query": (
            "Resume los cambios de estado de los expedientes que sigo en la "
            "última semana y qué implican para el calendario del procedimiento."
        ),
        "as_title": "{count} nuevas enmiendas presentadas a un expediente que sigues",
        "as_summary": (
            "{title} ha recibido {count} enmiendas en las últimas 24 horas. "
            "El centro de gravedad puede haberse desplazado."
        ),
        "as_query": (
            "Resume las nuevas enmiendas presentadas en las últimas 24 horas "
            "al procedimiento {ref}, y dime qué artículos se ven más afectados."
        ),
        "mb_title": "Tu resumen de la UE para hoy",
        "mb_summary": "{institution} tiene hoy en su agenda: {event_title}.",
        "mb_query": (
            "Hazme un resumen de {event_title} de hoy: agenda, quién se "
            "reúne y qué hay que vigilar."
        ),
        "wd_title": "Tu semana en Brubru",
        "wd_since_weekday": "desde el {weekday}",
        "wd_since_date": "desde el {day} {month}",
        "wd_moves_one": "1 de los expedientes que sigues se ha movido ({title})",
        "wd_moves_many": "{count} de los expedientes que sigues se han movido",
        "wd_new_one": "1 nuevo expediente ha aparecido en tus intereses ({title})",
        "wd_new_many": "{count} nuevos expedientes han aparecido en tus intereses",
        "wd_surge_one": "1 expediente seguido ha registrado una oleada de enmiendas",
        "wd_surge_many": "{count} expedientes seguidos han registrado una oleada de enmiendas",
        "wd_summary": "Mientras estabas fuera ({since}): {body}",
        "wd_query": (
            "Explícame qué se ha movido en mi seguimiento {since}: "
            "los cambios de estado de los expedientes, las nuevas coincidencias "
            "y cualquier oleada de enmiendas. Agrúpalo por temas y dime qué "
            "debo leer primero."
        ),
        "cr_title": "Retomemos donde lo dejamos",
        "cr_summary": (
            "La última vez me preguntaste sobre: {topic}. "
            "¿Quieres retomarlo donde lo dejamos?"
        ),
        "cr_query": (
            "¿Dónde lo dejamos sobre '{topic}'? Explícame qué comentamos "
            "y qué hacer a continuación."
        ),
        "lay_title": "Cuéntame qué sigues",
        "lay_summary": (
            "Todavía no conozco tu cartera. Dime un expediente o tema de la "
            "UE que te interese y le haré seguimiento por ti."
        ),
        "lay_query": "Sigo los siguientes expedientes y temas de la UE: ",
    },
    "fr": {
        "institutions": {
            "EP": "Le Parlement européen",
            "COMMISSION": "La Commission européenne",
            "COUNCIL": "Le Conseil de l'UE",
            "EUROPEAN_COUNCIL": "Le Conseil européen",
            "ECB": "La Banque centrale européenne",
            "COR": "Le Comité des régions",
            "EESC": "Le Comité économique et social européen",
            "CJEU": "La Cour de justice de l'UE",
            "THIRD_PARTY": "Un événement politique bruxellois",
            "EMA": "L'Agence européenne des médicaments",
            "EFSA": "L'Autorité européenne de sécurité des aliments",
            "ECHA": "L'Agence européenne des produits chimiques",
            "EEA": "L'Agence européenne pour l'environnement",
            "EASA": "L'Agence de la sécurité aérienne de l'UE",
            "ENISA": "L'Agence de l'UE pour la cybersécurité",
            "EBA": "L'Autorité bancaire européenne",
            "EIOPA": "L'Autorité européenne des assurances et des pensions professionnelles",
            "ESMA": "L'Autorité européenne des marchés financiers",
            "FRONTEX": "Frontex",
            "EUROPOL": "Europol",
            "EUIPO": "L'Office de la propriété intellectuelle de l'UE",
            "ACER": "L'Agence de l'UE pour la coopération des régulateurs de l'énergie",
            "AMLA": "L'Autorité de lutte contre le blanchiment de capitaux",
            "EPSO": "L'Office européen de sélection du personnel",
            "CEPOL": "CEPOL",
            "EEAS": "Le Service européen pour l'action extérieure",
            "REA": "L'Agence exécutive européenne pour la recherche",
            "ERC": "Le Conseil européen de la recherche",
        },
        "institution_fallback": "Une institution de l'UE",
        "status": {
            "announced": "annoncé", "tabled": "déposé",
            "in committee": "en commission",
            "close to adoption": "proche de l'adoption", "adopted": "adopté",
            "completed": "clos", "rejected": "rejeté",
            "withdrawn": "retiré",
        },
        "weekdays": ["lundi", "mardi", "mercredi", "jeudi", "vendredi",
                     "samedi", "dimanche"],
        "months": ["janvier", "février", "mars", "avril", "mai", "juin",
                   "juillet", "août", "septembre", "octobre", "novembre",
                   "décembre"],
        "nf_title_one": "Un nouveau dossier législatif est arrivé dans vos domaines politiques",
        "nf_title_many": "{count} nouveaux dossiers législatifs sont arrivés dans vos domaines politiques cette semaine",
        "nf_summary_one": "Le dossier correspondant :",
        "nf_summary_many": "Les correspondances les plus récentes :",
        "nf_query": (
            "Faites-moi un point sur les dossiers législatifs de l'UE ajoutés "
            "la semaine dernière qui correspondent à mes intérêts politiques."
        ),
        "tm_status_unknown": "un statut inconnu",
        "tm_title_one": "Un de vos dossiers suivis a changé de statut : {status}",
        "tm_summary_one": "Le dossier qui a évolué :",
        "tm_title_many": "{count} de vos dossiers suivis ont évolué cette semaine",
        "tm_summary_many": "Les dossiers qui ont évolué :",
        "tm_query": (
            "Résumez les changements de statut des dossiers que je suis au "
            "cours de la dernière semaine et ce qu'ils signifient pour le "
            "calendrier de la procédure."
        ),
        "as_title": "{count} nouveaux amendements déposés sur un dossier que vous suivez",
        "as_summary": (
            "{title} a reçu {count} amendements au cours des dernières 24 "
            "heures. Le centre de gravité a peut-être bougé."
        ),
        "as_query": (
            "Résumez les nouveaux amendements déposés au cours des dernières "
            "24 heures sur la procédure {ref}, et dites-moi quels articles "
            "sont les plus concernés."
        ),
        "mb_title": "Votre briefing UE du jour",
        "mb_summary": "{institution} a aujourd'hui à son agenda : {event_title}.",
        "mb_query": (
            "Faites-moi un point sur {event_title} aujourd'hui : agenda, "
            "qui se réunit et que surveiller."
        ),
        "wd_title": "Votre semaine sur Brubru",
        "wd_since_weekday": "depuis {weekday}",
        "wd_since_date": "depuis le {day} {month}",
        "wd_moves_one": "1 de vos dossiers suivis a évolué ({title})",
        "wd_moves_many": "{count} de vos dossiers suivis ont évolué",
        "wd_new_one": "1 nouveau dossier est apparu dans vos intérêts ({title})",
        "wd_new_many": "{count} nouveaux dossiers sont apparus dans vos intérêts",
        "wd_surge_one": "1 dossier suivi a connu une vague d'amendements",
        "wd_surge_many": "{count} dossiers suivis ont connu une vague d'amendements",
        "wd_summary": "Pendant votre absence ({since}) : {body}",
        "wd_query": (
            "Expliquez-moi ce qui a bougé dans mon suivi {since} : "
            "les changements de statut des dossiers, les nouvelles "
            "correspondances et toute vague d'amendements. Regroupez-les par "
            "thème et dites-moi quoi lire en premier."
        ),
        "cr_title": "Reprenons où nous en étions",
        "cr_summary": (
            "La dernière fois, vous m'avez interrogé sur : {topic}. "
            "Voulez-vous reprendre où nous en étions ?"
        ),
        "cr_query": (
            "Où en étions-nous sur '{topic}' ? Rappelez-moi ce que nous "
            "avons vu et la suite à donner."
        ),
        "lay_title": "Dites-moi ce que vous suivez",
        "lay_summary": (
            "Je ne connais pas encore votre portefeuille. Indiquez-moi un "
            "dossier ou un sujet de l'UE qui vous intéresse et je le suivrai "
            "pour vous."
        ),
        "lay_query": "Je suis les dossiers et sujets UE suivants : ",
    },
    "it": {
        "institutions": {
            "EP": "Il Parlamento europeo",
            "COMMISSION": "La Commissione europea",
            "COUNCIL": "Il Consiglio dell'UE",
            "EUROPEAN_COUNCIL": "Il Consiglio europeo",
            "ECB": "La Banca centrale europea",
            "COR": "Il Comitato delle regioni",
            "EESC": "Il Comitato economico e sociale europeo",
            "CJEU": "La Corte di giustizia dell'UE",
            "THIRD_PARTY": "Un evento politico di Bruxelles",
            "EMA": "L'Agenzia europea per i medicinali",
            "EFSA": "L'Autorità europea per la sicurezza alimentare",
            "ECHA": "L'Agenzia europea per le sostanze chimiche",
            "EEA": "L'Agenzia europea dell'ambiente",
            "EASA": "L'Agenzia della sicurezza aerea dell'UE",
            "ENISA": "L'Agenzia dell'UE per la cibersicurezza",
            "EBA": "L'Autorità bancaria europea",
            "EIOPA": "L'Autorità europea delle assicurazioni e delle pensioni aziendali e professionali",
            "ESMA": "L'Autorità europea degli strumenti finanziari e dei mercati",
            "FRONTEX": "Frontex",
            "EUROPOL": "Europol",
            "EUIPO": "L'Ufficio dell'UE per la proprietà intellettuale",
            "ACER": "L'Agenzia dell'UE per la cooperazione fra i regolatori nazionali dell'energia",
            "AMLA": "L'Autorità per la lotta al riciclaggio",
            "EPSO": "L'Ufficio europeo di selezione del personale",
            "CEPOL": "CEPOL",
            "EEAS": "Il Servizio europeo per l'azione esterna",
            "REA": "L'Agenzia esecutiva europea per la ricerca",
            "ERC": "Il Consiglio europeo della ricerca",
        },
        "institution_fallback": "Un'istituzione dell'UE",
        "status": {
            "announced": "annunciato", "tabled": "presentato",
            "in committee": "in commissione",
            "close to adoption": "vicino all'adozione", "adopted": "adottato",
            "completed": "completato", "rejected": "respinto",
            "withdrawn": "ritirato",
        },
        "weekdays": ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì",
                     "sabato", "domenica"],
        "months": ["gennaio", "febbraio", "marzo", "aprile", "maggio",
                   "giugno", "luglio", "agosto", "settembre", "ottobre",
                   "novembre", "dicembre"],
        "nf_title_one": "Un nuovo fascicolo legislativo è arrivato nelle tue aree politiche",
        "nf_title_many": "{count} nuovi fascicoli legislativi sono arrivati nelle tue aree politiche questa settimana",
        "nf_summary_one": "Il fascicolo corrispondente:",
        "nf_summary_many": "Le corrispondenze più recenti:",
        "nf_query": (
            "Fammi un riepilogo dei fascicoli legislativi dell'UE aggiunti "
            "nell'ultima settimana che corrispondono ai miei interessi politici."
        ),
        "tm_status_unknown": "uno stato sconosciuto",
        "tm_title_one": "Uno dei fascicoli che segui ha cambiato stato: {status}",
        "tm_summary_one": "Il fascicolo che si è mosso:",
        "tm_title_many": "{count} dei fascicoli che segui si sono mossi questa settimana",
        "tm_summary_many": "I fascicoli che si sono mossi:",
        "tm_query": (
            "Riassumi i cambiamenti di stato dei fascicoli che seguo "
            "nell'ultima settimana e cosa significano per il calendario della "
            "procedura."
        ),
        "as_title": "{count} nuovi emendamenti presentati su un fascicolo che segui",
        "as_summary": (
            "{title} ha ricevuto {count} emendamenti nelle ultime 24 ore. "
            "Il baricentro potrebbe essersi spostato."
        ),
        "as_query": (
            "Riassumi i nuovi emendamenti presentati nelle ultime 24 ore "
            "sulla procedura {ref}, e dimmi quali articoli sono più interessati."
        ),
        "mb_title": "Il tuo briefing UE di oggi",
        "mb_summary": "{institution} ha oggi in agenda: {event_title}.",
        "mb_query": (
            "Fammi un riepilogo di {event_title} di oggi: agenda, chi si "
            "riunisce e cosa osservare."
        ),
        "wd_title": "La tua settimana su Brubru",
        "wd_since_weekday": "da {weekday}",
        "wd_since_date": "dal {day} {month}",
        "wd_moves_one": "1 dei fascicoli che segui si è mosso ({title})",
        "wd_moves_many": "{count} dei fascicoli che segui si sono mossi",
        "wd_new_one": "1 nuovo fascicolo è apparso nei tuoi interessi ({title})",
        "wd_new_many": "{count} nuovi fascicoli sono apparsi nei tuoi interessi",
        "wd_surge_one": "1 fascicolo seguito ha registrato un'ondata di emendamenti",
        "wd_surge_many": "{count} fascicoli seguiti hanno registrato un'ondata di emendamenti",
        "wd_summary": "Mentre eri via ({since}): {body}",
        "wd_query": (
            "Spiegami cosa si è mosso nel mio monitoraggio {since}: "
            "i cambiamenti di stato dei fascicoli, le nuove corrispondenze e "
            "qualsiasi ondata di emendamenti. Raggruppali per tema e dimmi "
            "cosa leggere per primo."
        ),
        "cr_title": "Riprendiamo da dove eravamo rimasti",
        "cr_summary": (
            "L'ultima volta mi hai chiesto di: {topic}. "
            "Vuoi riprendere da dove eravamo rimasti?"
        ),
        "cr_query": (
            "Dove eravamo rimasti su '{topic}'? Spiegami cosa abbiamo "
            "discusso e cosa fare adesso."
        ),
        "lay_title": "Dimmi cosa segui",
        "lay_summary": (
            "Non conosco ancora il tuo portafoglio. Dimmi un fascicolo o un "
            "tema dell'UE che ti interessa e lo terrò d'occhio per te."
        ),
        "lay_query": "Seguo i seguenti fascicoli e temi dell'UE: ",
    },
    "nl": {
        "institutions": {
            "EP": "Het Europees Parlement",
            "COMMISSION": "De Europese Commissie",
            "COUNCIL": "De Raad van de EU",
            "EUROPEAN_COUNCIL": "De Europese Raad",
            "ECB": "De Europese Centrale Bank",
            "COR": "Het Comité van de Regio's",
            "EESC": "Het Europees Economisch en Sociaal Comité",
            "CJEU": "Het Hof van Justitie van de EU",
            "THIRD_PARTY": "Een Brussels beleidsevenement",
            "EMA": "Het Europees Geneesmiddelenbureau",
            "EFSA": "De Europese Autoriteit voor voedselveiligheid",
            "ECHA": "Het Europees Agentschap voor chemische stoffen",
            "EEA": "Het Europees Milieuagentschap",
            "EASA": "Het EU-Agentschap voor de veiligheid van de luchtvaart",
            "ENISA": "Het EU-Agentschap voor cyberbeveiliging",
            "EBA": "De Europese Bankautoriteit",
            "EIOPA": "De Europese Autoriteit voor verzekeringen en bedrijfspensioenen",
            "ESMA": "De Europese Autoriteit voor effecten en markten",
            "FRONTEX": "Frontex",
            "EUROPOL": "Europol",
            "EUIPO": "Het Bureau voor intellectuele eigendom van de EU",
            "ACER": "Het EU-Agentschap voor de samenwerking tussen energieregulators",
            "AMLA": "De Autoriteit voor de bestrijding van witwassen",
            "EPSO": "Het Europees Bureau voor personeelsselectie",
            "CEPOL": "CEPOL",
            "EEAS": "De Europese Dienst voor extern optreden",
            "REA": "Het Europees Uitvoerend Agentschap onderzoek",
            "ERC": "De Europese Onderzoeksraad",
        },
        "institution_fallback": "Een EU-instelling",
        "status": {
            "announced": "aangekondigd", "tabled": "ingediend",
            "in committee": "in de commissie",
            "close to adoption": "dicht bij vaststelling",
            "adopted": "vastgesteld", "completed": "afgerond",
            "rejected": "verworpen", "withdrawn": "ingetrokken",
        },
        "weekdays": ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag",
                     "zaterdag", "zondag"],
        "months": ["januari", "februari", "maart", "april", "mei", "juni",
                   "juli", "augustus", "september", "oktober", "november",
                   "december"],
        "nf_title_one": "Er is een nieuw wetgevingsdossier binnengekomen in jouw beleidsterreinen",
        "nf_title_many": "{count} nieuwe wetgevingsdossiers binnengekomen in jouw beleidsterreinen deze week",
        "nf_summary_one": "Het dossier dat overeenkwam:",
        "nf_summary_many": "De meest recente overeenkomsten:",
        "nf_query": (
            "Geef me een briefing over de EU-wetgevingsdossiers die de "
            "afgelopen week zijn toegevoegd en die overeenkomen met mijn "
            "beleidsinteresses."
        ),
        "tm_status_unknown": "een onbekende status",
        "tm_title_one": "Een van je gevolgde dossiers is nu {status}",
        "tm_summary_one": "Het dossier dat is verschoven:",
        "tm_title_many": "{count} van je gevolgde dossiers zijn deze week in beweging gekomen",
        "tm_summary_many": "De dossiers die zijn verschoven:",
        "tm_query": (
            "Vat de statuswijzigingen samen van de dossiers die ik volg in "
            "de afgelopen week en wat ze betekenen voor de proceduretijdlijn."
        ),
        "as_title": "{count} nieuwe amendementen ingediend op een dossier dat je volgt",
        "as_summary": (
            "{title} ontving {count} amendementen in de afgelopen 24 uur. "
            "Het zwaartepunt kan zijn verschoven."
        ),
        "as_query": (
            "Vat de nieuwe amendementen samen die in de afgelopen 24 uur "
            "zijn ingediend op procedure {ref}, en vertel me welke artikelen "
            "het meest geraakt worden."
        ),
        "mb_title": "Je EU-briefing voor vandaag",
        "mb_summary": "{institution} heeft vandaag op de agenda: {event_title}.",
        "mb_query": (
            "Geef me een briefing over {event_title} van vandaag: agenda, "
            "wie er vergadert en waar ik op moet letten."
        ),
        "wd_title": "Jouw week op Brubru",
        "wd_since_weekday": "sinds {weekday}",
        "wd_since_date": "sinds {day} {month}",
        "wd_moves_one": "1 van je gevolgde dossiers kwam in beweging ({title})",
        "wd_moves_many": "{count} van je gevolgde dossiers kwamen in beweging",
        "wd_new_one": "1 nieuw dossier verscheen in je interesses ({title})",
        "wd_new_many": "{count} nieuwe dossiers verschenen in je interesses",
        "wd_surge_one": "1 gevolgd dossier zag een amendementengolf",
        "wd_surge_many": "{count} gevolgde dossiers zagen een amendementengolf",
        "wd_summary": "Terwijl je weg was ({since}): {body}",
        "wd_query": (
            "Loop met me door wat er bewoog in mijn volglijst {since}: "
            "de statuswijzigingen, nieuwe overeenkomsten en eventuele "
            "amendementengolven. Groepeer ze per onderwerp en vertel me wat "
            "ik eerst moet lezen."
        ),
        "cr_title": "Verdergaan waar we gebleven waren",
        "cr_summary": (
            "De vorige keer vroeg je naar: {topic}. "
            "Wil je verdergaan waar we gebleven waren?"
        ),
        "cr_query": (
            "Waar waren we gebleven met '{topic}'? Loop met me door wat we "
            "hebben besproken en wat de volgende stap is."
        ),
        "lay_title": "Vertel me wat je volgt",
        "lay_summary": (
            "Ik ken je portefeuille nog niet. Noem één EU-dossier of "
            "onderwerp dat je belangrijk vindt en ik houd het voor je in de "
            "gaten."
        ),
        "lay_query": "Ik volg de volgende EU-dossiers en onderwerpen: ",
    },
}


def _t(lang: str, key: str) -> Any:
    """Look up a template for ``lang``, falling back to English."""
    table = TRIGGER_I18N.get(lang, TRIGGER_I18N["en"])
    val = table.get(key)
    if val is None:
        val = TRIGGER_I18N["en"][key]
    return val


def _localise_status(lang: str, status_en: str) -> str:
    """
    Translate a lowercased, de-underscored carriage status ('in committee',
    'close to adoption', ...) into the user's language. Unknown statuses
    fall back to the raw lowercased English, mirroring
    api/personalization.py::_RECAP_I18N.
    """
    statuses = _t(lang, "status")
    return statuses.get(status_en, status_en)


def _humanise_institution(raw: Optional[str], lang: str = "en") -> str:
    if not raw:
        return str(_t(lang, "institution_fallback"))
    key = str(raw).strip().upper()
    labels = _t(lang, "institutions")
    if key in labels:
        return labels[key]
    if key in INSTITUTION_LABELS:
        return INSTITUTION_LABELS[key]
    # Unknown value. Short all-caps tokens are acronyms and must keep their
    # capitalisation; .title() would render "EMA" as "Ema".
    if key.isalpha() and len(key) <= 6:
        return key
    return key.replace("_", " ").title()


@dataclass
class ProactiveBriefing:
    """One thing Brubru wants to tell the user without being asked."""

    trigger_source: TriggerSource
    title: str
    summary: str
    suggested_query: str
    evidence_refs: List[str] = field(default_factory=list)
    drill_down_path: Optional[str] = None
    # The concrete rows behind the briefing, one dict per file:
    # {"title", "ref", "carriage_id", "detail"}. Triggers that name specific
    # files fill this so the card can list them as separate, openable lines.
    # Anything the summary would otherwise have to cram into one sentence
    # belongs here. Empty for triggers with nothing itemisable to show.
    items: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "trigger_source": self.trigger_source,
            "title": self.title,
            "summary": self.summary,
            "suggested_query": self.suggested_query,
            "evidence_refs": self.evidence_refs,
            "drill_down_path": self.drill_down_path,
            "items": self.items,
        }


from services.legislative.title_display import (
    curated_alias as _curated_alias,
    file_item as _file_item,
    short_title as _short_title,
    split_celex_prefix as _split_celex_prefix,
)


def _policy_interests(user: User) -> List[str]:
    interests = user.policy_interests_list
    if not interests:
        return []
    return [str(x).strip() for x in interests if x and str(x).strip()]


def _briefing_new_file_match(
    db: Session, user: User, lang: str = "en"
) -> Optional[ProactiveBriefing]:
    interests = _policy_interests(user)
    if not interests:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_FILE_WINDOW_DAYS)
    try:
        rows = db.execute(
            text(
                """
                SELECT id, title, short_title, oeil_procedure_ref, policy_areas,
                       COUNT(*) OVER () AS total_count
                FROM legislative_carriages
                WHERE first_seen >= :cutoff
                  AND EXISTS (
                      SELECT 1 FROM unnest(policy_areas) AS area_v
                      WHERE EXISTS (
                          SELECT 1 FROM unnest(CAST(:interests AS text[])) AS interest_v
                          WHERE LOWER(area_v) = LOWER(interest_v)
                             OR LOWER(area_v) LIKE '%' || LOWER(interest_v) || '%'
                             OR LOWER(interest_v) LIKE '%' || LOWER(area_v) || '%'
                      )
                  )
                ORDER BY first_seen DESC
                LIMIT 3
                """
            ),
            {"cutoff": cutoff, "interests": interests},
        ).mappings().all()
    except Exception as exc:
        logger.warning("new_file_match query failed: %s", exc)
        db.rollback()
        return None

    if not rows:
        return None

    refs = [r["oeil_procedure_ref"] for r in rows if r.get("oeil_procedure_ref")]
    # How many files actually matched, not how many the LIMIT let through.
    # Reporting len(rows) meant the card said "3 new files" whenever there
    # were 3 or more, while the Overview tile beside it said the true 4.
    count = int(rows[0]["total_count"] or len(rows))

    # The file titles are official EU legal titles: routinely 150-400
    # characters each. Joining them into the summary produced a ~1,200-char
    # paragraph nobody could read. They go out as items instead, one openable
    # line per file, and the summary is a short lead-in to that list.
    items = [
        _file_item(
            r["title"],
            r["oeil_procedure_ref"],
            r["id"],
            areas=r.get("policy_areas"),
            lang=lang,
            cached_short_title=r.get("short_title"),
        )
        for r in rows
    ]

    if count == 1:
        title = _t(lang, "nf_title_one")
        summary = _t(lang, "nf_summary_one")
    else:
        title = _t(lang, "nf_title_many").format(count=count)
        summary = _t(lang, "nf_summary_many")

    return ProactiveBriefing(
        trigger_source="new_file_match",
        title=title,
        summary=summary,
        suggested_query=_t(lang, "nf_query"),
        evidence_refs=refs,
        drill_down_path="/my-eu-bubble?tab=my_files",
        items=items,
    )


def _briefing_tracked_file_movement(
    db: Session, user: User, lang: str = "en"
) -> Optional[ProactiveBriefing]:
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=TRACKED_MOVEMENT_WINDOW_DAYS
    )
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    lc.id AS carriage_id,
                    lc.title,
                    lc.short_title,
                    lc.policy_areas,
                    lc.oeil_procedure_ref AS procedure_ref,
                    h.status AS new_status,
                    h.changed_at,
                    COUNT(*) OVER () AS total_count
                FROM user_carriage_tracks uct
                JOIN legislative_carriages lc ON lc.id = uct.carriage_id
                JOIN carriage_status_history h ON h.carriage_id = lc.id
                WHERE uct.user_id = :uid
                  AND h.changed_at >= :cutoff
                ORDER BY h.changed_at DESC
                LIMIT 3
                """
            ),
            {"uid": str(user.id), "cutoff": cutoff},
        ).mappings().all()
    except Exception as exc:
        logger.warning("tracked_file_movement query failed: %s", exc)
        db.rollback()
        return None

    if not rows:
        return None

    refs = [r["procedure_ref"] for r in rows if r.get("procedure_ref")]
    # True number of status changes, not the LIMIT. See _briefing_new_file_match.
    count = int(rows[0]["total_count"] or len(rows))

    def _status_of(row) -> str:
        return (
            _localise_status(
                lang, str(row["new_status"]).replace("_", " ").lower()
            )
            if row.get("new_status")
            else _t(lang, "tm_status_unknown")
        )

    # One openable line per file, carrying the status it moved to, rather than
    # every title concatenated into the summary sentence.
    items = [
        _file_item(
            r["title"],
            r["procedure_ref"],
            r["carriage_id"],
            detail=_status_of(r),
            # The status is the point of this briefing, so it takes the pill
            # slot; one policy area rides alongside it for topic.
            areas=(r.get("policy_areas") or [])[:1],
            lang=lang,
            cached_short_title=r.get("short_title"),
        )
        for r in rows
    ]

    if count == 1:
        title = _t(lang, "tm_title_one").format(status=_status_of(rows[0]))
        summary = _t(lang, "tm_summary_one")
    else:
        title = _t(lang, "tm_title_many").format(count=count)
        summary = _t(lang, "tm_summary_many")

    return ProactiveBriefing(
        trigger_source="tracked_file_movement",
        title=title,
        summary=summary,
        suggested_query=_t(lang, "tm_query"),
        evidence_refs=refs,
        drill_down_path="/my-eu-bubble?tab=my_files",
        items=items,
    )


def _briefing_amendment_surge(
    db: Session, user: User, lang: str = "en"
) -> Optional[ProactiveBriefing]:
    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=AMENDMENT_SURGE_WINDOW_HOURS
    )
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    lc.title,
                    lc.oeil_procedure_ref AS procedure_ref,
                    COUNT(ma.id) AS amendment_count
                FROM user_carriage_tracks uct
                JOIN legislative_carriages lc ON lc.id = uct.carriage_id
                JOIN mep_amendments ma
                  ON ma.procedure_reference = lc.oeil_procedure_ref
                WHERE uct.user_id = :uid
                  AND ma.document_date >= :cutoff
                GROUP BY lc.id, lc.title, lc.oeil_procedure_ref
                HAVING COUNT(ma.id) >= :threshold
                ORDER BY amendment_count DESC
                LIMIT 1
                """
            ),
            {
                "uid": str(user.id),
                "cutoff": cutoff,
                "threshold": AMENDMENT_SURGE_THRESHOLD,
            },
        ).mappings().all()
    except Exception as exc:
        logger.debug("amendment_surge query unavailable: %s", exc)
        db.rollback()
        return None

    if not rows:
        return None

    r = rows[0]
    return ProactiveBriefing(
        trigger_source="amendment_surge",
        title=_t(lang, "as_title").format(count=r["amendment_count"]),
        summary=_t(lang, "as_summary").format(
            title=r["title"], count=r["amendment_count"]
        ),
        suggested_query=_t(lang, "as_query").format(
            ref=r.get("procedure_ref") or r["title"]
        ),
        evidence_refs=[r["procedure_ref"]] if r.get("procedure_ref") else [],
        drill_down_path="/my-eu-bubble?tab=amendments",
    )


# Calendar rows that classify a WEEK rather than describe an event.
#
# These are banners spanning Mon-Fri ("EP Committee Week", "EP Recess"). They
# have no agenda, no attendee list and no start time, so they must never be
# fed into a briefing that promises "agenda, who is meeting, and what to
# watch" -- there is nothing behind that promise to retrieve.
#
# On 20 July 2026 an "EP Committee Week" banner (itself wrongly classified;
# see migration 203 and scripts/derive_ep_calendar_from_pdf.py) produced
# exactly that briefing for a subscriber, who clicked it and was told a
# constituency week was a committee week. Excluding these rows here is the
# second line of defence: even with correct calendar data, a week banner is
# not an event.
_WEEK_BANNER_EVENT_TYPES = (
    "committee_week",
    "group_week",
    "recess",
    "external_activities",
)

# Single source of truth for the exclusion, substituted into the calendar
# queries below. The values are module constants, never user input.
_EXCLUDE_WEEK_BANNERS = "AND event_type::text NOT IN ({})".format(
    ", ".join(f"'{t}'" for t in _WEEK_BANNER_EVENT_TYPES)
)


# Rank events by institutional weight so the morning briefing leads with the
# most significant thing happening, not whichever row the planner happened to
# return first. Without this, a plenary-session day led with a routine agency
# committee meeting purely because start_time was NULL on both.
_SIGNIFICANCE_ORDER = """
        CASE
            WHEN event_type::text IN (
                'plenary_session', 'european_council_summit',
                'commission_college_meeting', 'council_meeting', 'eurogroup'
            ) THEN 0
            -- Outreach and awareness events are demoted even when a DG runs
            -- them: a local beach clean-up is not the day's institutional
            -- headline just because its institution column says COMMISSION.
            WHEN event_type::text IN (
                'conference', 'webinar', 'roundtable', 'training', 'workshop'
            ) THEN 3
            WHEN institution IN (
                'EP', 'COMMISSION', 'COUNCIL', 'EUROPEAN_COUNCIL', 'ECB'
            ) THEN 1
            WHEN institution = 'THIRD_PARTY' THEN 4
            ELSE 2
        END ASC,
        start_time ASC NULLS LAST
"""


def _sql(query: str) -> str:
    """Substitute shared fragments into a calendar query.

    Uses str.replace rather than str.format because these queries contain
    literal ``%`` wildcards and ``:param`` placeholders that format() would
    either choke on or mangle.
    """
    return (
        query
        .replace("{exclude_week_banners}", _EXCLUDE_WEEK_BANNERS)
        .replace("{significance_order}", _SIGNIFICANCE_ORDER)
    )


def _briefing_morning(
    db: Session, user: User, today: date, lang: str = "en"
) -> Optional[ProactiveBriefing]:
    """
    Morning briefing — fires only if the user has not already had one today
    AND there is at least one meaningful signal to mention.
    """
    interests = _policy_interests(user)

    # Pull one calendar event for today. Always prefer real EU institutional
    # events (EP / COMMISSION / COUNCIL / EUROPEAN_COUNCIL / ECB / COR / etc.)
    # over THIRD_PARTY euagenda.eu listings, then prefer those that match the
    # user's policy interests.
    today_event = None
    try:
        if interests:
            row = (
                db.execute(
                    text(
                        _sql(
                            """
                        SELECT title, institution, source_url
                        FROM eu_calendar_events
                        WHERE start_date = :today
                          AND status != 'cancelled'
                          AND institution != 'THIRD_PARTY'
                          {exclude_week_banners}
                          AND EXISTS (
                      SELECT 1 FROM unnest(policy_areas) AS area_v
                      WHERE EXISTS (
                          SELECT 1 FROM unnest(CAST(:interests AS text[])) AS interest_v
                          WHERE LOWER(area_v) = LOWER(interest_v)
                             OR LOWER(area_v) LIKE '%' || LOWER(interest_v) || '%'
                             OR LOWER(interest_v) LIKE '%' || LOWER(area_v) || '%'
                      )
                  )
                        ORDER BY {significance_order}
                        LIMIT 1
                        """
                        )
                    ),
                    {"today": today, "interests": interests},
                )
                .mappings()
                .first()
            )
            today_event = row
        if not today_event:
            # Any real EU institutional event today.
            row = (
                db.execute(
                    text(
                        _sql(
                            """
                        SELECT title, institution, source_url
                        FROM eu_calendar_events
                        WHERE start_date = :today
                          AND status != 'cancelled'
                          AND institution != 'THIRD_PARTY'
                          {exclude_week_banners}
                        ORDER BY {significance_order}
                        LIMIT 1
                        """
                        )
                    ),
                    {"today": today},
                )
                .mappings()
                .first()
            )
            today_event = row
        if not today_event:
            # Final fallback: third-party Brussels events. Better than nothing.
            row = (
                db.execute(
                    text(
                        _sql(
                            """
                        SELECT title, institution, source_url
                        FROM eu_calendar_events
                        WHERE start_date = :today
                          AND status != 'cancelled'
                          {exclude_week_banners}
                        ORDER BY {significance_order}
                        LIMIT 1
                        """
                        )
                    ),
                    {"today": today},
                )
                .mappings()
                .first()
            )
            today_event = row
    except Exception as exc:
        logger.debug("morning_brief calendar query failed: %s", exc)
        db.rollback()
        today_event = None

    # Only emit a morning briefing if there's something real to say.
    if not today_event:
        return None

    institution = _humanise_institution(today_event.get("institution"), lang)
    event_title = str(today_event["title"]).strip()
    summary = _t(lang, "mb_summary").format(
        institution=institution, event_title=event_title
    )

    # The follow-through query matches what the panel actually said: ask
    # about the specific event, not a generic "what is on today's agenda".
    suggested_query = _t(lang, "mb_query").format(event_title=event_title)

    return ProactiveBriefing(
        trigger_source="morning_brief",
        title=_t(lang, "mb_title"),
        summary=summary,
        suggested_query=suggested_query,
        evidence_refs=[],
        drill_down_path="/my-eu-bubble?tab=eu_calendar",
    )


def _briefing_weekly_digest(
    db: Session, user: User, since: datetime, lang: str = "en"
) -> Optional[ProactiveBriefing]:
    """
    Synthesise a "while you were away" digest for users returning after a
    multi-day absence. Combines tracked-file movements, new files matching
    interests, and amendment surges across the gap window into one hook.

    Only fires when the gap is at least 5 days. The actual gap is encoded
    in the spoken summary so the user sees "Since Friday" or "Since 5 May"
    rather than a generic "this week".
    """
    if not since:
        return None
    now = datetime.now(since.tzinfo) if since.tzinfo else datetime.utcnow()
    gap_days = (now - since).days
    if gap_days < 5:
        return None

    interests = _policy_interests(user)
    moves = 0
    move_titles: List[str] = []
    new_matches = 0
    new_match_titles: List[str] = []
    surges = 0

    try:
        rows = db.execute(
            text(
                """
                SELECT lc.title, h.status, h.changed_at
                FROM user_carriage_tracks uct
                JOIN legislative_carriages lc ON lc.id = uct.carriage_id
                JOIN carriage_status_history h ON h.carriage_id = lc.id
                WHERE uct.user_id = :uid
                  AND h.changed_at > :since
                ORDER BY h.changed_at DESC
                LIMIT 10
                """
            ),
            {"uid": str(user.id), "since": since},
        ).mappings().all()
        moves = len(rows)
        move_titles = [r["title"] for r in rows[:3]]
    except Exception as exc:
        logger.debug("weekly_digest moves query failed: %s", exc)
        db.rollback()

    if interests:
        try:
            rows = db.execute(
                text(
                    """
                    SELECT title FROM legislative_carriages
                    WHERE first_seen > :since
                      AND EXISTS (
                          SELECT 1 FROM unnest(policy_areas) AS area_v
                          WHERE EXISTS (
                              SELECT 1 FROM unnest(CAST(:interests AS text[])) AS interest_v
                              WHERE LOWER(area_v) = LOWER(interest_v)
                                 OR LOWER(area_v) LIKE '%' || LOWER(interest_v) || '%'
                                 OR LOWER(interest_v) LIKE '%' || LOWER(area_v) || '%'
                          )
                      )
                    ORDER BY first_seen DESC
                    LIMIT 10
                    """
                ),
                {"since": since, "interests": interests},
            ).mappings().all()
            new_matches = len(rows)
            new_match_titles = [r["title"] for r in rows[:3]]
        except Exception as exc:
            logger.debug("weekly_digest new_files query failed: %s", exc)
            db.rollback()

    try:
        row = db.execute(
            text(
                """
                SELECT COUNT(*) AS surge_count
                FROM (
                    SELECT lc.id
                    FROM user_carriage_tracks uct
                    JOIN legislative_carriages lc ON lc.id = uct.carriage_id
                    JOIN mep_amendments ma
                      ON ma.procedure_reference = lc.oeil_procedure_ref
                    WHERE uct.user_id = :uid
                      AND ma.document_date > :since
                    GROUP BY lc.id
                    HAVING COUNT(ma.id) >= :threshold
                ) s
                """
            ),
            {
                "uid": str(user.id),
                "since": since,
                "threshold": AMENDMENT_SURGE_THRESHOLD,
            },
        ).first()
        surges = int(row[0]) if row and row[0] else 0
    except Exception as exc:
        logger.debug("weekly_digest surges query failed: %s", exc)
        db.rollback()

    if moves == 0 and new_matches == 0 and surges == 0:
        return None

    # Localised "since Friday" / "des de divendres" / "depuis le 5 mai"
    # anchor. Weekday and month names come from the template table, never
    # from strftime, so the anchor follows the user's language.
    if gap_days < 7:
        since_str = _t(lang, "wd_since_weekday").format(
            weekday=_t(lang, "weekdays")[since.weekday()]  # e.g. "Friday"
        )
    else:
        since_str = _t(lang, "wd_since_date").format(
            day=since.day,
            month=_t(lang, "months")[since.month - 1],  # e.g. "5 May"
        )

    parts: List[str] = []
    if moves:
        if moves == 1:
            parts.append(_t(lang, "wd_moves_one").format(title=move_titles[0]))
        else:
            parts.append(_t(lang, "wd_moves_many").format(count=moves))
    if new_matches:
        if new_matches == 1:
            parts.append(
                _t(lang, "wd_new_one").format(title=new_match_titles[0])
            )
        else:
            parts.append(_t(lang, "wd_new_many").format(count=new_matches))
    if surges:
        if surges == 1:
            parts.append(_t(lang, "wd_surge_one"))
        else:
            parts.append(_t(lang, "wd_surge_many").format(count=surges))

    body = "; ".join(parts) + "."
    summary = _t(lang, "wd_summary").format(since=since_str, body=body)

    return ProactiveBriefing(
        trigger_source="weekly_digest",
        title=_t(lang, "wd_title"),
        summary=summary,
        suggested_query=_t(lang, "wd_query").format(since=since_str),
        evidence_refs=[],
        drill_down_path="/my-eu-bubble?tab=my_files",
    )


def _briefing_conversation_recall(
    db: Session, user: User, lang: str = "en"
) -> Optional[ProactiveBriefing]:
    """
    Surface a hook for the user's most recent unfinished conversation
    when it was within the last 14 days but NOT today. The companion
    move that says "I remember what we were talking about last time".

    Skipped when the gap is less than 1 day (same-day chats do not need
    a recall hook) or more than 14 days (cold trail, would feel weird).
    """
    try:
        row = db.execute(
            text(
                """
                SELECT id, title, last_message_at
                FROM chats
                WHERE user_id = :uid
                  AND last_message_at IS NOT NULL
                  AND last_message_at::date < CURRENT_DATE
                  AND last_message_at > (NOW() - INTERVAL '14 days')
                  AND title IS NOT NULL
                  AND title != ''
                ORDER BY last_message_at DESC
                LIMIT 1
                """
            ),
            {"uid": str(user.id)},
        ).mappings().first()
    except Exception as exc:
        logger.debug("conversation_recall query failed: %s", exc)
        db.rollback()
        return None

    if not row:
        return None

    raw_title = str(row["title"]).strip().rstrip(".?!")
    topic = raw_title
    if len(topic) > 90:
        topic = topic[:87].rstrip() + "..."

    return ProactiveBriefing(
        trigger_source="conversation_recall",
        title=_t(lang, "cr_title"),
        summary=_t(lang, "cr_summary").format(topic=topic),
        suggested_query=_t(lang, "cr_query").format(topic=topic),
        evidence_refs=[str(row["id"])],
        drill_down_path=None,
    )


def _briefing_learn_about_you(
    db: Session, user: User, lang: str = "en"
) -> Optional[ProactiveBriefing]:
    """
    Fired only when Brubru has nothing else to say AND the user has not
    told it what they care about. Companion ask-to-learn move.
    """
    interests = _policy_interests(user)
    if interests:
        return None

    try:
        count = db.execute(
            text("SELECT COUNT(*) FROM user_carriage_tracks WHERE user_id = :uid"),
            {"uid": str(user.id)},
        ).scalar()
    except Exception as exc:
        logger.debug("learn_about_you count query failed: %s", exc)
        db.rollback()
        return None

    if count and int(count) > 0:
        return None

    return ProactiveBriefing(
        trigger_source="learn_about_you",
        title=_t(lang, "lay_title"),
        summary=_t(lang, "lay_summary"),
        suggested_query=_t(lang, "lay_query"),
        evidence_refs=[],
        drill_down_path="/profile",
    )


def compute_pending_briefings(
    db: Session,
    user: User,
    today: Optional[date] = None,
    previous_last_login: Optional[datetime] = None,
) -> List[ProactiveBriefing]:
    """
    Compute up to ``MAX_BRIEFINGS_PER_REQUEST`` briefings for the user.

    Priority order:
      1. weekly_digest      (only when previous_last_login gap is >= 5 days)
      2. amendment_surge    (last 24h on a tracked file)
      3. tracked_file_movement
      4. new_file_match
      5. conversation_recall
      6. morning_brief
      7. learn_about_you    (only when portfolio is empty)
    """
    if not user or not user.is_active:
        return []

    today = today or date.today()
    briefings: List[ProactiveBriefing] = []

    # Resolve the user's language once and thread it through every
    # generator. The suggested_query is later sent to Chat as the user's
    # message, so a Catalan suggested_query also makes Chat answer in
    # Catalan.
    lang = resolve_greeting_language(getattr(user, "language", None))

    fns = []
    if previous_last_login is not None:
        fns.append(
            lambda: _briefing_weekly_digest(db, user, previous_last_login, lang)
        )
    fns.extend([
        lambda: _briefing_amendment_surge(db, user, lang),
        lambda: _briefing_tracked_file_movement(db, user, lang),
        lambda: _briefing_new_file_match(db, user, lang),
        lambda: _briefing_conversation_recall(db, user, lang),
        lambda: _briefing_morning(db, user, today, lang),
        lambda: _briefing_learn_about_you(db, user, lang),
    ])

    for fn in fns:
        if len(briefings) >= MAX_BRIEFINGS_PER_REQUEST:
            break
        try:
            b = fn()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("proactive trigger evaluation failed: %s", exc)
            db.rollback()
            continue
        if b is not None:
            briefings.append(b)

    return briefings
