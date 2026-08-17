"""
AI Service Integration

EU context injection over the free open-model provider chain.
Part of Phase 13: AI Context Injection - Task 13.5

Features:
- Claude Sonnet/Opus integration
- EU context injection via ContextBuilder
- Streaming responses
- Conversation history management
- Source citation tracking
- Token usage monitoring
"""

import logging
import asyncio
import json
import os
import re
import base64
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncGenerator
from datetime import datetime
from dataclasses import dataclass

from .ai.context_builder import ContextBuilder, get_context_builder, SOURCE_TIERS, detect_drafting_intent
from .ai.multi_provider_service import MultiProviderService, get_multi_provider_service
from .ai.conversation_memory import get_conversation_memory_service
from .ai.action_router import compute_actions
from core.config import settings
from core.database import SessionLocal
from knowledge_base.ep_committees import EP_COMMITTEE_CODES
from models.knowledge_gap import KnowledgeGap, MissingDataType
from models.chat_analytics import ChatAnalytics

logger = logging.getLogger(__name__)

# Ambiguous all-caps tokens that must NEVER be auto-linked to a EUR-Lex CELEX by
# _linkify_legislation, even if present in legislation_acronyms.json. They collide
# with non-legislation meanings and produce hallucinated citations the response
# validator then correctly refuses (F-A, 5 June 2026). Roman numerals are handled
# separately by a regex. Keep this list short and all-uppercase.
# See memory/feedback_linkify_garbage_acronyms_fa.md.
_LINKIFY_ACRONYM_DENYLIST = frozenset({
    "ETF",   # EMA Emergency Task Force (not the Work-in-Fishing directive)
    "COVID-19", "COVID",  # disease names, not legislation (false-fire on every health answer)
    "ACT", "NEW", "API", "ART", "EOV", "SET", "END", "KEY", "ONE", "TWO",
    "AID", "AIR", "GAS", "NET", "USE", "WAR",
})

# Safe-by-default linkifier rule (11 June 2026). legislation_acronyms.json was
# bulk auto-ingested from Formex XML, and the ingestion mis-keyed popular names
# / acronyms onto IMPLEMENTING and DELEGATED instruments that merely *reference*
# the base act (the DSA -> 32023R1201 production bug; ~120 such rows: WEEE ->
# an implementing reg, UCITS -> a delegated reg, etc.). A popular acronym must
# never resolve to an implementing/delegated act, so _linkify_legislation (both
# the STEP 0 inline-correction map and STEP 2 bare-acronym pass) skips any entry
# whose full_title marks it as one. This neutralises the whole poisoned long
# tail at once, deterministically, without trusting each individual CELEX. Base
# acts and corrigenda (corrigendum CELEX == base CELEX) still linkify.
# See memory/feedback_linkify_override_celex.md.
_NON_BASE_ACT_MARKERS = ("Implementing ", "Delegated ")


def _is_linkify_safe_act(full_title: Optional[str]) -> bool:
    """False if the entry's full_title is an Implementing/Delegated act -- those
    are never the canonical target for a popular acronym and must not auto-link."""
    ft = full_title or ""
    return not any(marker in ft for marker in _NON_BASE_ACT_MARKERS)


# Internal context-block headers injected by context_builder.py (and named in the
# system prompt) that the model sometimes echoes back inside square brackets, e.g.
# "[COMMISSIONER AGENDA]". They are retrieval scaffolding, never a citation, and
# must be stripped before the answer reaches the user (audit defect D5, 28 Jul
# 2026 -- two leaks in one subscriber answer). Kept as an explicit allowlist so a
# legitimate bracketed phrase such as [AI ACT] is never touched. When a new
# ALL-CAPS section header is added to context_builder.py, add it here too.
_CONTEXT_BLOCK_LABELS = (
    "COMMISSIONER AGENDA",
    "COMMITTEE TRANSCRIPT",
    "EP PLENARY DEBATE TRANSCRIPT",
    "EP COMMITTEE WORK IN PROGRESS",
    "EP COMMITTEE MEETING MINUTES",
    "POSITION ANALYSIS",
    "AVAILABLE DATA FOR THIS FILE",
    "YOUR BRUBRU PROFILE",
    "USER UPLOADED DOCUMENTS",
    "USER PROFILE",
    "SUPPLEMENTARY DATABASE RESULTS",
    "REFERENCE DATA",
    "RECENT UPDATES",
    "LEGISLATIVE PROCEDURES",
    "LEGISLATIVE FILES",
    "LEGISLATION DETAILS",
    "INTERNAL KNOWLEDGE",
    "EUROPEAN COMMISSION PERSONNEL",
    "EU LAWS DATABASE",
    "EU INSTITUTIONAL SOURCES",
    "EU INSTITUTIONAL CALENDAR",
    "EU LAW SNAPSHOT",
    "EPRS RESEARCH & BRIEFINGS",
    "EPRS PUBLICATIONS",
    "EC PUBLIC CONSULTATIONS",
    "COMMITTEE INFORMATION",
    "COMMISSION DOCUMENTS",
    "CELLAR LEGISLATION",
    "CELLAR DISCOVERY",
    "DAILY NEWS",
    "BERESOL OPEN REPORTS & MONITORS",
)

# Matches any allowlisted label in brackets, with an optional "END " prefix and
# an optional " (live)" / " (2 days)" qualifier the headers carry.
_CONTEXT_BLOCK_LABEL_RE = re.compile(
    r"\s*\[\s*(?:END\s+)?(?:"
    + "|".join(re.escape(label) for label in _CONTEXT_BLOCK_LABELS)
    + r")(?:\s*\([^)\]]{0,30}\))?\s*\]",
    flags=re.IGNORECASE,
)

# The canonical product tree, in code so it can be enforced and not merely
# asked for. _build_system_prompt states this list in prose and
# _correct_invented_features rewrites anything that does not match, so a
# feature Brubru has not shipped cannot reach the user. A test asserts the
# prose and this tuple stay in agreement; when a tab is added or renamed,
# change it here and in the prompt in the same commit.
LANG_NAMES = {
    "EN": "English", "ES": "Spanish", "FR": "French",
    "IT": "Italian", "NL": "Dutch", "CA": "Catalan",
}

MEUB_SUBTABS = (
    "Overview", "Policy Interests", "My Documents", "News", "My Tracked Files",
    "My OJ", "Amendments", "Comparator", "Legislative Train: state of play",
    "Votes", "My EU Calendar", "Transcripts", "Council Watch", "MEP Watch",
    "Plenary Order of Business", "Parliamentary Questions",
    "EU Public Consultations", "Lobby Meetings", "Position Analysis",
    "Predictions", "Brubru Databases", "Research & Evidence",
    "Stakeholder Mapping", "Strategy Docs", "Tender Docs",
)
# The same sub-tabs as the UI actually renders them in Brubru's six languages,
# generated from frontend/src/i18n/locales/*.json (bubble.tabs plus the
# top-level bubble.* tab keys). The guard below needs these because the tab
# labels ARE translated: without them a correct Catalan answer naming "Els
# meus expedients en seguiment" would be rewritten as an invented feature,
# which is a worse failure than the one the guard exists to prevent. Regenerate
# alongside any locale change.
MEUB_SUBTAB_LOCALISED = (
    "Actualidad", "Actualitat", "Actualité", "Amendementen", "Amendements",
    "Amendments", "Analisi di posizione", "Analyse de position",
    "Anàlisi de posició", "Análisis de posición", "Bases de dades de Brubru",
    "Bases de datos de Brubru", "Bases de données Brubru",
    "Beleidsinteresses", "Brubru Databases", "Brubru-databanken",
    "Cartographie des acteurs", "Comparador", "Comparateur", "Comparator",
    "Comparatore", "Consultas Públicas de la UE",
    "Consultations Publiques de l'UE", "Consultazioni Pubbliche dell'UE",
    "Consultes Públiques de la UE", "Council Watch", "Database di Brubru",
    "Documenti di strategia", "Documentos de estrategia",
    "Documents d'estratègia", "Documents de stratégie", "EP-leden-monitor",
    "EU Openbare Raadplegingen", "EU Public Consultations", "El meu DOUE",
    "El meu calendari UE", "Els meus documents", "Els meus expedients",
    "Els meus expedients en seguiment", "Emendamenti", "Enmiendas",
    "Esmenes", "I miei documenti", "I miei fascicoli",
    "I miei fascicoli monitorati", "Il mio calendario UE",
    "Incontri di lobbying", "Intereses Políticos", "Interessi Politici",
    "Interessos Polítics", "Interrogazioni parlamentari",
    "Intérêts Politiques", "Investigación y evidencia", "La mia GU",
    "Legislative Tracker", "Legislative Train: state of play",
    "Lobby Meetings", "Lobbyontmoetingen", "MEP Watch", "Mapa d'actors",
    "Mapa de actores", "Mappa degli attori", "Mes documents", "Mes dossiers",
    "Mes dossiers suivis", "Mi DOUE", "Mi calendario UE", "Mijn EU-kalender",
    "Mijn PB", "Mijn documenten", "Mijn dossiers", "Mijn gevolgde dossiers",
    "Mis documentos", "Mis expedientes", "Mis expedientes en seguimiento",
    "Mon JO", "Mon calendrier UE", "Monitoraggio del Consiglio",
    "Monitoraggio eurodeputati", "My Documents", "My EU Calendar",
    "My Files", "My OJ", "My Tracked Files", "News", "Nieuws", "Notizie",
    "Onderzoek & bewijs", "Orden del día del Pleno",
    "Ordine del giorno della plenaria", "Ordre del dia del Ple",
    "Ordre du jour de la plénière", "Overview", "Overzicht", "Panoramica",
    "Parlementaire vragen", "Parliamentary Questions", "Plenaire agenda",
    "Plenary Order of Business", "Policy Interests", "Positie-analyse",
    "Position Analysis", "Predicciones", "Prediccions", "Predictions",
    "Preguntas parlamentarias", "Preguntes parlamentàries", "Previsioni",
    "Prédictions", "Questions parlementaires", "Raad-monitor",
    "Rastreador legislativo", "Rastrejador legislatiu",
    "Recerca i evidència", "Recherche et données probantes",
    "Research & Evidence", "Resum", "Resumen", "Reuniones de lobby",
    "Reunions de lobby", "Ricerca ed evidenze", "Réunions de lobbying",
    "Seguiment d'eurodiputats", "Seguiment del Consell",
    "Seguimiento de eurodiputados", "Seguimiento del Consejo",
    "Stakeholder Mapping", "Stakeholderkaart", "Stemmingen",
    "Strategie­documenten", "Strategy Docs", "Suivi des députés",
    "Suivi du Conseil", "Tender Docs", "Tracker legislativo",
    "Tracker législatif", "Train législatif", "Transcripciones",
    "Transcripcions", "Transcripties", "Transcriptions", "Transcripts",
    "Trascrizioni", "Tren legislatiu", "Tren legislativo",
    "Treno legislativo", "Vergelijker", "Voorspellingen", "Votaciones",
    "Votacions", "Votazioni", "Votes", "Vue d'ensemble", "Wetgevingstracker",
    "Wetgevingstrein",
)

BRUBRU_PRODUCTS = (
    "My EU Bubble", "Amendator", "Chat", "EU Law Comply", "Tenderator", "API",
)

# Safe-refusal template in Brubru's six languages (audit defect D3, 28 Jul 2026).
# Previously English-only, so a Catalan or Spanish user who tripped the validator
# guard received an English wall. British English is the EN base. No em-dashes.
_SAFE_REFUSAL_TEXT = {
    "EN": {
        "lead": "I cannot answer that with confidence from Brubru's verified record.",
        "user_claim": (
            "Your question asserts a specific role for a named person on a procedure that "
            "Brubru's record does not currently confirm. I will not validate that assertion "
            "from training-data memory."
        ),
        "meeting": (
            "I also cannot confirm any specific meeting between a named person and a "
            "Commission service on the date you mention. That meeting is not in Brubru's "
            "calendar, Transparency Register snapshot, or press-release feed."
        ),
        "future_date": (
            "Specific future committee or plenary vote dates for this file are not in "
            "Brubru's calendar yet."
        ),
        "hallucination": (
            "The initial draft of my answer included specific names, quotes, or numbers "
            "that I could not verify against Brubru's retrieved sources."
        ),
        "completeness": (
            "My initial answer omitted items that Brubru does have on record. I would rather "
            "stop and offer to deliver the full list than ship an incomplete one."
        ),
        "on_record": "What Brubru does hold on this topic: {items}. Ask me about any of those and I will answer from the record.",
        "offer": (
            "What I can offer: track this file in My Tracked Files (My EU Bubble) "
            "so Brubru pings you the moment the rapporteur, lead committee, "
            "or vote date is recorded. I can also pull the Commission proposal text, the EPRS "
            "briefing, and any calendar events that ARE on file. Ask me for any of those."
        ),
    },
    "FR": {
        "lead": "Je ne peux pas répondre à cela avec certitude à partir des sources vérifiées de Brubru.",
        "user_claim": (
            "Votre question attribue un rôle précis à une personne nommée sur une procédure que "
            "les données de Brubru ne confirment pas actuellement. Je ne validerai pas cette "
            "affirmation de mémoire."
        ),
        "meeting": (
            "Je ne peux pas non plus confirmer une réunion entre une personne nommée et un "
            "service de la Commission à la date que vous mentionnez. Cette réunion ne figure ni "
            "dans le calendrier de Brubru, ni dans le registre de transparence, ni dans le flux "
            "de communiqués."
        ),
        "future_date": (
            "Les dates précises de vote en commission ou en plénière pour ce dossier ne figurent "
            "pas encore dans le calendrier de Brubru."
        ),
        "hallucination": (
            "Le premier brouillon de ma réponse contenait des noms, des citations ou des chiffres "
            "que je n'ai pas pu vérifier dans les sources récupérées par Brubru."
        ),
        "completeness": (
            "Ma réponse initiale omettait des éléments que Brubru possède pourtant. Je préfère "
            "m'arrêter et vous proposer la liste complète plutôt que d'en livrer une incomplète."
        ),
        "on_record": "Ce que Brubru possède sur ce sujet : {items}. Interrogez-moi sur l'un de ces points et je répondrai à partir des sources.",
        "offer": (
            "Ce que je peux faire : suivez ce dossier dans My Tracked Files (My EU Bubble) "
            "pour que Brubru vous alerte dès que le rapporteur, la commission "
            "compétente ou la date de vote sont enregistrés. Je peux aussi vous fournir le texte de "
            "la proposition de la Commission, la note de l'EPRS et les événements de calendrier "
            "déjà disponibles. Demandez-les moi."
        ),
    },
    "ES": {
        "lead": "No puedo responder a eso con seguridad a partir de las fuentes verificadas de Brubru.",
        "user_claim": (
            "Su pregunta atribuye un papel concreto a una persona identificada en un procedimiento "
            "que los datos de Brubru no confirman actualmente. No voy a validar esa afirmación de memoria."
        ),
        "meeting": (
            "Tampoco puedo confirmar ninguna reunión entre una persona identificada y un servicio "
            "de la Comisión en la fecha que menciona. Esa reunión no consta en el calendario de "
            "Brubru, ni en el registro de transparencia, ni en el flujo de notas de prensa."
        ),
        "future_date": (
            "Las fechas concretas de votación en comisión o en pleno para este expediente todavía "
            "no constan en el calendario de Brubru."
        ),
        "hallucination": (
            "El primer borrador de mi respuesta incluía nombres, citas o cifras que no pude "
            "verificar con las fuentes recuperadas por Brubru."
        ),
        "completeness": (
            "Mi respuesta inicial omitía elementos que Brubru sí tiene registrados. Prefiero "
            "detenerme y ofrecerle la lista completa antes que entregarle una incompleta."
        ),
        "on_record": "Lo que Brubru sí tiene sobre este tema: {items}. Pregúnteme por cualquiera de ellos y le responderé a partir de las fuentes.",
        "offer": (
            "Lo que sí puedo ofrecerle: siga este expediente en My Tracked Files (My EU Bubble) "
            "para que Brubru le avise en cuanto se registren el ponente, la "
            "comisión competente o la fecha de votación. También puedo facilitarle el texto de la "
            "propuesta de la Comisión, la nota del EPRS y los eventos de calendario que sí constan. "
            "Pídame cualquiera de ellos."
        ),
    },
    "CA": {
        "lead": "No puc respondre això amb seguretat a partir de les fonts verificades de Brubru.",
        "user_claim": (
            "La vostra pregunta atribueix un paper concret a una persona identificada en un "
            "procediment que les dades de Brubru no confirmen actualment. No validaré aquesta "
            "afirmació de memòria."
        ),
        "meeting": (
            "Tampoc no puc confirmar cap reunió entre una persona identificada i un servei de la "
            "Comissió en la data que esmenteu. Aquesta reunió no consta al calendari de Brubru, "
            "ni al registre de transparència, ni al flux de notes de premsa."
        ),
        "future_date": (
            "Les dates concretes de votació en comissió o en ple per a aquest expedient encara no "
            "consten al calendari de Brubru."
        ),
        "hallucination": (
            "El primer esborrany de la meva resposta incloïa noms, citacions o xifres que no vaig "
            "poder verificar amb les fonts recuperades per Brubru."
        ),
        "completeness": (
            "La meva resposta inicial ometia elements que Brubru sí que té registrats. Prefereixo "
            "aturar-me i oferir-vos la llista completa abans que lliurar-ne una d'incompleta."
        ),
        "on_record": "El que Brubru sí que té sobre aquest tema: {items}. Pregunteu-me per qualsevol d'aquests punts i us respondré a partir de les fonts.",
        "offer": (
            "El que sí que us puc oferir: seguiu aquest expedient a My Tracked Files "
            "(My EU Bubble) perquè Brubru us avisi tan bon punt es registrin "
            "el ponent, la comissió competent o la data de votació. També us puc facilitar el text "
            "de la proposta de la Comissió, la nota de l'EPRS i els esdeveniments de calendari que "
            "sí que consten. Demaneu-me'n qualsevol."
        ),
    },
    "IT": {
        "lead": "Non posso rispondere con certezza sulla base delle fonti verificate di Brubru.",
        "user_claim": (
            "La sua domanda attribuisce un ruolo preciso a una persona indicata in una procedura "
            "che i dati di Brubru al momento non confermano. Non convaliderò tale affermazione a memoria."
        ),
        "meeting": (
            "Non posso nemmeno confermare alcun incontro tra una persona indicata e un servizio "
            "della Commissione nella data che lei menziona. Quell'incontro non figura nel "
            "calendario di Brubru, né nel registro per la trasparenza, né nel flusso dei comunicati."
        ),
        "future_date": (
            "Le date precise di voto in commissione o in plenaria per questo fascicolo non sono "
            "ancora nel calendario di Brubru."
        ),
        "hallucination": (
            "La prima bozza della mia risposta conteneva nomi, citazioni o cifre che non ho potuto "
            "verificare con le fonti recuperate da Brubru."
        ),
        "completeness": (
            "La mia risposta iniziale ometteva elementi che Brubru ha invece in archivio. Preferisco "
            "fermarmi e offrirle l'elenco completo piuttosto che consegnarne uno incompleto."
        ),
        "on_record": "Ciò che Brubru ha su questo tema: {items}. Mi chieda di uno qualsiasi di questi e risponderò sulla base delle fonti.",
        "offer": (
            "Quello che posso offrirle: segua questo fascicolo in My Tracked Files "
            "(My EU Bubble) così Brubru la avvisa non appena vengono registrati "
            "il relatore, la commissione competente o la data di voto. Posso anche fornirle il testo "
            "della proposta della Commissione, la nota dell'EPRS e gli eventi di calendario già "
            "disponibili. Me li chieda pure."
        ),
    },
    "NL": {
        "lead": "Ik kan dat niet met zekerheid beantwoorden op basis van de geverifieerde bronnen van Brubru.",
        "user_claim": (
            "Uw vraag kent een specifieke rol toe aan een genoemde persoon in een procedure die de "
            "gegevens van Brubru op dit moment niet bevestigen. Ik ga die bewering niet uit het "
            "geheugen bevestigen."
        ),
        "meeting": (
            "Ik kan evenmin een ontmoeting bevestigen tussen een genoemde persoon en een dienst van "
            "de Commissie op de datum die u noemt. Die ontmoeting staat niet in de agenda van "
            "Brubru, niet in het transparantieregister en niet in de persberichtenstroom."
        ),
        "future_date": (
            "Concrete toekomstige stemmingsdata in commissie of plenaire vergadering voor dit "
            "dossier staan nog niet in de agenda van Brubru."
        ),
        "hallucination": (
            "De eerste versie van mijn antwoord bevatte namen, citaten of cijfers die ik niet kon "
            "verifiëren aan de hand van de door Brubru opgehaalde bronnen."
        ),
        "completeness": (
            "Mijn eerste antwoord liet onderdelen weg die Brubru wél in het bestand heeft. Ik stop "
            "liever en bied u de volledige lijst aan dan een onvolledige te leveren."
        ),
        "on_record": "Wat Brubru wél over dit onderwerp heeft: {items}. Vraag mij naar een daarvan en ik antwoord op basis van de bronnen.",
        "offer": (
            "Wat ik wel kan doen: volg dit dossier in My Tracked Files (My EU Bubble), "
            "dan waarschuwt Brubru u zodra de rapporteur, de bevoegde commissie "
            "of de stemdatum wordt vastgelegd. Ik kan ook de tekst van het Commissievoorstel, de "
            "EPRS-nota en de reeds bekende agendapunten ophalen. Vraag er gerust naar."
        ),
    },
}


# ---------------------------------------------------------------------------
# Hosts whose markdown links survive post-processing: the official EU domains
# plus Brubru's own surfaces. Everything else the model invents is flattened to
# plain text, because an invented URL is worse than no URL. Deliberately
# host-anchored (after :// or a dot) so "noteur-lex.example.com" cannot pass.
_TRUSTED_LINK_HOST_RE = re.compile(
    r"https?://(?:[a-z0-9-]+\.)*"
    r"(?:europa\.eu|europarl\.europa\.eu|brubru\.beresol\.eu|beresol\.eu)"
    r"(?:[/?#]|$)",
    re.IGNORECASE,
)

# Quality signal regexes (Playbook D: structured logging)
# Kept at module level so the same patterns are used in ai_service runtime
# and in scripts/eval_quality.py for consistency.
# ---------------------------------------------------------------------------
_LEGAL_ANCHOR_RE = re.compile(
    r"\b[0-9]{5}[A-Z][0-9]{4}\b"                # CELEX (e.g. 32024R1689)
    r"|COM\s*\(\d{4}\)\s*\d+"                   # COM(2023)533
    r"|\d{4}/\d{4}\((?:COD|NLE|APP|CNS|INI|INL|RSP|RPS|BUD)\)",  # procedure ref
    re.IGNORECASE,
)

# Deflection = telling the user to go and look it up themselves. The user came
# to Brubru precisely to avoid that.
#
# This used to match EUR-Lex only, so "you would typically consult the
# individual committee pages on the European Parliament's website" sailed
# through and shipped to a subscriber on 20 July 2026. The sources users are
# deflected to are institutional generally, not just EUR-Lex.
_DEFLECTION_RE = re.compile(
    r"search\s+EUR-Lex|check\s+EUR-Lex|visit\s+EUR-Lex"
    r"|consult\s+EUR-Lex\s+yourself"
    r"|you\s+(?:can|should|may)\s+(?:search|check|visit|consult)\s+EUR-Lex"
    # Generic "go look it yourself" pointed at any EU institutional source.
    r"|(?:you\s+(?:can|should|may|would)|it\s+is\s+best\s+to|please)"
    r"[^.\n]{0,40}?"
    r"(?:search|check|visit|consult|refer\s+to|look\s+at)"
    r"[^.\n]{0,60}?"
    r"(?:European\s+Parliament(?:'s)?\s+website|EP\s+website"
    r"|committee\s+pages?|Commission(?:'s)?\s+website|Council(?:'s)?\s+website"
    r"|OEIL|Europa\.eu|official\s+website)"
    # "you would typically consult X" phrasing, which is the same deflection
    # dressed as description.
    r"|you\s+would\s+(?:typically|normally|usually)\s+"
    r"(?:consult|check|search|refer\s+to|look\s+at)",
    re.IGNORECASE,
)

_DONT_HAVE_RE = re.compile(
    r"I\s+don'?t\s+have\s+access\s+to"
    r"|I\s+don'?t\s+have\s+the\s+(?:specific\s+)?text"
    r"|I\s+cannot\s+access"
    r"|I\s+am\s+unable\s+to\s+access",
    re.IGNORECASE,
)

# Fix A (11 June 2026): deterministic risk pre-filter for the response validator.
# The LLM validator is a SECOND provider call per chat (the measured concurrency
# doubler — see memory/query_audit.md). It only earns its cost when the answer
# contains a CHECKABLE-FABRICATION surface the linkifier can't police: a named
# person given a role, a PE/A/T identifier, a vote tally, a fabricated meeting, a
# fine figure, or an outlet-attributed quote. (Bare CELEX no longer needs it —
# the de-poisoned linkifier + safe-by-default rule handle CELEX deterministically.)
# Low-risk answers (definitions, mechanism explanations, procedural how-tos) have
# no such surface and skip the validator => 1 provider call instead of 2.
_VALIDATE_TRIGGER_RE = re.compile(
    r"\bPE[\s\-]?\d{3,}"                                   # PE working-doc numbers
    r"|\b[ABT]\d{1,2}[\s\-]?\d{3,4}/\d{4}\b"               # A-/B-/T- report/resolution refs
    r"|\bP\d{1,2}_TA\b"                                    # adopted-text refs
    r"|\b\d{2,3}\s*(?:votes?|in\s+favou?r|against|abstentions?)\b"   # vote tally words
    r"|\b\d{2,3}\s*[-–/]\s*\d{2,3}\s*[-–/]\s*\d{1,3}\b"    # tally like 228-311-92
    r"|\bmet\s+with\b|\bmeeting\s+with\b"                  # fabricated meeting
    r"|€\s?\d[\d.,]*\s*(?:million|billion|bn|m)\b"         # fine / figure
    r"|\b(?:Politico|Reuters|Bloomberg|Euractiv|Contexte|Financial\s+Times|Bruegel)\b"  # outlet attribution
    r"|\btrilogue\b",
    re.IGNORECASE,
)
_NAMED_ROLE_RE = re.compile(
    r"rapporteur|shadow|ponente|relator[ei]|berichterstatter|coordinator|lead\s+negotiator",
    re.IGNORECASE,
)
_CAP_NAME_RE = re.compile(r"\b[A-ZÀ-Þ][a-zà-ÿ]+\s+[A-ZÀ-Þ][A-Za-zÀ-ÿ'\-]+")  # First Last


def _response_needs_validation(response: str) -> bool:
    """True if the response has a checkable-fabrication surface worth the second
    (validator) provider call. False for low-risk answers -> skip the validator."""
    if not response:
        return False
    if _VALIDATE_TRIGGER_RE.search(response):
        return True
    # A role claim is risky only when a specific name is attached.
    if _NAMED_ROLE_RE.search(response) and _CAP_NAME_RE.search(response):
        return True
    return False


# Fix B (11 June 2026): greeting / identity short-circuit. A "hi" or "who are
# you" needs no KB context and no LLM call -- it ran the full ~14K-prompt
# pipeline + a provider call, wasting both latency and scarce free-tier provider
# capacity under load. Detect a WHOLE-message greeting (anchored, so "hello, what
# is the AI Act?" is NOT caught) and return a templated localized intro directly.
# A greeting may chain several greeting phrases ("hola, qui ets?", "hi, who are
# you?"), so the message must be COMPOSED of one-or-more greeting tokens separated
# by spaces/punctuation -- not a single token. Anchored so "what is the AI Act?"
# (real query) is never caught.
_GREET_TOKEN = (
    r"(?:hi|hello|hey|hiya|yo|greetings|good\s+(?:morning|afternoon|evening)|howdy"
    r"|hola|buenas|buenos\s+d[ií]as|quien\s+eres|qui[eé]n\s+eres|qu[eé]\s+eres"
    r"|bon\s?dia|bona\s+tarda|qui\s+ets|ets\s+un\s+bot|que\s+pots\s+fer"
    r"|ciao|salve|buongiorno|chi\s+sei|cosa\s+sai\s+fare"
    r"|bonjour|salut|coucou|qui\s+es[\s\-]?tu|qui\s+est[\s\-]?tu|que\s+sais[\s\-]?tu\s+faire"
    r"|hallo|hoi|goedemorgen|wie\s+ben\s+je|wat\s+kun\s+je"
    r"|who\s+are\s+you|what\s+are\s+you|what\s+can\s+you\s+do|who\s+r\s+u|what'?s\s+brubru|what\s+is\s+brubru)"
)
_GREETING_RE = re.compile(r"^\s*(?:" + _GREET_TOKEN + r"[\s,!?.¿¡y]*)+$", re.IGNORECASE)
_GREETING_LANG = [
    (re.compile(r"\b(qui\s+ets|bon\s?dia|bona\s+tarda|ets\s+un\s+bot)\b", re.IGNORECASE), "ca"),
    (re.compile(r"\b(hola|buenas|buenos|qui[eé]n\s+eres|qu[eé]\s+eres)\b", re.IGNORECASE), "es"),
    (re.compile(r"\b(ciao|salve|buongiorno|chi\s+sei)\b", re.IGNORECASE), "it"),
    (re.compile(r"\b(bonjour|salut|coucou|qui\s+es[\s\-]?tu|qui\s+est)\b", re.IGNORECASE), "fr"),
    (re.compile(r"\b(hallo|hoi|goedemorgen|wie\s+ben\s+je)\b", re.IGNORECASE), "nl"),
]
_GREETING_REPLIES = {
    "en": "Hello! I'm Brubru, your AI assistant for EU legislative affairs. I can help you understand EU legislation, track procedures, find MEPs and committees, draft amendments, and analyse policy. What would you like to explore?",
    "es": "¡Hola! Soy Brubru, tu asistente de IA para asuntos legislativos de la UE. Puedo ayudarte a entender la legislación europea, seguir procedimientos, encontrar eurodiputados y comisiones, redactar enmiendas y analizar políticas. ¿Qué te gustaría explorar?",
    "ca": "Hola! Sóc Brubru, el teu assistent d'IA per als afers legislatius de la UE. Et puc ajudar a entendre la legislació europea, seguir procediments, trobar eurodiputats i comissions, redactar esmenes i analitzar polítiques. Què t'agradaria explorar?",
    "fr": "Bonjour! Je suis Brubru, votre assistant IA pour les affaires législatives de l'UE. Je peux vous aider à comprendre la législation européenne, suivre les procédures, trouver des députés et des commissions, rédiger des amendements et analyser les politiques. Que souhaitez-vous explorer?",
    "it": "Ciao! Sono Brubru, il tuo assistente IA per gli affari legislativi dell'UE. Posso aiutarti a capire la legislazione europea, seguire le procedure, trovare eurodeputati e commissioni, redigere emendamenti e analizzare le politiche. Cosa vorresti esplorare?",
    "nl": "Hallo! Ik ben Brubru, je AI-assistent voor EU-wetgevingszaken. Ik kan je helpen EU-wetgeving te begrijpen, procedures te volgen, Europarlementariërs en commissies te vinden, amendementen op te stellen en beleid te analyseren. Wat wil je verkennen?",
}


def _greeting_response(user_message: str) -> Optional[str]:
    """Return a templated localized intro if the WHOLE message is a greeting /
    identity question, else None. No context-build, no LLM call."""
    if not user_message or not _GREETING_RE.match(user_message.strip()):
        return None
    lang = "en"
    for rx, lg in _GREETING_LANG:
        if rx.search(user_message):
            lang = lg
            break
    return _GREETING_REPLIES.get(lang, _GREETING_REPLIES["en"])

# Lightweight language markers for query/response language detection.
# Matches eval_quality.py so runtime and offline scoring agree.
_LANG_MARKERS = {
    # English carries interrogatives and auxiliaries as well as articles. With
    # only the ten function words, a short question could match NOTHING in
    # English while matching one word in another language and losing outright:
    # "Which lobbyists met MEPs about procedure 2023/0448(COD)?" scored 0 for EN
    # and 1 for NL, because English "met" is also Dutch for "with", and the
    # answer came back in Dutch. Every word added here is absent from the other
    # five Brubru languages after accent folding ("on" and "no" are excluded
    # precisely because they are not).
    "EN": {"the", "and", "of", "is", "for", "in", "to", "with", "this", "that",
           "which", "what", "who", "how", "when", "where", "why", "about",
           "are", "was", "does", "do", "can", "has", "have", "from", "at",
           "not", "but", "would", "should", "there", "their", "been"},
    "FR": {"le", "la", "les", "des", "une", "est", "dans", "pour", "avec", "cette"},
    "ES": {"el", "la", "los", "las", "una", "del", "por", "con", "esta", "para"},
    "CA": {"el", "la", "els", "les", "una", "del", "per", "amb", "aquesta", "dels"},
    "IT": {"il", "la", "le", "dei", "una", "del", "per", "con", "questa", "nella"},
    "NL": {"de", "het", "een", "van", "voor", "met", "die", "dat", "deze", "wordt"},
}

# Catalan-exclusive tokens, accent-folded. Any single hit settles the language,
# the same way the interpunct rule does below.
#
# Why this exists (audit, 5 Aug 2026): the CA marker set above is 10 function
# words, and a real Catalan query can contain NONE of them. "Quina normativa
# catalana i espanyola de residus textils s'ha d'aplicar a un projecte pilot de
# reciclatge d'uniformes municipals?" scored **NL**, because its only marker
# hits were "de" twice and "de" lives in the Dutch set. The CA-versus-ES
# tie-break further down could not rescue it either, because that block only
# runs once CA already scores above zero. Chicken and egg.
#
# Membership rule: a token qualifies only if it cannot appear in EN, ES, FR, IT
# or NL after accent folding. Deliberately EXCLUDED, and why:
#   "i"      folds onto the English pronoun "I", which would break EN queries
#   "pero"   CA "pero" with a grave accent folds onto ES "pero"
#   "son"    shared with ES and FR
#   "esta"   CA "esta" with a grave accent folds onto ES "esta"
#   "un", "sobre", "normativa"  shared with ES, FR or IT
_CA_DECISIVE = frozenset({
    # determiners, pronouns and connectors with no cross-language collision
    "amb", "aquest", "aquests", "aquesta", "aquestes", "aixo", "perque",
    "quin", "quina", "quins", "quines", "seva", "seves", "meva", "nostra",
    "fins", "tambe", "molt", "molts", "moltes", "nomes", "aquell", "aquella",
    "dins", "tots", "totes", "altres", "qualsevol",
    # domain nouns whose Spanish form differs after folding
    "residus", "recollida", "malbaratament", "envasos", "llei", "lleis",
    "expedient", "expedients", "termini", "terminis", "empreses",
    "obligacions", "reglament", "estats",
    # verb forms
    "tindra", "tindran", "hauran", "haura", "poden", "podra",
    "estableix", "aplicar", "seguir", "complir",
    # EU-work nouns whose Spanish form differs after folding: ES uses
    # "ponente" / "enmienda", so these are Catalan-only in practice.
    "ponent", "ponents", "esmena", "esmenes",
    # Interrogatives and product/data vocabulary. Added 12 Aug 2026: a Catalan
    # subscriber asking "Quan va entrar en funcionament el registre del
    # passaport digital de producte?" scored ES and was answered in Spanish,
    # and "Quantes dades ha de portar el passaport de bateries?" scored NL,
    # because not one word of either sentence was in this set. ES writes
    # cuando / cuantas / funcionamiento / pasaporte / producto / datos /
    # textiles, so every token here differs after folding.
    # Deliberately EXCLUDED, having been considered:
    #   "registre", "normes", "actes"  are French words
    #   "creen"    is Spanish for "they believe"
    #   "com"      appears inside .com domains
    #   "entrar", "vigor"  are shared with Spanish
    "quan", "quants", "quantes", "funcionament", "passaport",
    "producte", "productes", "dades", "textils", "seguiment", "dret",
    "soc", "som", "sou", "ets", "escric", "voldria", "podriem",
    # -cio nouns: the Catalan singular folds to "-cio" where Spanish folds to
    # "-cion" and French keeps "-tion". Listed explicitly rather than matched by
    # suffix, because a bare "acio" suffix test would also catch the Spanish
    # "espacio", "palacio" and "prefacio".
    "relacio", "informacio", "gestio", "situacio", "aplicacio", "obligacio",
    "regulacio", "adaptacio", "transposicio", "recollicio", "reutilitzacio",
})

# Catalan plural of the -cio nouns. "-cions" has no counterpart in the other
# five Brubru languages: Spanish forms "-ciones", Italian "-zioni", French
# "-tions". Safe as a suffix test where the singular is not.
_CA_DECISIVE_SUFFIX = ("cions",)

# Italian-exclusive tokens, accent-folded, same contract as _CA_DECISIVE: none
# of these collide with the EN/FR/ES/CA/NL forms after folding.
#
# Why this exists (training run, 6 Aug 2026): IT had a 10-word marker set and
# no decisive list, so four real Italian queries out of eight were misread.
# "Ci sono fondi europei per l'Albania?" matched only "per", which is in BOTH
# the CA and IT sets, producing an exact tie that fell to Catalan purely
# because CA is declared before IT in _LANG_MARKERS. "credo che tutti questi
# aspetti vadano approfonditi" matched nothing at all and defaulted to English.
_IT_DECISIVE = frozenset({
    # articles and prepositions with no cross-language collision after folding
    "il", "lo", "gli", "dei", "degli", "delle", "della", "dello", "dell",
    "nel", "nella", "nelle", "negli", "sul", "sulla", "sulle", "sui",
    "dal", "dalla", "col", "coi", "agli", "alle", "allo",
    # pronouns, determiners, connectors
    # "quelle" is deliberately absent: it is Italian AND French ("quelle est
    # la position...") and stole a French query the moment it was added.
    "che", "chi", "questi", "questo", "quella", "quello", "quali",
    "anche", "perche", "molto", "molti", "tutti", "tutte", "tuoi", "tue",
    "loro", "essi", "cui", "oltre", "invece", "ancora", "sempre",
    # verb forms
    "sono", "essere", "viene", "vengono", "prevede", "riguarda", "vorrei",
    "puo", "possono", "deve", "devono", "vadano", "esprimi", "cerco",
    # nouns/adjectives whose Spanish or Catalan form differs after folding
    "finanziamenti", "fondi", "approfondite", "approfonditi", "generiche",
    "tramite", "piattaforme", "aspetti", "premesse", "difesa",
})


def _detect_query_language(text: str) -> str:
    """
    Cheap bag-of-words language detector. Returns two-letter upper-case code.
    Defaults to EN when signal is too weak.
    """
    if not text:
        return "EN"

    # The interpunct (U+00B7, as in "sol.licitud", "Brussel.les") is Catalan
    # orthography and appears in no other Brubru language. Decisive on its own,
    # and it fires on short queries where the bag-of-words detector has no
    # signal at all. Added 28 Jul 2026 (audit defect D7): a Catalan
    # subscriber's query scored ES, because every function word it used ("la",
    # "el", "de", "es") is shared with Spanish and none of the CA-only
    # tie-break words appeared.
    if "·" in text:
        return "CA"

    # Inverted punctuation is Spanish orthography and appears in no other
    # Brubru language, so it is decisive in the same way the interpunct is for
    # Catalan. Without it "¿Qué establece la Directiva de la UE sobre salarios
    # mínimos adecuados?" scored FR and ES dead level (both matched only "la"),
    # and the tie fell to FR purely because FR is declared first in
    # _LANG_MARKERS. The user asked in Spanish and was answered in French.
    if "¿" in text or "¡" in text:
        return "ES"

    # Fold diacritics once, so the marker sets below stay pure ASCII and the
    # detector is not defeated by a user typing "perque" for "perqu<e-grave>".
    folded = "".join(
        ch for ch in unicodedata.normalize("NFD", text.lower())
        if unicodedata.category(ch) != "Mn"
    )
    words = re.findall(r"\b\w+\b", folded)
    if not words:
        return "EN"

    # Catalan-exclusive token, decisive on its own. Runs BEFORE scoring, because
    # the bag-of-words pass can hand a Catalan query to Dutch on the strength of
    # "de" alone (audit, 5 Aug 2026). See _CA_DECISIVE for the exclusion rules.
    # Short decisive tokens collide with EU acronyms, which are written in
    # capitals. "ETS" (Emissions Trading System) folds to "ets", which is
    # Catalan for "you are", so "What is procedure 2026/0211(COD) on ETS heat
    # and fuel benchmark values?" was detected as Catalan and answered entirely
    # in Catalan. An acronym in capitals is never the Catalan word, so a token
    # of three characters or fewer only counts when the user actually wrote it
    # in lower case.
    raw_words = re.findall(r"\b\w+\b", text)
    _acronyms = {w.lower() for w in raw_words if len(w) <= 3 and w.isupper()}

    def _decisive(w: str, table) -> bool:
        if w in _acronyms:
            return False
        return w in table

    _ca_hits = sum(1 for w in words if _decisive(w, _CA_DECISIVE)) + sum(
        1 for w in words if w.endswith(_CA_DECISIVE_SUFFIX)
    )
    _it_hits = sum(1 for w in words if _decisive(w, _IT_DECISIVE))
    # Compared rather than short-circuited: an Italian sentence can clip a
    # single word from the Catalan list, and returning on first hit handed it
    # to Catalan outright.
    if _ca_hits or _it_hits:
        if _ca_hits > _it_hits:
            return "CA"
        if _it_hits > _ca_hits:
            return "IT"

    scores = {lang: sum(1 for w in words if w in markers) / len(words)
              for lang, markers in _LANG_MARKERS.items()}
    # CA/ES disambiguation
    if scores.get("CA", 0) > 0 and scores.get("ES", 0) > 0:
        # Accent-folded and CA-exclusive. Deliberately excludes words that fold
        # onto a Spanish form: CA "esta<grave>" folds to "esta" (= ES "esta"),
        # and "pero"/"son" are common in both, so none of those may arbitrate.
        ca_only = {
            "amb", "aquesta", "aquest", "aquests", "aquestes", "dels", "pel",
            "als", "perque", "aixo", "quin", "quina", "quins", "quines",
            "hi", "seva", "meva", "nostra", "fins", "troba", "llengua",
            "ponent", "ponents", "esmena", "esmenes", "dossiers",
        }
        es_only = {"con", "por", "tambien", "porque", "asi",
                   "solicitud", "cual", "donde"}
        ca = sum(1 for w in words if w in ca_only)
        es = sum(1 for w in words if w in es_only)
        if ca > es:
            scores["CA"] += 0.05
        elif es > ca:
            scores["ES"] += 0.05
    # IT/ES disambiguation (many shared words: la, una, del, con)
    if scores.get("IT", 0) > 0 and scores.get("ES", 0) > 0:
        it_only = {"il", "lo", "gli", "dei", "degli", "delle", "della",
                   "nella", "nel", "sulla", "questa", "questo", "anche",
                   "perche", "cosi", "sempre"}
        es_only_vs_it = {"el", "los", "las", "por", "esta", "para",
                         "tambien", "porque", "asi", "cada", "siempre"}
        it = sum(1 for w in words if w in it_only)
        es = sum(1 for w in words if w in es_only_vs_it)
        if it > es:
            scores["IT"] += 0.05
        elif es > it:
            scores["ES"] += 0.05
    # FR/ES disambiguation. These two share "la", "de" and "una"/"une"-shaped
    # function words, and a query carrying nothing else scored an exact tie
    # that dict order silently handed to French. Spanish is one of the most
    # common query languages in production, so the tie needed arbitrating on
    # evidence rather than declaration order.
    if scores.get("FR", 0) > 0 and scores.get("ES", 0) > 0:
        fr_only = {"le", "les", "des", "une", "est", "dans", "pour", "avec",
                   "cette", "du", "au", "aux", "quelle", "quels", "quelles",
                   "sur", "sont", "ainsi", "aussi", "tres", "ceux", "leur"}
        es_only_vs_fr = {"el", "los", "las", "por", "con", "para", "esta",
                         "cual", "cuales", "como", "sobre", "tambien", "asi",
                         "segun", "muy", "cuanto", "donde", "quienes",
                         "establece", "espanol", "espana"}
        fr = sum(1 for w in words if w in fr_only)
        es = sum(1 for w in words if w in es_only_vs_fr)
        if es > fr:
            scores["ES"] += 0.05
        elif fr > es:
            scores["FR"] += 0.05

    best = max(scores, key=scores.get)
    return best if scores[best] > 0.02 else "EN"


@dataclass
class ChatMessage:
    """Chat message structure"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ChatResponse:
    """AI chat response"""
    message: str
    citations: List[Dict[str, str]]
    tokens_used: int
    model: str
    search_time_ms: float
    total_time_ms: float
    actions: List[Dict[str, Any]] = None
    drafted_document: Optional[Dict[str, Any]] = None
    # Which provider in the chain actually answered. The router reads it as
    # `getattr(response, 'provider', '')`; while the field did not exist that
    # defensive default silently wrote NULL on EVERY non-streaming answer, so
    # the model was attributable and the provider was not. The 6 Aug 2026
    # attribution fix covered chat_stream() only (audit 17 Aug 2026).
    provider: str = ""


class AIService:
    """
    AI service for chat with EU context injection.

    Workflow:
    1. User sends message
    2. ContextBuilder fetches relevant EU data
    3. Context injected into Claude prompt
    4. Claude generates response with citations
    5. Response streamed back to user
    """

    # Model configurations
    # Chat does not run on a single fixed model: every request is served by
    # whichever link of the open-model chain answers first, and the real id is
    # reported per-request via the "meta" event and saved on the message row.
    # This label used to be "claude-sonnet-4-20250514", a model that is
    # deprecated AND returns 404 for our key -- so /api/chat/health advertised
    # a dead Anthropic model as the generator long after chat stopped using it.
    MODEL_CHAIN_LABEL = "multi-provider-open-model-chain"
    MODEL_SONNET = MODEL_CHAIN_LABEL  # back-compat alias for existing callers
    MODEL_OPUS = "claude-opus-4-20250514"

    # Token limits
    MAX_CONTEXT_TOKENS = 150000  # Claude 4 context window
    MAX_OUTPUT_TOKENS = 8000     # Maximum response length

    def __init__(
        self,
        api_key: str,
        context_builder: ContextBuilder,
        model: str = MODEL_SONNET,
        temperature: float = 0.3,
        max_output_tokens: int = 4000,
        use_fallback: bool = True
    ):
        """
        Initialize AI service.

        Args:
            api_key: unused; retained for signature compatibility
            context_builder: Context builder instance
            model: Claude model to use
            temperature: Response temperature (0-1)
            max_output_tokens: Maximum response tokens
            use_fallback: Enable multi-provider fallback chain
        """
        # No Anthropic client. Chat generates ONLY through the open-model
        # chain in multi_provider_service; there is no direct-to-Anthropic
        # path left to fall back to (removed 6 Aug 2026, cost decision).
        self.context_builder = context_builder
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.use_fallback = use_fallback
        # Wall-clock budget for the anti-hallucination validator's provider
        # call. Overridable via CHAT_VALIDATOR_TIMEOUT_S.
        try:
            self.validator_timeout_s = float(os.getenv("CHAT_VALIDATOR_TIMEOUT_S", "25"))
        except (TypeError, ValueError):
            self.validator_timeout_s = 25.0

        # Initialise multi-provider service for fallback
        if use_fallback:
            try:
                self.multi_provider = get_multi_provider_service()
                logger.info(
                    f"Initialized AIService with fallback chain: "
                    f"{', '.join(self.multi_provider.available_providers)}"
                )
            except Exception as e:
                logger.error(f"Multi-provider init FAILED -- chat has no generator: {e}")
                self.multi_provider = None
                self.use_fallback = False
        else:
            self.multi_provider = None

        logger.info(f"Initialized AIService with {model}")

    async def chat(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        user_id: Optional[str] = None,
        document_ids: Optional[List[str]] = None,
        use_context: bool = True,
        stream: bool = False,
        is_pre_user: bool = False
    ) -> ChatResponse:
        """
        Send chat message and get AI response.

        Args:
            user_message: User's message
            conversation_history: Previous messages in conversation
            use_context: Whether to inject EU context
            stream: Whether to stream response

        Returns:
            ChatResponse with AI message and metadata

        Example:
            >>> response = await ai_service.chat(
            ...     user_message="What's the status of the AI Act?",
            ...     use_context=True
            ... )
            >>> print(response.message)
            >>> print(response.citations)
        """
        start_time = datetime.now()

        # Fix B: greeting / identity short-circuit -- no context-build, no LLM call.
        _greet = _greeting_response(user_message)
        if _greet is not None:
            return ChatResponse(
                message=_greet,
                citations=[],
                tokens_used=0,
                model="brubru-greeting",
                search_time_ms=0.0,
                total_time_ms=(datetime.now() - start_time).total_seconds() * 1000,
                actions=[],
                drafted_document=None,
            )

        # Build EU context if enabled
        context_str = ""
        citations = []
        search_time_ms = 0.0
        mep_data = {}  # For MEP name linking
        context_data = None

        if use_context:
            # Get full context data to extract MEP information
            context_data = await self.context_builder.build_context_for_query(
                user_message=user_message,
                conversation_history=self._convert_to_dict(conversation_history),
                user_id=user_id
            )

            # Extract MEP name-to-ID mapping from committee info
            mep_data = self._extract_mep_data(context_data)
            print(f"\n{'='*70}")
            print(f"[MEP LINKING DEBUG] Extracted {len(mep_data)} MEP profiles from context")
            if mep_data:
                print(f"[MEP LINKING DEBUG] First 5 MEP names: {list(mep_data.keys())[:5]}")
            else:
                print(f"[MEP LINKING DEBUG] NO MEP DATA EXTRACTED!")
                print(f"[MEP LINKING DEBUG] hasattr(context_data, 'committee_info'): {hasattr(context_data, 'committee_info')}")
                if hasattr(context_data, 'committee_info'):
                    print(f"[MEP LINKING DEBUG] context_data.committee_info: {context_data.committee_info}")
            print(f"{'='*70}\n")
            logger.info(f"Extracted {len(mep_data)} MEP profiles from context")
            if mep_data:
                logger.debug(f"First 3 MEP names: {list(mep_data.keys())[:3]}")

            # Format context and build citations
            context_str = self.context_builder.format_context_for_ai(context_data)

            # Phase 1 of docs/applications/euvoc.md — prepend a localised
            # glossary block when the assembled context contains EU authority
            # URIs. Fail-soft: any error returns no glossary, never breaks chat.
            try:
                from services.vocabularies.glossary_injector import (
                    build_glossary_block as _build_glossary_block,
                    detect_language as _detect_language,
                )
                _glossary_lang = _detect_language(user_message)
                _glossary_db = SessionLocal()
                try:
                    _glossary = _build_glossary_block(context_str, _glossary_db, _glossary_lang)
                finally:
                    _glossary_db.close()
                if _glossary:
                    context_str = _glossary + "\n\n" + context_str
                    logger.info(
                        "[euvoc-glossary] Prepended glossary block (%d chars, lang=%s)",
                        len(_glossary), _glossary_lang,
                    )
            except Exception as _e:  # noqa: BLE001
                logger.warning("[euvoc-glossary] injection failed: %s", _e)

            citations = self._build_citations_from_context(context_data)

            search_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Load uploaded documents if provided
        document_content = []
        if document_ids:
            logger.info(f"Loading {len(document_ids)} documents: {document_ids}")
            document_content = await self._load_documents(document_ids)
            logger.info(f"Successfully loaded {len(document_content)} of {len(document_ids)} documents for analysis")

        # Phase D3: Process conversation memory for entity extraction
        memory_context = ""
        conversation_id = user_id or "anonymous"  # Use user_id as conversation scope
        try:
            memory_service = get_conversation_memory_service()

            # Process current message
            memory_service.process_message(conversation_id, user_message, 'user')

            # Process conversation history for entity extraction
            if conversation_history:
                for msg in conversation_history[-5:]:  # Last 5 messages
                    memory_service.process_message(
                        conversation_id,
                        msg.content,
                        msg.role
                    )

            # Get context enhancement from memory
            memory_context = memory_service.get_context_enhancement(conversation_id)
            if memory_context:
                logger.debug(f"Memory context added: {memory_context[:200]}...")

        except Exception as e:
            logger.warning(f"Conversation memory processing failed: {e}")

        # Enhance context with memory if available
        if memory_context and context_str:
            context_str = f"{memory_context}\n\n{context_str}"
        elif memory_context:
            context_str = memory_context

        # Build system prompt
        _qlang = _detect_query_language(user_message)
        system_prompt = self._build_system_prompt(
            is_pre_user=is_pre_user,
            query_lang=_qlang,
        )

        # Build messages
        messages = self._build_messages(
            user_message=user_message,
            context=context_str,
            query_lang=_qlang,
            conversation_history=conversation_history,
            documents=document_content
        )

        # Call AI (with fallback chain if enabled)
        if stream:
            # Streaming not yet implemented in this version
            pass

        provider_used = "unknown"
        tokens_used = 0

        if self.use_fallback and self.multi_provider:
            # Use multi-provider fallback chain
            # Route to Claude Haiku when knowledge guides are matched
            has_knowledge = bool(
                context_data and (
                    context_data.internal_knowledge
                    or context_data.eu_institutional_results
                )
            )
            try:
                provider_response = await self.multi_provider.generate(
                    system_prompt=system_prompt,
                    messages=messages,
                    max_tokens=self.max_output_tokens,
                    temperature=self.temperature,
                    prefer_claude=has_knowledge
                )
                assistant_message = provider_response.message
                tokens_used = provider_response.tokens_used
                provider_used = provider_response.provider
                actual_model = provider_response.model

                if provider_used:
                    logger.info(f"Response generated by fallback provider: {provider_used}")

            except RuntimeError as e:
                # All providers failed
                logger.error(f"All AI providers failed: {e}")
                raise
        else:
            # There is no non-chain generator. The direct Anthropic call that
            # used to live here was removed on 6 August 2026: Anthropic is out
            # of the chat path entirely (too expensive; Brubru runs on open
            # models). If the chain is unavailable, that is a configuration
            # error worth surfacing, not something to paper over with a paid
            # provider nobody asked for.
            raise RuntimeError(
                "No AI provider chain available. Chat runs on the open-model "
                "chain (Cerebras/Gemini/Groq/NVIDIA/Mistral); configure at "
                "least one key."
            )

        # Remove any markdown links the AI created (except footnote citations)
        assistant_message = self._remove_ai_generated_links(assistant_message)

        # Strip fabricated bare beresol.eu CTA links (e.g. an invented
        # "Read Beresol's full deep-dive here: https://beresol.eu/public-affairs").
        # The only legitimate Brubru deep-dive surface is brubru.beresol.eu/...,
        # added by _append_deep_dive_link when a guide flags it.
        assistant_message = self._strip_fabricated_beresol_links(assistant_message)

        # Strip orphan [N] citation markers that don't map to real sources
        assistant_message = self._strip_orphan_citations(assistant_message, citations)

        # Strip leaked internal context markers from response
        assistant_message = self._strip_context_markers(assistant_message)

        # ASCII-fold Unicode hyphens inside URLs so eur‑lex (U+2011) links resolve
        assistant_message = self._normalise_url_hyphens(assistant_message)

        # Strip a self-introduction greeting the model sometimes bolts onto a
        # real answer ("Hello! I'm Brubru ... I can help you with ...\n\n<answer>")
        assistant_message = self._strip_leading_greeting(assistant_message)

        # Drop an invented regulation number stated in apposition to a named act
        # (audit defect D2, 28 Jul 2026)
        assistant_message = self._strip_contradicting_act_numbers(assistant_message)

        # Zero em-dashes on user-facing surfaces, and the recurring Catalan
        # slips (audit defect D7, 28 Jul 2026)
        assistant_message = self._fold_prose_dashes(assistant_message)
        assistant_message = self._apply_catalan_corrections(assistant_message, user_message)

        # Ensure a guide-flagged Brubru deep-dive/explainer URL is surfaced
        assistant_message = self._append_deep_dive_link(assistant_message, context_str)

        # Post-process to add MEP links
        if mep_data:
            print(f"\n{'='*70}")
            print(f"[MEP LINKING DEBUG] Post-processing response with {len(mep_data)} MEP profiles")
            print(f"[MEP LINKING DEBUG] MEP names to link: {list(mep_data.keys())[:5]}...")
            print(f"[MEP LINKING DEBUG] Response preview (first 500 chars):\n{assistant_message[:500]}")
            print(f"{'='*70}\n")

            logger.info(f"Post-processing response with {len(mep_data)} MEP profiles")
            logger.info(f"MEP names to link: {list(mep_data.keys())[:5]}...")  # Log first 5
            logger.info(f"Response preview (first 500 chars): {assistant_message[:500]}")
            original_message = assistant_message
            assistant_message = self._linkify_mep_names(assistant_message, mep_data)
            if original_message != assistant_message:
                print(f"[MEP LINKING DEBUG] ✓ Successfully added MEP profile links\n")
                logger.info(f"Successfully added MEP profile links")
            else:
                print(f"[MEP LINKING DEBUG] ✗ No MEP names found in response to link")
                print(f"[MEP LINKING DEBUG] Full MEP names available: {[mep_data[k]['name'] for k in list(mep_data.keys())[:10]]}\n")
                logger.warning(f"No MEP names found in response to link")
                logger.info(f"Full MEP names available: {[mep_data[k]['name'] for k in list(mep_data.keys())[:10]]}")

        # Post-process: Inject document URLs from knowledge guides
        if context_data and context_data.internal_knowledge:
            assistant_message = self._inject_guide_document_links(
                assistant_message, context_data.internal_knowledge
            )

        # Post-process: Add EUR-Lex links for legislation acronyms
        logger.info("Post-processing response with legislation acronyms")
        assistant_message = self._linkify_legislation(assistant_message)

        # Workstream 1: response validator. As of 28 May 2026 ON in production with
        # CRITICAL_OVERRIDE action -- a critical-severity verdict replaces the
        # response with a safe refusal template that names the violation types.
        # See memory/project_chat_ai_architecture_evolution.md and
        # memory/feedback_biotech_act_andriukaitis_incident_2026_05_28.md.
        assistant_message = await self._validate_and_maybe_override(
            message=assistant_message,
            user_message=user_message,
            context_str=context_str,
            provider_used=provider_used,
            user_id=user_id,
            use_context=use_context,
        )

        total_time_ms = (datetime.now() - start_time).total_seconds() * 1000

        logger.info(
            f"AI response generated by {provider_used}: {len(assistant_message)} chars, "
            f"{tokens_used} tokens, {total_time_ms:.2f}ms"
        )

        # Phase C: Detect and log knowledge gaps for continuous improvement
        gap_info = self._detect_knowledge_gap(assistant_message)
        if gap_info:
            logger.info(f"Knowledge gap detected: {gap_info['missing_data_type']}")
            # Log asynchronously to avoid slowing response
            asyncio.create_task(
                self._log_knowledge_gap(
                    query=user_message,
                    gap_info=gap_info,
                    user_id=user_id,
                    conversation_id=None  # Could be passed if available
                )
            )

        # Phase E1: Log analytics for monitoring dashboard
        source_tiers = self._extract_source_tiers(citations)
        asyncio.create_task(
            self._log_analytics(
                user_id=user_id,
                provider=provider_used,
                model=actual_model,
                tokens_used=tokens_used,
                response_time_ms=total_time_ms,
                search_time_ms=search_time_ms,
                had_knowledge_gap=gap_info is not None,
                knowledge_gap_type=gap_info.get('missing_data_type') if gap_info else None,
                source_tiers_used=source_tiers,
                citation_count=len(citations),
                context_sources_count=len(citations),
                query_length=len(user_message),
                response_length=len(assistant_message)
            )
        )

        # Quality logging (Playbook D): structured signals for every response.
        # Grep-friendly prefix lets us aggregate into BQS metrics later.
        try:
            guides_matched = len(context_data.internal_knowledge) if context_data and context_data.internal_knowledge else 0

            # Citation verification (Sprint 1a, 26 Apr 2026): log-only.
            # We do NOT mutate the response in 1a -- the goal is to MEASURE
            # broken-ref rate before designing the UX response. Synchronous
            # by deliberate choice so the cost lands in observed latency.
            try:
                from services.citation_verifier import verify_text as _verify_text
                _vdb = SessionLocal()
                try:
                    _verify_summary = await _verify_text(assistant_message, db=_vdb)
                finally:
                    _vdb.close()
                citation_verify = {
                    "total_refs": _verify_summary.total_refs,
                    "verified": _verify_summary.verified,
                    "broken": _verify_summary.broken,
                    "unknown": _verify_summary.unknown,
                    "cache_hits": _verify_summary.cache_hits,
                    "cache_misses": _verify_summary.cache_misses,
                    "verification_ms": _verify_summary.verification_ms,
                }
            except Exception as ve:
                logger.warning(f"citation verify failed (non-critical): {ve}")
                citation_verify = {"error": str(ve)[:100]}

            quality_signals = {
                "ts": datetime.now().isoformat(),
                "provider": provider_used,
                "model": actual_model,
                "response_time_ms": round(total_time_ms, 1),
                "tokens": tokens_used,
                "guides_matched": guides_matched,
                "source_tiers": source_tiers,
                "citations": len(citations),
                "query_lang": _detect_query_language(user_message),
                "response_lang": _detect_query_language(assistant_message),
                "has_legal_anchor": bool(_LEGAL_ANCHOR_RE.search(assistant_message)),
                "deflection": bool(_DEFLECTION_RE.search(assistant_message)),
                "dont_have": bool(_DONT_HAVE_RE.search(assistant_message)),
                "confidence": "high" if guides_matched > 0 else "low",
                "query_len": len(user_message),
                "response_len": len(assistant_message),
                "citation_verify": citation_verify,
            }
            logger.info(f"[QUALITY] {json.dumps(quality_signals, ensure_ascii=False)}")
        except Exception as e:
            logger.warning(f"Quality logging failed (non-critical): {e}")

        # Compute action buttons from entities and intent
        action_dicts = []
        if use_context and context_data is not None:
            try:
                tracked_refs = self._get_tracked_procedure_refs(user_id) if user_id else set()
                actions = compute_actions(
                    entities=context_data.entities,
                    drafting_intent=context_data.drafting_intent,
                    has_train_match=bool(context_data.legislative_train_files),
                    is_pre_user=is_pre_user,
                    tracked_refs=tracked_refs,
                )
                action_dicts = [a.to_dict() for a in actions]
            except Exception as e:
                logger.warning(f"Action routing failed (non-critical): {e}")

        # --- Agentic draft: if the user asked to PRODUCE a document we can
        # auto-draft (one-pager / stakeholder map / resolution / EP question
        # / talking points), generate it, persist it as a user_documents row,
        # and attach a preview + edit URL to the response. The chat UI will
        # render an inline draft card with an "Open in Documents" button.
        drafted_dict = None
        if (
            use_context
            and context_data is not None
            and user_id is not None
            and not is_pre_user
            and getattr(context_data.drafting_intent, "is_drafting_query", False)
        ):
            try:
                from services.ai.document_drafter import (
                    draft_from_chat_query,
                    pick_autodraft_subtype,
                )
                from models.user import User as _UserModel
                import uuid as _uuid_mod
                if pick_autodraft_subtype(context_data.drafting_intent) is not None:
                    _drafter_db = SessionLocal()
                    try:
                        try:
                            _uid = _uuid_mod.UUID(user_id)
                        except Exception:
                            _uid = user_id  # already a UUID
                        _user = _drafter_db.query(_UserModel).filter(_UserModel.id == _uid).first()
                        drafted = await draft_from_chat_query(
                            query=user_message,
                            drafting_intent=context_data.drafting_intent,
                            user=_user,
                            db=_drafter_db,
                        )
                        if drafted is not None:
                            drafted_dict = drafted.to_dict()
                            # Replace the generic "generate_document" wizard
                            # action with an "open_document" action that takes
                            # the user straight to the just-drafted document.
                            replaced = False
                            for a in action_dicts:
                                if a.get("action_type") == "generate_document":
                                    a["action_type"] = "open_document"
                                    a["label"] = f"Open in Documents"
                                    a["icon"] = "mdi-file-document-edit-outline"
                                    a["colour"] = "#0d9488"
                                    a["route"] = drafted.edit_url
                                    a["params"] = {
                                        "document_id": drafted.document_id,
                                        "document_subtype": drafted.document_subtype,
                                    }
                                    replaced = True
                                    break
                            if not replaced:
                                action_dicts.insert(0, {
                                    "action_type": "open_document",
                                    "label": "Open in Documents",
                                    "icon": "mdi-file-document-edit-outline",
                                    "colour": "#0d9488",
                                    "route": drafted.edit_url,
                                    "params": {
                                        "document_id": drafted.document_id,
                                        "document_subtype": drafted.document_subtype,
                                    },
                                    "requires_auth": True,
                                    "pre_user_label": "Sign up to open drafted documents",
                                })
                    finally:
                        _drafter_db.close()
            except Exception as e:
                logger.warning(f"Chat-side auto-draft failed (non-critical): {e}")

        return ChatResponse(
            message=assistant_message,
            citations=citations,
            tokens_used=tokens_used,
            model=actual_model,
            search_time_ms=search_time_ms,
            total_time_ms=total_time_ms,
            actions=action_dicts,
            drafted_document=drafted_dict,
            provider=provider_used,
        )

    async def _validate_and_maybe_override(
        self,
        *,
        message: str,
        user_message: str,
        context_str: str,
        provider_used: str,
        user_id: Optional[str],
        use_context: bool,
    ) -> str:
        """Run the anti-hallucination validator; return the final answer text.

        Returns `message` unchanged unless the validator returns a critical
        verdict AND override is configured, in which case a safe refusal
        template replaces it. Never raises: a validator failure must not cost
        the user their answer.

        Shared by chat() and chat_stream(). Until 6 August 2026 this pass
        existed only on the non-streaming path, which the UI never calls, so
        the validator has been enabled in production since 28 May 2026 and has
        never once run for a real user.
        """
        if not message:
            return message
        try:
            from services.ai.validator_settings import (
                VALIDATOR_ENABLED,
                VALIDATOR_SHADOW_MODE,
                VALIDATOR_CRITICAL_ACTION,
            )
            # Skip the second provider call unless the answer has a
            # checkable-fabrication surface.
            if not (VALIDATOR_ENABLED and use_context and _response_needs_validation(message)):
                return message

            from services.ai.response_validator import get_response_validator
            _validator = get_response_validator()
            if not _validator.is_available:
                return message

            # Bounded: the validator is a SECOND provider call on the same
            # saturated free-tier chain. On the streaming path it runs after
            # the user already has the answer, so an unbounded wait would hold
            # the SSE connection (and the message's DB write) open behind a
            # queued provider. Past the budget we keep the answer as-is.
            _validation = await asyncio.wait_for(
                _validator.validate(
                    query=user_message,
                    context_blocks=context_str,
                    response=message,
                ),
                timeout=self.validator_timeout_s,
            )
            logger.info(
                "[VALIDATOR] passed=%s severity=%s violations=%d latency_ms=%d error=%s",
                _validation.passed,
                _validation.severity,
                len(_validation.violations),
                _validation.latency_ms,
                _validation.error or "-",
            )
            asyncio.create_task(
                self._log_chat_validation(
                    query=user_message,
                    response=message,
                    context_length=len(context_str),
                    generator=provider_used,
                    language=_detect_query_language(user_message),
                    result=_validation,
                    shadow_mode=VALIDATOR_SHADOW_MODE,
                    user_id=user_id,
                )
            )
            if (
                not VALIDATOR_SHADOW_MODE
                and _validation.should_override
                and VALIDATOR_CRITICAL_ACTION == "override"
            ):
                logger.warning(
                    "[VALIDATOR] critical violation -- swapping in safe refusal template (types=%s)",
                    ",".join(v.type for v in _validation.violations) or "-",
                )
                return self._build_safe_refusal_response(
                    query=user_message,
                    violations=_validation.violations,
                    context_str=context_str,
                )
        except asyncio.TimeoutError:
            logger.warning(
                "[VALIDATOR] exceeded %ss budget -- answer kept unvalidated",
                self.validator_timeout_s,
            )
        except Exception as _e:  # noqa: BLE001
            logger.warning("validator pass failed (non-fatal): %s", _e)
        return message

    def _post_process_text(
        self,
        message: str,
        citations: Optional[List[Dict]] = None,
        context_str: str = "",
        context_data: Any = None,
        user_query: str = "",
    ) -> str:
        """Apply the whole-text clean-up transforms to a finished response.

        These are the transforms that need the COMPLETE message and therefore
        cannot be applied to individual streamed tokens: orphan-citation
        stripping, fabricated-link removal, hyphen normalisation, greeting
        stripping, deep-dive link appending and legislation linkification.

        The streaming path used to skip all of them, so a streamed answer
        shipped defects the non-streaming path would have caught. On 20 July
        2026 a subscriber received orphan "[1]" / "[2]" markers for exactly
        this reason, despite a system-prompt rule forbidding them.

        NOTE: the non-streaming path in chat() still applies these transforms
        inline, interleaved with MEP linking and validator work. Collapsing
        that path onto this helper is the remaining half of the unification
        and is owned by the Chat session.
        """
        if not message:
            return message

        message = self._remove_ai_generated_links(message)
        message = self._strip_fabricated_beresol_links(message)
        # citations=[] means every [N] marker is an orphan, which is the
        # correct reading when no sources were attached.
        message = self._strip_orphan_citations(message, citations or [])
        message = self._strip_context_markers(message)
        message = self._normalise_url_hyphens(message)
        message = self._repair_stale_urls(message)
        message = self._strip_leading_greeting(message)
        message = self._strip_contradicting_act_numbers(message)
        message = self._fold_prose_dashes(message)
        message = self._apply_catalan_corrections(message, user_query or "")
        message = self._correct_invented_features(message)
        message = self._append_deep_dive_link(message, context_str)

        if context_data is not None and getattr(
            context_data, "internal_knowledge", None
        ):
            message = self._inject_guide_document_links(
                message, context_data.internal_knowledge
            )

        message = self._linkify_legislation(message)
        # After the acronym pass, so an acronym that already became a link is
        # treated as a link segment here and is not touched again.
        message = self._linkify_references(message)
        return message

    async def chat_stream(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        use_context: bool = True,
        is_pre_user: bool = False,
        document_ids: Optional[List[str]] = None,
        nav_context: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response with dynamic status events.

        Yields JSON status events during context building, then text chunks.

        Args:
            user_message: User's message
            conversation_history: Previous messages
            use_context: Whether to inject EU context
            is_pre_user: Whether user is anonymous
            document_ids: Document IDs for status detection
            user_id: Authenticated user, from the JWT. Required for the
                personalised layers: the private-guide block resolves
                `users.private_guide_slug` from it, tracked-procedure
                awareness reads the user's carriage tracks, and the
                validator/analytics rows are attributed with it. Until
                6 Aug 2026 this parameter did not exist, so the streaming
                path -- the only path the UI uses -- was user-blind and
                56 users with `private_guide_status='ready'` never once
                received their own guide.

        Yields:
            JSON status events ({"type":"status","message":"..."}) and text chunks
        """
        start_time = datetime.now()

        # Policy-interest navigation: a lightweight, taxonomy-grounded mapping
        # flow (route free text -> canonical Brubru policy areas). Deliberately
        # routed to the cheap provider (Mistral-first) and kept off the heavy
        # knowledge-context path. See knowledge_base/policy_taxonomy.json.
        if nav_context == "policy_interests":
            async for chunk in self._stream_policy_nav(user_message, conversation_history):
                yield chunk
            logger.info(
                f"Streamed policy-nav response in {(datetime.now() - start_time).total_seconds():.2f}s"
            )
            return

        # Fix B: greeting / identity short-circuit -- no context-build, no LLM call.
        _greet = _greeting_response(user_message)
        if _greet is not None:
            yield _greet
            logger.info("Streamed templated greeting (no context, no LLM)")
            return

        # --- Emit entity-aware status events before context building ---
        if use_context:
            # Fast sync detection (<1ms each)
            entities = self.context_builder.extract_entities(user_message)
            drafting = detect_drafting_intent(user_message)

            # Companion status messages: name what we are actually looking up
            # so the wait does not feel generic. Felt-latency is half the
            # battle. Cap each entity string so the chip stays one line.
            def _trim(s: str, n: int = 40) -> str:
                s = " ".join((s or "").split())
                return s if len(s) <= n else s[: n - 1].rstrip() + "..."

            # Opening status. If we detected a recognisable law alias,
            # funding context, or policy area in the user message, surface
            # it instead of the generic "Searching EU legislation...".
            opening_label = None
            funding_topic_ids = getattr(entities, "funding_topic_ids", []) or []
            funding_programmes = getattr(entities, "funding_programmes", []) or []
            if funding_topic_ids:
                opening_label = f"Looking up funding topic {_trim(funding_topic_ids[0], 32)}..."
            elif funding_programmes:
                opening_label = f"Searching {_trim(funding_programmes[0], 24)} opportunities..."
            elif entities.celex_numbers:
                opening_label = f"Looking up CELEX {_trim(entities.celex_numbers[0], 20)}..."
            elif entities.procedure_references:
                opening_label = f"Checking procedure {_trim(entities.procedure_references[0], 24)}..."
            elif entities.policy_areas:
                opening_label = f"Searching {_trim(entities.policy_areas[0], 28)} files..."
            yield json.dumps({"type": "status", "message": opening_label or "Searching EU legislation..."})

            # Subsequent entity-specific statuses, each naming what we found.
            # Filter mep_names against a known set of institutional acronyms
            # the extractor sometimes mis-classifies as people (CELEX, COM,
            # OEIL, ECLI, etc.). A real MEP name contains a space or lowercase.
            _MEP_NOISE = {"CELEX", "COM", "OEIL", "ECLI", "EUR-LEX", "OJ", "PE", "CFSP"}
            mep_clean = [m for m in entities.mep_names
                         if m and m.upper() not in _MEP_NOISE
                         and (" " in m or any(c.islower() for c in m))]
            if mep_clean:
                first = _trim(mep_clean[0], 28)
                more = f" (+{len(mep_clean) - 1} more)" if len(mep_clean) > 1 else ""
                yield json.dumps({"type": "status", "message": f"Looking up {first}{more}..."})
            if entities.committee_codes:
                code = _trim(entities.committee_codes[0], 12)
                yield json.dumps({"type": "status", "message": f"Fetching {code} committee work..."})
            if entities.procedure_references and not opening_label:
                # Already surfaced if opening_label used it; emit only if not.
                ref = _trim(entities.procedure_references[0], 24)
                yield json.dumps({"type": "status", "message": f"Checking procedure {ref}..."})
            if document_ids:
                yield json.dumps({"type": "status", "message": "Reading your document..."})
            if drafting.is_drafting_query:
                doc_type = getattr(drafting, "document_type", "") or "document"
                label = str(doc_type).replace("_", " ").title()
                yield json.dumps({"type": "status", "message": f"Preparing to draft your {label.lower()}..."})

            # The identifiers this answer is about: procedure references, CELEX
            # numbers, committees. Emitted for everyone, not just pre-users.
            # This was scoped to the pre-user smart-suggestion experiment, which
            # meant subscribers -- the only people who have a My EU Bubble to
            # open these in -- received nothing, and their suggestions fell back
            # to the generic "walk me through this" line.
            yield json.dumps({
                "type": "entities",
                "mep_names": entities.mep_names[:3],
                "committee_codes": entities.committee_codes[:3],
                "procedure_references": entities.procedure_references[:3],
                "celex_numbers": entities.celex_numbers[:3],
                "policy_areas": entities.policy_areas[:3],
            })

        # Build context (the slow part: 2-5s)
        # Use an asyncio.Queue to emit progress status during context building
        context_str = ""
        # Assigned from the context task below when use_context is on; must
        # exist either way because post-processing reads it unconditionally.
        stream_citations: List[Dict] = []
        context_data: Any = None
        mep_data: Dict[str, Dict[str, str]] = {}
        context_ms = 0.0
        if use_context:
            status_queue: asyncio.Queue = asyncio.Queue()

            # Pick a topic noun for the knowledge-base / ranking statuses so
            # the wait does not feel generic. Order of priority mirrors what
            # the user is most likely thinking about.
            topic = None
            if entities.celex_numbers:
                topic = f"CELEX {entities.celex_numbers[0]}"
            elif entities.procedure_references:
                topic = f"procedure {entities.procedure_references[0]}"
            elif entities.policy_areas:
                topic = entities.policy_areas[0]
            elif entities.committee_codes:
                topic = f"the {entities.committee_codes[0]} committee"

            kb_message = f"Searching {topic} in the knowledge base..." if topic else "Searching knowledge base..."
            rank_message = f"Ranking sources on {topic}..." if topic else "Ranking sources..."

            async def _build_context_with_progress():
                """Run context building and emit progress events to queue.

                Mirrors the non-streaming path in chat() exactly: build the
                structured ContextData, format it, then derive citations from
                it. The old implementation called build_context_with_citations,
                which takes no user_id and returns only a string -- so the
                streaming path lost BOTH the personalised context (private
                guides, tracked procedures) and the structured object that
                guide-document link injection and MEP linkification need.
                """
                await status_queue.put(kb_message)
                cdata = await self.context_builder.build_context_for_query(
                    user_message=user_message,
                    conversation_history=self._convert_to_dict(conversation_history),
                    user_id=user_id,
                )
                await status_queue.put(rank_message)
                context = self.context_builder.format_context_for_ai(cdata)

                # Localised EU-vocabulary glossary, same as chat(). Fail-soft:
                # any error yields no glossary rather than breaking the answer.
                try:
                    from services.vocabularies.glossary_injector import (
                        build_glossary_block as _build_glossary_block,
                        detect_language as _detect_language,
                    )
                    _glossary_db = SessionLocal()
                    try:
                        _glossary = _build_glossary_block(
                            context, _glossary_db, _detect_language(user_message)
                        )
                    finally:
                        _glossary_db.close()
                    if _glossary:
                        context = _glossary + "\n\n" + context
                except Exception as _e:  # noqa: BLE001
                    logger.warning("[euvoc-glossary] stream injection failed: %s", _e)

                citations = self._build_citations_from_context(cdata)
                await status_queue.put(None)  # Signal completion
                return context, citations, cdata

            # Run context building as a task so we can drain status events
            context_task = asyncio.create_task(_build_context_with_progress())

            # Drain status events while context builds
            while True:
                try:
                    status = await asyncio.wait_for(status_queue.get(), timeout=0.5)
                    if status is None:
                        break
                    yield json.dumps({"type": "status", "message": status})
                except asyncio.TimeoutError:
                    # No status yet -- emit a heartbeat to keep the SSE connection alive
                    continue

            # Keep the citations: the streaming path needs them to tell an
            # orphan [N] marker from a real one during post-processing.
            # context_data carries the structured object that guide-document
            # link injection and MEP linkification read.
            context_str, stream_citations, context_data = await context_task
            mep_data = self._extract_mep_data(context_data)
            context_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Signal context building done, AI composing
        yield json.dumps({"type": "status", "message": "Composing response..."})

        # Load uploaded documents (parity with non-streaming path). Without
        # this, the frontend can attach document_ids but the user's question
        # never receives the document content as a Claude content block, so
        # the model answers as if no document had been uploaded.
        document_content: List[Dict[str, Any]] = []
        if document_ids:
            try:
                logger.info(
                    f"[stream] Loading {len(document_ids)} document(s): {document_ids}"
                )
                document_content = await self._load_documents(document_ids)
                logger.info(
                    f"[stream] Loaded {len(document_content)} of {len(document_ids)} document(s)"
                )
            except Exception as exc:
                logger.warning(
                    f"[stream] Document loading failed (continuing without docs): {exc}"
                )
                document_content = []

        # Build prompts
        _qlang = _detect_query_language(user_message)
        system_prompt = self._build_system_prompt(
            is_pre_user=is_pre_user,
            query_lang=_qlang,
        )
        messages = self._build_messages(
            user_message=user_message,
            context=context_str,
            query_lang=_qlang,
            conversation_history=conversation_history,
            documents=document_content or None,
        )

        # Stream response via the FREE open-model chain (Groq -> Gemini ->
        # Mistral -> Cerebras -> Anthropic opportunistic). OpenAI-compatible
        # providers stream token deltas natively; others yield a single full
        # chunk. This is the 10 June 2026 migration that ends the streaming
        # path's Anthropic-only dependency (see project_chat_oss_migration.md).
        # Falls back to direct Anthropic streaming only if the multi-provider
        # chain is unavailable (no keys configured at all).
        # Buffer everything we emit so the whole-text post-processing chain can
        # run once the response is complete (see _post_process_text).
        streamed_parts: List[str] = []
        stream_failed = False
        # Caller-owned telemetry: which provider actually answered, on which
        # model, after how many failed attempts. Without this the streaming
        # path persisted model=NULL and latency could not be attributed.
        telemetry: Dict[str, Any] = {}
        llm_started = datetime.now()

        if self.use_fallback and self.multi_provider:
            try:
                async for piece in self.multi_provider.generate_stream(
                    system_prompt=system_prompt,
                    messages=messages,
                    max_tokens=self.max_output_tokens,
                    temperature=self.temperature,
                    telemetry=telemetry,
                ):
                    streamed_parts.append(piece)
                    yield piece
            except Exception as e:
                logger.error(f"[stream] free open-model chain failed: {e}")
                stream_failed = True
                yield ("I could not generate a response just now because the AI "
                       "providers are temporarily unavailable. Please try again "
                       "in a moment.")
        else:
            # Same as chat(): no Anthropic fallback exists any more.
            logger.error("[stream] no provider chain configured")
            stream_failed = True
            yield ("I could not generate a response just now because no AI "
                   "provider is configured. Please try again shortly.")

        # Post-process the completed response. Tokens have already reached the
        # user, so when clean-up changes the text we emit a "replace" event and
        # the client swaps in the corrected version. Emitting nothing when the
        # text is unchanged keeps the common case free of extra traffic.
        if streamed_parts and not stream_failed:
            raw_message = "".join(streamed_parts)
            try:
                cleaned = self._post_process_text(
                    raw_message,
                    citations=stream_citations,
                    context_str=context_str,
                    # Unified 6 Aug 2026: the streaming path now builds the
                    # structured ContextData, so guide-document link injection
                    # runs here exactly as it does in chat().
                    context_data=context_data,
                    user_query=user_message,
                )
                # MEP profile links, previously non-streaming only.
                if mep_data:
                    cleaned = self._linkify_mep_names(cleaned, mep_data)
                # Anti-hallucination validator. Enabled in production since
                # 28 May 2026 but, until today, only on the path the UI never
                # calls. It runs after the tokens have reached the user, so a
                # critical verdict arrives as a "replace" that swaps the answer
                # for a safe refusal.
                cleaned = await self._validate_and_maybe_override(
                    message=cleaned,
                    user_message=user_message,
                    context_str=context_str,
                    provider_used=telemetry.get("provider", "") or "stream",
                    user_id=user_id,
                    use_context=use_context,
                )
                if cleaned != raw_message:
                    logger.info(
                        "[stream] post-processing changed the response "
                        f"({len(raw_message)} -> {len(cleaned)} chars)"
                    )
                    yield json.dumps({"type": "replace", "content": cleaned})
            except Exception as e:
                # Never let clean-up break a response the user can already see.
                logger.warning(f"[stream] post-processing failed: {e}")

            # Send the citation list. Without this the streaming path renders
            # bare [1] [2] markers with nothing to resolve to: the markers are
            # NOT orphans (they map to real sources, which is why the stripper
            # keeps them), the client simply never received the sources. The
            # non-streaming path has always returned them in its JSON body.
            # Audit follow-up, 28 Jul 2026. Emitted after any "replace" so the
            # client applies them to the final text.
            if stream_citations:
                yield json.dumps({
                    "type": "citations",
                    "citations": stream_citations,
                })

        # Provider telemetry. Deliberately emitted as an SSE event that the
        # ROUTER consumes and never forwards to the browser, so persisting
        # model/provider/tokens needs no frontend change and cannot render as
        # raw JSON in a stale bundle (see
        # memory/feedback_sse_event_ships_frontend_first).
        yield json.dumps({
            "type": "meta",
            "provider": telemetry.get("provider", ""),
            "model": telemetry.get("model", ""),
            "tokens_used": telemetry.get("tokens_used", 0),
            "attempts": telemetry.get("attempts", []),
            "context_ms": round(context_ms, 1),
            "llm_ms": round((datetime.now() - llm_started).total_seconds() * 1000, 1),
        })

        # After streaming completes, compute and emit action buttons
        if use_context:
            try:
                has_train_match = self._check_train_match(entities.procedure_references) if entities.procedure_references else False
                # The streaming path now carries user_id, so "already tracked"
                # is known and the Track button stops being offered for files
                # the user has already added. Run the sync ORM query in a
                # thread: production is a SINGLE uvicorn worker, and blocking
                # the loop here would stall every other in-flight request
                # (see memory/feedback_cron_subprocess_blocks_event_loop).
                if user_id:
                    tracked_refs = await asyncio.get_event_loop().run_in_executor(
                        None, self._get_tracked_procedure_refs, user_id
                    )
                else:
                    tracked_refs = set()
                actions = compute_actions(
                    entities=entities,
                    drafting_intent=drafting,
                    has_train_match=has_train_match,
                    is_pre_user=is_pre_user,
                    tracked_refs=tracked_refs,
                )
                if actions:
                    yield json.dumps({
                        "type": "actions",
                        "actions": [a.to_dict() for a in actions],
                    })
            except Exception as e:
                logger.warning(f"Action routing failed in stream (non-critical): {e}")

        total_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Analytics. This ran only in chat(), which no real user reaches --
        # /api/chat/stream is the only live path (see
        # memory/feedback_chat_stream_is_the_only_real_path). The consequence
        # was that chat_analytics stopped describing reality: 28 rows for 169
        # answers in the 30 days to 9 Aug 2026, so provider mix, latency and
        # citation counts were quietly reporting on dead code.
        #
        # Reuses the `telemetry` dict already collected above rather than
        # introducing a second provider-reporting mechanism. Fired as a task so
        # it never delays the final SSE frame, and wrapped so a telemetry
        # failure can never break an answer the user already has.
        try:
            asyncio.create_task(
                self._log_analytics(
                    user_id=user_id,
                    provider=telemetry.get("provider", "") or "unknown",
                    model=telemetry.get("model", "") or self.model,
                    tokens_used=telemetry.get("tokens_used", 0) or 0,
                    response_time_ms=total_ms,
                    search_time_ms=round(context_ms, 1),
                    had_knowledge_gap=False,
                    knowledge_gap_type=None,
                    source_tiers_used=self._extract_source_tiers(stream_citations),
                    citation_count=len(stream_citations),
                    context_sources_count=len(stream_citations),
                    query_length=len(user_message),
                    response_length=len("".join(streamed_parts)),
                )
            )
        except Exception as e:
            logger.warning(f"Analytics logging failed in stream (non-critical): {e}")

        logger.info(f"Streamed response in {total_ms / 1000:.2f}s")

    _policy_taxonomy_cache: Optional[dict] = None

    @classmethod
    def _load_policy_taxonomy(cls) -> dict:
        """Load + cache the canonical policy taxonomy JSON (shared with the
        frontend selector and the /api/policy-taxonomy endpoint)."""
        if cls._policy_taxonomy_cache is None:
            import json
            from pathlib import Path
            path = (
                Path(__file__).resolve().parents[1]
                / "knowledge_base" / "policy_taxonomy.json"
            )
            with path.open(encoding="utf-8") as fh:
                cls._policy_taxonomy_cache = json.load(fh)
        return cls._policy_taxonomy_cache

    def _build_policy_nav_prompt(self) -> str:
        """System prompt for the policy-interest navigation flow: map free text
        to the canonical Brubru policy areas, grounded ONLY on the taxonomy."""
        taxonomy = self._load_policy_taxonomy()
        lines = []
        for cat in taxonomy.get("categories", []):
            names = " | ".join(pa["name"] for pa in cat.get("policy_areas", []))
            lines.append(f"- {cat['category']}: {names}")
        leaf_block = "\n".join(lines)
        return (
            "You are Brubru's policy-interest guide. Everything in My EU Bubble "
            "is organised around a FIXED set of EU policy areas (listed below). "
            "The user is choosing which areas to follow and could not find their "
            "topic in the picker.\n\n"
            "Your job:\n"
            "1. Map what the user typed to 1-3 areas FROM THE LIST BELOW. Use only "
            "names from the list; never invent an area.\n"
            "2. Write each chosen area name EXACTLY as it appears in the list and "
            "in English (verbatim), so the app can offer it as a one-click option. "
            "You may explain in the user's language, but keep the area names in "
            "English.\n"
            "3. Say briefly why each fits (one short clause).\n"
            "4. Geography is a SEPARATE axis. If the user names a country or region, "
            "do not treat it as a policy area: name the closest policy area and note "
            "that geography is filtered separately.\n"
            "5. If nothing on the list genuinely fits, say so plainly (\"Brubru does "
            "not have a dedicated area for that yet\") and name the single closest "
            "area, or suggest a broader term. Do not force a bad match.\n"
            "6. Finish with one line in this exact shape: \"In Policy Interests, "
            "tick: <Area>, <Area>.\"\n\n"
            "Keep it short (3-6 sentences). Answer in the user's language. Do not "
            "discuss legislation, procedures, or other Brubru tools here, only the "
            "policy-area mapping.\n\n"
            "Policy areas (by category):\n"
            f"{leaf_block}"
        )

    async def _stream_policy_nav(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
    ) -> AsyncGenerator[str, None]:
        """Run the policy-nav mapping. Mistral-first (prefer_claude=False); the
        answer is short so we yield it as a single chunk. Falls back to the
        Anthropic stream if the multi-provider chain is unavailable."""
        system_prompt = self._build_policy_nav_prompt()
        messages = self._build_messages(
            user_message=user_message,
            context="",
            conversation_history=conversation_history,
            documents=None,
        )
        if self.use_fallback and self.multi_provider:
            try:
                resp = await self.multi_provider.generate(
                    system_prompt=system_prompt,
                    messages=messages,
                    max_tokens=600,
                    temperature=0.2,
                    prefer_claude=False,
                )
                yield resp.message
                return
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning(f"policy-nav multi-provider failed: {exc}")
                yield ("I could not map that to a policy area just now. "
                       "Please try again in a moment.")
                return
        logger.error("policy-nav: no provider chain configured")
        yield ("I could not map that to a policy area just now. "
               "Please try again in a moment.")

    def _append_deep_dive_link(self, message: str, context_str: str) -> str:
        """
        If the injected EU context flags a Brubru explainer / deep-dive URL for
        the topic (a line containing both 'brubru.beresol.eu' and an
        explainer/deep-dive marker), make sure that URL is surfaced in the
        answer. Scoped tightly to the guide marker so it never appends an
        unrelated link. Plain text only; the frontend linkifies it.
        """
        if not message or not context_str:
            return message
        import re as _re
        candidates: list[str] = []
        for line in context_str.splitlines():
            low = line.lower()
            if "brubru.beresol.eu" in low and (
                "explainer" in low or "deep-dive" in low or "deep dive" in low
            ):
                for url in _re.findall(r"https://brubru\.beresol\.eu/[^\s)\]\"']+", line):
                    candidates.append(url.rstrip(".,);"))
        # De-duplicate, preserve order, keep only URLs not already in the answer.
        seen: set[str] = set()
        to_add = [u for u in candidates if not (u in seen or seen.add(u)) and u not in message]
        if not to_add:
            return message

        # TOPIC-MATCH GUARD (audit defect D1, 22 Jun 2026). When the context
        # carries deep-dive markers for several retrieved guides, blindly
        # appending the FIRST candidate mislinks the answer: an end-of-life
        # vehicles answer got /eu-inc/ and an RRF answer got the AI-Act canon.
        # Appending a wrong deep-dive is worse than appending none, so only
        # surface a candidate whose slug is actually relevant to the answer
        # text; omit entirely if nothing matches.
        # Generic path/structural tokens that must never count as a topic match.
        # Generic tokens that must never count as a topic match on their own.
        # "ai" is here because nearly every AI-policy answer says "AI" -- without
        # it the generic word pulled the CADA /cloud-ai-act/ deep-dive onto an
        # unrelated Frontier-AI answer (live test, 22 Jun 2026). Distinctive
        # compound slugs like "aiact" (len>=5) still match via substring.
        _noise = {
            "index", "html", "htm", "eucanon", "eu", "www", "brubru", "beresol",
            "the", "of", "and", "a", "an", "act", "regulation", "directive",
            "guide", "guides", "explainer", "deep", "dive", "ai", "data", "new",
        }
        msg_norm = _re.sub(r"[^a-z0-9]+", " ", message.lower())
        msg_compact = msg_norm.replace(" ", "")
        msg_words = set(msg_norm.split())

        def _slug_tokens(url: str) -> list[str]:
            path = _re.sub(r"^https://brubru\.beresol\.eu/", "", url)
            toks = []
            for t in _re.split(r"[/\-_.]+", path.lower()):
                if not t or t in _noise or t.isdigit():
                    continue
                toks.append(t)
            return toks

        def _matches(url: str) -> bool:
            toks = _slug_tokens(url)
            if not toks:
                return False
            for t in toks:
                # Long distinctive slug token: allow despaced substring match so
                # "aiact" matches an answer that says "AI Act" (-> "aiact").
                if len(t) >= 5 and t in msg_compact:
                    return True
                # Shorter token: require a whole-word hit to avoid false matches
                # ("inc" must be the word "inc", not a substring of "including").
                if t in msg_words:
                    return True
            return False

        matched = next((u for u in to_add if _matches(u)), None)
        if not matched:
            return message
        return message.rstrip() + f"\n\nRead Brubru's full deep-dive here: {matched}"

    def _build_system_prompt(self, is_pre_user: bool = False, query_lang: str = "EN") -> str:
        """
        Build system prompt for Claude.

        Args:
            is_pre_user: Whether the user is a non-registered pre-user

        Returns:
            System prompt string
        """
        prompt = """You are Brubru, an expert assistant on European Union legislative affairs, policy and institutional practice. You are also the guide to Brubru the product: for most users you are the first thing they meet, so you explain what Brubru holds, what each feature does, and which one to use next.

You cover EU legislation and case law, legislative procedures and their status, MEPs, committees and institutions, and policy developments. Your data comes from EUR-Lex and the Publications Office, OEIL, EP open data, AI-transcribed EP committee recordings, EU institutional news, the EU institutional calendar, and Brubru's curated knowledge guides.

Today is {today}.

================================================================
1. THE RULE THAT OUTRANKS EVERYTHING: GROUND EVERY SPECIFIC
================================================================
Specific facts must come from the EU CONTEXT supplied with this query, never from memory: names, dates, CELEX and procedure and case numbers, article numbers, vote tallies, fines, percentages, budgets, deadlines, risk levels, case counts.

If a specific is not in the context, do not supply it. Say which field is missing and name the source that would have it. "This is not on file in Brubru's record; OEIL lists the current assignment at <URL>" is a good answer. A plausible invented value is the worst thing you can produce, because a professional will act on it.

You may explain frameworks, mechanisms, processes and history from general knowledge. The line is: general explanation yes, specific unverified values no. When you draw on general knowledge rather than context, say so ("Based on publicly available information...").

Never fill a gap with a web-search result and present it as Brubru's verified record.

Never fabricate these identifier formats when the value is not in context: PE numbers, A-reports, T-texts and P_TA references, vote tallies, trilogue dates, rapporteur and shadow names. Describe where to find them instead. Do not echo any identifier value unless that exact string is in the context for this query.

If a knowledge guide marks a field as NOT YET VERIFIED, TBC, or explicitly says not to cite it, refuse to give a value for that field even if you believe you know it, and say the record is not yet verified. Training memory does not override a guide that says the data is unconfirmed.

Do not invent: that two events on the same date share a venue; what an upcoming meeting will discuss when you only have its title; a weekday you computed yourself (use the TODAY BLOCK's verbatim day); a regulatory artefact with no matching context item; an attribution to a named outlet or reporter.

================================================================
2. LANGUAGE
================================================================
This query's language has been detected as {{QUERY_LANG_NAME}}. Write your ENTIRE answer in {{QUERY_LANG_NAME}}, including headings, section labels and the closing follow-up. The detection is authoritative; do not re-decide it from the wording, which is unreliable for short queries.

Brubru works in English, French, Dutch, Spanish, Catalan and Italian. Use British English spelling in English answers (analyse, colour, organisation).

Catalan has its own EU vocabulary and getting it wrong reads as a half-finished translation:
- A Regulation is a "Reglament", never "Regulació": "Reglament (UE) 2024/1689". Directive is "Directiva", Decision "Decisió", Recommendation "Recomanació", Opinion "Dictamen", Communication "Comunicació", Proposal "Proposta", Treaty "Tractat", Judgment "Sentència".
- Implementing act is "d'execució"; delegated act is "delegat" or "delegada".
- Use the Catalan acronym, not the English one: "responsabilitat ampliada del productor (RAP)", never "(EPR)"; "passaport digital de producte (PDP)". Same in Spanish: "responsabilidad ampliada del productor (RAP)".
- "Tenint en compte" for Having regard to, "Ha adoptat" for has adopted, "Paràgraf" for paragraph, "Comitè dels Estats membres".
- Accents and the middle dot are obligatory, and every example here is spelled the way you must spell it: sóc, perquè, política, Brussel·les, intel·ligència, execució, Víctor Solé.
- Never let Spanish forms (Reglamento, Decisión, Recomendación, Sentencia) leak into Catalan.

Never use em-dashes in any answer, in any language. Use a comma, a colon, or a full stop.

If the user sends only a language request ("in English", "en catala", "auf Deutsch"), translate your PREVIOUS answer into that language keeping the same content, structure and depth. It is not a new question.

================================================================
3. SHAPE OF AN ANSWER
================================================================
Lead with the direct answer. Then the substance, organised with bold labels for anything complex. Then one closing follow-up.

For a substantive answer about a specific EU law or file, put the legal anchor in the opening paragraph, not a footnote: a CELEX number, a COM reference, or a procedure reference. This applies to information, analysis and drafting alike. A position paper with no anchor is worthless to a professional. If the act has no CELEX yet, use the COM or procedure reference; if none is in context, say the reference is not in your sources.

For a specific legislative file, give the procedure reference, the lead committee, the rapporteur when known, and every date with its year ("May 2026", never "in May"). Structure it as current stage, key actors, recent developments, next steps.

For complex topics, layer it: a two or three sentence summary that answers the question, then details by subtopic, then an offer to go deeper on one point.

Be confident when the context supports you. When a knowledge guide gives you article numbers, mechanisms, dates or a ten-item list, use them in full and never flatten them into four generic bullets or say you lack detail the guide provides. When the user follows up on the same topic, keep using the guide rather than getting progressively vaguer.

Do not hedge facts that are in your context. "There might be a fund for this" is wrong when the guide names the fund. Reserve conditional language for genuinely open outcomes such as votes and future decisions.

Never end by sending the user away. "Check EUR-Lex yourself" is not an answer; they came to Brubru to avoid that. You may point to EUR-Lex for the official consolidated text after you have answered.

================================================================
4. CITATIONS AND LINKS
================================================================
Cite with numbered markers [1], [2] that correspond to distinct sources in the EU CONTEXT. The interface renders these as a clickable source panel, so they must be real and sequential. If there is no EU CONTEXT, use no markers at all rather than inventing them.

Hyperlink every legislative reference you name, using these patterns:
- CELEX: [Regulation (EU) 2024/1735](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R1735)
- COM: [COM(2026)100](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=COM:2026:100:FIN)
- Procedure: [2022/0095(COD)](https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=2022/0095(COD))
A bare reference with no link is of little use to a professional.

Link only to *.europa.eu pages and brubru.beresol.eu. Links to any other domain are stripped before the user sees them, so write those sources as plain text. Reproduce URLs from the context exactly. Never invent one.

Do not hyperlink legislation acronyms (GDPR, CBAM, DSA, DMA, AI Act). They are law names, not committee codes. Write them plain or bold and give the CELEX instead. MEP names are linked automatically; do not link them yourself.

When the context carries a Brubru deep-dive or explainer URL (any https://brubru.beresol.eu/ link), you must surface it as plain text and point the user to it. This is not optional.

Institutional links, when asked for an agenda or calendar:
- EP plenary agenda https://www.europarl.europa.eu/plenary/en/agendas.html
- EP committee calendar https://www.europarl.europa.eu/committees/en/meetings/calendar
- Council calendar https://www.consilium.europa.eu/en/meetings/calendar/
- College of Commissioners https://commission.europa.eu/about-european-commission/college/meetings-college-commissioners_en
- OEIL procedure file https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference=<ref>

When asked for documents, present every reference in the guide's Key Documents or AVAILABLE DATA section that has a URL, as a markdown link, all versions at once, never asking which one they want. Bare refs follow these patterns: adopted text T10-XXXX/YYYY becomes /doceo/document/TA-10-YYYY-XXXX_EN.html; committee report A10-XXXX/YYYY becomes /doceo/document/A-10-YYYY-XXXX_EN.html; Council texts sit on data.consilium.europa.eu as ST-XXXXX-YYYY.

Source hierarchy when they conflict: EUR-Lex and the Official Journal first, then OEIL and EP official data, then EU institutional news, then curated guides and EPRS, then trusted policy media (name them: "According to Bruegel..."), then general web, which you always flag.

A statement about what the law requires, permits, prohibits or repeals needs an authoritative source: EUR-Lex, the Official Journal, a national official gazette, an institution's own page, or the act text in your context. A consultancy page, NGO explainer or law-firm newsletter is not authority for a legal claim. If that is all you have, say the status is unconfirmed and name what would confirm it. Never state that a national statute is in force or repealed without the instrument that did it.

An empowerment to adopt delegated or implementing acts is not a present obligation. A private or industry standard is not law unless an act names it.

================================================================
5. LEGAL STATUS DISTINCTIONS THAT ARE EASY TO GET WRONG
================================================================
A Commission proposal is not a decision. If a guide marks something as a proposal, present it as still requiring adoption: "the Commission has proposed X; the co-legislators must still adopt it". A date it carries is the proposed date, so write "would extend to" and not "has extended to". Only call something adopted or in force when the context shows the adopting act with a CELEX or an explicit adoption date.

A provisional agreement is not law. Say the co-legislators reached a provisional agreement to amend X, not that the law now bans X, until the amending act appears in the Official Journal.

For trade agreements, three states are distinct and two of them can have opposite answers: signature (not binding), provisional application (trade chapters operational under a Council Decision, Article 218(5) TFEU, before all member states ratify), and full ratification (all national parliaments plus EP consent). Cite both states where relevant, using only the dates in the injected guide.

Reproduce precise dates exactly as the guide's QUICK FACTS or LATEST line gives them. Never soften a specific day to a month or a season, and never substitute a different month. If you are unsure, say the exact date is not in your sources rather than approximating: an approximated date reads as verified.

Every item in a list of legal acts must be a real act with a number and directly relevant. Two genuine items beat six padded ones. Never list a news article or a vague category as legislation.

Do not list specific tenders, grants or funding calls unless each has a real reference (a TED notice number, a Funding and Tenders topic ID, a grant call ID) present in the context. If none, say you cannot list live individual calls, explain the framework if useful, point to TED or the EU Funding and Tenders portal, and offer the Tenderator.

The EU does not number sanctions packages in law. "19th package" and similar are press shorthand. Ground the answer on the Council acts and CELEX numbers in the sanctions block and describe them as the most recent acts adopted on that date.

Brubru holds no epidemiological surveillance feed. Never invent case counts, death tolls or risk levels, and never raise or invert a risk rating: quote it exactly as the context gives it. You can always describe the EU health-security legal framework instead.

================================================================
6. PEOPLE AND ROLES
================================================================
A rapporteur or shadow rapporteur is always an MEP, never a Commissioner. Commissioners are the "responsible Commissioner" or an Executive Vice-President.

If a procedure block says the lead rapporteur or shadows are not populated, do not invent them. Say Brubru's record does not list one yet, give the OEIL link, and mention that tracking the file surfaces the assignment when it is made. Never guess shadows from committee membership: "likely shadows include" is misleading.

When listing MEPs, each entry carries the full name, political group, country, committee, and the procedure they are rapporteur on. Bare names are useless to a professional. Be explicit about how complete the list is, and omit any web result that lacks group, committee and procedure rather than adding a low-confidence section at the end.

For committee membership, use only the context, use its exact member count, and group by role (Chair, Vice-Chairs, Members, Substitutes) as a table or grouped list.

For Commission officials, cite only names in the organigramme or personnel block, with the exact unit code and role, and keep Head of Unit, Director, Deputy Director-General and Director-General distinct. Never mix names across DGs. If the role is not in the block, point to commission.europa.eu/about/organisation. A wrong name is worse than no name.

When a College of Commissioners block is present and the user asks who the Commissioners are, list every member it contains. Never write "key Commissioners include" or "selected members": the canonical answer is the complete list from the block, and length is not a constraint.

A role the USER asserts is a hypothesis, not data. "He's the rapporteur", "she's the shadow", "X leads the negotiation" must be checked against the context first. If the context confirms it, proceed. If it contradicts it, state the contradiction once and give the verified name. If the context is silent, say you cannot confirm that person holds that role, say what Brubru does know about the file, and do not repeat the asserted pairing anywhere else in the answer. Never invent a quote, a meeting or a future vote date to support the user's claim. Never split one person into two because their name has variants, and never invent a group-cohesion percentage or confidence level that is not in a Position Analysis or Predictions block.

================================================================
7. TIME
================================================================
"Today" is {today}, or the TODAY BLOCK's date verbatim if one is present. "Yesterday" is that date minus one. "This week" is the ISO week containing it, never the previous committee week. Never present an event from an earlier week as today's.

Prefer the EU institutional calendar over news feeds and memory for when something happened. Never cite an older event when the context holds a newer one. If nothing is listed for today, say so rather than inventing a meeting to fill the gap.

"As of" always means today. The date of the most recent event on a file is not the current date: if the last thing that happened was a provisional agreement in May and today is August, the file has been sitting at that stage for three months, and writing "as of May" tells the reader the opposite. Write "as of {today}, the file is at X, unchanged since [date of that event]". A stage with no movement is itself information a professional wants.

The EP calendar assigns exactly one type to a day, and each type tells you what is NOT happening: plenary (committees do not hold ordinary meetings), committee week (no plenary sitting), political group week (neither plenary nor committees), constituency week (MEPs in their home countries, no committee agenda exists), recess (nothing sits). If the user asks what committees are meeting during a group, constituency or recess week, the answer is that none are, and you name the week type. Do not soften that into "agendas are not detailed in the calendar", which implies meetings you merely cannot see. A calendar row naming a week type classifies the week; it is not an event with an agenda or attendees.

When a plenary session, summit or College meeting is happening this week or next, bring it into general EP or institutional questions proactively, with concrete agenda items rather than an abstract explanation of how the EP works.

If the question asserts something your context contradicts ("today's committee week", "the vote last Tuesday"), correct it first, plainly, then give the right picture. Never restate a false premise as though your sources supported it, and never write that your data "confirms" something without naming the evidence. This applies equally when the question came from a Brubru-generated suggestion: a suggestion carries no authority.

================================================================
8. BRUBRU THE PRODUCT: YOU ARE ITS GUIDE
================================================================
Every substantive answer names at least one Brubru feature the user can act in next, by its exact name. Chat is where users discover the rest of the product.

The canonical tree, six products. My EU Bubble is the cockpit, with exactly these 25 sub-tabs: Overview, Policy Interests, My Documents, News, My Tracked Files, My OJ, Amendments, Comparator, Legislative Train: state of play, Votes, My EU Calendar, Transcripts, Council Watch, MEP Watch, Plenary Order of Business, Parliamentary Questions, EU Public Consultations, Lobby Meetings, Position Analysis, Predictions, Brubru Databases, Research & Evidence, Stakeholder Mapping, Strategy Docs, Tender Docs. The other five products are Amendator, Chat (this conversation), EU Law Comply, Tenderator, and API. That list is complete: if a sub-tab you have in mind is not on it, it does not exist, so name My EU Bubble alone rather than inventing a room inside it.

Route intent to the right place: amendments to the Amendator; tracking a file or trilogue to My Tracked Files; who supports or opposes to Position Analysis; an MEP or committee to MEP Watch; Council, presidency or Coreper to Council Watch; dates and deadlines to My EU Calendar; the plenary agenda to Plenary Order of Business; roll-call results to Votes; what was said to Transcripts; written questions to Parliamentary Questions; lobbying and the Transparency Register to Lobby Meetings; who to talk to to Stakeholder Mapping; the Official Journal to My OJ; recent developments to News; whether it will pass to Predictions; consultations to EU Public Consultations; position papers and briefings to Strategy Docs; studies and impact assessments to Research & Evidence; what data Brubru holds to Brubru Databases; comparing files side by side to the Comparator, a spreadsheet workspace where rows are files and columns are rapporteur, status, committee, deadlines and article counts, every cell cited; obligations and gap analysis to EU Law Comply; tenders, procurement and EU funding to the Tenderator, with Tender Docs for the paperwork; machine-readable access and MCP to the API.

When someone asks what you can do, how Brubru works, or where to start, answer as the guide: name the two or three features that fit what they described, say in one line what each does for them, and give the first click.

When a user compares Brubru with a named competitor (Politico Pro, Contexte, Agence Europe, Euractiv Pro, MLex, Dods, or any other), answer with a plain list of what Brubru does. Do NOT build a two-column table, and do NOT write a column, heading or sentence describing the other product, including "why X cannot match it". You hold no data on any other company's feature set, so every such claim is unsourceable, and a citation marker after one implies Brubru's records support it when they do not. End by inviting the user to compare that list against whatever they use today. Their tool, their judgement.

Explain features only as far as you actually know them. Describe what a feature does and where it lives ("EU Law Comply, from the top bar") and stop there rather than inventing a click path. A confident but wrong walkthrough of our own product is the fastest way to lose a user, because they can check it in one click.

You cannot write to the user's workspace. You cannot track a file, save or pin a document, subscribe them to alerts, generate a document, run a prediction, or change a setting. Those happen only when the user clicks, or uses an action button shown under your answer. Never say you have done one ("I've added this to your tracker" is false and leaves them expecting alerts they do not have), and never offer to do one in the first person. Tell them where they do it: "You can track this file in My Tracked Files (My EU Bubble)." If they ask you directly to track something, say plainly that you cannot write to their workspace, then give the exact path and mention the Track button if one is shown.

Close every substantive answer with one specific follow-up that names a canonical feature. "You can track this file in My Tracked Files (My EU Bubble)" or "The Predictions tab (My EU Bubble) will forecast the outcome for this procedure". Use the verbs the product supports: track, surface, draft, generate, run, compare, pin, save, export, schedule. Anything you produce yourself (identify, explain, compare, draft text) may be phrased as an offer, "Would you like me to..."; anything that writes to the workspace is phrased as their action. Forbidden: "let me know if you have questions", "explore the platform", "check the tabs", and any offer with no feature in it. When you name My EU Bubble, always name one sub-tab with it. No follow-up is needed after greetings or identity questions.

Base the follow-up on data that exists. When the context has an AVAILABLE DATA FOR THIS FILE section, only offer what it confirms: offer the draft report only if one is listed, the committee vote only if one was held, the amendments only if they are tabled. Offering a dead end is worse than a generic close.

Vote outcomes belong to Predictions, which analyses group positions, Council dynamics and timelines. Give political context if useful, but point there rather than predicting yourself.

For amendment IDEAS, give three to five concrete ones, each naming an article or recital, the weakness in the current text, and the direction of the change. Never give topic summaries dressed as amendment ideas. For actual amendment TEXT, hand off in two or three sentences: the Amendator produces properly formatted EP amendments with justifications, opened from the green pen icon in the top bar, loading the file and using the AI Assistant tab.

When Beresol publishes a free Intelligence Monitor on the topic, mention it with its URL: defence https://beresol.eu/defence, capital markets union https://beresol.eu/cmu, tariffs and trade https://beresol.eu/tariffs, AI https://beresol.eu/ai-monitor, quantum https://beresol.eu/quantum, startups https://beresol.eu/startups, gold https://beresol.eu/gold. Only when the question is genuinely about that topic.

================================================================
9. READING THE QUERY
================================================================
Classify first. A CLEAR query names a specific entity (a law, an MEP, a committee, a procedure, an institution, a date): answer it directly. A BROAD query names no entity or spans many topics: acknowledge it in one sentence, list three to five specific angles as bullets, ask which one, and stay under 100 words until they choose. When uncertain, ask; when certain, answer.

An explicit instruction verb is the instruction. "Summarise", "list", "compare", "explain", "draft", "analyse" mean produce it now. Do not ask about audience, length or format first. Only ask when the TOPIC is ambiguous, never when the action is clear.

A short follow-up with no topic anchor ("what is the expected timeline?", "and next steps?") when nothing earlier in this conversation established the topic gets ONE short clarifying question. Do not guess the topic from unrelated context blocks. This does not apply when the previous turn in this same conversation set the topic: then just answer.

Interpret abbreviations rather than refusing. FR is the Financial Regulation, OLP the ordinary legislative procedure, MFF the multiannual financial framework, TEU and TFEU the Treaties, GA a grant agreement, CoR the Committee of the Regions, EESC the European Economic and Social Committee, DG a Directorate-General. Split run-together articles ("laFR" is "la FR"). Offer your best reading confidently and check it, or give the top two or three if genuinely ambiguous. Never answer "I don't have information about X" and stop.

A DRAFTING MODE ACTIVE signal, or an action word in any language (draft, write, prepare, redactar, redigir, brouillon, esborrany, borrador, bozza, ontwerp), means they want a document produced. Acknowledge in their language, use the template's headings if the context has one, ask one or two tailoring questions, name the relevant feature, and offer to start. Be action-oriented from the first sentence: open with "I can help you draft a position paper on the PFAS restriction", never with a backgrounder on what PFAS are. But information verbs are not drafting: summarise, recap, explain, overview, and requests for studies or reports want existing content listed, not a document written.

For an EP written question, confirm they mean a question for written answer to the Commission, then draft it: descriptive title up to 200 characters, the header block, two to four context paragraphs citing legislation, the bridge "In the light of the above:", one to three numbered sub-questions, British English and formal voice. Note that it saves to My Documents in My EU Bubble.

When the user's message matches a follow-up you offered, they are selecting it. Act on it immediately; do not comment that it was your own text. If what they selected is a workspace write, do not claim to have done it and do not ask them to re-name a file they already named: answer the substance, then give the click path.

Accept user corrections immediately and permanently. If they say someone is no longer an MEP or a date is wrong, that holds for the rest of the conversation, that person never appears in a later list, and you never argue or reintroduce the corrected item.

If the EU CONTEXT opens with a profile block describing the user's organisation, sector or tracked files, answer self-referential questions ("what does this mean for my work", "where do I start", "how does this affect us") THROUGH that profile. Name their actual files and sector. Defaulting to generic headlines about files they never tracked reads as having forgotten who they are.

Treat an uploaded document as a primary source: summarise, analyse or cross-reference it as asked, combine it with the EU context, cite its sections and articles, and use it as the base text for amendments. For a debate transcript, extract positions by political group and MEP.

================================================================
10. NAMED CONTEXT BLOCKS
================================================================
When one of these blocks is present, report only what it contains. Never invent quotes, speakers, positions, member-state stances or amendments, always cite the block's confidence level verbatim, and never pass a predicted stance off as an observed one.

- LEGAL TEXT INTELLIGENCE (article or recital of a specific act): authoritative for that resolution. Cite its CELEX and URL verbatim. Quote its linked recitals when asked about purpose or intent, and reproduce its statutory definitions verbatim when relevant. If it says a field is not yet cached, say so and link EUR-Lex rather than inventing article text. If it resolved an alias ("GDPR" to 32016R0679), repeat that resolution so the user sees the link.
- STAKEHOLDER FEEDBACK ON HAVE YOUR SAY: total plus breakdown by type and country, four to six representative quotes each attributed in bold by organisation, country and stakeholder type, divergent positions grouped, ending with the Have Your Say URL.
- POSITION ANALYSIS: a compact four-column table (Commission, Parliament by group, Council by member state or bloc, the user's own position if known), the rapporteur and group named, confidence cited, Council blocking minorities flagged, the user's specific group or country answered first, one actionable next step at the end.
- COMMISSIONER AGENDA: name, portfolio and country, then a chronological list with date, title, location and detail link. If nothing falls in the window, say so and link the source.
- EP PLENARY DEBATE TRANSCRIPT (official CRE): title and date, the Commission then Council position if they spoke, then per group that spoke the name, number of speakers and main argument, then an overall read on consensus or division, with the CRE link.
- COMMITTEE TRANSCRIPT (AI-transcribed from the EP Multimedia Centre): committee, date and source; agenda items with procedure references; three to five key points quoting sparingly; speakers and groups where labelled, saying so when they are not; focused on the user's procedure. Always add that it is an AI-generated transcript and the minutes and final reports are authoritative, and say explicitly when it is partial.

You hold a great deal of verified EU data. When it is in your context, answer with confidence. When it is not, say so plainly and point to where it lives. Both are good answers; inventing the difference is not."""

        if is_pre_user:
            prompt += """

PRE-USER CONTEXT:
This user has NOT signed up yet. When your answer relates to a Brubru feature, mention it naturally in ONE sentence:
- Legislative file tracking -> "You can track this file's progress in My Tracked Files (My EU Bubble)."
- Amendment drafting -> "The Amendator lets you draft amendments to this file."
- Document generation -> "Brubru's Strategy Docs (My EU Bubble) can produce full position papers and briefings."
- Compliance analysis -> "EU Law Comply can analyse your organisation's compliance gaps."
Maximum one feature mention per response. Keep it natural, not salesy."""

        # Inject dynamic date into temporal accuracy section
        from datetime import date as _date
        prompt = prompt.replace('{today}', _date.today().isoformat())

        # Inject the detected query language as a stated fact. Leaving the model
        # to infer it produced a Catalan question answered entirely in English
        # (audit, 5 Aug 2026: T1-ca detected CA correctly yet the answer came
        # back in English, because the rule asked the model to decide).
        prompt = prompt.replace(
            '{{QUERY_LANG_NAME}}', LANG_NAMES.get(query_lang, "English")
        )

        return prompt

    def _build_messages(
        self,
        user_message: str,
        context: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        documents: Optional[List[Dict[str, Any]]] = None,
        query_lang: str = "EN",
    ) -> List[Dict[str, Any]]:
        """
        Build messages array for the model.

        Args:
            user_message: Current user message
            context: EU context string
            conversation_history: Previous messages
            documents: List of document content blocks
            query_lang: Detected language of the query, restated at the very end
                of the user turn. The system prompt already names it, but a long
                context block in another language beats a distant instruction:
                a Terraqui user asking "who am I and which organisation do I work
                for?" in ENGLISH got a Catalan answer, because their 19,708-char
                private guide is written in Catalan. Recency wins, so the
                reminder goes last.

        Returns:
            Messages array
        """
        messages = []
        lang_name = LANG_NAMES.get(query_lang, "English")

        # Add conversation history
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages
                messages.append({
                    'role': msg.role,
                    'content': msg.content
                })

        # Build user content (may be multi-modal with documents)
        if documents:
            # Multi-modal message with documents
            content_blocks = []

            # Add documents first
            for doc in documents:
                content_blocks.append(doc)

            # Add text prompt
            if context:
                text_content = f"""EU CONTEXT:
{context}

---

USER QUESTION: {user_message}

Please analyse the uploaded documents above along with the EU context provided. Include citations [1], [2], etc. when referencing specific sources. Write the entire answer in {lang_name}, whatever language the context or the documents happen to be written in."""
            else:
                text_content = f"""Please analyze the uploaded documents above and answer: {user_message}"""

            content_blocks.append({
                'type': 'text',
                'text': text_content
            })

            messages.append({
                'role': 'user',
                'content': content_blocks
            })
        else:
            # Text-only message
            if context:
                user_content = f"""EU CONTEXT:
{context}

---

USER QUESTION: {user_message}

Please answer using the EU context provided above. Include citations [1], [2], etc. when referencing specific sources. Write the entire answer in {lang_name}, whatever language the context happens to be written in."""
            else:
                user_content = user_message

            messages.append({
                'role': 'user',
                'content': user_content
            })

        return messages

    def _convert_to_dict(
        self,
        conversation_history: Optional[List[ChatMessage]]
    ) -> Optional[List[Dict[str, str]]]:
        """Convert ChatMessage objects to dict format"""
        if not conversation_history:
            return None

        return [
            {
                'role': msg.role,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat()
            }
            for msg in conversation_history
        ]

    def _get_tracked_procedure_refs(self, user_id: str) -> set:
        """Get procedure refs the user already tracks. Non-critical, returns empty set on failure."""
        try:
            from models.legislative_train import LegislativeCarriage, UserCarriageTrack
            import uuid as uuid_mod
            db = SessionLocal()
            try:
                rows = db.query(LegislativeCarriage.oeil_procedure_ref).join(
                    UserCarriageTrack,
                    UserCarriageTrack.carriage_id == LegislativeCarriage.id
                ).filter(
                    UserCarriageTrack.user_id == uuid_mod.UUID(user_id),
                    LegislativeCarriage.oeil_procedure_ref.isnot(None)
                ).all()
                return {r[0] for r in rows}
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to get tracked refs: {e}")
            return set()

    def _check_train_match(self, procedure_refs: List[str]) -> bool:
        """Check if any procedure refs exist in the legislative train DB. Quick indexed lookup."""
        if not procedure_refs:
            return False
        try:
            from models.legislative_train import LegislativeCarriage
            db = SessionLocal()
            try:
                count = db.query(LegislativeCarriage.id).filter(
                    LegislativeCarriage.oeil_procedure_ref.in_(procedure_refs)
                ).limit(1).count()
                return count > 0
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to check train match: {e}")
            return False

    def _extract_mep_data(self, context_data: Any) -> Dict[str, Dict[str, str]]:
        """
        Extract MEP name-to-ID mapping from context data.

        Args:
            context_data: ContextData object with committee info

        Returns:
            Dict mapping MEP names to their data:
            {
                "ANTONIO DECARO": {
                    "mep_id": "257122",
                    "name": "Antonio DECARO",
                    "url": "https://www.europarl.europa.eu/meps/en/257122/ANTONIO_DECARO/home"
                }
            }
        """
        mep_data = {}

        logger.debug(f"_extract_mep_data: hasattr committee_info = {hasattr(context_data, 'committee_info')}")
        if hasattr(context_data, 'committee_info'):
            logger.debug(f"_extract_mep_data: committee_info = {context_data.committee_info}")

        # Extract from committee_info
        if hasattr(context_data, 'committee_info') and context_data.committee_info:
            for committee in context_data.committee_info:
                members_by_role = committee.get('members_by_role', {})

                # Iterate through all roles (Chair, Vice-Chair, Member, Substitute)
                for role, members in members_by_role.items():
                    for member in members:
                        name = member.get('name', '')
                        mep_id = member.get('mep_id', '')

                        if name and mep_id:
                            # Store with uppercase key for matching
                            key = name.upper()

                            # Create URL-safe name (replace spaces with +)
                            url_name = name.replace(' ', '+')

                            mep_data[key] = {
                                'mep_id': mep_id,
                                'name': name,  # Keep original formatting
                                'url': f"https://www.europarl.europa.eu/meps/en/{mep_id}/{url_name}/home"
                            }

        # Also extract from mep_profiles if available
        if hasattr(context_data, 'mep_profiles') and context_data.mep_profiles:
            for profile in context_data.mep_profiles:
                name = profile.get('name', '')
                mep_id = profile.get('mep_id', '')

                if name and mep_id:
                    key = name.upper()
                    url_name = name.replace(' ', '+')

                    mep_data[key] = {
                        'mep_id': mep_id,
                        'name': name,
                        'url': f"https://www.europarl.europa.eu/meps/en/{mep_id}/{url_name}/home"
                    }

        # Also extract from procedure_details (rapporteurs have names + groups)
        if hasattr(context_data, 'procedure_details') and context_data.procedure_details:
            for proc in context_data.procedure_details:
                meps_info = proc.get('meps', {})
                # Rapporteur
                rapporteur = meps_info.get('rapporteur', '')
                if rapporteur and isinstance(rapporteur, str):
                    # Rapporteur names from OEIL don't have mep_id, but we can still
                    # store the name for reference (without a link)
                    key = rapporteur.upper()
                    if key not in mep_data:
                        mep_data[key] = {
                            'mep_id': '',
                            'name': rapporteur,
                            'url': '',
                            'role': 'rapporteur',
                        }
                # Shadow rapporteurs
                for shadow in meps_info.get('shadows', []):
                    if shadow and isinstance(shadow, str):
                        key = shadow.upper()
                        if key not in mep_data:
                            mep_data[key] = {
                                'mep_id': '',
                                'name': shadow,
                                'url': '',
                                'role': 'shadow rapporteur',
                            }

        # Also extract from legislative_train_files (may contain rapporteur names)
        if hasattr(context_data, 'legislative_train_files') and context_data.legislative_train_files:
            for ltf in context_data.legislative_train_files:
                rapporteur = ltf.get('rapporteur', '')
                if rapporteur and isinstance(rapporteur, str):
                    key = rapporteur.upper()
                    if key not in mep_data:
                        mep_data[key] = {
                            'mep_id': '',
                            'name': rapporteur,
                            'url': '',
                            'role': 'rapporteur',
                        }

        # Also extract from mep_amendments_summary (MEP names in amendments)
        if hasattr(context_data, 'mep_amendments_summary') and context_data.mep_amendments_summary:
            for summary in context_data.mep_amendments_summary:
                for am in summary.get('key_amendments', []):
                    authors_str = am.get('authors', '')
                    if authors_str:
                        for author in authors_str.split(','):
                            author = author.strip()
                            if author and len(author) > 3:
                                key = author.upper()
                                if key not in mep_data:
                                    mep_data[key] = {
                                        'mep_id': '',
                                        'name': author,
                                        'url': '',
                                        'role': 'amendment author',
                                    }

        logger.info(f"Extracted {len(mep_data)} MEP profiles for linking")
        return mep_data

    def _remove_ai_generated_links(self, text: str) -> str:
        """
        Remove markdown links that the AI generated on its own.

        Keep footnote citations like [1], [2], etc.
        Replace markdown links [text](url) with just the text.

        Args:
            text: AI response text

        Returns:
            Text with AI-generated markdown links removed
        """
        # Pattern to match markdown links [text](url)
        # But NOT footnote citations like [1], [2], etc.
        # Negative lookahead to exclude [number] patterns

        def replace_link(match):
            link_text, url = match.group(1), match.group(2)
            # Keep links to authoritative EU sources and to Brubru's own
            # surfaces; flatten everything else.
            #
            # Stripping ALL of them (the behaviour until 6 Aug 2026) directly
            # contradicted two instructions the model is given: the context
            # block states "Any markdown links in the guides below are VERIFIED.
            # Reproduce them exactly ... Do NOT strip the URLs", and the prompt
            # requires hyperlinking every COM/CELEX/procedure reference. The
            # stripper won, so a guide's verified deep-dive, OEIL page or EP
            # document URL was flattened to dead text and only bare CELEX
            # numbers got re-linked afterwards. That is also why an answer could
            # name a Brubru feature four times and link it zero times.
            if _TRUSTED_LINK_HOST_RE.search(url or ''):
                return match.group(0)
            return link_text

        # Match [text](url) but not [number]
        # Use a more specific pattern that requires at least one non-digit character in brackets
        pattern = r'\[([^\]]+)\]\((https?://[^\)]+)\)'

        cleaned_text = re.sub(pattern, replace_link, text)

        # Log if we removed any links. `pattern` captures (text, url), so
        # findall yields TUPLES -- passing one to re.escape raises TypeError.
        if cleaned_text != text:
            untrusted = [
                (lt, url) for lt, url in re.findall(pattern, text)
                if not _TRUSTED_LINK_HOST_RE.search(url or '')
            ]
            logger.info(
                "Flattened %d untrusted markdown link(s): %s",
                len(untrusted),
                ", ".join(u[:80] for _, u in untrusted[:5]) or "-",
            )

        return cleaned_text

    def _strip_fabricated_beresol_links(self, text: str) -> str:
        """
        Remove fabricated bare beresol.eu CTA links from a response.

        The model occasionally invents a promotional link such as
        "https://beresol.eu/public-affairs" presented as a Brubru/Beresol
        "deep-dive" or "open report". No knowledge guide contains such a URL.
        The only legitimate Brubru deep-dive surface is the brubru.beresol.eu
        subdomain (added by _append_deep_dive_link when a guide flags it).

        Strategy: drop any line that references a beresol.eu URL which is NOT on
        the brubru.beresol.eu subdomain (and is not the hello@beresol.eu
        signature, which should never appear in chat anyway). Line-level removal
        is safe because the fabricated CTA is always emitted as its own
        paragraph ("Read Beresol's full deep-dive here: <url>").
        """
        if "beresol.eu" not in text:
            return text

        kept_lines = []
        dropped = 0
        for line in text.split("\n"):
            low = line.lower()
            has_bad_beresol = (
                "beresol.eu" in low
                and "brubru.beresol.eu" not in low
                and "@beresol.eu" not in low
            )
            if has_bad_beresol:
                dropped += 1
                continue
            kept_lines.append(line)

        if dropped:
            logger.info(f"Stripped {dropped} fabricated beresol.eu CTA line(s)")
            print(f"[LINK REMOVAL] Stripped {dropped} fabricated beresol.eu CTA line(s)")
            # Collapse any blank-line gap the removal opened up
            cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept_lines)).strip()
            return cleaned

        return text

    def _strip_context_markers(self, text: str) -> str:
        """
        Strip leaked internal context section markers from AI response.
        These are injected as system prompt structure but sometimes leak
        into the visible response (e.g., "EU LAW SNAPSHOT EU INSTITUTIONAL CALENDAR").
        """
        markers = [
            'EU LAW SNAPSHOT',
            'EU INSTITUTIONAL CALENDAR',
            'LEGISLATIVE FILES',
            'COMMISSION DOCUMENTS',
            'COMMITTEE WORK IN PROGRESS',
            'EPRS PUBLICATIONS',
            'EU CONTEXT',
        ]
        cleaned = text
        for marker in markers:
            # Remove standalone markers (with optional surrounding whitespace)
            cleaned = re.sub(rf'\s*{re.escape(marker)}\s*', ' ', cleaned)

        # Strip bracketed INTERNAL source tags that leak from retrieval, e.g.
        # [DG_MOVE_ORGANIGRAMME], [LEGISLATIVE_FILES], [COM_2025_847.pdf]
        # (audit defect, 18 Jun 2026). These are internal identifiers, not real
        # citations. Designed NOT to touch real references:
        #   - [CELEX: 32026R1184] / [OEIL: 2025/0847(COD)] -> colon+space, kept
        #   - [1], [2] -> numeric, handled by _strip_orphan_citations, kept
        #   - [COM(2025)847] -> parentheses, readable ref, kept
        # 1) ALL-CAPS tags joined by underscores (DG_MOVE_ORGANIGRAMME, LEGISLATIVE_FILES)
        cleaned = re.sub(r'\s*\[[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\]', ' ', cleaned)
        # 2) bare bracketed filenames ([COM_2025_847.pdf], [report.docx])
        cleaned = re.sub(r'\s*\[[A-Za-z0-9_\-]+\.(?:pdf|docx?|xml|html?|txt|json)\]', ' ', cleaned, flags=re.IGNORECASE)
        # 3) bracketed internal context-BLOCK labels the model echoes from the
        # injected section headers, e.g. [Today Block] (from "=== TODAY BLOCK ==="),
        # [Web Summary] (web-search source label). Audit defect D2, 10 Jul 2026:
        # these are Title-Case with a space, so the ALL-CAPS-underscore rule (1)
        # never caught them and they leaked verbatim (11x in one plenary-brief
        # answer). Explicit allowlist so legitimate bracketed prose is never touched.
        cleaned = re.sub(r'\s*\[\s*(?:end\s+)?today\s+block\s*\]', ' ', cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r'\s*\[\s*web\s+summary\s*\]', ' ', cleaned, flags=re.IGNORECASE)
        # 4) SPACE-separated multiword section headers the model echoes verbatim,
        # e.g. [COMMISSIONER AGENDA] (from "COMMISSIONER AGENDA (live):"). Rule (1)
        # only matches underscore-joined tags and rule (3) only covers two named
        # labels, so these leaked untouched -- twice in one subscriber answer on
        # 24 Jul 2026 (audit defect D5, 28 Jul 2026). Allowlisted rather than
        # pattern-matched: a blanket "bracketed ALL-CAPS words" rule would eat
        # legitimate prose such as [AI ACT] or [EU INC].
        cleaned = _CONTEXT_BLOCK_LABEL_RE.sub(' ', cleaned)
        # Tidy stray punctuation left behind ("(MOVE),." -> "(MOVE).") and double spaces
        # Collapse repeated commas/periods left by truncated enumerations
        # ("2 December 2027,,,." -> "2 December 2027.") -- audit defect D4, 22 Jun 2026.
        cleaned = re.sub(r',{2,}', ',', cleaned)
        cleaned = re.sub(r',\s*\.', '.', cleaned)
        cleaned = re.sub(r'\s+([.,;:])', r'\1', cleaned)
        cleaned = re.sub(r'  +', ' ', cleaned)

        # Clean up trailing whitespace
        cleaned = cleaned.strip()
        if cleaned != text.strip():
            logger.info(f"Stripped leaked context markers from response")
        return cleaned

    # Unicode hyphen/dash code points a model may "prettify" into a URL, all of
    # which break the link (a browser will not resolve eur‑lex.europa.eu).
    _URL_HYPHENS = str.maketrans({
        "‐": "-",  # HYPHEN
        "‑": "-",  # NON-BREAKING HYPHEN (the confirmed offender)
        "‒": "-",  # FIGURE DASH
        "–": "-",  # EN DASH
        "—": "-",  # EM DASH
        "―": "-",  # HORIZONTAL BAR
        "−": "-",  # MINUS SIGN
    })

    def _normalise_url_hyphens(self, text: str) -> str:
        """
        ASCII-fold Unicode hyphens/dashes that appear INSIDE http(s) URLs.

        Sonnet occasionally typographically prettifies a hyphen inside a URL,
        e.g. ``https://eur‑lex.europa.eu/...`` with a NON-BREAKING HYPHEN
        (U+2011). Browsers cannot resolve such a host, so every EUR-Lex CELEX
        link in the answer is dead when clicked (audit defect D1, 10 Jul 2026).
        Only characters inside a matched URL token are folded; ordinary prose
        (where an en/em dash is legitimate typography) is never touched.
        """
        if not text:
            return text

        def _fold(match: "re.Match") -> str:
            return match.group(0).translate(self._URL_HYPHENS)

        # A URL token runs until whitespace or a markdown/paren delimiter.
        return re.sub(r'https?://[^\s\)\]<>"]+', _fold, text)

    # Legacy OEIL procedure-file URL. Any host, http or https, with the
    # reference carried in the query string. The reference itself contains
    # parentheses -- 2022/0095(COD) -- so it is captured explicitly rather
    # than by a generic "not whitespace" run, which would swallow a trailing
    # markdown delimiter.
    # The reference may arrive percent-encoded (2025%2F2952%28DEA%29), which is
    # still a perfectly recoverable reference -- decoding it keeps the user on
    # their file instead of dropping them on the search page.
    _OEIL_LEGACY_RE = re.compile(
        r"https?://[\w.-]*europarl\.europa\.eu/oeil/popups/ficheprocedure\.do"
        r"(?:\?[^\s)\]\"']*?)?reference="
        r"(\d{4}(?:/|%2F)\d{4}(?:\(|%28)[A-Z]{3}(?:\)|%29))[^\s)\]\"']*",
        re.IGNORECASE,
    )
    _OEIL_LEGACY_BARE_RE = re.compile(
        r"https?://[\w.-]*europarl\.europa\.eu/oeil/popups/ficheprocedure\.do"
        r"[^\s)\]\"']*",
        re.IGNORECASE,
    )
    _OEIL_SEARCH_URL = "https://oeil.secure.europarl.europa.eu/oeil/en/search"

    def _repair_stale_urls(self, text: str) -> str:
        """Rewrite URL patterns that are known to be dead, in place.

        The legacy ``oeil/popups/ficheprocedure.do`` endpoint 404s for recent
        procedure files. A code sweep on 25 May 2026 fixed every place Brubru
        BUILDS one, which left the larger source untouched: the model writes
        them into prose itself, and the one knowledge guide that exists to
        forbid the pattern quotes it twice as a "do not use" example, which is
        exactly the re-priming that feedback_negation_paradox_in_warnings
        warns about. 17 stored answers carry a dead link, against 39 with the
        canonical one, so roughly a third of the OEIL links Chat has ever
        emitted do not resolve. Two were served on 7 August 2026.

        This runs where the instruction could not: _linkify_references
        deliberately skips anything that is already a link, so a dead href is
        precisely what it protects. Repairing the href is deterministic, which
        per feedback_context_block_beats_prompt_rule is the layer this belongs
        in rather than another line of prompt.

        A URL carrying a procedure reference becomes the canonical
        procedure-file link for that reference; one without a usable reference
        becomes the OEIL search page, since a working search beats a 404.
        """
        if not text:
            return text

        def _canonical(m: "re.Match") -> str:
            ref = (m.group(1)
                   .replace("%2F", "/").replace("%2f", "/")
                   .replace("%28", "(").replace("%29", ")"))
            return (
                "https://oeil.secure.europarl.europa.eu/oeil/en/"
                f"procedure-file?reference={ref}"
            )

        text = self._OEIL_LEGACY_RE.sub(_canonical, text)
        # Anything still on the legacy path had no reference to rescue.
        return self._OEIL_LEGACY_BARE_RE.sub(self._OEIL_SEARCH_URL, text)

    def _strip_leading_greeting(self, message: str) -> str:
        """
        Remove a self-introduction greeting the model occasionally prepends to a
        substantive answer, e.g.:

            "Hello! I'm Brubru, your expert AI assistant for European Union
             legislative affairs. I can help you with EU legislation ... and more.

             <the real answer>"

        Pure greetings are already short-circuited before the LLM by
        ``_greeting_response``; this catches the case where the model bolts an
        intro onto real content (audit defect D2, recurring -- 5th confirmation
        22 Jun 2026, now seen on authenticated traffic). Only strips when a
        substantial answer remains, so a genuine short greeting is never gutted.
        """
        if not message:
            return message
        m = re.match(
            r"\s*(?:hello|hi|hey|greetings)\b[^\n]{0,40}?\bbrubru\b[^\n]{0,260}?\n{1,}",
            message,
            flags=re.IGNORECASE,
        )
        if not m:
            return message
        remainder = message[m.end():].lstrip()
        if len(remainder) >= 80:
            logger.info("Stripped leaked self-introduction greeting preamble")
            return remainder
        return message

    def _strip_orphan_citations(self, text: str, citations: List[Dict]) -> str:
        """
        Remove [N] citation markers from AI response when they don't map
        to actual sources. Prevents hallucinated references from appearing.

        Args:
            text: AI response text
            citations: List of real citation dicts built from context

        Returns:
            Text with orphan citation markers removed
        """
        max_valid = len(citations)

        def replace_orphan(match):
            ws = match.group(1)
            num = int(match.group(3))
            if num < 1 or num > max_valid:
                return ""  # Strip orphan (and its leading whitespace)
            # Keep valid; normalise fullwidth CJK brackets to ASCII so the marker
            # matches the rendered References footer.
            return f"{ws}[{num}]"

        # Match [N] AND fullwidth CJK 【N】 markers (audit defect A1, 23 Jun 2026).
        # Cerebras/Gemini occasionally emit 【1】 (U+3010/U+3011) which the old
        # ASCII-only regex never touched, so orphans survived with no footer.
        cleaned = re.sub(r'(\s*)([\[【])(\d+)([\]】])', replace_orphan, text)

        # Strip fabricated fullwidth bracket-URL citations the model invents, e.g.
        # 【https://www.consilium.europa.eu/.../18-19/】 (audit defect A2, 23 Jun 2026).
        # These are not real stored references and frequently point at unverified
        # paths. Only fullwidth brackets containing a URL are removed; ASCII text
        # and legitimate [N]/footer links are untouched.
        cleaned = re.sub(r'\s*【[^】]*?https?://[^】]*?】', '', cleaned)

        # Clean up any double spaces left behind
        cleaned = re.sub(r'  +', ' ', cleaned)

        if cleaned != text:
            orphan_count = (
                len(re.findall(r'[\[【](\d+)[\]】]', text))
                - len(re.findall(r'[\[【](\d+)[\]】]', cleaned))
            )
            if orphan_count > 0:
                logger.info(f"Stripped {orphan_count} orphan citation markers (had {max_valid} real sources)")

        return cleaned

    def _linkify_mep_names(self, text: str, mep_data: Dict[str, Dict[str, str]]) -> str:
        """
        Post-process AI response to add markdown links for MEP names.

        Args:
            text: AI response text
            mep_data: MEP name-to-data mapping

        Returns:
            Text with MEP names converted to markdown links
        """
        if not mep_data:
            return text

        # Sort MEP names by length (longest first) to avoid partial matches
        sorted_names = sorted(mep_data.keys(), key=len, reverse=True)

        links_added = 0
        for name_key in sorted_names:
            mep_info = mep_data[name_key]
            name = mep_info['name']
            url = mep_info['url']

            # Pattern to match the MEP name in various formats:
            # 1. Exact match: "Antonio DECARO"
            # 2. Wrapped in markdown: **Antonio DECARO**
            # 3. Different casing: "Antonio Decaro", "ANTONIO DECARO"
            #
            # Split name into parts for flexible matching
            name_parts = name.split()

            if len(name_parts) >= 2:
                # Match full name with flexible spacing and optional markdown
                first_name = name_parts[0]
                last_name = ' '.join(name_parts[1:])

                # Pattern: optional **, then first name, space(s), last name, optional **
                # Use word boundaries to avoid matching inside other words
                # Negative lookbehind/lookahead to avoid matching already-linked names
                pattern = r'(?<!\]\()(?<!\[)\*{0,2}\b(' + re.escape(first_name) + r')\s+(' + re.escape(last_name) + r')\b\*{0,2}(?!\]\()'

                # Replacement: preserve any found text structure but wrap in link
                def replace_func(match):
                    nonlocal links_added
                    matched_text = match.group(0)
                    # Remove any markdown bold from the matched text
                    cleaned_text = matched_text.replace('**', '')
                    links_added += 1
                    return f'[{cleaned_text}]({url})'

                text = re.sub(pattern, replace_func, text, flags=re.IGNORECASE)
            else:
                # Single name (edge case)
                pattern = r'(?<!\]\()(?<!\[)\*{0,2}\b(' + re.escape(name) + r')\b\*{0,2}(?!\]\()'

                def replace_func(match):
                    nonlocal links_added
                    matched_text = match.group(0)
                    cleaned_text = matched_text.replace('**', '')
                    links_added += 1
                    return f'[{cleaned_text}]({url})'

                text = re.sub(pattern, replace_func, text, flags=re.IGNORECASE)

        if links_added > 0:
            logger.info(f"Added {links_added} MEP profile links to response")
        else:
            logger.warning(f"No MEP names found to link despite having {len(mep_data)} MEP profiles")

        return text

    def _inject_guide_document_links(self, text: str, knowledge_items: list) -> str:
        """
        Post-process AI response to inject clickable URLs for document references
        mentioned in the response, using URLs from knowledge guide content.

        The AI model often lists document references (T9-0299/2024, A9-0156/2024,
        COM(2023)533, ST-10462-2025) without making them clickable, even when the
        guide provides the URLs. This method fixes that by scanning the guide for
        markdown links and injecting them into the response.
        """
        # Extract all markdown links from guide content: [label](url)
        doc_urls = {}  # reference_key -> (label, url)
        for item in knowledge_items:
            content = item.get('content', '')
            # Find all markdown links in guide content
            # Simple approach: find [label]( then extract URL with balanced parens
            for match in re.finditer(r'\[([^\]]+)\]\(', content):
                label = match.group(1)
                # Extract URL: start after the ( and find matching )
                url_start = match.end()
                depth = 1
                i = url_start
                while i < len(content) and depth > 0:
                    if content[i] == '(':
                        depth += 1
                    elif content[i] == ')':
                        depth -= 1
                    i += 1
                url = content[url_start:i - 1]
                if not url.startswith('http'):
                    continue
                # Extract document reference from the label
                # Match patterns like T9-0299/2024, A9-0156/2024, COM(2023)533, ST-10462-2025, PE756.002
                for ref_match in re.finditer(
                    r'(T9-\d{4}/\d{4}|A9-\d{4}/\d{4}|COM\(\d{4}\)\d+|ST-\d+-\d+|PE\d+\.\d+|SWD\(\d{4}\)\d+)',
                    label
                ):
                    ref = ref_match.group(1)
                    doc_urls[ref] = (label, url)

        if not doc_urls:
            return text

        links_injected = 0
        for ref, (label, url) in doc_urls.items():
            escaped_ref = re.escape(ref)
            # Only match references NOT already inside a markdown link
            # Pattern: ref that is NOT preceded by [ or followed by ](
            # Match bold or plain references like **T9-0299/2024** or T9-0299/2024
            pattern = r'(?<!\[)(\*{0,2})(' + escaped_ref + r')(\*{0,2})(?!\]\()'
            # Check if this ref appears unlinked in the text
            if re.search(pattern, text):
                # Replace first unlinked occurrence with a markdown link
                def make_link(m):
                    nonlocal links_injected
                    links_injected += 1
                    return f'[{m.group(1)}{m.group(2)}{m.group(3)}]({url})'
                text = re.sub(pattern, make_link, text, count=1)

        if links_injected > 0:
            logger.info(f"Injected {links_injected} document links from knowledge guides")

        return text

    def _correct_invented_features(self, text: str) -> str:
        """Repair references to Brubru features that do not exist.

        The system prompt lists the canonical tree and says plainly that a
        sub-tab not on the list does not exist, but that is an instruction and
        instructions get ignored: a DG CONNECT answer closed by sending the
        user to "My EU Bubble > EU Who-is-Who", a tab we have never shipped.
        Of every kind of hallucination this product can emit, an invented
        feature is the one the user disproves fastest, because it is one click
        away.

        So the canonical names live here in code as well as in the prose, and
        anything that does not match is rewritten rather than shipped:
          - a real product named as if it were a sub-tab keeps its own name
          - an invented sub-tab collapses to plain "My EU Bubble"

        Kept deliberately narrow. It only touches text that explicitly pairs a
        name with My EU Bubble, so ordinary prose that happens to mention a
        capitalised phrase is left alone.
        """
        if not text or "My EU Bubble" not in text:
            return text

        def _norm(s: str) -> str:
            s = re.sub(r"[*_`]", "", s)
            # The model emits non-breaking hyphens and curly quotes; fold them
            # so "Who-is-Who" and "Who‑is‑Who" compare equal.
            s = s.replace("‑", "-").replace("–", "-").replace("—", "-")
            s = s.replace("’", "'")
            s = re.sub(r"\s+", " ", s).strip(" .,:;>→").lower()
            # "The Predictions tab" must resolve to the canonical "Predictions".
            # Without this the guard deleted correct feature names, which is a
            # worse failure than the one it exists to prevent.
            s = re.sub(r"^(?:the|el|la|le|il|els|les|los|las|de|het)\s+", "", s)
            return s

        subtabs = {_norm(s) for s in MEUB_SUBTABS}
        subtabs |= {_norm(s) for s in MEUB_SUBTAB_LOCALISED}
        products = {_norm(p): p for p in BRUBRU_PRODUCTS}

        def _resolve(name: str, whole: str) -> str:
            key = _norm(name)
            if not key or key in subtabs:
                return whole
            if key in products:
                # "EU Law Comply (My EU Bubble)" names a product as though it
                # lived inside the cockpit. Keep the product, drop the parent.
                return products[key]
            logger.info("[FEATURE-GUARD] dropped invented feature reference: %r", name)
            return "My EU Bubble"

        # "My EU Bubble > X". The tab name runs into the rest of the sentence,
        # so take the LONGEST canonical prefix of what follows rather than
        # everything up to the next full stop. Reading to the punctuation ate
        # the trailing clause of "Recerca i evidència per als estudis" and
        # condemned a correct Catalan tab name as invented.
        def _arrow(m: re.Match) -> str:
            head, rest = m.group(1), m.group(2)
            words = rest.split()
            for n in range(min(8, len(words)), 0, -1):
                if _norm(" ".join(words[:n])) in subtabs:
                    return m.group(0)
            run = []
            for w in words:
                # The closing-bracket class matters: without it a name written
                # inside parentheses, "(My EU Bubble -> EU Law Tracker).", broke
                # the run at "Tracker)." and only "EU Law" was dropped, leaving
                # the invented "My EU Bubble Tracker" -- a name less real than
                # the one being repaired (audit 17 Aug 2026).
                if re.match(r"^\*{0,2}[A-Z0-9][\w&:’'\-‑]*\*{0,2}[)\]]*[.,;:]?$", w):
                    run.append(w)
                    # A closing bracket or sentence punctuation ENDS the name.
                    # Without this break the run walks into the next sentence,
                    # because its first word is capitalised too, and "…Tracker).
                    # This will help." lost its "This".
                    if re.search(r"[)\].,;:]$", w):
                        break
                else:
                    break
            if not run:
                return m.group(0)
            logger.info(
                "[FEATURE-GUARD] dropped invented feature reference: %r", " ".join(run)
            )
            tail = " ".join(words[len(run):])
            # Keep whatever closing bracket / sentence punctuation was riding on
            # the last word, so the bracket that opened before "My EU Bubble"
            # still closes.
            end_m = re.search(r"[)\]]*[.,;:]?$", run[-1])
            end = end_m.group(0) if end_m else ""
            return f"{head}{end}" + (f" {tail}" if tail else "")

        text = re.sub(
            r"(My EU Bubble)\s*(?:>|→|-&gt;|->)\s*([^\n]{0,90})",
            _arrow,
            text,
        )
        # "X (My EU Bubble)". The name is whatever sits immediately before the
        # parenthetical, so this reads BACKWARDS a few words and asks whether
        # any suffix is canonical, rather than letting a regex run greedily
        # leftwards. An earlier version did the latter and rewrote
        # "Compare them in the Comparator (My EU Bubble)" down to "My EU
        # Bubble", destroying the sentence around a perfectly valid feature.
        def _paren(m: re.Match) -> str:
            before, trail = m.group(1), m.group(2)
            words = re.findall(r"[^\s]+", before)

            def _rebuild(keep_n: int, name: str) -> str:
                """Splice `name` in place of the last keep_n words, keeping bold paired."""
                kept = " ".join(words[: len(words) - keep_n])
                opened = words[len(words) - keep_n].startswith("**")
                if opened and trail == "**":
                    piece = f"**{name}**"
                else:
                    piece = f"{name}{trail}"
                return (f"{kept} " if kept else "") + piece
            # Longest-first: "Legislative Train: state of play" must win over
            # "play", and a canonical hit anywhere means leave the text alone.
            for n in range(min(6, len(words)), 0, -1):
                cand = " ".join(words[-n:])
                key = _norm(re.sub(r"\btabs?\b\s*$", "", cand, flags=re.I))
                if key in subtabs:
                    return m.group(0)
                if key in products:
                    return _rebuild(n, products[key])
            # Nothing canonical. Only rewrite when the words immediately before
            # the parenthetical look like a feature name (a Title Case run);
            # otherwise this is ordinary prose and must not be touched.
            run = []
            for w in reversed(words):
                if re.match(r"^\*{0,2}[A-Z][\w&:’'\-‑]*\*{0,2}$", w):
                    run.insert(0, w)
                else:
                    break
            if not run:
                return m.group(0)
            logger.info(
                "[FEATURE-GUARD] dropped invented feature reference: %r", " ".join(run)
            )
            return _rebuild(len(run), "My EU Bubble")

        text = re.sub(
            r"([^\n(]{0,80}?)\s*(?:tab\s*)?\((?:the\s+)?My EU Bubble\)(\*{0,2})",
            _paren,
            text,
        )
        return text

    # COM(2025)102 / COM (2025) 102, and OEIL procedure refs 2025/0102(COD).
    _COM_REF_RE = re.compile(r"\bCOM\s?\(\s?(\d{4})\s?\)\s?(\d{1,4})\b")
    _PROC_REF_RE = re.compile(r"\b(\d{4})/(\d{4})\s?\(\s?(COD|CNS|APP|INI|RSP|DEA|NLE|BUD|ACI|REG|IMM)\s?\)")
    _BARE_CELEX_RE = re.compile(r"(?<![:/\w])(3\d{4}[A-Z]{1,2}\d{4})\b")
    # "Regulation (EU) 2024/795", "Directive (EU) 2022/2041",
    # "Regulation (EU, Euratom) 2018/1046", "Decision (EU) 2025/1050".
    # This is how a professional writes a law in prose, and it was the one form
    # left unlinked: watching a real answer render in the browser, STEP was a
    # link and "Regulation (EU) 2024/795" beside it was plain text.
    # All six Brubru languages. An English-only pattern left every non-English
    # answer with no act links at all: a Catalan answer opened "Directiva (UE)
    # 2022/2041 del Parlament Europeu i del Consell" in plain text while the
    # English answer beside it linked the same act.
    _ACT_NAME_RE = re.compile(
        r"\b(Regulation|Directive|Decision"
        r"|Reglamento|Directiva|Decisi[oó]n"
        r"|Reglament|Decisi[oó]"
        r"|R[eè]glement|D[eé]cision"
        r"|Regolamento|Direttiva|Decisione"
        r"|Verordening|Richtlijn|Besluit)"
        r"\s+\((?:EU|EC|CE|UE)(?:,\s?Euratom)?\)\s+(\d{4})/(\d{1,4})\b",
        re.IGNORECASE,
    )
    _ACT_LETTER = {
        "regulation": "R", "reglamento": "R", "reglament": "R",
        "règlement": "R", "reglement": "R", "regolamento": "R",
        "verordening": "R",
        "directive": "L", "directiva": "L", "direttiva": "L",
        "richtlijn": "L",
        "decision": "D", "decisión": "D", "decisio": "D", "decisió": "D",
        "décision": "D", "decisione": "D", "besluit": "D",
    }

    def _linkify_references(self, text: str) -> str:
        """Hyperlink COM, procedure and bare CELEX references.

        The system prompt has always demanded that every legislative reference
        be a link, on the grounds that a bare reference is of little use to a
        professional. It was simply not happening: across four production
        answers on 7 August 2026, ZERO of one COM reference and zero of three
        procedure references were linked, including an answer that named
        COM(2025)102 and 2025/0102(COD) and linked neither.

        Asking the model was the wrong mechanism. The URL patterns are fixed,
        so the links are generated here instead, exactly as _linkify_legislation
        already does for acronyms.

        Segments that are already a markdown link or a bare URL are left alone,
        so nothing is double-linked and no existing href is rewritten.
        """
        if not text:
            return text

        def _com(m: re.Match) -> str:
            year, num = m.group(1), m.group(2)
            return (f"[{m.group(0)}](https://eur-lex.europa.eu/legal-content/EN/TXT/"
                    f"?uri=COM:{year}:{int(num)}:FIN)")

        def _proc(m: re.Match) -> str:
            ref = f"{m.group(1)}/{m.group(2)}({m.group(3)})"
            return (f"[{m.group(0)}](https://oeil.secure.europarl.europa.eu/oeil/en/"
                    f"procedure-file?reference={ref})")

        def _celex(m: re.Match) -> str:
            return (f"[{m.group(1)}](https://eur-lex.europa.eu/legal-content/EN/TXT/"
                    f"?uri=CELEX:{m.group(1)})")

        def _act(m: re.Match) -> str:
            kind, year, num = m.group(1), m.group(2), m.group(3)
            letter = self._ACT_LETTER.get(kind.lower())
            if not letter:
                return m.group(0)
            celex = f"3{year}{letter}{int(num):04d}"
            return (f"[{m.group(0)}](https://eur-lex.europa.eu/legal-content/EN/TXT/"
                    f"?uri=CELEX:{celex})")

        # Split into link/non-link segments; only the odd-index pieces are
        # existing markdown links or URLs, which must survive untouched.
        parts = re.split(r"(\[[^\]]*\]\([^)]*\)|https?://\S+)", text)
        for i in range(0, len(parts), 2):
            seg = parts[i]
            seg = self._COM_REF_RE.sub(_com, seg)
            seg = self._PROC_REF_RE.sub(_proc, seg)
            seg = self._ACT_NAME_RE.sub(_act, seg)
            seg = self._BARE_CELEX_RE.sub(_celex, seg)
            parts[i] = seg
        return "".join(parts)

    def _linkify_legislation(self, text: str) -> str:
        """
        Post-process AI response to add EUR-Lex markdown links for legislation acronyms.

        Args:
            text: AI response text

        Returns:
            Text with legislation acronyms converted to EUR-Lex links
        """
        # Load legislation acronyms database
        try:
            acronyms_path = Path(__file__).parent.parent / 'knowledge_base' / 'institutions' / 'legislation_acronyms.json'
            with open(acronyms_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                acronyms_db = data.get('acronyms', {})
        except Exception as e:
            logger.warning(f"Could not load legislation acronyms: {e}")
            return text

        if not acronyms_db:
            return text

        # STEP 0 (11 June 2026): correct a WRONG CELEX the generator emitted
        # INLINE. A weaker open model (e.g. NVIDIA Llama-3.3-70B) sometimes
        # writes a full EUR-Lex markdown link with a fabricated CELEX -- the
        # production DSA bug was [Digital Services Act](...CELEX:32023R1201)
        # when the real number is 32022R2065. STEP 2 below only links BARE
        # acronyms and deliberately skips already-linked text, so without this
        # the wrong CELEX ships and the validator can only refuse the whole
        # answer (degraded UX). Here we authoritatively rewrite the CELEX when
        # the link TEXT exactly matches a known acronym or its popular name in
        # our curated DB. Conservative: only acts when the text is an exact
        # name match AND the URL's CELEX differs; never touches non-EUR-Lex
        # links or ambiguous text. See memory/feedback_linkify_override_celex.md.
        name_to_celex: Dict[str, str] = {}
        for _acr, _info in acronyms_db.items():
            if _acr.upper() in _LINKIFY_ACRONYM_DENYLIST:
                continue
            if re.fullmatch(r'[IVXLCDM]+', _acr):
                continue
            if not _is_linkify_safe_act((_info or {}).get('full_title')):
                continue  # implementing/delegated act -> never a popular acronym's target
            _celex = (_info or {}).get('celex')
            if not _celex:
                continue
            if len(_acr) > 2 and not _acr.isdigit():
                name_to_celex.setdefault(_acr.strip().lower(), _celex)
            _full = (_info.get('full_name') or '').strip().lower()
            if len(_full) > 3:
                name_to_celex.setdefault(_full, _celex)

        celex_link_pattern = re.compile(
            r'\[([^\]]+)\]\(https://eur-lex\.europa\.eu/legal-content/[^)]*?'
            r'CELEX(?::|%3A)([0-9][0-9A-Za-z]+)[^)]*\)'
        )
        celex_corrected = 0

        def _fix_inline_celex(match):
            nonlocal celex_corrected
            link_text = match.group(1)
            url_celex = match.group(2).upper()
            key = link_text.replace('**', '').strip().lower()
            correct = name_to_celex.get(key)
            if correct and correct.upper() != url_celex:
                celex_corrected += 1
                return (
                    f'[{link_text}](https://eur-lex.europa.eu/legal-content/'
                    f'EN/TXT/?uri=CELEX:{correct})'
                )
            return match.group(0)

        text = celex_link_pattern.sub(_fix_inline_celex, text)
        if celex_corrected > 0:
            logger.info(
                f"Corrected {celex_corrected} wrong inline CELEX link(s) to canonical EUR-Lex"
            )

        # STEP 1: Remove incorrect committee hyperlinks for legislation acronyms
        # Claude sometimes treats legislation acronyms (CBAM, GDPR) as committees
        # We only remove committee links for acronyms IN our legislation database
        # This preserves actual committee links (ENVI, AGRI, etc.)

        links_removed = 0
        for acronym in acronyms_db.keys():
            escaped_acronym = re.escape(acronym)
            # Pattern: [ACRONYM](https://www.europarl.europa.eu/committees/en/ACRONYM/...)
            committee_link_pattern = r'\[(' + escaped_acronym + r')\]\(https://www\.europarl\.europa\.eu/committees/[^\)]+\)'

            # Replace with just the acronym text (no link)
            def remove_link(match):
                nonlocal links_removed
                links_removed += 1
                return match.group(1)  # Just the acronym text

            text = re.sub(committee_link_pattern, remove_link, text)

        if links_removed > 0:
            logger.info(f"Removed {links_removed} incorrect committee links for legislation acronyms")

        # STEP 1b: Remove committee links where the code is NOT a real EP committee
        # Catches cases like [NZIA](https://www.europarl.europa.eu/committees/en/NZIA/home)
        # where NZIA is not one of the 26 real EP committees
        fake_committee_pattern = r'\[([A-Z][A-Za-z0-9 ]+?)\]\(https://www\.europarl\.europa\.eu/committees/en/([A-Z]+)/[^\)]+\)'

        def remove_fake_committee_link(match):
            nonlocal links_removed
            link_text = match.group(1)
            committee_code = match.group(2)
            if committee_code not in EP_COMMITTEE_CODES:
                links_removed += 1
                return link_text  # Strip the link, keep the text
            return match.group(0)  # Keep valid committee links

        text = re.sub(fake_committee_pattern, remove_fake_committee_link, text)

        if links_removed > 0:
            logger.info(f"Total removed incorrect committee links: {links_removed}")

        # STEP 2: Add correct EUR-Lex hyperlinks
        # Sort acronyms by length (longest first) to avoid partial matches
        # e.g., "AI Act" before "AI"
        # Skip short acronyms (<=2 chars) and pure numbers to avoid false positives
        sorted_acronyms = sorted(acronyms_db.keys(), key=len, reverse=True)

        links_added = 0
        for acronym in sorted_acronyms:
            # Skip very short or numeric-only entries that cause false matches
            if len(acronym) <= 2 or acronym.isdigit():
                continue

            # Defence-in-depth (5 June 2026): never linkify Roman-numeral tokens
            # (e.g. "III" from "Annex III" or "Iron(III)") or a small denylist of
            # ambiguous all-caps tokens that collide with non-legislation meanings
            # (ETF = EMA Emergency Task Force, not the fishing directive; ACT, NEW,
            # API, etc.). These slip past the <=2-char filter and produce
            # hallucinated EUR-Lex links the validator then correctly refuses.
            # Root cause class: CLAUDE.md EEC/GATT rule. See
            # memory/feedback_linkify_garbage_acronyms_fa.md.
            if re.fullmatch(r'[IVXLCDM]+', acronym):
                continue
            if acronym.upper() in _LINKIFY_ACRONYM_DENYLIST:
                continue

            leg_info = acronyms_db[acronym]
            # Safe-by-default: skip entries whose full_title is an implementing
            # or delegated act -- the auto-ingestion mis-keyed popular acronyms
            # onto those (DSA->implementing-reg class). See _is_linkify_safe_act.
            if not _is_linkify_safe_act(leg_info.get('full_title')):
                continue
            celex = leg_info['celex']

            # Build EUR-Lex URL
            eurlex_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"

            # Pattern to match the acronym in various formats:
            # 1. Exact match: "CBAM"
            # 2. Wrapped in markdown: **CBAM**
            # 3. Case-sensitive for most, but allow some flexibility
            #
            # Use word boundaries to avoid matching inside other words
            # Negative lookbehind/lookahead to avoid matching already-linked text
            # Special handling for multi-word acronyms like "AI Act"

            # Escape special regex characters in acronym
            escaped_acronym = re.escape(acronym)

            # Pattern: optional **, then acronym, optional **
            # Negative lookbehind: not preceded by [ or ](
            # Negative lookahead: not followed by ]( or )
            pattern = r'(?<!\]\()(?<!\[)\*{0,2}\b(' + escaped_acronym + r')\b\*{0,2}(?!\]\()(?!\))'

            # Replacement: preserve any found text structure but wrap in link
            def replace_func(match):
                nonlocal links_added
                matched_text = match.group(0)
                # Remove any markdown bold from the matched text
                cleaned_text = matched_text.replace('**', '')
                links_added += 1
                return f'[{cleaned_text}]({eurlex_url})'

            # For case-sensitive matching (most acronyms are uppercase).
            # count=1 (24 Jun 2026): link only the FIRST unlinked occurrence of
            # each acronym. Without it, re.sub linkified EVERY occurrence, so a
            # single sentence rendered "[CBAM](url) ... buy [CBAM](url)
            # certificates" -- the same EUR-Lex link repeated 2-3x per line,
            # which reads as broken. Mirrors the count=1 doc-link injector above.
            # See audit B1 2026-06-24.
            text = re.sub(pattern, replace_func, text, count=1)

        if links_added > 0:
            logger.info(f"Added {links_added} legislation EUR-Lex links to response")

        # STEP 3 (24 Jun 2026): convert bare [CELEX:<num>] bracket tokens the
        # model sometimes emits as literal text (e.g. "...started on 1 January
        # 2026 [CELEX:32023R0956].") into proper EUR-Lex markdown links. Only
        # touches a [CELEX:...] token NOT already followed by "(" (i.e. not
        # already a markdown link). See audit B2 2026-06-24.
        celex_token_converted = 0

        def _convert_bare_celex(match):
            nonlocal celex_token_converted
            celex_token_converted += 1
            celex = match.group(1)
            return (
                f'[CELEX:{celex}](https://eur-lex.europa.eu/legal-content/'
                f'EN/TXT/?uri=CELEX:{celex})'
            )

        text = re.sub(
            r'\[CELEX:([0-9][0-9A-Za-z]+)\](?!\()',
            _convert_bare_celex,
            text,
        )
        if celex_token_converted > 0:
            logger.info(
                f"Converted {celex_token_converted} bare [CELEX:...] token(s) to EUR-Lex links"
            )

        return text

    def _build_citations_from_context(self, context_data: Any) -> List[Dict[str, Any]]:
        """
        Build the citation list from context data. THE single citation builder.

        Shape is what the frontend Citation type reads: id / type / title / url
        / metadata, plus `source_tier` which _extract_source_tiers() aggregates
        for analytics.

        Unified 6 August 2026. Before that there were two builders that
        disagreed: this one (used by chat()) covered 5 context fields and set no
        source_tier, while context_builder.build_context_with_citations (used by
        chat_stream()) covered 9 fields with tiers but a different key shape and
        no ids. Collapsing the streaming path onto the shorter builder would
        have silently dropped news, web-search, calendar, tender and Beresol
        sources from every streamed answer, so the union is built here instead.
        """
        from services.ai.context_builder import get_source_tier

        citations: List[Dict[str, Any]] = []

        def add(kind: str, title: str, url: str, **meta: Any) -> None:
            citations.append({
                'type': kind,
                'title': title or 'Untitled',
                'url': url or '',
                'source_tier': get_source_tier(kind),
                'metadata': {k: ('' if v is None else str(v)) for k, v in meta.items()},
            })

        for doc in getattr(context_data, 'relevant_documents', None) or []:
            md = doc.get('metadata') or {}
            add('search_result', md.get('title', 'Untitled'), md.get('url', ''),
                source=doc.get('collection', ''), score=doc.get('score', 0))

        for leg in getattr(context_data, 'legislation_details', None) or []:
            add('legislation', leg.get('title', ''), leg.get('url', ''),
                celex=leg.get('celex', ''), date=leg.get('date', ''))

        for proc in getattr(context_data, 'procedure_details', None) or []:
            add('procedure', proc.get('title', ''), proc.get('url', ''),
                reference=proc.get('reference', ''),
                status=proc.get('status', ''), stage=proc.get('stage', ''))

        for mep in getattr(context_data, 'mep_profiles', None) or []:
            add('mep', mep.get('name', ''),
                mep.get('url') or mep.get('profile_url', ''),
                country=mep.get('country', ''),
                group=mep.get('political_group', ''))

        for cm in getattr(context_data, 'committee_info', None) or []:
            add('committee',
                f"{cm.get('name', '')} ({cm.get('code', '')})".strip(),
                cm.get('url', ''), members=cm.get('member_count', 0))

        for entry in getattr(context_data, 'recent_rss_entries', None) or []:
            add('news', entry.get('title', ''), entry.get('link', ''),
                published=entry.get('published'), source=entry.get('source', ''))

        for result in getattr(context_data, 'web_search_results', None) or []:
            if result.get('source') == 'tavily_ai_answer':
                continue  # the AI summary is not a citable source
            add('web_search', result.get('title', ''), result.get('url', ''),
                published=result.get('published_date'), source='tavily')

        for item in getattr(context_data, 'beresol_content', None) or []:
            if item.get('type') == 'beresol_report':
                add('beresol_report', item.get('title', ''), item.get('source_url', ''),
                    author=item.get('author', ''), date=item.get('date'),
                    policy_area=item.get('policy_area', ''),
                    publisher=item.get('publisher', ''))
            elif item.get('type') == 'beresol_monitor':
                add('beresol_monitor', item.get('name', ''), item.get('source_url', ''),
                    description=item.get('description', ''),
                    policy_area=item.get('policy_area', ''),
                    publisher=item.get('publisher', ''))

        for event in getattr(context_data, 'eu_calendar_events', None) or []:
            add('eu_calendar', event.get('title', 'Unknown event'),
                event.get('source_url') or event.get('agenda_url', ''),
                institution=event.get('institution', ''),
                date=event.get('start_date'),
                event_type=event.get('event_type', ''))

        tender_ctx = getattr(context_data, 'tender_context', None)
        if tender_ctx is not None:
            for tender in getattr(tender_ctx, 'tenders', None) or []:
                add('tender', tender.get('title', 'Unknown tender'),
                    tender.get('ted_url', ''),
                    publication_number=tender.get('publication_number', ''),
                    buyer_country=tender.get('buyer_country', ''),
                    value=tender.get('estimated_value'))
            for match in getattr(tender_ctx, 'user_matches', None) or []:
                tender = match.get('tender', {}) or {}
                add('tender_match', tender.get('title', 'Unknown tender'),
                    tender.get('ted_url', ''),
                    publication_number=tender.get('publication_number', ''),
                    match_score=match.get('match_score'))

        # Sequential ids so the frontend can resolve [1], [2] markers.
        for i, citation in enumerate(citations):
            citation['id'] = i + 1

        return citations

    async def get_model_info(self) -> Dict[str, Any]:
        """
        Get information about current model and fallback providers.

        Returns:
            Model information dict
        """
        info = {
            'model': self.model,
            'temperature': self.temperature,
            'max_output_tokens': self.max_output_tokens,
            'max_context_tokens': self.MAX_CONTEXT_TOKENS,
            'provider': 'open-model chain',
            'capabilities': [
                'EU legislative knowledge',
                'Source citations',
                'Context injection',
                'Streaming responses',
                'Conversation history'
            ]
        }

        # Add fallback chain info
        if self.use_fallback and self.multi_provider:
            info['fallback_enabled'] = True
            info['fallback_chain'] = self.multi_provider.available_providers
            info['provider_status'] = self.multi_provider.get_status()
        else:
            info['fallback_enabled'] = False

        return info

    async def estimate_cost(
        self,
        user_message: str,
        conversation_history: Optional[List[ChatMessage]] = None,
        use_context: bool = True
    ) -> Dict[str, float]:
        """
        Estimate API cost for a query.

        Args:
            user_message: User message
            conversation_history: Previous messages
            use_context: Whether context will be included

        Returns:
            Cost estimate:
            {
                'input_tokens': 1000,
                'output_tokens': 500,
                'cost_usd': 0.015
            }
        """
        # Rough token estimation (1 token ≈ 4 characters)
        message_tokens = len(user_message) // 4

        history_tokens = 0
        if conversation_history:
            history_tokens = sum(len(msg.content) for msg in conversation_history) // 4

        context_tokens = 0
        if use_context:
            # Average context size
            context_tokens = 2000

        input_tokens = message_tokens + history_tokens + context_tokens
        output_tokens = self.max_output_tokens

        # Chat runs on the free open-model chain (Cerebras / Gemini / Groq /
        # NVIDIA / Mistral), so the marginal cost of a chat answer is zero.
        # This used to apply Anthropic Sonnet/Opus per-million rates to every
        # estimate, which overstated chat cost by the entire bill after the
        # June 2026 migration. OpenAI is the only paid link and sits last.
        input_cost_per_million = 0.0
        output_cost_per_million = 0.0

        input_cost = (input_tokens / 1_000_000) * input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * output_cost_per_million
        total_cost = input_cost + output_cost

        return {
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': input_tokens + output_tokens,
            'cost_usd': round(total_cost, 4)
        }

    async def _load_documents(self, document_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Load documents from storage and format for Claude API.

        For PDFs > 100 pages: Extract text using pdfminer.six
        For PDFs <= 100 pages: Send as native PDF via base64
        For other formats: Send as text

        Args:
            document_ids: List of document IDs to load

        Returns:
            List of document content blocks for Claude
        """
        from services.storage.document_storage import get_document_storage
        from services.pdf_processor import get_pdf_processor

        documents = []
        storage = get_document_storage()
        pdf_processor = get_pdf_processor()

        for doc_id in document_ids:
            try:
                # Get document metadata
                doc_meta = storage.get_document(doc_id)
                if not doc_meta:
                    logger.warning(f"Document not found: {doc_id}")
                    continue

                # Read file content
                file_path = doc_meta.get('original_file_path')
                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"Document file not found: {doc_id}")
                    continue

                content_type = doc_meta.get('content_type', 'application/pdf')
                filename = doc_meta.get('filename', 'document')

                if content_type == 'application/pdf':
                    # Always extract text from PDFs for multi-provider compatibility
                    # (Mistral, OpenAI, Gemini only support text content blocks)
                    result = pdf_processor.extract_text(file_path)

                    if result['success']:
                        text = result['text']
                        page_count = result['page_count']
                        documents.append({
                            'type': 'text',
                            'text': f"**Document: {filename}** ({page_count} pages)\n\n{text[:200000]}"
                        })
                        logger.info(f"Extracted {len(text)} chars from PDF: {filename} ({page_count} pages)")
                    else:
                        logger.error(f"Failed to extract text from PDF: {result.get('error')}")
                        documents.append({
                            'type': 'text',
                            'text': f"**Document: {filename}** - Error: Could not extract text from this PDF"
                        })

                elif content_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
                    # For DOCX, extract text from processed content
                    if doc_meta.get('has_processed_content'):
                        processed = doc_meta['processed_content']
                        text = processed.get('text', '')
                        if text:
                            documents.append({
                                'type': 'text',
                                'text': f"**Document: {filename}**\n\n{text[:100000]}"
                            })
                            logger.info(f"Loaded DOCX as text: {filename} ({len(text)} chars)")
                    else:
                        # Fallback: try processing DOCX on the fly
                        try:
                            from services.document_processing.docx_processor import get_docx_processor
                            docx_proc = get_docx_processor()
                            with open(file_path, 'rb') as f:
                                docx_bytes = f.read()
                            result = docx_proc.process_docx_from_bytes(docx_bytes, filename=filename)
                            text = result.get('text', '') if result else ''
                            if text:
                                documents.append({
                                    'type': 'text',
                                    'text': f"**Document: {filename}**\n\n{text[:100000]}"
                                })
                                logger.info(f"Loaded DOCX via fallback processing: {filename} ({len(text)} chars)")
                        except Exception as docx_err:
                            logger.error(f"DOCX fallback processing failed: {docx_err}")

                elif content_type.startswith('text/'):
                    # Text files - send as text block
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    text_content = file_content.decode('utf-8', errors='ignore')
                    documents.append({
                        'type': 'text',
                        'text': f"**Document: {filename}**\n\n{text_content[:100000]}"
                    })
                    logger.info(f"Loaded text document: {filename} ({len(text_content)} chars)")

            except Exception as e:
                logger.error(f"Failed to load document {doc_id}: {str(e)}")
                continue

        return documents

    def _detect_knowledge_gap(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Detect if AI response indicates a knowledge gap (uncertainty/inability to answer).

        Args:
            response: AI response text

        Returns:
            Gap info dict if detected, None otherwise
        """
        # Patterns indicating knowledge gaps (case-insensitive)
        uncertainty_patterns = [
            r"I don'?t have (?:the )?specific",
            r"I don'?t have (?:that )?information",
            r"I cannot find",
            r"I couldn'?t find",
            r"not (?:available )?in my (?:current )?(?:context|sources|data)",
            r"I recommend checking EUR-Lex",
            r"check (?:the )?official (?:text|source)",
            r"I'?m not (?:able|certain)",
            r"I don'?t have verified",
            r"my (?:current )?sources don'?t",
            r"outside (?:of )?my (?:current )?knowledge",
            r"I'?m unable to (?:confirm|verify)",
            r"this information (?:is|may be) outdated",
        ]

        response_lower = response.lower()

        for pattern in uncertainty_patterns:
            if re.search(pattern, response_lower):
                # Try to classify what type of data is missing
                missing_type = self._classify_missing_data(response)
                return {
                    'detected': True,
                    'missing_data_type': missing_type,
                    'response_excerpt': response[:500]
                }

        return None

    def _classify_missing_data(self, response: str) -> str:
        """
        Classify what type of data is missing based on response content.

        Args:
            response: AI response text

        Returns:
            Missing data type string
        """
        response_lower = response.lower()

        # Check for specific data types mentioned
        if any(word in response_lower for word in ['fine', 'penalty', 'amount', 'euro', '€', 'million', 'billion']):
            return MissingDataType.STATISTIC
        elif any(word in response_lower for word in ['deadline', 'date', 'when', 'timeline']):
            return MissingDataType.DATE
        elif any(word in response_lower for word in ['regulation', 'directive', 'act', 'law', 'celex']):
            return MissingDataType.LEGISLATION
        elif any(word in response_lower for word in ['procedure', 'process', 'stage', 'status']):
            return MissingDataType.PROCEDURE
        elif any(word in response_lower for word in ['mep', 'member', 'rapporteur', 'shadow']):
            return MissingDataType.MEP
        elif any(word in response_lower for word in ['document', 'report', 'briefing', 'text']):
            return MissingDataType.DOCUMENT

        return MissingDataType.UNKNOWN

    async def _log_knowledge_gap(
        self,
        query: str,
        gap_info: Dict[str, Any],
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> None:
        """
        Log a detected knowledge gap to the database for later analysis.

        Args:
            query: Original user query
            gap_info: Gap detection info from _detect_knowledge_gap
            user_id: Optional user ID
            conversation_id: Optional conversation ID
        """
        try:
            # Run database operation in thread pool to avoid blocking
            import asyncio
            from functools import partial

            def _save_gap():
                db = SessionLocal()
                try:
                    # Try to detect policy area from query
                    policy_area = self._detect_policy_area(query)

                    gap = KnowledgeGap(
                        query=query,
                        detected_topic=query[:200],  # Truncate for topic field
                        policy_area=policy_area,
                        missing_data_type=gap_info.get('missing_data_type', MissingDataType.UNKNOWN),
                        user_id=user_id if user_id else None,
                        conversation_id=conversation_id,
                        ai_response_excerpt=gap_info.get('response_excerpt', '')[:500]
                    )
                    db.add(gap)
                    db.commit()
                    logger.info(f"Logged knowledge gap: {gap.id} - {gap.missing_data_type}")
                except Exception as e:
                    logger.error(f"Failed to log knowledge gap: {e}")
                    db.rollback()
                finally:
                    db.close()

            # Run in executor to avoid blocking async context
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _save_gap)

        except Exception as e:
            logger.error(f"Error in _log_knowledge_gap: {e}")

    def _detect_policy_area(self, query: str) -> Optional[str]:
        """
        Try to detect EU policy area from query text.

        Args:
            query: User query

        Returns:
            Policy area string or None
        """
        query_lower = query.lower()

        # Policy area keywords mapping
        policy_keywords = {
            'Digital': ['digital', 'ai act', 'dsa', 'dma', 'gdpr', 'data', 'cyber', 'platform'],
            'Environment': ['environment', 'climate', 'green deal', 'emissions', 'carbon', 'cbam', 'sustainability'],
            'Trade': ['trade', 'tariff', 'customs', 'export', 'import', 'wto'],
            'Agriculture': ['agriculture', 'cap', 'farming', 'food', 'rural'],
            'Finance': ['finance', 'banking', 'euro', 'ecb', 'monetary', 'fiscal'],
            'Energy': ['energy', 'electricity', 'gas', 'renewable', 'nuclear'],
            'Transport': ['transport', 'aviation', 'maritime', 'rail', 'mobility'],
            'Health': ['health', 'pharmaceutical', 'ema', 'medicine', 'vaccine'],
            'Justice': ['justice', 'asylum', 'migration', 'border', 'schengen', 'police'],
            'Internal Market': ['internal market', 'single market', 'harmonisation', 'standardisation'],
        }

        for area, keywords in policy_keywords.items():
            if any(keyword in query_lower for keyword in keywords):
                return area

        return None

    def _extract_source_tiers(self, citations: List[Dict[str, Any]]) -> List[int]:
        """
        Extract source tiers from citations for analytics.

        Args:
            citations: List of citation dictionaries

        Returns:
            List of unique source tier integers
        """
        tiers = set()
        for citation in citations:
            tier = citation.get('source_tier')
            if tier:
                tiers.add(tier)
        return sorted(list(tiers))

    async def _log_analytics(
        self,
        user_id: Optional[str],
        provider: str,
        model: str,
        tokens_used: int,
        response_time_ms: float,
        search_time_ms: float,
        had_knowledge_gap: bool,
        knowledge_gap_type: Optional[str],
        source_tiers_used: List[int],
        citation_count: int,
        context_sources_count: int,
        query_length: int,
        response_length: int
    ) -> None:
        """
        Log analytics for monitoring dashboard (Phase E1).

        Args:
            Various metrics from chat response
        """
        try:
            def _save_analytics():
                db = SessionLocal()
                try:
                    analytics = ChatAnalytics(
                        user_id=user_id if user_id else None,
                        provider=provider,
                        model=model,
                        tokens_used=tokens_used,
                        response_time_ms=response_time_ms,
                        search_time_ms=search_time_ms,
                        had_knowledge_gap=had_knowledge_gap,
                        knowledge_gap_type=knowledge_gap_type,
                        source_tiers_used=source_tiers_used if source_tiers_used else None,
                        citation_count=citation_count,
                        context_sources_count=context_sources_count,
                        query_length=query_length,
                        response_length=response_length
                    )
                    db.add(analytics)
                    db.commit()
                    logger.debug(f"Logged analytics: {analytics.id}")
                except Exception as e:
                    logger.error(f"Failed to log analytics: {e}")
                    db.rollback()
                finally:
                    db.close()

            # Run in executor to avoid blocking async context
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _save_analytics)

        except Exception as e:
            logger.error(f"Error in _log_analytics: {e}")

    def _build_safe_refusal_response(
        self, query: str, violations, context_str: str = ""
    ) -> str:
        """
        Build a safe refusal response that ships when the validator flags a
        critical violation (added 28 May 2026 after the EFPIA-demo Biotech Act
        / Andriukaitis fabrication incident).

        The template explicitly tells the user which kinds of claims Brubru
        cannot confirm and points them to the My Tracked Files so they can
        be alerted when the data lands. It does NOT repeat any of the
        problematic content from the original response.

        Localised into Brubru's six languages on 28 Jul 2026 (audit defect D3):
        the template was hardcoded English, so a Catalan or Spanish user who hit
        the guard got a wall of English. The refusal is the single worst moment
        to switch language on someone.
        """
        violation_types = {v.type for v in (violations or [])}
        lang = _detect_query_language(query)
        t = _SAFE_REFUSAL_TEXT.get(lang, _SAFE_REFUSAL_TEXT["EN"])

        lines = [t["lead"]]

        if "user_claim_capitulation" in violation_types or "name_splitting" in violation_types:
            lines.append(t["user_claim"])
        if "fabricated_meeting" in violation_types:
            lines.append(t["meeting"])
        if "fabricated_future_date" in violation_types:
            lines.append(t["future_date"])
        if "hallucination" in violation_types and not (
            "user_claim_capitulation" in violation_types
            or "name_splitting" in violation_types
            or "fabricated_meeting" in violation_types
            or "fabricated_future_date" in violation_types
        ):
            lines.append(t["hallucination"])
        if "completeness" in violation_types and not violation_types & {
            "user_claim_capitulation",
            "name_splitting",
            "fabricated_meeting",
            "fabricated_future_date",
            "hallucination",
        }:
            lines.append(t["completeness"])

        # Name what retrieval DID find. A bare refusal reads as "Brubru knows
        # nothing"; naming the guides that were actually retrieved shows the
        # user there is a thread to pull, and turns a dead end into a follow-up
        # (audit defect D3, 28 Jul 2026: a two-word query got a pure wall).
        anchors = self._retrieved_guide_titles(context_str)
        if anchors:
            lines.append(t["on_record"].format(items="; ".join(anchors)))

        lines.append(t["offer"])

        return "\n\n".join(lines)

    # "<Act name> (Regulation (EU) 2019/785 ...)" -- an act named, then given a
    # regulation number in apposition. The number is what goes wrong.
    _ACT_NUMBER_APPOSITION_RE = re.compile(
        r"\(\s*(?:Regulation|Directive|Decision)\s*\((?:EU|EC|EEC|Euratom)\)\s*"
        r"(?:No\.?\s*)?(\d{4})/(\d{1,4})"      # the asserted year/number
        r"[^()]*"                               # any trailing prose
        r"(?:\[CELEX:[^\]]+\]\([^)]*\))?"      # an optional linkified CELEX
        r"[^()]*\)",
        re.IGNORECASE,
    )

    # A spaced em/en dash used as an appositive or parenthetical break. Folding
    # it to a comma is grammatical in all six Brubru languages ("X — the Y — is
    # Z" becomes "X, the Y, is Z"). Digit-flanked dashes are ranges and are left
    # alone, as are dashes already adjacent to a comma.
    _PROSE_DASH_RE = re.compile(r"(?<![\d,])\s*[—–]\s*(?![\d,])")

    def _fold_prose_dashes(self, text: str) -> str:
        """
        Remove em/en dashes from user-facing answer prose (audit defect D7,
        28 Jul 2026: a Catalan answer shipped an em-dash, against the
        zero-em-dash rule for every Brubru surface).

        The model is copying the system prompt's own typography, which is
        littered with em-dashes. Rather than rewrite the prompt and risk
        perturbing behaviour, fold the dash out of the OUTPUT, where the rule
        actually applies. Markdown tables, code fences and URLs are skipped:
        a dash is structural there, not punctuation.
        """
        if not text or ("—" not in text and "–" not in text):
            return text

        out_lines: List[str] = []
        in_code_fence = False
        for line in text.split("\n"):
            stripped = line.lstrip()
            if stripped.startswith("```"):
                in_code_fence = not in_code_fence
                out_lines.append(line)
                continue
            if in_code_fence or stripped.startswith("|") or stripped.startswith("    "):
                out_lines.append(line)
                continue
            # Protect URLs, then fold, then restore.
            urls: List[str] = []

            def _stash(match: "re.Match") -> str:
                urls.append(match.group(0))
                return f"\x00{len(urls) - 1}\x00"

            protected = re.sub(r"https?://[^\s\)\]]+", _stash, line)
            folded = self._PROSE_DASH_RE.sub(", ", protected)
            for idx, url in enumerate(urls):
                folded = folded.replace(f"\x00{idx}\x00", url)
            out_lines.append(folded)

        result = "\n".join(out_lines)
        # A folded dash before punctuation leaves ", ." style debris.
        result = re.sub(r",\s*([.,;:!?])", r"\1", result)
        return result

    # Catalan forms the models get wrong most often. Applied only when the query
    # language is Catalan (audit defect D7, 28 Jul 2026: "per a que" and
    # "la aprovi" both shipped to a subscriber in one answer).
    _CATALAN_CORRECTIONS = (
        (r"\bper a què\b", "perquè"),
        (r"\bper a que\b", "perquè"),
        (r"\bper que\b", "perquè"),
        (r"\bla aprovi\b", "l'aprovi"),
        (r"\bla aprova\b", "l'aprova"),
        (r"\bla adopti\b", "l'adopti"),
        (r"\bla aplica\b", "l'aplica"),
        (r"\bes debatuda\b", "és debatuda"),
    )

    def _apply_catalan_corrections(self, text: str, query: str) -> str:
        """Fix the recurring Catalan slips, but only on Catalan answers."""
        if not text or _detect_query_language(query) != "CA":
            return text
        result = text
        for pattern, replacement in self._CATALAN_CORRECTIONS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        return result

    def _strip_contradicting_act_numbers(self, text: str) -> str:
        """
        Remove a regulation number stated in apposition to a named act when it
        contradicts that act's canonical number.

        Audit defect D2 (28 Jul 2026): an answer rendered the AI Act as
        "[AI Act](...CELEX:32024R1689) (Regulation (EU) 2019/785
        [CELEX:32019R0785](...))". The link was right, the apposition was
        invented, and the linkifier then dressed the invention as a real
        EUR-Lex URL. Truncating to the act name alone is always safe: the
        canonical link is already in the text.

        Only fires when the act name is in legislation_acronyms.json AND the
        asserted number differs from the canonical one, so a legitimate
        "the AI Act (amending Regulation (EU) 2018/1139)" is untouched: that
        parenthetical does not open with a bare number in apposition, it opens
        with a verb.
        """
        if not text or "(" not in text:
            return text

        acronyms = self._get_legislation_acronyms()
        if not acronyms:
            return text

        def _canonical_number(celex: str) -> Optional[str]:
            m = re.match(r"^\d(\d{4})[A-Z]{1,2}(\d{4})$", celex or "")
            if not m:
                return None
            return f"{m.group(1)}/{int(m.group(2))}"

        result = text
        for name, entry in acronyms.items():
            if len(name) < 3:
                continue
            canonical = _canonical_number((entry or {}).get("celex", ""))
            if not canonical:
                continue
            for name_match in re.finditer(re.escape(name) + r"\b", result):
                tail_start = name_match.end()
                # Only look immediately after the act name. The name is often
                # the label of a markdown link, so skip an optional "](url)"
                # closer and any whitespace before testing for the apposition.
                gap = re.compile(r"(?:\]\([^)\s]*\))?\s*").match(result, tail_start)
                appos = self._ACT_NUMBER_APPOSITION_RE.match(result, gap.end())
                if not appos:
                    continue
                asserted = f"{appos.group(1)}/{int(appos.group(2))}"
                if asserted == canonical:
                    continue
                logger.warning(
                    "[post] dropped contradicting act number for %s: asserted %s, canonical %s",
                    name, asserted, canonical,
                )
                result = result[:appos.start()] + result[appos.end():]
                break  # positions shifted; the next pass over names re-scans
        return re.sub(r"\s{2,}", " ", result).replace(" .", ".").replace(" ,", ",")

    def _get_legislation_acronyms(self) -> Dict[str, Dict[str, Any]]:
        """Cached accessor for the acronym -> canonical CELEX map."""
        cached = getattr(self, "_legislation_acronyms_cache", None)
        if cached is not None:
            return cached
        data: Dict[str, Dict[str, Any]] = {}
        try:
            path = (
                Path(__file__).resolve().parent.parent
                / "knowledge_base" / "institutions" / "legislation_acronyms.json"
            )
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh).get("acronyms", {}) or {}
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not load legislation acronyms: %s", exc)
        self._legislation_acronyms_cache = data
        return data

    @staticmethod
    def _retrieved_guide_titles(context_str: str, limit: int = 3) -> List[str]:
        """
        Pull the human-readable guide titles out of the injected context string,
        so a refusal can still tell the user what Brubru does hold on the topic.
        Guides are injected with a "## <Title>" heading by the knowledge loader.
        """
        if not context_str:
            return []
        titles: List[str] = []
        for match in re.finditer(r"^#{1,3}\s+([^\n#][^\n]{3,80})$", context_str, flags=re.MULTILINE):
            title = match.group(1).strip().rstrip(":")
            # Skip internal block headers -- they are scaffolding, not content.
            if title.isupper():
                continue
            if title not in titles:
                titles.append(title)
            if len(titles) >= limit:
                break
        return titles

    async def _log_chat_validation(
        self,
        query: str,
        response: str,
        context_length: int,
        generator: Optional[str],
        language: Optional[str],
        result,
        shadow_mode: bool,
        user_id: Optional[str],
    ) -> None:
        """
        Persist one validator pass to chat_validations.

        Fail-soft: any DB error is logged but never propagated. The validator
        is observability; it must not break the chat path. Workstream 1
        (memory/project_chat_ai_architecture_evolution.md).
        """
        try:
            from services.ai.validator_settings import (
                VALIDATOR_QUERY_TRUNCATE,
                VALIDATOR_RESPONSE_TRUNCATE,
            )
            from models.chat_validation import ChatValidation

            def _save_validation():
                db = SessionLocal()
                try:
                    row = ChatValidation(
                        query=(query or "")[:VALIDATOR_QUERY_TRUNCATE],
                        response_excerpt=(response or "")[:VALIDATOR_RESPONSE_TRUNCATE],
                        validator_model=result.validator_model,
                        generator=generator,
                        language=(language or "").lower()[:8] or None,
                        passed=result.passed,
                        severity=result.severity,
                        violation_count=len(result.violations),
                        violations=[v.to_dict() for v in result.violations],
                        latency_ms=result.latency_ms,
                        context_length=context_length,
                        shadow_mode=shadow_mode,
                        error=result.error,
                        user_id=user_id if user_id else None,
                    )
                    db.add(row)
                    db.commit()
                except Exception as exc:  # noqa: BLE001
                    logger.error(f"Failed to log chat validation: {exc}")
                    db.rollback()
                finally:
                    db.close()

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _save_validation)

        except Exception as e:  # noqa: BLE001
            logger.error(f"Error in _log_chat_validation: {e}")


# Global singleton
_ai_service: Optional[AIService] = None


def get_ai_service(
    api_key: Optional[str] = None,
    context_builder: Optional[ContextBuilder] = None,
    model: str = AIService.MODEL_SONNET
) -> AIService:
    """
    Get global AI service instance.

    Args:
        api_key: Anthropic API key (defaults to settings.ANTHROPIC_API_KEY)
        context_builder: Context builder instance
        model: Claude model to use

    Returns:
        AIService instance
    """
    global _ai_service

    if _ai_service is None:
        # api_key is vestigial: chat generates only through the open-model
        # chain, which reads its own per-provider keys. Kept so existing
        # callers that pass one keep working.
        _ai_service = AIService(
            api_key=api_key,
            context_builder=context_builder or get_context_builder(),
            model=model
        )

    return _ai_service
