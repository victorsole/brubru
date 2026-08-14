"""
Context Builder for AI

Builds comprehensive EU context from user queries for AI chat responses.
Part of Phase 13: AI Context Injection - Task 13.4

Critical function: build_context_for_query()
- Semantic search for relevant documents
- Entity extraction (CELEX, procedures, MEPs)
- Live API calls for detected entities
- Recent RSS updates
- Formatted context for AI consumption
"""

import logging
import re
import asyncio
import unicodedata
from typing import List, Dict, Any, Optional, Set, Tuple, TYPE_CHECKING
from datetime import date, datetime, timedelta
from dataclasses import dataclass, field

from services.search.hybrid_search import HybridSearch, get_hybrid_search, semantic_store_available
from services.indexing.metadata_extractor import MetadataExtractor, get_metadata_extractor
# EPRSIndexer is NOT imported at module level: services.indexing.eprs_indexer imports
# services.vector_db.vector_store (chromadb + onnxruntime, ~200 MB resident). In
# production the vector store is empty, so the EPRS ChromaDB pass returns nothing and
# the PostgreSQL pass carries EPRS retrieval. The indexer is imported and constructed
# only when a populated store exists (see __init__ below), so the boot path stays light.
if TYPE_CHECKING:  # pragma: no cover
    from services.indexing.eprs_indexer import EPRSIndexer
# EPRSMatcher is NOT imported at module level either: it wraps the EPRSIndexer, so it
# transitively pulls chromadb. All of its matching runs on the vector store (no
# PostgreSQL path), so on an empty production store it returns nothing. Constructed and
# imported only when a populated store exists (see __init__ below).
if TYPE_CHECKING:  # pragma: no cover
    from services.matching.eprs_matcher import EPRSMatcher
from .ai_summary_generator import AISummaryGenerator, get_ai_summary_generator  # Phase 5: AI summaries
from .freshness_detector import FreshnessDetector, get_freshness_detector  # Phase 5: Freshness detection
from .tender_context_provider import TenderContextProvider, get_tender_context_provider, TenderIntent, TenderContextData  # Phase 8: Tender chat
from services.api_clients.eurlex_client import EURLexClient
from services.api_clients.oeil_client import OEILClient
from services.api_clients.european_parliament_client import EuropeanParliamentClient
from services.api_clients.tavily_client import TavilyClient, get_tavily_client, TavilySearchResponse
# from services.scrapers.rss_manager import RSSManager  # TODO: Fix - RSSManager doesn't exist
from knowledge_base.reference_data import ReferenceDataService, get_reference_data_service
from knowledge_base.knowledge_loader import KnowledgeLoader, get_knowledge_loader
from knowledge_base.beresol_knowledge_loader import BeresolKnowledgeLoader, get_beresol_knowledge_loader
from models.legislative_train import LegislativeTrain, LegislativeCarriage
from models.committee_work import CommitteeWorkItem, ProcedureTypeEnum
from models.public_consultation import PublicConsultation, ConsultationStatusEnum
from models.commission_document import CommissionDocument
from knowledge_base.ep_committees import EP_COMMITTEE_BY_CODE
from knowledge_base.ec_consultations import DGS, PolicyArea, get_dg_full_name
from core.database import SessionLocal

logger = logging.getLogger(__name__)


def _enum_str(value, default: str) -> str:
    """Return the string form of a column that may be an Enum or a plain string.

    committee_work_items stores procedure_type / committee_role / status as plain
    TEXT (the scraper writes 'DEA', 'LEAD', 'IN_COMMITTEE'), but this module read
    them as `.value` on an Enum. On a str that raises AttributeError, and because
    the surrounding try/except swallowed it and returned [], committee work items
    NEVER reached chat context for any user. Found 5 Aug 2026 while populating a
    real user's Committee Work tab.
    """
    if value is None:
        return default
    return getattr(value, "value", value)



# Phase C: Source Tier Hierarchy for citation trustworthiness
# Tier 1 = Most authoritative, Tier 5 = Least authoritative
SOURCE_TIERS = {
    # Tier 1: Official legal text (highest authority)
    'eurlex': 1,
    'celex': 1,
    'legislation': 1,

    # Tier 2: Legislative observatory and official EP data
    'oeil': 2,
    'procedure': 2,
    'ep_official': 2,
    'mep': 2,
    'committee': 2,

    # Tier 3: News and updates from official sources
    'rss_feeds': 3,
    'news': 3,
    'press_release': 3,

    # Tier 4: Curated knowledge and analysis
    'knowledge_base': 4,
    'eprs': 4,
    'search_result': 4,
    'internal': 4,

    # Tier 4.5: EU institutional search (official .europa.eu + trusted policy media)
    'eu_institutional_search': 4,

    # Tier 5: Real-time web search (lowest authority, needs verification)
    'web_search': 5,
    'tavily': 5,
    'tender': 4,
    'tender_match': 4,

    # Beresol open reports/monitors (Tier 4 - curated analysis from Brubru's company)
    'beresol_report': 4,
    'beresol_monitor': 4,

    # EP Committee Work in Progress (Tier 4 - curated EP committee data)
    'committee_work': 4,

    # EC Public Consultations (Tier 3 - official EC "Have Your Say" portal)
    'public_consultation': 3,

    # EC Commission Documents (Tier 2 - official EC Register proposals and legislation)
    'commission_document': 2,

    # EU Calendar Events (Tier 2 - official institutional calendar data with exact dates)
    'eu_calendar': 2,

    # User uploaded documents (Tier 4 - user-provided reference material)
    'user_uploaded': 4,
}


def get_source_tier(source_type: str) -> int:
    """Get the authority tier for a source type (1=highest, 5=lowest)"""
    return SOURCE_TIERS.get(source_type, 4)  # Default to Tier 4


# Phase 4: Tenderator bridge entity extractors. Small enough to stay
# inline (no separate module). All regexes are compiled lazily.
_TOPIC_ID_RE = re.compile(
    r"\b(?:HORIZON|HE|DIGITAL|DEP|LIFE|CEF|EU4H|EU4HEALTH|ERASMUS|EIC|CREA|JTM|AMIF|ISF|BMVI)"
    r"[-_][A-Z0-9]+(?:[-_][A-Z0-9]+){2,8}\b",
    re.IGNORECASE,
)

_PROGRAMME_ALIASES = [
    # (canonical, [regex aliases])
    ("HORIZON", re.compile(r"\b(?:horizon\s+europe|horizon)\b", re.IGNORECASE)),
    ("LIFE", re.compile(r"\b(?:LIFE\s+programme|LIFE)\b")),
    ("CEF", re.compile(r"\b(?:connecting\s+europe\s+facility|CEF)\b", re.IGNORECASE)),
    ("DEP", re.compile(r"\b(?:digital\s+europe\s+programme|digital\s+europe|DEP)\b", re.IGNORECASE)),
    ("EU4H", re.compile(r"\b(?:EU4Health|EU\s*for\s*Health)\b", re.IGNORECASE)),
    ("ERASMUS", re.compile(r"\b(?:erasmus\s*\+|erasmus\s*plus|erasmus)\b", re.IGNORECASE)),
    ("CREA", re.compile(r"\b(?:creative\s+europe|CREA)\b", re.IGNORECASE)),
    ("EIC", re.compile(r"\b(?:european\s+innovation\s+council|EIC\s+accelerator|EIC)\b", re.IGNORECASE)),
    ("H2020", re.compile(r"\bH2020\b")),
    ("FP7", re.compile(r"\bFP7\b")),
]

# EU agency acronyms → economy_items.body_code. Used to route a Chat query
# that mentions a decentralised agency straight into the Tenderator's
# `source=agency&body=<slug>` view. Acronyms that collide with common
# vocabulary (FRA = France, ERA = era, EEA = European Economic Area) are
# scoped to ALL-CAPS-only matches; the rest are case-insensitive.
_AGENCY_ALIASES = [
    # (body_code, regex)
    ("efca", re.compile(r"\bEFCA\b")),
    ("cedefop", re.compile(r"\bCedefop\b", re.IGNORECASE)),
    ("ema", re.compile(r"\bEMA\b")),
    ("efsa", re.compile(r"\bEFSA\b")),
    ("eurojust", re.compile(r"\bEurojust\b", re.IGNORECASE)),
    ("etf", re.compile(r"\bETF\b")),
    ("eige", re.compile(r"\bEIGE\b")),
    ("euaa", re.compile(r"\bEUAA\b")),
    ("fra", re.compile(r"\bFRA\b")),          # all-caps only — avoids "France" collisions
    ("era", re.compile(r"\bERA\b")),          # all-caps only — avoids "era" word
    ("eurofound", re.compile(r"\bEurofound\b", re.IGNORECASE)),
    ("eea", re.compile(r"\bEEA\b")),          # all-caps only
    ("echa", re.compile(r"\bECHA\b")),
    ("euda", re.compile(r"\bEUDA\b")),
    ("ecdc", re.compile(r"\bECDC\b")),
    ("enisa", re.compile(r"\bENISA\b")),
    ("eu_osha", re.compile(r"\bEU[-\s]?OSHA\b")),
]


def _extract_funding_topic_ids(text: str) -> List[str]:
    """Pull EU funding topic_ids out of free-form chat text. e.g.
    HORIZON-CL4-2026-DIGITAL-EMERGING-01-01."""
    if not text:
        return []
    seen = set()
    out: List[str] = []
    for m in _TOPIC_ID_RE.finditer(text):
        token = m.group(0).upper()
        if token not in seen and "-" in token and len(token) >= 12:
            seen.add(token)
            out.append(token)
    return out[:5]


def _extract_funding_programmes(text: str) -> List[str]:
    """Canonical programme codes named in the text. Returns a stable
    ordered list with duplicates removed."""
    if not text:
        return []
    out: List[str] = []
    seen = set()
    for code, regex in _PROGRAMME_ALIASES:
        if code in seen:
            continue
        if regex.search(text):
            seen.add(code)
            out.append(code)
    return out


def _extract_agency_codes(text: str) -> List[str]:
    """Decentralised EU agency acronyms named in the text → body_code list
    (e.g. 'EFSA tenders' → ['efsa']). Stable, deduped, in regex order."""
    if not text:
        return []
    out: List[str] = []
    seen = set()
    for code, regex in _AGENCY_ALIASES:
        if code in seen:
            continue
        if regex.search(text):
            seen.add(code)
            out.append(code)
    return out


# Identity fields a knowledge guide carries in its QUICK FACTS block. These are
# the guide's stable "what is this act" facts, as opposed to the dated LATEST
# bullets that accumulate above them. Matched case-insensitively at the start of
# a markdown bullet, tolerating bold markers: "- **CELEX**:" / "- CELEX:".
_GUIDE_IDENTITY_FIELDS = (
    "celex", "eli", "full name", "official title", "type", "status",
    "procedure", "legal basis", "commission proposal", "ep adoption",
    "council adoption", "entry into force", "applies from", "application date",
    "deadline", "transposition", "lead ep committee", "lead ep committees",
    "committee", "rapporteur", "rapporteurs", "co-rapporteur", "co-rapporteurs",
    "responsible commissioner", "commissioner", "lead dg", "dg",
    "max penalty", "penalties", "oj reference", "brubru deep-dive",
)

_GUIDE_IDENTITY_RE = re.compile(
    r"^[ \t]*[-*][ \t]+\*{0,2}(" + "|".join(re.escape(f) for f in _GUIDE_IDENTITY_FIELDS) + r")\*{0,2}[ \t]*:",
    re.IGNORECASE,
)


def guide_excerpt(content: str, budget: int = 4000, identity_reserve: int = 1000) -> str:
    """Truncate a knowledge guide to `budget` chars WITHOUT losing its identity facts.

    Why this exists (28 July 2026). Guides are loaded at 8,000 chars but this
    module re-truncated them to 4,000 with a plain slice. Guides accumulate a
    dated "LATEST" bullet at the TOP of QUICK FACTS on every refresh, and those
    bullets are long. Measured across all 535 guides carrying a QUICK FACTS
    block: 102 (19%) had QUICK FACTS running past the 4,000-char cap, and 6 lost
    their own CELEX line entirely. The flagship `ai_act_regulation` guide keeps
    `CELEX: 32024R1689` at char 6,057 — it never reached the model, so the chat
    was answering AI Act questions with the act's own identifier truncated away.

    Strategy: keep the plain head slice (so the newest LATEST bullets still lead,
    which is what recency-sensitive answers need), but reserve a slice of the
    same budget for identity bullets that fall past the cut, and append those.
    Total stays within `budget`, so the prompt does not grow.

    Guides shorter than `budget` are returned untouched — no behaviour change for
    the ~81% of guides that already fit.

    SCOPE IS DELIBERATELY THE QUICK FACTS BLOCK ONLY. Later `##` sections of a
    guide describe OTHER documents (committee own-initiative reports, related
    procedures) and carry their own `- **Rapporteur:** ...` bullets. Rescuing
    those would strand a foreign name next to the act's identity facts — on
    `ai_act_regulation` an unscoped scan lifted the AFCO draft-report rapporteur
    (Kefalogiannis) to sit beside the AI Act, whose rapporteurs are Benifei and
    Tudorache. That is precisely the fabrication this function exists to prevent.
    """
    if not content:
        return ""
    if len(content) <= budget:
        return content

    # Restrict the rescue to the QUICK FACTS block — the guide's own identity
    # section. Mirrors KnowledgeLoader._extract_quick_facts.
    qf = re.search(r"##\s*QUICK\s*FACTS\s*\n(.*?)(?=\n##\s|\Z)", content, re.DOTALL | re.IGNORECASE)
    if not qf:
        return content[:budget]
    scan_from = max(budget, qf.start())
    scan_region = content[scan_from:qf.end()]

    marker = "\n[... guide truncated; key identifiers preserved below ...]\n"
    # Never let the rescued block crowd out the head. Capped at half the budget
    # so a small `budget` cannot overflow (at budget=4000 this is a no-op: the
    # 1,000-char reserve is well under the 1,970 ceiling).
    reserve = min(identity_reserve, max(0, (budget - len(marker)) // 2))
    if reserve <= 0:
        return content[:budget]

    # Identity bullets living beyond the plain cut-off, in document order.
    rescued: List[str] = []
    used = 0
    for line in scan_region.splitlines():
        if not _GUIDE_IDENTITY_RE.match(line):
            continue
        line = line.rstrip()
        # Skip anything already visible in the head slice.
        if line.strip() in content[:budget]:
            continue
        if used + len(line) + 1 > reserve:
            break
        rescued.append(line)
        used += len(line) + 1

    if not rescued:
        return content[:budget]

    head_budget = max(0, budget - used - len(marker))
    return content[:head_budget] + marker + "\n".join(rescued)


def _resolve_event_location(institution: Optional[str], title: Optional[str], week_type: Optional[str]) -> str:
    """
    Resolve an EU institutional event's city for the TODAY BLOCK.

    Precedence:
      1. Explicit city mention in the event title (Strasbourg / Luxembourg / Brussels).
      2. EP and Commission default to Strasbourg during plenary weeks, Brussels otherwise.
      3. Council, European Council, and any other institution default to Brussels.

    This is shown verbatim to the LLM so it does not have to infer where a
    same-day Council meeting happens just because the College is in Strasbourg.
    """
    title_lower = (title or "").lower()
    for city in ("strasbourg", "luxembourg", "brussels"):
        if city in title_lower:
            return city.capitalize()
    inst = (institution or "").upper()
    is_plenary = "plenary" in (week_type or "").lower()
    if inst in ("EP", "COMMISSION"):
        return "Strasbourg" if is_plenary else "Brussels"
    return "Brussels"


# Policy topic keywords -> DG codes mapping
# Used to resolve "who should I contact about X?" queries to real EC personnel
POLICY_TO_DG = {
    'agriculture': ['AGRI'],
    'agrifood': ['AGRI', 'SANTE'],
    'agri-food': ['AGRI', 'SANTE'],
    'food': ['AGRI', 'SANTE'],
    'farming': ['AGRI'],
    'rural': ['AGRI'],
    'fisheries': ['MARE'],
    'maritime': ['MARE'],
    'climate': ['CLIMA'],
    'environment': ['ENV', 'CLIMA'],
    'green deal': ['ENV', 'CLIMA'],
    'digital': ['CNECT'],
    'technology': ['CNECT'],
    'telecom': ['CNECT'],
    'cyber': ['CNECT'],
    'trade': ['TRADE'],
    'tariff': ['TRADE', 'TAXUD'],
    'health': ['SANTE'],
    'pharmaceutical': ['SANTE'],
    'transport': ['MOVE'],
    'mobility': ['MOVE'],
    'energy': ['ENER'],
    'nuclear': ['ENER'],
    'competition': ['COMP'],
    'antitrust': ['COMP'],
    'state aid': ['COMP'],
    'internal market': ['GROW'],
    'industry': ['GROW'],
    'sme': ['GROW'],
    'defence': ['DEFIS'],
    'space': ['DEFIS'],
    'budget': ['BUDG'],
    'financial': ['FISMA', 'ECFIN'],
    'banking': ['FISMA'],
    'economy': ['ECFIN'],
    'euro': ['ECFIN'],
    'tax': ['TAXUD'],
    'customs': ['TAXUD'],
    'employment': ['EMPL'],
    'social': ['EMPL'],
    'education': ['EAC'],
    'culture': ['EAC'],
    'youth': ['EAC'],
    'research': ['RTD'],
    'innovation': ['RTD'],
    'regional': ['REGIO'],
    'cohesion': ['REGIO'],
    'migration': ['HOME'],
    'asylum': ['HOME'],
    'security': ['HOME'],
    'justice': ['JUST'],
    'fundamental rights': ['JUST'],
    'enlargement': ['NEAR'],
    'neighbourhood': ['NEAR'],
    'humanitarian': ['ECHO'],
    'development': ['INTPA'],
    'international partnerships': ['INTPA'],
}

# Contact-intent phrases that trigger broader DG code detection
CONTACT_INTENT_PHRASES = [
    # English
    'who should i contact', 'who to contact', 'who to talk to',
    'who is responsible', 'who is in charge', 'who handles',
    'who deals with', 'contact person', 'point of contact',
    'who can i reach', 'who works on', 'who do i contact',
    'who should i reach out to', 'who should i write to',
    'who heads', 'who leads', 'who runs', 'who directs',
    'director of', 'head of unit', 'head of', 'director-general',
    # Spanish
    'quién es el responsable', 'a quién contactar', 'persona de contacto',
    'quién se encarga', 'quién dirige', 'quién lidera',
    'director general de', 'jefe de unidad', 'jefe de',
    'quién trabaja en', 'contacto de',
    # Catalan
    'qui és el responsable', 'a qui contactar', 'persona de contacte',
    'qui s\'encarrega', 'qui dirigeix', 'qui lidera',
    'director general de', 'cap d\'unitat', 'cap de',
    'qui treballa a', 'contacte de',
    # French
    'qui est responsable', 'qui contacter', 'personne de contact',
    'qui est en charge', 'qui dirige', 'qui gère',
    'directeur général de', 'chef d\'unité', 'chef de',
    'qui travaille', 'point de contact',
    # Dutch
    'wie is verantwoordelijk', 'wie contacteren', 'contactpersoon',
    'wie is belast met', 'wie leidt', 'wie beheert',
    'directeur-generaal van', 'hoofd van', 'wie werkt bij',
    # Italian
    'chi è il responsabile', 'chi contattare', 'persona di contatto',
    'chi è incaricato', 'chi dirige', 'chi gestisce',
    'direttore generale di', 'capo unità', 'capo di',
    'chi lavora', 'punto di contatto',
]

# Country name to demonym mapping for rapporteur-by-country queries
COUNTRY_DEMONYMS = {
    'spanish': 'Spain', 'spain': 'Spain', 'espanol': 'Spain', 'espanyol': 'Spain',
    'french': 'France', 'france': 'France', 'francais': 'France', 'frances': 'France',
    'german': 'Germany', 'germany': 'Germany', 'aleman': 'Germany', 'alemany': 'Germany',
    'italian': 'Italy', 'italy': 'Italy', 'italiano': 'Italy', 'italia': 'Italy',
    'dutch': 'Netherlands', 'netherlands': 'Netherlands', 'holandes': 'Netherlands', 'neerlandes': 'Netherlands',
    'belgian': 'Belgium', 'belgium': 'Belgium', 'belga': 'Belgium',
    'polish': 'Poland', 'poland': 'Poland', 'polaco': 'Poland',
    'romanian': 'Romania', 'romania': 'Romania', 'rumano': 'Romania',
    'greek': 'Greece', 'greece': 'Greece', 'griego': 'Greece', 'grec': 'Greece',
    'portuguese': 'Portugal', 'portugal': 'Portugal', 'portugues': 'Portugal',
    'swedish': 'Sweden', 'sweden': 'Sweden', 'sueco': 'Sweden', 'suec': 'Sweden',
    'danish': 'Denmark', 'denmark': 'Denmark', 'danes': 'Denmark',
    'finnish': 'Finland', 'finland': 'Finland', 'finlandes': 'Finland',
    'irish': 'Ireland', 'ireland': 'Ireland', 'irlandes': 'Ireland',
    'austrian': 'Austria', 'austria': 'Austria', 'austriaco': 'Austria',
    'czech': 'Czechia', 'czechia': 'Czechia',
    'hungarian': 'Hungary', 'hungary': 'Hungary', 'hungaro': 'Hungary',
    'bulgarian': 'Bulgaria', 'bulgaria': 'Bulgaria',
    'croatian': 'Croatia', 'croatia': 'Croatia', 'croata': 'Croatia',
    'slovak': 'Slovakia', 'slovakia': 'Slovakia',
    'slovenian': 'Slovenia', 'slovenia': 'Slovenia',
    'estonian': 'Estonia', 'estonia': 'Estonia',
    'latvian': 'Latvia', 'latvia': 'Latvia',
    'lithuanian': 'Lithuania', 'lithuania': 'Lithuania',
    'cypriot': 'Cyprus', 'cyprus': 'Cyprus',
    'maltese': 'Malta', 'malta': 'Malta',
    'luxembourgish': 'Luxembourg', 'luxembourg': 'Luxembourg',
}

# Rapporteur-intent phrases
RAPPORTEUR_INTENT_PHRASES = [
    'rapporteur', 'rapporteurs', 'ponente', 'ponentes', 'ponent', 'ponents',
    'relator', 'relatores', 'berichterstatter',
    # Shadow rapporteur variants (triggers same country-rapporteur pipeline)
    'shadow rapporteur', 'shadow rapporteurs', 'shadow-rapporteur',
    'ponente sombra', 'ponentes sombra', 'ponent ombra', 'ponents ombra',
    'schattenberichterstatter', 'rapporteur fictif', 'rapporteurs fictifs',
    'relator-sombra', 'relatores-sombra',
]

# Country name to ISO 3166-1 alpha-2 code (for EP API filtering)
COUNTRY_NAME_TO_CODE = {
    'Spain': 'ES', 'France': 'FR', 'Germany': 'DE', 'Italy': 'IT',
    'Netherlands': 'NL', 'Belgium': 'BE', 'Poland': 'PL', 'Romania': 'RO',
    'Greece': 'GR', 'Portugal': 'PT', 'Sweden': 'SE', 'Denmark': 'DK',
    'Finland': 'FI', 'Ireland': 'IE', 'Austria': 'AT', 'Czechia': 'CZ',
    'Hungary': 'HU', 'Bulgaria': 'BG', 'Croatia': 'HR', 'Slovakia': 'SK',
    'Slovenia': 'SI', 'Estonia': 'EE', 'Latvia': 'LV', 'Lithuania': 'LT',
    'Cyprus': 'CY', 'Malta': 'MT', 'Luxembourg': 'LU',
}


@dataclass
class DraftingIntent:
    """Detected drafting/action intent from user query.

    When a user wants to PRODUCE a document (not just learn about a topic),
    the context builder signals this so the AI switches to drafting mode.
    """
    is_drafting_query: bool
    action_word: str = ""  # The detected action word (e.g., "draft", "justificacio")
    document_type: str = ""  # Best guess at document type (e.g., "justification", "briefing", "position_paper")
    topic: str = ""  # The topic/subject extracted from the query
    confidence: float = 0.0


# Action words that signal the user wants to PRODUCE something, not learn about it.
# Organised by language, with the document type they map to.
ACTION_WORD_MAP = {
    # English -- explicit action phrases only (no standalone nouns that match inside other words)
    'draft': 'draft', 'write': 'draft', 'prepare': 'draft', 'redact': 'draft',
    'template': 'template', 'sample': 'template',
    'justification': 'justification', 'justify': 'justification',
    'draft a briefing': 'briefing', 'write a briefing': 'briefing', 'prepare a briefing': 'briefing',
    'briefing note': 'briefing',
    'position paper': 'position_paper', 'draft a position': 'position_paper',
    'amendment': 'amendment', 'amend': 'amendment',
    'talking points': 'talking_points',
    'summarise': 'summary', 'summarize': 'summary',
    'draft a note': 'briefing', 'write a note': 'briefing', 'prepare a note': 'briefing',
    'memo': 'briefing', 'memorandum': 'briefing',
    'draft a letter': 'letter', 'write a letter': 'letter', 'write an email': 'letter',
    'draft a report': 'report', 'write a report': 'report', 'prepare a report': 'report',
    'draft report': 'report', 'write report': 'report',
    'draft a proposal': 'proposal', 'write a proposal': 'proposal',
    'draft a resolution': 'resolution', 'write a resolution': 'resolution',
    'draft a question': 'ep_question', 'write a question': 'ep_question',
    'parliamentary question': 'ep_question', 'written question': 'ep_question',
    'draft a petition': 'petition', 'write a petition': 'petition', 'make a petition': 'petition',
    'file a petition': 'petition', 'lodge a petition': 'petition', 'submit a petition': 'petition',
    'ep petition': 'petition', 'petition to the european parliament': 'petition',
    'petition to the ep': 'petition', 'petition to parliament': 'petition',
    'peticio al parlament': 'petition', 'redacta una peticio': 'petition', 'fes una peticio': 'petition',
    'peticion al parlamento': 'petition', 'redacta una peticion': 'petition', 'haz una peticion': 'petition',
    'petition au parlement': 'petition', 'rediger une petition': 'petition',
    'petizione al parlamento': 'petition', 'fai una petizione': 'petition',
    'verzoekschrift': 'petition',
    # petition - accented variants (the matcher does not strip accents)
    'petició al parlament': 'petition', 'redacta una petició': 'petition', 'fes una petició': 'petition',
    'petición al parlamento': 'petition', 'redacta una petición': 'petition', 'haz una petición': 'petition',
    'pétition au parlement': 'petition', 'rédiger une pétition': 'petition',
    # Catalan
    'justificacio': 'justification', 'redacta': 'draft', 'escriu': 'draft',
    'esborrany': 'draft', 'prepara': 'draft', 'plantilla': 'template',
    'resumeix': 'summary',
    'redacta una nota': 'briefing', 'escriu una nota': 'briefing',
    'redacta informe': 'report', 'escriu informe': 'report',
    'redacta una carta': 'letter', 'escriu una carta': 'letter',
    'redacta una proposta': 'proposal', 'esmena': 'amendment',
    # Spanish
    'justificacion': 'justification', 'redactar': 'draft', 'escribir': 'draft',
    'borrador': 'draft', 'preparar': 'draft',
    'resumir': 'summary',
    'argumentario': 'talking_points', 'posicionamiento': 'position_paper',
    'enmienda': 'amendment',
    'redactar una nota': 'briefing', 'escribir una nota': 'briefing',
    # French
    'brouillon': 'draft', 'rediger': 'draft', 'ecrire': 'draft',
    'argumentaire': 'talking_points', 'justificatif': 'justification',
    'resumer': 'summary',
    'amendement': 'amendment',
    'rediger une note': 'briefing', 'ecrire une note': 'briefing',
    # Italian
    'bozza': 'draft', 'scrivere': 'draft', 'redigere': 'draft',
    'giustificazione': 'justification', 'riassunto': 'summary',
    'emendamento': 'amendment',
    # Dutch
    'ontwerp': 'draft', 'schrijven': 'draft', 'samenvatting': 'summary',
    'rechtvaardiging': 'justification',
}

# Map document types to the best matching template names
DOC_TYPE_TO_TEMPLATE = {
    'position_paper': ['position_paper_template', 'coalition_position_template'],
    'briefing': ['briefing_note', 'mep_briefing_note_template', 'meeting_preparation_brief_template'],
    'talking_points': ['briefing_note', 'mep_briefing_note_template'],
    'report': ['monthly_monitoring_report_template', 'weekly_legislative_monitoring_report_template'],
    'letter': ['briefing_note'],
    'ep_question': [],  # Handled by Document Generator
    'resolution': [],  # Handled by Document Generator
    'petition': [],  # Handled by Document Generator
    'amendment': [],  # Handled by Amendator
    'template': [],  # Will search all templates
    'draft': [],  # Generic -- will search all
    'justification': ['eu_strategy_advocacy_template'],
    'summary': [],
    'proposal': ['position_paper_template', 'eu_strategy_advocacy_template'],
}


def detect_drafting_intent(query: str) -> DraftingIntent:
    """
    Detect whether a user query is asking to PRODUCE a document vs learn about a topic.

    Examples:
        "Justificacio interreg" -> DraftingIntent(is_drafting_query=True, action_word="justificacio",
                                                   document_type="justification", topic="interreg")
        "What is the AI Act?" -> DraftingIntent(is_drafting_query=False)
        "Draft a position paper on REACH" -> DraftingIntent(is_drafting_query=True, ...)
    """
    query_lower = query.lower().strip()

    # Guard: if the query is clearly asking for STATUS or INFORMATION, skip drafting detection
    INFO_INTENT_PHRASES = [
        # English -- status & information
        "what's the status", "what is the status", "status of",
        "what is", "what are", "tell me about", "explain",
        "how does", "how do", "how is", "who is", "who are",
        "when is", "when will", "where is", "will it be voted",
        "voted during", "voted in", "next plenary", "plenary session",
        "inform me", "can you inform", "give me an overview",
        "latest studies", "latest reports", "released by",
        "published by", "conducted by", "do you know",
        "are there any", "can you find", "can you check",
        "can you look", "do look", "look for", "search for",
        "overview of", "list of", "show me",
        "what amendments", "what proposals", "what resolutions",
        "which amendments", "which proposals",
        "has this mep", "has tabled", "have tabled",
        # Catalan
        "qual es", "que es", "que son", "quin es", "quina es",
        "dona'm", "mostra'm", "busca", "cerca",
        # Spanish
        "cuales son", "informame", "dame un resumen",
        "busca", "muestra",
        # French
        "quel est", "qu'est", "quels sont", "quelles sont",
        "informez-moi", "donnez-moi", "montrez-moi", "cherchez",
        # Italian
        "cos'e", "quali sono", "mostrami", "cercami",
        # Dutch
        "wat is", "wat zijn", "laat me zien", "zoek",
        # Plenary debate queries (summarise a debate = information, not drafting)
        "plenary debate", "debate in parliament", "ep debate", "meps discussed",
        "what did meps say", "parliament debate", "parliament discussed",
        "debate on", "debated in plenary", "debate transcript",
        "who spoke in plenary", "speakers in the debate",
        "summarise the debate", "summarize the debate",
        "summarise the plenary", "summarize the plenary",
        "debat en pleniere", "debat au parlement", "debate en el pleno",
        "debat al plenari", "dibattito in plenaria", "plenair debat",
    ]
    for phrase in INFO_INTENT_PHRASES:
        if phrase in query_lower:
            return DraftingIntent(is_drafting_query=False)

    # Find ALL action words present in the query (longest match first)
    sorted_actions = sorted(ACTION_WORD_MAP.keys(), key=len, reverse=True)
    found_actions = []

    temp_query = query_lower
    for action_word in sorted_actions:
        if action_word in temp_query:
            found_actions.append((action_word, ACTION_WORD_MAP[action_word]))
            # Remove this action word from temp_query so topic extraction is clean
            temp_query = temp_query.replace(action_word, ' ')

    if not found_actions:
        return DraftingIntent(is_drafting_query=False)

    # Pick the most specific document type (prefer non-generic types over "draft")
    # Priority: specific types > "draft" > "template" > "summary"
    TYPE_PRIORITY = {
        'position_paper': 10, 'briefing': 9, 'talking_points': 9,
        'justification': 9, 'amendment': 9, 'ep_question': 9,
        'resolution': 9, 'petition': 9, 'report': 8, 'letter': 8,
        'proposal': 7, 'summary': 5, 'template': 4, 'draft': 3,
    }
    found_actions.sort(key=lambda x: TYPE_PRIORITY.get(x[1], 0), reverse=True)
    best_action_word, best_doc_type = found_actions[0]

    # Extract topic: remove ALL action words from query
    topic = temp_query.strip()
    # Clean up multiple spaces
    topic = re.sub(r'\s+', ' ', topic).strip()
    # Clean up common connectors at the start (loop until stable)
    connectors = ['for', 'about', 'on', 'of', 'per', 'sobre', 'pour', 'sur',
                  'de la', 'de les', 'de', 'del', 'dels',  # longer first
                  'un', 'una', 'el', 'la', 'les', 'los', 'las',
                  'il', 'le', 'het', 'een', 'a']
    changed = True
    while changed:
        changed = False
        for connector in connectors:
            if topic.startswith(connector + ' '):
                topic = topic[len(connector) + 1:].strip()
                changed = True
                break
    topic = topic.strip()

    # Confidence scoring
    confidence = 0.9 if query_lower.startswith(best_action_word) else 0.7
    if len(found_actions) > 1:
        confidence = min(confidence + 0.1, 1.0)  # Multiple action words = high confidence
    if topic and len(topic) > 2:
        confidence = min(confidence + 0.1, 1.0)

    return DraftingIntent(
        is_drafting_query=True,
        action_word=best_action_word,
        document_type=best_doc_type,
        topic=topic,
        confidence=confidence
    )


@dataclass
class ExtractedEntities:
    """Entities extracted from user query"""
    celex_numbers: List[str]
    procedure_references: List[str]
    mep_names: List[str]
    committee_codes: List[str]
    article_references: List[str]
    policy_areas: List[str]
    dg_codes: List[str]  # Commission DG codes (e.g., GROW, CLIMA)
    assistant_intent: bool = False  # True if user asks about MEP assistants
    # Phase 4: Tenderator bridge entities
    funding_topic_ids: List[str] = field(default_factory=list)  # e.g. HORIZON-CL4-2026-DIGITAL-EMERGING-01-01
    funding_programmes: List[str] = field(default_factory=list)  # canonical codes: HORIZON, LIFE, CEF, DEP, EU4H, ERASMUS
    # All-EU funding extension: decentralised agency body_codes the user
    # named (efca, efsa, ema, eurojust, etf, cedefop, eige, …). Routes the
    # Tenderator deep link to source=agency&body=<code>.
    agency_codes: List[str] = field(default_factory=list)


@dataclass
class ContextData:
    """Complete context data for AI"""
    # Semantic search results
    relevant_documents: List[Dict[str, Any]]

    # Extracted entities
    entities: ExtractedEntities

    # Live API data
    legislation_details: List[Dict[str, Any]]
    procedure_details: List[Dict[str, Any]]
    mep_profiles: List[Dict[str, Any]]
    committee_info: List[Dict[str, Any]]  # Committee membership data

    # Recent updates
    recent_rss_entries: List[Dict[str, Any]]

    # Internal knowledge base
    internal_knowledge: List[Dict[str, Any]]
    reference_data_context: Optional[str]

    # Phase 2: EPRS Publications (EU jargon translators)
    eprs_publications: List[Dict[str, Any]]

    # Phase 5: AI-generated briefings (smart summaries)
    ai_generated_briefings: List[Dict[str, Any]]

    # EC Personnel data (organigrammes)
    ec_personnel: List[Dict[str, Any]]

    # Legislative Train Schedule (EC priorities tracking)
    legislative_train_files: List[Dict[str, Any]]

    # Local EU Laws Database (50k+ laws from LEG_2025-11)
    local_eu_laws: List[Dict[str, Any]]

    # Real-time web search (Tavily)
    web_search_results: List[Dict[str, Any]]

    # Beresol open reports and monitors (Brubru's company)
    beresol_content: List[Dict[str, Any]]

    # EP Committee Work in Progress items
    committee_work_items: List[Dict[str, Any]]

    # EP Committee Meeting Minutes
    committee_minutes: List[Dict[str, Any]]

    # EC Public Consultations (Have Your Say portal)
    public_consultations: List[Dict[str, Any]]

    # EC Commission Documents (Register of Commission Documents - Yellow/Blue tier)
    commission_documents: List[Dict[str, Any]]

    # MCP Toolbox supplementary results
    toolbox_results: List[Dict[str, Any]]

    # User uploaded documents (for personalised AI context)
    user_uploaded_documents: List[Dict[str, Any]]

    # MEP amendments (scraped EP committee amendments)
    mep_amendments_summary: List[Dict[str, Any]]

    # EU Calendar Events (institutional calendar data with exact dates)
    eu_calendar_events: List[Dict[str, Any]]

    # Metadata
    query: str
    search_time_ms: float
    total_sources: int

    # Org intelligence (aggregated user profile for personalisation)
    org_intelligence: Optional[Dict[str, Any]] = None

    # Phase 8: Tender data (Tenderator integration) - optional, must come after required fields
    tender_context: Optional[TenderContextData] = None

    # Drafting intent detection (action vs information)
    drafting_intent: Optional[DraftingIntent] = None

    # CELLAR on-demand legislation (EuroVoc fallback when no guides match)
    cellar_legislation: Optional[List[Dict[str, Any]]] = None

    # EU institutional source search (Tavily fallback when no guides match)
    eu_institutional_results: Optional[List[Dict[str, Any]]] = None

    # Rapporteur-by-country results (for "Spanish MEPs who are rapporteurs" queries)
    rapporteur_by_country: Optional[List[Dict[str, Any]]] = None
    rapporteur_country: Optional[str] = None

    # EP plenary debate transcript (CRE)
    plenary_debate_transcript: Optional[str] = None

    # On-demand: stakeholder feedback to a public consultation
    consultation_feedback_block: Optional[str] = None

    # On-demand: a Commissioner's published agenda
    commissioner_agenda_block: Optional[str] = None

    # On-demand: Position Analysis (Commission / Parliament / Council stances on a file)
    position_block: Optional[str] = None

    # On-demand: EP committee meeting transcript (AI-transcribed from EP Multimedia)
    committee_transcript_block: Optional[str] = None

    # On-demand: TODAY block (current date + EP week type + 3-day calendar window + recent Commission docs)
    # Triggered by "today"/"hoy"/"avui"/"aujourd'hui"/"oggi"/"vandaag"/"heute"/"this week"/"esta semana"...
    today_block: Optional[str] = None
    daily_brief_block: Optional[str] = None
    # Always-on for tenant-audience users (e.g. EFPIA pilot): their curated
    # daily brief + tracked priority files, so the chat can answer questions
    # about "my files" / today's headlines from the same content the email sends.
    audience_brief_block: Optional[str] = None

    # On-demand: Legal-text article block (W1b, 12 May 2026)
    # Triggered by "Article N (paragraph M) of <CELEX|alias>", "Recital N of <CELEX|alias>",
    # in 6 languages (EN/FR/ES/CA/IT/NL). Pulls cached recital-article map + defined terms
    # from the legal-text intelligence layer + composes a high-priority context block with
    # the EUR-Lex URL. See memory/project_chat_ai_architecture_evolution.md (W1b).
    legal_text_article_block: Optional[str] = None

    # On-demand: Cellar SPARQL discovery block (live retrieval from publications.europa.eu/webapi/rdf/sparql)
    # Triggered by "what was published since/this/last <period>", "list/find/show me recent <regs|directives|decisions>",
    # "regulations on <topic>", "consolidated version of <CELEX>".
    cellar_discovery_block: Optional[str] = None

    # On-demand: EU restrictive measures (CFSP sanctions consolidated list)
    # Triggered by "sanction(ed)", "restrictive measure", "asset freeze", "CFSP", "EU.<n>.<n>"
    sanctions_block: Optional[str] = None

    # On-demand: EU Transparency Register (interest representatives / lobbyists)
    # Triggered by "lobby(ist)", "interest representative", "EP pass", "lobbying costs"
    transparency_register_block: Optional[str] = None

    # On-demand: Comitology Register documents (committee meeting outputs)
    # Triggered by "comitology", "implementing act", "committee vote", "SCoPAFF", "summary record", "scrutiny"
    comitology_block: Optional[str] = None

    # On-demand: EU Geographical Indications (PDO / PGI / TSG / wine / spirit / craft)
    gi_block: Optional[str] = None

    # On-demand: EU international agreements (FTA / EPA / AA / PCA / Fisheries / Aviation)
    fta_block: Optional[str] = None

    # On-demand: EU anti-dumping / countervailing / safeguard regulations
    trade_defence_block: Optional[str] = None

    # On-demand: DG COMP competition cases (state aid / antitrust / merger) — live HTTP
    competition_cases_block: Optional[str] = None

    # On-demand: JRC Data Catalogue (scientific datasets)
    jrc_datasets_block: Optional[str] = None

    # On-demand: DG REGIO Cohesion Open Data datasets
    cohesion_datasets_block: Optional[str] = None

    # On-demand: Combined Nomenclature (CN) tariff codes — live HTTP via Access2Markets
    cn_codes_block: Optional[str] = None

    # Layer 2 (May 2026): wire the 4 remaining v1 surfaces into chat retrieval.
    # Same pattern as Layer 1 — intent regex + stopwords + DB-backed fetch.
    commission_register_block: Optional[str] = None
    delegated_acts_block: Optional[str] = None
    ecli_block: Optional[str] = None
    eurio_research_block: Optional[str] = None

    # Layer 2b: open funding calls (F&T Portal opportunities + calls-for-proposals).
    # Disambiguated from eurio_research_block (past projects) by intent regex:
    # only fires on "open call" / "apply" / "deadline" / "grant" phrasings.
    eu_funding_block: Optional[str] = None

    # Layer 2c (May 2026 batch #31-40 follow-up): Council documents + Infringements
    council_documents_block: Optional[str] = None
    infringements_block: Optional[str] = None

    # Layer 2d (May 2026 batch #41-50 follow-up): Transparency Register meetings
    transparency_meetings_block: Optional[str] = None

    # EP written/oral questions (7 Aug 2026). Brubru has held these all along
    # and Parliamentary Questions is a My EU Bubble sub-tab, but the chat
    # context builder never fetched them, so a question named by reference was
    # answered from training memory. Asked about E-004916/2025 (Military
    # Schengen and sovereignty, tabled by Moreira de Sá and others), chat
    # invented a question about German authorities transferring people across
    # borders and cited a document reference that does not correspond to it.
    parliamentary_questions_block: Optional[str] = None

    # Individual MEP roll-call votes (7 Aug 2026). 143,338 records existed and
    # chat could not read one of them, so "how did MEP X vote" was answered by
    # guessing the political group's line. It is right often enough to look
    # trustworthy and wrong exactly when it matters: David Casa (PPE) and Barry
    # Andrews (Renew) both voted AGAINST the 28th tax regime resolution against
    # their group majority, and chat reported both as voting in favour, one of
    # them with an invented verbatim quote attributed to the MEP.
    roll_call_block: Optional[str] = None

    # Transparency Register meetings (7 Aug 2026). Lobby Meetings is a My EU
    # Bubble sub-tab, and chat named the Commission and the Parliament as the
    # lobbyists an MEP had met, then declared nothing else was on record.
    lobby_meetings_block: Optional[str] = None

    # Committee amendment documents (7 Aug 2026). Chat invented both the
    # amendment count and the PE reference when it could not read the table.
    amendment_documents_block: Optional[str] = None

    # Constraint injected when the user names a competitor (7 Aug 2026): chat
    # was asserting what rival products lack, with citation markers attached.
    competitor_guard_block: Optional[str] = None

    # Private user/org bespoke knowledge bundle (20 May 2026).
    # Always-on for the authenticated user when users.private_guide_status='ready'.
    # Loaded from backend/knowledge_base/private_guides/{slug}/ (gitignored).
    # Rendered FIRST in format_context_for_ai so the "Brubru already knows you"
    # framing survives 32k truncation. Hook for high-value prospects + clients.
    private_guide_block: Optional[str] = None


class ContextBuilder:
    """
    Build AI context from user queries.

    Process:
    1. Semantic/hybrid search for relevant documents
    2. Entity extraction from query
    3. Live API calls for detected entities
    4. Recent RSS feed monitoring
    5. Format everything for AI consumption
    """

    def __init__(
        self,
        hybrid_search: HybridSearch,
        metadata_extractor: MetadataExtractor,
        eurlex_client: Optional[EURLexClient] = None,
        oeil_client: Optional[OEILClient] = None,
        parliament_client: Optional[EuropeanParliamentClient] = None,
        rss_manager: Optional[Any] = None,  # RSSManager not yet implemented
        reference_data_service: Optional[ReferenceDataService] = None,
        knowledge_loader: Optional[KnowledgeLoader] = None,
        eprs_indexer: "Optional[EPRSIndexer]" = None,  # Phase 2: EPRS search
        eprs_matcher: "Optional[EPRSMatcher]" = None,  # Phase 3: Auto-matching
        ai_summary_generator: Optional[AISummaryGenerator] = None,  # Phase 5: AI summaries
        freshness_detector: Optional[FreshnessDetector] = None,  # Phase 5: Freshness detection
        tender_context_provider: Optional[TenderContextProvider] = None,  # Phase 8: Tender chat
        tavily_client: Optional[TavilyClient] = None,  # Real-time web search
        beresol_loader: Optional[BeresolKnowledgeLoader] = None,  # Beresol open reports
        max_search_results: int = 10,
        max_live_api_calls: int = 5,
        rss_lookback_days: int = 7,
        max_internal_knowledge_results: int = 5,
        max_eprs_results: int = 5,  # Phase 2: Max EPRS publications
        auto_include_explainers: bool = True,  # Phase 3: Auto-inject EPRS explainers
        enable_ai_summaries: bool = True,  # Phase 5: Generate AI summaries when no EPRS briefing
        enable_freshness_check: bool = True,  # Phase 5: Check for outdated briefings
        enable_web_search: bool = True  # Enable Tavily real-time web search
    ):
        """
        Initialize context builder.

        Args:
            hybrid_search: Hybrid search service
            metadata_extractor: Entity extraction service
            eurlex_client: EUR-Lex API client (optional)
            oeil_client: OEIL API client (optional)
            parliament_client: European Parliament API client (optional)
            rss_manager: RSS feed manager (optional)
            reference_data_service: Reference data service for calendars/institutions (optional)
            knowledge_loader: Knowledge base loader (optional)
            eprs_indexer: EPRS indexer for searching publications (optional, Phase 2)
            eprs_matcher: EPRS matcher for auto-linking (optional, Phase 3)
            max_search_results: Max semantic search results
            max_live_api_calls: Max live API calls per entity type
            rss_lookback_days: Days to look back for RSS entries
            max_internal_knowledge_results: Max internal knowledge results
            max_eprs_results: Max EPRS publication results (Phase 2)
            auto_include_explainers: Automatically include EPRS explainers for legislation (Phase 3)
        """
        self.hybrid_search = hybrid_search
        self.metadata_extractor = metadata_extractor
        self.eurlex_client = eurlex_client
        self.oeil_client = oeil_client
        self.parliament_client = parliament_client
        self.rss_manager = rss_manager
        self.reference_data_service = reference_data_service or get_reference_data_service()
        self.knowledge_loader = knowledge_loader or get_knowledge_loader()
        # EPRS semantic (ChromaDB) indexer: constructed only when a populated vector
        # store exists. In production the store is empty, so this stays None and the
        # ChromaDB pass is skipped -- EPRS retrieval runs on the PostgreSQL pass alone.
        # Constructing it imports chromadb + onnxruntime (~200 MB); gating avoids that.
        if eprs_indexer is not None:
            self.eprs_indexer = eprs_indexer
        elif semantic_store_available():
            from services.indexing.eprs_indexer import get_eprs_indexer
            self.eprs_indexer = get_eprs_indexer()
        else:
            self.eprs_indexer = None  # Phase 2: ChromaDB pass disabled (empty store)
        # EPRS matcher (Phase 3): wraps the ChromaDB indexer, so gated the same way.
        # None on an empty production store; the two call sites below are skipped.
        if eprs_matcher is not None:
            self.eprs_matcher = eprs_matcher
        elif semantic_store_available():
            from services.matching.eprs_matcher import get_eprs_matcher
            self.eprs_matcher = get_eprs_matcher()
        else:
            self.eprs_matcher = None  # Phase 3: auto-matching disabled (empty store)
        self.ai_summary_generator = ai_summary_generator or get_ai_summary_generator()  # Phase 5
        self.freshness_detector = freshness_detector or get_freshness_detector()  # Phase 5
        self.tender_context_provider = tender_context_provider or get_tender_context_provider()  # Phase 8
        self.tavily_client = tavily_client or get_tavily_client()  # Real-time web search
        self.beresol_loader = beresol_loader or get_beresol_knowledge_loader()  # Beresol reports
        self.max_search_results = max_search_results
        self.max_live_api_calls = max_live_api_calls
        self.rss_lookback_days = rss_lookback_days
        self.max_internal_knowledge_results = max_internal_knowledge_results
        self.max_eprs_results = max_eprs_results  # Phase 2
        self.auto_include_explainers = auto_include_explainers  # Phase 3
        self.enable_ai_summaries = enable_ai_summaries  # Phase 5
        self.enable_freshness_check = enable_freshness_check  # Phase 5
        self.enable_web_search = enable_web_search  # Tavily

        logger.info(
            "Initialized ContextBuilder with EPRS publications, "
            f"auto-explainers {'enabled' if auto_include_explainers else 'disabled'}, "
            f"AI summaries {'enabled' if enable_ai_summaries else 'disabled'}, "
            f"web search {'enabled' if enable_web_search and self.tavily_client else 'disabled'}"
        )

    async def build_context_for_query(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[str] = None,
        use_live_apis: bool = True,
        use_rss: bool = True
    ) -> ContextData:
        """
        Build comprehensive context for user query.

        Args:
            user_message: User's question/message
            conversation_history: Previous messages in conversation
            use_live_apis: Whether to call live APIs for entities
            use_rss: Whether to include recent RSS entries

        Returns:
            ContextData with all relevant information

        Example:
            User: "What's the status of the AI Act?"
            Returns:
            - OEIL procedure data (status, timeline)
            - EUR-Lex legislation (CELEX, full text excerpt)
            - Related amendments from RSS
            - MEPs involved (rapporteur, shadows)
            - Recent votes
        """
        start_time = datetime.now()

        logger.info(f"Building context for query: {user_message[:100]}...")

        # Entities and the history-augmented retrieval query are computed FIRST
        # so that even the semantic pass below sees a follow-up's real topic.
        entities = self.extract_entities(user_message)
        retrieval_query = self._augment_query_with_history(
            user_message, conversation_history, entities
        )

        # 1. Semantic/hybrid search for relevant documents
        search_results = await self.hybrid_search.search(
            query=retrieval_query,
            limit=self.max_search_results,
            use_recency_boost=True,
            use_authority_boost=True
        )

        relevant_documents = [
            {
                'id': result.id,
                'text': result.text[:500],  # Truncate for context size
                'score': result.score,
                'metadata': result.metadata,
                'collection': result.collection
            }
            for result in search_results.results
        ]

        # (entities extracted above, before the semantic pass)

        # 2b. Detect drafting/action intent (user wants to PRODUCE something)
        drafting_intent = detect_drafting_intent(user_message)
        if drafting_intent.is_drafting_query:
            logger.info(f"[DRAFTING] Detected action intent: {drafting_intent.action_word} -> "
                        f"{drafting_intent.document_type} (topic: {drafting_intent.topic}, "
                        f"confidence: {drafting_intent.confidence:.0%})")

        # 3. Run all async operations in parallel for maximum speed
        # This reduces total wait time from sum(times) to max(time)

        # Prepare tasks to run concurrently
        tasks = []

        # Every text-similarity retrieval below runs on `retrieval_query`, not
        # on the raw message: for a context-bare follow-up it carries the topic
        # forward from the previous turns. Multi-turn only started working on
        # 3 Aug 2026, so until then every follow-up was a first message and
        # this did not matter. It does now. Applying it to the guide lookup
        # ALONE was not enough -- verified on production 6 Aug: turn 1 asked
        # about geographical indications for spirit drinks, turn 2 asked "When
        # did it enter into force?", and the answer came back about the AI Act
        # because the web/EPRS/eu_laws lookups were still running on the bare
        # sentence. Entity-keyed fetches (CELEX, procedure, MEP, committee)
        # keep using the extracted entities and are unaffected.
        # (retrieval_query computed above, before the semantic pass)

        # Legislative Train files (always run)
        tasks.append(self._fetch_legislative_train_files(query=retrieval_query, entities=entities))

        # Internal knowledge base (always run)
        tasks.append(self._query_internal_knowledge(retrieval_query, drafting_intent=drafting_intent))

        # EPRS publications (always run)
        tasks.append(self._search_eprs_publications(query=retrieval_query, entities=entities))

        # Local EU laws database (always run)
        tasks.append(self._fetch_eu_laws_from_database(query=retrieval_query, entities=entities))

        # Helper functions for empty results
        async def empty_result():
            return []

        async def empty_tuple_result():
            return ([], [])

        # RSS entries (conditional)
        if use_rss and self.rss_manager:
            tasks.append(self._fetch_recent_rss(query=retrieval_query, entities=entities, days=self.rss_lookback_days))
        else:
            tasks.append(empty_result())

        # Live API calls (conditional)
        if use_live_apis:
            # Legislation details
            if entities.celex_numbers and self.eurlex_client:
                tasks.append(self._fetch_legislation_details(entities.celex_numbers[:self.max_live_api_calls]))
            else:
                tasks.append(empty_tuple_result())

            # Procedure details
            if entities.procedure_references and self.oeil_client:
                tasks.append(self._fetch_procedure_details(entities.procedure_references[:self.max_live_api_calls]))
            else:
                tasks.append(empty_result())

            # MEP profiles (include assistants if user is asking about them)
            if entities.mep_names and self.parliament_client:
                tasks.append(self._fetch_mep_profiles(
                    entities.mep_names[:self.max_live_api_calls],
                    include_assistants=entities.assistant_intent
                ))
            else:
                tasks.append(empty_result())

            # Committee info
            if entities.committee_codes:
                tasks.append(self._fetch_committee_info(entities.committee_codes[:self.max_live_api_calls]))
            else:
                tasks.append(empty_result())

            # EC personnel
            # Safety net: if contact-intent detected but no DG codes found,
            # do a broader keyword scan to ensure we fetch real people
            query_lower = user_message.lower()
            if not entities.dg_codes:
                is_contact_query = any(kw in query_lower for kw in CONTACT_INTENT_PHRASES)
                if is_contact_query:
                    for keyword, dg_list in POLICY_TO_DG.items():
                        if re.search(r'\b' + re.escape(keyword) + r'\b', query_lower):
                            entities.dg_codes.extend(
                                dg for dg in dg_list if dg not in entities.dg_codes
                            )

            if entities.dg_codes:
                tasks.append(self._fetch_ec_personnel(entities.dg_codes[:self.max_live_api_calls], query_lower))
            else:
                tasks.append(empty_result())
        else:
            # Add empty result tasks if not using live APIs
            tasks.append(empty_tuple_result())  # legislation details
            for _ in range(4):
                tasks.append(empty_result())

        # Phase 8: Tender context (detect tender-related queries)
        tender_intent = self.tender_context_provider.detect_tender_intent(user_message)
        if tender_intent.is_tender_query:
            tasks.append(self.tender_context_provider.fetch_tender_context(
                intent=tender_intent,
                user_id=user_id
            ))
        else:
            async def empty_tender_result():
                return None
            tasks.append(empty_tender_result())

        # Real-time web search (Tavily) for current events and breaking news
        if self.enable_web_search and self.tavily_client:
            tasks.append(self._fetch_web_search(query=retrieval_query))
        else:
            tasks.append(empty_result())

        # Beresol open reports and monitors (Brubru's company)
        if self.beresol_loader:
            tasks.append(self._fetch_beresol_content(query=retrieval_query))
        else:
            tasks.append(empty_result())

        # EP Committee Work in Progress items
        tasks.append(self._fetch_committee_work_items(query=retrieval_query, entities=entities))

        # EP Committee Meeting Minutes
        tasks.append(self._fetch_committee_minutes(query=retrieval_query, entities=entities))

        # Phase 9: Fetch EC Public Consultations (Have Your Say portal)
        tasks.append(self._fetch_public_consultations(query=retrieval_query, entities=entities))

        # EC Commission Documents (Yellow/Blue tier only)
        tasks.append(self._fetch_commission_documents(query=retrieval_query, entities=entities, user_id=user_id))

        # MCP Toolbox supplementary DB queries (non-blocking)
        tasks.append(self._fetch_via_toolbox(query=retrieval_query, entities=entities))

        # User uploaded documents (personalised AI context)
        if user_id:
            tasks.append(self._fetch_user_uploaded_documents(user_id=user_id, query=user_message))
        else:
            tasks.append(empty_result())

        # Org intelligence (aggregated user profile)
        if user_id:
            tasks.append(self._fetch_org_intelligence(user_id=user_id))
        else:
            tasks.append(empty_result())

        # MEP amendments (scraped EP committee amendments)
        if entities.procedure_references or entities.mep_names:
            tasks.append(self._fetch_mep_amendments(
                entities.procedure_references,
                mep_names=entities.mep_names,
            ))
        else:
            tasks.append(empty_result())

        # EU Calendar Events (institutional calendar with exact dates)
        tasks.append(self._fetch_eu_calendar_events(query=retrieval_query, entities=entities))

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Unpack results (order matches task addition)
        legislative_train_files = results[0] if not isinstance(results[0], Exception) else []

        # Enrich matched legislative files with procedural actions (draft reports,
        # amendments, votes, rapporteur info) for data-driven follow-up suggestions
        if legislative_train_files:
            try:
                legislative_train_files = await self._enrich_train_files_with_actions(
                    legislative_train_files
                )
            except Exception as e:
                logger.warning(f"[OEIL-ACTIONS] Enrichment pass failed, continuing: {e}")

        internal_knowledge = results[1] if not isinstance(results[1], Exception) else []
        eprs_publications = results[2] if not isinstance(results[2], Exception) else []
        local_eu_laws = results[3] if not isinstance(results[3], Exception) else []
        recent_rss_entries = results[4] if not isinstance(results[4], Exception) else []

        # Unpack live API results
        legislation_details = []
        ai_generated_briefings = []
        procedure_details = []
        mep_profiles = []
        committee_info = []
        ec_personnel = []

        if use_live_apis:
            leg_result = results[5]
            if not isinstance(leg_result, Exception) and isinstance(leg_result, tuple):
                legislation_details, leg_ai_briefings = leg_result
                ai_generated_briefings.extend(leg_ai_briefings)

            procedure_details = results[6] if not isinstance(results[6], Exception) else []
            mep_profiles = results[7] if not isinstance(results[7], Exception) else []
            committee_info = results[8] if not isinstance(results[8], Exception) else []
            ec_personnel = results[9] if not isinstance(results[9], Exception) else []

        # Phase 8: Unpack tender context (index 10)
        tender_context = results[10] if not isinstance(results[10], Exception) else None

        # Unpack web search results (index 11)
        web_search_results = results[11] if not isinstance(results[11], Exception) else []

        # Unpack Beresol content (index 12)
        beresol_content = results[12] if not isinstance(results[12], Exception) else []

        # Unpack Committee Work items (index 13)
        committee_work_items = results[13] if not isinstance(results[13], Exception) else []

        # Unpack Committee Minutes (index 14)
        committee_minutes = results[14] if not isinstance(results[14], Exception) else []

        # Unpack Public Consultations (index 15)
        public_consultations = results[15] if not isinstance(results[15], Exception) else []

        # Unpack Commission Documents (index 16)
        commission_documents = results[16] if not isinstance(results[16], Exception) else []

        # Unpack MCP Toolbox results (index 17)
        toolbox_results = results[17] if not isinstance(results[17], Exception) else []

        # Unpack User Uploaded Documents (index 18)
        user_uploaded_documents = results[18] if not isinstance(results[18], Exception) else []

        # Unpack Org Intelligence (index 19)
        org_intelligence = results[19] if not isinstance(results[19], Exception) else None

        # Unpack MEP Amendments summary (index 20)
        mep_amendments_summary = results[20] if not isinstance(results[20], Exception) else []

        # Unpack EU Calendar Events (index 21)
        eu_calendar_events = results[21] if not isinstance(results[21], Exception) else []

        # Fix 4: Extract procedure_refs from plenary events and fetch their amendments
        # This connects plenary scheduling to amendment data
        if eu_calendar_events and not mep_amendments_summary:
            plenary_proc_refs = set()
            for event in eu_calendar_events:
                if event.get('procedure_refs'):
                    plenary_proc_refs.update(event['procedure_refs'])
                # Also check plenary sessions (these may have amendments filed)
                if event.get('event_type') in ('plenary_session',) and event.get('procedure_refs'):
                    plenary_proc_refs.update(event['procedure_refs'])

            # Subtract already-fetched procedure refs
            already_fetched = set(entities.procedure_references or [])
            new_refs = list(plenary_proc_refs - already_fetched)[:3]

            if new_refs:
                try:
                    plenary_amendments = await self._fetch_mep_amendments(
                        procedure_references=new_refs,
                    )
                    mep_amendments_summary.extend(plenary_amendments)
                except Exception as e:
                    logger.warning(f"[PLENARY-AM] Failed to fetch plenary amendments: {e}")

        # Post-gather parallel operations: run independent fetches concurrently
        # instead of sequentially. Reduces total latency from sum(times) to max(time).
        # Inspired by Claude Code's coordinator pattern: parallel research workers.

        query_lower = user_message.lower()

        # Prepare post-gather tasks (all independent of each other)
        post_tasks = {}

        # 1. Rapporteur-by-country query
        detected_country = None
        for demonym, country in COUNTRY_DEMONYMS.items():
            if demonym in query_lower:
                detected_country = country
                break
        has_rapporteur_intent = any(phrase in query_lower for phrase in RAPPORTEUR_INTENT_PHRASES)

        async def _fetch_rapporteur_by_country_safe():
            if detected_country and has_rapporteur_intent:
                try:
                    return await self._fetch_rapporteurs_by_country(detected_country)
                except Exception as e:
                    logger.warning(f"[RAPPORTEUR] Country rapporteur fetch failed: {e}")
            return []

        post_tasks['rapporteur'] = _fetch_rapporteur_by_country_safe()

        # 2. CELLAR on-demand fallback (only if no knowledge guides matched)
        async def _fetch_cellar_safe():
            if not internal_knowledge and self.eurlex_client:
                topic_keywords = self._extract_topic_keywords(user_message.lower())
                if topic_keywords:
                    try:
                        results = await self._fetch_cellar_legislation_context(topic_keywords)
                        if results:
                            logger.info(f"[CELLAR] Fallback returned {len(results)} results "
                                        f"for keywords: {topic_keywords}")
                        return results
                    except Exception as e:
                        logger.warning(f"[CELLAR] On-demand fallback failed: {e}")
            return []

        post_tasks['cellar'] = _fetch_cellar_safe()

        # 3. EP plenary debate transcript (CRE)
        debate_date = self._detect_plenary_debate_intent(user_message)

        async def _fetch_debate_safe():
            if debate_date:
                try:
                    transcript = await self._fetch_plenary_debate(user_message, debate_date)
                    if transcript:
                        logger.info(f"[CRE] Injected plenary debate transcript ({len(transcript)} chars)")
                    return transcript
                except Exception as e:
                    logger.warning(f"[CRE] Failed to fetch plenary debate: {e}")
            return None

        post_tasks['debate'] = _fetch_debate_safe()

        # 3b. On-demand: Have Your Say stakeholder feedback
        consultation_feedback_intent = self._detect_consultation_feedback_intent(user_message)

        async def _fetch_feedback_safe():
            if not consultation_feedback_intent:
                return None
            try:
                block = await self._fetch_consultation_feedback(user_message, public_consultations)
                if block:
                    logger.info("[HYS-feedback] Injected stakeholder feedback block (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[HYS-feedback] Failed: %s", e)
                return None

        post_tasks['consultation_feedback'] = _fetch_feedback_safe()

        # 3c. On-demand: Commissioner agenda
        commissioner_intent = self._detect_commissioner_agenda_intent(user_message)

        async def _fetch_commissioner_agenda_safe():
            if not commissioner_intent:
                return None
            name, df, dt = commissioner_intent
            try:
                block = await self._fetch_commissioner_agenda(name, df, dt)
                if block:
                    logger.info("[commissioner-agenda] Injected agenda block for %s (%d chars)", name, len(block))
                return block
            except Exception as e:
                logger.warning("[commissioner-agenda] Failed for %s: %s", name, e)
                return None

        post_tasks['commissioner_agenda'] = _fetch_commissioner_agenda_safe()

        # 3d. On-demand: Position Analysis
        position_intent = self._detect_position_intent(user_message)

        async def _fetch_position_safe():
            if not position_intent:
                return None
            try:
                block = await self._fetch_position_block(user_message, position_intent)
                if block:
                    logger.info("[position] Injected position block (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[position] Failed: %s", e)
                return None

        post_tasks['position'] = _fetch_position_safe()

        # 3e. On-demand: EP committee meeting transcript
        committee_transcript_intent = self._detect_committee_transcript_intent(user_message)

        async def _fetch_committee_transcript_safe():
            if not committee_transcript_intent:
                return None
            try:
                block = await self._fetch_committee_transcript_block(committee_transcript_intent)
                if block:
                    logger.info(
                        "[committee-transcript] Injected transcript for %s (%d chars)",
                        committee_transcript_intent.get("committee_code"), len(block),
                    )
                return block
            except Exception as e:
                logger.warning("[committee-transcript] Failed: %s", e)
                return None

        post_tasks['committee_transcript'] = _fetch_committee_transcript_safe()

        # 3f. On-demand: TODAY block (date-anchored calendar + active files)
        today_intent = self._detect_today_intent(user_message)

        async def _fetch_today_safe():
            if not today_intent:
                return None
            try:
                block = await self._fetch_today_block(user_message)
                if block:
                    logger.info("[today-block] Injected today block (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[today-block] Failed: %s", e)
                return None

        post_tasks['today_block'] = _fetch_today_safe()

        # 3f2. On-demand: Daily Brief block (daily_briefs DB card for "Daily News DD/MM/YYYY" queries)
        daily_brief_intent = self._detect_daily_brief_intent(user_message)

        async def _fetch_daily_brief_safe():
            if not daily_brief_intent:
                return None
            try:
                block = await self._fetch_daily_brief_block(user_message)
                if block:
                    logger.info("[daily-brief-block] Injected daily brief block (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[daily-brief-block] Failed: %s", e)
                return None

        post_tasks['daily_brief_block'] = _fetch_daily_brief_safe()

        # 3f3. Always-on for tenant-audience users (e.g. EFPIA): inject their own
        # curated brief + tracked priority files so the chat answers "my files" /
        # today's headlines from the same content the email sends. No-op (None)
        # for non-audience users.
        async def _fetch_audience_brief_safe():
            try:
                block = await self._fetch_audience_brief_block(user_id)
                if block:
                    logger.info("[audience-brief-block] Injected audience brief block (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[audience-brief-block] Failed: %s", e)
                return None

        post_tasks['audience_brief_block'] = _fetch_audience_brief_safe()

        # 3g. On-demand: Cellar SPARQL discovery block (live retrieval from publications.europa.eu)
        cellar_discovery_intent = self._detect_cellar_discovery_intent(user_message)

        async def _fetch_cellar_discovery_safe():
            if not cellar_discovery_intent:
                return None
            try:
                block = await self._fetch_cellar_discovery_block(user_message, cellar_discovery_intent)
                if block:
                    logger.info("[cellar-discovery] Injected discovery block (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[cellar-discovery] Failed: %s", e)
                return None

        post_tasks['cellar_discovery_block'] = _fetch_cellar_discovery_safe()

        # 3g-bis. On-demand: Legal-text article / recital block (W1b, 12 May 2026).
        # Triggered by "Article N (paragraph M) of <CELEX|alias>" or "Recital N of <CELEX|alias>"
        # across EN/FR/ES/CA/IT/NL. See memory/project_chat_ai_architecture_evolution.md (W1b).
        legal_text_intent = self._detect_legal_text_article_intent(user_message)
        async def _fetch_legal_text_safe():
            if not legal_text_intent:
                return None
            try:
                block = await self._fetch_legal_text_article_block(db, legal_text_intent)
                if block:
                    logger.info(
                        "[legal-text-article] Injected block (%d chars, type=%s, num=%s, celex=%s)",
                        len(block),
                        legal_text_intent.get("type"),
                        legal_text_intent.get("number"),
                        legal_text_intent.get("celex"),
                    )
                return block
            except Exception as e:  # noqa: BLE001
                logger.warning("[legal-text-article] Failed: %s", e)
                return None
        post_tasks['legal_text_article_block'] = _fetch_legal_text_safe()

        # 3h. On-demand: EU Sanctions block
        sanctions_intent = self._detect_sanctions_intent(user_message)
        async def _fetch_sanctions_safe():
            if not sanctions_intent:
                return None
            try:
                block = await self._fetch_sanctions_block(user_message, sanctions_intent)
                if block:
                    logger.info("[sanctions-block] Injected sanctions block (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[sanctions-block] Failed: %s", e)
                return None
        post_tasks['sanctions_block'] = _fetch_sanctions_safe()

        # 3i. On-demand: EU Transparency Register block
        tr_intent = self._detect_transparency_register_intent(user_message)
        async def _fetch_tr_safe():
            if not tr_intent:
                return None
            try:
                block = await self._fetch_transparency_register_block(user_message, tr_intent)
                if block:
                    logger.info("[tr-block] Injected transparency-register block (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[tr-block] Failed: %s", e)
                return None
        post_tasks['transparency_register_block'] = _fetch_tr_safe()

        # 3j. On-demand: Comitology Register block
        comitology_intent = self._detect_comitology_intent(user_message)
        async def _fetch_comitology_safe():
            if not comitology_intent:
                return None
            try:
                block = await self._fetch_comitology_block(user_message, comitology_intent)
                if block:
                    logger.info("[comitology-block] Injected comitology block (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[comitology-block] Failed: %s", e)
                return None
        post_tasks['comitology_block'] = _fetch_comitology_safe()

        # 3k. On-demand: Geographical Indications block
        gi_intent = self._detect_gi_intent(user_message)
        async def _fetch_gi_safe():
            if not gi_intent: return None
            try:
                block = await self._fetch_gi_block(user_message, gi_intent)
                if block: logger.info("[gi-block] injected (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[gi-block] failed: %s", e); return None
        post_tasks['gi_block'] = _fetch_gi_safe()

        # 3l. On-demand: International Agreements / FTA block
        fta_intent = self._detect_fta_intent(user_message)
        async def _fetch_fta_safe():
            if not fta_intent: return None
            try:
                block = await self._fetch_fta_block(user_message, fta_intent)
                if block: logger.info("[fta-block] injected (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[fta-block] failed: %s", e); return None
        post_tasks['fta_block'] = _fetch_fta_safe()

        # 3m. On-demand: Trade Defence block
        td_intent = self._detect_td_intent(user_message)
        async def _fetch_td_safe():
            if not td_intent: return None
            try:
                block = await self._fetch_td_block(user_message, td_intent)
                if block: logger.info("[td-block] injected (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[td-block] failed: %s", e); return None
        post_tasks['trade_defence_block'] = _fetch_td_safe()

        # 3n. On-demand: DG COMP competition cases (live HTTP)
        comp_intent = self._detect_comp_intent(user_message)
        async def _fetch_comp_safe():
            if not comp_intent: return None
            try:
                block = await self._fetch_comp_block(user_message, comp_intent)
                if block: logger.info("[comp-block] injected (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[comp-block] failed: %s", e); return None
        post_tasks['competition_cases_block'] = _fetch_comp_safe()

        # 3o. On-demand: JRC Data Catalogue block
        jrc_intent = self._detect_jrc_intent(user_message)
        async def _fetch_jrc_safe():
            if not jrc_intent: return None
            try:
                block = await self._fetch_jrc_block(user_message, jrc_intent)
                if block: logger.info("[jrc-block] injected (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[jrc-block] failed: %s", e); return None
        post_tasks['jrc_datasets_block'] = _fetch_jrc_safe()

        # 3p. On-demand: DG REGIO Cohesion datasets block
        cohesion_intent = self._detect_cohesion_intent(user_message)
        async def _fetch_cohesion_safe():
            if not cohesion_intent: return None
            try:
                block = await self._fetch_cohesion_block(user_message, cohesion_intent)
                if block: logger.info("[cohesion-block] injected (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[cohesion-block] failed: %s", e); return None
        post_tasks['cohesion_datasets_block'] = _fetch_cohesion_safe()

        # 3q. On-demand: Combined Nomenclature / CN codes block (live HTTP)
        cn_intent = self._detect_cn_intent(user_message)
        async def _fetch_cn_safe():
            if not cn_intent: return None
            try:
                block = await self._fetch_cn_block(user_message, cn_intent)
                if block: logger.info("[cn-block] injected (%d chars)", len(block))
                return block
            except Exception as e:
                logger.warning("[cn-block] failed: %s", e); return None
        post_tasks['cn_codes_block'] = _fetch_cn_safe()

        # 3r. Commission Document Register (Layer 2)
        commreg_intent = self._detect_commreg_intent(user_message)
        async def _fetch_commreg_safe():
            if not commreg_intent: return None
            try:
                b = await self._fetch_commreg_block(user_message, commreg_intent)
                if b: logger.info("[commreg-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[commreg-block] failed: %s", e); return None
        post_tasks['commission_register_block'] = _fetch_commreg_safe()

        # 3s. Delegated + Implementing acts (Layer 2)
        delegated_intent = self._detect_delegated_intent(user_message)
        async def _fetch_delegated_safe():
            if not delegated_intent: return None
            try:
                b = await self._fetch_delegated_block(user_message, delegated_intent)
                if b: logger.info("[delegated-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[delegated-block] failed: %s", e); return None
        post_tasks['delegated_acts_block'] = _fetch_delegated_safe()

        # 3t. ECLI court rulings (Layer 2)
        ecli_intent = self._detect_ecli_intent(user_message)
        async def _fetch_ecli_safe():
            if not ecli_intent: return None
            try:
                b = await self._fetch_ecli_block(user_message, ecli_intent)
                if b: logger.info("[ecli-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[ecli-block] failed: %s", e); return None
        post_tasks['ecli_block'] = _fetch_ecli_safe()

        # 3u. EURIO research projects (Layer 2)
        eurio_intent = self._detect_eurio_intent(user_message)
        async def _fetch_eurio_safe():
            if not eurio_intent: return None
            try:
                b = await self._fetch_eurio_block(user_message, eurio_intent)
                if b: logger.info("[eurio-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[eurio-block] failed: %s", e); return None
        post_tasks['eurio_research_block'] = _fetch_eurio_safe()

        # 3v. EU open funding calls (Layer 2b)
        funding_intent = self._detect_funding_intent(user_message)
        async def _fetch_funding_safe():
            if not funding_intent: return None
            try:
                b = await self._fetch_funding_block(user_message, funding_intent)
                if b: logger.info("[funding-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[funding-block] failed: %s", e); return None
        post_tasks['eu_funding_block'] = _fetch_funding_safe()

        # 3w. Council documents + meetings (Layer 2c)
        council_intent = self._detect_council_intent(user_message)
        async def _fetch_council_safe():
            if not council_intent: return None
            try:
                b = await self._fetch_council_block(user_message, council_intent)
                if b: logger.info("[council-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[council-block] failed: %s", e); return None
        post_tasks['council_documents_block'] = _fetch_council_safe()

        # 3x. Commission infringement procedures (Layer 2c)
        infring_intent = self._detect_infringement_intent(user_message)
        async def _fetch_infring_safe():
            if not infring_intent: return None
            try:
                b = await self._fetch_infringement_block(user_message, infring_intent)
                if b: logger.info("[infringement-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[infringement-block] failed: %s", e); return None
        post_tasks['infringements_block'] = _fetch_infring_safe()

        # 3y. Commission Transparency Register meetings (Layer 2d)
        tr_meetings_intent = self._detect_tr_meetings_intent(user_message)
        async def _fetch_tr_meetings_safe():
            if not tr_meetings_intent: return None
            try:
                b = await self._fetch_tr_meetings_block(user_message, tr_meetings_intent)
                if b: logger.info("[tr-meetings-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[tr-meetings-block] failed: %s", e); return None
        post_tasks['transparency_meetings_block'] = _fetch_tr_meetings_safe()

        # 3z. Commissioners list (Layer 2e — added 12 May 2026 after audit)
        commissioners_intent = self._detect_commissioners_intent(user_message)
        async def _fetch_commissioners_safe():
            if not commissioners_intent: return None
            try:
                b = await self._fetch_commissioners_block(user_message)
                if b: logger.info("[commissioners-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[commissioners-block] failed: %s", e); return None
        post_tasks['commissioners_block'] = _fetch_commissioners_safe()

        # 3aa. DG personnel — directors of DG X (Layer 2f — added 12 May 2026)
        dg_personnel_intent = self._detect_dg_personnel_intent(user_message)
        async def _fetch_dg_personnel_safe():
            if not dg_personnel_intent: return None
            try:
                b = await self._fetch_dg_personnel_block(user_message, dg_personnel_intent)
                if b: logger.info("[dg-personnel-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[dg-personnel-block] failed: %s", e); return None
        post_tasks['dg_personnel_block'] = _fetch_dg_personnel_safe()

        # 3bb. Procedure rapporteur — lead + shadows (Layer 2g — added 12 May 2026)
        procedure_rapporteur_intent = self._detect_procedure_rapporteur_intent(user_message)
        async def _fetch_procedure_rapporteur_safe():
            if not procedure_rapporteur_intent: return None
            try:
                b = await self._fetch_procedure_rapporteur_block(user_message, procedure_rapporteur_intent)
                if b: logger.info("[procedure-rapporteur-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[procedure-rapporteur-block] failed: %s", e); return None
        post_tasks['procedure_rapporteur_block'] = _fetch_procedure_rapporteur_safe()

        # 3cc. EP committee meeting agenda (Layer 2h — added 12 May 2026)
        committee_agenda_intent = self._detect_committee_meeting_agenda_intent(user_message)
        async def _fetch_committee_agenda_safe():
            if not committee_agenda_intent: return None
            try:
                b = await self._fetch_committee_meeting_agenda_block(user_message, committee_agenda_intent)
                if b: logger.info("[committee-agenda-block] injected (%d chars)", len(b))
                return b
            except Exception as e:
                logger.warning("[committee-agenda-block] failed: %s", e); return None
        post_tasks['committee_agenda_block'] = _fetch_committee_agenda_safe()

        # 4. EU institutional source search fallback
        async def _fetch_eu_search_safe():
            if not (self.tavily_client and self.enable_web_search):
                return []

            procedure_intent_phrases = [
                'timeline', 'status', 'rapporteur', 'shadow', 'deadline',
                'vote', 'adopted', 'tabled', 'reading', 'trilogue',
                'committee report', 'plenary vote', 'amendment deadline',
                'ini ', ' ini', 'own-initiative', 'cod ', ' cod',
                'procedure', 'legislative procedure',
            ]
            has_procedure_intent = any(p in query_lower for p in procedure_intent_phrases)
            no_procedure_data = not procedure_details

            has_trigger_match = any(
                item.get('trigger_matched', False)
                for item in internal_knowledge
                if item.get('type') == 'guide'
            )
            only_content_fallback = bool(internal_knowledge) and not has_trigger_match

            current_event_phrases = [
                'decision to', 'decided to', 'announced', 'just announced',
                'new rule', 'new ban', 'ban on', 'banned', 'prevent',
                'launched', 'just launched', 'unveiled', 'proposed today',
                'yesterday', 'this week', 'this morning', 'today',
            ]
            has_current_event_signal = any(p in query_lower for p in current_event_phrases)

            should_search = (
                not internal_knowledge
                or (has_procedure_intent and no_procedure_data)
                or (only_content_fallback and has_current_event_signal)
            )

            if should_search:
                try:
                    return await self._fetch_eu_institutional_search(query=user_message)
                except Exception as e:
                    logger.warning(f"[EU-SEARCH] Institutional fallback failed: {e}")
            return []

        post_tasks['eu_search'] = _fetch_eu_search_safe()

        # Execute all post-gather tasks in parallel
        post_keys = list(post_tasks.keys())
        post_results = await asyncio.gather(*post_tasks.values(), return_exceptions=True)
        post_map = {}
        for key, result in zip(post_keys, post_results):
            post_map[key] = result if not isinstance(result, Exception) else ([] if key != 'debate' else None)

        rapporteur_by_country = post_map['rapporteur']
        cellar_legislation = post_map['cellar']
        plenary_debate_transcript = post_map['debate']
        eu_institutional_results = post_map['eu_search']
        consultation_feedback_block = post_map.get('consultation_feedback')

        # --- Tier-3 backstop (v1 API coverage reinforcer) -------------------
        # Principle: every chat query must be covered. If Tier 1 (DB smart
        # filters) and Tier 2 (on-demand fetchers) left key surfaces empty,
        # re-query with the simpler broad-filter logic that powers the public
        # v1 API endpoints. Ensures a chat query never fails because a smart
        # filter was too aggressive. See memory/feedback_three_tier_coverage.md.
        try:
            fallback_events = await self._fetch_api_fallback_calendar(
                query=user_message,
                entities=entities,
                existing_events=eu_calendar_events,
            )
            if fallback_events:
                existing_ids = {e.get('title') for e in eu_calendar_events or []}
                merged = list(eu_calendar_events or [])
                for ev in fallback_events:
                    if ev.get('title') not in existing_ids:
                        merged.append(ev)
                eu_calendar_events = merged
                logger.info("[tier3] Calendar backstop added %d events (total now %d)", len(fallback_events), len(eu_calendar_events))
        except Exception as e:
            logger.warning("[tier3] Calendar backstop failed: %s", e)

        # Private user bundle (per-user gitignored knowledge guides).
        # Resolves users.private_guide_slug + status='ready' via the DB, then
        # loads from backend/knowledge_base/private_guides/{slug}/*.md. Fail-soft:
        # any error returns None so chat falls back to the standard retrieval.
        private_guide_block = None
        if user_id:
            try:
                from core.database import SessionLocal as _PG_SessionLocal
                from models.user import User as _PG_User
                from knowledge_base.knowledge_loader import (
                    get_knowledge_loader as _pg_get_loader,
                )
                _pg_db = _PG_SessionLocal()
                try:
                    _pg_user = _pg_db.query(_PG_User).filter(
                        _PG_User.id == user_id
                    ).first()
                    if (
                        _pg_user
                        and _pg_user.private_guide_slug
                        and _pg_user.private_guide_status in ("ready", "locked")
                    ):
                        _pg_loader = _pg_get_loader()
                        private_guide_block = _pg_loader.format_private_guides_block(
                            _pg_user.private_guide_slug
                        )
                        if private_guide_block:
                            logger.info(
                                "[private-guide] Injected bundle for slug=%s status=%s (%d chars)",
                                _pg_user.private_guide_slug,
                                _pg_user.private_guide_status,
                                len(private_guide_block),
                            )
                finally:
                    _pg_db.close()
            except Exception as _pg_err:
                logger.warning("[private-guide] Lookup failed (fail-soft): %s", _pg_err)

        commissioner_agenda_block = post_map.get('commissioner_agenda')
        position_block = post_map.get('position')
        committee_transcript_block = post_map.get('committee_transcript')
        today_block = post_map.get('today_block')
        daily_brief_block = post_map.get('daily_brief_block')
        audience_brief_block = post_map.get('audience_brief_block')
        legal_text_article_block = post_map.get('legal_text_article_block')
        cellar_discovery_block = post_map.get('cellar_discovery_block')
        sanctions_block = post_map.get('sanctions_block')
        transparency_register_block = post_map.get('transparency_register_block')
        comitology_block = post_map.get('comitology_block')
        gi_block = post_map.get('gi_block')
        fta_block = post_map.get('fta_block')
        trade_defence_block = post_map.get('trade_defence_block')
        competition_cases_block = post_map.get('competition_cases_block')
        jrc_datasets_block = post_map.get('jrc_datasets_block')
        cohesion_datasets_block = post_map.get('cohesion_datasets_block')
        cn_codes_block = post_map.get('cn_codes_block')
        commission_register_block = post_map.get('commission_register_block')
        delegated_acts_block = post_map.get('delegated_acts_block')
        ecli_block = post_map.get('ecli_block')
        eurio_research_block = post_map.get('eurio_research_block')
        eu_funding_block = post_map.get('eu_funding_block')
        council_documents_block = post_map.get('council_documents_block')
        infringements_block = post_map.get('infringements_block')
        transparency_meetings_block = post_map.get('transparency_meetings_block')

        # Build reference data context (synchronous, fast)
        reference_data_context = self._build_reference_data_context(user_message)
        parliamentary_questions_block = self._fetch_parliamentary_questions_block(
            user_message
        )
        roll_call_block = self._fetch_roll_call_block(user_message)
        lobby_meetings_block = self._fetch_lobby_meetings_block(user_message)
        amendment_documents_block = self._fetch_amendment_documents_block(user_message)
        competitor_guard_block = self._build_competitor_guard_block(user_message)

        # Calculate metadata
        search_time = (datetime.now() - start_time).total_seconds() * 1000
        tender_source_count = len(tender_context.tenders) + len(tender_context.user_matches) if tender_context else 0
        total_sources = (
            len(relevant_documents) +
            len(legislation_details) +
            len(procedure_details) +
            len(mep_profiles) +
            len(committee_info) +
            len(ec_personnel) +
            len(legislative_train_files) +
            len(recent_rss_entries) +
            len(internal_knowledge) +
            len(eprs_publications) +  # Phase 2
            len(local_eu_laws) +  # Local laws
            tender_source_count +  # Phase 8: Tender data
            len(web_search_results) +  # Tavily web search
            len(beresol_content) +  # Beresol open reports
            len(committee_work_items) +  # EP Committee Work
            len(public_consultations) +  # EC Public Consultations
            len(commission_documents) +  # EC Commission Documents
            len(toolbox_results) +  # MCP Toolbox supplementary
            len(user_uploaded_documents) +  # User uploaded documents
            len(mep_amendments_summary) +  # MEP amendments
            len(eu_calendar_events) +  # EU Calendar events
            len(cellar_legislation) +  # CELLAR on-demand fallback
            len(eu_institutional_results)  # EU institutional source search
        )

        context_data = ContextData(
            relevant_documents=relevant_documents,
            entities=entities,
            legislation_details=legislation_details,
            procedure_details=procedure_details,
            mep_profiles=mep_profiles,
            committee_info=committee_info,
            ec_personnel=ec_personnel,
            legislative_train_files=legislative_train_files,
            recent_rss_entries=recent_rss_entries,
            internal_knowledge=internal_knowledge,
            eprs_publications=eprs_publications,  # Phase 2
            ai_generated_briefings=ai_generated_briefings,  # Phase 5
            local_eu_laws=local_eu_laws,  # Local laws
            web_search_results=web_search_results,  # Tavily web search
            beresol_content=beresol_content,  # Beresol open reports
            committee_work_items=committee_work_items,  # EP Committee Work
            committee_minutes=committee_minutes,  # EP Committee Minutes
            public_consultations=public_consultations,  # EC Public Consultations
            commission_documents=commission_documents,  # EC Commission Documents
            toolbox_results=toolbox_results,  # MCP Toolbox supplementary
            user_uploaded_documents=user_uploaded_documents,  # User uploaded documents
            org_intelligence=org_intelligence,  # Aggregated user profile
            mep_amendments_summary=mep_amendments_summary,  # MEP amendments
            eu_calendar_events=eu_calendar_events,  # EU Calendar events
            cellar_legislation=cellar_legislation if cellar_legislation else None,  # CELLAR fallback
            eu_institutional_results=eu_institutional_results if eu_institutional_results else None,  # EU source search
            tender_context=tender_context,  # Phase 8: Tender data
            drafting_intent=drafting_intent if drafting_intent.is_drafting_query else None,
            rapporteur_by_country=rapporteur_by_country if rapporteur_by_country else None,
            rapporteur_country=detected_country if rapporteur_by_country else None,
            plenary_debate_transcript=plenary_debate_transcript,
            consultation_feedback_block=consultation_feedback_block,
            commissioner_agenda_block=commissioner_agenda_block,
            position_block=position_block,
            committee_transcript_block=committee_transcript_block,
            today_block=today_block,
            daily_brief_block=daily_brief_block,
            audience_brief_block=audience_brief_block,
            legal_text_article_block=legal_text_article_block,
            cellar_discovery_block=cellar_discovery_block,
            sanctions_block=sanctions_block,
            transparency_register_block=transparency_register_block,
            comitology_block=comitology_block,
            gi_block=gi_block,
            fta_block=fta_block,
            trade_defence_block=trade_defence_block,
            competition_cases_block=competition_cases_block,
            jrc_datasets_block=jrc_datasets_block,
            cohesion_datasets_block=cohesion_datasets_block,
            cn_codes_block=cn_codes_block,
            commission_register_block=commission_register_block,
            delegated_acts_block=delegated_acts_block,
            ecli_block=ecli_block,
            eurio_research_block=eurio_research_block,
            eu_funding_block=eu_funding_block,
            council_documents_block=council_documents_block,
            infringements_block=infringements_block,
            transparency_meetings_block=transparency_meetings_block,
            private_guide_block=private_guide_block,
            reference_data_context=reference_data_context,
            parliamentary_questions_block=parliamentary_questions_block,
            roll_call_block=roll_call_block,
            lobby_meetings_block=lobby_meetings_block,
            amendment_documents_block=amendment_documents_block,
            competitor_guard_block=competitor_guard_block,
            query=user_message,
            search_time_ms=search_time,
            total_sources=total_sources
        )

        logger.info(
            f"Built context: {total_sources} sources "
            f"({len(relevant_documents)} search, {len(legislation_details)} legislation, "
            f"{len(procedure_details)} procedures, {len(mep_profiles)} MEPs, "
            f"{len(committee_info)} committees, {len(ec_personnel)} EC personnel, "
            f"{len(legislative_train_files)} LT files, {len(recent_rss_entries)} RSS, "
            f"{len(internal_knowledge)} internal, {len(eprs_publications)} EPRS, "
            f"{len(local_eu_laws)} local laws, {tender_source_count} tenders, "
            f"{len(web_search_results)} web, {len(beresol_content)} beresol, "
            f"{len(committee_work_items)} committee work, "
            f"{len(public_consultations)} consultations, "
            f"{len(commission_documents)} commission docs, "
            f"{len(toolbox_results)} toolbox, "
            f"{len(user_uploaded_documents)} user uploads, "
            f"{len(mep_amendments_summary)} MEP amendments, "
            f"{len(eu_calendar_events)} calendar events, "
            f"{len(cellar_legislation)} CELLAR, "
            f"{len(eu_institutional_results)} EU-search) in {search_time:.2f}ms"
        )

        return context_data

    def extract_entities(self, text: str) -> ExtractedEntities:
        """
        Extract EU entities from text.

        Args:
            text: Query text

        Returns:
            ExtractedEntities with all detected entities
        """
        # Use metadata extractor
        extracted = self.metadata_extractor.extract_all(text)

        # Extract policy areas
        policy_areas = self.metadata_extractor.extract_policy_areas(text)

        # Extract DG codes
        dg_codes = self._extract_dg_codes(text)

        # Detect assistant intent
        assistant_intent = self.metadata_extractor.detect_assistant_intent(text)

        # Phase 4: Tenderator bridge entities
        funding_topic_ids = _extract_funding_topic_ids(text)
        funding_programmes = _extract_funding_programmes(text)
        agency_codes = _extract_agency_codes(text)

        return ExtractedEntities(
            celex_numbers=extracted['celex_numbers'],
            procedure_references=extracted['procedure_references'],
            mep_names=extracted['mep_mentions'],
            committee_codes=[c['code'] for c in extracted['committees']],
            article_references=extracted['articles'],
            policy_areas=policy_areas,
            dg_codes=dg_codes,
            assistant_intent=assistant_intent,
            funding_topic_ids=funding_topic_ids,
            funding_programmes=funding_programmes,
            agency_codes=agency_codes,
        )

    def _extract_dg_codes(self, text: str) -> List[str]:
        """
        Extract European Commission DG codes from text.

        Detects patterns like:
        - "DG GROW"
        - "DG Grow"
        - "GROW" (when context suggests a DG)
        - "Director General of DG CLIMA"

        Args:
            text: Query text

        Returns:
            List of DG codes (e.g., ['GROW', 'CLIMA'])
        """
        dg_codes = []
        text_upper = text.upper()

        # Pattern 1: "DG [CODE]" format
        dg_pattern = r'\bDG\s+([A-Z]{2,6})\b'
        matches = re.findall(dg_pattern, text_upper)
        dg_codes.extend(matches)

        # Pattern 2: Check if standalone DG codes are mentioned
        # Get all available DG codes from knowledge loader
        available_dgs = self.knowledge_loader.list_all_dgs() if self.knowledge_loader else []
        available_codes = {dg['dg_code'].upper() for dg in available_dgs}

        # Look for standalone codes (e.g., "GROW", "CLIMA")
        words = re.findall(r'\b[A-Z]{2,6}\b', text_upper)
        for word in words:
            if word in available_codes and word not in dg_codes:
                # Additional context check to avoid false positives
                # Check if nearby words suggest Commission context
                context_keywords = ['COMMISSION', 'DIRECTOR', 'GENERAL', 'DIRECTORATE']
                if any(keyword in text_upper for keyword in context_keywords):
                    dg_codes.append(word)

        # Pattern 3: Map policy/topic keywords to DG codes
        # Catches queries like "who should I contact about agrifood?" -> AGRI, SANTE
        # Uses word boundaries to avoid false positives (e.g. "euro" in "European",
        # "culture" in "agriculture")
        text_lower = text.lower()
        for keyword, dg_list in POLICY_TO_DG.items():
            if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                for dg in dg_list:
                    if dg not in dg_codes:
                        dg_codes.append(dg)

        # Pattern 4: Non-Commission institutions (Council, European Council, COREPER)
        # These map to organigramme JSONs: EURCOU.json, GSC.json, COREPER.json, GOVREP.json
        INSTITUTION_KEYWORDS = {
            # === European Council ===
            'european council': 'EURCOU', 'euco': 'EURCOU',
            'council presidency': 'EURCOU',
            'heads of state': 'EURCOU', 'heads of government': 'EURCOU',
            # ES
            'consejo europeo': 'EURCOU', 'jefes de estado': 'EURCOU',
            'presidencia del consejo': 'EURCOU',
            # CA
            'consell europeu': 'EURCOU', 'caps d\'estat': 'EURCOU',
            'presidència del consell': 'EURCOU',
            # FR
            'conseil européen': 'EURCOU', 'chefs d\'état': 'EURCOU',
            'présidence du conseil': 'EURCOU',
            # NL
            'europese raad': 'EURCOU', 'staatshoofden': 'EURCOU',
            # IT
            'consiglio europeo': 'EURCOU', 'capi di stato': 'EURCOU',

            # === General Secretariat of the Council ===
            'general secretariat of the council': 'GSC',
            'council secretariat': 'GSC', 'gsc': 'GSC',
            'secretariat-general of the council': 'GSC',
            # ES
            'secretaría general del consejo': 'GSC',
            # CA
            'secretaria general del consell': 'GSC',
            # FR
            'secrétariat général du conseil': 'GSC',
            # NL
            'secretariaat-generaal van de raad': 'GSC',
            # IT
            'segretariato generale del consiglio': 'GSC',

            # === COREPER ===
            'coreper': 'COREPER',
            'permanent representative': 'COREPER',
            'permanent representation': 'COREPER',
            # ES
            'representante permanente': 'COREPER',
            'representación permanente': 'COREPER',
            # CA
            'representant permanent': 'COREPER',
            'representació permanent': 'COREPER',
            # FR
            'représentant permanent': 'COREPER',
            'représentation permanente': 'COREPER',
            # NL
            'permanente vertegenwoordiger': 'COREPER',
            'permanente vertegenwoordiging': 'COREPER',
            # IT
            'rappresentante permanente': 'COREPER',
            'rappresentanza permanente': 'COREPER',

            'government representative': 'GOVREP',

            # === European Parliament ===
            'ep secretariat': 'EP_SG', 'ep secretary general': 'EP_SG',
            'secretariat general of the parliament': 'EP_SG',
            'secretariat-general of the european parliament': 'EP_SG',
            'ep directorate': 'EP_SG', 'ep dg': 'EP_SG',
            # ES
            'secretaría general del parlamento': 'EP_SG',
            'parlamento europeo secretaría': 'EP_SG',
            # CA
            'secretaria general del parlament': 'EP_SG',
            'parlament europeu secretaria': 'EP_SG',
            # FR
            'secrétariat général du parlement': 'EP_SG',
            'parlement européen secrétariat': 'EP_SG',
            # NL
            'secretariaat-generaal van het parlement': 'EP_SG',
            'europees parlement secretariaat': 'EP_SG',
            # IT
            'segretariato generale del parlamento': 'EP_SG',
            'parlamento europeo segretariato': 'EP_SG',

            'political group secretariat': 'EP_GROUP_SEC',
            'group secretariat': 'EP_GROUP_SEC',
            # ES/CA/FR/IT
            'secretaría del grupo': 'EP_GROUP_SEC',
            'secretaria del grup': 'EP_GROUP_SEC',
            'secrétariat du groupe': 'EP_GROUP_SEC',
            'segretariato del gruppo': 'EP_GROUP_SEC',

            # === European Central Bank ===
            'ecb': 'ECB', 'bce': 'ECB',
            'european central bank': 'ECB',
            'central bank': 'ECB',
            # ES
            'banco central europeo': 'ECB',
            # CA
            'banc central europeu': 'ECB',
            # FR
            'banque centrale européenne': 'ECB',
            # NL
            'europese centrale bank': 'ECB',
            # IT
            'banca centrale europea': 'ECB',

            # === Court of Justice ===
            'court of justice': 'ECJ', 'cjeu': 'ECJ', 'ecj': 'ECJ',
            'general court': 'ECJ',
            # ES
            'tribunal de justicia': 'ECJ', 'tjue': 'ECJ',
            'tribunal general': 'ECJ',
            # CA
            'tribunal de justícia': 'ECJ',
            # FR
            'cour de justice': 'ECJ',
            'tribunal général': 'ECJ',
            # NL
            'hof van justitie': 'ECJ',
            'gerecht': 'ECJ',
            # IT
            'corte di giustizia': 'ECJ',
            'tribunale generale': 'ECJ',

            # === Court of Auditors ===
            'court of auditors': 'ECA', 'eca': 'ECA',
            # ES
            'tribunal de cuentas': 'ECA',
            # CA
            'tribunal de comptes': 'ECA',
            # FR
            'cour des comptes': 'ECA',
            # NL
            'rekenkamer': 'ECA',
            # IT
            'corte dei conti': 'ECA',

            # === EEAS ===
            'eeas': 'EEAS',
            'external action service': 'EEAS',
            'eu delegations': 'EEAS',
            # ES
            'servicio europeo de acción exterior': 'EEAS',
            'seae': 'EEAS',
            'delegaciones de la ue': 'EEAS',
            # CA
            'servei europeu d\'acció exterior': 'EEAS',
            'delegacions de la ue': 'EEAS',
            # FR
            'service européen pour l\'action extérieure': 'EEAS',
            'délégations de l\'ue': 'EEAS',
            # NL
            'europese dienst voor extern optreden': 'EEAS',
            'edeo': 'EEAS',
            # IT
            'servizio europeo per l\'azione esterna': 'EEAS',
            'delegazioni dell\'ue': 'EEAS',

            # === Committee of the Regions ===
            'committee of the regions': 'COR', 'cor': 'COR',
            # ES
            'comité de las regiones': 'COR', 'cdr': 'COR',
            # CA
            'comitè de les regions': 'COR',
            # FR
            'comité des régions': 'COR',
            # NL
            'comité van de regio\'s': 'COR',
            # IT
            'comitato delle regioni': 'COR',

            # === EESC ===
            'economic and social committee': 'EESC', 'eesc': 'EESC',
            # ES
            'comité económico y social': 'EESC', 'cese': 'EESC',
            # CA
            'comitè econòmic i social': 'EESC',
            # FR
            'comité économique et social': 'EESC',
            # NL
            'economisch en sociaal comité': 'EESC',
            # IT
            'comitato economico e sociale': 'EESC',

            # === EIB ===
            'european investment bank': 'EIB', 'eib': 'EIB', 'bei': 'EIB',
            # ES
            'banco europeo de inversiones': 'EIB',
            # CA
            'banc europeu d\'inversions': 'EIB',
            # FR
            'banque européenne d\'investissement': 'EIB',
            # NL
            'europese investeringsbank': 'EIB',
            # IT
            'banca europea per gli investimenti': 'EIB',

            # === EDPS ===
            'data protection supervisor': 'EDPS', 'edps': 'EDPS', 'edpb': 'EDPS',
            # ES
            'supervisor europeo de protección de datos': 'EDPS',
            'protección de datos': 'EDPS',
            # CA
            'supervisor europeu de protecció de dades': 'EDPS',
            'protecció de dades': 'EDPS',
            # FR
            'contrôleur européen de la protection des données': 'EDPS',
            'protection des données': 'EDPS',
            # NL
            'europese toezichthouder voor gegevensbescherming': 'EDPS',
            'gegevensbescherming': 'EDPS',
            # IT
            'garante europeo della protezione dei dati': 'EDPS',
            'protezione dei dati': 'EDPS',

            # === Ombudsman ===
            'ombudsman': 'OMBUDSMAN',
            # ES
            'defensor del pueblo europeo': 'OMBUDSMAN',
            # CA
            'defensor del poble europeu': 'OMBUDSMAN',
            # FR
            'médiateur européen': 'OMBUDSMAN',
            # NL
            'europese ombudsman': 'OMBUDSMAN',
            # IT
            'mediatore europeo': 'OMBUDSMAN',

            # === Agencies ===
            'eu agencies': 'AGENCIES',
            # ES
            'agencias de la ue': 'AGENCIES', 'agencias europeas': 'AGENCIES',
            # CA
            'agències de la ue': 'AGENCIES', 'agències europees': 'AGENCIES',
            # FR
            'agences de l\'ue': 'AGENCIES', 'agences européennes': 'AGENCIES',
            # NL
            'eu-agentschappen': 'AGENCIES', 'europese agentschappen': 'AGENCIES',
            # IT
            'agenzie dell\'ue': 'AGENCIES', 'agenzie europee': 'AGENCIES',

            # === European Parliament (institution queries) ===
            'european parliament': 'EP',
            # ES
            'parlamento europeo': 'EP',
            # CA
            'parlament europeu': 'EP',
            # FR
            'parlement européen': 'EP',
            # NL
            'europees parlement': 'EP',
            # IT
            'parlamento europeo': 'EP',

            # === European Commission (full institution) ===
            'european commission': 'COMMISSION',
            # ES
            'comisión europea': 'COMMISSION',
            # CA
            'comissió europea': 'COMMISSION',
            # FR
            'commission européenne': 'COMMISSION',
            # NL
            'europese commissie': 'COMMISSION',
            # IT
            'commissione europea': 'COMMISSION',
        }
        for keyword, inst_code in INSTITUTION_KEYWORDS.items():
            if keyword in text_lower and inst_code not in dg_codes:
                dg_codes.append(inst_code)

        # Also detect "council" in personnel context (who works at, head of, director)
        if any(kw in text_lower for kw in CONTACT_INTENT_PHRASES):
            # Council detection (EN/ES/CA/FR/NL/IT)
            council_patterns = r'\b(?:council|consejo|consell|conseil|raad|consiglio)\b'
            eu_council_patterns = r'(?:european council|consejo europeo|consell europeu|conseil européen|europese raad|consiglio europeo)'
            if re.search(council_patterns, text_lower) and not re.search(eu_council_patterns, text_lower):
                if 'GSC' not in dg_codes:
                    dg_codes.append('GSC')
            # EP personnel queries (EN/ES/CA/FR/NL/IT)
            if re.search(r'\b(?:parliament|parlamento|parlament|parlement|parlamento)\b|\bep\b', text_lower):
                if 'EP_SG' not in dg_codes:
                    dg_codes.append('EP_SG')

        return list(set(dg_codes))  # Remove duplicates

    async def _fetch_legislation_details(
        self,
        celex_numbers: List[str]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Fetch legislation details from EUR-Lex API.

        Phase 3: Automatically includes EPRS explainers if auto_include_explainers is True.
        Phase 5: Generates AI briefing if no EPRS explainer exists or if outdated.

        Returns:
            Tuple of (legislation_details, ai_generated_briefings)
        """
        details = []
        ai_briefings = []

        for celex in celex_numbers:
            try:
                # Get document metadata
                metadata = await self.eurlex_client.get_document_metadata(celex)

                # Get document text (excerpt for display, full for AI generation)
                text_response = await self.eurlex_client.get_document_text(celex, format='txt')
                text_excerpt = text_response[:2000] if text_response else ""
                full_text = text_response[:15000] if text_response else ""  # For AI generation

                leg_detail = {
                    'celex': celex,
                    'title': metadata.get('title', ''),
                    'date': metadata.get('date', ''),
                    'type': metadata.get('type', ''),
                    'status': metadata.get('status', ''),
                    'text_excerpt': text_excerpt,
                    'url': f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
                }

                # Phase 3: Auto-include EPRS explainers
                has_current_explainer = False
                if self.auto_include_explainers and self.eprs_matcher is not None:
                    explainers = await self.eprs_matcher.find_explainers_for_celex(
                        celex=celex,
                        max_results=2
                    )

                    if explainers:
                        leg_detail['eprs_explainers'] = explainers
                        has_current_explainer = True
                        logger.debug(
                            f"Auto-included {len(explainers)} EPRS explainers for {celex}"
                        )

                        # Phase 5: Check freshness of EPRS explainers
                        if self.enable_freshness_check and explainers:
                            try:
                                # Get briefing date from first explainer
                                first_explainer = explainers[0]
                                briefing_date_str = first_explainer.get('metadata', {}).get('publication_date')

                                if briefing_date_str:
                                    briefing_date = datetime.fromisoformat(briefing_date_str.replace("Z", "+00:00"))

                                    # Check freshness
                                    freshness_status = await self.freshness_detector.check_briefing_freshness(
                                        briefing_date=briefing_date,
                                        celex=celex,
                                        legislation_data=metadata
                                    )

                                    # Add freshness info to explainer
                                    leg_detail['eprs_explainers_freshness'] = {
                                        'level': freshness_status.freshness_level.value,
                                        'is_outdated': freshness_status.is_outdated,
                                        'days_outdated': freshness_status.days_outdated,
                                        'recommendation': freshness_status.recommendation,
                                        'needs_ai_update': freshness_status.needs_ai_update
                                    }

                                    # If outdated, mark it
                                    if freshness_status.is_outdated:
                                        logger.info(
                                            f"EPRS briefing for {celex} is outdated "
                                            f"({freshness_status.days_outdated} days behind)"
                                        )
                                        has_current_explainer = False  # Trigger AI generation

                            except Exception as e:
                                logger.warning(f"Freshness check failed for {celex}: {str(e)}")

                # Phase 5: Generate AI briefing if no current explainer exists
                if self.enable_ai_summaries and not has_current_explainer:
                    logger.info(f"No current EPRS briefing for {celex}, generating AI briefing...")

                    try:
                        ai_briefing = await self.ai_summary_generator.generate_legislative_briefing(
                            celex=celex,
                            title=metadata.get('title', ''),
                            legal_text=full_text,
                            metadata={
                                'date': metadata.get('date'),
                                'type': metadata.get('type'),
                                'status': metadata.get('status')
                            }
                        )

                        # Add to AI briefings list
                        ai_briefings.append({
                            'celex': celex,
                            'title': ai_briefing.title,
                            'summary': ai_briefing.summary,
                            'key_points': ai_briefing.key_points,
                            'background': ai_briefing.background,
                            'main_provisions': ai_briefing.main_provisions,
                            'confidence_score': ai_briefing.confidence_score,
                            'generated_at': ai_briefing.generated_at.isoformat(),
                            'source': 'ai_generated'
                        })

                        logger.info(
                            f"Generated AI briefing for {celex} "
                            f"(confidence: {ai_briefing.confidence_score:.2%})"
                        )

                    except Exception as e:
                        logger.error(f"Failed to generate AI briefing for {celex}: {str(e)}")

                details.append(leg_detail)

                logger.debug(f"Fetched legislation: {celex}")

            except Exception as e:
                logger.error(f"Failed to fetch legislation {celex}: {str(e)}")

        return details, ai_briefings

    async def _fetch_procedure_details(
        self,
        procedure_references: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch procedure details from OEIL API.

        Phase 3: Automatically includes EPRS explainers (especially "At a Glance" summaries).
        """
        details = []

        for proc_ref in procedure_references:
            proc_detail: Optional[Dict[str, Any]] = None
            try:
                procedure = await self.oeil_client.get_procedure(proc_ref)

                # Only accept the live result if it actually resolved to a real
                # procedure (a title). An empty/minimal dict means the OEIL page
                # 404'd or timed out -- in that case we must fall back to the DB,
                # otherwise the chat tells the user the procedure "is not in the
                # database" when legislative_carriages in fact holds it
                # (audit defect, 18 Jun 2026: 2023/0271(COD) reported missing).
                if procedure and procedure.get('title'):
                    proc_detail = {
                        'reference': proc_ref,
                        'title': procedure.get('title', ''),
                        'type': procedure.get('type', ''),
                        'status': procedure.get('current_stage', ''),
                        'timeline': procedure.get('events', [])[:5],  # Last 5 events
                        'committees': procedure.get('committees', []),
                        'meps': {
                            'rapporteur': procedure.get('rapporteur', ''),
                            'shadows': procedure.get('shadow_rapporteurs', [])
                        },
                        'url': f"https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={proc_ref}",
                        'source': 'oeil_live',
                    }
                    logger.debug(f"Fetched procedure (live OEIL): {proc_ref}")

            except Exception as e:
                logger.error(f"Failed to fetch procedure {proc_ref} (live OEIL): {str(e)}")

            # DB fallback: live OEIL fetch missing/empty -> read legislative_carriages
            # (same source get_procedure_status / the v1 API reads, so chat and API agree).
            if proc_detail is None:
                proc_detail = self._fetch_procedure_from_carriage(proc_ref)
                if proc_detail:
                    logger.info(f"Fetched procedure (DB carriage fallback): {proc_ref}")

            if proc_detail is None:
                continue

            # Phase 3: Auto-include EPRS explainers (prioritize "At a Glance")
            # -- attach regardless of whether the detail came from OEIL or the DB.
            if self.auto_include_explainers and self.eprs_matcher is not None:
                try:
                    explainers = await self.eprs_matcher.find_explainers_for_procedure(
                        procedure_ref=proc_ref,
                        max_results=2,
                        prefer_at_a_glance=True
                    )
                    if explainers:
                        proc_detail['eprs_explainers'] = explainers
                        logger.debug(
                            f"Auto-included {len(explainers)} EPRS explainers for {proc_ref}"
                        )
                except Exception as e:
                    logger.debug(f"EPRS explainer lookup failed for {proc_ref}: {str(e)}")

            details.append(proc_detail)

        return details

    def _fetch_procedure_from_carriage(self, proc_ref: str) -> Optional[Dict[str, Any]]:
        """
        DB fallback for a procedure reference when the live OEIL fetch fails.

        Reads the same legislative_carriages row that get_procedure_status (the
        MCP/v1 API) reads, so the chat and the API never disagree about whether a
        procedure exists. Returns a dict in the same shape as the live OEIL path
        (so the downstream formatter is unchanged), or None if genuinely absent.
        """
        db = SessionLocal()
        try:
            row = db.query(LegislativeCarriage).filter(
                LegislativeCarriage.oeil_procedure_ref == proc_ref
            ).first()
            if row is None:
                # Tolerate trailing/format noise (e.g. "2023/0271 (COD)")
                row = db.query(LegislativeCarriage).filter(
                    LegislativeCarriage.oeil_procedure_ref.ilike(f"%{proc_ref}%")
                ).first()
            if row is None:
                return None

            # current_status is a CarriageStatusEnum -> emit the clean name
            # ("ADOPTED"), matching the live OEIL path which returns a plain string.
            status = getattr(row.current_status, 'name', None) or (str(row.current_status) if row.current_status else '')

            events = row.oeil_key_events or []
            if not isinstance(events, list):
                events = []

            committees: List[str] = []
            if row.lead_committee:
                committees.append(row.lead_committee)
            if isinstance(row.opinion_committees, list):
                committees.extend([c for c in row.opinion_committees if c])

            return {
                'reference': proc_ref,
                'title': row.title or '',
                'type': row.text_type or '',
                'status': status,
                'timeline': events[:5],
                'committees': committees,
                'meps': {'rapporteur': '', 'shadows': []},
                'url': f"https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={proc_ref}",
                'celex_numbers': row.celex_numbers or [],
                'source': 'db_carriage',
            }
        except Exception as e:
            logger.error(f"DB carriage fallback failed for {proc_ref}: {str(e)}")
            return None
        finally:
            db.close()

    async def _fetch_mep_profiles(
        self,
        mep_names: List[str],
        include_assistants: bool = False
    ) -> List[Dict[str, Any]]:
        """Fetch MEP profiles from European Parliament scraper (includes email/phone)"""
        from services.scrapers.european_parliament_scraper import EuropeanParliamentScraper

        profiles = []
        scraper = None

        try:
            scraper = EuropeanParliamentScraper()

            for name in mep_names:
                try:
                    # Search for MEP by name using scraper
                    search_results = await scraper.search_meps(name)

                    if search_results:
                        mep = search_results[0]  # Take first match
                        mep_id = mep.mep_id

                        # Get detailed profile (includes email, phone, committees)
                        if mep_id:
                            details = await scraper.get_mep_details(mep_id)

                            profile = {
                                'mep_id': mep_id,
                                'name': mep.full_name,
                                'country': mep.country or '',
                                'party': mep.national_party or '',
                                'group': mep.political_group.name if mep.political_group else '',
                                'committees': details.get('committees', []),
                                'delegations': details.get('delegations', []),
                                'email': details.get('email', ''),
                                'phone': details.get('phone', ''),
                                'url': f"https://www.europarl.europa.eu/meps/en/{mep_id}"
                            }

                            # Fetch assistant data if the user is asking about assistants
                            if include_assistants:
                                try:
                                    assistants = await scraper.get_mep_assistants(mep_id, mep.full_name)
                                    profile['assistants'] = assistants
                                    profile['assistants_url'] = f"https://www.europarl.europa.eu/meps/en/{mep_id}/{mep.full_name.upper().split()[0]}_{'+'.join(mep.full_name.upper().split()[1:])}/assistants"
                                except Exception as e:
                                    logger.warning(f"Failed to fetch assistants for {name}: {str(e)}")
                                    profile['assistants'] = []

                            profiles.append(profile)
                            logger.debug(f"Fetched MEP profile: {name}")

                except Exception as e:
                    logger.error(f"Failed to fetch MEP {name}: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to initialize EP scraper: {str(e)}")
        finally:
            if scraper:
                await scraper.close()

        return profiles

    async def _fetch_rapporteurs_by_country(
        self,
        country_name: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch all known rapporteurs and shadow rapporteurs from a specific country.
        Aggregates data from legislative_carriages (OEIL cache) and committee_work.
        Uses EP API country filter (ISO code) to get MEPs from target country,
        then matches rapporteur names against that list.

        Args:
            country_name: Country name (e.g., "Spain", "France")

        Returns:
            List of rapporteur entries with name, group, committee, procedure, title, role
        """
        rapporteurs = []
        seen_entries = set()  # (name_lower, procedure_ref, role) to avoid duplicates

        try:
            from sqlalchemy import text
            import json

            db = SessionLocal()

            # 1. Query OEIL-cached rapporteur + shadow data from legislative_carriages
            oeil_results = db.execute(text("""
                SELECT
                    oeil_procedure_data->'key_players'->'committee_responsible'->'rapporteur'->>'name' as rap_name,
                    oeil_procedure_data->'key_players'->'committee_responsible'->'rapporteur'->>'political_group' as rap_grp,
                    oeil_procedure_data->'key_players'->'committee_responsible'->>'shadow_rapporteurs' as shadows_json,
                    lead_committee, oeil_procedure_ref, title
                FROM legislative_carriages
                WHERE oeil_procedure_data IS NOT NULL
                AND oeil_procedure_data->'key_players'->'committee_responsible' IS NOT NULL
            """)).fetchall()

            # 2. Query committee_work rapporteurs
            cw_results = db.execute(text("""
                SELECT rapporteur_name, committee_code, procedure_ref, title
                FROM committee_work_items
                WHERE rapporteur_name IS NOT NULL AND rapporteur_name != ''
            """)).fetchall()

            db.close()

            # Count rapporteurs and shadows from OEIL
            oeil_rap_count = sum(1 for r in oeil_results if r[0])
            oeil_shadow_count = 0
            for r in oeil_results:
                if r[2]:
                    try:
                        shadows = json.loads(r[2]) if isinstance(r[2], str) else r[2]
                        if isinstance(shadows, list):
                            oeil_shadow_count += len(shadows)
                    except (json.JSONDecodeError, TypeError):
                        pass

            logger.info(f"[RAPPORTEUR] DB data: {oeil_rap_count} OEIL rapporteurs, "
                        f"{oeil_shadow_count} OEIL shadows, {len(cw_results)} committee_work")

            # 3. Get all MEPs from the target country using EP API with country code filter
            country_code = COUNTRY_NAME_TO_CODE.get(country_name)
            country_mep_name_parts = {}  # lowercase name -> set of name parts
            country_mep_info = {}  # lowercase name -> {full_name, group, mep_id}

            if country_code:
                try:
                    from services.api_clients.european_parliament_client import EuropeanParliamentClient
                    ep_client = EuropeanParliamentClient()
                    api_meps = await ep_client.get_mep_list(country=country_code, limit=500)
                    await ep_client.close()

                    for mep_data in api_meps:
                        name = mep_data.get('name', '')
                        if not name:
                            continue
                        name_lower = name.lower().strip()
                        parts = set(name_lower.split())
                        country_mep_name_parts[name_lower] = parts
                        country_mep_info[name_lower] = {
                            'full_name': name,
                            'group': '',
                            'mep_id': mep_data.get('id', ''),
                        }

                    logger.info(f"[RAPPORTEUR] EP API returned {len(api_meps)} MEPs for {country_name} ({country_code})")
                except Exception as e:
                    logger.warning(f"[RAPPORTEUR] Failed to fetch MEP list for {country_name}: {e}")
            else:
                logger.warning(f"[RAPPORTEUR] No ISO code found for country: {country_name}")

            # 4. Name matching helper
            CONNECTOR_WORDS = {'de', 'da', 'di', 'van', 'von', 'del', 'la', 'le', 'el', 'dos', 'das'}

            def match_to_country_mep(rapp_name_lower: str):
                """Match a rapporteur name against country MEPs. Requires 2+ name part overlap."""
                rapp_parts = set(rapp_name_lower.split())
                rapp_parts = {p for p in rapp_parts if len(p) > 1 and p not in CONNECTOR_WORDS}

                for mep_name, mep_parts in country_mep_name_parts.items():
                    clean_mep_parts = {p for p in mep_parts if len(p) > 1 and p not in CONNECTOR_WORDS}
                    overlap = rapp_parts & clean_mep_parts
                    if len(overlap) >= 2:
                        return country_mep_info.get(mep_name)
                return None

            def clean_name(name: str) -> tuple:
                """Remove group annotation, return (cleaned_name, cleaned_lower)."""
                if '(' in name:
                    name = name[:name.index('(')].strip()
                return name, name.lower().strip()

            def add_entry(name, group, committee, proc_ref, title, role, source):
                """Add a rapporteur/shadow entry if not duplicate."""
                _, name_lower = clean_name(name)
                entry_key = (name_lower, proc_ref or '', role)
                if entry_key in seen_entries:
                    return False

                matched_info = match_to_country_mep(name_lower)
                if not matched_info:
                    return False

                seen_entries.add(entry_key)
                rapporteurs.append({
                    'name': matched_info.get('full_name', name),
                    'political_group': group or matched_info.get('group', ''),
                    'committee': committee or '',
                    'procedure_ref': proc_ref or '',
                    'file_title': (title or '')[:100],
                    'role': role,
                    'source': source,
                })
                return True

            # 5. Match OEIL lead rapporteurs to country
            for row in oeil_results:
                rap_name = row[0] or ''
                if rap_name:
                    add_entry(rap_name, row[1], row[3], row[4], row[5], 'rapporteur', 'OEIL')

                # 6. Match OEIL shadow rapporteurs to country
                shadows_raw = row[2]
                if shadows_raw:
                    try:
                        shadows = json.loads(shadows_raw) if isinstance(shadows_raw, str) else shadows_raw
                        if isinstance(shadows, list):
                            for shadow in shadows:
                                if isinstance(shadow, dict):
                                    shadow_name = shadow.get('name', '')
                                    shadow_group = shadow.get('political_group', '')
                                    if shadow_name:
                                        add_entry(
                                            shadow_name, shadow_group,
                                            row[3], row[4], row[5],
                                            'shadow rapporteur', 'OEIL'
                                        )
                    except (json.JSONDecodeError, TypeError):
                        pass

            # 7. Match committee_work rapporteurs to country
            for row in cw_results:
                rapp_name = row[0] or ''
                if rapp_name:
                    add_entry(rapp_name, '', row[1], row[2], row[3], 'rapporteur', 'committee_work')

            # Count by role
            lead_count = sum(1 for r in rapporteurs if r['role'] == 'rapporteur')
            shadow_count = sum(1 for r in rapporteurs if r['role'] == 'shadow rapporteur')
            logger.info(f"[RAPPORTEUR] Found {lead_count} rapporteurs + {shadow_count} shadows from {country_name} "
                        f"(checked {len(oeil_results)} OEIL + {len(cw_results)} committee_work "
                        f"against {len(country_mep_name_parts)} {country_name} MEPs)")

        except Exception as e:
            logger.error(f"[RAPPORTEUR] Failed to fetch rapporteurs by country: {e}")
            import traceback
            traceback.print_exc()

        return rapporteurs

    async def _fetch_committee_info(
        self,
        committee_codes: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch committee information including members.

        Uses the European Parliament scraper to get committee details
        and member lists.

        Args:
            committee_codes: List of committee codes (e.g., ['ENVI', 'ITRE'])

        Returns:
            List of committee information dictionaries
        """
        from services.scrapers.european_parliament_scraper import EuropeanParliamentScraper

        committee_data = []
        scraper = None

        try:
            scraper = EuropeanParliamentScraper()

            for code in committee_codes:
                try:
                    # Get committee details with members
                    details = await scraper.get_committee_details(code)

                    # Format member data
                    members_by_role = {}
                    for member in details.get('members', []):
                        role = member.get('role', 'Member')
                        if role not in members_by_role:
                            members_by_role[role] = []
                        members_by_role[role].append({
                            'name': member.get('name', ''),
                            'country': member.get('country', ''),
                            'group': member.get('political_group', ''),
                            'mep_id': member.get('mep_id', '')
                        })

                    committee_data.append({
                        'code': details.get('code', code),
                        'name': details.get('name', ''),
                        'member_count': details.get('member_count', 0),
                        'members_by_role': members_by_role,
                        'url': details.get('url', ''),
                        'last_updated': details.get('last_updated', '')
                    })

                    logger.debug(f"Fetched committee info: {code}")

                except Exception as e:
                    logger.error(f"Failed to fetch committee {code}: {str(e)}")

        except Exception as e:
            logger.error(f"Failed to initialize committee scraper: {str(e)}")
        finally:
            if scraper:
                await scraper.close()

        return committee_data

    async def _fetch_ec_personnel(
        self,
        dg_codes: List[str],
        query_text: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Fetch European Commission personnel information from organigrammes.

        Includes director-general, deputy DGs, directorate directors, and unit heads
        with standard EC email format (firstname.lastname@ec.europa.eu).

        For large institutions (>200 persons, e.g. EP with 6,591), filters units
        to only those matching query keywords to avoid context window overflow.

        Args:
            dg_codes: List of DG codes (e.g., ['GROW', 'CLIMA'])
            query_text: Lowercased query text for filtering large institutions

        Returns:
            List of EC personnel information dictionaries
        """
        personnel_data = []

        def _generate_eu_email(name: str, domain: str = 'ec.europa.eu') -> str:
            """Generate standard EU institution email from name.
            Domains: ec.europa.eu (Commission), consilium.europa.eu (Council/GSC),
            europarl.europa.eu (EP officials and MEPs)."""
            if not name or name.lower() in ('not shown', 'vacant', 'unknown', ''):
                return ''
            # Strip honorifics (Mr, Ms, Mrs)
            clean = name.strip()
            clean = re.sub(r'^(Mr|Ms|Mrs|Dr)\s+', '', clean)
            parts = clean.split()
            if len(parts) < 2:
                return ''
            # Use first and last name parts, normalise diacritics
            diacritics = {'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e',
                          'ö': 'o', 'ó': 'o', 'ô': 'o', 'ő': 'o',
                          'ü': 'u', 'ú': 'u', 'û': 'u', 'ű': 'u',
                          'ñ': 'n', 'ń': 'n', 'ņ': 'n',
                          'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a',
                          'í': 'i', 'î': 'i', 'ï': 'i',
                          'ç': 'c', 'č': 'c', 'ć': 'c',
                          'š': 's', 'ś': 's', 'ș': 's',
                          'ž': 'z', 'ź': 'z', 'ż': 'z',
                          'ř': 'r', 'ł': 'l', 'đ': 'd', 'ð': 'd',
                          'ț': 't', 'ý': 'y', 'ă': 'a', 'ī': 'i',
                          'ū': 'u', 'ē': 'e', 'ā': 'a', 'ļ': 'l',
                          'ķ': 'k', 'ģ': 'g'}
            def normalise(s):
                s = s.lower()
                for k, v in diacritics.items():
                    s = s.replace(k, v)
                return s
            first = normalise(parts[0])
            last = normalise(parts[-1])
            return f"{first}.{last}@{domain}"

        def _generate_ec_email(name: str) -> str:
            """Shortcut for Commission emails."""
            return _generate_eu_email(name, 'ec.europa.eu')

        # Non-Commission institution codes that use tree-structured JSONs
        NON_COMMISSION_CODES = {
            'EURCOU', 'GSC', 'COREPER', 'GOVREP', 'EP', 'EP_SG', 'EP_MEPS', 'EP_GROUP_SEC',
            # New PDF-parsed institution files
            'COMMISSION', 'COUNCIL_EU', 'EUROPEAN_COUNCIL', 'ECB', 'ECJ', 'ECA',
            'EEAS', 'COR', 'EESC', 'EIB', 'EIF', 'EDPS', 'OMBUDSMAN', 'AGENCIES',
        }

        for dg_code in dg_codes:
            try:
                # Get full organigramme (not just summary)
                org = self.knowledge_loader.get_dg_organigramme(dg_code)

                if not org:
                    logger.warning(f"No organigramme data found for DG {dg_code}")
                    continue

                # Handle non-Commission institutions (tree-structured JSONs)
                if dg_code.upper() in NON_COMMISSION_CODES:
                    personnel_data.append(
                        self._format_institution_organigramme(dg_code.upper(), org, query_text)
                    )
                    logger.debug(f"Fetched institution personnel for {dg_code}")
                    continue

                # Director-General (handle both old and new JSON formats, plus acting/secretary variants)
                leadership = org.get('leadership', {})
                dg_info = (
                    leadership.get('director_general')
                    or org.get('director_general')
                    or leadership.get('acting_director_general')
                    or org.get('secretary_general')
                    or {}
                )
                dg_name = dg_info.get('name') if isinstance(dg_info, dict) else (dg_info if isinstance(dg_info, str) else None)

                # Deputy DGs (handle plural list, singular dict, and leadership-nested variants)
                deputy_dgs = []
                raw_ddgs = (
                    leadership.get('deputy_director_generals', [])
                    or leadership.get('deputy_directors_general', [])
                    or org.get('deputy_directors_general', [])
                )
                # Handle singular deputy_director_general (dict) at top level
                if not raw_ddgs:
                    singular = leadership.get('deputy_director_general', org.get('deputy_director_general'))
                    if isinstance(singular, dict) and 'name' in singular:
                        raw_ddgs = [singular]
                    # Also check for deputy_director_general_2 (e.g., DG HR)
                    singular2 = org.get('deputy_director_general_2')
                    if isinstance(singular2, dict) and 'name' in singular2:
                        raw_ddgs = list(raw_ddgs) + [singular2]

                for ddg in raw_ddgs:
                    if isinstance(ddg, dict) and 'name' in ddg:
                        deputy_dgs.append({
                            'name': ddg['name'],
                            'responsibilities': ddg.get('responsibilities', ddg.get('responsible_for', '')),
                            'email': _generate_ec_email(ddg['name'])
                        })

                # Directorate directors and unit heads
                directorates = []
                for directorate in org.get('directorates', []):
                    dir_data = {
                        'code': directorate.get('code', ''),
                        'name': directorate.get('name', ''),
                        'director': directorate.get('director', ''),
                        'director_email': _generate_ec_email(directorate.get('director', '')),
                        'units': []
                    }

                    for unit in directorate.get('units', []):
                        head_name = unit.get('head', '')
                        if head_name and head_name not in ('Not shown', 'Vacant'):
                            dir_data['units'].append({
                                'code': unit.get('code', ''),
                                'name': unit.get('name', ''),
                                'head': head_name,
                                'head_email': _generate_ec_email(head_name)
                            })

                    directorates.append(dir_data)

                personnel_data.append({
                    'dg_code': dg_code.upper(),
                    'dg_name': org.get('dg_name', ''),
                    'commissioner': (
                    org['commissioner'].get('name', '') if isinstance(org.get('commissioner'), dict)
                    else org.get('commissioner', org.get('executive_vice_president', ''))
                ),
                    'director_general': dg_name,
                    'director_general_email': _generate_ec_email(dg_name) if dg_name else '',
                    'deputy_directors_general': deputy_dgs,
                    'directorates': directorates,
                    'num_directorates': len(org.get('directorates', [])),
                    'num_units': sum(len(d.get('units', [])) for d in org.get('directorates', [])),
                    'num_agencies': len(org.get('agencies', []))
                })

                logger.debug(f"Fetched EC personnel for DG {dg_code}")

            except Exception as e:
                logger.error(f"Failed to fetch EC personnel for DG {dg_code}: {str(e)}")

        return personnel_data

    def _format_institution_organigramme(
        self, inst_code: str, org: Dict[str, Any], query_text: str = ""
    ) -> Dict[str, Any]:
        """
        Format non-Commission institution organigrammes (EURCOU, GSC, COREPER,
        GOVREP, EP, EP_SG, EP_GROUP_SEC) into a structure compatible with the
        ec_personnel formatting pipeline.

        These JSONs use a tree structure with 'structure'/'units'/'persons' instead of
        the Commission's flat 'directorates'/'units' format.

        For large institutions (>200 persons), filters to units matching query keywords.
        """
        inst_name = org.get('institution_name', inst_code)

        # Determine email domain based on institution
        INSTITUTION_EMAIL_DOMAINS = {
            'GSC': 'consilium.europa.eu',
            'EURCOU': 'consilium.europa.eu',
            'COREPER': '',  # varies by country
            'GOVREP': '',   # varies by country
            'EP': 'europarl.europa.eu',
            'EP_SG': 'europarl.europa.eu',
            'EP_MEPS': 'europarl.europa.eu',
            'EP_GROUP_SEC': 'europarl.europa.eu',
            'COMMISSION': 'ec.europa.eu',
            'COUNCIL_EU': 'consilium.europa.eu',
            'EUROPEAN_COUNCIL': 'consilium.europa.eu',
            'ECB': 'ecb.europa.eu',
            'ECJ': 'curia.europa.eu',
            'ECA': 'eca.europa.eu',
            'EEAS': 'eeas.europa.eu',
            'COR': 'cor.europa.eu',
            'EESC': 'eesc.europa.eu',
            'EIB': 'eib.org',
            'EIF': 'eif.org',
            'EDPS': 'edps.europa.eu',
            'OMBUDSMAN': 'ombudsman.europa.eu',
            'AGENCIES': '',  # varies by agency
        }
        email_domain = INSTITUTION_EMAIL_DOMAINS.get(inst_code, '')

        def _make_email(name: str) -> str:
            if not email_domain or not name:
                return ''
            # Strip honorifics
            clean = re.sub(r'^(Mr|Ms|Mrs|Dr)\s+', '', name.strip())
            parts = clean.split()
            if len(parts) < 2:
                return ''
            diacritics = {'é': 'e', 'è': 'e', 'ë': 'e', 'ê': 'e',
                          'ö': 'o', 'ó': 'o', 'ô': 'o', 'ő': 'o',
                          'ü': 'u', 'ú': 'u', 'û': 'u', 'ű': 'u',
                          'ñ': 'n', 'ń': 'n', 'ņ': 'n',
                          'á': 'a', 'à': 'a', 'â': 'a', 'ä': 'a', 'ã': 'a',
                          'í': 'i', 'î': 'i', 'ï': 'i',
                          'ç': 'c', 'č': 'c', 'ć': 'c',
                          'š': 's', 'ś': 's', 'ș': 's',
                          'ž': 'z', 'ź': 'z', 'ż': 'z',
                          'ř': 'r', 'ł': 'l', 'đ': 'd',
                          'ț': 't', 'ý': 'y', 'ă': 'a', 'ī': 'i',
                          'ū': 'u', 'ē': 'e', 'ā': 'a', 'ļ': 'l',
                          'ķ': 'k', 'ģ': 'g'}
            def norm(s):
                s = s.lower()
                for k, v in diacritics.items():
                    s = s.replace(k, v)
                return s
            first = norm(parts[0])
            last = norm(parts[-1])
            return f"{first}.{last}@{email_domain}"

        def _flatten_tree(nodes, depth=0, max_depth=4):
            """Flatten tree nodes into directorate-like entries."""
            directorates = []
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                code = node.get('code', '')
                name = node.get('name', '')
                persons = node.get('persons', [])
                sub_units = node.get('units', [])

                # Top-level nodes become "directorates", sub-nodes become "units"
                director_name = persons[0]['name'] if persons else ''
                units = []
                for sub in sub_units:
                    sub_persons = sub.get('persons', [])
                    sub_head = sub_persons[0]['name'] if sub_persons else ''
                    if sub_head:
                        units.append({
                            'code': sub.get('code', ''),
                            'name': sub.get('name', ''),
                            'head': sub_head,
                            'head_email': _make_email(sub_head)
                        })
                    # Recurse one more level for deeper units
                    for subsub in sub.get('units', []):
                        ss_persons = subsub.get('persons', [])
                        ss_head = ss_persons[0]['name'] if ss_persons else ''
                        if ss_head:
                            units.append({
                                'code': subsub.get('code', ''),
                                'name': subsub.get('name', ''),
                                'head': ss_head,
                                'head_email': _make_email(ss_head)
                            })

                directorates.append({
                    'code': code,
                    'name': name,
                    'director': director_name,
                    'director_email': _make_email(director_name),
                    'units': units
                })
            return directorates

        # NEW FORMAT: PDF-parsed JSONs have "units" dict with persons lists
        if 'units' in org and isinstance(org.get('units'), dict):
            all_units = org['units']
            total_persons = sum(len(u.get('persons', [])) for u in all_units.values())

            # For large institutions (>200 persons), filter to query-relevant units
            # and person name matches to avoid context window overflow
            MAX_UNITS_TO_INJECT = 20
            if total_persons > 200 and query_text:
                # Use meaningful keywords (>=4 chars), skip stopwords
                stopwords = {
                    'what', 'who', 'where', 'when', 'which', 'that', 'this',
                    'with', 'from', 'have', 'does', 'about', 'their', 'there',
                    'been', 'the', 'and', 'for', 'are', 'but', 'not', 'you',
                    'all', 'can', 'her', 'was', 'one', 'our', 'out',
                    'european', 'parliament', 'commission', 'council',
                    # Structural words that match too many units
                    'committee', 'directorate', 'unit', 'head', 'chair',
                    'director', 'general', 'secretariat', 'service',
                    'delegation', 'office', 'group', 'member', 'works',
                    'contact', 'email', 'phone', 'person', 'people',
                    'affairs', 'policy', 'policies',
                }
                query_words = [
                    w for w in query_text.split()
                    if len(w) >= 4 and w not in stopwords
                ]
                if not query_words:
                    query_words = [w for w in query_text.split() if len(w) >= 3 and w not in stopwords]

                filtered_units = {}
                name_matches = {}
                for uname, udata in all_units.items():
                    uname_lower = uname.lower()
                    # Match unit name against query words (word boundary)
                    if any(re.search(r'\b' + re.escape(w) + r'\b', uname_lower) for w in query_words):
                        filtered_units[uname] = udata
                        continue
                    # Match person names within the unit (surname match)
                    for p in udata.get('persons', []):
                        pname = p.get('name', '').lower()
                        if any(w in pname for w in query_words):
                            if uname not in name_matches:
                                name_matches[uname] = udata
                            break
                filtered_units.update(name_matches)
                if filtered_units:
                    # Cap at MAX_UNITS_TO_INJECT even after filtering
                    all_units = dict(list(filtered_units.items())[:MAX_UNITS_TO_INJECT])
                    logger.info(
                        f"Filtered {inst_code} from {len(org['units'])} to "
                        f"{len(all_units)} units for query"
                    )
                else:
                    # No match found -- include just the top-level leadership units
                    all_units = dict(list(org['units'].items())[:10])
                    logger.info(
                        f"No unit match for {inst_code}, showing top 10 of "
                        f"{len(org['units'])} units"
                    )
            elif total_persons > 200:
                # No query text -- just show top leadership
                all_units = dict(list(org['units'].items())[:MAX_UNITS_TO_INJECT])

            directorates = []
            for unit_name, unit_data in all_units.items():
                persons_list = unit_data.get('persons', [])
                director_name = ''
                units = []
                for p in persons_list:
                    name = p.get('name', '')
                    title = p.get('title', '')
                    email = p.get('email', '')
                    phone = p.get('phone', '')
                    if not director_name:
                        director_name = name
                        continue
                    entry = {
                        'code': '',
                        'name': title or name,
                        'head': name,
                        'head_email': email or _make_email(name),
                    }
                    if phone:
                        entry['phone'] = phone
                    units.append(entry)

                directorates.append({
                    'code': '',
                    'name': unit_name,
                    'director': director_name,
                    'director_email': (
                        persons_list[0].get('email', '') if persons_list
                        else _make_email(director_name)
                    ),
                    'units': units
                })

            return {
                'dg_code': inst_code,
                'dg_name': org.get('institution', inst_name),
                'commissioner': '',
                'director_general': '',
                'director_general_email': '',
                'deputy_directors_general': [],
                'directorates': directorates,
                'num_directorates': len(directorates),
                'num_units': sum(len(d.get('units', [])) for d in directorates),
                'num_agencies': 0,
                'is_non_commission': True,
                'total_persons': org.get('total_persons', 0),
            }

        # OLD FORMAT: tree-structured JSONs (EURCOU, GSC, COREPER, etc.)
        structure = org.get('structure', org.get('countries', []))

        # For GSC/EP_SG, the secretary-general is the top person
        sg = org.get('secretary_general', org.get('president', {}))
        sg_name = sg.get('name', '') if isinstance(sg, dict) else ''

        directorates = _flatten_tree(structure)

        return {
            'dg_code': inst_code,
            'dg_name': inst_name,
            'commissioner': '',
            'director_general': sg_name,
            'director_general_email': _make_email(sg_name),
            'deputy_directors_general': [],
            'directorates': directorates,
            'num_directorates': len(directorates),
            'num_units': sum(len(d.get('units', [])) for d in directorates),
            'num_agencies': 0,
            'is_non_commission': True
        }

    async def _fetch_recent_rss(
        self,
        query: str,
        entities: ExtractedEntities,
        days: int
    ) -> List[Dict[str, Any]]:
        """Fetch recent RSS entries related to query"""
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Get all recent entries
            all_entries = await self.rss_manager.get_entries_by_date_range(
                start_date=start_date,
                end_date=end_date,
                limit=100
            )

            # Filter by relevance
            relevant_entries = []
            query_lower = query.lower()

            for entry in all_entries:
                title = entry.get('title', '').lower()
                summary = entry.get('summary', '').lower()

                # Check if query terms appear in entry
                if query_lower in title or query_lower in summary:
                    relevant_entries.append(entry)
                    continue

                # Check if entities appear in entry
                text = f"{title} {summary}"

                # Check CELEX numbers
                if any(celex in text for celex in entities.celex_numbers):
                    relevant_entries.append(entry)
                    continue

                # Check procedure references
                if any(proc in text for proc in entities.procedure_references):
                    relevant_entries.append(entry)
                    continue

                # Check MEP names
                if any(mep.lower() in text for mep in entities.mep_names):
                    relevant_entries.append(entry)
                    continue

            # Limit and format
            relevant_entries = relevant_entries[:10]  # Max 10 RSS entries

            formatted = [
                {
                    'title': entry.get('title', ''),
                    'summary': entry.get('summary', '')[:300],
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'source': entry.get('source', '')
                }
                for entry in relevant_entries
            ]

            logger.debug(f"Found {len(formatted)} relevant RSS entries")
            return formatted

        except Exception as e:
            logger.error(f"Failed to fetch recent RSS: {str(e)}")
            return []

    # Anaphors that signal a message leaning on the previous turn for its
    # topic, in Brubru's six languages. Matched at the START of the message
    # or as a bare object ("about it", "sobre això").
    _FOLLOWUP_MARKERS = (
        # EN
        "it", "this", "that", "they", "them", "these", "those", "its", "their",
        "the act", "the file", "the same", "there",
        # ES
        "eso", "esto", "esta", "este", "ese", "ella", "ello", "lo mismo", "ahí",
        # CA
        "això", "aquest", "aquesta", "aquell", "el mateix", "aquí",
        # FR
        "ce", "cet", "cette", "celui", "celle", "cela", "ça", "le même",
        # IT
        "questo", "questa", "quello", "quella", "cio", "ciò", "lo stesso",
        # NL
        "dit", "dat", "deze", "die", "hetzelfde", "ervan",
    )

    # Words capitalised by grammar rather than because they name something.
    _CAPS_NOISE = frozenset({
        "what", "when", "where", "which", "who", "whom", "how", "why",
        "and", "the", "is", "are", "do", "does", "did", "can", "could",
        "should", "would", "will", "answer", "explain", "tell", "show",
        "give", "list", "also", "but", "for", "about", "please",
        "quan", "quin", "quina", "que", "cual", "cuales", "quelle", "quel",
        "quali", "quale", "wat", "wanneer", "welke", "hoe", "come", "como",
        "si", "es", "el", "la", "le", "il", "de", "het",
    })

    @classmethod
    def _carries_own_topic(cls, user_message: str) -> bool:
        """True when a short question names its own subject.

        A bare acronym or a proper noun IS a topic: "What is CBAM?", "Explain
        REACH.", "What about Xylella fastidiosa?" and "Is L-cysteine authorised
        as feed?" are all short, all yield no extractable entity, and all are
        clean topic switches that must NOT inherit the previous subject.
        """
        # Acronym, excluding the ones that are just context ("EU", "AI").
        if re.search(r"\b(?!EU\b|UE\b|AI\b)[A-Z]{3,10}\b", user_message):
            return True
        # Capitalised word that is not the sentence opener and not grammar.
        for idx, tok in enumerate(re.findall(r"[A-Za-zÀ-ÿ][\w'’-]*", user_message)):
            if idx == 0:
                continue  # the first word is capitalised by convention
            if tok[:1].isupper() and len(tok) >= 4 and tok.lower() not in cls._CAPS_NOISE:
                return True
        return False

    def _augment_query_with_history(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]],
        entities: "ExtractedEntities",
    ) -> str:
        """Prepend the previous turn's topic to a context-bare follow-up.

        Returns `user_message` unchanged for anything that carries its own
        topic. Augmenting unconditionally would be worse than not augmenting
        at all: a genuine change of subject would keep dragging the old topic
        into retrieval and bury the new one.

        A message is treated as context-bare when the entity extractor found
        nothing to anchor on AND the message is either short or opens with an
        anaphor.
        """
        if not conversation_history or not user_message:
            return user_message

        # mep_names is deliberately NOT an anchor. The extractor routinely
        # returns sentence fragments as people ("Who is the"), and trusting it
        # here suppressed augmentation on exactly the follow-ups that need it:
        # "Who is the rapporteur?" was left un-augmented for that reason.
        has_anchor = any((
            getattr(entities, "celex_numbers", None),
            getattr(entities, "procedure_references", None),
            getattr(entities, "committee_codes", None),
            getattr(entities, "policy_areas", None),
            getattr(entities, "funding_programmes", None),
        ))
        if has_anchor:
            return user_message

        # Opening with a conjunction is an explicit continuation signal, and it
        # outranks the topic heuristics below: "And for SMEs?" is the previous
        # act applied to SMEs, not a new subject, even though "SMEs" would
        # otherwise read as a proper noun.
        opens_with_continuation = any(
            user_message.strip().lower().startswith(c)
            for c in ("and ", "also ", "but ", "et ", "y ", "i ", "e ",
                      "en ", "und ", "ook ", "a mes ", "ademas ")
        )
        if not opens_with_continuation and self._carries_own_topic(user_message):
            return user_message

        # Accent-fold before matching: users type "aixo" and "esto" as often
        # as "això" and "éso", and an unfolded list would miss them.
        stripped = "".join(
            c for c in unicodedata.normalize("NFD", user_message.strip().lower())
            if unicodedata.category(c) != "Mn"
        )
        words = stripped.split()
        padded = f" {stripped} "
        has_anaphor = any(
            f" {unicodedata.normalize('NFD', m).encode('ascii', 'ignore').decode()} " in padded
            for m in self._FOLLOWUP_MARKERS
        )
        # Augment only for a message that either leans on a previous turn
        # (anaphor) or is too short to carry a topic at all. A 13-word
        # question about a brand-new subject must NOT drag the old topic in:
        # "What are the rules on geographical indications for spirit drinks"
        # has no anchor entity either, and length alone would have augmented it.
        if not (has_anaphor or len(words) <= 6):
            return user_message

        # Take the most recent USER turns; assistant text is long and would
        # swamp the query with its own vocabulary.
        prior = [
            (m.get("content") or "").strip()
            for m in conversation_history
            if (m.get("role") == "user") and (m.get("content") or "").strip()
        ][-2:]
        if not prior:
            return user_message

        augmented = " ".join(prior + [user_message])
        logger.info(
            "[RETRIEVAL] context-bare follow-up augmented with %d prior turn(s): %r -> %r",
            len(prior), user_message[:60], augmented[:120],
        )
        return augmented

    async def _query_internal_knowledge(
        self,
        query: str,
        drafting_intent: Optional[DraftingIntent] = None
    ) -> List[Dict[str, Any]]:
        """
        Query internal knowledge base (templates, guides).

        When drafting intent is detected, templates are prioritised over guides
        and the best-matching templates for the document type are injected first.

        Args:
            query: User query
            drafting_intent: Detected drafting intent (if any)

        Returns:
            List of relevant internal knowledge documents
        """
        knowledge_items = []

        try:
            query_lower = query.lower()

            # If drafting intent detected, prioritise templates FIRST
            if drafting_intent and drafting_intent.is_drafting_query:
                logger.info(f"[DRAFTING] Boosting templates for document type: {drafting_intent.document_type}")

                # 1. Inject best-matching templates for detected document type
                preferred_templates = DOC_TYPE_TO_TEMPLATE.get(drafting_intent.document_type, [])
                for template_name in preferred_templates:
                    template_content = self.knowledge_loader.get_template(template_name)
                    if template_content:
                        title_match = re.search(r'^#\s+(.+)$', template_content, re.MULTILINE)
                        title = title_match.group(1) if title_match else template_name.replace('_', ' ').title()
                        knowledge_items.append({
                            'type': 'template',
                            'name': template_name,
                            'title': title,
                            'content': template_content[:2000],
                            'full_length': len(template_content),
                            'drafting_match': True  # Signal this was matched via intent
                        })

                # 2. Also search templates by topic keywords
                if drafting_intent.topic:
                    topic_templates = self.knowledge_loader.search_templates(drafting_intent.topic)
                    added_names = {item['name'] for item in knowledge_items}
                    for template_name in topic_templates:
                        if template_name not in added_names:
                            template_content = self.knowledge_loader.get_template(template_name)
                            if template_content:
                                title_match = re.search(r'^#\s+(.+)$', template_content, re.MULTILINE)
                                title = title_match.group(1) if title_match else template_name.replace('_', ' ').title()
                                knowledge_items.append({
                                    'type': 'template',
                                    'name': template_name,
                                    'title': title,
                                    'content': template_content[:2000],
                                    'full_length': len(template_content)
                                })

                # 3. Then add guides for background context (fewer slots)
                matching_guides = self.knowledge_loader.search_guides(query)
                remaining_slots = max(1, self.max_internal_knowledge_results - len(knowledge_items))
                if matching_guides:
                    for guide in matching_guides[:remaining_slots]:
                        guide_content = self.knowledge_loader.get_guide(guide['id'])
                        if guide_content:
                            item = {
                                'type': 'guide',
                                'name': guide['id'],
                                'title': guide['title'],
                                'content': guide_content[:8000],
                                'full_length': len(guide_content),
                                'snippet': guide.get('snippet', '')
                            }
                            staleness = self.knowledge_loader.get_guide_staleness(guide['id'])
                            if staleness:
                                item['staleness_caveat'] = staleness
                            knowledge_items.append(item)

                logger.info(f"[DRAFTING] Injected {len(knowledge_items)} items "
                            f"({sum(1 for i in knowledge_items if i['type'] == 'template')} templates, "
                            f"{sum(1 for i in knowledge_items if i['type'] == 'guide')} guides)")

            else:
                # Standard path: guides first, then templates
                # Two-step pipeline inspired by Claude Code's memory recall:
                # 1. Get candidates with quick_facts for ranking (low token cost)
                # 2. Fetch full content only for top-ranked guides
                max_guides = self.max_internal_knowledge_results
                matching_guides = self.knowledge_loader.search_guides(query, output_mode='quick_facts')

                if matching_guides:
                    # If more candidates than slots, rank by query relevance
                    if len(matching_guides) > max_guides:
                        ranked = self._rank_guides_by_relevance(query, matching_guides)
                        selected = ranked[:max_guides]
                        logger.info(
                            f"[GUIDE-RANK] {len(matching_guides)} candidates -> "
                            f"top {len(selected)}: {[g['id'] for g in selected]}"
                        )
                    else:
                        selected = matching_guides

                    for guide in selected:
                        guide_content = self.knowledge_loader.get_guide(guide['id'])
                        if guide_content:
                            item = {
                                'type': 'guide',
                                'name': guide['id'],
                                'title': guide['title'],
                                'content': guide_content[:8000],
                                'full_length': len(guide_content),
                                'snippet': guide.get('snippet', ''),
                                'trigger_matched': guide.get('trigger_matched', False)
                            }
                            # Staleness caveat for guides older than 30 days
                            staleness = self.knowledge_loader.get_guide_staleness(guide['id'])
                            if staleness:
                                item['staleness_caveat'] = staleness
                            knowledge_items.append(item)

                    logger.debug(f"Found {len(matching_guides)} guide matches for query: {query}")

                # Also search templates (document templates)
                matching_templates = self.knowledge_loader.search_templates(query)

                if matching_templates:
                    remaining_slots = self.max_internal_knowledge_results - len(knowledge_items)
                    for template_name in matching_templates[:remaining_slots]:
                        template_content = self.knowledge_loader.get_template(template_name)
                        if template_content:
                            title_match = re.search(r'^#\s+(.+)$', template_content, re.MULTILINE)
                            title = title_match.group(1) if title_match else template_name.replace('_', ' ').title()

                            knowledge_items.append({
                                'type': 'template',
                                'name': template_name,
                                'title': title,
                                'content': template_content[:2000],
                                'full_length': len(template_content)
                            })

                    logger.debug(f"Found {len(matching_templates)} template matches for query: {query}")

            if not knowledge_items:
                logger.debug(f"No internal knowledge matches found for query: {query}")

        except Exception as e:
            logger.error(f"Failed to query internal knowledge: {str(e)}")

        return knowledge_items

    def _rank_guides_by_relevance(
        self,
        query: str,
        guides: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rank candidate guides by relevance to the query using QUICK FACTS.

        Scoring (no API call, pure keyword density):
        - Query word hits in quick_facts (weighted 3x)
        - Query word hits in title (weighted 2x)
        - Trigger-matched guides get a bonus
        - Longer quick_facts = more specific guide = small bonus

        Inspired by Claude Code's memory relevance selector pattern.
        """
        query_lower = query.lower()
        # Extract meaningful words (>3 chars, no stopwords)
        stopwords = {
            'what', 'when', 'where', 'which', 'that', 'this', 'these', 'those',
            'have', 'does', 'will', 'would', 'could', 'should', 'about', 'with',
            'from', 'they', 'their', 'there', 'been', 'being', 'some', 'more',
            'also', 'than', 'then', 'very', 'just', 'like', 'tell', 'explain',
        }
        query_words = [w for w in query_lower.split() if len(w) > 3 and w not in stopwords]

        scored = []
        for guide in guides:
            score = 0.0
            qf = (guide.get('quick_facts') or '').lower()
            title = (guide.get('title') or '').lower()

            # Query word hits in quick_facts (3x weight)
            for word in query_words:
                if word in qf:
                    score += 3.0
                if word in title:
                    score += 2.0

            # Full query phrase match bonus
            if query_lower in qf:
                score += 5.0
            if query_lower in title:
                score += 4.0

            # Trigger-matched guides get a large bonus.
            #
            # A keyword trigger is a CURATED, hand-written mapping from a phrase
            # to the one guide that answers it. Incidental word overlap is not
            # remotely as good a signal, yet at +2.0 a trigger lost to any guide
            # with two word hits in its QUICK FACTS (3.0 each). Measured 6 Aug
            # 2026: "What is the CSRD?" fired the CSRD trigger and still ranked
            # eu_taxonomy_sustainable_finance first, so the act's own guide was
            # not what the model read.
            if guide.get('trigger_matched'):
                score += 8.0

            # Specificity bonus: longer quick_facts = more detailed guide
            if len(qf) > 200:
                score += 0.5

            scored.append((score, guide))

        # Sort by score descending, stable sort preserves trigger-first order on ties
        scored.sort(key=lambda x: x[0], reverse=True)
        return [g for _, g in scored]

    # =========================================================================
    # CELLAR On-Demand Context (EuroVoc fallback)
    # =========================================================================

    # Topic keywords for CELLAR EuroVoc search
    # Maps common query terms to EuroVoc-compatible keywords
    CELLAR_TOPIC_KEYWORDS = {
        'fisheries': ['fisheries'], 'fishing': ['fisheries'], 'aquaculture': ['aquaculture'],
        'agriculture': ['agriculture'], 'farming': ['agriculture'], 'cap': ['common agricultural policy'],
        'humanitarian': ['humanitarian aid'], 'civil protection': ['civil protection'],
        'trade': ['trade policy'], 'trade agreement': ['trade agreement'],
        'consumer': ['consumer protection'], 'product safety': ['product safety'],
        'culture': ['culture'], 'creative': ['cultural policy'],
        'development': ['development cooperation'], 'development aid': ['development aid'],
        'customs': ['customs'], 'customs union': ['customs union'],
        'human rights': ['human rights'], 'fundamental rights': ['fundamental rights'],
        'education': ['education'], 'erasmus': ['student mobility'],
        'enlargement': ['enlargement'], 'accession': ['accession'],
        'sme': ['small and medium-sized enterprises'], 'enterprise': ['enterprise policy'],
        'environment': ['environment'], 'biodiversity': ['biodiversity'],
        'climate': ['climate change'], 'green deal': ['climate change'],
        'taxation': ['taxation'], 'vat': ['value added tax'], 'tax': ['taxation'],
        'fraud': ['fraud'], 'anti-fraud': ['anti-fraud'], 'corruption': ['corruption'],
        'justice': ['justice'], 'security': ['internal security'],
        'migration': ['migration'], 'asylum': ['asylum'],
        'internal market': ['internal market'], 'single market': ['internal market'],
        'foreign policy': ['foreign policy'], 'defence': ['defence'],
        'external relations': ['external relations'],
        'health': ['public health'], 'pharmaceutical': ['pharmaceutical product'],
        'digital': ['digital economy'], 'cybersecurity': ['cybersecurity'],
        'transport': ['transport'], 'maritime': ['maritime transport'],
        'energy': ['energy policy'], 'renewable': ['renewable energy'],
    }

    def _extract_topic_keywords(self, query_lower: str) -> List[str]:
        """Extract EuroVoc topic keywords from a user query.

        Args:
            query_lower: Lowercased user query

        Returns:
            List of EuroVoc-compatible keywords (max 3)
        """
        matched = []
        # Check multi-word terms first (longer = more specific)
        sorted_terms = sorted(self.CELLAR_TOPIC_KEYWORDS.keys(), key=len, reverse=True)
        for term in sorted_terms:
            if term in query_lower:
                for kw in self.CELLAR_TOPIC_KEYWORDS[term]:
                    if kw not in matched:
                        matched.append(kw)
                if len(matched) >= 3:
                    break
        return matched[:3]

    async def _fetch_cellar_legislation_context(
        self,
        topic_keywords: List[str],
        date_from: str = "2020-01-01",
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Fetch relevant legislation from CELLAR by EuroVoc topics.

        This is a fallback method called only when no knowledge guides
        matched the user query. Results are cached by the EURLexClient.

        Args:
            topic_keywords: EuroVoc keywords extracted from query
            date_from: Minimum document date
            limit: Max results per keyword

        Returns:
            List of legislation dicts with celex, title, date, source
        """
        if not self.eurlex_client or not topic_keywords:
            return []

        results = await self.eurlex_client.search_by_eurovoc_keyword(
            keywords=topic_keywords,
            date_from=date_from,
            limit=limit
        )

        return results

    async def _fetch_legislative_train_files(
        self,
        query: str,
        entities: ExtractedEntities
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant legislative files from all sources.

        Sources:
        - Legislative Train Schedule (EC priorities)
        - OEIL (Legislative Observatory) - direct procedure imports
        - EUR-Lex RSS feeds - legislation and proposals

        Looks for:
        - Mentions of EC priorities (1-7)
        - Policy area matches
        - Blocked files (if query mentions "blocked" or "stuck")
        - Recent/new legislation (if query mentions "new", "recent", "latest")
        - Specific train/carriage references
        - CELEX numbers or procedure references

        Args:
            query: User query
            entities: Extracted entities

        Returns:
            List of relevant legislative files with status and source
        """
        from datetime import datetime, timedelta
        from models.legislative_train import CarriageSourceEnum

        try:
            db = SessionLocal()
            train_files = []
            query_lower = query.lower()

            # Check if user is asking about recent/new legislation
            is_recent_query = any(term in query_lower for term in [
                'new', 'recent', 'latest', 'last week', 'today', 'yesterday',
                'just added', 'newly', 'fresh', 'update', 'sync'
            ])

            # Check if asking about specific sources
            is_oeil_query = 'oeil' in query_lower or 'legislative observatory' in query_lower
            is_eurlex_query = 'eur-lex' in query_lower or 'eurlex' in query_lower or 'celex' in query_lower

            results = []

            if is_recent_query:
                # Fetch recently added files (last 7 days)
                seven_days_ago = datetime.utcnow() - timedelta(days=7)
                recent_query = db.query(LegislativeCarriage, LegislativeTrain).join(
                    LegislativeTrain,
                    LegislativeCarriage.train_id == LegislativeTrain.id,
                    isouter=True
                ).filter(
                    LegislativeCarriage.first_seen >= seven_days_ago
                ).order_by(
                    LegislativeCarriage.first_seen.desc()
                ).limit(10)
                results = recent_query.all()

            elif is_oeil_query:
                # Fetch OEIL-sourced files
                oeil_query = db.query(LegislativeCarriage, LegislativeTrain).join(
                    LegislativeTrain,
                    LegislativeCarriage.train_id == LegislativeTrain.id,
                    isouter=True
                ).filter(
                    LegislativeCarriage.source == CarriageSourceEnum.OEIL_DIRECT
                ).order_by(
                    LegislativeCarriage.last_updated.desc()
                ).limit(10)
                results = oeil_query.all()

            elif is_eurlex_query:
                # Fetch EUR-Lex sourced files
                eurlex_query = db.query(LegislativeCarriage, LegislativeTrain).join(
                    LegislativeTrain,
                    LegislativeCarriage.train_id == LegislativeTrain.id,
                    isouter=True
                ).filter(
                    LegislativeCarriage.source == CarriageSourceEnum.EURLEX
                ).order_by(
                    LegislativeCarriage.last_updated.desc()
                ).limit(10)
                results = eurlex_query.all()

            else:
                from sqlalchemy import or_

                match_filters = []

                # 1. Check for procedure references from entity extraction
                if entities.procedure_references:
                    for proc_ref in entities.procedure_references:
                        match_filters.append(
                            LegislativeCarriage.oeil_procedure_ref.ilike(f"%{proc_ref}%")
                        )

                # 2. Check for CELEX numbers from entity extraction
                if entities.celex_numbers:
                    for celex in entities.celex_numbers:
                        match_filters.append(
                            LegislativeCarriage.celex_numbers.any(celex)
                        )

                # 3. Keyword-tokenised title + description search
                stopwords = {
                    'tell', 'about', 'what', 'which', 'where', 'when', 'does',
                    'have', 'this', 'that', 'with', 'from', 'they', 'been',
                    'were', 'will', 'would', 'could', 'should', 'there',
                    'their', 'some', 'more', 'than', 'very', 'just', 'also',
                    'know', 'like', 'want', 'need', 'give', 'information',
                    'status', 'current', 'progress', 'update', 'explain',
                    'look', 'show', 'find', 'search', 'list',
                    'main', 'issues', 'within', 'proposal', 'regulation',
                    'directive', 'please', 'could', 'think', 'opinion',
                    'effects', 'impact', 'implications', 'details', 'overview',
                    'addressing', 'regarding', 'concerning', 'related',
                    'negative', 'positive', 'specific', 'general', 'brief',
                    'important', 'major', 'different', 'various', 'other',
                    'union', 'european', 'market', 'global',
                }
                words = [w for w in query_lower.split() if len(w) > 3 and w not in stopwords]
                if words:
                    for word in words[:8]:
                        match_filters.append(
                            LegislativeCarriage.title.ilike(f"%{word}%")
                        )
                        match_filters.append(
                            LegislativeCarriage.description.ilike(f"%{word}%")
                        )

                if match_filters:
                    carriages_query = db.query(LegislativeCarriage, LegislativeTrain).join(
                        LegislativeTrain,
                        LegislativeCarriage.train_id == LegislativeTrain.id,
                        isouter=True
                    ).filter(
                        or_(*match_filters)
                    ).order_by(
                        LegislativeCarriage.last_updated.desc()
                    ).limit(10)
                    results = carriages_query.all()
                else:
                    results = []

            # Format results
            for carriage, train in results:
                # Determine source label
                source_label = 'Legislative Train'
                if carriage.source:
                    source_map = {
                        'legislative_train': 'Legislative Train',
                        'oeil_direct': 'OEIL (Legislative Observatory)',
                        'eurlex': 'EUR-Lex',
                        'ep_opendata': 'EP Open Data'
                    }
                    source_label = source_map.get(carriage.source.value, carriage.source.value)

                train_files.append({
                    'train_name': train.name if train else source_label,
                    'train_priority': train.priority_number if train else None,
                    'file_title': carriage.title,
                    'current_status': carriage.current_status.value if hasattr(carriage.current_status, 'value') else str(carriage.current_status),
                    'days_in_current_status': carriage.days_in_current_status,
                    'is_blocked': carriage.is_blocked,
                    'committees': carriage.committees or [],
                    'oeil_ref': carriage.oeil_procedure_ref,
                    'celex_numbers': carriage.celex_numbers or [],
                    'source': source_label,
                    'first_seen': carriage.first_seen.isoformat() if carriage.first_seen else None,
                    'description': carriage.description[:300] if carriage.description else None,
                    # EP Legislative Train editorial "state of play" narrative —
                    # high-value grounding OEIL lacks (purpose, politics, funding,
                    # latest developments). Capped to protect the prompt budget.
                    'legislative_train_summary': (
                        carriage.legislative_train_summary[:1800]
                        if getattr(carriage, 'legislative_train_summary', None) else None
                    ),
                })

            # On-demand OEIL lookup: if entity extractor found procedure refs
            # not matched in DB results, fetch from OEIL and persist
            if entities.procedure_references:
                found_refs = {f.get('oeil_ref') for f in train_files}
                missing_refs = [
                    ref for ref in entities.procedure_references
                    if ref not in found_refs
                ]

                if missing_refs:
                    logger.info(
                        f"[OEIL-ONDEMAND] {len(missing_refs)} procedure ref(s) not in DB, "
                        f"fetching from OEIL: {missing_refs}"
                    )
                    try:
                        from services.scrapers.oeil_scraper import OEILScraper

                        scraper = OEILScraper(use_api=True)
                        for ref in missing_refs[:3]:  # Limit to 3 to avoid slow responses
                            try:
                                proc_data = await scraper.get_procedure(ref)
                                if proc_data and 'error' not in proc_data:
                                    # Persist to DB as OEIL-direct carriage
                                    from models.legislative_train import CarriageSourceEnum, CarriageStatusEnum
                                    from datetime import datetime

                                    title = proc_data.get('title', ref)
                                    existing = db.query(LegislativeCarriage).filter(
                                        LegislativeCarriage.oeil_procedure_ref == ref
                                    ).first()

                                    if not existing:
                                        new_carriage = LegislativeCarriage(
                                            title=title[:500] if title else ref,
                                            description=proc_data.get('subject', '')[:2000],
                                            oeil_procedure_ref=ref,
                                            source=CarriageSourceEnum.OEIL_DIRECT,
                                            current_status=CarriageStatusEnum.ONGOING,
                                            committees=proc_data.get('committees', []),
                                            lead_committee=proc_data.get('committee_responsible'),
                                            oeil_procedure_data=proc_data,
                                            first_seen=datetime.utcnow(),
                                            last_updated=datetime.utcnow(),
                                        )
                                        db.add(new_carriage)
                                        db.commit()
                                        logger.info(f"[OEIL-ONDEMAND] Persisted: {ref} - {title[:60]}")

                                        train_files.append({
                                            'train_name': 'OEIL (Legislative Observatory)',
                                            'train_priority': None,
                                            'file_title': title,
                                            'current_status': 'ongoing',
                                            'days_in_current_status': None,
                                            'is_blocked': False,
                                            'committees': proc_data.get('committees', []),
                                            'oeil_ref': ref,
                                            'celex_numbers': [],
                                            'source': 'OEIL (on-demand)',
                                            'first_seen': datetime.utcnow().isoformat(),
                                            'description': proc_data.get('subject', '')[:300],
                                        })
                                    else:
                                        logger.debug(f"[OEIL-ONDEMAND] Already exists: {ref}")

                            except Exception as e:
                                logger.warning(f"[OEIL-ONDEMAND] Failed to fetch {ref}: {e}")

                        try:
                            await scraper.close()
                        except Exception:
                            pass

                    except ImportError:
                        logger.warning("[OEIL-ONDEMAND] OEILScraper not available")

            # OEIL topic search fallback: when no procedure ref was extracted
            # and DB keyword search returned no confident results, use Tavily
            # scoped to OEIL to find the specific procedure by topic.
            # This catches queries like "timeline of the INI on trade and
            # economic security" where the user describes a procedure by topic.
            # "No confident results" means: either no results at all, OR the
            # OR-keyword results don't contain any file whose title matches
            # at least 2 of the query's content words (i.e., all noise).
            has_confident_match = False
            if train_files:
                content_words = [
                    w for w in query_lower.split()
                    if len(w) > 3 and w not in {
                        'what', 'which', 'where', 'when', 'does', 'have',
                        'this', 'that', 'with', 'from', 'they', 'been',
                        'were', 'will', 'would', 'could', 'should', 'there',
                        'their', 'some', 'more', 'than', 'very', 'just',
                        'also', 'timeline', 'status', 'role',
                    }
                ]
                for f in train_files:
                    title_lower = (f.get('file_title') or '').lower()
                    matches = sum(1 for w in content_words if w in title_lower)
                    if matches >= 2:
                        has_confident_match = True
                        break

            if not entities.procedure_references and not has_confident_match:
                procedure_topic_phrases = [
                    'timeline', 'status', 'rapporteur', 'shadow', 'deadline',
                    'vote', 'adopted', 'tabled', 'reading', 'trilogue',
                    'committee report', 'amendment deadline', 'ini ',
                    ' ini', 'own-initiative', 'procedure',
                ]
                has_procedure_topic_intent = any(
                    p in query_lower for p in procedure_topic_phrases
                )

                if has_procedure_topic_intent and self.tavily_client:
                    try:
                        logger.info(
                            f"[OEIL-TOPIC] No procedure ref and no DB matches, "
                            f"searching OEIL by topic for: {query[:80]}"
                        )
                        oeil_response = await self.tavily_client.search(
                            query=query,
                            search_depth="basic",
                            max_results=3,
                            include_domains=[
                                "oeil.secure.europarl.europa.eu",
                                "europarl.europa.eu",
                            ],
                        )

                        for result in oeil_response.results:
                            # Extract procedure ref from OEIL URL if present
                            import re as _re
                            proc_match = _re.search(
                                r'reference=(\d{4}/\d{4}\([A-Z]+\))',
                                result.url or ''
                            )
                            found_ref = proc_match.group(1) if proc_match else None

                            train_files.append({
                                'train_name': 'OEIL (topic search)',
                                'train_priority': None,
                                'file_title': result.title or '',
                                'current_status': 'unknown',
                                'days_in_current_status': None,
                                'is_blocked': False,
                                'committees': [],
                                'oeil_ref': found_ref,
                                'celex_numbers': [],
                                'source': 'OEIL (topic search)',
                                'first_seen': None,
                                'description': (result.content or '')[:400],
                                'source_url': result.url,
                            })

                        if train_files:
                            logger.info(
                                f"[OEIL-TOPIC] Found {len(train_files)} results "
                                f"via topic search"
                            )

                    except Exception as e:
                        logger.warning(
                            f"[OEIL-TOPIC] Topic search failed: {e}"
                        )

            # Attach real EP vote tallies (committee + plenary roll-call) from
            # ep_roll_call_votes, keyed on OEIL ref, so Chat can ground "how did
            # X vote / did plenary follow the committee" on actual numbers — not
            # just the date-only "vote held" markers. Authoritative doceo source.
            try:
                refs = {f.get('oeil_ref') for f in train_files if f.get('oeil_ref')}
                if refs:
                    from models.ep_vote import EpVote
                    vmap: Dict[str, Dict[str, Any]] = {}
                    for v in db.query(EpVote).filter(EpVote.procedure_ref.in_(refs)).all():
                        vmap.setdefault(v.procedure_ref, {})[v.level] = v
                    for f in train_files:
                        rec = vmap.get(f.get('oeil_ref'))
                        if not rec:
                            continue
                        c, p = rec.get('committee'), rec.get('plenary')
                        parts = []
                        if c:
                            parts.append(
                                f"committee {c.votes_for}/{c.votes_against}/{c.votes_abstention} {c.result}"
                                + (f" [{c.committee_code}]" if c.committee_code else ""))
                        if p:
                            parts.append(f"plenary {p.votes_for}/{p.votes_against}/{p.votes_abstention} {p.result}")
                        if c and p:
                            parts.append("plenary confirmed committee" if c.result == p.result
                                         else "plenary diverged from committee")
                        if parts:
                            f['vote_summary'] = "; ".join(parts)
            except Exception as e:
                logger.warning(f"[VOTES] vote-summary enrichment failed: {e}")

            db.close()

            logger.debug(f"Found {len(train_files)} legislative files for query")
            return train_files

        except Exception as e:
            logger.error(f"Failed to fetch legislative files: {str(e)}")
            return []

    # =========================================================================
    # Procedural Action Enrichment (Added February 2026)
    # =========================================================================

    def _extract_actions_from_cached_data(
        self,
        oeil_data: Dict[str, Any],
        carriage
    ) -> Dict[str, Any]:
        """
        Parse cached oeil_procedure_data to determine available procedural actions.

        Handles two data shapes:
        1. Full OEILProcedure dump (from get_procedure_full): has key_players,
           key_events, documentation, forecasts
        2. Partial enrichment (documentation_gateway only): has documentation_gateway list
        """
        actions = {
            'has_draft_report': False,
            'draft_report_committee': None,
            'draft_report_date': None,
            'has_amendments': False,
            'amendment_count_hint': 0,
            'has_committee_report': False,
            'has_committee_opinions': [],
            'has_committee_vote': False,
            'committee_vote_date': None,
            'has_plenary_vote': False,
            'plenary_vote_date': None,
            'has_plenary_debate': False,
            'rapporteur_name': None,
            'rapporteur_group': None,
            'rapporteur_committee': carriage.lead_committee,
            'shadow_rapporteurs': [],
            'lead_committee': carriage.lead_committee,
            'has_celex': bool(carriage.celex_numbers),
            'upcoming_events': [],
            'key_documents': [],  # Document Gateway references with URLs
        }

        if not oeil_data:
            return actions

        # --- Documentation Gateway ---
        doc_gateway = oeil_data.get('documentation_gateway', [])

        for doc in doc_gateway:
            code = doc.get('doc_type_code', '')
            if code == 'PR':
                actions['has_draft_report'] = True
                actions['draft_report_committee'] = doc.get('committee')
                actions['draft_report_date'] = doc.get('date')
            elif code == 'AM':
                actions['has_amendments'] = True
                actions['amendment_count_hint'] += 1
            elif code == 'RD':
                actions['has_committee_report'] = True
            elif code == 'AD':
                committee = doc.get('committee')
                if committee and committee not in actions['has_committee_opinions']:
                    actions['has_committee_opinions'].append(committee)

        # --- Extract key document references with URLs ---
        # These are injected into the AI context so it can present clickable
        # links to EP texts adopted, committee reports, amendments, and opinions.
        for doc in doc_gateway:
            ref = doc.get('a_reference') or doc.get('pe_reference') or doc.get('reference', '')
            url = doc.get('doceo_url') or doc.get('url', '')
            code = doc.get('doc_type_code', '')
            doc_type_text = doc.get('doc_type_text', '')
            date = doc.get('date', '')
            committee = doc.get('committee', '')

            if ref and url:
                actions['key_documents'].append({
                    'reference': ref,
                    'url': url,
                    'type': code,
                    'type_text': doc_type_text,
                    'date': date,
                    'committee': committee,
                })

        # Cap at 15 documents to avoid bloating context
        actions['key_documents'] = actions['key_documents'][:15]

        # --- Key Players (from full OEIL dump) ---
        key_players = oeil_data.get('key_players', {})
        if isinstance(key_players, dict):
            responsible = key_players.get('committee_responsible', {})
            if isinstance(responsible, dict):
                rapporteur = responsible.get('rapporteur', {})
                if isinstance(rapporteur, dict) and rapporteur.get('name'):
                    actions['rapporteur_name'] = rapporteur['name']
                    actions['rapporteur_group'] = rapporteur.get('political_group')
                    actions['rapporteur_committee'] = responsible.get('code') or carriage.lead_committee

                shadows = responsible.get('shadow_rapporteurs', [])
                if isinstance(shadows, list):
                    actions['shadow_rapporteurs'] = [
                        {'name': s.get('name'), 'group': s.get('political_group')}
                        for s in shadows if isinstance(s, dict) and s.get('name')
                    ]

        # --- Key Events (votes, debates) ---
        key_events = oeil_data.get('key_events', {})
        events = key_events.get('events', []) if isinstance(key_events, dict) else []

        for event in events:
            if not isinstance(event, dict):
                continue
            event_type = (event.get('event_type') or event.get('type') or '').lower()
            event_date = event.get('date')

            if 'vote in committee' in event_type:
                actions['has_committee_vote'] = True
                actions['committee_vote_date'] = event_date
            elif 'decision by parliament' in event_type or 'vote in parliament' in event_type:
                actions['has_plenary_vote'] = True
                actions['plenary_vote_date'] = event_date
            elif 'debate in plenary' in event_type:
                actions['has_plenary_debate'] = True

        # --- Forecasts (upcoming events) ---
        forecasts = oeil_data.get('forecasts', {})
        forecast_list = forecasts.get('forecasts', []) if isinstance(forecasts, dict) else []

        for forecast in forecast_list[:3]:
            if isinstance(forecast, dict):
                actions['upcoming_events'].append({
                    'event_type': forecast.get('event_type') or forecast.get('type', ''),
                    'date': str(forecast.get('forecast_date') or forecast.get('date', '')),
                })

        return actions

    async def _enrich_train_files_with_actions(
        self,
        train_files: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich matched legislative files with available procedural actions.

        For each file with an OEIL procedure reference, determine what
        concrete actions/data exist (draft reports, amendments, votes,
        rapporteur info) so the AI can offer grounded follow-up questions.

        Uses cached oeil_procedure_data when available (< 7 days old).
        Falls back to OEILClient.get_documentation_gateway() for fresh data.
        """
        from core.database import SessionLocal
        from models.legislative_train import LegislativeCarriage
        from datetime import datetime, timezone, timedelta

        # Only enrich files that have OEIL refs, limit to 3
        files_to_enrich = [
            (i, f) for i, f in enumerate(train_files)
            if f.get('oeil_ref')
        ][:3]

        if not files_to_enrich:
            return train_files

        db = SessionLocal()
        try:
            # Collect uncached refs that need OEIL fetch
            uncached_tasks = []
            cache_cutoff = datetime.now(timezone.utc) - timedelta(days=7)

            for idx, file_data in files_to_enrich:
                oeil_ref = file_data['oeil_ref']
                carriage = db.query(LegislativeCarriage).filter(
                    LegislativeCarriage.oeil_procedure_ref == oeil_ref
                ).first()

                if not carriage:
                    continue

                # Check cache freshness
                oeil_data = carriage.oeil_procedure_data or {}
                has_gateway = 'documentation_gateway' in oeil_data
                cache_fresh = (
                    carriage.enriched_at and
                    carriage.enriched_at.replace(tzinfo=timezone.utc) > cache_cutoff
                )

                if has_gateway and cache_fresh:
                    # Use cached data
                    actions = self._extract_actions_from_cached_data(oeil_data, carriage)
                    train_files[idx]['available_actions'] = actions
                    logger.debug(f"[OEIL-ACTIONS] Cached actions for {oeil_ref}")
                else:
                    # Need to fetch from OEIL
                    uncached_tasks.append((idx, oeil_ref, carriage))

            # Fetch uncached in parallel
            if uncached_tasks:
                from services.api_clients.oeil_client import OEILClient

                client = OEILClient()
                try:
                    # Fetch documentation gateway AND procedure lookup in parallel
                    # Gateway gives us docs (PR/AM/RD/AD), lookup gives rapporteur
                    gateway_tasks = [
                        client.get_documentation_gateway(ref)
                        for _, ref, _ in uncached_tasks
                    ]
                    lookup_tasks = [
                        client.lookup_procedure(ref)
                        for _, ref, _ in uncached_tasks
                    ]
                    all_results = await asyncio.gather(
                        *gateway_tasks, *lookup_tasks,
                        return_exceptions=True
                    )

                    n = len(uncached_tasks)
                    gateway_results = all_results[:n]
                    lookup_results = all_results[n:]

                    for i, (idx, oeil_ref, carriage) in enumerate(uncached_tasks):
                        gateway_result = gateway_results[i]
                        lookup_result = lookup_results[i]

                        if isinstance(gateway_result, Exception):
                            logger.warning(f"[OEIL-ACTIONS] Failed to fetch gateway for {oeil_ref}: {gateway_result}")
                            # Still try to extract from whatever cached data exists
                            actions = self._extract_actions_from_cached_data(
                                carriage.oeil_procedure_data or {}, carriage
                            )
                            train_files[idx]['available_actions'] = actions
                            continue

                        # Build cache data from gateway + lookup
                        existing_data = carriage.oeil_procedure_data or {}
                        existing_data['documentation_gateway'] = gateway_result
                        existing_data['documentation_gateway_fetched_at'] = datetime.now(timezone.utc).isoformat()

                        # Extract rapporteur + shadow rapporteurs from lookup result
                        if not isinstance(lookup_result, Exception) and lookup_result:
                            import re

                            def _parse_rap(text):
                                gm = re.search(r'\(([^)]+)\)', text)
                                nm = re.sub(r'\s*\([^)]*\)\s*', '', text).strip()
                                return {'name': nm, 'political_group': gm.group(1) if gm else None}

                            committee_data = existing_data.get('key_players', {}).get('committee_responsible', {})
                            committee_data['code'] = carriage.lead_committee

                            if lookup_result.rapporteurs:
                                committee_data['rapporteur'] = _parse_rap(lookup_result.rapporteurs[0])

                            if lookup_result.shadow_rapporteurs:
                                committee_data['shadow_rapporteurs'] = [
                                    _parse_rap(s) for s in lookup_result.shadow_rapporteurs
                                ]
                            elif 'shadow_rapporteurs' not in committee_data:
                                committee_data['shadow_rapporteurs'] = []

                            existing_data.setdefault('key_players', {})
                            existing_data['key_players']['committee_responsible'] = committee_data

                        carriage.oeil_procedure_data = existing_data
                        carriage.enriched_at = datetime.now(timezone.utc)

                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(carriage, 'oeil_procedure_data')

                        try:
                            db.commit()
                        except Exception as e:
                            logger.warning(f"[OEIL-ACTIONS] Cache write failed for {oeil_ref}: {e}")
                            db.rollback()

                        actions = self._extract_actions_from_cached_data(existing_data, carriage)
                        train_files[idx]['available_actions'] = actions
                        logger.info(
                            f"[OEIL-ACTIONS] Enriched {oeil_ref}: "
                            f"report={actions['has_draft_report']}, "
                            f"amendments={actions['has_amendments']}, "
                            f"rapporteur={actions['rapporteur_name']}"
                        )
                finally:
                    await client.close()

        except Exception as e:
            logger.warning(f"[OEIL-ACTIONS] Enrichment failed: {e}")
        finally:
            db.close()

        return train_files

    async def _fetch_committee_work_items(
        self,
        query: str,
        entities: ExtractedEntities
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant EP Committee Work in Progress items.

        Looks for:
        - Committee codes mentioned in query (AFET, LIBE, etc.)
        - Procedure references (2025/0580(CNS))
        - Procedure types (COD, CNS, APP, etc.)
        - Keywords in titles

        Args:
            query: User query
            entities: Extracted entities

        Returns:
            List of relevant committee work items
        """
        from sqlalchemy import or_

        try:
            db = SessionLocal()
            work_items = []
            query_lower = query.lower()

            # Check for committee mentions
            committee_mentions = []
            for code in EP_COMMITTEE_BY_CODE.keys():
                if code.lower() in query_lower:
                    committee_mentions.append(code)

            # Check for procedure type mentions
            procedure_type_mentions = []
            type_keywords = {
                'ordinary legislative': ProcedureTypeEnum.COD,
                'codecision': ProcedureTypeEnum.COD,
                'cod': ProcedureTypeEnum.COD,
                'consultation': ProcedureTypeEnum.CNS,
                'cns': ProcedureTypeEnum.CNS,
                'consent': ProcedureTypeEnum.APP,
                'app': ProcedureTypeEnum.APP,
                'own-initiative': ProcedureTypeEnum.INI,
                'ini': ProcedureTypeEnum.INI,
            }
            for keyword, proc_type in type_keywords.items():
                if keyword in query_lower and proc_type not in procedure_type_mentions:
                    procedure_type_mentions.append(proc_type)

            # Build query
            base_query = db.query(CommitteeWorkItem)

            # If specific committees mentioned, filter by those
            if committee_mentions or entities.committee_codes:
                all_committees = list(set(committee_mentions + entities.committee_codes))
                base_query = base_query.filter(
                    CommitteeWorkItem.committee_code.in_(all_committees)
                )

            # If procedure types mentioned, filter by those
            if procedure_type_mentions:
                base_query = base_query.filter(
                    CommitteeWorkItem.procedure_type.in_(procedure_type_mentions)
                )

            # If procedure references mentioned, add those
            if entities.procedure_references:
                base_query = base_query.filter(
                    or_(
                        CommitteeWorkItem.procedure_ref.in_(entities.procedure_references),
                        CommitteeWorkItem.committee_code.in_(committee_mentions) if committee_mentions else True
                    )
                )

            # If no specific filters matched, try keyword search in titles
            if not committee_mentions and not entities.committee_codes and \
               not procedure_type_mentions and not entities.procedure_references:
                # Extract meaningful keywords (3+ chars, skip stopwords)
                stopwords = {'the', 'and', 'for', 'that', 'this', 'with', 'from',
                             'about', 'what', 'how', 'does', 'are', 'was', 'has',
                             'tell', 'which', 'where', 'when', 'who', 'can', 'any',
                             'new', 'latest', 'recent', 'current'}
                keywords = [w for w in query_lower.split()
                            if len(w) >= 3 and w not in stopwords]
                if keywords:
                    keyword_filters = [
                        CommitteeWorkItem.title.ilike(f'%{kw}%')
                        for kw in keywords[:5]  # max 5 keywords
                    ]
                    base_query = base_query.filter(or_(*keyword_filters))

            # Order by relevance score then last updated
            base_query = base_query.order_by(
                CommitteeWorkItem.relevance_score.desc(),
                CommitteeWorkItem.last_updated.desc()
            )

            # Limit results
            results = base_query.limit(10).all()

            # Format results
            for item in results:
                committee_info = EP_COMMITTEE_BY_CODE.get(item.committee_code)
                committee_name = committee_info.name if committee_info else item.committee_code

                work_items.append({
                    'source_type': 'committee_work',
                    'procedure_ref': item.procedure_ref,
                    'committee_code': item.committee_code,
                    'committee_name': committee_name,
                    'title': item.title,
                    'procedure_type': _enum_str(item.procedure_type, 'INI'),
                    'committee_role': _enum_str(item.committee_role, 'lead'),
                    'relevance_score': item.relevance_score,
                    'rapporteur': item.rapporteur_name,
                    'status': _enum_str(item.status, 'unknown'),
                    'oeil_url': item.oeil_url,
                    'ep_page_url': item.ep_page_url,
                    'last_updated': item.last_updated.isoformat() if item.last_updated else None,
                    'description': item.description[:300] if item.description else None
                })

            db.close()

            logger.debug(f"Found {len(work_items)} committee work items for query")
            return work_items

        except Exception as e:
            logger.error(f"Failed to fetch committee work items: {str(e)}")
            return []

    async def _fetch_committee_minutes(
        self,
        query: str,
        entities: ExtractedEntities
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant EP Committee meeting minutes.

        Searches by committee code, procedure reference, or recent minutes.
        """
        from models.committee_minutes import CommitteeMinutes

        try:
            db = SessionLocal()
            minutes = []
            query_lower = query.lower()

            # Check for committee mentions
            committee_mentions = []
            for code in EP_COMMITTEE_BY_CODE.keys():
                if code.lower() in query_lower:
                    committee_mentions.append(code)

            all_committees = list(set(committee_mentions + (entities.committee_codes if entities.committee_codes else [])))

            # Check for minutes/meeting intent keywords
            minutes_intent = any(kw in query_lower for kw in [
                'minutes', 'meeting', 'discussed', 'voted', 'vote in committee',
                'committee vote', 'committee decision', 'acta', 'proces-verbal',
                'actes', 'minutes of', 'what did', 'what was discussed',
            ])

            if all_committees:
                results = (
                    db.query(CommitteeMinutes)
                    .filter(CommitteeMinutes.committee_code.in_(all_committees))
                    .order_by(CommitteeMinutes.meeting_date.desc())
                    .limit(5)
                    .all()
                )
                for r in results:
                    minutes.append({
                        'title': r.title,
                        'committee_code': r.committee_code,
                        'meeting_date': r.meeting_date.strftime('%Y-%m-%d') if r.meeting_date else None,
                        'publication_date': r.publication_date.strftime('%Y-%m-%d') if r.publication_date else None,
                        'pdf_url': r.pdf_url,
                        'full_text': r.full_text[:800] if r.full_text else None,
                        'votes': r.votes or [],
                        'agenda_items': r.agenda_items or [],
                        'decisions': r.decisions or [],
                        'source_type': 'committee_minutes',
                    })

            elif minutes_intent:
                # Generic minutes query: return most recent across all committees
                results = (
                    db.query(CommitteeMinutes)
                    .order_by(CommitteeMinutes.meeting_date.desc())
                    .limit(5)
                    .all()
                )
                for r in results:
                    minutes.append({
                        'title': r.title,
                        'committee_code': r.committee_code,
                        'meeting_date': r.meeting_date.strftime('%Y-%m-%d') if r.meeting_date else None,
                        'publication_date': r.publication_date.strftime('%Y-%m-%d') if r.publication_date else None,
                        'pdf_url': r.pdf_url,
                        'full_text': r.full_text[:800] if r.full_text else None,
                        'votes': r.votes or [],
                        'agenda_items': r.agenda_items or [],
                        'decisions': r.decisions or [],
                        'source_type': 'committee_minutes',
                    })

            db.close()
            return minutes

        except Exception as e:
            logger.error(f"Failed to fetch committee minutes: {str(e)}")
            return []

    async def _fetch_public_consultations(
        self,
        query: str,
        entities: ExtractedEntities
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant EC Public Consultations from Have Your Say portal.

        Looks for:
        - DG codes mentioned in query (GROW, CLIMA, etc.)
        - Policy area keywords
        - Consultation-related keywords
        - Open consultations with upcoming deadlines

        Args:
            query: User query
            entities: Extracted entities

        Returns:
            List of relevant public consultations
        """
        from sqlalchemy import or_, and_
        from datetime import datetime, timedelta

        try:
            db = SessionLocal()
            consultations = []
            query_lower = query.lower()

            # Check for consultation-related keywords
            consultation_keywords = [
                'consultation', 'have your say', 'public consultation',
                'feedback', 'participate', 'contribute', 'stakeholder',
                'ec consultation', 'european commission consultation'
            ]
            is_consultation_query = any(kw in query_lower for kw in consultation_keywords)

            # Check for DG mentions
            dg_mentions = []
            for dg in DGS:
                if dg.code.lower() in query_lower or dg.name.lower() in query_lower:
                    dg_mentions.append(dg.code)

            # Also check extracted DG codes from entities
            if entities.dg_codes:
                dg_mentions.extend(entities.dg_codes)
            dg_mentions = list(set(dg_mentions))

            # Check for policy area mentions
            policy_area_mentions = []
            for area in PolicyArea:
                if area.value in query_lower or area.name.lower() in query_lower:
                    policy_area_mentions.append(area.value)

            # Also check entities for policy areas
            if entities.policy_areas:
                policy_area_mentions.extend(entities.policy_areas)
            policy_area_mentions = list(set(policy_area_mentions))

            # Build query
            base_query = db.query(PublicConsultation)

            # Prioritise open consultations
            base_query = base_query.filter(
                PublicConsultation.status == ConsultationStatusEnum.OPEN
            )

            # If DGs mentioned, filter by those
            if dg_mentions:
                base_query = base_query.filter(
                    PublicConsultation.dg_responsible.in_(dg_mentions)
                )

            # If policy areas mentioned, filter by those
            if policy_area_mentions:
                # policy_areas is a JSONB array, need to use contains
                area_conditions = []
                for area in policy_area_mentions:
                    area_conditions.append(
                        PublicConsultation.policy_areas.contains([area])
                    )
                if area_conditions:
                    base_query = base_query.filter(or_(*area_conditions))

            # Order by deadline (soonest first) then by relevance score
            base_query = base_query.order_by(
                PublicConsultation.end_date.asc().nulls_last(),
                PublicConsultation.relevance_score.desc()
            )

            # Limit results
            results = base_query.limit(8).all()

            # If no results but it's a consultation query, try without filters
            if not results and is_consultation_query:
                fallback_query = db.query(PublicConsultation).filter(
                    PublicConsultation.status == ConsultationStatusEnum.OPEN
                ).order_by(
                    PublicConsultation.end_date.asc().nulls_last()
                ).limit(5)
                results = fallback_query.all()

            # Format results
            today = date.today()
            for item in results:
                days_remaining = None
                is_closing_soon = False
                if item.end_date:
                    end = item.end_date.date() if hasattr(item.end_date, "date") and not isinstance(item.end_date, date) else item.end_date
                    days_remaining = (end - today).days
                    is_closing_soon = 0 <= days_remaining <= 7

                consultations.append({
                    'source_type': 'public_consultation',
                    'consultation_id': item.initiative_id,
                    'publication_id': getattr(item, 'publication_id', None),
                    'initiative_id': getattr(item, 'initiative_id', None),
                    'title': item.title,
                    'short_title': getattr(item, 'short_title', None),
                    'description': item.description[:400] if item.description else None,
                    'dg_responsible': item.dg_responsible,
                    'dg_name': get_dg_full_name(item.dg_responsible) if item.dg_responsible else None,
                    'consultation_type': item.consultation_type.value if item.consultation_type else 'public_consultation',
                    'status': item.status.value if item.status else 'open',
                    'policy_areas': item.policy_areas or [],
                    'start_date': item.start_date.isoformat() if item.start_date else None,
                    'end_date': item.end_date.isoformat() if item.end_date else None,
                    'days_remaining': days_remaining,
                    'is_closing_soon': is_closing_soon,
                    'feedback_count': item.feedback_count,
                    'portal_url': item.portal_url,
                    'feedback_url': getattr(item, 'feedback_url', None),
                    'relevance_score': item.relevance_score
                })

            db.close()

            logger.debug(f"Found {len(consultations)} public consultations for query")
            return consultations

        except Exception as e:
            logger.error(f"Failed to fetch public consultations: {str(e)}")
            return []

    async def _fetch_mep_amendments(
        self,
        procedure_references: List[str],
        mep_names: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch scraped MEP amendment summaries from the database.

        Two modes:
        1. By procedure reference: summaries per procedure
        2. By MEP name (cross-procedure): when user asks about a specific MEP
           without a procedure reference, query amendments by author name
        """
        try:
            from collections import Counter
            from models.mep_amendment import MEPAmendment

            summaries = []

            # Mode 1: By procedure reference
            for proc_ref in (procedure_references or [])[:3]:
                amendments = self.db.query(MEPAmendment).filter(
                    MEPAmendment.procedure_reference == proc_ref
                ).all()

                if not amendments:
                    continue

                total = len(amendments)

                # Group counts
                group_counts = Counter(a.political_group or 'Unknown' for a in amendments)
                group_summary = ', '.join(
                    f"{g} ({c})" for g, c in group_counts.most_common(5)
                )

                # Most contested elements
                element_counts = Counter(a.element_reference for a in amendments)
                top_elements = [
                    {'reference': ref, 'count': c}
                    for ref, c in element_counts.most_common(5)
                ]

                # Top 5 key amendments (highest amendment numbers = later = often more political)
                key_amendments = sorted(amendments, key=lambda a: a.amendment_number)[:5]
                key_am_list = []
                for am in key_amendments:
                    key_am_list.append({
                        'number': am.amendment_number,
                        'authors': ', '.join(am.author_names or []),
                        'group': am.political_group or 'Unknown',
                        'element': am.element_reference,
                        'type': am.amendment_type,
                        'proposed_text': (am.proposed_text or '')[:150],
                    })

                summaries.append({
                    'procedure_reference': proc_ref,
                    'total': total,
                    'group_summary': group_summary,
                    'top_elements': top_elements,
                    'key_amendments': key_am_list,
                })

            # Mode 2: Cross-procedure MEP search (when no procedure refs detected)
            if not procedure_references and mep_names:
                for mep_name in (mep_names or [])[:2]:
                    amendments = (
                        self.db.query(MEPAmendment)
                        .filter(MEPAmendment.author_names.any(mep_name))
                        .limit(200)
                        .all()
                    )

                    if not amendments:
                        continue

                    total = len(amendments)

                    # Procedure breakdown
                    proc_counts = Counter(a.procedure_reference for a in amendments)
                    proc_summary = ', '.join(
                        f"{ref} ({c})" for ref, c in proc_counts.most_common(10)
                    )

                    # Group
                    groups = set(a.political_group for a in amendments if a.political_group)
                    group_str = ', '.join(sorted(groups)) if groups else 'Unknown'

                    # Sample amendments (first 5)
                    key_am_list = []
                    for am in amendments[:5]:
                        key_am_list.append({
                            'number': am.amendment_number,
                            'authors': ', '.join(am.author_names or []),
                            'group': am.political_group or 'Unknown',
                            'element': am.element_reference,
                            'type': am.amendment_type,
                            'procedure': am.procedure_reference,
                            'proposed_text': (am.proposed_text or '')[:150],
                        })

                    summaries.append({
                        'mep_name': mep_name,
                        'total': total,
                        'political_group': group_str,
                        'procedures_count': len(proc_counts),
                        'procedure_summary': proc_summary,
                        'key_amendments': key_am_list,
                    })

            return summaries

        except Exception as e:
            logger.error(f"Failed to fetch MEP amendments: {str(e)}")
            return []

    async def _fetch_commission_documents(
        self,
        query: str,
        entities: ExtractedEntities,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant Commission Documents from the EC Register.

        Tier-gated: Yellow and Blue tier users only (White tier returns []).

        Looks for:
        - DG codes mentioned in query or extracted from entities
        - Procedure references matching document procedure_ref
        - Doc type keywords (proposal -> COM, staff working -> SWD, joint -> JOIN)
        - Reference patterns (COM(...), SWD(...), JOIN(...))
        - Keyword search in titles for remaining queries

        Args:
            query: User query
            entities: Extracted entities
            user_id: Current user ID (for tier gating)

        Returns:
            List of relevant Commission documents
        """
        from sqlalchemy import or_
        from models.user import User

        try:
            db = SessionLocal()

            # Tier gate: Yellow and Blue only (pre-users get Blue-tier access as a preview)
            if user_id:
                user = db.query(User).filter(User.id == user_id).first()
                if not user or user.subscription_tier == 'white':
                    db.close()
                    return []
            # Pre-users (user_id=None) get full access to showcase Brubru's capabilities

            documents = []
            query_lower = query.lower()
            filters = []

            # 1. Check for DG mentions
            dg_mentions = []
            if entities.dg_codes:
                dg_mentions.extend(entities.dg_codes)
            for dg in DGS:
                if dg.code.lower() in query_lower or dg.name.lower() in query_lower:
                    dg_mentions.append(dg.code)
            dg_mentions = list(set(dg_mentions))

            if dg_mentions:
                filters.append(CommissionDocument.dg_responsible.in_(dg_mentions))

            # 2. Check for procedure references
            if entities.procedure_references:
                proc_conditions = []
                for proc_ref in entities.procedure_references:
                    proc_conditions.append(
                        CommissionDocument.procedure_ref.ilike(f"%{proc_ref}%")
                    )
                filters.append(or_(*proc_conditions))

            # 3. Check for document reference patterns (COM(...), SWD(...), JOIN(...))
            ref_pattern = re.search(r'(COM|SWD|JOIN|SEC)\s*\(\s*\d{4}\s*\)\s*\d+', query, re.IGNORECASE)
            if ref_pattern:
                ref_text = ref_pattern.group(0).replace(' ', '')
                filters.append(CommissionDocument.reference.ilike(f"%{ref_text}%"))

            # 4. Check for doc type keywords
            doc_type_filter = None
            if any(kw in query_lower for kw in ['proposal', 'initiative', 'com document', 'commission proposal']):
                doc_type_filter = 'COM'
            elif any(kw in query_lower for kw in ['staff working', 'swd', 'impact assessment']):
                doc_type_filter = 'SWD'
            elif any(kw in query_lower for kw in ['joint', 'join document']):
                doc_type_filter = 'JOIN'
            elif any(kw in query_lower for kw in ['official journal', 'adopted', 'regulation', 'directive']):
                doc_type_filter = 'OJ'

            if doc_type_filter:
                filters.append(CommissionDocument.doc_type == doc_type_filter)

            # Build query
            base_query = db.query(CommissionDocument)

            if filters:
                base_query = base_query.filter(or_(*filters))
            else:
                # 5. Keyword search in titles for general queries
                stopwords = {
                    'tell', 'about', 'what', 'which', 'where', 'when', 'does',
                    'have', 'this', 'that', 'with', 'from', 'they', 'been',
                    'were', 'will', 'would', 'could', 'should', 'there',
                    'their', 'some', 'more', 'than', 'very', 'just', 'also',
                    'know', 'like', 'want', 'need', 'give', 'information',
                    'main', 'issues', 'within', 'proposal', 'regulation',
                    'directive', 'please', 'could', 'think', 'opinion',
                    'effects', 'impact', 'implications', 'details', 'overview',
                    'addressing', 'regarding', 'concerning', 'related',
                    'negative', 'positive', 'specific', 'general', 'brief',
                    'important', 'major', 'different', 'various', 'other',
                    'union', 'european', 'market', 'global',
                }
                words = [w for w in query_lower.split() if len(w) > 3 and w not in stopwords]
                if words:
                    title_conditions = []
                    for word in words[:8]:
                        title_conditions.append(
                            CommissionDocument.title.ilike(f"%{word}%")
                        )
                        title_conditions.append(
                            CommissionDocument.common_name.ilike(f"%{word}%")
                        )
                    base_query = base_query.filter(or_(*title_conditions))

            # Order by most recent first
            base_query = base_query.order_by(
                CommissionDocument.publication_date.desc().nulls_last()
            )

            results = base_query.limit(10).all()

            # Fallback: if no specific matches, return most recent documents
            if not results:
                results = db.query(CommissionDocument).order_by(
                    CommissionDocument.publication_date.desc().nulls_last()
                ).limit(5).all()

            # Format results
            for item in results:
                documents.append({
                    'source_type': 'commission_document',
                    'reference': item.reference,
                    'title': item.title,
                    'common_name': item.common_name,
                    'doc_type': item.doc_type,
                    'dg_responsible': item.dg_responsible,
                    'publication_date': item.publication_date.isoformat() if item.publication_date else None,
                    'procedure_ref': item.procedure_ref,
                    'portal_url': item.portal_url,
                })

            db.close()

            logger.debug(f"Found {len(documents)} commission documents for query")
            return documents

        except Exception as e:
            logger.error(f"Failed to fetch commission documents: {str(e)}")
            return []

    async def _fetch_api_fallback_calendar(
        self,
        query: str,
        entities: "ExtractedEntities",
        existing_events: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Tier-3 v1 API backstop for calendar events.

        Fires when Tier 1 (smart context_builder filters) returned few/no events
        but the query clearly asks about events/meetings/dates. Uses the broad
        filter logic that backs `/api/v1/calendar/events`: date range + exclude
        recess only -- no NLP, no policy-area, no committee constraints that
        might over-filter.

        Only triggers when a minimum "calendar intent" signal is present, so
        we don't flood unrelated queries with calendar data.
        """
        # Don't run if we already have decent coverage from Tier 1
        if existing_events and len(existing_events) >= 3:
            return []

        q_lower = (query or "").lower()
        # Broad calendar-intent check (distinct from the narrower keyword sets
        # used by _fetch_eu_calendar_events itself)
        calendar_signal_words = (
            "event", "events", "meeting", "meetings", "agenda", "schedule",
            "calendar", "this week", "next week", "happening", "what's on",
            "upcoming", "planned", "plenary", "plenaries", "council", "councils",
            "college", "committee", "summit",
            # Third-party (euagenda) event-type keywords — added 22 April 2026
            "conference", "webinar", "roundtable", "workshop", "training",
            "think tank", "seminar",
        )
        has_calendar_intent = any(w in q_lower for w in calendar_signal_words)
        if not has_calendar_intent:
            return []

        from models.eu_calendar import EUCalendarEvent, EventTypeEnum
        from sqlalchemy import and_
        from datetime import date

        try:
            db = SessionLocal()
            today = date.today()
            # Broad window that mirrors /api/v1/calendar/events default surface
            date_start = today - timedelta(days=3)
            date_end = today + timedelta(days=21)

            # Explicit date detection already handled upstream; keep filters minimal
            q = db.query(EUCalendarEvent).filter(and_(
                EUCalendarEvent.start_date >= date_start,
                EUCalendarEvent.start_date <= date_end,
                EUCalendarEvent.event_type != EventTypeEnum.RECESS.value,
            )).order_by(EUCalendarEvent.start_date.asc()).limit(8)

            rows = q.all()
            events: List[Dict[str, Any]] = []
            for event in rows:
                events.append({
                    'source_type': 'eu_calendar_api_fallback',
                    'institution': event.institution if isinstance(event.institution, str) else event.institution.value,
                    'title': event.title,
                    'description': event.description,
                    'start_date': event.start_date.isoformat() if event.start_date else None,
                    'end_date': event.end_date.isoformat() if event.end_date else None,
                    'event_type': event.event_type if isinstance(event.event_type, str) else event.event_type.value,
                    'source_url': event.source_url,
                    'agenda_url': event.agenda_url,
                    'procedure_refs': event.procedure_refs or [],
                    'ep_committee_code': event.ep_committee_code,
                    'council_configuration': event.council_configuration,
                    'policy_areas': list(event.policy_areas or []),
                })
            db.close()
            return events
        except Exception as exc:
            logger.warning("[tier3] Calendar fallback DB query failed: %s", exc)
            return []

    async def _fetch_eu_calendar_events(
        self,
        query: str,
        entities: ExtractedEntities,
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant EU Calendar events from the database.

        No tier-gating -- calendar data is public knowledge.

        Detects temporal intent:
        - "last meeting" / "recent" / "what happened" -> past 30 days, desc
        - "next" / "upcoming" / "when is" -> next 30 days, asc
        - Default: next 14 days + past 14 days

        Filters by institution and committee code when detected.
        Excludes recess events.
        """
        from models.eu_calendar import EUCalendarEvent, EventTypeEnum, InstitutionEnum
        from sqlalchemy import and_, or_
        from datetime import date

        try:
            db = SessionLocal()
            today = date.today()
            query_lower = query.lower()

            # Detect temporal direction
            past_keywords = [
                'last meeting', 'last session', 'previous', 'recent',
                'what happened', 'what did', 'discussed', 'talked about',
                'took place', 'was held', 'outcome', 'results of',
                'latest meeting', 'most recent',
            ]
            future_keywords = [
                'next', 'upcoming', 'when is', 'when will', 'when does',
                'scheduled', 'planned', 'agenda for', 'what is on',
                'calendar', 'coming up',
            ]

            look_past = any(kw in query_lower for kw in past_keywords)
            look_future = any(kw in query_lower for kw in future_keywords)

            if look_past and not look_future:
                date_start = today - timedelta(days=30)
                date_end = today
                order_desc = True
            elif look_future and not look_past:
                date_start = today
                date_end = today + timedelta(days=30)
                order_desc = False
            else:
                # Default: window around today
                date_start = today - timedelta(days=14)
                date_end = today + timedelta(days=14)
                order_desc = False

            # Base filters: date range + exclude recess
            filters = [
                EUCalendarEvent.start_date >= date_start,
                EUCalendarEvent.start_date <= date_end,
                EUCalendarEvent.event_type != EventTypeEnum.RECESS.value,
            ]

            # Institution filter
            institution_map = {
                'parliament': InstitutionEnum.EP.value,
                'plenary': InstitutionEnum.EP.value,
                'plenaries': InstitutionEnum.EP.value,
                'mep': InstitutionEnum.EP.value,
                'committee': InstitutionEnum.EP.value,
                'council': InstitutionEnum.COUNCIL.value,
                'councils': InstitutionEnum.COUNCIL.value,
                'european council': InstitutionEnum.EUROPEAN_COUNCIL.value,
                'summit': InstitutionEnum.EUROPEAN_COUNCIL.value,
                'commission': InstitutionEnum.COMMISSION.value,
                'commissioner': InstitutionEnum.COMMISSION.value,
                'college': InstitutionEnum.COMMISSION.value,
                'ecb': InstitutionEnum.ECB.value,
                'central bank': InstitutionEnum.ECB.value,
            }
            # Collect ALL institution matches. If the query mentions multiple
            # institutions (e.g. "meetings, plenaries, councils"), drop the filter
            # entirely so results span every relevant institution — otherwise a
            # greedy first-match would narrow the answer to only one source.
            matched_institutions = set()
            for keyword, inst_value in institution_map.items():
                if keyword in query_lower:
                    matched_institutions.add(inst_value)

            if len(matched_institutions) == 1:
                filters.append(EUCalendarEvent.institution == next(iter(matched_institutions)))
            # else: 0 or 2+ matches -> no institution filter (broad retrieval)
            multi_institution_query = len(matched_institutions) != 1

            # Policy-area filter: detect common policy topics in the query and
            # match against event.policy_areas ARRAY. Increases precision for
            # queries like "energy events next week", "climate meetings".
            policy_keyword_map = {
                'energy': ['energy', 'climate'],
                'climate': ['climate', 'energy'],
                'environment': ['environment', 'climate'],
                'digital': ['digital'],
                'ai ': ['digital'],
                'artificial intelligence': ['digital'],
                'defence': ['defence', 'foreign_affairs'],
                'defense': ['defence', 'foreign_affairs'],
                'trade': ['trade', 'foreign_affairs'],
                'foreign': ['foreign_affairs'],
                'health': ['health'],
                'agriculture': ['agriculture'],
                'farming': ['agriculture'],
                'fisheries': ['fisheries'],
                'transport': ['transport'],
                'employment': ['employment'],
                'budget': ['budget', 'economy'],
                'economy': ['economy', 'budget'],
                'migration': ['migration', 'justice'],
                'justice': ['justice'],
                'security': ['security', 'defence'],
                'cohesion': ['cohesion', 'regional'],
                'regional': ['regional', 'cohesion'],
                'research': ['research'],
            }
            matched_areas: List[str] = []
            for keyword, areas in policy_keyword_map.items():
                if keyword in query_lower:
                    matched_areas.extend(areas)
            matched_areas = list(dict.fromkeys(matched_areas))  # dedupe, preserve order
            if matched_areas:
                area_conditions = [
                    EUCalendarEvent.policy_areas.any(area) for area in matched_areas
                ]
                filters.append(or_(*area_conditions))

            # Committee code filter. Skip when the query explicitly spans
            # multiple institutions (Council, Commission events don't carry an
            # ep_committee_code, so a hard filter would wrongly exclude them).
            # Also keep Council/Commission events even when a committee code
            # was inferred from a policy topic (e.g. "energy" -> ITRE).
            if entities.committee_codes and not multi_institution_query:
                committee_conditions = [
                    EUCalendarEvent.ep_committee_code == code
                    for code in entities.committee_codes
                ]
                # Always allow non-EP events through so institutional coverage
                # stays broad when the user asks "what's happening".
                committee_conditions.append(EUCalendarEvent.institution != InstitutionEnum.EP.value)
                filters.append(or_(*committee_conditions))

            # Procedure reference filter
            if entities.procedure_references:
                proc_conditions = []
                for proc_ref in entities.procedure_references:
                    proc_conditions.append(
                        EUCalendarEvent.procedure_refs.any(proc_ref)
                    )
                filters.append(or_(*proc_conditions))

            # Build query
            base_query = db.query(EUCalendarEvent).filter(and_(*filters))

            if order_desc:
                base_query = base_query.order_by(EUCalendarEvent.start_date.desc())
            else:
                base_query = base_query.order_by(EUCalendarEvent.start_date.asc())

            results = base_query.limit(8).all()

            # Format results
            events = []
            for event in results:
                events.append({
                    'source_type': 'eu_calendar',
                    'institution': event.institution if isinstance(event.institution, str) else event.institution.value,
                    'title': event.title,
                    'description': event.description,
                    'start_date': event.start_date.isoformat() if event.start_date else None,
                    'end_date': event.end_date.isoformat() if event.end_date else None,
                    'start_time': event.start_time.isoformat() if event.start_time else None,
                    'all_day': event.all_day,
                    'event_type': event.event_type if isinstance(event.event_type, str) else event.event_type.value,
                    'source_url': event.source_url,
                    'agenda_url': event.agenda_url,
                    'procedure_refs': event.procedure_refs or [],
                    'ep_committee_code': event.ep_committee_code,
                    'council_configuration': event.council_configuration,
                })

            db.close()

            logger.debug(f"Found {len(events)} EU Calendar events for query")
            return events

        except Exception as e:
            logger.error(f"Failed to fetch EU Calendar events: {str(e)}")
            return []

    def _resolve_alias_celex_pairs(
        self, query: str, existing: List[Dict[str, Any]]
    ) -> List[tuple[str, Any]]:
        """
        If the query mentions a law by acronym/nickname (GDPR, DSA, AI Act,
        Chips Act, ...) return the resolved (celex, alias) pairs that are not
        already covered by `existing` laws.
        """
        try:
            from services.parsers.law_alias_resolver import find_aliases_with_celex
        except Exception:
            return []
        covered = {(l.get('celex') or '').upper() for l in existing}
        out = []
        for alias, celex in find_aliases_with_celex(query).items():
            if celex and celex.upper() not in covered:
                out.append((celex, alias))
                covered.add(celex.upper())
        return out

    def _fetch_recital_article_links(
        self,
        db,
        laws: List[Dict[str, Any]],
        query: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        For each law in `laws`, if the query mentions one or more articles,
        return TF-IDF-linked recitals for those articles.

        Returns a dict keyed by CELEX with entries:
            {
              celex: [
                {"article": "Article 12", "recitals": [{number, score, snippet}, ...]},
                ...
              ]
            }

        The recital-article map is computed on demand from the local Formex
        archive and cached in eu_laws.extra_metadata (see
        services/parsers/recital_article_store.py).
        """
        if not laws:
            return {}

        import re as _re

        # Pull article numbers from the query: supports "Article 12", "Art. 7(3)",
        # "articles 3 and 4", "article 3" (case-insensitive). Capture the integer.
        article_numbers = set()
        for m in _re.finditer(r"\b(?:article|art\.?)\s*(\d{1,3})", query, _re.IGNORECASE):
            article_numbers.add(m.group(1))
        if not article_numbers:
            return {}

        from services.parsers.recital_article_store import get_or_compute_map

        out: Dict[str, List[Dict[str, Any]]] = {}
        for law_dict in laws:
            celex = law_dict.get('celex')
            if not celex:
                continue
            mapping = get_or_compute_map(db, celex)
            if not mapping:
                continue
            rows = []
            for num in article_numbers:
                for key in (f"Article {num}", f"Article {num.zfill(2)}", f"Article {num.zfill(3)}", num):
                    if key in mapping and mapping[key]:
                        rows.append({"article": f"Article {num}", "recitals": mapping[key][:3]})
                        break
            if rows:
                out[celex] = rows
        return out

    def _fetch_defined_terms_matches(
        self,
        db,
        laws: List[Dict[str, Any]],
        query: str,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        For each law in `laws`, return any defined terms (from Article 3/4 of
        that law) whose term appears in the query. Up to 5 per law.

        Uses the on-demand Formex-parsed store (see
        services/parsers/definition_store.py).
        """
        if not laws:
            return {}
        from services.parsers.definition_store import get_or_compute_map as _get_defs

        q_lower = query.lower()
        out: Dict[str, List[Dict[str, Any]]] = {}
        for law_dict in laws:
            celex = law_dict.get('celex')
            if not celex:
                continue
            terms = _get_defs(db, celex)
            if not terms:
                continue
            hits: List[Dict[str, Any]] = []
            for term_key, entry in terms.items():
                # term_key is already lowercase per extract_definitions_map
                # Require word-boundary-ish hit: at least 4 characters and present as substring
                if len(term_key) < 4:
                    continue
                if term_key in q_lower:
                    hits.append(entry)
                    if len(hits) >= 5:
                        break
            if hits:
                out[celex] = hits
        return out

    async def _fetch_eu_laws_from_database(
        self,
        query: str,
        entities: ExtractedEntities
    ) -> List[Dict[str, Any]]:
        """
        Fetch EU laws from local LEG_2025-11 database (28K+ laws).

        Uses PostgreSQL TSVECTOR full-text search (GIN-indexed) for fast,
        relevance-ranked results. Falls back to CELEX direct lookup when
        the user references specific law identifiers.

        Args:
            query: User query
            entities: Extracted entities (CELEX, policy areas, etc.)

        Returns:
            List of relevant EU laws
        """
        from services.eu_law_search import EULawSearchService
        from models.eu_law import EULaw
        from core.database import SessionLocal

        laws = []

        try:
            db = SessionLocal()

            try:
                search_service = EULawSearchService(db)

                # Priority 1: Direct CELEX lookup
                if entities.celex_numbers:
                    for celex in entities.celex_numbers[:3]:
                        law = db.query(EULaw).filter(EULaw.celex == celex).first()
                        if law:
                            laws.append({
                                'celex': law.celex,
                                'title': law.title,
                                'doc_type': law.doc_type_normalized or law.doc_type,
                                'date': law.date.isoformat() if law.date else None,
                                'oj_reference': law.oj_reference,
                                'policy_area': law.policy_area,
                                'legal_basis': law.legal_basis or [],
                                'citations': law.citations or [],
                                'source': 'local_database',
                            })
                            logger.debug(f"Found law in local database: {celex}")

                # Priority 1b: resolve aliases/nicknames in the free-text query
                # (GDPR, DSA, AI Act, Chips Act, CBAM, ...) to their CELEX and
                # load the same way. This makes recital-article and defined-term
                # enrichment below work even when the user never types a CELEX.
                try:
                    alias_pairs = self._resolve_alias_celex_pairs(query, laws)
                    for alias_celex, alias_name in alias_pairs[:3]:
                        law = db.query(EULaw).filter(EULaw.celex == alias_celex).first()
                        if law:
                            laws.append({
                                'celex': law.celex,
                                'title': law.title,
                                'doc_type': law.doc_type_normalized or law.doc_type,
                                'date': law.date.isoformat() if law.date else None,
                                'oj_reference': law.oj_reference,
                                'policy_area': law.policy_area,
                                'legal_basis': law.legal_basis or [],
                                'citations': law.citations or [],
                                'source': f'local_database (via alias "{alias_name}")',
                                'resolved_alias': alias_name,
                            })
                            logger.debug(f"Found law in local database via alias {alias_name} -> {alias_celex}")
                except Exception as e:  # pragma: no cover
                    logger.debug(f"alias resolution skipped: {e}")

                # Recital-article enrichment: if the query mentions "Article N",
                # fetch the TF-IDF-linked recitals for that article from
                # extra_metadata.recital_article_map (computed on demand).
                try:
                    recital_article_ctx = self._fetch_recital_article_links(
                        db=db, laws=laws, query=query
                    )
                    if recital_article_ctx:
                        for law_dict in laws:
                            key = law_dict['celex']
                            if key in recital_article_ctx:
                                law_dict['recital_article_links'] = recital_article_ctx[key]
                except Exception as e:  # pragma: no cover
                    logger.debug(f"recital_article enrichment skipped: {e}")

                # Defined-terms enrichment: surface any Article 3/4 definitions
                # whose term appears in the query.
                try:
                    defined_terms_ctx = self._fetch_defined_terms_matches(
                        db=db, laws=laws, query=query
                    )
                    if defined_terms_ctx:
                        for law_dict in laws:
                            key = law_dict['celex']
                            if key in defined_terms_ctx:
                                law_dict['defined_terms'] = defined_terms_ctx[key]
                except Exception as e:  # pragma: no cover
                    logger.debug(f"defined_terms enrichment skipped: {e}")

                # Priority 2: TSVECTOR full-text search (relevance-ranked)
                if not laws:
                    policy_area = entities.policy_areas[0] if entities.policy_areas else None

                    results = search_service.search_tsvector(
                        query=query,
                        policy_area=policy_area,
                        primary_only=True,
                        doc_types=["Regulation", "Directive", "Decision"],
                        limit=5,
                    )

                    for result in results:
                        laws.append({
                            'celex': result.get('celex'),
                            'title': result.get('title'),
                            'doc_type': result.get('doc_type'),
                            'date': result.get('date'),
                            'policy_area': result.get('policy_area'),
                            'citations': result.get('citations') or [],
                            'source': 'local_database_search',
                        })

                    logger.debug(f"TSVECTOR search returned {len(results)} laws")

                logger.info(f"Fetched {len(laws)} laws from local database")

            finally:
                db.close()

        except Exception as e:
            logger.error(f"Failed to fetch from local EU laws database: {str(e)}")

        return laws

    async def _search_eprs_publications(
        self,
        query: str,
        entities: ExtractedEntities
    ) -> List[Dict[str, Any]]:
        """
        Search EPRS publications for relevant briefings and explanations.

        Phase 2: This is the KEY method that brings EPRS "jargon translators"
        into the AI context.

        Two-pass search:
        1. PostgreSQL (persistent, always available) - by CELEX, procedure, or text search
        2. ChromaDB (semantic, may be empty) - vector similarity search

        Args:
            query: User query
            entities: Extracted entities (to help with filtering)

        Returns:
            List of relevant EPRS publications
        """
        eprs_results = []
        seen_ids = set()

        # Pass 1: PostgreSQL search (persistent, reliable)
        try:
            pg_results = self._search_eprs_postgresql(query, entities)
            for pub in pg_results:
                pub_id = pub.get('publication_id')
                if pub_id and pub_id not in seen_ids:
                    seen_ids.add(pub_id)
                    eprs_results.append(pub)

            if pg_results:
                logger.debug(f"Found {len(pg_results)} EPRS publications from PostgreSQL")

        except Exception as e:
            logger.warning(f"PostgreSQL EPRS search failed (non-fatal): {str(e)}")

        # Pass 2: ChromaDB semantic search (if we need more results)
        # Skipped when the vector store is empty (production): self.eprs_indexer is None,
        # the PostgreSQL pass above already carried EPRS retrieval, and we never touch
        # chromadb. Runs only when a populated store made the indexer available.
        if self.eprs_indexer is not None and len(eprs_results) < self.max_eprs_results:
            try:
                # Build filters based on extracted entities
                filters = {}
                if entities.policy_areas:
                    filters['policy_areas'] = entities.policy_areas[0]
                if entities.committee_codes:
                    filters['committees'] = entities.committee_codes[0]

                search_results = await self.eprs_indexer.search(
                    query=query,
                    limit=self.max_eprs_results - len(eprs_results),
                    filters=filters if filters else None
                )

                for result in search_results:
                    metadata = result.get('metadata', {})
                    pub_id = metadata.get('publication_id')

                    if pub_id and pub_id in seen_ids:
                        continue
                    seen_ids.add(pub_id)

                    eprs_results.append({
                        'chunk_id': result.get('id'),
                        'publication_id': pub_id,
                        'text': result.get('text', '')[:500],
                        'title': metadata.get('title', 'Unknown'),
                        'publication_type': metadata.get('publication_type', 'unknown'),
                        'publication_url': metadata.get('html_url'),
                        'pdf_url': metadata.get('pdf_url'),
                        'related_celex': metadata.get('related_celex_numbers', '').split(',') if metadata.get('related_celex_numbers') else [],
                        'related_procedures': metadata.get('related_procedures', '').split(',') if metadata.get('related_procedures') else [],
                        'policy_areas': metadata.get('policy_areas', '').split(',') if metadata.get('policy_areas') else [],
                        'distance': result.get('distance')
                    })

                if search_results:
                    logger.debug(f"Found {len(search_results)} additional EPRS publications from ChromaDB")

            except Exception as e:
                logger.warning(f"ChromaDB EPRS search failed (non-fatal): {str(e)}")

        if eprs_results:
            logger.debug(f"Total: {len(eprs_results)} EPRS publications for query")
        else:
            logger.debug("No EPRS publications found for query")

        return eprs_results[:self.max_eprs_results]

    def _search_eprs_postgresql(
        self,
        query: str,
        entities: ExtractedEntities
    ) -> List[Dict[str, Any]]:
        """
        Search EPRS publications in PostgreSQL.

        Searches by:
        1. CELEX number match (highest priority)
        2. Procedure reference match
        3. Title/summary text search (fallback)

        Returns:
            List of formatted EPRS publication dicts
        """
        from core.database import SessionLocal
        from models.eprs_publication import EPRSPublication as EPRSPubModel
        from sqlalchemy import or_, desc

        results = []
        db = None

        try:
            db = SessionLocal()

            # Strategy 1: Exact CELEX match
            if entities.celex_numbers:
                for celex in entities.celex_numbers[:3]:
                    pubs = (
                        db.query(EPRSPubModel)
                        .filter(EPRSPubModel.related_celex_numbers.any(celex))
                        .order_by(desc(EPRSPubModel.publication_date))
                        .limit(3)
                        .all()
                    )
                    results.extend(pubs)

            # Strategy 2: Procedure reference match
            if entities.procedure_references and len(results) < self.max_eprs_results:
                for proc_ref in entities.procedure_references[:3]:
                    pubs = (
                        db.query(EPRSPubModel)
                        .filter(EPRSPubModel.related_procedures.any(proc_ref))
                        .order_by(desc(EPRSPubModel.publication_date))
                        .limit(3)
                        .all()
                    )
                    results.extend(pubs)

            # Strategy 3: Title/summary text search (only if no structured matches)
            if not results:
                # Extract meaningful search terms
                query_lower = query.lower()
                search_words = [
                    w for w in query_lower.split()
                    if len(w) > 4 and w not in {
                        'about', 'there', 'their', 'which', 'would',
                        'could', 'should', 'where', 'these', 'those',
                        'being', 'having', 'doing', 'going', 'making',
                    }
                ]

                if search_words:
                    # Use the most specific terms (longest words first)
                    search_words.sort(key=len, reverse=True)
                    search_term = f"%{' '.join(search_words[:3])}%"

                    pubs = (
                        db.query(EPRSPubModel)
                        .filter(
                            or_(
                                EPRSPubModel.title.ilike(search_term),
                                EPRSPubModel.summary.ilike(search_term)
                            )
                        )
                        .order_by(desc(EPRSPubModel.publication_date))
                        .limit(self.max_eprs_results)
                        .all()
                    )

                    # If combined search fails, try individual terms
                    if not pubs and len(search_words) > 1:
                        for word in search_words[:2]:
                            word_pubs = (
                                db.query(EPRSPubModel)
                                .filter(
                                    or_(
                                        EPRSPubModel.title.ilike(f"%{word}%"),
                                        EPRSPubModel.summary.ilike(f"%{word}%")
                                    )
                                )
                                .order_by(desc(EPRSPubModel.publication_date))
                                .limit(3)
                                .all()
                            )
                            pubs.extend(word_pubs)

                    results.extend(pubs)

            # Deduplicate and format
            seen = set()
            formatted = []
            for pub in results:
                if pub.publication_id in seen:
                    continue
                seen.add(pub.publication_id)

                text_excerpt = ''
                if pub.full_text:
                    text_excerpt = pub.full_text[:500]
                elif pub.summary:
                    text_excerpt = pub.summary[:500]

                formatted.append({
                    'publication_id': pub.publication_id,
                    'text': text_excerpt,
                    'title': pub.title,
                    'publication_type': pub.publication_type or 'unknown',
                    'publication_url': pub.html_url,
                    'pdf_url': pub.pdf_url,
                    'related_celex': pub.related_celex_numbers or [],
                    'related_procedures': pub.related_procedures or [],
                    'policy_areas': pub.policy_areas or [],
                })

            return formatted[:self.max_eprs_results]

        except Exception as e:
            logger.error(f"PostgreSQL EPRS search error: {str(e)}")
            return []

        finally:
            if db:
                db.close()

    async def _fetch_web_search(
        self,
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch real-time web search results via Tavily.

        Provides current news, statements, and web content that may not
        yet be in our structured EU databases.

        Args:
            query: User query

        Returns:
            List of web search results with title, url, content, and source
        """
        web_results = []

        if not self.tavily_client:
            return web_results

        try:
            # Determine if this is a news-focused query
            news_keywords = [
                'latest', 'recent', 'today', 'yesterday', 'this week',
                'breaking', 'news', 'announced', 'said', 'statement',
                'vote', 'voted', 'adopted', 'rejected', 'approved'
            ]
            query_lower = query.lower()
            is_news_query = any(kw in query_lower for kw in news_keywords)

            if is_news_query:
                # Use news-focused search for EU sources
                response = await self.tavily_client.search_eu_news(
                    query=query,
                    max_results=5
                )
            else:
                # General search
                response = await self.tavily_client.search(
                    query=f"{query} EU European Union",
                    max_results=5
                )

            # Format results
            for result in response.results:
                web_results.append({
                    'title': result.title,
                    'url': result.url,
                    'content': result.content[:500] if result.content else '',
                    'score': result.score,
                    'published_date': result.published_date,
                    'source': 'tavily_web_search'
                })

            # Include AI-generated answer if available
            if response.answer:
                web_results.insert(0, {
                    'title': 'AI Summary of Web Results',
                    'url': '',
                    'content': response.answer,
                    'score': 1.0,
                    'published_date': None,
                    'source': 'tavily_ai_answer'
                })

            if web_results:
                logger.debug(
                    f"Tavily returned {len(web_results)} results "
                    f"in {response.response_time:.2f}s"
                )

        except Exception as e:
            logger.error(f"Web search failed: {str(e)}")
            # Don't fail context building if web search fails

        return web_results

    # Trusted EU institutional domains for fallback search
    EU_INSTITUTIONAL_DOMAINS = [
        # Official EU institutions
        "eur-lex.europa.eu",
        "europarl.europa.eu",
        "consilium.europa.eu",
        "ec.europa.eu",
        "commission.europa.eu",
        "cor.europa.eu",
        "eesc.europa.eu",
        "curia.europa.eu",
        "ecb.europa.eu",
        "op.europa.eu",
        "data.europa.eu",
        # EU agencies
        "eba.europa.eu",
        "esma.europa.eu",
        "eiopa.europa.eu",
        # DG subdomains (covered by ec.europa.eu but explicit for Tavily)
        "joint-research-centre.ec.europa.eu",
        # EP Think Tank
        "epthinktank.eu",
        # Policy media and think tanks (MUST include)
        "politico.eu",
        "contexte.com",
        "bruegel.org",
        "euractiv.com",
        # Other media
        "euronews.com",
    ]

    # Map domains to human-readable source names for AI attribution
    DOMAIN_TO_SOURCE_NAME = {
        "eur-lex.europa.eu": "EUR-Lex",
        "europarl.europa.eu": "European Parliament",
        "epthinktank.eu": "EP Think Tank (EPRS)",
        "consilium.europa.eu": "Council of the EU",
        "ec.europa.eu": "European Commission",
        "commission.europa.eu": "European Commission",
        "cor.europa.eu": "Committee of the Regions",
        "eesc.europa.eu": "European Economic and Social Committee",
        "curia.europa.eu": "Court of Justice of the EU",
        "ecb.europa.eu": "European Central Bank",
        "op.europa.eu": "EU Publications Office",
        "data.europa.eu": "EU Open Data Portal",
        "eba.europa.eu": "European Banking Authority",
        "esma.europa.eu": "European Securities and Markets Authority",
        "eiopa.europa.eu": "European Insurance and Occupational Pensions Authority",
        "joint-research-centre.ec.europa.eu": "Joint Research Centre (JRC)",
        "politico.eu": "Politico Europe",
        "contexte.com": "Contexte",
        "bruegel.org": "Bruegel",
        "euractiv.com": "Euractiv",
        "euronews.com": "Euronews",
    }

    @staticmethod
    def _extract_source_name(url: str) -> str:
        """Extract a human-readable source name from a URL."""
        if not url:
            return "Unknown"
        try:
            from urllib.parse import urlparse
            hostname = urlparse(url).hostname or ""
            # Try exact match first, then partial match on parent domain
            for domain, name in ContextBuilder.DOMAIN_TO_SOURCE_NAME.items():
                if hostname == domain or hostname.endswith("." + domain):
                    return name
            # Fallback: use hostname cleaned up
            return hostname.replace("www.", "").split(".")[0].capitalize()
        except Exception:
            return "Unknown"

    # ── EP Committee Meeting Transcripts (AI-transcribed via Whisper) ────

    COMMITTEE_TRANSCRIPT_INTENT_PHRASES = [
        # English
        "committee meeting", "committee debate", "committee discussion",
        "committee hearing", "said in committee", "committee exchange",
        "committee transcript", "libe committee", "envi committee",
        "econ committee", "agri committee", "imco committee", "juri committee",
        "itre committee", "tran committee", "regi committee", "budg committee",
        "cont committee", "pech committee", "afet committee", "inta committee",
        "empl committee", "cult committee", "femm committee", "fisc committee",
        "sede subcommittee", "droi subcommittee", "peti committee",
        "euds subcommittee", "hous committee", "sant subcommittee",
        # French
        "réunion de commission", "commission libe", "commission envi",
        "commission econ", "en commission parlementaire",
        # Spanish
        "reunión de comisión", "comisión parlamentaria", "comisión libe",
        "comisión del parlamento",
        # Italian
        "riunione di commissione", "commissione parlamentare",
        # Dutch
        "parlementaire commissie", "vergadering commissie",
        # Catalan
        "reunió de comissió", "comissió parlamentària",
    ]

    # ── EP Plenary Debate Transcripts (CRE) ──────────────────────────────

    DEBATE_INTENT_PHRASES = [
        # English
        "plenary debate", "debate in parliament", "ep debate", "meps discussed",
        "what did meps say", "parliament debate", "parliament discussed",
        "plenary session debate", "debate on", "debated in plenary",
        "summarise the debate", "summarize the debate", "plenary discussion",
        "what was said in plenary", "debate transcript", "cre transcript",
        "who spoke in plenary", "speakers in the debate",
        # French
        "debat en pleniere", "debat au parlement", "discussion en pleniere",
        # Spanish
        "debate en el pleno", "debate en el parlamento", "sesion plenaria debate",
        # Catalan
        "debat al plenari", "debat al parlament",
        # Italian
        "dibattito in plenaria", "dibattito al parlamento",
        # Dutch
        "debat in de plenaire", "plenair debat",
    ]

    def _detect_plenary_debate_intent(self, query: str) -> Optional[date]:
        """Detect if user is asking about an EP plenary debate and extract the date.

        Returns the plenary session date if debate intent is detected, None otherwise.
        """
        date_type = date  # alias for clarity
        query_lower = query.lower()

        # Check for debate intent phrases
        has_debate_intent = any(phrase in query_lower for phrase in self.DEBATE_INTENT_PHRASES)
        if not has_debate_intent:
            return None

        # Try to extract a date from the query
        # Pattern 1: "March 10" / "10 March" / "march 10 2026"
        date_patterns = [
            r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})?',
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:\s*,?\s*(\d{4}))?',
            r'(\d{4})-(\d{2})-(\d{2})',
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
        ]

        import re as _re
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        }

        # Day Month [Year]
        m = _re.search(r'(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})?', query_lower)
        if m:
            day = int(m.group(1))
            month = month_names[m.group(2)]
            year = int(m.group(3)) if m.group(3) else date_type.today().year
            try:
                return date_type(year, month, day)
            except ValueError:
                pass

        # Month Day [Year]
        m = _re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})(?:\s*,?\s*(\d{4}))?', query_lower)
        if m:
            month = month_names[m.group(1)]
            day = int(m.group(2))
            year = int(m.group(3)) if m.group(3) else date_type.today().year
            try:
                return date_type(year, month, day)
            except ValueError:
                pass

        # ISO date
        m = _re.search(r'(\d{4})-(\d{2})-(\d{2})', query_lower)
        if m:
            try:
                return date_type(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass

        # Relative dates: "last week", "this week", "yesterday", "today"
        today = date_type.today()
        if "yesterday" in query_lower:
            return today - timedelta(days=1)
        if "last monday" in query_lower or "last tuesday" in query_lower or "last wednesday" in query_lower or "last thursday" in query_lower:
            # Find last occurrence of that weekday
            day_names = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4}
            for day_name, weekday in day_names.items():
                if f"last {day_name}" in query_lower:
                    days_back = (today.weekday() - weekday) % 7
                    if days_back == 0:
                        days_back = 7
                    return today - timedelta(days=days_back)

        # "this week" or "last week" with debate topic -> try to find the most recent plenary
        if "this week" in query_lower or "last week" in query_lower:
            # Most recent Monday-Thursday (plenary days)
            offset = 7 if "last week" in query_lower else 0
            for i in range(offset, offset + 7):
                d = today - timedelta(days=i)
                if d.weekday() in (0, 1, 2, 3):  # Mon-Thu
                    return d

        # No date found but debate intent detected -> try most recent plenary week
        # Return last Monday-Thursday
        for i in range(0, 14):
            d = today - timedelta(days=i)
            if d.weekday() in (0, 1, 2, 3):
                return d

        return None

    async def _fetch_plenary_debate(self, query: str, session_date: date) -> Optional[str]:
        """Fetch CRE transcript and find the matching debate for a user query."""
        from services.api_clients.cre_client import get_cre_client

        client = get_cre_client()
        session = await client.fetch_session(session_date)

        if not session or not session.debates:
            # Try adjacent days (plenary sessions span Mon-Thu)
            from datetime import timedelta
            for offset in [-1, 1, -2, 2]:
                alt_date = session_date + timedelta(days=offset)
                session = await client.fetch_session(alt_date)
                if session and session.debates:
                    break

        if not session or not session.debates:
            return None

        # Extract topic from query (remove debate intent phrases)
        import re as _re
        topic = query.lower()
        for phrase in self.DEBATE_INTENT_PHRASES:
            topic = topic.replace(phrase, "")
        # Remove date-related and stop words using word boundaries
        stop_words = {"march", "april", "may", "june", "monday", "tuesday", "wednesday",
                      "thursday", "friday", "last", "this", "week", "2026", "2025",
                      "the", "on", "about", "of", "what", "did", "was", "summarise",
                      "summarize", "summary", "tell", "me", "10", "11", "12", "13"}
        words = topic.split()
        topic = " ".join(w for w in words if w.strip(".,;:!?") not in stop_words)
        topic = topic.strip()

        # Try to find specific debate by topic
        debate = client.search_debate_by_topic(session, topic)
        if debate:
            return client.format_debate_for_context(debate)

        # If no specific topic match, return session overview + largest debate
        result = client.format_session_overview(session)
        if session.debates:
            largest = max(session.debates, key=lambda d: d.speaker_count)
            result += "\n\n" + client.format_debate_for_context(largest)
        return result

    # ------------------------------------------------------------------
    # On-demand: TODAY block (date-anchored calendar + active files)
    # ------------------------------------------------------------------

    # Phrases across EN/ES/CA/FR/IT/NL/DE that indicate the user wants
    # CURRENT / TODAY / THIS-WEEK legislative activity rather than general
    # background. Detection is permissive (substring match, accent-tolerant).
    TODAY_INTENT_PHRASES = (
        # English
        "today", "right now", "happening now", "this week", "these days",
        "currently being", "in progress today", "being discussed today",
        "being processed today", "what is going on", "what's going on",
        "being debated today", "what laws are being",
        # Spanish
        "hoy", "hoy en dia", "hoy en día", "en este momento", "esta semana",
        "estos dias", "estos días", "actualmente se", "se estan tramitando",
        "se están tramitando", "que leyes se", "qué leyes se",
        "durante el dia de hoy", "durante el día de hoy",
        # Catalan
        "avui", "aquesta setmana", "aquests dies", "actualment es",
        "durant el dia d'avui", "durant el dia davui",
        # French
        "aujourd'hui", "cette semaine", "ces jours",
        "en cours aujourd'hui", "quelles lois",
        # Italian
        "oggi", "questa settimana",
        # Dutch
        "vandaag", "deze week",
        # German
        "heute", "diese woche",
    )

    def _detect_today_intent(self, query: str) -> bool:
        """Return True if the query asks about current / today / this-week events.

        Matches are substring-based and normalised to lowercase with common
        accent folding for Spanish/Catalan/French. Accent-bearing user input
        (hoy día, qué leyes, aujourd'hui) hits the folded and the raw form.
        """
        if not query:
            return False
        q = query.lower()
        q_nfd = (
            q.replace("á", "a").replace("é", "e").replace("í", "i")
             .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
             .replace("ü", "u").replace("à", "a").replace("è", "e")
             .replace("ò", "o").replace("ç", "c")
        )
        for phrase in self.TODAY_INTENT_PHRASES:
            if phrase in q or phrase in q_nfd:
                return True
        return False

    # Cache of {year: {date: week_type}} built from the verified calendar JSON.
    _EP_WEEK_TYPE_CACHE: Dict[int, Dict[str, str]] = {}

    @classmethod
    def _load_ep_week_types(cls, year: int) -> Dict[str, str]:
        """Build a {ISO date: week type} map from the verified EP calendar.

        Single source of truth: backend/knowledge_base/calendars/
        ep_calendar_{year}.json, generated from the European Parliament's own
        calendar PDF by scripts/derive_ep_calendar_from_pdf.py and verified
        against the EP's published session dates.
        """
        if year in cls._EP_WEEK_TYPE_CACHE:
            return cls._EP_WEEK_TYPE_CACHE[year]

        import json as _json
        import os as _os
        from datetime import date as _date, timedelta as _timedelta

        label = {
            "committee_week": "Committee week",
            "group_week": "Group week",
            "external_activities": "Constituency week",
            "recess": "Recess",
        }
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

        path = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.dirname(
                _os.path.abspath(__file__)))),
            "knowledge_base", "calendars", f"ep_calendar_{year}.json",
        )
        mapping: Dict[str, str] = {}
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = _json.load(handle)
        except Exception as exc:
            logger.warning("[WARN] EP week-type calendar unavailable: %s", exc)
            cls._EP_WEEK_TYPE_CACHE[year] = mapping
            return mapping

        seen = set()
        for month in data.get("months", {}).values():
            for week in month.get("weeks", []):
                dates = week.get("dates", "")
                if not dates or dates in seen:
                    continue
                seen.add(dates)
                try:
                    monday = _date.fromisoformat(dates.split(" to ")[0].strip())
                except Exception:
                    continue

                activity = week.get("activity_type", "")
                daily = week.get("daily") or {}

                if activity == "plenary_session":
                    # The PDF marks all sessions the same red. The EP holds
                    # four-day part-sessions in Strasbourg and short two-day
                    # (or one-day) sessions in Brussels, so session length is
                    # what distinguishes them.
                    session_days = week.get("session_days") or []
                    week_label = (
                        "Mini-plenary Brussels" if len(session_days) <= 2
                        else "Plenary Strasbourg"
                    )
                else:
                    week_label = label.get(activity, "Committee week")

                for offset in range(7):
                    day = monday + _timedelta(days=offset)
                    if day.year != year:
                        continue
                    if offset < 5 and daily.get(day_names[offset]):
                        mapping[day.isoformat()] = label.get(
                            daily[day_names[offset]], week_label
                        )
                    else:
                        mapping[day.isoformat()] = week_label

        cls._EP_WEEK_TYPE_CACHE[year] = mapping
        return mapping

    def _lookup_ep_week_type(self, d: "date") -> str:
        """Return the EP calendar week type for the given date.

        Values: "Plenary Strasbourg", "Mini-plenary Brussels",
        "Committee week", "Group week", "Constituency week", "Recess",
        or "Unknown".

        Reads the verified calendar JSON (see _load_ep_week_types). This used
        to be a hardcoded table of date ranges citing "memory/
        ep_calendar_2026.md" as its source, but that file does not exist and
        the table had drifted badly: it placed the September plenary in the
        wrong week, and had no entry at all for 20-24 July 2026, so that week
        fell through to a `return "Committee week"` default. That default is
        what told a subscriber on 20 July 2026 that a constituency week was a
        committee week. There is now exactly one calendar in the codebase.
        """
        try:
            week_types = self._load_ep_week_types(d.year)
            resolved = week_types.get(d.isoformat())
            if resolved:
                return resolved
            logger.warning(
                "[WARN] No EP week type for %s -- calendar JSON may be missing "
                "or out of range", d.isoformat()
            )
            return "Unknown"
        except Exception:
            return "Unknown"

    async def _fetch_today_block(self, query: str) -> Optional[str]:
        """Build a TODAY-anchored context block.

        Fallbacks (always returns something non-None when intent is detected):
          1. If DB calendar query fails     -> still return date + week type
          2. If no calendar events today    -> say "no verified events recorded"
          3. If Commission docs unavailable -> skip section silently
          4. If OEIL recent events fail     -> skip section silently

        The block is injected NEAR THE TOP of format_context_for_ai() so it
        survives the 32k truncation cap.
        """
        try:
            from datetime import datetime, date, timedelta
            try:
                from zoneinfo import ZoneInfo
                today = datetime.now(ZoneInfo("Europe/Brussels")).date()
            except Exception:
                today = datetime.utcnow().date()
        except Exception as e:
            logger.warning("[today-block] could not resolve date: %s", e)
            return None

        week_type = self._lookup_ep_week_type(today)

        lines: List[str] = []
        lines.append("=== TODAY BLOCK (current date anchor) ===")
        lines.append(f"Today is {today.strftime('%A, %d %B %Y')} ({today.isoformat()}).")
        lines.append(f"EP calendar week type: {week_type}.")
        lines.append("")

        # Section A: calendar events in the 3-day window today-1 .. today+1
        events = []
        try:
            from models.eu_calendar import EUCalendarEvent
            window_start = today - timedelta(days=1)
            window_end = today + timedelta(days=1)
            db = SessionLocal()
            try:
                events = (
                    db.query(EUCalendarEvent)
                    .filter(EUCalendarEvent.start_date >= window_start)
                    .filter(EUCalendarEvent.start_date <= window_end)
                    .filter(EUCalendarEvent.institution.in_(
                        ["EP", "COMMISSION", "COUNCIL", "EUROPEAN_COUNCIL"]
                    ))
                    .order_by(EUCalendarEvent.start_date, EUCalendarEvent.start_time)
                    .limit(40)
                    .all()
                )
            finally:
                db.close()
            if events:
                lines.append("Institutional events (today - 1 / today / today + 1, verified DB):")
                lines.append(
                    "(each event line shows its OWN location after 'in'. Two events"
                    " on the same day are in the SAME location ONLY if both lines"
                    " say the same city.)"
                )
                for e in events:
                    time_str = str(e.start_time)[:5] if e.start_time else "--:--"
                    # e.institution is a SQLAlchemy enum; str() on it yields
                    # "InstitutionEnum.COMMISSION", which leaked that internal
                    # repr straight into the model's context. Take .value.
                    inst = getattr(e.institution, "value", e.institution) or "EU"
                    committee = f" ({e.ep_committee_code})" if e.ep_committee_code else ""
                    title = (e.title or "")[:160]
                    location = _resolve_event_location(inst, title, week_type)
                    lines.append(
                        f"- {e.start_date.isoformat()} {time_str} [{inst}{committee}] "
                        f"{title} in {location}"
                    )
            else:
                lines.append("(no institutional events recorded in eu_calendar_events for today +/- 1 day)")
        except Exception as e:
            logger.warning("[today-block] calendar fetch failed: %s", e)
            lines.append("(calendar lookup unavailable; proceed with general knowledge)")

        lines.append("")

        # Section B: Commission documents in the last 48h
        try:
            from models.commission_document import CommissionDocument
            cutoff = today - timedelta(days=2)
            db = SessionLocal()
            try:
                docs = (
                    db.query(CommissionDocument)
                    .filter(CommissionDocument.document_date >= cutoff)
                    .order_by(CommissionDocument.document_date.desc())
                    .limit(12)
                    .all()
                )
            finally:
                db.close()
            if docs:
                lines.append("Commission documents in the last 48h (verified DB):")
                for d in docs:
                    dtype = getattr(d, "document_type", "DOC") or "DOC"
                    ref = getattr(d, "reference", "") or ""
                    title = (getattr(d, "title", "") or "")[:140]
                    date_str = d.document_date.isoformat() if getattr(d, "document_date", None) else "?"
                    lines.append(f"- {date_str} {dtype} {ref}: {title}")
                lines.append("")
        except Exception as e:
            logger.debug("[today-block] commission_documents lookup skipped: %s", e)
            # non-fatal

        # Section C: active OEIL procedures with a key event in the last 7 days
        try:
            from sqlalchemy import text as _sql_text
            db = SessionLocal()
            try:
                rows = db.execute(_sql_text(
                    """
                    SELECT oeil_procedure_ref, current_status, title, last_updated
                    FROM legislative_carriages
                    WHERE last_updated >= :cutoff
                      AND current_status NOT IN ('ADOPTED', 'WITHDRAWN', 'REJECTED')
                    ORDER BY last_updated DESC
                    LIMIT 15
                    """
                ), {"cutoff": today - timedelta(days=7)}).fetchall()
            finally:
                db.close()
            if rows:
                lines.append("Active OEIL procedures with a key event in the last 7 days:")
                for r in rows:
                    ref, status, title, _ = r
                    lines.append(f"- {ref} ({status}): {(title or '')[:140]}")
                lines.append("")
        except Exception as e:
            logger.debug("[today-block] legislative_carriages lookup skipped: %s", e)
            # non-fatal

        # Section D: EP plenary adopted texts in the last 5 days (verified DB).
        # Self-gating: texts_adopted only gains rows around a plenary sitting, so
        # this section is empty off-week and populated during/after a plenary.
        # Fixes the gap where "brief me on today's plenary agenda" fell back to the
        # Commissioner-diary calendar rows in Section A (audit defect D3, 10 Jul 2026).
        try:
            from sqlalchemy import text as _sql_text
            db = SessionLocal()
            try:
                ta_rows = db.execute(_sql_text(
                    """
                    SELECT ta_reference, title, procedure_ref, adoption_date
                    FROM texts_adopted
                    WHERE adoption_date >= :cutoff
                    ORDER BY adoption_date DESC
                    LIMIT 20
                    """
                ), {"cutoff": today - timedelta(days=5)}).fetchall()
            finally:
                db.close()
            if ta_rows:
                lines.append(
                    "EP plenary adopted texts in the last 5 days (verified DB -- this IS the current"
                    " plenary's voting record; use it for 'today's plenary' / 'this week's plenary' /"
                    " plenary-agenda questions):"
                )
                for r in ta_rows:
                    taref, ta_title, proc, adopted = r
                    d = adopted.date().isoformat() if hasattr(adopted, "date") else str(adopted)[:10]
                    procs = f" [{proc}]" if proc else ""
                    lines.append(f"- {d} {taref}: {(ta_title or '')[:150]}{procs}")
                lines.append("")
        except Exception as e:
            logger.debug("[today-block] texts_adopted lookup skipped: %s", e)
            # non-fatal

        # CRITICAL instruction for the model
        lines.append("CRITICAL -- when the user asks about 'today' / 'hoy' / 'avui' / 'aujourd\\'hui' / 'this week' / 'esta semana':")
        lines.append("- Anchor every claim in the TODAY BLOCK above (today's date, week type, verified events).")
        lines.append("- For 'today's plenary' / 'this week's plenary' / plenary-agenda / 'what is Parliament voting on' questions, answer from the EP plenary adopted texts section above (real TA references + procedure refs), NOT from Commissioner diary entries in the events list.")
        lines.append("- Do NOT describe previous weeks or confabulate committee meetings from past dates as if they were current.")
        lines.append("- If no verified event is listed for today, say so explicitly and point to the current EP week type.")
        lines.append("- Never invent a Council/ECOFIN/Eurogroup or committee meeting on a date not present in the TODAY BLOCK.")
        lines.append("- Respond in the SAME LANGUAGE as the user's question.")
        lines.append("=== END TODAY BLOCK ===")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # On-demand: Daily Brief block (daily_briefs DB card for a specific date)
    # Triggered by "Daily News DD/MM/YYYY" or "daily news today" queries.
    # ------------------------------------------------------------------

    DAILY_BRIEF_INTENT_PHRASES = (
        "daily news", "daily brief", "brubru brief", "noticies del dia",
        "noticias del dia", "nouvelles du jour", "notizie del giorno",
        "nieuws van vandaag",
    )

    def _detect_daily_brief_intent(self, query: str) -> bool:
        if not query:
            return False
        q = query.lower()
        for phrase in self.DAILY_BRIEF_INTENT_PHRASES:
            if phrase in q:
                return True
        return False

    def _parse_date_from_query(self, query: str) -> "Optional[date]":
        """Extract a date from a query string. Handles:
        - DD / MM / YYYY  (with any spacing around slashes)
        - DD/MM/YYYY
        - YYYY-MM-DD
        Falls back to today (Europe/Brussels) if no date found.
        """
        import re
        from datetime import date as _date
        # DD[/.]MM[/.]YYYY with optional spaces
        m = re.search(r'(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})', query)
        if m:
            try:
                return _date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            except ValueError:
                pass
        # YYYY-MM-DD
        m = re.search(r'(\d{4})-(\d{2})-(\d{2})', query)
        if m:
            try:
                return _date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                pass
        # Fall back to today
        try:
            from zoneinfo import ZoneInfo
            return __import__('datetime').datetime.now(ZoneInfo("Europe/Brussels")).date()
        except Exception:
            return __import__('datetime').date.today()

    async def _fetch_daily_brief_block(self, query: str) -> Optional[str]:
        """Fetch daily_briefs rows for the date in the query and return a context block."""
        try:
            target_date = self._parse_date_from_query(query)
            from sqlalchemy import text as _sql_text
            db = SessionLocal()
            try:
                rows = db.execute(_sql_text(
                    """
                    SELECT priority, headline, snippet, suggested_query, audience
                    FROM daily_briefs
                    WHERE brief_date = :d
                      AND (audience IS NULL OR audience = 'public')
                      AND headline NOT LIKE '[32%'
                      AND headline NOT LIKE 'OJ:%'
                      AND headline NOT LIKE '[320%'
                    ORDER BY priority ASC
                    LIMIT 12
                    """
                ), {"d": target_date}).fetchall()
            finally:
                db.close()

            if not rows:
                return None

            lines = [f"=== BRUBRU DAILY NEWS — {target_date.strftime('%d %B %Y')} ==="]
            for row in rows:
                priority, headline, snippet, suggested_query, _ = row
                lines.append(f"\n• {headline}")
                if snippet:
                    lines.append(f"  {snippet}")
                if suggested_query:
                    lines.append(f"  Suggested query: {suggested_query}")
            lines.append("\nINSTRUCTION: Use ONLY the headlines above to answer this Daily News query. "
                         "Do NOT invent or add any news items not listed here.")
            lines.append("=== END DAILY NEWS ===")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("[daily-brief-block] Failed: %s", e)
            return None

    async def _fetch_audience_brief_block(self, user_id: Optional[str]) -> Optional[str]:
        """
        For a tenant-audience user (e.g. the EFPIA pilot), inject their curated
        daily brief + tracked priority files into chat context.

        This is what makes the same content the email sends queryable in chat:
        "where are my priority files?", "what is in today's brief?", and the
        individual headline questions all become grounded. Resolves the user's
        audience from their email via services.audience.resolve_audience, then
        pulls the most recent daily_briefs rows tagged with that audience.

        Always-on for audience users (not gated on date intent) so any question
        about their portfolio is grounded. Returns None for non-audience users.
        """
        if not user_id:
            return None
        try:
            from sqlalchemy import text as _sql_text
            from services.audience import resolve_audience

            db = SessionLocal()
            try:
                urow = db.execute(
                    _sql_text("SELECT email FROM users WHERE id = :uid"),
                    {"uid": user_id},
                ).fetchone()
                email = urow[0] if urow else None
                audience = resolve_audience(email) if email else None
                if not audience:
                    return None

                rows = db.execute(
                    _sql_text(
                        """
                        SELECT brief_date, priority, headline, snippet, suggested_query
                        FROM daily_briefs
                        WHERE audience = :aud
                          AND brief_date >= (CURRENT_DATE - INTERVAL '10 days')
                        ORDER BY brief_date DESC, priority ASC
                        LIMIT 30
                        """
                    ),
                    {"aud": audience},
                ).fetchall()
            finally:
                db.close()

            if not rows:
                return None

            label = audience.upper()
            lines = [
                f"=== WHAT BRUBRU IS MONITORING FOR YOU ({label}) ===",
                "This is your own curated daily brief and tracked priority files, the same "
                "content Brubru emails you. Treat it as verified context. Use it to answer "
                "questions about your priority files, today's brief, and the headlines below. "
                "Do NOT add named people, meeting dates, or vote dates that are not written here. "
                "Do NOT invent any statistic that is not written here: case counts, death tolls, "
                "infection numbers, percentages, or monetary figures. If a headline says "
                "'confirmed cases and deaths' without a number, say the number is not on file -- "
                "never supply one. Do NOT contradict, raise, or invert any risk level or "
                "assessment stated in a headline: if it says the risk is 'very low', the risk is "
                "very low; quote risk ratings exactly as written. "
                "When a date appears here (a court judgment or ruling date, an application or "
                "entry-into-force date, a meeting or vote date), quote it EXACTLY as written: "
                "never shift, round, paraphrase, or change it by even a day. If a headline says "
                "'judgment of 21 May 2026', the date is 21 May 2026 -- do not write any other date.",
            ]
            current_date = None
            for brief_date, _priority, headline, snippet, suggested_query in rows:
                if brief_date != current_date:
                    current_date = brief_date
                    lines.append(f"\n-- Brief for {brief_date.strftime('%d %B %Y')} --")
                lines.append(f"\n• {headline}")
                if snippet:
                    lines.append(f"  {snippet}")
                if suggested_query:
                    lines.append(f"  (You can ask: {suggested_query})")
            lines.append(f"\n=== END {label} MONITORING ===")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("[audience-brief-block] Failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # On-demand: Cellar SPARQL discovery (live retrieval from
    # publications.europa.eu/webapi/rdf/sparql)
    # ------------------------------------------------------------------

    # Two-token detector:
    # - corpus token = the kind of thing the user is asking about
    # - recency token = a signal that they want a list / fresh slice (not "tell me about X")
    # Both must be present. Single-word matches are too broad (every query about a
    # specific regulation would falsely fire).
    _CELLAR_CORPUS_TOKENS = {
        # English
        "regulation", "regulations", "directive", "directives", "decision", "decisions",
        "acts ", "legislation", "official journal", " oj ", "in force",
        "proposal", "proposals", "case law", "court ruling", "judgment", "ruling",
        # Spanish
        "reglamento", "reglamentos", "directiva", "directivas", "decision",
        "decisiones", "doue", "legislacion", "propuesta", "propuestas",
        "jurisprudencia", "sentencia",
        # Catalan
        "reglament", "reglaments", "directiva", "directives", "decisio", "decisions",
        "proposta", "propostes", "jurisprudencia",
        # French
        "reglement", "reglements", "directive", "directives", "decision", "decisions",
        "joue", "legislation", "proposition", "propositions", "jurisprudence",
        # Italian
        "regolamento", "regolamenti", "direttiva", "direttive", "proposta", "proposte",
        "giurisprudenza",
        # Dutch
        "verordening", "verordeningen", "richtlijn", "richtlijnen", "voorstel",
        "rechtspraak",
    }
    _CELLAR_RECENCY_TOKENS = {
        # English
        "recent", "recently", "lately", "published", "since", " new ", "last week",
        "last month", "this month", "this year", "list ", "find ", "show me",
        "what was published", "what's been published", "what has been published",
        "in force", "from 20", "until 20", "between 20",
        # Spanish
        "reciente", "recientes", "publicado", "publicados", "ultim", "este mes",
        "este ano", "este año", "desde 20", "hasta 20",
        # Catalan
        "recent", "recents", "publicat", "publicats", "ultim", "aquest mes",
        "aquest any", "des de 20", "fins a 20",
        # French
        "recent", "recents", "publie", "publies", "dernier", "ce mois", "cette annee",
        "depuis 20",
        # Italian
        "recente", "recenti", "pubblicato", "pubblicati", "ultimo", "questo mese",
        "dal 20", "dal 19",
        # Dutch
        "recent", "onlangs", "gepubliceerd", "deze maand", "dit jaar", "sinds 20",
    }

    def _detect_cellar_discovery_intent(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect corpus-wide discovery queries.

        Returns None when the query is about a specific document (let the
        normal retrieval pipeline handle it) or unrelated. Returns a small
        intent dict otherwise: {kind: 'discovery', sectors: [...]}.

        Heuristic: must contain BOTH a corpus-token AND a recency-token.
        Specific-CELEX queries ("32016R0679") are excluded.
        """
        if not query:
            return None
        q = query.lower().strip()
        q_nfd = (
            q.replace("á", "a").replace("é", "e").replace("í", "i")
             .replace("ó", "o").replace("ú", "u").replace("ñ", "n")
             .replace("è", "e").replace("à", "a").replace("ç", "c")
        )
        # Bail out on obvious specific-doc queries — let normal retrieval handle.
        # CELEX numbers (sector + year + type-letter + serial) — rough match.
        import re as _re
        if _re.search(r"\b\d[A-Z\d]{0,1}\d{4}[A-Z]\d{4}\b", query):
            return None

        corpus_hit = next(
            (t.strip() for t in self._CELLAR_CORPUS_TOKENS if t in q or t in q_nfd),
            None,
        )
        recency_hit = next(
            (t.strip() for t in self._CELLAR_RECENCY_TOKENS if t in q or t in q_nfd),
            None,
        )
        if not (corpus_hit and recency_hit):
            return None

        sectors = ["3"]
        if any(w in q_nfd for w in ["proposal", "propuesta", "proposta", "voorstel", "vorschlag"]):
            sectors = ["5"]
        if any(w in q_nfd for w in ["case law", "judgment", "ruling", "tribunal", "court", "sentencia"]):
            sectors = ["6"]
        return {
            "kind": "discovery",
            "sectors": sectors,
            "corpus_hit": corpus_hit,
            "recency_hit": recency_hit,
        }

    async def _fetch_cellar_discovery_block(
        self,
        query: str,
        intent: Dict[str, Any],
    ) -> Optional[str]:
        """Live Cellar SPARQL fetch — surfaces 5-8 recent acts matching the
        user's discovery question. Result is a compact context block injected
        near the top of format_context_for_ai (above the 32k truncation cap).
        """
        from datetime import date as _date, timedelta as _td

        # Lazy import to avoid hard dependency on httpx for unrelated tests
        try:
            from services.api_clients.cellar_sparql_client import CellarSPARQLClient
        except Exception as e:
            logger.warning("[cellar-discovery] client import failed: %s", e)
            return None

        # 30-day default window. Specific date phrases ("since 2024", "this year")
        # are NOT yet parsed — keep behaviour simple and reliable.
        today = _date.today()
        start = today - _td(days=30)
        sectors = intent.get("sectors") or ["3"]

        try:
            async with CellarSPARQLClient(timeout=30) as client:
                rows = await client.discover_by_date_range(
                    date_from=start,
                    date_to=today,
                    sectors=sectors,
                    limit=8,
                )
        except Exception as e:
            logger.warning("[cellar-discovery] SPARQL call failed: %s", e)
            return None

        if not rows:
            return None

        sector_label = {
            "3": "EU legislation in force",
            "5": "Commission proposals",
            "6": "EU case law",
        }.get(sectors[0], "EU acts")

        lines = [
            "=== CELLAR DISCOVERY (live SPARQL, last 30 days) ===",
            f"Source: publications.europa.eu/webapi/rdf/sparql",
            f"Filter: {sector_label} (CELEX sector {sectors[0]}), {start.isoformat()} -> {today.isoformat()}",
            "",
            "Recent matching acts (cite verbatim — these are LIVE, verified by Cellar):",
        ]
        for r in rows[:8]:
            celex = r.get("celex") or "?"
            d = r.get("date") or "?"
            title = (r.get("title") or "").strip()
            if len(title) > 180:
                title = title[:177] + "..."
            url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
            lines.append(f"- [{celex}] ({d}) {title}")
            lines.append(f"    {url}")
        lines.append("")
        lines.append("INSTRUCTIONS:")
        lines.append("- Cite each act by its CELEX number and link, never invent identifiers.")
        lines.append("- If the user asked about a topic not represented above, say so plainly.")
        lines.append("- Respond in the SAME LANGUAGE as the user's question.")
        lines.append("=== END CELLAR DISCOVERY ===")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # On-demand: EP committee meeting transcripts (AI-transcribed)
    # ------------------------------------------------------------------

    # Known EP committee codes for direct match in queries
    EP_COMMITTEE_CODES = {
        "AFCO", "AFET", "AGRI", "BUDG", "CONT", "CULT", "DEVE", "DROI", "ECON",
        "EMPL", "ENVI", "FEMM", "FISC", "IMCO", "INTA", "ITRE", "JURI", "LIBE",
        "PECH", "PETI", "REGI", "SEDE", "TRAN", "PANA", "SANT",
        "EUDS", "HOUS",  # term 10 additions
    }

    def _detect_committee_transcript_intent(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect queries about EP committee meeting transcripts.

        Real users don't type "2025/0429(COD)". They say "ePrivacy Directive
        extension" or "the CSAM file". Accept three entry paths:

          1. Explicit committee code (LIBE, ENVI, ...) + transcript phrase or
             verbatim word ("said", "discussed").
          2. Procedure alias match (resolved via procedure_alias_resolver) +
             transcript phrase or verbatim word — committee code inferred from
             the alias, so the user doesn't need to know it.
          3. Formal procedure_ref like "2025/0429(COD)" anywhere in the query.

        Returns a dict with at least one of {committee_code, procedure_ref}
        populated, plus optional topic_keywords and date_hint; or None.
        """
        if not query:
            return None

        import re as _re
        import unicodedata as _ud

        def _strip_accents(s: str) -> str:
            return "".join(
                c for c in _ud.normalize("NFKD", s) if not _ud.combining(c)
            )

        q = query.lower()
        q_norm = _strip_accents(q)
        phrases_norm = [_strip_accents(p) for p in self.COMMITTEE_TRANSCRIPT_INTENT_PHRASES]
        phrase_match = any(p in q_norm for p in phrases_norm)

        code_match = None
        for code in self.EP_COMMITTEE_CODES:
            if _re.search(rf"\b{code.lower()}\b", q):
                code_match = code
                break

        # Verbatim/speech words suggest transcript retrieval even without an explicit "committee" phrase
        verbatim_words = (
            "said", "say", "says", "saying",
            "discussed", "discuss", "discussing", "discussion",
            "heard", "hear", "hearing",
            "debated", "debate", "debating",
            "exchange of views", "exchange",
            "asked", "ask", "asking",
            "told", "tell", "tells", "telling",
            "replied", "reply", "replies",
            "stated", "state", "stating",
            "argued", "argue", "arguing",
            "spoke", "speak", "speaking",
            "mentioned", "mention", "mentions",
            "addressed", "address", "addresses",
            "talked", "talk", "talks", "talking",
            "raised", "raise", "raises",
        )
        has_verbatim = any(w in q for w in verbatim_words)
        has_transcript_signal = phrase_match or has_verbatim

        # Resolve a procedure alias (e.g. "ePrivacy Directive extension" -> "2025/0429(COD)")
        proc_from_alias: Optional[Dict[str, Any]] = None
        try:
            from services.parsers.procedure_alias_resolver import (
                resolve_procedure, extract_topic_keywords,
            )
            proc_from_alias = resolve_procedure(query)
            topic_keywords = extract_topic_keywords(query)
        except Exception as exc:
            logger.debug("[committee-transcript] alias resolver unavailable: %s", exc)
            topic_keywords = []

        # Extract formal procedure_ref directly from query (belt-and-braces)
        proc_match = _re.search(r"\d{4}/\d{4}\s*\([A-Z]{2,4}\)", query)
        procedure_ref = proc_match.group(0) if proc_match else None
        if not procedure_ref and proc_from_alias:
            procedure_ref = proc_from_alias.get("procedure_ref")

        # If alias gave us a lead committee and the user didn't name one, use it
        if not code_match and proc_from_alias:
            lead = (proc_from_alias.get("lead_committee") or "").split("-")[0].strip()
            if lead in self.EP_COMMITTEE_CODES:
                code_match = lead

        # Decision: we need either (committee code + transcript signal) OR
        # (procedure alias/ref + transcript signal) to fire this path.
        has_procedure_signal = bool(procedure_ref) or bool(proc_from_alias)

        if not has_transcript_signal:
            return None
        if not code_match and not has_procedure_signal:
            return None

        date_hint = self._detect_plenary_debate_intent(query)  # reuse parser

        return {
            "committee_code": code_match,         # may be None if procedure-only query
            "procedure_ref": procedure_ref,       # formal COD/NLE/CNS ref if any
            "procedure_title": (proc_from_alias or {}).get("title"),
            "matched_alias": (proc_from_alias or {}).get("matched_alias"),
            "topic_keywords": topic_keywords,
            "date_hint": date_hint,
        }

    # EP question references look like "E-004916/2025" or "P-001237/2026",
    # and users write them with or without the dash.
    _PQ_REF_RE = re.compile(r"\b([EPOep])[-\s]?(\d{6})\s*/\s*(\d{4})\b")
    _PQ_TOPIC_RE = re.compile(
        r"parliamentary question|written question|oral question|question for written"
        r"|pregunta parlament|question parlementaire|interrogazione|parlementaire vraag",
        re.IGNORECASE,
    )

    def _fetch_parliamentary_questions_block(self, user_message: str) -> Optional[str]:
        """EP written and oral questions, by reference or by topic.

        Added 7 August 2026. Brubru has held these all along and Parliamentary
        Questions is a My EU Bubble sub-tab, but nothing ever put them in the
        chat context. Asked what E-004916/2025 was about, chat produced a
        confident summary of an entirely different question and attributed it
        to a document reference that does not exist for that file. The subject
        line and full text were sitting in the database the whole time.

        Deliberately synchronous: it is one indexed lookup, and the callers of
        the other reference-data blocks are synchronous too.
        """
        if not user_message:
            return None

        refs = self._PQ_REF_RE.findall(user_message)
        wants_topic = bool(self._PQ_TOPIC_RE.search(user_message))
        if not refs and not wants_topic:
            return None

        try:
            from sqlalchemy import text as _sql_text
            db = SessionLocal()
            try:
                if refs:
                    wanted = [f"{p.upper()}-{num}/{yr}" for p, num, yr in refs][:3]
                    rows = db.execute(_sql_text(
                        """
                        SELECT question_reference, question_type, subject,
                               text_question, text_answer, submitted_date,
                               answered_date, asking_mep_names,
                               answering_commissioner, source_url, answer_url
                        FROM parliamentary_questions
                        WHERE question_reference = ANY(:refs)
                        LIMIT 3
                        """
                    ), {"refs": wanted}).fetchall()
                else:
                    # Topic query: strip the trigger words so the ILIKE runs on
                    # the subject matter rather than on "parliamentary question".
                    topic = self._PQ_TOPIC_RE.sub(" ", user_message)
                    topic = re.sub(r"[^\w\s]", " ", topic)
                    terms = [w for w in topic.split() if len(w) > 4][:4]
                    if not terms:
                        return None
                    rows = db.execute(_sql_text(
                        """
                        SELECT question_reference, question_type, subject,
                               text_question, text_answer, submitted_date,
                               answered_date, asking_mep_names,
                               answering_commissioner, source_url, answer_url
                        FROM parliamentary_questions
                        WHERE subject ILIKE ANY(:pats)
                        ORDER BY submitted_date DESC NULLS LAST
                        LIMIT 4
                        """
                    ), {"pats": [f"%{t}%" for t in terms]}).fetchall()
            finally:
                db.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("[PQ] parliamentary question lookup failed: %s", e)
            return None

        if not rows:
            # Say nothing rather than nothing-found: an explicit "not on file"
            # line stops the model reaching for training memory to fill in.
            if refs:
                asked = ", ".join(f"{p.upper()}-{n}/{y}" for p, n, y in refs[:3])
                return (
                    "[EP PARLIAMENTARY QUESTIONS]\n"
                    f"{asked}: NOT on file in Brubru's record. Do not describe its "
                    "contents; point the user to europarl.europa.eu/doceo and to "
                    "Parliamentary Questions (My EU Bubble).\n"
                )
            return None

        out = ["[EP PARLIAMENTARY QUESTIONS]"]
        for r in rows:
            (ref, qtype, subject, qtext, atext, submitted, answered,
             askers, commissioner, src, ans_url) = r
            out.append(f"- REFERENCE: {ref}  TYPE: {qtype or 'written'}")
            out.append(f"  SUBJECT: {(subject or '').strip()[:300]}")
            if askers:
                names = askers if isinstance(askers, str) else ", ".join(askers)
                out.append(f"  TABLED BY: {names[:220]}")
            if submitted:
                out.append(f"  SUBMITTED: {submitted}")
            if qtext:
                body = re.sub(r"\s+", " ", str(qtext)).strip()
                out.append(f"  QUESTION TEXT: {body[:900]}")
            if atext:
                ans = re.sub(r"\s+", " ", str(atext)).strip()
                out.append(f"  ANSWER ({commissioner or 'Commission'}"
                           f"{', ' + str(answered) if answered else ''}): {ans[:700]}")
            elif answered is None:
                out.append("  ANSWER: not yet answered on Brubru's record.")
            if src:
                out.append(f"  SOURCE: {src}")
            if ans_url:
                out.append(f"  ANSWER URL: {ans_url}")
        out.append(
            "Report ONLY what these rows contain. Do not infer the subject of a "
            "question from its reference number, and do not cite a document "
            "reference that is not printed above."
        )
        return "\n".join(out) + "\n"

    # Named competitors, and the comparison verbs that pull the model into a
    # two-column table about someone else's product.
    _COMPETITOR_RE = re.compile(
        r"\b(politico(?:\s+pro)?|contexte|agence\s+europe|euractiv(?:\s+pro)?|mlex|"
        r"dods|vote\s?watch|eubusiness|borderlex|montel|argus\s+media|"
        r"lobbyfacts|integrity\s?watch)\b",
        re.IGNORECASE,
    )
    _COMPARE_RE = re.compile(
        r"compare|comparison|versus|\bvs\b|better than|instead of|different from|"
        r"can't get from|cannot get from|why (?:use|choose)|worth switching",
        re.IGNORECASE,
    )

    def _build_competitor_guard_block(self, user_message: str) -> Optional[str]:
        """Stop chat asserting what a rival product does not do.

        Asked what Brubru offers that Politico Pro does not, chat produced a
        two-column table whose right-hand column read "no amendment drafting
        tool", "no API for machine-readable data", "limited access to primary
        documents", each tagged with a citation marker as though Brubru's
        records supported it. Brubru holds no data on any competitor's feature
        set, so those are unsourceable claims about a named third party.

        The system prompt was given this rule twice, in progressively blunter
        wording, and the comparison table came back both times: the pull of the
        question's format beat an instruction sitting thousands of tokens
        earlier. A context block sits next to the question instead, which is
        the position that has actually changed behaviour elsewhere in this
        file.
        """
        if not user_message:
            return None
        who = self._COMPETITOR_RE.search(user_message)
        if not who or not self._COMPARE_RE.search(user_message):
            return None
        name = who.group(1)
        return (
            "[COMPARISON REQUEST -- ANSWER CONSTRAINT]\n"
            f"The user named {name}. Brubru holds NO data on that product, so "
            "you cannot describe what it does, does not do, or cannot match.\n"
            "- Do NOT build a two-column table.\n"
            "- Do NOT write any column, heading, bullet or clause about "
            f"{name}'s capabilities, and never attach a citation marker to one.\n"
            "- DO give a plain list of what Brubru does, named by feature, and "
            "close by inviting the user to compare that against whatever they "
            "use today. Their tool, their judgement.\n"
        )

    _AMDT_INTENT_RE = re.compile(
        r"amendment|amendements|esmen|enmienda|emendament|amendementen|\bPE\s?\d{3}",
        re.IGNORECASE,
    )

    def _fetch_amendment_documents_block(self, user_message: str) -> Optional[str]:
        """Committee amendment documents: PE reference, count, committee, link.

        Added 7 August 2026. amendment_documents held 1,326 rows and chat could
        not read one, so it invented the two things professionals actually act
        on. Asked how many amendments were tabled on 2025/0380(COD) it answered
        "111" when the record says 101, and asked for the PE reference on
        2025/0312(COD) it produced "PE 785", which is not even a well-formed PE
        number, with a footnote marker as though it were sourced.

        The system prompt already forbids inventing PE numbers and tallies. It
        was being ignored because the real values were nowhere in context; a
        rule cannot compete with an empty context.
        """
        if not user_message or not self._AMDT_INTENT_RE.search(user_message):
            return None

        proc = re.search(r"\b(\d{4}/\d{4}\([A-Z]{3}\))", user_message)
        pe = re.search(r"\bPE\s?(\d{3})[.,]?(\d{3})\b", user_message, re.IGNORECASE)
        if not proc and not pe:
            return None

        try:
            from sqlalchemy import text as _sql_text
            db = SessionLocal()
            try:
                if proc:
                    rows = db.execute(_sql_text(
                        """
                        SELECT procedure_reference, committee_code, pe_reference,
                               document_type, document_date, rapporteur_name,
                               total_amendments, doceo_url, status
                        FROM amendment_documents
                        WHERE procedure_reference = :p
                        ORDER BY document_date DESC NULLS LAST LIMIT 8
                        """
                    ), {"p": proc.group(1)}).fetchall()
                else:
                    rows = db.execute(_sql_text(
                        """
                        SELECT procedure_reference, committee_code, pe_reference,
                               document_type, document_date, rapporteur_name,
                               total_amendments, doceo_url, status
                        FROM amendment_documents
                        WHERE replace(replace(pe_reference,'.',''),' ','') = :pe
                        LIMIT 4
                        """
                    ), {"pe": f"PE{pe.group(1)}{pe.group(2)}"}).fetchall()
            finally:
                db.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("[AMDT] amendment document lookup failed: %s", e)
            return None

        what = proc.group(1) if proc else f"PE{pe.group(1)}.{pe.group(2)}"
        if not rows:
            return (
                "[COMMITTEE AMENDMENT DOCUMENTS]\n"
                f"No amendment document on file for {what}. Do NOT state a number "
                "of amendments and do NOT produce a PE reference: both must come "
                "from the record. Say the document is not on file and point to "
                "Amendments (My EU Bubble) and the committee page.\n"
            )

        # Spelled out because the counts are NOT commensurable. A file usually
        # carries a draft report (the rapporteur's own amendments) alongside the
        # AM document (amendments tabled by other MEPs). For 2025/0380(COD)
        # that is 10 and 101, and the file-level total of 111 that Position
        # Analysis reports is the two added together.
        types = {"AM": "Amendments tabled in committee by MEPs",
                 "AD": "Amendments in another committee's opinion",
                 "PR": "Rapporteur's own amendments in the draft report"}
        out = ["[COMMITTEE AMENDMENT DOCUMENTS]"]

        # State the answer outright, because TWO Brubru blocks report a figure
        # under the words "amendments tabled" and they disagree. This block
        # counts the AM document (101 for 2025/0380(COD)); the Position
        # Analysis block counts every amendment document on the file and
        # reports 111. Neither is wrong, but a user asking "how many amendments
        # were tabled in committee" wants the AM figure, and without a stated
        # answer the model picks whichever it read last or reconciles the two
        # mid-sentence.
        am = [r for r in rows if (r[3] or "") == "AM"]
        if am:
            head = am[0]
            out.append(
                f"ANSWER TO 'how many amendments were tabled in committee': "
                f"{head[6]} in {head[1] or 'committee'} "
                f"({head[2] or 'no PE reference'}). Lead with this figure. If a "
                "Position Analysis block also gives a file-level total, that "
                "total counts every amendment document on the file including "
                "the draft report, so name it as the file-level total rather "
                "than contradicting or averaging the two."
            )
        for pref, cttee, peref, dtype, date, rapp, total, url, status in rows:
            bits = [f"- {pref}", f"{types.get(dtype, dtype or 'document')}"]
            if cttee:
                bits.append(f"in {cttee}")
            if peref:
                bits.append(f"| PE reference {peref}")
            if total is not None:
                bits.append(f"| {total} amendments")
            if date:
                bits.append(f"| {str(date)[:10]}")
            if rapp:
                bits.append(f"| rapporteur {rapp}")
            out.append(" ".join(bits))
            if url:
                out.append(f"    {url}")
            if status and status != "parsed":
                out.append(f"    (parse status: {status}, the count may be incomplete)")
        out.append(
            "Amendment counts and PE references above are the record. Quote them "
            "exactly, INCLUDING THE PUNCTUATION: write PE785.330, never "
            "'PE 785 330', because a reference with spaces substituted for the "
            "full stop finds nothing in the Parliament's document search and "
            "the user cannot look it up. Never round, adjust or invent either. "
            "NEVER ADD THE COUNTS "
            "TOGETHER: each line counts a different document, and 'amendments "
            "tabled in committee' means the AM line alone. Report each document "
            "on its own line with its committee, and give the doceo link where "
            "one is shown so the user can open the document."
        )
        return "\n".join(out) + "\n"

    _LOBBY_INTENT_RE = re.compile(
        r"lobb(?:y|ied|yist|ying)|transparency register|who met|which organisations? "
        r"(?:has|have|did)|meetings? with|reuni(?:ó|o)n(?:s|es)? amb|incontr",
        re.IGNORECASE,
    )

    def _fetch_lobby_meetings_block(self, user_message: str) -> Optional[str]:
        """Transparency Register meetings between MEPs and organisations.

        Added 7 August 2026. Lobby Meetings is a My EU Bubble sub-tab and the
        chat context builder could not read the table, so "which organisations
        has MEP X met" was answered by naming the EU institutions themselves as
        the lobbyists and then asserting nothing else was on record. The real
        meetings were on file.

        484 of the 1,245 rows carry the literal string "Past meetings" in
        mep_name: a scraped section header captured as a person, with the
        meeting subject concatenated onto the organisation. Those rows are
        excluded here rather than shown, on the same principle as the seed
        fixtures: a production-shared table needs its garbage filterable at
        query time. The scraper itself still needs fixing.
        """
        if not user_message or not self._LOBBY_INTENT_RE.search(user_message):
            return None

        proc = re.search(r"\b(\d{4}/\d{4}\([A-Z]{3}\))", user_message)
        stop = {"MEP", "MEPs", "EU", "European", "Parliament", "Commission",
                "Council", "Which", "Who", "What", "Register", "Transparency"}
        names = [w.strip(".,?!'\"") for w in re.findall(r"\b[A-Z][\w’'-]{2,}", user_message)]
        names = [n for n in names if n not in stop]
        if not proc and not names:
            return None

        try:
            from sqlalchemy import text as _sql_text
            db = SessionLocal()
            try:
                rows = []
                if proc:
                    rows = db.execute(_sql_text(
                        """
                        SELECT mep_name, role, committee, meeting_date,
                               organisation, transparency_register_id, procedure_ref
                        FROM mep_lobby_meetings
                        WHERE procedure_ref = :p AND mep_name <> 'Past meetings'
                        ORDER BY meeting_date DESC NULLS LAST LIMIT 12
                        """
                    ), {"p": proc.group(1)}).fetchall()
                if not rows and names:
                    rows = db.execute(_sql_text(
                        """
                        SELECT mep_name, role, committee, meeting_date,
                               organisation, transparency_register_id, procedure_ref
                        FROM mep_lobby_meetings
                        WHERE mep_name <> 'Past meetings'
                          AND (mep_name ILIKE ANY(:pats)
                               OR organisation ILIKE ANY(:pats))
                        ORDER BY meeting_date DESC NULLS LAST LIMIT 12
                        """
                    ), {"pats": [f"%{n}%" for n in names[:4]]}).fetchall()
            finally:
                db.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("[LOBBY] meeting lookup failed: %s", e)
            return None

        who = proc.group(1) if proc else ", ".join(names[:3])
        if not rows:
            return (
                "[TRANSPARENCY REGISTER MEETINGS]\n"
                f"No registered meeting on file for {who}. Say so plainly. Do NOT "
                "name the Commission, the Parliament or any institution as a "
                "lobbyist, and do NOT infer meetings from a file's subject "
                "matter. Point to Lobby Meetings (My EU Bubble) and to the "
                "Transparency Register.\n"
            )

        out = ["[TRANSPARENCY REGISTER MEETINGS]"]
        for mep, role, cttee, date, org, trid, pref in rows:
            bits = [f"- {mep}"]
            if role:
                bits.append(f"({role}{', ' + cttee if cttee else ''})")
            bits.append(f"met {org}")
            if trid:
                bits.append(f"[TR {trid}]")
            if date:
                bits.append(f"on {str(date)[:10]}")
            if pref:
                bits.append(f"re {pref}")
            out.append(" ".join(bits))
        out.append(
            "These are the registered meetings on file. Organisations listed are "
            "the outside parties; EU institutions are not lobbyists. Do not add "
            "meetings that are not listed above."
        )
        return "\n".join(out) + "\n"

    _VOTE_INTENT_RE = re.compile(
        r"\bhow did\b.*\bvote\b|\bvoted?\b.*\b(for|against|in favour)\b"
        r"|voting record|roll[- ]call|com(?:o|e) (?:ha )?vot|c[oó]mo vot[oó]|ha votat",
        re.IGNORECASE,
    )

    def _fetch_roll_call_block(self, user_message: str) -> Optional[str]:
        """How a named MEP actually voted, from ep_roll_call_records.

        Added 7 August 2026 after the individual-vote fabrication. Without this
        the model answered from the political group's line, which is right for
        the ~90% who follow the whip and confidently wrong for the rebels, who
        are the only interesting case. It also manufactured the evidence: one
        answer quoted a written explanation of vote that does not exist.

        Names in ep_roll_call_records are SURNAMES only ("Casa", "Andrews"), so
        the surname is matched rather than the full name the user types.
        """
        if not user_message or not self._VOTE_INTENT_RE.search(user_message):
            return None

        # Capitalised tokens are the candidate surnames. Strip the honorifics
        # and institution words that are also capitalised.
        stop = {"MEP", "EP", "European", "Parliament", "Commission", "Council",
                "EU", "How", "What", "Did", "The", "Regulation", "Directive",
                "Act", "Resolution", "Report", "Group", "Member"}
        cands = [w.strip(".,?!'\"") for w in re.findall(r"\b[A-Z][\w’'-]{2,}", user_message)]
        cands = [c for c in cands if c not in stop][-3:]
        if not cands:
            return None

        # Topic words locate the vote itself. The candidate surnames must be
        # excluded or they end up in the title match: "MEP David Casa" put
        # "David" in the topic, and no vote title contains it, so an ILIKE ALL
        # matched nothing at all.
        _names_lower = {c.lower() for c in cands}
        _noise = {"votes", "voted", "vote", "resolution", "parliament", "european",
                  "how", "did", "the", "on", "of", "mep", "meps", "and", "for"}
        # Three characters, not five. The old threshold dropped "tax", which is
        # the only word separating "The 28th Regime: a new legal framework for
        # innovative companies" from "Feasibility of a 28th TAX regime", two
        # different files with different votes. Losing it sent the answer to the
        # wrong roll-call.
        topic = [w for w in re.sub(r"[^\w\s]", " ", user_message).split()
                 if len(w) >= 3
                 and w.lower() not in _noise
                 and w.lower() not in _names_lower]
        if not topic:
            return None

        try:
            from sqlalchemy import text as _sql_text
            db = SessionLocal()
            try:
                # ONE vote, not several. A single file carries many roll-calls
                # (the resolution plus each amendment), and matching them all
                # returned the same MEP as both FOR and AGAINST with a tally
                # borrowed from a different vote.
                # Score candidates on how many topic words the title carries,
                # rather than taking whichever vote has the most MEP records.
                # Record count picked the biggest roll-call on a merely similar
                # title, which is how "28th tax regime" was answered with the
                # numbers from the separate 28th Regime company-law file.
                cand_votes = db.execute(_sql_text(
                    """
                    SELECT v.id, v.title, v.ta_reference, v.procedure_ref,
                           v.vote_date, v.level,
                           (SELECT count(*) FROM ep_roll_call_records x
                             WHERE x.vote_id = v.id) AS n
                    FROM ep_roll_call_votes v
                    WHERE v.title ILIKE ANY(:topic)
                    ORDER BY v.vote_date DESC NULLS LAST
                    LIMIT 40
                    """
                ), {"topic": [f"%{t}%" for t in topic[:6]]}).fetchall()
                if not cand_votes:
                    return None
                terms = [t.lower() for t in topic[:6]]

                def _rank(v):
                    tl = (v[1] or "").lower()
                    hits = sum(1 for t in terms if t in tl)
                    # Plenary before committee: "how did X vote" means the
                    # house vote unless the user says committee.
                    plenary = 1 if (v[5] or "") == "plenary" else 0
                    return (hits, plenary, v[6] or 0)

                vote = max(cand_votes, key=_rank)
                vote_id = vote[0]
                # Surnames come last, so try the last capitalised token first and
                # stop at the first that actually appears in this roll-call.
                # Otherwise "MEP David Casa" also matched an unrelated MEP whose
                # surname is David.
                rows = []
                for cand in reversed(cands):
                    rows = db.execute(_sql_text(
                        """
                        SELECT r.mep_name, r.political_group, r.vote_choice
                        FROM ep_roll_call_records r
                        WHERE r.vote_id = :vid AND r.mep_name = :name
                        """
                    ), {"vid": vote_id, "name": cand}).fetchall()
                    if rows:
                        break
                tally = db.execute(_sql_text(
                    """
                    SELECT vote_choice, count(*) FROM ep_roll_call_records
                    WHERE vote_id = :vid GROUP BY vote_choice
                    """
                ), {"vid": vote_id}).fetchall()
            finally:
                db.close()
        except Exception as e:  # noqa: BLE001
            logger.warning("[ROLLCALL] lookup failed: %s", e)
            return None
        title, ta, proc, when = vote[1], vote[2], vote[3], vote[4]

        if not rows:
            return (
                "[EP ROLL-CALL VOTE]\n"
                f"No roll-call record on file for {', '.join(cands)} on this vote. "
                "Do NOT infer how they voted from their political group's position, "
                "and do NOT quote an explanation of vote. Say the individual record "
                "is not on file and point to the Votes tab (My EU Bubble) and to "
                "europarl.europa.eu/plenary/en/votes.html.\n"
            )

        choice = {"+": "FOR", "-": "AGAINST", "0": "ABSTENTION"}
        out = ["[EP ROLL-CALL VOTE]"]
        out.append(f"VOTE: {(title or '')[:180]}")
        if ta:
            out.append(f"ADOPTED TEXT: {ta}")
        if proc:
            out.append(f"PROCEDURE: {proc}")
        if when:
            out.append(f"DATE: {when}")
        if tally:
            counts = {c: n for c, n in tally}
            out.append(
                f"TALLY: {counts.get('+', 0)} for / {counts.get('-', 0)} against / "
                f"{counts.get('0', 0)} abstentions")
        out.append("INDIVIDUAL RECORDS (authoritative, from the roll-call):")
        for name, grp, ch in rows:
            out.append(f"- {name} ({grp or 'n/a'}): {choice.get(ch, ch)}")
        out.append(
            "These are the recorded votes. An MEP can vote against their own "
            "group, so never substitute the group's line for the record above, "
            "and never invent an explanation of vote."
        )
        return "\n".join(out) + "\n"

    async def _fetch_committee_transcript_block(
        self,
        intent: Dict[str, Any],
    ) -> Optional[str]:
        """Fetch a committee-meeting transcript for the chatbot context.

        Retrieval cascade (each step narrows less than the previous one):
          A. COMPLETED + committee_code + procedure_ref + date window
          B. COMPLETED + committee_code + procedure_ref
          C. COMPLETED + committee_code + keyword ILIKE on title / agenda / text
          D. COMPLETED + keyword ILIKE on title / agenda / text (no committee filter)
          E. COMPLETED + committee_code (most recent)
          F. PENDING with video_url — transcribe on demand

        Committee code may be None (procedure-only queries). Procedure_ref may
        also be None (pure keyword queries).
        """
        if not intent:
            return None
        if not intent.get("committee_code") and not intent.get("procedure_ref") \
                and not intent.get("topic_keywords"):
            return None

        try:
            from core.database import SessionLocal
            from models.committee_meeting_transcript import (
                CommitteeMeetingTranscript, TranscriptStatusEnum,
            )
            from services.committee_transcription_service import (
                get_committee_transcription_service,
            )
            from sqlalchemy import or_, cast, String as SAString
        except Exception as exc:
            logger.warning("[committee-transcript] Import failed: %s", exc)
            return None

        code = intent.get("committee_code")
        proc_ref = intent.get("procedure_ref")
        date_hint = intent.get("date_hint")
        topic_keywords = intent.get("topic_keywords") or []

        # Only use higher-signal keywords (drop aliases that are already baked
        # into proc_ref) to avoid polluting ILIKE searches with common words.
        signal_keywords = [k for k in topic_keywords if len(k) >= 5][:5]

        session = SessionLocal()
        try:
            Completed = CommitteeMeetingTranscript.status == TranscriptStatusEnum.COMPLETED

            # Seed/test transcripts must never surface in production chatbot
            # context — they contain synthetic facts (fabricated vote numbers,
            # T-document IDs, rapporteur statements) inserted to verify the
            # retrieval pipeline, not real Whisper output from real meetings.
            # Filter by event_id / title markers.
            from sqlalchemy import not_
            _NotSeed = not_(or_(
                CommitteeMeetingTranscript.event_id.ilike('%seed%'),
                CommitteeMeetingTranscript.event_id.ilike('%test%'),
                CommitteeMeetingTranscript.title.ilike('%seed test transcript%'),
                CommitteeMeetingTranscript.title.ilike('%synthetic%'),
            ))

            def _committee_filter(query):
                if code:
                    return query.filter(
                        CommitteeMeetingTranscript.committee_code.ilike(f"%{code}%")
                    )
                return query

            def _date_filter(query):
                if not date_hint:
                    return query
                from datetime import datetime as _dt, timedelta
                window_start = _dt.combine(date_hint - timedelta(days=7), _dt.min.time())
                window_end = _dt.combine(date_hint + timedelta(days=7), _dt.max.time())
                return query.filter(
                    CommitteeMeetingTranscript.meeting_date >= window_start,
                    CommitteeMeetingTranscript.meeting_date <= window_end,
                )

            def _keyword_filter(query, keywords):
                if not keywords:
                    return query
                clauses = []
                for kw in keywords:
                    like = f"%{kw}%"
                    clauses.append(CommitteeMeetingTranscript.title.ilike(like))
                    clauses.append(CommitteeMeetingTranscript.transcript_text.ilike(like))
                    clauses.append(
                        cast(CommitteeMeetingTranscript.agenda_items, SAString).ilike(like)
                    )
                return query.filter(or_(*clauses))

            base = session.query(CommitteeMeetingTranscript).filter(Completed).filter(_NotSeed)

            # A. code + proc_ref + date
            transcript = None
            if code and proc_ref:
                q = _committee_filter(base)
                q = q.filter(CommitteeMeetingTranscript.related_procedure_refs.any(proc_ref))
                q = _date_filter(q)
                transcript = q.order_by(CommitteeMeetingTranscript.meeting_date.desc()).first()

                # B. code + proc_ref (drop date)
                if not transcript:
                    q = _committee_filter(base).filter(
                        CommitteeMeetingTranscript.related_procedure_refs.any(proc_ref)
                    )
                    transcript = q.order_by(CommitteeMeetingTranscript.meeting_date.desc()).first()

            # Procedure-only query (no committee): try proc_ref across all committees
            if not transcript and proc_ref and not code:
                q = base.filter(
                    CommitteeMeetingTranscript.related_procedure_refs.any(proc_ref)
                )
                transcript = q.order_by(CommitteeMeetingTranscript.meeting_date.desc()).first()

            # C. code + keyword
            if not transcript and code and signal_keywords:
                q = _keyword_filter(_committee_filter(base), signal_keywords)
                transcript = q.order_by(CommitteeMeetingTranscript.meeting_date.desc()).first()

            # D. keyword only (no committee filter)
            if not transcript and signal_keywords:
                q = _keyword_filter(base, signal_keywords)
                transcript = q.order_by(CommitteeMeetingTranscript.meeting_date.desc()).first()

            # E. code only, most recent
            if not transcript and code:
                q = _committee_filter(base)
                transcript = q.order_by(CommitteeMeetingTranscript.meeting_date.desc()).first()

            # ── Step 2: On-demand transcription ─────────────────────────
            if not transcript:
                pending_base = session.query(CommitteeMeetingTranscript).filter(
                    CommitteeMeetingTranscript.status.in_([
                        TranscriptStatusEnum.PENDING,
                        TranscriptStatusEnum.FAILED,
                    ]),
                    CommitteeMeetingTranscript.video_url.isnot(None),
                )
                pq = _committee_filter(pending_base)
                if proc_ref:
                    pq = pq.filter(
                        CommitteeMeetingTranscript.related_procedure_refs.any(proc_ref)
                    )
                pending = pq.order_by(
                    CommitteeMeetingTranscript.meeting_date.desc()
                ).first()
                if not pending and signal_keywords:
                    pending = _keyword_filter(
                        _committee_filter(pending_base), signal_keywords
                    ).order_by(
                        CommitteeMeetingTranscript.meeting_date.desc()
                    ).first()

                if not pending:
                    logger.info(
                        "[committee-transcript] No COMPLETED or PENDING transcript for code=%s ref=%s",
                        code, proc_ref,
                    )
                    return None

                logger.info(
                    "[committee-transcript] On-demand transcription: %s %s (cost ~$0.006/min)",
                    pending.committee_code, pending.meeting_date,
                )
                pending.status = TranscriptStatusEnum.TRANSCRIBING
                session.commit()

                svc = get_committee_transcription_service()
                meeting_date = pending.meeting_date
                if hasattr(meeting_date, "date"):
                    md_arg = meeting_date.date()
                else:
                    md_arg = meeting_date
                result = await svc.transcribe_meeting(
                    video_url=pending.video_url,
                    committee_code=pending.committee_code,
                    meeting_date=md_arg,
                    title=pending.title,
                    agenda_items=pending.agenda_items or [],
                )

                for k, v in result.items():
                    if hasattr(pending, k):
                        setattr(pending, k, v)
                if result.get("status") == "completed":
                    from datetime import datetime as _dt
                    pending.transcribed_at = _dt.utcnow()

                session.commit()
                session.refresh(pending)

                if pending.status != TranscriptStatusEnum.COMPLETED:
                    logger.warning(
                        "[committee-transcript] On-demand transcription failed for %s: %s",
                        pending.event_id, pending.error_message,
                    )
                    return None
                transcript = pending

            # ── Step 3: Format for context injection ────────────────────
            svc = get_committee_transcription_service()
            meeting_date = transcript.meeting_date
            if hasattr(meeting_date, "date"):
                meeting_date = meeting_date.date()
            block = svc.format_transcript_for_context(
                transcript_text=transcript.transcript_text or "",
                committee_code=transcript.committee_code,
                meeting_date=meeting_date,
                title=transcript.title,
                agenda_items=transcript.agenda_items or [],
                procedure_ref=proc_ref,
                max_chars=4000,
            )

            header = "COMMITTEE TRANSCRIPT (live — AI-transcribed from EP Multimedia):"
            return f"{header}\n{block}"

        finally:
            session.close()

    # ------------------------------------------------------------------
    # On-demand: stakeholder feedback on EC public consultations
    # ------------------------------------------------------------------

    CONSULTATION_FEEDBACK_INTENT_PHRASES = (
        "feedback on", "feedback to", "feedback from", "feedback on the consultation",
        "stakeholder feedback", "stakeholder responses", "stakeholder contributions",
        "what did stakeholders say", "what stakeholders said",
        "contributions to", "contributions on the consultation",
        "comments on the consultation", "comments to the consultation",
        "responses to the consultation", "responses on the consultation",
        "have your say feedback", "have your say contributions",
        # FR
        "contributions a la consultation", "contributions à la consultation",
        "reponses a la consultation", "réponses à la consultation",
        "qui a repondu a", "qui a répondu à",
        # ES
        "respuestas a la consulta", "comentarios sobre la consulta",
        "qué dijeron sobre la consulta", "que dijeron sobre la consulta",
        # CA
        "que van dir sobre la consulta", "què van dir sobre la consulta",
        "respostes a la consulta",
        # NL
        "feedback op de raadpleging", "reacties op de consultatie",
        # IT
        "feedback sulla consultazione", "risposte alla consultazione",
    )

    def _detect_consultation_feedback_intent(self, query: str) -> bool:
        if not query:
            return False
        q = query.lower()
        return any(p in q for p in self.CONSULTATION_FEEDBACK_INTENT_PHRASES)

    async def _fetch_consultation_feedback(
        self,
        query: str,
        consultations: List[Dict[str, Any]],
        limit: int = 8,
    ) -> Optional[str]:
        """If the user is asking about feedback to a consultation, find the best
        matching consultation (across ALL statuses) and fetch the top stakeholder
        contributions live from Have Your Say.
        """
        from services.api_clients.have_your_say_feedback_client import (
            get_have_your_say_feedback_client,
        )
        client = get_have_your_say_feedback_client()

        def _extract_ids(c: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
            """Return (publication_id, initiative_id) from a consultation dict."""
            pub_id = None
            init_id = None
            for key, target in [("publication_id", "pub"), ("initiative_id", "init")]:
                val = c.get(key)
                if val:
                    try:
                        parsed = int(str(val).strip())
                        if target == "pub":
                            pub_id = parsed
                        else:
                            init_id = parsed
                    except (TypeError, ValueError):
                        pass
            if not init_id and c.get("portal_url"):
                m = re.search(r"/initiatives/(\d+)\b", c["portal_url"])
                if m:
                    init_id = int(m.group(1))
            return pub_id, init_id

        # Build candidate pool: (consultation_dict, pub_id, init_id, score)
        candidates: List[Tuple[Dict[str, Any], Optional[int], Optional[int], int]] = []

        stop = {"the", "and", "for", "with", "what", "did", "say", "about",
                "consultation", "feedback", "stakeholders", "contributions",
                "show", "give", "tell", "have", "your", "from", "this", "that",
                "kept", "purposes", "their"}
        tokens = [t.lower() for t in re.findall(r"[A-Za-z\u00C0-\u017F]{4,}", query)]
        tokens = [t for t in tokens if t not in stop][:8]

        def _score(consultation: Dict[str, Any]) -> int:
            text = " ".join([
                consultation.get("title") or "",
                consultation.get("short_title") or "",
            ]).lower()
            return sum(1 for t in tokens if t in text)

        # 1) Score consultations from the main pipeline
        for c in consultations or []:
            pub_id, init_id = _extract_ids(c)
            if pub_id is None and init_id is None:
                continue
            candidates.append((c, pub_id, init_id, _score(c)))

        # 2) Augment with keyword search across ALL statuses (open/closed/upcoming)
        if tokens:
            try:
                from core.database import SessionLocal
                from models.public_consultation import PublicConsultation
                from sqlalchemy import or_, func
                db = SessionLocal()
                try:
                    q = db.query(PublicConsultation)
                    conds = []
                    for t in tokens:
                        like = f"%{t}%"
                        conds.append(func.lower(PublicConsultation.title).like(like))
                        conds.append(func.lower(func.coalesce(PublicConsultation.short_title, "")).like(like))
                    q = q.filter(or_(*conds))
                    q = q.order_by(PublicConsultation.feedback_count.desc().nulls_last())
                    rows = q.limit(8).all()
                finally:
                    db.close()
                for it in rows:
                    d = {
                        "title": it.title,
                        "short_title": it.short_title,
                        "publication_id": it.publication_id,
                        "initiative_id": it.initiative_id,
                        "portal_url": it.portal_url,
                        "feedback_url": it.feedback_url,
                        "feedback_count": it.feedback_count or 0,
                    }
                    pub_id, init_id = _extract_ids(d)
                    if pub_id is None and init_id is None:
                        continue
                    # Deduplicate by initiative_id (the stable identifier)
                    if any(init_id and init_id == ei for _, _, ei, _ in candidates):
                        continue
                    candidates.append((d, pub_id, init_id, _score(d)))
            except Exception as exc:  # noqa: BLE001
                logger.warning("[HYS-feedback] keyword fallback failed: %s", exc)

        if not candidates:
            return None

        # Sort by score desc, then by feedback_count desc (DB hint), then preserve order
        candidates.sort(key=lambda quad: (-quad[3], -(quad[0].get("feedback_count") or 0)))

        # Try each candidate in order until we get non-empty live feedback.
        # When publication_id is missing, resolve it from initiative_id via
        # the HYS detail API (initiative_id != publicationId in the EC system).
        chosen: Optional[Dict[str, Any]] = None
        pid: Optional[int] = None
        items: List[Any] = []
        summary: Dict[str, Any] = {}
        for c, c_pub_id, c_init_id, score in candidates[:5]:
            # Build list of publicationIds to try for this candidate
            try_pids: List[int] = []
            if c_pub_id:
                try_pids.append(c_pub_id)
            if c_init_id and c_init_id not in try_pids:
                # Resolve initiative_id -> publication_ids via HYS detail API
                resolved = await client.resolve_publication_ids(c_init_id)
                if resolved:
                    try_pids.extend(p for p in resolved if p not in try_pids)
                else:
                    # Fallback: try initiative_id directly (works for some)
                    try_pids.append(c_init_id)

            for try_pid in try_pids:
                try:
                    items = await client.fetch_feedback(try_pid, limit=limit)
                except Exception:
                    items = []
                if items:
                    chosen, pid = c, try_pid
                    try:
                        summary = await client.get_summary_counts(try_pid)
                    except Exception:
                        summary = {"total": len(items), "by_user_type": {}, "by_country": {}}
                    break
            if items:
                break

        if not items or chosen is None or pid is None:
            return None

        title = chosen.get("title") or chosen.get("short_title") or "the consultation"
        public_url = chosen.get("portal_url") or chosen.get("feedback_url") or ""

        lines: List[str] = []
        lines.append(f"\nSTAKEHOLDER FEEDBACK ON HAVE YOUR SAY (live, top {len(items)} of approx {summary.get('total', 0)} sampled):")
        lines.append(f"Consultation: {title}")
        if public_url:
            lines.append(f"Source: {public_url}")
        if summary.get("by_user_type"):
            top_types = sorted(summary["by_user_type"].items(), key=lambda kv: -kv[1])[:5]
            lines.append("By stakeholder type: " + ", ".join(f"{k}={v}" for k, v in top_types))
        if summary.get("by_country"):
            top_countries = sorted(summary["by_country"].items(), key=lambda kv: -kv[1])[:6]
            lines.append("By country: " + ", ".join(f"{k}={v}" for k, v in top_countries))
        lines.append("")
        for it in items:
            who = it.organisation or it.author_name or "anonymous"
            tr = f" (TR {it.transparency_register_number})" if it.transparency_register_number else ""
            lines.append(f"- [{it.user_type or 'UNKNOWN'} | {it.country or '??'}] {who}{tr}")
            if it.short_text:
                lines.append(f"  \"{it.short_text}\"")
            if it.attachments:
                lines.append(f"  Attachments: {len(it.attachments)}")
            lines.append(f"  Submitted: {it.date}")
            lines.append("")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # On-demand: Commissioner agenda
    # ------------------------------------------------------------------

    COMMISSIONER_AGENDA_INTENT_PHRASES = (
        "agenda", "schedule", "calendar", "meeting", "meetings",
        "agenda of", "agenda for", "agenda de", "agenda di",
        "what is", "what was", "what will", "what did",
        "doing today", "doing tomorrow", "doing yesterday",
        "did today", "did yesterday", "will do",
        "meeting", "meetings", "schedule", "calendar",
        # FR
        "rendez-vous de", "agenda de la commissaire", "agenda du commissaire",
        # ES
        "agenda del comisario", "agenda de la comisaria",
        # CA
        "agenda del comissari", "agenda de la comissaria", "que fa", "què fa",
        # IT
        "agenda del commissario",
        # NL
        "agenda van",
    )

    def _detect_commissioner_agenda_intent(
        self, query: str
    ) -> Optional[Tuple[str, Optional[date], Optional[date]]]:
        """Return (commissioner_name, date_from, date_to) or None.

        Detection works in two passes:
          1) Try to resolve a commissioner name in the query.
          2) Require either an agenda-style intent phrase OR a date/relative-date
             token. If only a commissioner name appears with no agenda or date hint,
             do not trigger (avoids false positives on biographical questions).
        """
        if not query:
            return None
        q = query.lower()

        from services.api_clients.commissioner_agenda_client import (
            get_commissioner_agenda_client,
        )
        client = get_commissioner_agenda_client()
        words = re.findall(r"[\w\u00C0-\u017F\-']+", query)
        profile = None
        for n in (3, 2, 1):
            for i in range(len(words) - n + 1):
                cand = " ".join(words[i : i + n])
                if len(cand) < 3:
                    continue
                p = client.resolve(cand)
                if p:
                    profile = p
                    break
            if profile:
                break
        if profile is None:
            return None

        # date / relative-date detection
        relative_date_tokens = (
            "today", "yesterday", "tomorrow", "this week", "next week", "last week",
            "demain", "ahir", "demà", "hoy", "ayer", "mañana", "manana",
            "oggi", "ieri", "domani", "avui", "aujourd'hui",
        )
        has_intent_phrase = any(p in q for p in self.COMMISSIONER_AGENDA_INTENT_PHRASES)
        has_relative_date = any(w in q for w in relative_date_tokens)
        has_iso_date = bool(re.search(r"\b\d{4}-\d{2}-\d{2}\b", q))
        has_named_date = bool(re.search(
            r"\b\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b",
            q,
        ))
        if not (has_intent_phrase or has_relative_date or has_iso_date or has_named_date):
            return None

        # date detection
        today = date.today()
        date_from: Optional[date] = None
        date_to: Optional[date] = None
        if "today" in q or "hoy" in q or "avui" in q or "oggi" in q or "aujourd'hui" in q:
            date_from = date_to = today
        elif "yesterday" in q or "ayer" in q or "ahir" in q or "ieri" in q or "hier" in q:
            date_from = date_to = today - timedelta(days=1)
        elif "tomorrow" in q or "mañana" in q or "manana" in q or "demà" in q or "demain" in q or "domani" in q:
            date_from = date_to = today + timedelta(days=1)
        elif "this week" in q:
            start = today - timedelta(days=today.weekday())
            date_from = start
            date_to = start + timedelta(days=6)
        elif "next week" in q:
            start = today - timedelta(days=today.weekday()) + timedelta(days=7)
            date_from = start
            date_to = start + timedelta(days=6)
        elif "last week" in q:
            start = today - timedelta(days=today.weekday()) - timedelta(days=7)
            date_from = start
            date_to = start + timedelta(days=6)
        else:
            # try ISO date or "Day Month [Year]"
            m = re.search(r"(\d{4})-(\d{2})-(\d{2})", q)
            if m:
                try:
                    date_from = date_to = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                except ValueError:
                    pass
            else:
                month_names = {
                    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
                    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
                }
                m = re.search(
                    r"(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s*(\d{4})?",
                    q,
                )
                if m:
                    try:
                        y = int(m.group(3)) if m.group(3) else today.year
                        d = date(y, month_names[m.group(2)], int(m.group(1)))
                        date_from = date_to = d
                    except (ValueError, KeyError):
                        pass

        # default: a 2-week window centred on today
        if date_from is None and date_to is None:
            date_from = today - timedelta(days=7)
            date_to = today + timedelta(days=7)

        return profile.name, date_from, date_to

    async def _fetch_commissioner_agenda(
        self,
        commissioner_name: str,
        date_from: Optional[date],
        date_to: Optional[date],
    ) -> Optional[str]:
        from services.api_clients.commissioner_agenda_client import (
            get_commissioner_agenda_client,
        )
        client = get_commissioner_agenda_client()
        try:
            profile, items = await client.fetch_agenda(commissioner_name, date_from=date_from, date_to=date_to)
        except Exception as exc:  # noqa: BLE001
            logger.warning("[commissioner-agenda] fetch failed name=%s: %s", commissioner_name, exc)
            return None
        if not profile:
            return None
        if not items:
            window = ""
            if date_from and date_to:
                window = f" between {date_from.isoformat()} and {date_to.isoformat()}"
            return (
                f"\nCOMMISSIONER AGENDA (live):\nNo public agenda items for {profile.name}"
                f"{window}. Source: https://commission.europa.eu/about/organisation/college-commissioners/"
                "calendar-items-president-and-commissioners_en"
            )
        lines: List[str] = []
        window = ""
        if date_from and date_to:
            window = f" ({date_from.isoformat()} to {date_to.isoformat()})"
        lines.append(f"\nCOMMISSIONER AGENDA (live){window}:")
        lines.append(f"{profile.name} -- {profile.portfolio} ({profile.country})")
        lines.append(f"Source: https://commission.europa.eu/about/organisation/college-commissioners/calendar-items-president-and-commissioners_en")
        lines.append("")
        for it in items[:25]:
            loc = f" -- {it.location}" if it.location else ""
            url = f"\n  Detail: {it.detail_url}" if it.detail_url else ""
            lines.append(f"- {it.date.isoformat()}: {it.title}{loc}{url}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # On-demand: Position Analysis (Commission / Parliament / Council)
    # ------------------------------------------------------------------

    POSITION_INTENT_PHRASES = (
        "position of", "stance of", "where does", "what is the position",
        "position on", "stance on", "for or against", "supports or opposes",
        "support or oppose", "who is for", "who is against",
        # FR
        "position de", "position du", "position sur",
        # ES
        "postura de", "postura sobre", "quién apoya", "quien apoya",
        # CA
        "postura de", "postura sobre", "qui dóna suport", "qui dona suport",
        # IT
        "posizione di", "posizione sul",
        # NL
        "standpunt van",
    )

    def _detect_position_intent(self, query: str) -> Optional[Dict[str, Any]]:
        """Detect a position-analysis intent. Requires either:
          (a) a position phrase, or
          (b) a procedure reference that the user is asking about in substantive terms.
        Returns {"procedure_ref"?, "free_text"} or None.
        """
        if not query:
            return None
        q = query.lower()
        has_phrase = any(p in q for p in self.POSITION_INTENT_PHRASES)
        # Procedure reference detection
        m = re.search(r"(\d{4}/\d{4}\s*\([A-Z]{2,4}\))", query)
        procedure_ref = m.group(1).replace(" ", "") if m else None
        if not (has_phrase or procedure_ref):
            return None
        return {"procedure_ref": procedure_ref, "free_text": query}

    async def _fetch_position_block(
        self, query: str, intent: Dict[str, Any]
    ) -> Optional[str]:
        """Fetch + format a FilePosition block. Uses cached snapshot if fresh."""
        from core.database import SessionLocal
        from models.file_position import FilePositionSnapshot
        from models.legislative_train import LegislativeCarriage
        from services.positions import get_position_aggregator

        db = SessionLocal()
        try:
            carriage = None
            if intent.get("procedure_ref"):
                carriage = (
                    db.query(LegislativeCarriage)
                    .filter(LegislativeCarriage.oeil_procedure_ref == intent["procedure_ref"])
                    .first()
                )
            if carriage is None:
                # Keyword search on title against recent carriages
                stop = {"position", "stance", "of", "the", "on", "for", "about",
                        "what", "is", "who", "supports", "opposes", "group", "council"}
                tokens = [t.lower() for t in re.findall(r"[A-Za-z\u00C0-\u017F]{4,}", query)]
                tokens = [t for t in tokens if t not in stop][:6]
                if not tokens:
                    return None
                from sqlalchemy import or_, func as sqlfunc
                q2 = db.query(LegislativeCarriage).filter(LegislativeCarriage.oeil_procedure_ref.isnot(None))
                conds = [sqlfunc.lower(LegislativeCarriage.title).like(f"%{t}%") for t in tokens]
                q2 = q2.filter(or_(*conds)).order_by(LegislativeCarriage.is_recently_updated.desc().nullslast())
                carriage = q2.first()
            if carriage is None:
                return None

            agg = get_position_aggregator(db=db)
            snap = agg.get_cached(carriage.id)
            if snap is None or not agg.is_fresh(snap):
                try:
                    await agg.aggregate_and_cache(carriage)
                    snap = agg.get_cached(carriage.id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("[position] aggregation failed: %s", exc)
                    return None
            if snap is None:
                return None
            return self._format_position_block(carriage, snap)
        finally:
            db.close()

    def _format_position_block(self, carriage, snap) -> str:
        parl = snap.parliament_position or {}
        coun = snap.council_position or {}
        comm = snap.commission_position or {}
        groups = parl.get("groups", []) or []
        ms = coun.get("member_states", []) or []
        summary = coun.get("summary") or {}
        lines = []
        lines.append(f"\nPOSITION ANALYSIS (cached, {snap.confidence} confidence, {snap.data_completeness} completeness):")
        lines.append(f"File: {carriage.title or '(untitled)'} [{snap.procedure_ref}]")
        if comm.get("com_references"):
            lines.append(f"Commission: {', '.join(comm['com_references'])}")
            if comm.get("proposal_date"):
                lines.append(f"Proposal date: {comm['proposal_date']}")
        if parl.get("rapporteur"):
            rg = f" ({parl.get('rapporteur_group')})" if parl.get("rapporteur_group") else ""
            lines.append(f"Rapporteur: {parl['rapporteur']}{rg} -- {parl.get('lead_committee') or ''}")
        if parl.get("amendment_activity"):
            act = parl["amendment_activity"]
            lines.append(f"Amendments tabled: {act.get('total', 0)}")
            bg = act.get("by_group", {})
            if bg:
                top = sorted(bg.items(), key=lambda kv: -kv[1])[:6]
                lines.append("  By group: " + ", ".join(f"{k}={v}" for k, v in top))
        if groups:
            lines.append("Parliament stance (per group):")
            for g in groups:
                lines.append(f"  - {g['group_code']}: {g['stance']} (cohesion {g['cohesion']}, {g['confidence']} confidence, {g['amendment_count']} amendments) -- {g.get('rationale','')}")
        if ms:
            lines.append("Council stance (per Member State):")
            supp = summary.get("supporting", [])
            opp = summary.get("opposing", [])
            und = [x['country_code'] for x in ms if x.get('stance') not in ('support','oppose')]
            lines.append(f"  Supporting ({len(supp)}): {', '.join(supp) or '(none)'}")
            lines.append(f"  Opposing ({len(opp)}): {', '.join(opp) or '(none)'}")
            lines.append(f"  Undecided ({len(und)}): {', '.join(und[:15])}{' ...' if len(und)>15 else ''}")
        if coun.get("general_approach_adopted"):
            lines.append("Council general approach: ADOPTED")
        if parl.get("plenary_adopted", {}).get("adopted"):
            lines.append(f"EP plenary text adopted: {parl['plenary_adopted'].get('date','?')}")
        lines.append("Source: file_position_snapshots (generated_at " + (snap.generated_at.isoformat() if snap.generated_at else '?') + ")")
        return "\n".join(lines)

    async def _fetch_eu_institutional_search(
        self,
        query: str,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search trusted EU institutional sources via Tavily.

        Only called when no knowledge guides matched (fallback).
        Scoped to official .europa.eu domains plus key policy media
        (Politico, Contexte, Bruegel, Euractiv).

        Results include a 'source_name' field for AI attribution:
        the AI MUST cite the source by name when using these results.
        """
        results = []

        if not self.tavily_client:
            return results

        try:
            response = await self.tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=max_results,
                include_domains=self.EU_INSTITUTIONAL_DOMAINS,
            )

            for result in response.results:
                source_name = self._extract_source_name(result.url)
                results.append({
                    'title': result.title,
                    'url': result.url,
                    'content': result.content[:600] if result.content else '',
                    'score': result.score,
                    'published_date': result.published_date,
                    'source': 'eu_institutional_search',
                    'source_name': source_name,
                })

            if results:
                logger.info(
                    f"[EU-SEARCH] Institutional fallback returned "
                    f"{len(results)} results in {response.response_time:.2f}s"
                )

        except Exception as e:
            logger.warning(f"[EU-SEARCH] Institutional fallback failed: {e}")

        return results

    async def _fetch_beresol_content(
        self,
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch relevant content from Beresol open reports and monitors.

        Beresol is Brubru's company. Their open reports provide in-depth
        analysis on EU policy topics that can enhance AI responses.

        IMPORTANT: When referencing Beresol content, always mention:
        - Source: "Beresol Open Report" or "Beresol Monitor"
        - Link: https://beresol.eu/public-affairs

        Args:
            query: User query

        Returns:
            List of relevant Beresol content items
        """
        beresol_results = []

        if not self.beresol_loader:
            return beresol_results

        try:
            # Get relevant content from Beresol knowledge bundle
            content_items = self.beresol_loader.get_relevant_content_for_query(
                query=query,
                max_reports=2,
                max_content_length=3000
            )

            for item in content_items:
                if item.get('type') == 'beresol_report':
                    beresol_results.append({
                        'type': 'beresol_report',
                        'id': item['id'],
                        'title': item['title'],
                        'subtitle': item.get('subtitle', ''),
                        'author': item['author'],
                        'date': item.get('date'),
                        'policy_area': item['policy_area'],
                        'executive_summary': item.get('executive_summary', ''),
                        'key_findings': item.get('key_findings', ''),
                        'content_excerpt': item.get('content_excerpt', ''),
                        'keywords': item.get('keywords', []),
                        'source': item['source'],
                        'publisher': item['publisher'],
                        'source_url': item['source_url'],
                        'attribution_note': item['attribution_note']
                    })
                elif item.get('type') == 'beresol_monitor':
                    beresol_results.append({
                        'type': 'beresol_monitor',
                        'id': item['id'],
                        'name': item['name'],
                        'description': item['description'],
                        'policy_area': item['policy_area'],
                        'keywords': item.get('keywords', []),
                        'source': item['source'],
                        'publisher': item['publisher'],
                        'source_url': item['source_url'],
                        'attribution_note': item['attribution_note']
                    })

            if beresol_results:
                logger.debug(f"Found {len(beresol_results)} relevant Beresol items for query")

        except Exception as e:
            logger.error(f"Failed to fetch Beresol content: {str(e)}")
            # Don't fail context building if Beresol fetch fails

        return beresol_results

    def _build_reference_data_context(
        self,
        query: str
    ) -> Optional[str]:
        """
        Build reference data context (calendars, institutions).

        Args:
            query: User query

        Returns:
            Formatted reference data context or None
        """
        context_parts = []

        # Each source is guarded on its own. A single try around both meant one
        # failing source discarded the other's output as well: while
        # find_person_in_commission was raising on every query, the calendar
        # context was built successfully and then thrown away with it.
        for label, build in (
            ("calendar", self.reference_data_service.build_calendar_context),
            ("institution", self.reference_data_service.build_institution_context),
        ):
            try:
                part = build(query)
                if part:
                    context_parts.append(part)
            except Exception as e:
                logger.error(
                    "Failed to build %s reference context: %s", label, e, exc_info=True
                )

        return "\n\n".join(context_parts) if context_parts else None

    async def _fetch_via_toolbox(
        self,
        query: str,
        entities: ExtractedEntities
    ) -> List[Dict[str, Any]]:
        """
        Fetch supplementary data via MCP Toolbox for Databases.

        Calls relevant Toolbox tools based on extracted entities.
        Returns results that supplement (not replace) existing context sources.
        Gracefully returns empty list if Toolbox is unavailable.
        """
        from services.toolbox_service import get_toolbox_service

        toolbox = get_toolbox_service()
        if not toolbox.available:
            return []

        results = []

        try:
            # Search for texts adopted if the query mentions resolutions or plenary
            resolution_keywords = ['resolution', 'adopted', 'plenary', 'vote', 'voted']
            if any(kw in query.lower() for kw in resolution_keywords):
                texts = await toolbox.get_texts_adopted(keyword=query.split()[0])
                if texts:
                    for item in texts[:5]:
                        results.append({
                            'source_type': 'toolbox_texts_adopted',
                            'title': item.get('title', ''),
                            'ta_reference': item.get('ta_reference', ''),
                            'text_type': item.get('text_type', ''),
                            'adoption_date': str(item.get('adoption_date', '')),
                            'procedure_ref': item.get('procedure_ref', ''),
                        })

            # Search carriages by procedure reference if detected
            if entities.procedure_references:
                for ref in entities.procedure_references[:2]:
                    carriages = await toolbox.search_legislative_carriages(keyword=ref)
                    if carriages:
                        for item in carriages[:3]:
                            results.append({
                                'source_type': 'toolbox_carriage',
                                'title': item.get('title', ''),
                                'status': item.get('current_status', ''),
                                'oeil_ref': item.get('oeil_procedure_ref', ''),
                                'committee': item.get('lead_committee', ''),
                                'summary': (item.get('ai_summary', '') or '')[:500],
                            })

            logger.debug(f"Toolbox returned {len(results)} supplementary results")

        except Exception as e:
            logger.warning(f"Toolbox fetch failed: {e}")

        return results

    async def _fetch_user_uploaded_documents(
        self,
        user_id: str,
        query: str,
        max_docs: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Fetch user's documents marked for AI context inclusion.

        Previously restricted to ``document_type == 'uploaded'`` rows; now any
        user document (uploads, notes, analyses, strategies, AI-generated
        position papers / MEP briefings / talking points / resolutions /
        EP questions / consultation responses) is eligible as long as the
        user has flagged it with ``include_in_ai_context = True``.
        Scores by keyword relevance to the query and returns top matches.
        """
        if not user_id:
            return []

        try:
            from models.user_document import UserDocument

            db = SessionLocal()
            docs = db.query(UserDocument).filter(
                UserDocument.user_id == user_id,
                UserDocument.include_in_ai_context == True,
                UserDocument.content != None,
            ).order_by(UserDocument.updated_at.desc()).limit(15).all()

            if not docs:
                db.close()
                return []

            results = []
            query_lower = query.lower()
            query_words = set(w for w in query_lower.split() if len(w) > 2)

            for doc in docs:
                content_lower = (doc.content or '')[:5000].lower()
                title_lower = (doc.title or '').lower()
                score = sum(1 for w in query_words if w in content_lower or w in title_lower)

                # Label the source so the system prompt can reason about it.
                if doc.document_type == 'uploaded':
                    src = 'user_uploaded'
                else:
                    src = f"user_document_{doc.document_type}"

                results.append({
                    'id': str(doc.id),
                    'title': doc.title,
                    'document_type': doc.document_type,
                    'tags': list(doc.tags or []),
                    'original_filename': doc.original_filename,
                    'celex_number': doc.celex_number,
                    'procedure_reference': doc.procedure_reference,
                    'content_excerpt': (doc.content or '')[:2000],
                    'relevance_score': score,
                    'source_type': src,
                })

            results.sort(key=lambda x: x['relevance_score'], reverse=True)
            db.close()

            selected = results[:max_docs]
            if selected:
                logger.info(
                    f"Found {len(selected)} relevant user documents for context "
                    f"(types: {sorted({r['document_type'] for r in selected})})"
                )
            return selected

        except Exception as e:
            logger.warning(f"Failed to fetch user uploaded documents: {e}")
            return []

    async def _fetch_org_intelligence(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch aggregated org intelligence profile for personalised context."""
        try:
            db = SessionLocal()
            try:
                from sqlalchemy import text
                result = db.execute(
                    text("SELECT policy_areas, tracked_files, amended_files, sector, country, "
                         "query_count, amendment_count, top_topics FROM org_intelligence WHERE user_id = :uid"),
                    {"uid": user_id}
                ).fetchone()
                if not result:
                    return None
                policy_areas, tracked_files, amended_files, sector, country, \
                    query_count, amendment_count, top_topics = result
                if not policy_areas and not tracked_files and query_count == 0:
                    return None
                return {
                    'policy_areas': policy_areas or [],
                    'tracked_files': tracked_files or [],
                    'amended_files': amended_files or [],
                    'sector': sector,
                    'country': country,
                    'query_count': query_count or 0,
                    'amendment_count': amendment_count or 0,
                    'top_topics': top_topics or {},
                }
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to fetch org intelligence: {e}")
            return None

    # ------------------------------------------------------------------
    # Specialised EC Databases — on-demand blocks for /sanctions,
    # /transparency-register and /comitology. Each block respects the
    # 4,000-char prompt-injection cap (per CLAUDE.md) and is appended
    # near the TOP of format_context_for_ai so it survives 32k truncation.
    # ------------------------------------------------------------------

    _SANCTIONS_INTENT = re.compile(
        r"\b(sanction(ed|s)?|restrictive\s+measures?|asset\s+freeze|"
        r"sdn\s+list|CFSP|frozen\s+assets|EU\.\d+\.\d+|"
        r"prohibited\s+(?:from|to)\s+(?:enter|trade|do\s+business))\b",
        re.IGNORECASE,
    )

    _TR_INTENT = re.compile(
        r"\b(lobby(?:ist|ists|ing)?|interest\s+representatives?|"
        r"transparency\s+register|EP\s+pass(?:es)?|lobbying\s+costs?|"
        r"who\s+lobbies|registered\s+lobbyist)\b",
        re.IGNORECASE,
    )

    _COMITOLOGY_INTENT = re.compile(
        r"\b(comitology|implementing\s+act|committee\s+(?:vote|opinion|meeting|record)|"
        r"SCoPAFF|standing\s+committee\s+on|examination\s+procedure|"
        r"advisory\s+procedure|summary\s+record|urgency\s+letter|"
        r"voting\s+sheet|draft\s+implementing|comitology\s+(?:document|register))\b",
        re.IGNORECASE,
    )

    # W1b (12 May 2026): legal-text article intent detector + fetcher.
    # Recognises "Article N (paragraph M / point a) of <CELEX|alias>" in 6 languages
    # (EN/FR/ES/CA/IT/NL), with a separate slot for "Recital N of <CELEX|alias>".
    # On match, the fetcher resolves the alias to a CELEX and pulls the cached
    # recital-article map + defined terms from the legal-text intelligence layer.
    # Fail-soft: if neither cache is populated for the CELEX, the block still
    # ships the resolution + EUR-Lex URL so the model has something concrete to
    # cite. See memory/project_chat_ai_architecture_evolution.md (W1b).
    _LEGAL_TEXT_ARTICLE_RE = re.compile(
        r"(?ix)"
        r"\b(?P<kw>article|art\.|articolo|art[íi]culo|artikel|recital|consid[eé]rant|considerando|overweging)"
        r"\s+(?P<num>\d{1,3})(?P<sub>[a-z])?"
        r"(?:\s*\(\s*(?P<para>\d{1,2})\s*\))?"
        r"(?:\s*[,\(]?\s*(?:paragraph|paragraphe|p[áa]rrafo|apartado|paragrafo|comma|par[àa]graf|apartat|lid)\s+(?P<para2>\d{1,2}))?"
        r"(?:\s*\(\s*(?P<point>[a-z])\s*\))?"
    )

    def _detect_legal_text_article_intent(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Detect "Article N (paragraph M, point X) of <CELEX|alias>" or
        "Recital N of <CELEX|alias>" in 6 languages.
        Returns {type, number, paragraph, point, celex, alias_used, raw_match} or None.
        """
        if not query:
            return None
        m = self._LEGAL_TEXT_ARTICLE_RE.search(query)
        if not m:
            return None

        kw = (m.group("kw") or "").lower()
        # Map keyword to canonical type
        recital_kws = ("recital", "considerant", "considérant", "considerando", "overweging")
        type_ = "recital" if any(rk in kw for rk in recital_kws) else "article"

        number = m.group("num")
        sub = m.group("sub") or ""  # e.g. "a" in "Article 3a"
        paragraph = m.group("para") or m.group("para2")
        point = m.group("point")

        # Resolve the law reference from the same query string.
        try:
            from services.parsers.law_alias_resolver import (
                find_alias_matches as _find_alias_matches,
                resolve_law_reference as _resolve_law_reference,
            )
        except Exception:  # noqa: BLE001
            return None

        celex = None
        alias_used = None
        hits = _find_alias_matches(query)
        if hits:
            celex = hits[0].celex
            alias_used = hits[0].alias
        else:
            # Fall back to the broader resolver (handles "Regulation (EU) YYYY/N" forms)
            ref = _resolve_law_reference(query)
            if ref:
                celex = ref
                alias_used = ref

        if not celex:
            return None

        return {
            "type": type_,
            "number": (number + sub) if sub else number,
            "paragraph": paragraph,
            "point": point,
            "celex": celex,
            "alias_used": alias_used,
            "raw_match": m.group(0),
        }

    async def _fetch_legal_text_article_block(
        self, db, intent: Dict[str, Any]
    ) -> Optional[str]:
        """
        Compose a legal-text intelligence context block for the matched
        Article / Recital reference. Fail-soft on every store lookup.
        """
        celex = intent.get("celex")
        if not celex:
            return None

        type_ = intent.get("type", "article")
        number = str(intent.get("number") or "").strip()
        paragraph = intent.get("paragraph")
        point = intent.get("point")
        alias_used = intent.get("alias_used") or celex

        # Best-effort: cached recital-article map (only ~5 acts cached today; flagship
        # laws compute on first request when the Formex XML is present).
        recital_map = None
        try:
            from services.parsers.recital_article_store import get_or_compute_map as _get_ram
            recital_map = _get_ram(db, celex)
        except Exception as e:  # noqa: BLE001
            logger.debug("[legal-text] recital_article_store lookup failed for %s: %s", celex, e)

        # Best-effort: cached defined-terms map.
        defined_terms = None
        try:
            from services.parsers.definition_store import get_or_compute_map as _get_defs
            defined_terms = _get_defs(db, celex)
        except Exception as e:  # noqa: BLE001
            logger.debug("[legal-text] definition_store lookup failed for %s: %s", celex, e)

        # Find linked recitals for this article number (only meaningful when type=article).
        article_recitals: List[Dict[str, Any]] = []
        if type_ == "article" and recital_map and isinstance(recital_map, dict):
            target_keys = {number, f"article {number}", f"art. {number}", f"art {number}", f"Article {number}"}
            for k, v in recital_map.items():
                if str(k).strip().lower() in {tk.lower() for tk in target_keys}:
                    if isinstance(v, list):
                        article_recitals = v[:3]
                    break

        # Find definitions whose article matches the queried article.
        article_definitions: List[Dict[str, Any]] = []
        if type_ == "article" and defined_terms and isinstance(defined_terms, dict):
            for term, entry in defined_terms.items():
                if not isinstance(entry, dict):
                    continue
                entry_article = str(entry.get("article") or "").strip().lower()
                if entry_article in (number, f"article {number}", f"art. {number}", f"art {number}"):
                    article_definitions.append({
                        "term": entry.get("term") or term,
                        "definition": (entry.get("definition") or "")[:600],
                        "point": entry.get("point"),
                    })
                    if len(article_definitions) >= 8:
                        break

        # Compose the block.
        eurlex_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
        lines: List[str] = []
        header = f"=== LEGAL TEXT INTELLIGENCE -- {type_.upper()} {number}"
        if paragraph:
            header += f"({paragraph})"
        if point:
            header += f", point ({point})"
        header += f" of CELEX {celex} ==="
        lines.append(header)

        if alias_used and alias_used != celex:
            lines.append(f"Alias resolved: '{alias_used}' -> {celex}")
        lines.append(f"EUR-Lex URL: {eurlex_url}")
        lines.append(f"Raw user reference: {intent.get('raw_match', '')}")

        if type_ == "article":
            if article_recitals:
                lines.append("")
                lines.append(f"Top-3 linked recitals (TF-IDF cosine) for Article {number}:")
                for r in article_recitals[:3]:
                    rn = r.get("recital_number") or r.get("recital") or "?"
                    score = r.get("score")
                    score_str = f"{score:.2f}" if isinstance(score, (int, float)) else "n/a"
                    snippet = (r.get("snippet") or "")[:400]
                    lines.append(f"  - Recital {rn} (score={score_str}): {snippet}")
            else:
                lines.append("")
                lines.append(f"Linked recitals for Article {number}: not yet cached for {celex}.")
                lines.append("  (TF-IDF cosine map computes on demand when Formex XML is available.)")

            if article_definitions:
                lines.append("")
                lines.append(f"Statutory definitions in Article {number}:")
                for d in article_definitions:
                    pt = f"point ({d['point']})" if d.get("point") else ""
                    lines.append(f"  - '{d['term']}' {pt}: {d['definition']}")
            else:
                lines.append("")
                lines.append(f"Statutory definitions in Article {number}: none cached.")
        else:  # recital
            lines.append("")
            lines.append(f"Recital {number} of {celex}: see EUR-Lex URL above for the verbatim text.")
            lines.append("  (Brubru caches article-to-recital cosine links; the verbatim recital text is available on demand via /api/v1/laws/{celex}/text.)")

        lines.append("")
        lines.append("**Rule:** Brubru MUST ground its answer in this block and cite the EUR-Lex URL.")
        lines.append("Do NOT invent article text not present here. If asked for verbatim text and it is not")
        lines.append("in this block, say so honestly and point to the EUR-Lex URL.")

        return "\n".join(lines)

    def _detect_sanctions_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        m = self._SANCTIONS_INTENT.search(query)
        if not m:
            return None
        # Extract EU.<n>.<n> if mentioned directly
        eu_ref = re.search(r"EU\.\d+\.\d+", query)
        # Extract a country/programme hint
        prog = None
        for kw, code in {
            "ukraine": "UKR", "ukrainian": "UKR", "russia": "UKR", "russian": "UKR",
            "iran": "IRN", "iranian": "IRN",
            "belarus": "BLR", "belarusian": "BLR",
            "syria": "SYR", "syrian": "SYR",
            "north korea": "PRK", "dprk": "PRK",
            "myanmar": "MMR", "burma": "MMR",
            "terrorist": "TERR", "terrorism": "TERR",
            "haiti": "HR",
        }.items():
            if kw in query.lower():
                prog = code
                break
        return {"keyword": m.group(0), "eu_ref": eu_ref.group(0) if eu_ref else None, "programme": prog}

    def _detect_transparency_register_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        m = self._TR_INTENT.search(query)
        if not m:
            return None
        return {"keyword": m.group(0)}

    def _detect_comitology_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query:
            return None
        m = self._COMITOLOGY_INTENT.search(query)
        if not m:
            return None
        # Detect committee code if mentioned (e.g. C20407)
        cm = re.search(r"\bC\d{5}\b", query)
        return {"keyword": m.group(0), "committee_code": cm.group(0) if cm else None}

    _SANCTIONS_STOPWORDS = {
        "sanction", "sanctioned", "sanctions", "restrictive", "measure", "measures",
        "freeze", "asset", "sdn", "list", "cfsp", "frozen", "prohibited", "on", "the",
        "who", "what", "is", "are", "a", "an", "of", "in", "to", "for", "and", "or",
        "eu", "european", "union", "officials", "official", "from", "by",
        # Expanded 12 May 2026 — yesterday's audit showed ILIKE on these words matched
        # garbage rows like "Federal NEWS Agency LLC" for the query "the NEW sanctions
        # package AGAINST Russia". The chatbot then distrusted the block and fabricated.
        "new", "newest", "latest", "recent", "recently", "last", "most",
        "package", "packages", "round", "tranche", "batch", "wave",
        "against", "controls", "control", "export", "exports", "import", "imports",
        "interact", "interacts", "interaction", "dual", "use",
        "organisation", "organisations", "organization", "organizations", "org", "orgs",
        "entity", "entities", "person", "persons", "people", "individuals", "individual",
        "any", "all", "some", "few", "many", "much", "more", "less",
        "fetch", "fetched", "info", "information", "data", "thanks",
        "can", "could", "would", "should", "may", "might", "must", "shall",
        "this", "that", "these", "those", "them", "their", "there",
        "but", "however", "though", "although", "while",
        "you", "your", "yours", "yourself", "i", "we", "our", "us", "me",
        "repeat", "repeatedly", "again", "still", "again",
        "commission", "council", "parliament", "members",
        "names", "name", "first", "second", "third", "next", "previous",
        "give", "tell", "show", "find", "search", "look", "looking",
    }

    # Matches "latest / new / recent / last sanctions package" — temporal questions where
    # the right answer is "the most recently adopted Council acts" rather than a keyword search.
    _SANCTIONS_TEMPORAL_PATTERN = re.compile(
        r"\b(latest|newest|new|recent|recently|last|most\s+recent|just\s+adopted|"
        r"upcoming|newly\s+added|recently\s+added|new\s+package|recent\s+package|"
        r"latest\s+package|last\s+package)\b",
        re.I,
    )

    async def _fetch_sanctions_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        """Pull sanctions rows matching the query.

        Two modes:
        - **Temporal** (query asks for "latest/new/recent/last [package]"): return the
          most-recent OJ-published Council acts under sanctions regulations from
          `commission_documents` PLUS the most-recent additions to the `eu_sanctions`
          consolidated list. This matches the user's actual intent — "what's the new
          package" — and avoids ILIKE-on-stopwords nonsense.
        - **Entity** (query names a person/entity/programme): keyword ILIKE on
          `eu_sanctions.full_name` and `.citizenships`, with the expanded stopword filter
          above to avoid matching things like "Federal NEWS Agency LLC" on the word "NEW".
        """
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                is_temporal = bool(self._SANCTIONS_TEMPORAL_PATTERN.search(query))

                lines: list[str] = []

                if is_temporal:
                    # ---- Branch A: recent Council acts under sanctions regulations ----
                    # commission_documents holds the OJ items we synced. Sanctions acts are
                    # Council Implementing Regulations + Council CFSP Decisions. We filter
                    # on title patterns + on doc_type ∈ {OJ, CFSP, COM (proposals)} and
                    # order by reference recency (CELEX year ≫ document_date is sparse).
                    title_filter = (
                        "("
                        "title ILIKE '%restrictive measures%' "
                        "OR title ILIKE '%sanctions%' "
                        "OR title ILIKE '%CFSP%' "
                        "OR title ILIKE '%Council Implementing Regulation%'"
                        ")"
                    )
                    prog_clause = ""
                    if intent.get("programme") == "UKR":
                        prog_clause = (
                            " AND (title ILIKE '%Russia%' OR title ILIKE '%Ukraine%' "
                            "OR title ILIKE '%269/2014%' OR title ILIKE '%833/2014%' "
                            "OR title ILIKE '%2014/145%')"
                        )
                    elif intent.get("programme") == "IRN":
                        prog_clause = " AND (title ILIKE '%Iran%' OR title ILIKE '%Iranian%')"
                    elif intent.get("programme") == "BLR":
                        prog_clause = " AND (title ILIKE '%Belarus%' OR title ILIKE '%Belarusian%')"
                    elif intent.get("programme") == "SYR":
                        prog_clause = " AND (title ILIKE '%Syria%' OR title ILIKE '%Syrian%')"
                    elif intent.get("programme") == "PRK":
                        prog_clause = (
                            " AND (title ILIKE '%North Korea%' OR title ILIKE '%DPRK%' "
                            "OR title ILIKE '%Democratic People''s Republic of Korea%')"
                        )
                    elif intent.get("programme") == "MMR":
                        prog_clause = " AND (title ILIKE '%Myanmar%' OR title ILIKE '%Burma%')"

                    recent_acts = db.execute(text(f"""
                        SELECT reference, title, publication_date, doc_type
                          FROM commission_documents
                         WHERE {title_filter}{prog_clause}
                         ORDER BY first_seen DESC NULLS LAST, reference DESC
                         LIMIT 10
                    """)).mappings().all()

                    # ---- Branch B: most-recent additions to consolidated list ----
                    san_params: Dict[str, Any] = {}
                    san_where = ""
                    if intent.get("programme"):
                        san_where = "WHERE programme = :programme"
                        san_params["programme"] = intent["programme"]
                    recent_entries = db.execute(text(f"""
                        SELECT eu_ref_num, full_name, programme, subject_type, citizenships,
                               legal_basis_title, date_file
                          FROM eu_sanctions
                          {san_where}
                         ORDER BY date_file DESC NULLS LAST, full_name
                         LIMIT 5
                    """), san_params).mappings().all()

                    if not recent_acts and not recent_entries:
                        return None

                    lines = [
                        "EU SANCTIONS / RESTRICTIVE MEASURES — recent acts and listings:",
                        f"Query intent: temporal ('latest/new/recent/last')"
                        + (f" | programme: {intent['programme']}" if intent.get("programme") else ""),
                        "",
                    ]

                    if recent_acts:
                        lines.append("RECENT COUNCIL ACTS (from commission_documents, OJ-published):")
                        for r in recent_acts:
                            ref = r.get("reference") or "—"
                            title = (r.get("title") or "—")[:180]
                            dt = str(r.get("publication_date") or "—")[:10]
                            lines.append(f"  - {ref} | {title} | OJ date {dt}")
                        lines.append("")

                    if recent_entries:
                        lines.append("MOST-RECENT ADDITIONS TO CONSOLIDATED LIST (from eu_sanctions):")
                        for r in recent_entries:
                            ref = r.get("eu_ref_num") or "—"
                            name = r.get("full_name") or "—"
                            prog = r.get("programme") or "?"
                            st = "person" if r.get("subject_type") == "P" else "entity"
                            citi = ", ".join(r.get("citizenships") or []) or "—"
                            leba = (r.get("legal_basis_title") or "")[:70]
                            dt = str(r.get("date_file") or "—")[:10]
                            lines.append(
                                f"  - {name} ({st}) | EU ref {ref} | programme {prog} "
                                f"| citizenship {citi} | legal basis {leba} | refreshed {dt}"
                            )
                        lines.append("")

                    lines.append(
                        "NOTE: the EU does NOT formally number sanctions packages in legal text. "
                        "Numbered package labels (e.g. '19th Russia package') are external press "
                        "shorthand used by Politico / Reuters / Bloomberg. Do not assert a numbered "
                        "package unless that number appears verbatim above."
                    )
                    lines.append(
                        "Source: commission_documents (OJ) + eu_sanctions consolidated list. "
                        "Brubru endpoints: /api/v1/specialised/sanctions, /api/v1/laws."
                    )

                else:
                    # ---- Branch C: entity-name lookup with stopword filter ----
                    params: Dict[str, Any] = {}
                    where: list[str] = []
                    terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                             if t.lower() not in self._SANCTIONS_STOPWORDS]
                    terms = terms[:3]
                    if terms:
                        name_clauses = []
                        for i, t in enumerate(terms):
                            name_clauses.append(
                                f"(full_name ILIKE :nm{i} OR "
                                f"EXISTS (SELECT 1 FROM unnest(citizenships) c WHERE c ILIKE :nm{i}))"
                            )
                            params[f"nm{i}"] = f"%{t}%"
                        where.append("(" + " OR ".join(name_clauses) + ")")
                    if intent.get("eu_ref"):
                        where.append("eu_ref_num = :eu_ref")
                        params["eu_ref"] = intent["eu_ref"]
                    if intent.get("programme"):
                        where.append("programme = :programme")
                        params["programme"] = intent["programme"]
                    where_sql = "WHERE " + " AND ".join(where) if where else ""

                    rows = db.execute(text(f"""
                        SELECT eu_ref_num, full_name, programme, subject_type, citizenships,
                               legal_basis_title, date_file
                          FROM eu_sanctions
                          {where_sql}
                         ORDER BY date_file DESC NULLS LAST, full_name
                         LIMIT 10
                    """), params).mappings().all()

                    if not rows:
                        return None

                    lines = [
                        "EU SANCTIONS / RESTRICTIVE MEASURES (from eu_sanctions; CFSP consolidated list):",
                        f"Query keyword: '{intent.get('keyword')}'"
                        + (f" | programme: {intent['programme']}" if intent.get("programme") else "")
                        + (f" | EU ref: {intent['eu_ref']}" if intent.get("eu_ref") else ""),
                        "",
                    ]
                    for r in rows:
                        ref = r.get("eu_ref_num") or "—"
                        name = r.get("full_name") or "—"
                        prog = r.get("programme") or "?"
                        st = "person" if r.get("subject_type") == "P" else "entity"
                        citi = ", ".join(r.get("citizenships") or []) or "—"
                        leba = (r.get("legal_basis_title") or "")[:70]
                        dt = str(r.get("date_file") or "—")[:10]
                        lines.append(f"  - {name} ({st}) | EU ref {ref} | programme {prog} | citizenship {citi} | "
                                     f"legal basis {leba} | refreshed {dt}")
                    lines.append("")
                    lines.append("Source: webgate.ec.europa.eu/fsd/fsf (daily public CSV). "
                                 "Brubru endpoint: /api/v1/specialised/sanctions.")

                block = "\n".join(lines)
                if len(block) > 4500:
                    block = block[:4400] + "\n[truncated — query the /sanctions endpoint for the full list]"
                return block
            finally:
                db.close()
        except Exception as e:
            logger.warning("[sanctions-block] failed: %s", e)
            return None

    # ================================================================
    # Layer 2e — Commissioners list (added 12 May 2026 after audit)
    # ================================================================
    _COMMISSIONERS_INTENT = re.compile(
        r"\b(commissioners?|college\s+of\s+commissioners?|college\s+members?|"
        r"(?:vice[\s\-]?)?presidents?|EVPs?|executive\s+vice[\s\-]?presidents?|"
        r"who\s+(?:are|is)\s+the\s+commissioners?|"
        r"list\s+(?:of|all)\s+commissioners?|portfolio\s+of\s+commissioners?|"
        r"all\s+commissioners?|every\s+commissioner)\b",
        re.I,
    )

    def _detect_commissioners_intent(self, query: str) -> bool:
        if not query:
            return False
        return bool(self._COMMISSIONERS_INTENT.search(query))

    async def _fetch_commissioners_block(self, query: str) -> Optional[str]:
        """Return the canonical list of 27 College members with portfolios + countries."""
        try:
            from services.api_clients.commissioner_agenda_client import (
                load_commissioner_profiles,
            )
            profiles = load_commissioner_profiles()
            if not profiles:
                return None

            lines = [
                "EU COLLEGE OF COMMISSIONERS (2024-2029 mandate, 27 members):",
                "Source: commissioners.json (Brubru canonical) / commission.europa.eu",
                "",
            ]
            # President + EVPs first (slug 'president' or portfolio starts with 'Executive Vice-President')
            president = [p for p in profiles if p.slug == "president"]
            evps = [p for p in profiles if "Executive Vice-President" in (p.portfolio or "")
                    and p.slug != "president"]
            rest = [p for p in profiles if p.slug != "president"
                    and "Executive Vice-President" not in (p.portfolio or "")]

            def fmt(p):
                portfolio = (p.portfolio or "—").strip()
                return f"  - {p.name} ({p.country}) — {portfolio} [slug: {p.slug}]"

            if president:
                lines.append("PRESIDENT:")
                for p in president:
                    lines.append(fmt(p))
                lines.append("")
            if evps:
                lines.append(f"EXECUTIVE VICE-PRESIDENTS ({len(evps)}):")
                for p in sorted(evps, key=lambda x: x.name):
                    lines.append(fmt(p))
                lines.append("")
            if rest:
                lines.append(f"COMMISSIONERS ({len(rest)}):")
                for p in sorted(rest, key=lambda x: x.name):
                    lines.append(fmt(p))

            lines.append("")
            lines.append(
                f"Total: {len(profiles)} members. Brubru endpoints: "
                "/api/v1/commissioners (all profiles), /api/v1/commissioners/{slug} (profile), "
                "/api/v1/commissioners/{name}/agenda (live calendar)."
            )
            lines.append("")
            lines.append(
                "CRITICAL FOR THE LLM: when the user asks 'who are the commissioners of the EU' or "
                "any general list query, your answer MUST include ALL of the names above (President + "
                f"all {len(profiles) - 1} EVPs and Commissioners). Do not abbreviate to 'Key Commissioners "
                "include' or list only 5-7 — the user asked for the canonical list, and you have it here."
            )

            block = "\n".join(lines)
            if len(block) > 6000:
                block = block[:5900] + "\n[truncated — query /api/v1/commissioners for the full list]"
            return block
        except Exception as e:
            logger.warning("[commissioners-block] failed: %s", e)
            return None

    # ================================================================
    # Layer 2f — DG personnel (added 12 May 2026 after audit V11)
    # ================================================================
    _DG_PERSONNEL_INTENT = re.compile(
        r"\b(directors?\s+(?:of|in)\s+DG|DG[\s\-_]?[A-Z]{2,6}\s+(?:directors?|personnel|director[\s\-]?general|"
        r"deputy|head)|who\s+(?:heads?|leads?|runs?)\s+DG|director[\s\-]?general\s+of\s+DG|"
        r"deputy\s+director[\s\-]?general|head\s+of\s+unit|"
        r"organigramme?|org\s+chart\s+of\s+DG)\b",
        re.I,
    )

    # Map common DG abbreviations to canonical org-chart filenames.
    _DG_ALIASES = {
        "REGIO": "DG REGIO", "regio": "DG REGIO",
        "COMP": "DG COMP", "comp": "DG COMP",
        "ENV": "DG ENV", "env": "DG ENV",
        "CLIMA": "DG CLIMA", "clima": "DG CLIMA",
        "ENER": "DG ENER", "ener": "DG ENER",
        "MOVE": "DG MOVE", "move": "DG MOVE",
        "EAC": "DG EAC", "eac": "DG EAC",
        "SANTE": "DG SANTE", "sante": "DG SANTE",
        "HOME": "DG HOME", "home": "DG HOME",
        "JUST": "DG JUST", "just": "DG JUST",
        "FISMA": "DG FISMA", "fisma": "DG FISMA",
        "TRADE": "DG TRADE", "trade": "DG TRADE",
        "TAXUD": "DG TAXUD", "taxud": "DG TAXUD",
        "CNECT": "DG CNECT", "cnect": "DG CNECT", "connect": "DG CNECT",
        "DEFIS": "DG DEFIS", "defis": "DG DEFIS",
        "GROW": "DG GROW", "grow": "DG GROW",
        "EMPL": "DG EMPL", "empl": "DG EMPL",
        "AGRI": "DG AGRI", "agri": "DG AGRI",
        "MARE": "DG MARE", "mare": "DG MARE",
        "ECFIN": "DG ECFIN", "ecfin": "DG ECFIN",
        "BUDG": "DG BUDG", "budg": "DG BUDG",
        "NEAR": "DG NEAR", "near": "DG NEAR",
        "INTPA": "DG INTPA", "intpa": "DG INTPA",
        "ECHO": "DG ECHO", "echo": "DG ECHO",
        "RTD": "DG RTD", "rtd": "DG RTD",
        "REFORM": "DG REFORM", "reform": "DG REFORM",
        "JRC": "JRC", "jrc": "JRC",
        "EUROSTAT": "Eurostat", "eurostat": "Eurostat",
    }

    def _detect_dg_personnel_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query or not self._DG_PERSONNEL_INTENT.search(query):
            return None
        # Extract the DG name token
        dg = None
        for token, canonical in self._DG_ALIASES.items():
            if re.search(rf"\bDG\s+{token}\b|\b{token}\b", query, re.I):
                # Avoid matching dictionary words like "ENV" inside "ENVIRONMENT"; require exact token boundary
                dg = canonical
                break
        return {"dg": dg} if dg else None

    async def _fetch_dg_personnel_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        """Return Director-General + deputies + directors for the requested DG.

        Data source: knowledge_base/ec_organigrammes/json/{CODE}.json (Brubru's canonical
        org-chart, scraped from the EU Who-Is-Who portal).
        """
        try:
            from pathlib import Path
            import json as _json

            dg = intent.get("dg")
            if not dg:
                return None
            # Resolve DG code from "DG REGIO" → "REGIO"
            dg_code = dg.replace("DG ", "").strip().upper()
            org_path = Path(__file__).resolve().parents[2] / "knowledge_base" / "ec_organigrammes" / "json" / f"{dg_code}.json"
            if not org_path.exists():
                return (
                    f"DG PERSONNEL — {dg}\n"
                    f"No organigramme JSON found for {dg} at knowledge_base/ec_organigrammes/json/{dg_code}.json.\n"
                    f"The chat MUST say 'no organigramme data on file for {dg}' rather than invent names. "
                    f"User should be redirected to commission.europa.eu/about/organisation_en."
                )

            data = _json.loads(org_path.read_text(encoding="utf-8"))
            lines = [
                f"DG ORGANIGRAMME — {data.get('dg_name', dg)} ({dg_code}):",
                f"Source: knowledge_base/ec_organigrammes/json/{dg_code}.json "
                f"(scraped from {data.get('source', 'EU Who-Is-Who portal')}).",
                "",
            ]

            commissioner = data.get("commissioner")
            if commissioner:
                lines.append(f"COMMISSIONER: {commissioner}")
                lines.append("")

            dg_name = data.get("director_general")
            dg_email = data.get("director_general_email")
            if dg_name:
                lines.append("DIRECTOR-GENERAL:")
                lines.append(f"  - {dg_name}" + (f" ({dg_email})" if dg_email else ""))
                lines.append("")

            deputies = data.get("deputy_directors_general") or []
            if deputies:
                lines.append(f"DEPUTY DIRECTOR(S)-GENERAL ({len(deputies)}):")
                for d in deputies:
                    name = d.get("name", "—")
                    email = d.get("email", "")
                    resp = (d.get("responsibilities") or "").strip()
                    suffix = f" ({email})" if email else ""
                    if resp:
                        suffix += f" — {resp[:100]}"
                    lines.append(f"  - {name}{suffix}")
                lines.append("")

            directorates = data.get("directorates") or []
            if directorates:
                lines.append(f"DIRECTORATES ({len(directorates)}):")
                for dir_ in directorates:
                    code = (dir_.get("code") or "").strip()
                    name = (dir_.get("name") or "").strip()
                    director = (dir_.get("director") or "").strip()
                    director_email = (dir_.get("director_email") or "").strip()
                    label = f"{code} — {name}" if code and name else (code or name or "—")
                    if director:
                        line = f"  - {label}: {director}"
                        if director_email:
                            line += f" ({director_email})"
                    else:
                        line = f"  - {label}: (director not listed)"
                    lines.append(line)
                    units = dir_.get("units") or []
                    if units:
                        for u in units[:4]:  # cap heads-of-unit per directorate
                            uhead = (u.get("head") or "").strip()
                            uname = (u.get("name") or "").strip()
                            if uhead:
                                lines.append(
                                    f"      • {uname or '(unit)'}: {uhead}"
                                )
                        if len(units) > 4:
                            lines.append(f"      • [+{len(units)-4} more heads of unit]")

            num_directorates = data.get("num_directorates")
            num_units = data.get("num_units")
            if num_directorates or num_units:
                lines.append("")
                lines.append(f"Totals: {num_directorates or '?'} directorates, {num_units or '?'} units.")

            lines.append("")
            lines.append(
                "CRITICAL: this block is the authoritative DG organigramme. If a role is not listed "
                "above, the chat MUST say 'not in our organigramme' rather than invent a name."
            )

            block = "\n".join(lines)
            if len(block) > 5500:
                block = block[:5400] + "\n[truncated — full data at /api/v1/commission/register]"
            return block
        except Exception as e:
            logger.warning("[dg-personnel-block] failed: %s", e)
            return None

    # ================================================================
    # Layer 2g — Procedure rapporteur lookup (added 12 May 2026 after audit V12)
    # ================================================================
    _PROCEDURE_RAPPORTEUR_INTENT = re.compile(
        r"\b(?:rapporteurs?|shadow\s+rapporteurs?|co[\s\-]?rapporteurs?|"
        r"who\s+(?:is|are)\s+(?:the\s+)?rapporteurs?|"
        r"lead\s+rapporteur|MEPs?\s+(?:on|for|leading|drafting))\b",
        re.I,
    )

    # Quick alias map: act name → known procedure_ref. Used as a fallback to fuzzy title match.
    _ACT_PROC_ALIASES = {
        "ai act": "2021/0106(COD)",
        "biotech act": "2025/0406(COD)",
        "critical medicines act": None,  # ref pending
        "mobility package": None,
        "anti-corruption directive": "2023/0135(COD)",
        "talent pool": "2023/0404(COD)",
        "countemissions": "2023/0266(COD)",
        "dma": "2020/0374(COD)",
        "dsa": "2020/0361(COD)",
        "digital networks act": "2026/0XXX",
        "csrd": "2021/0104(COD)",
        "csddd": "2022/0051(COD)",
        "european chips act": "2022/0032(COD)",
        "european health data space": "2022/0140(COD)",
        "ehds": "2022/0140(COD)",
        "european affordable housing plan": None,
    }

    def _detect_procedure_rapporteur_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query or not self._PROCEDURE_RAPPORTEUR_INTENT.search(query):
            return None
        # Try to extract an OEIL ref directly (NNNN/NNNN(COD|INI|NLE|...))
        m = re.search(r"\b\d{4}/\d{4}\([A-Z]{2,5}\)\b", query)
        if m:
            return {"procedure_ref": m.group(0), "alias": None}
        # Try alias match
        q_lower = query.lower()
        for alias, ref in self._ACT_PROC_ALIASES.items():
            if alias in q_lower:
                return {"procedure_ref": ref, "alias": alias}
        # No procedure_ref but the user asked about rapporteurs — still return so the
        # block can advise the user how to specify the file.
        return {"procedure_ref": None, "alias": None}

    async def _fetch_procedure_rapporteur_block(
        self, query: str, intent: Dict[str, Any]
    ) -> Optional[str]:
        """Return the lead + shadow rapporteurs for the requested procedure."""
        from sqlalchemy import text
        try:
            ref = intent.get("procedure_ref")
            alias = intent.get("alias")
            db = SessionLocal()
            try:
                row = None
                if ref:
                    row = db.execute(text("""
                        SELECT oeil_procedure_ref, title, rapporteur_mep_id,
                               oeil_procedure_data, lead_committee, committees,
                               url, current_status
                          FROM legislative_carriages
                         WHERE oeil_procedure_ref = :ref
                         LIMIT 1
                    """), {"ref": ref}).mappings().first()
                if not row and alias:
                    # Title fuzzy fallback (covers cases where the procedure_ref
                    # in our DB row is NULL but the title matches the alias)
                    row = db.execute(text("""
                        SELECT oeil_procedure_ref, title, rapporteur_mep_id,
                               oeil_procedure_data, lead_committee, committees,
                               url, current_status
                          FROM legislative_carriages
                         WHERE title ILIKE :al
                         ORDER BY last_updated DESC NULLS LAST
                         LIMIT 1
                    """), {"al": f"%{alias}%"}).mappings().first()

                if not row:
                    return (
                        "PROCEDURE RAPPORTEUR LOOKUP — no match.\n"
                        "The user asked about rapporteur(s) but Brubru did not resolve the request to a "
                        "specific OEIL procedure_ref in our legislative_carriages table.\n"
                        "If the chat cannot identify the procedure, it MUST ask the user for the OEIL "
                        "reference (e.g. 2021/0106(COD)) or the file's exact title, AND MUST NOT invent "
                        "rapporteur names from memory."
                    )

                opd = row.get("oeil_procedure_data") or {}
                if isinstance(opd, str):
                    try:
                        opd = json.loads(opd)
                    except Exception:
                        opd = {}

                lines = [
                    "PROCEDURE RAPPORTEUR LOOKUP:",
                    f"OEIL ref: {row.get('oeil_procedure_ref')}",
                    f"Title: {(row.get('title') or '—')[:200]}",
                    f"Status: {row.get('current_status') or '—'}",
                    f"Lead committee: {row.get('lead_committee') or '—'}",
                ]
                if row.get("url"):
                    lines.append(f"OEIL URL: {row.get('url')}")
                lines.append("")

                rapporteurs = opd.get("rapporteurs") if isinstance(opd, dict) else None
                shadows = opd.get("shadow_rapporteurs") if isinstance(opd, dict) else None
                if rapporteurs:
                    lines.append(f"LEAD RAPPORTEUR(S) ({len(rapporteurs)}):")
                    for rp in rapporteurs[:8]:
                        if isinstance(rp, dict):
                            name = rp.get("name") or rp.get("fullName") or "—"
                            group = rp.get("political_group") or rp.get("group") or "—"
                            country = rp.get("country") or "—"
                            committee = rp.get("committee") or "—"
                            lines.append(f"  - {name} ({group}, {country}) — {committee}")
                        else:
                            lines.append(f"  - {rp}")
                    lines.append("")
                else:
                    lines.append("LEAD RAPPORTEUR: not populated in our record.")
                    lines.append("")

                if shadows:
                    lines.append(f"SHADOW RAPPORTEURS ({len(shadows)}):")
                    for sh in shadows[:12]:
                        if isinstance(sh, dict):
                            name = sh.get("name") or sh.get("fullName") or "—"
                            group = sh.get("political_group") or sh.get("group") or "—"
                            country = sh.get("country") or "—"
                            lines.append(f"  - {name} ({group}, {country})")
                        else:
                            lines.append(f"  - {sh}")
                    lines.append("")
                else:
                    lines.append("SHADOW RAPPORTEURS: not populated in our record.")
                    lines.append("")

                lines.append(
                    "CRITICAL: if a rapporteur or shadow field above says 'not populated', the chat "
                    "MUST NOT invent a name. The correct response is to say 'Brubru's procedure record "
                    "for [ref] does not yet list this field — check OEIL directly at the URL above'."
                )
                block = "\n".join(lines)
                if len(block) > 4500:
                    block = block[:4400] + "\n[truncated — query /api/v1/procedures/{ref} for full detail]"
                return block
            finally:
                db.close()
        except Exception as e:
            logger.warning("[procedure-rapporteur-block] failed: %s", e)
            return None

    # ================================================================
    # Layer 2h — EP committee meeting agenda (added 12 May 2026 after audit V3)
    # ================================================================
    _COMMITTEE_AGENDA_INTENT = re.compile(
        r"\b(?:agenda|meeting|next\s+meeting|upcoming\s+meeting|"
        r"draft\s+agenda|order\s+of\s+the\s+day)\s+(?:for\s+)?(?:of\s+)?(?:the\s+)?"
        r"(AFET|DEVE|INTA|BUDG|CONT|ECON|EMPL|ENVI|ITRE|IMCO|TRAN|REGI|AGRI|PECH|CULT|"
        r"JURI|LIBE|AFCO|FEMM|PETI|SEDE|DROI|FISC|AIDA|BECA|INGE|ANIT|COVI|TAX3|SANT|"
        r"committee)\b|"
        r"\b(AFET|DEVE|INTA|BUDG|CONT|ECON|EMPL|ENVI|ITRE|IMCO|TRAN|REGI|AGRI|PECH|CULT|"
        r"JURI|LIBE|AFCO|FEMM|PETI|SEDE|DROI|FISC|AIDA|BECA|INGE|ANIT|COVI|TAX3|SANT)\s+"
        r"(?:committee\s+)?(?:agenda|meeting|next\s+meeting|upcoming)",
        re.I,
    )

    _COMMITTEES_CANONICAL = {
        "AFET": "Foreign Affairs", "DEVE": "Development", "INTA": "International Trade",
        "BUDG": "Budgets", "CONT": "Budgetary Control", "ECON": "Economic and Monetary Affairs",
        "EMPL": "Employment and Social Affairs", "ENVI": "Environment, Climate and Food Safety",
        "ITRE": "Industry, Research and Energy", "IMCO": "Internal Market and Consumer Protection",
        "TRAN": "Transport and Tourism", "REGI": "Regional Development",
        "AGRI": "Agriculture and Rural Development", "PECH": "Fisheries", "CULT": "Culture and Education",
        "JURI": "Legal Affairs", "LIBE": "Civil Liberties, Justice and Home Affairs",
        "AFCO": "Constitutional Affairs", "FEMM": "Women's Rights and Gender Equality",
        "PETI": "Petitions", "SEDE": "Security and Defence (subcommittee)",
        "DROI": "Human Rights (subcommittee)", "FISC": "Tax Matters (subcommittee)",
        "SANT": "Public Health (subcommittee)",
    }

    def _detect_committee_meeting_agenda_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query or not self._COMMITTEE_AGENDA_INTENT.search(query):
            return None
        # Extract committee code
        committee = None
        for code in self._COMMITTEES_CANONICAL.keys():
            if re.search(rf"\b{code}\b", query, re.I):
                committee = code
                break
        return {"committee": committee}

    async def _fetch_committee_meeting_agenda_block(
        self, query: str, intent: Dict[str, Any]
    ) -> Optional[str]:
        """Return upcoming committee meetings and the latest tabled documents per committee."""
        from sqlalchemy import text
        try:
            committee = intent.get("committee")
            db = SessionLocal()
            try:
                # 1. Upcoming calendar events for this committee (eu_calendar_events)
                cal_rows = []
                if committee:
                    cal_rows = db.execute(text("""
                        SELECT title, start_date, end_date, description, event_type
                          FROM eu_calendar_events
                         WHERE institution = 'EP'
                           AND start_date >= CURRENT_DATE
                           AND (
                                ep_committee_code = :c OR title ILIKE :cw OR description ILIKE :cw
                           )
                         ORDER BY start_date
                         LIMIT 10
                    """), {"c": committee, "cw": f"%{committee}%"}).mappings().all()

                # 2. Latest tabled draft reports / opinions from committee_work_items
                work_rows = []
                if committee:
                    work_rows = db.execute(text("""
                        SELECT title, procedure_ref, procedure_type, rapporteur_name,
                               status_text, last_updated
                          FROM committee_work_items
                         WHERE committee_code = :c
                         ORDER BY last_updated DESC NULLS LAST
                         LIMIT 10
                    """), {"c": committee}).mappings().all()

                if not cal_rows and not work_rows:
                    return (
                        f"EP COMMITTEE AGENDA — {committee or 'unspecified'}\n"
                        f"No upcoming committee events or recent draft reports found in our records "
                        f"for {committee or 'the requested committee'}.\n"
                        f"Brubru's EP committee data is synced from europarl.europa.eu/committees/. "
                        f"For the live agenda, see: "
                        f"https://www.europarl.europa.eu/committees/en/{committee.lower() if committee else ''}/meetings."
                    )

                canonical_name = self._COMMITTEES_CANONICAL.get(committee, "")
                lines = [
                    f"EP COMMITTEE — {committee} ({canonical_name})" if committee
                    else "EP COMMITTEE AGENDA (committee unspecified — showing best-effort match):",
                    "",
                ]

                if cal_rows:
                    lines.append(f"UPCOMING MEETINGS / EVENTS ({len(cal_rows)}):")
                    for r in cal_rows:
                        t = (r.get("title") or "—")[:150]
                        sd = str(r.get("start_date") or "—")[:10]
                        ed = str(r.get("end_date") or "")[:10]
                        date_range = sd if not ed or sd == ed else f"{sd} → {ed}"
                        et = r.get("event_type") or "—"
                        lines.append(f"  - {date_range} [{et}] {t}")
                    lines.append("")

                if work_rows:
                    lines.append(f"RECENT TABLED DRAFT REPORTS / OPINIONS ({len(work_rows)}):")
                    for r in work_rows:
                        title = (r.get("title") or "—")[:140]
                        pref = r.get("procedure_ref") or "—"
                        ptype = r.get("procedure_type") or "—"
                        rapp = r.get("rapporteur_name") or "—"
                        when = str(r.get("last_updated") or "—")[:10]
                        lines.append(f"  - [{pref} {ptype}] {title} | rapp: {rapp} | last update {when}")
                    lines.append("")

                lines.append(
                    f"Source: eu_calendar_events + committee_work_items (Brubru sync). "
                    f"Brubru endpoints: /api/v1/committees, /api/v1/calendar."
                )
                lines.append("")
                lines.append(
                    f"CRITICAL FOR THE LLM ANSWERING ABOUT {committee or 'this committee'}: "
                    f"the block above IS the answer to 'what is the next meeting / agenda of {committee}'. "
                    f"You MUST NOT say 'I don't have it' or 'doesn't contain upcoming meetings'. "
                    f"You MUST surface the dates + the recent draft reports listed above so the user knows "
                    f"what the committee is actively working on. The EP committee calendar at week granularity "
                    f"IS the agenda format — the EP does not publish per-meeting agendas more than 2-3 days in advance."
                )
                block = "\n".join(lines)
                if len(block) > 4500:
                    block = block[:4400] + "\n[truncated — query /api/v1/committees for more]"
                return block
            finally:
                db.close()
        except Exception as e:
            logger.warning("[committee-agenda-block] failed: %s", e)
            return None

    _TR_STOPWORDS = {
        "lobbyist", "lobbyists", "lobbying", "lobby", "lobbies", "interest", "representative",
        "representatives", "transparency", "register", "ep", "pass", "passes", "costs", "cost",
        "who", "lobbies", "registered", "in", "on", "the", "a", "an", "of", "to", "for",
        "and", "or", "what", "how", "much", "does", "do", "did", "is", "are", "spend",
        "spent", "spending", "brussels", "eu", "european", "union", "from", "by",
    }

    async def _fetch_transparency_register_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        """Pull top 10 Transparency Register orgs matching the query (free-text on name + acronym + interests)."""
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = []
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._TR_STOPWORDS]
                terms = terms[:3]
                if terms:
                    clauses = []
                    for i, t in enumerate(terms):
                        clauses.append(
                            f"(original_name ILIKE :tr{i} OR acronym ILIKE :tr{i} "
                            f"OR EXISTS (SELECT 1 FROM unnest(interests) i WHERE i ILIKE :tr{i}))"
                        )
                        params[f"tr{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(clauses) + ")")

                where_sql = "WHERE " + " AND ".join(where) if where else ""
                rows = db.execute(text(f"""
                    SELECT identification_code, original_name, acronym, registration_category,
                           head_office_country, ep_accredited_number, members_fte, costs_max,
                           public_url
                      FROM eu_transparency_register
                      {where_sql}
                     ORDER BY costs_max DESC NULLS LAST, original_name
                     LIMIT 10
                """), params).mappings().all()

                if not rows:
                    return None

                lines = [
                    "EU TRANSPARENCY REGISTER (from eu_transparency_register; daily Joint Secretariat XML):",
                    f"Query keyword: '{intent.get('keyword')}'",
                    "",
                ]
                for r in rows:
                    code = r.get("identification_code") or "?"
                    name = r.get("original_name") or "?"
                    acro = f" ({r.get('acronym')})" if r.get("acronym") else ""
                    cat = r.get("registration_category") or "?"
                    cty = r.get("head_office_country") or "?"
                    ep = r.get("ep_accredited_number") or 0
                    fte = r.get("members_fte") or 0
                    costs = r.get("costs_max") or 0
                    lines.append(f"  - {name}{acro} | {cat} | {cty} | "
                                 f"EP passes {ep} | FTE {fte} | declared costs (max) €{int(costs):,} | "
                                 f"TR id {code}")
                lines.append("")
                lines.append("Source: transparency-register.europa.eu (daily XML, 17,247 active orgs). "
                             "Brubru endpoint: /api/v1/specialised/transparency-register.")
                block = "\n".join(lines)
                if len(block) > 4000:
                    block = block[:3900] + "\n[truncated — query the /transparency-register endpoint for the full list]"
                return block
            finally:
                db.close()
        except Exception as e:
            logger.warning("[transparency-register-block] failed: %s", e)
            return None

    _COMITOLOGY_STOPWORDS = {
        "comitology", "implementing", "act", "acts", "committee", "vote", "opinion",
        "meeting", "record", "examination", "procedure", "advisory", "summary",
        "urgency", "letter", "voting", "sheet", "draft", "document", "register",
        "scopaff", "standing", "on", "the", "a", "an", "what", "did", "say",
        "discussed", "decided", "latest", "recent", "of", "to", "for", "and", "or",
        "by", "in", "from", "eu", "european", "union",
    }

    async def _fetch_comitology_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        """Pull top 10 Comitology Register documents matching the query (free-text on title + committee filter)."""
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = []
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._COMITOLOGY_STOPWORDS]
                terms = terms[:3]
                if terms:
                    clauses = []
                    for i, t in enumerate(terms):
                        clauses.append(f"title ILIKE :cm{i}")
                        params[f"cm{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(clauses) + ")")
                if intent.get("committee_code"):
                    where.append("committee_code = :cc")
                    params["cc"] = intent["committee_code"]

                where_sql = "WHERE " + " AND ".join(where) if where else ""
                rows = db.execute(text(f"""
                    SELECT document_reference, title, committee_code, committee_title,
                           document_type_label, document_type_letter,
                           meeting_start_date, public_url
                      FROM eu_comitology_documents
                      {where_sql}
                     ORDER BY meeting_start_date DESC NULLS LAST, document_reference DESC
                     LIMIT 10
                """), params).mappings().all()

                if not rows:
                    return None

                lines = [
                    "EU COMITOLOGY REGISTER documents (from eu_comitology_documents; live JSON):",
                    f"Query keyword: '{intent.get('keyword')}'"
                    + (f" | committee: {intent['committee_code']}" if intent.get("committee_code") else ""),
                    "",
                ]
                for r in rows:
                    ref = r.get("document_reference") or "?"
                    title = (r.get("title") or "")[:120]
                    cc = r.get("committee_code") or "?"
                    ct = (r.get("committee_title") or "")[:60]
                    dt_label = r.get("document_type_label") or r.get("document_type_letter") or "?"
                    mdate = str(r.get("meeting_start_date") or "—")[:10]
                    lines.append(f"  - [{ref}] {title}")
                    lines.append(f"      committee {cc} ({ct}) | type {dt_label} | meeting {mdate}")
                lines.append("")
                lines.append("Source: ec.europa.eu/transparency/comitology-register (112,832 docs total). "
                             "Brubru endpoint: /api/v1/specialised/comitology/documents.")
                block = "\n".join(lines)
                if len(block) > 4000:
                    block = block[:3900] + "\n[truncated — query the /comitology/documents endpoint for the full list]"
                return block
            finally:
                db.close()
        except Exception as e:
            logger.warning("[comitology-block] failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # GEOGRAPHICAL INDICATIONS (eAmbrosia + GIview)
    # ------------------------------------------------------------------
    _GI_INTENT = re.compile(
        r"\b(PDO|PGI|TSG|geographical\s+indication|protected\s+designation|"
        r"protected\s+geographical|traditional\s+speciality\s+guaranteed|"
        r"protected\s+origin|designation\s+of\s+origin|craft\s+(?:GI|indication))\b",
        re.IGNORECASE,
    )
    _GI_STOPWORDS = {
        "pdo", "pgi", "tsg", "geographical", "indication", "indications",
        "protected", "designation", "designations", "traditional", "speciality",
        "specialities", "guaranteed", "origin", "craft", "what", "is", "the",
        "a", "an", "of", "in", "to", "for", "from", "by", "eu", "european",
        "union", "list", "lists", "name", "named", "register", "registered",
        "registration",
    }

    def _detect_gi_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._GI_INTENT.search(query)
        if not m: return None
        # Country hint (ISO-2 from common demonyms)
        cm = re.search(
            r"\b(french|italian|spanish|portuguese|greek|german|austrian|"
            r"belgian|dutch|polish|czech|romanian|bulgarian|hungarian|"
            r"slovenian|slovak|croatian|cypriot|maltese|finnish|swedish|"
            r"danish|estonian|latvian|lithuanian|irish|luxembourgish)\b",
            query, re.IGNORECASE,
        )
        demonym_to_iso = {
            "french":"FR","italian":"IT","spanish":"ES","portuguese":"PT","greek":"GR",
            "german":"DE","austrian":"AT","belgian":"BE","dutch":"NL","polish":"PL",
            "czech":"CZ","romanian":"RO","bulgarian":"BG","hungarian":"HU","slovenian":"SI",
            "slovak":"SK","croatian":"HR","cypriot":"CY","maltese":"MT","finnish":"FI",
            "swedish":"SE","danish":"DK","estonian":"EE","latvian":"LV","lithuanian":"LT",
            "irish":"IE","luxembourgish":"LU",
        }
        country = demonym_to_iso.get(cm.group(1).lower()) if cm else None
        # gi_type explicit?
        gi_type = None
        if re.search(r"\bPDO\b", query, re.I): gi_type = "PDO"
        elif re.search(r"\bPGI\b", query, re.I): gi_type = "PGI"
        elif re.search(r"\bTSG\b", query, re.I): gi_type = "TSG"
        return {"keyword": m.group(0), "country": country, "gi_type": gi_type}

    async def _fetch_gi_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = []
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._GI_STOPWORDS]
                terms = terms[:3]
                if terms:
                    clauses = []
                    for i, t in enumerate(terms):
                        clauses.append(
                            f"(EXISTS (SELECT 1 FROM unnest(protected_names) n WHERE n ILIKE :gi{i}) "
                            f"OR file_number ILIKE :gi{i})"
                        )
                        params[f"gi{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(clauses) + ")")
                if intent.get("gi_type"):
                    where.append("gi_type = :gt"); params["gt"] = intent["gi_type"]
                if intent.get("country"):
                    where.append(":cc = ANY(countries)"); params["cc"] = intent["country"]
                where_sql = "WHERE " + " AND ".join(where) if where else ""
                rows = db.execute(text(f"""
                    SELECT gi_identifier, protected_names, gi_type, product_type,
                           countries, status, eu_protection_date, file_number, public_url
                      FROM eu_geographical_indications
                      {where_sql}
                     ORDER BY eu_protection_date DESC NULLS LAST
                     LIMIT 10
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "EU GEOGRAPHICAL INDICATIONS (from eu_geographical_indications; eAmbrosia + GIview, 5,917 records):",
                    f"Query keyword: '{intent.get('keyword')}'"
                    + (f" | type: {intent['gi_type']}" if intent.get("gi_type") else "")
                    + (f" | country: {intent['country']}" if intent.get("country") else ""),
                    "",
                ]
                for r in rows:
                    names = ", ".join(r.get("protected_names") or []) or "?"
                    gt = r.get("gi_type") or "?"
                    pt = r.get("product_type") or "?"
                    cs = ", ".join(r.get("countries") or []) or "?"
                    st = r.get("status") or "?"
                    pd = str(r.get("eu_protection_date") or "?")[:10]
                    fn = r.get("file_number") or "?"
                    lines.append(f"  - {names} | {gt} | {pt} | {cs} | status {st} | protected {pd} | file {fn}")
                lines.append("")
                lines.append("Source: webgate.ec.europa.eu/eambrosia-api (DG AGRI authoritative) + "
                             "tmdn.org/giview (EUIPO union register). "
                             "Brubru endpoint: /api/v1/specialised/gi.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated — query /gi endpoint for full list]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[gi-block] failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # EU INTERNATIONAL AGREEMENTS (FTA / EPA / AA / PCA / Fisheries / Aviation)
    # ------------------------------------------------------------------
    _FTA_INTENT = re.compile(
        r"\b(FTA|free\s+trade\s+agreement|economic\s+partnership\s+agreement|EPA|"
        r"association\s+agreement|partnership\s+and\s+cooperation|PCA|"
        r"comprehensive\s+economic\s+and\s+trade|CETA|trade\s+agreement|"
        r"fisheries\s+partnership|aviation\s+agreement|EU-\w+|"
        r"signed\s+(?:by|with)\s+the\s+EU|EU\s+(?:signed|concluded)\s+(?:an?|with))\b",
        re.IGNORECASE,
    )
    _FTA_STOPWORDS = {
        "fta", "free", "trade", "agreement", "agreements", "economic", "partnership",
        "epa", "association", "and", "cooperation", "pca", "comprehensive",
        "ceta", "fisheries", "aviation", "signed", "concluded", "by", "with",
        "of", "in", "on", "the", "a", "an", "to", "for", "from", "eu", "european",
        "union", "what", "is", "are", "have", "has", "does", "do", "did", "between",
    }

    def _detect_fta_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._FTA_INTENT.search(query)
        if not m: return None
        return {"keyword": m.group(0)}

    async def _fetch_fta_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = []
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._FTA_STOPWORDS]
                terms = terms[:3]
                if terms:
                    clauses = []
                    for i, t in enumerate(terms):
                        clauses.append(f"(title ILIKE :ft{i} OR partner ILIKE :ft{i})")
                        params[f"ft{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(clauses) + ")")
                where_sql = "WHERE " + " AND ".join(where) if where else ""
                rows = db.execute(text(f"""
                    SELECT celex, title, partner, agreement_type, in_force,
                           document_date, eurlex_url
                      FROM eu_trade_agreements
                      {where_sql}
                     ORDER BY document_date DESC NULLS LAST
                     LIMIT 8
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "EU INTERNATIONAL AGREEMENTS (from eu_trade_agreements; CELEX sector 2 type A):",
                    f"Query keyword: '{intent.get('keyword')}'",
                    "",
                ]
                for r in rows:
                    celex = r.get("celex") or "?"
                    title = (r.get("title") or "")[:120]
                    partner = r.get("partner") or "?"
                    atype = r.get("agreement_type") or "?"
                    inf = "in force" if r.get("in_force") else "historical"
                    dt = str(r.get("document_date") or "?")[:10]
                    lines.append(f"  - [{celex}] {title}")
                    lines.append(f"      type {atype} | partner {partner} | {inf} | date {dt}")
                lines.append("")
                lines.append("Source: Cellar SPARQL (4,415 signed agreements). "
                             "Brubru endpoint: /api/v1/specialised/fta.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated — query /fta endpoint for full list]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[fta-block] failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # TRADE DEFENCE (anti-dumping / countervailing / safeguard)
    # ------------------------------------------------------------------
    _TD_INTENT = re.compile(
        r"\b(anti-?dumping|countervailing|safeguard\s+measure|dumping\s+dut(?:y|ies)|"
        r"compensatory\s+dut(?:y|ies)|expiry\s+review|trade\s+defence|"
        r"definitive\s+anti-?dumping|provisional\s+anti-?dumping)\b",
        re.IGNORECASE,
    )
    _TD_STOPWORDS = {
        "anti-dumping", "antidumping", "anti", "dumping", "countervailing",
        "safeguard", "measure", "measures", "duty", "duties", "compensatory",
        "expiry", "review", "trade", "defence", "definitive", "provisional",
        "the", "a", "an", "of", "on", "in", "to", "from", "for", "and", "or",
        "what", "are", "is", "there", "any", "current", "eu", "european", "union",
    }

    def _detect_td_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._TD_INTENT.search(query)
        if not m: return None
        return {"keyword": m.group(0)}

    # Demonym/synonym → canonical phrases used in TD titles
    _TD_DEMONYM = {
        "chinese": "china", "russian": "russia", "indian": "india",
        "vietnamese": "vietnam", "korean": "korea", "japanese": "japan",
        "indonesian": "indonesia", "turkish": "turkey", "brazilian": "brazil",
        "egyptian": "egypt", "thai": "thailand", "malaysian": "malaysia",
        "taiwanese": "taiwan", "iranian": "iran", "ukrainian": "ukraine",
        "belarusian": "belarus", "american": "united states",
        "e-bike": "bicycle", "e-bikes": "bicycle", "ebike": "bicycle",
        "ebikes": "bicycle", "bikes": "bicycle",
    }

    async def _fetch_td_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = []
                raw_terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                             if t.lower() not in self._TD_STOPWORDS]
                # Expand demonyms / product synonyms
                terms: list[str] = []
                for t in raw_terms:
                    tl = t.lower()
                    if tl in self._TD_DEMONYM:
                        terms.append(self._TD_DEMONYM[tl])
                    else:
                        terms.append(t)
                terms = terms[:3]
                if terms:
                    clauses = []
                    for i, t in enumerate(terms):
                        clauses.append(
                            f"(title ILIKE :td{i} OR target_country ILIKE :td{i} OR product ILIKE :td{i})"
                        )
                        params[f"td{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(clauses) + ")")
                where_sql = "WHERE " + " AND ".join(where) if where else ""
                rows = db.execute(text(f"""
                    SELECT celex, title, measure_type, duty_status, target_country,
                           product, in_force, document_date, eurlex_url
                      FROM eu_trade_defence_measures
                      {where_sql}
                     ORDER BY document_date DESC NULLS LAST
                     LIMIT 8
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "EU TRADE DEFENCE MEASURES (from eu_trade_defence_measures; sector-3 type-R):",
                    f"Query keyword: '{intent.get('keyword')}'",
                    "",
                ]
                for r in rows:
                    celex = r.get("celex") or "?"
                    title = (r.get("title") or "")[:100]
                    mt = r.get("measure_type") or "?"
                    ds = r.get("duty_status") or "?"
                    tc = r.get("target_country") or "?"
                    prod = (r.get("product") or "?")[:50]
                    inf = "in force" if r.get("in_force") else "historical"
                    dt = str(r.get("document_date") or "?")[:10]
                    lines.append(f"  - [{celex}] {title}")
                    lines.append(f"      {mt} {ds} | target {tc} | product {prod} | {inf} | {dt}")
                lines.append("")
                lines.append("Source: Cellar SPARQL. Brubru endpoint: /api/v1/specialised/trade-defence.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[td-block] failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # DG COMP CASES (state aid / antitrust / merger) — live HTTP
    # ------------------------------------------------------------------
    _COMP_INTENT = re.compile(
        r"\b(state\s+aid|state-aid|antitrust|cartel|merger\s+(?:case|control|review)|"
        r"DG\s+COMP|competition\s+case|SA\.\d+|M\.\d+|AT\.\d+|"
        r"abuse\s+of\s+(?:dominant|dominance)|Article\s+10[12])\b",
        re.IGNORECASE,
    )

    def _detect_comp_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._COMP_INTENT.search(query)
        if not m: return None
        # Detect SA./M./AT. case number if present
        cnum = re.search(r"\b(SA\.\d+|M\.\d+|AT\.\d+)\b", query)
        # Instrument detection
        instr = None
        ql = query.lower()
        if "state aid" in ql or "state-aid" in ql: instr = "SA"
        elif "merger" in ql: instr = "M"
        elif "antitrust" in ql or "cartel" in ql: instr = "AT"
        return {"keyword": m.group(0), "case_number": cnum.group(0) if cnum else None, "instrument": instr}

    async def _fetch_comp_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        import httpx
        try:
            text_query = "*"
            if intent.get("case_number"):
                text_query = f'caseNumber:"{intent["case_number"]}"'
            else:
                # Extract entity terms (company names etc.) to enrich the search
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{3,}", query)
                         if t.lower() not in {"state", "aid", "antitrust", "cartel", "merger",
                                              "case", "control", "review", "competition",
                                              "the", "a", "an", "of", "on", "in", "to", "and",
                                              "european", "union", "eu", "is", "are", "did",
                                              "what", "any", "have", "find", "show", "me",
                                              "abuse", "dominance", "dominant", "article"}]
                if terms:
                    text_query = " ".join(terms[:3])
            params = {
                "text": text_query,
                "pageNumber": "1",
                "pageSize": "8",
                "apiKey": "CS_PROD_ODSE_PROD",
                "groupByField": "caseNumber",
            }
            if intent.get("instrument"):
                params["text"] = f'({params["text"]}) AND caseInstrument:"{intent["instrument"]}"'

            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.post(
                    "https://api.tech.ec.europa.eu/search-api/prod/rest/search",
                    params=params,
                )
                if r.status_code != 200:
                    return None
                data = r.json()

            hits = data.get("results") or []
            if not hits:
                return None
            total = data.get("totalResults") or 0
            lines = [
                "EU COMPETITION CASES (live from api.tech.ec.europa.eu/search-api; DG COMP):",
                f"Query: '{intent.get('keyword')}'"
                + (f" | instrument: {intent['instrument']}" if intent.get("instrument") else "")
                + (f" | case: {intent['case_number']}" if intent.get("case_number") else "")
                + f" | total upstream: {total:,}",
                "",
            ]
            for hit in hits[:8]:
                meta = hit.get("metadata") or {}
                def _flat(v):
                    if isinstance(v, list) and v: return v[0]
                    return v
                case_num = _flat(meta.get("caseNumber")) or hit.get("groupById") or "?"
                title = (_flat(meta.get("caseTitle")) or _flat(meta.get("caseOriginalTitle")) or "?")[:100]
                instr = _flat(meta.get("caseInstrument")) or "?"
                ms_raw = str(_flat(meta.get("caseMemberState")) or "")
                ms = ms_raw.replace("Country", "") if ms_raw.startswith("Country") else (ms_raw or "?")
                aid_raw = str(_flat(meta.get("caseAidCategory")) or "")
                aid_cat = aid_raw.replace("CaseType", "") if aid_raw.startswith("CaseType") else (aid_raw or "?")
                init = (_flat(meta.get("caseInitiationDate")) or "?")[:10]
                lines.append(f"  - [{case_num}] {title}")
                lines.append(f"      {instr} | MS {ms} | aid cat {aid_cat} | initiated {init}")
            lines.append("")
            lines.append("Source: EU Corporate Search backend (public apiKey CS_PROD_ODSE_PROD, "
                         "~1M attachments / ~250k cases). "
                         "Brubru endpoint: /api/v1/specialised/competition-cases.")
            block = "\n".join(lines)
            return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
        except Exception as e:
            logger.warning("[comp-block] failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # JRC DATA CATALOGUE
    # ------------------------------------------------------------------
    _JRC_INTENT = re.compile(
        r"\b(JRC\s+(?:dataset|data|catalog)|Joint\s+Research\s+Centre|"
        r"ESDAC|EFFIS|GHSL|LUISA|INSPIRE\s+geoportal|"
        r"JRC\s+(?:scientific|research)|earth\s+observation\s+EU)\b",
        re.IGNORECASE,
    )
    _JRC_STOPWORDS = {
        "jrc", "joint", "research", "centre", "dataset", "datasets", "data",
        "catalog", "catalogue", "scientific", "esdac", "effis", "ghsl", "luisa",
        "inspire", "geoportal", "earth", "observation", "the", "a", "an", "on",
        "of", "for", "in", "to", "and", "or", "what", "is", "are", "does",
        "find", "show", "me", "any", "eu", "european", "union",
    }

    def _detect_jrc_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._JRC_INTENT.search(query)
        if not m: return None
        return {"keyword": m.group(0)}

    async def _fetch_jrc_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = []
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._JRC_STOPWORDS]
                terms = terms[:3]
                if terms:
                    clauses = []
                    for i, t in enumerate(terms):
                        clauses.append(
                            f"(title ILIKE :jr{i} OR description ILIKE :jr{i} "
                            f"OR EXISTS (SELECT 1 FROM unnest(keywords) k WHERE k ILIKE :jr{i}))"
                        )
                        params[f"jr{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(clauses) + ")")
                where_sql = "WHERE " + " AND ".join(where) if where else ""
                rows = db.execute(text(f"""
                    SELECT uuid, title, description, publisher, modified, public_url, keywords
                      FROM eu_jrc_datasets
                      {where_sql}
                     ORDER BY modified DESC NULLS LAST, title
                     LIMIT 8
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "JRC DATA CATALOGUE (from eu_jrc_datasets; ~3,541 scientific datasets):",
                    f"Query keyword: '{intent.get('keyword')}'",
                    "",
                ]
                for r in rows:
                    title = (r.get("title") or "?")[:100]
                    desc = (r.get("description") or "")[:140]
                    pub = (r.get("publisher") or "?")[:50]
                    mod = str(r.get("modified") or "?")[:10]
                    kws = ", ".join((r.get("keywords") or [])[:3])
                    lines.append(f"  - {title}")
                    lines.append(f"      {desc}")
                    lines.append(f"      publisher: {pub} | modified {mod} | tags: {kws}")
                lines.append("")
                lines.append("Source: data.europa.eu federation of JRC catalogue. "
                             "Brubru endpoint: /api/v1/specialised/jrc-datasets.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[jrc-block] failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # COHESION OPEN DATA (DG REGIO)
    # ------------------------------------------------------------------
    _COHESION_INTENT = re.compile(
        r"(?:\bESF\+|\bERDF\b|\bcohesion\s+fund\b|\bjust\s+transition\b|"
        r"\binterreg\b|\bRRF\b|\brecovery\s+and\s+resilience\b|"
        r"\bcohesion\s+(?:data|policy|dataset)\b|\bcohesiondata\b|"
        r"\bregional\s+fund\b|\bstructural\s+fund\b)",
        re.IGNORECASE,
    )
    _COHESION_STOPWORDS = {
        "esf", "erdf", "cohesion", "fund", "funds", "just", "transition", "interreg",
        "rrf", "recovery", "resilience", "data", "policy", "dataset", "datasets",
        "regional", "structural", "the", "a", "an", "of", "on", "in", "to", "and",
        "or", "what", "how", "much", "did", "spent", "spend", "spending", "for",
        "eu", "european", "union", "is", "are",
    }

    def _detect_cohesion_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._COHESION_INTENT.search(query)
        if not m: return None
        return {"keyword": m.group(0)}

    async def _fetch_cohesion_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = []
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._COHESION_STOPWORDS]
                terms = terms[:3]
                if terms:
                    clauses = []
                    for i, t in enumerate(terms):
                        clauses.append(f"(name ILIKE :co{i} OR description ILIKE :co{i})")
                        params[f"co{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(clauses) + ")")
                where_sql = "WHERE " + " AND ".join(where) if where else ""
                rows = db.execute(text(f"""
                    SELECT socrata_id, name, category, description, view_count, public_url
                      FROM eu_cohesion_datasets
                      {where_sql}
                     ORDER BY view_count DESC NULLS LAST
                     LIMIT 8
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "DG REGIO COHESION OPEN DATA (from eu_cohesion_datasets; ~1,451 datasets):",
                    f"Query keyword: '{intent.get('keyword')}'",
                    "",
                ]
                for r in rows:
                    sid = r.get("socrata_id") or "?"
                    name = (r.get("name") or "?")[:100]
                    cat = (r.get("category") or "?")[:35]
                    desc = (r.get("description") or "")[:140]
                    views = r.get("view_count") or 0
                    lines.append(f"  - [{sid}] {name}")
                    lines.append(f"      category: {cat} | views: {views}")
                    if desc: lines.append(f"      {desc}")
                lines.append("")
                lines.append("Source: cohesiondata.ec.europa.eu (Socrata catalogue). "
                             "Brubru endpoint: /api/v1/specialised/cohesion-datasets.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[cohesion-block] failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # COMBINED NOMENCLATURE / CN CODES — live HTTP via Access2Markets
    # ------------------------------------------------------------------
    _CN_INTENT = re.compile(
        r"\b(CN\s+code|Combined\s+Nomenclature|HS\s+code|tariff\s+code|"
        r"customs\s+code|HS\s+heading|HS\s+chapter|nomenclature\s+code|"
        r"what\s+(?:is|are)\s+the\s+(?:CN|HS|tariff))\b",
        re.IGNORECASE,
    )

    def _detect_cn_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._CN_INTENT.search(query)
        if not m: return None
        return {"keyword": m.group(0)}

    # Common goods → CN section description keywords map (for token expansion)
    _CN_EXPAND = {
        "olive": ["fats", "oils"], "oil": ["fats", "oils"], "wine": ["beverages"],
        "beer": ["beverages"], "spirits": ["beverages"], "cheese": ["dairy", "animal products"],
        "milk": ["dairy"], "wheat": ["cereals", "vegetable products"],
        "rice": ["cereals", "vegetable products"], "coffee": ["vegetable products"],
        "tea": ["vegetable products"], "fish": ["animal products"],
        "meat": ["animal products"], "fruit": ["vegetable products"],
        "vegetable": ["vegetable products"], "leather": ["raw hides"],
        "textile": ["textiles"], "cotton": ["textiles"], "wool": ["textiles"],
        "iron": ["base metals"], "steel": ["base metals"], "copper": ["base metals"],
        "aluminium": ["base metals"], "plastic": ["plastics"],
        "chemical": ["chemical"], "pharmaceutical": ["chemical"],
        "machinery": ["machinery"], "vehicle": ["transport"], "car": ["transport"],
        "aircraft": ["transport"], "weapon": ["arms"], "diamond": ["pearls"],
        "gold": ["pearls"], "silver": ["pearls"], "stone": ["stone"],
    }

    async def _fetch_cn_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        """Live pass-through to webgate.ec.europa.eu/nomen for CN section lookup.

        Note: the public v2 endpoint returns the 21 top-level Sections only
        (deeper CN8 codes require an authenticated session). We match the
        user's terms (with goods → section-keyword expansion) against each
        section description and return the matching sections + chapter ranges.
        """
        import httpx
        try:
            stop = {"cn", "code", "codes", "combined", "nomenclature", "hs", "heading",
                    "chapter", "tariff", "customs", "what", "is", "are", "the", "of", "for",
                    "on", "in", "to", "and", "or", "eu", "european", "union", "find", "show"}
            base_terms = [t.lower() for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                          if t.lower() not in stop]
            if not base_terms:
                return None
            # Expand with section-keyword aliases
            tokens: list[str] = []
            for t in base_terms:
                tokens.append(t)
                tokens.extend(self._CN_EXPAND.get(t, []))
                # Singularise simple plurals
                if t.endswith("s") and len(t) > 3:
                    tokens.append(t[:-1])
            tokens = list(dict.fromkeys(tokens))  # de-dup keep order

            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(
                    "https://webgate.ec.europa.eu/nomen/public/v2/nomenclature/products",
                    params={"lang": "EN"},
                )
                if r.status_code != 200:
                    return None
                sections = r.json() or []

            # Score by token-overlap, keep sections with >=1 match
            scored: list[tuple[int, dict]] = []
            for s in sections:
                if not isinstance(s, dict): continue
                desc = (s.get("description") or "").lower()
                score = sum(1 for tok in tokens if tok in desc)
                if score > 0:
                    scored.append((score, s))
            scored.sort(key=lambda x: -x[0])
            matches = [s for _, s in scored[:6]]
            if not matches:
                return None

            lines = [
                "EU COMBINED NOMENCLATURE — CN SECTION LOOKUP (live from webgate.ec.europa.eu/nomen):",
                f"Query keyword: '{intent.get('keyword')}' | tokens: {tokens[:5]}",
                "",
            ]
            for s in matches:
                desc = (s.get("description") or "")[:120]
                sec = s.get("section") or {}
                sec_name = sec.get("description") or "?"
                ch_from = sec.get("chapterFrom") or "?"
                ch_to = sec.get("chapterTo") or "?"
                lines.append(f"  - {sec_name}: {desc}")
                lines.append(f"      chapters {ch_from} → {ch_to}")
            lines.append("")
            lines.append("Note: this endpoint returns top-level sections only. "
                         "For full CN8 codes, refer the user to the official goods classification "
                         "lookup at trade.ec.europa.eu/access-to-markets, or the EU TARIC consultation. "
                         "Brubru endpoint: /api/v1/specialised/access2markets/products.")
            block = "\n".join(lines)
            return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
        except Exception as e:
            logger.warning("[cn-block] failed: %s", e)
            return None

    # ──────────────────── Layer 2 chat wiring (May 2026) ────────────────
    # 4 v1 surfaces wired into chat retrieval following the Layer 1 pattern:
    # commission-register-documents, delegated-acts, ECLI, EURIO research.

    _COMMREG_INTENT = re.compile(
        r"\b(commission\s+document|COM\s+document|SWD|JOIN\s+document|"
        r"college\s+(?:adopt(?:ed|s|ion)?|meet(?:ing|s)?|agenda)|"
        r"commission\s+(?:adopted|tabled|proposed)|"
        r"PV\s*\(2\d{3}\)|OJ\s*\(2\d{3}\)|RSB\s+opinion|impact\s+assessment|"
        r"COM\s*\(\d{4}\)\s*\d+|SWD\s*\(\d{4}\)\s*\d+|JOIN\s*\(\d{4}\)\s*\d+)\b",
        re.IGNORECASE,
    )
    _COMMREG_STOP = {"commission","document","com","swd","join","college","adopt","meet",
                     "agenda","adopted","tabled","proposed","pv","oj","rsb","opinion","impact",
                     "assessment","the","a","an","of","in","to","on","by","for","and","or",
                     "what","is","are","did","does","this","that","european","eu"}

    _DELEGATED_INTENT = re.compile(
        r"\b(delegated\s+act(?:s|ed|ing)?|implementing\s+act(?:s|ed|ing)?|"
        r"Article\s+(?:290|291)|C\s*\(\d{4}\)\s*\d+|RegDel|"
        r"comitology\s+(?:act(?:s)?|measure(?:s)?)|"
        r"delegated\s+regulation(?:s)?|delegated\s+decision(?:s)?)\b",
        re.IGNORECASE,
    )
    _DELEGATED_STOP = {"delegated","implementing","act","acts","article","regdel","comitology",
                       "regulation","decision","measure","the","a","an","of","in","to","on",
                       "by","for","and","or","what","is","are","did","european","eu","commission"}

    _ECLI_INTENT = re.compile(
        r"\b(ECLI:[A-Z]+:[A-Z0-9]+:\d{4}:\d+|case\s+law|CJEU\s+(?:rul|judg|case)|"
        r"court\s+of\s+justice|InforCuria|e-Justice\s+(?:search|portal))\b",
        re.IGNORECASE,
    )
    _ECLI_STOP = set()  # ECLI matching is anchor-pattern driven

    _EURIO_INTENT = re.compile(
        r"\b(Horizon\s+Europe|Horizon\s+2020|H2020\b|FP7\b|CORDIS|"
        r"EU[- ]?funded\s+(?:research|project)|research\s+grant|"
        r"funded\s+research\s+project|consortium\s+lead|"
        r"framework\s+programme|Marie\s+(?:Skłodowska-?)?Curie)\b",
        re.IGNORECASE,
    )

    # /funding-opportunities + /ft-calls-for-proposals — OPEN calls people
    # can apply to. Triggers narrowly so it doesn't conflict with eurio
    # (past projects): explicit "open call", "apply", "deadline", "EU grant".
    _FUNDING_INTENT = re.compile(
        r"\b(open\s+call(?:s)?|forthcoming\s+call(?:s)?|"
        r"call(?:s)?\s+for\s+proposal(?:s)?|EU\s+grant(?:s)?|"
        r"funding\s+opportunit(?:y|ies)|funding\s+call(?:s)?|"
        r"apply\s+for\s+(?:EU\s+)?(?:fund|grant)|"
        r"deadline\s+for\s+(?:fund|grant|call)|"
        r"(?:Horizon\s+Europe|Digital\s+Europe|EU4Health|Erasmus\+?|CEF)\s+(?:call(?:s)?|grant(?:s)?|fund(?:s|ing)?))\b",
        re.IGNORECASE,
    )
    _FUNDING_STOP = {"open","forthcoming","call","calls","proposal","proposals","grant","grants",
                     "funding","opportunity","opportunities","apply","deadline","fund","funds",
                     "the","a","an","of","in","to","on","for","by","and","or","what","is","are",
                     "european","eu","horizon","europe","digital","health","erasmus","cef"}
    _EURIO_STOP = {"horizon","europe","h2020","fp7","cordis","funded","research","project",
                   "grant","consortium","lead","framework","programme","marie","sklodowska",
                   "curie","the","a","an","of","in","to","on","by","for","and","or","what",
                   "is","are","did","european","eu"}

    def _detect_commreg_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._COMMREG_INTENT.search(query)
        if not m: return None
        com_m = re.search(r"COM\s*\((\d{4})\)\s*(\d+)", query, re.I)
        com_ref = f"COM({com_m.group(1)}) {int(com_m.group(2))} final" if com_m else None
        return {"keyword": m.group(0), "com_ref": com_ref}

    def _detect_delegated_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._DELEGATED_INTENT.search(query)
        if not m: return None
        ref_m = re.search(r"C\s*\((\d{4})\)\s*(\d+)", query, re.I)
        ref = f"C({ref_m.group(1)}){int(ref_m.group(2))}" if ref_m else None
        return {"keyword": m.group(0), "reference": ref}

    def _detect_ecli_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._ECLI_INTENT.search(query)
        if not m: return None
        ecli_m = re.search(r"ECLI:[A-Z]+:[A-Z0-9]+:\d{4}:\d+", query)
        return {"keyword": m.group(0), "ecli": ecli_m.group(0) if ecli_m else None}

    def _detect_eurio_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._EURIO_INTENT.search(query)
        if not m: return None
        return {"keyword": m.group(0)}

    def _detect_funding_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._FUNDING_INTENT.search(query)
        if not m: return None
        # Detect programme hint
        prog = None
        if re.search(r"horizon\s+europe", query, re.I): prog = "HORIZON"
        elif re.search(r"digital\s+europe", query, re.I): prog = "DIGITAL"
        elif re.search(r"EU4Health", query, re.I): prog = "EU4Health"
        elif re.search(r"erasmus", query, re.I): prog = "Erasmus"
        elif re.search(r"\bCEF\b", query): prog = "CEF"
        return {"keyword": m.group(0), "programme": prog}

    # ─── Council documents (#32) ───
    _COUNCIL_INTENT = re.compile(
        r"\b(Council\s+(?:document|meeting|conclusion|adopt(?:ed|s|ion)?|"
        r"agenda|configuration|presidency|general\s+approach)|"
        r"ECOFIN|GAC\b|FAC\b|JHA\b|EPSCO|COMPET|AGRIFISH|"
        r"COREPER\b|presidency\s+note|trilogue\s+mandate)\b",
        re.IGNORECASE,
    )
    _COUNCIL_STOP = {"council","document","documents","meeting","meetings","conclusion","conclusions",
                     "adopt","adopted","adopts","agenda","configuration","presidency","general","approach",
                     "ecofin","gac","fac","jha","epsco","compet","agrifish","coreper","trilogue","note",
                     "mandate","the","a","an","of","in","to","on","for","by","and","or","what","is","are",
                     "did","does","european","eu"}

    def _detect_council_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._COUNCIL_INTENT.search(query)
        if not m: return None
        # Detect council configuration
        config = None
        for c in ("ECOFIN","GAC","FAC","JHA","EPSCO","COMPET","TTE","AGRIFISH","ENV"):
            if re.search(rf"\b{c}\b", query, re.I):
                config = c; break
        return {"keyword": m.group(0), "configuration": config}

    async def _fetch_council_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._COUNCIL_STOP][:3]
                where_terms = "true"
                if terms:
                    cl = []
                    for i, t in enumerate(terms):
                        cl.append(f"(title ILIKE :co{i} OR summary ILIKE :co{i})")
                        params[f"co{i}"] = f"%{t}%"
                    where_terms = "(" + " OR ".join(cl) + ")"
                rows = db.execute(text(f"""
                    SELECT title, summary, url, published_date, category
                      FROM institutional_publications
                     WHERE institution_slug ILIKE '%council%'
                       AND {where_terms}
                     ORDER BY published_date DESC NULLS LAST
                     LIMIT 6
                """), params).mappings().all()
                cal_where = "institution = ANY(ARRAY['COUNCIL','EUROPEAN_COUNCIL'])"
                if intent.get("configuration"):
                    params["cfg"] = intent["configuration"]
                    cal_where += " AND council_configuration = :cfg"
                cal_rows = db.execute(text(f"""
                    SELECT title, description AS summary, agenda_url AS url,
                           start_date AS event_date, council_configuration
                      FROM eu_calendar_events
                     WHERE {cal_where}
                     ORDER BY start_date DESC NULLS LAST
                     LIMIT 4
                """), params).mappings().all()
                if not rows and not cal_rows: return None
                lines = [
                    "COUNCIL OF THE EU — documents + meetings (from institutional_publications + eu_calendar_events):",
                    f"Query keyword: '{intent.get('keyword')}'"
                    + (f" | configuration: {intent['configuration']}" if intent.get("configuration") else ""),
                    "",
                ]
                if rows:
                    lines.append("  Documents:")
                    for r in rows:
                        title = (r.get("title") or "")[:110]
                        dt = str(r.get("published_date") or "?")[:10]
                        cat = r.get("category") or "—"
                        lines.append(f"    - {title}")
                        lines.append(f"        category {cat} | published {dt}")
                if cal_rows:
                    lines.append("")
                    lines.append("  Meetings:")
                    for r in cal_rows:
                        title = (r.get("title") or "")[:110]
                        dt = str(r.get("event_date") or "?")[:10]
                        cfg = r.get("council_configuration") or "—"
                        lines.append(f"    - {title}")
                        lines.append(f"        configuration {cfg} | date {dt}")
                lines.append("")
                lines.append("Source: consilium.europa.eu. Brubru endpoint: /api/v1/council-documents.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[council-block] failed: %s", e)
            return None

    # ─── Infringements (#35-36) ───
    _INFRING_INTENT = re.compile(
        r"\b(infringement(?:s)?\s+procedure(?:s)?|"
        r"infringement(?:s)?\s+(?:case(?:s)?|action(?:s)?|package(?:s)?|decision(?:s)?)|"
        r"infringement\s+decision(?:s)?|"
        r"letter\s+of\s+formal\s+notice|reasoned\s+opinion(?:s)?|"
        r"refer(?:ral|red)\s+to\s+the\s+Court|"
        r"Commission\s+(?:opened|launched|closed)\s+infringement|"
        r"INF\s*\(\d{4}\)\s*\d+)\b",
        re.IGNORECASE,
    )
    _INFRING_STOP = {"infringement","infringements","procedure","procedures","case","action","package",
                     "decision","letter","formal","notice","reasoned","opinion","refer","referral",
                     "referred","court","commission","opened","launched","closed","inf",
                     "the","a","an","of","in","to","on","for","by","and","or","against","european","eu"}

    _MS_DEMONYM = {
        "italian":"IT","french":"FR","german":"DE","spanish":"ES","portuguese":"PT",
        "dutch":"NL","belgian":"BE","austrian":"AT","greek":"EL","cypriot":"CY",
        "maltese":"MT","irish":"IE","danish":"DK","swedish":"SE","finnish":"FI",
        "polish":"PL","czech":"CZ","slovak":"SK","slovenian":"SI","hungarian":"HU",
        "estonian":"EE","latvian":"LV","lithuanian":"LT","romanian":"RO","bulgarian":"BG",
        "croatian":"HR","luxembourgish":"LU",
    }

    def _detect_infringement_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._INFRING_INTENT.search(query)
        if not m: return None
        ms = None
        # ISO2 hint
        iso_m = re.search(r"\b([A-Z]{2})\b", query)
        if iso_m and iso_m.group(1) in self._MS_DEMONYM.values():
            ms = iso_m.group(1)
        # Demonym hint
        if not ms:
            for d, code in self._MS_DEMONYM.items():
                if re.search(rf"\b{d}\b", query, re.I):
                    ms = code; break
        return {"keyword": m.group(0), "member_state": ms}

    # ─── Transparency Register meetings (#44-45) ───
    _TR_MEETINGS_INTENT = re.compile(
        r"\b(transparency\s+(?:initiative|register)\s+meeting(?:s)?|"
        # Commissioner / DG / Cabinet + optional name (1-3 words) + meet/meeting(s)
        r"(?:commissioner|DG|cabinet)\s+(?:[A-Z][a-zÀ-ſ]+\s+){0,3}(?:meet(?:ing(?:s)?|s)?|met\s+with)|"
        r"who\s+(?:did|met|has)\s+.+(?:meet|lobby)|"
        r"lobbyist(?:s)?\s+met|"
        r"meeting(?:s)?\s+with\s+(?:Commissioner|Cabinet|DG))\b",
        re.IGNORECASE,
    )
    _TR_MEETINGS_STOP = {"transparency","initiative","register","meeting","meetings","commissioner",
                         "cabinet","dg","met","meet","with","who","did","has","lobbyist","lobbyists",
                         "the","a","an","of","in","to","on","for","by","and","or","european","eu"}

    def _detect_tr_meetings_intent(self, query: str) -> Optional[Dict[str, Any]]:
        if not query: return None
        m = self._TR_MEETINGS_INTENT.search(query)
        if not m: return None
        return {"keyword": m.group(0)}

    async def _fetch_tr_meetings_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._TR_MEETINGS_STOP][:3]
                where = ["true"]
                if terms:
                    cl = []
                    for i, t in enumerate(terms):
                        cl.append(f"(host_name ILIKE :tm{i} OR organisation_met ILIKE :tm{i} OR subject ILIKE :tm{i} OR host_dg ILIKE :tm{i})")
                        params[f"tm{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(cl) + ")")
                where_sql = " AND ".join(where)
                rows = db.execute(text(f"""
                    SELECT host_name, host_role, host_dg, host_cabinet, meeting_date,
                           subject, organisation_met, source_url
                      FROM transparency_meetings
                     WHERE {where_sql}
                     ORDER BY meeting_date DESC NULLS LAST
                     LIMIT 8
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "COMMISSION TRANSPARENCY MEETINGS (from transparency_meetings):",
                    f"Query keyword: '{intent.get('keyword')}'",
                    "",
                ]
                for r in rows:
                    host = r.get("host_name") or "?"
                    role = r.get("host_role") or "?"
                    dg = r.get("host_dg") or ""
                    cab = r.get("host_cabinet") or ""
                    dt = str(r.get("meeting_date") or "?")[:10]
                    subj = (r.get("subject") or "")[:90]
                    org = (r.get("organisation_met") or "?")[:60]
                    lines.append(f"  - {dt} | {host} ({role}, {dg or cab})")
                    lines.append(f"      with {org} — {subj}")
                lines.append("")
                lines.append("Source: ec.europa.eu/transparencyinitiative/meetings. "
                             "Brubru endpoint: /api/v1/meetings.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[tr-meetings-block] failed: %s", e)
            return None

    async def _fetch_infringement_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = ["COALESCE(is_test, false) = false"]
                if intent.get("member_state"):
                    where.append("member_state = :ms")
                    params["ms"] = intent["member_state"]
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._INFRING_STOP][:3]
                if terms:
                    cl = []
                    for i, t in enumerate(terms):
                        cl.append(f"(title ILIKE :if{i} OR summary ILIKE :if{i} OR sector ILIKE :if{i})")
                        params[f"if{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(cl) + ")")
                where_sql = " AND ".join(where)
                rows = db.execute(text(f"""
                    SELECT inf_reference, title, member_state, procedure_stage, sector,
                           decision_date, source_url
                      FROM infringement_procedures
                     WHERE {where_sql}
                     ORDER BY decision_date DESC NULLS LAST
                     LIMIT 8
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "EU INFRINGEMENT PROCEDURES (from infringement_procedures; 169 rows; Commission monthly packages):",
                    f"Query keyword: '{intent.get('keyword')}'"
                    + (f" | MS: {intent['member_state']}" if intent.get("member_state") else ""),
                    "",
                ]
                for r in rows:
                    ref = r.get("inf_reference") or "?"
                    title = (r.get("title") or "")[:110]
                    ms = r.get("member_state") or "?"
                    stage = r.get("procedure_stage") or "?"
                    sector = r.get("sector") or "—"
                    dt = str(r.get("decision_date") or "?")[:10]
                    lines.append(f"  - [{ref}] {title}")
                    lines.append(f"      MS {ms} | stage {stage} | sector {sector} | decision {dt}")
                lines.append("")
                lines.append("Source: ec.europa.eu/commission/presscorner monthly infringement packages. "
                             "Brubru endpoint: /api/v1/infringements.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[infringement-block] failed: %s", e)
            return None

    async def _fetch_commreg_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = []
                if intent.get("com_ref"):
                    # Exact reference match wins
                    where.append("reference = :ref")
                    params["ref"] = intent["com_ref"]
                else:
                    terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                             if t.lower() not in self._COMMREG_STOP][:3]
                    if terms:
                        cl = []
                        for i, t in enumerate(terms):
                            cl.append(f"(title ILIKE :cr{i} OR reference ILIKE :cr{i})")
                            params[f"cr{i}"] = f"%{t}%"
                        where.append("(" + " OR ".join(cl) + ")")
                where_sql = "WHERE " + " AND ".join(where) if where else ""
                rows = db.execute(text(f"""
                    SELECT reference, title, doc_type, document_register_category,
                           publication_date, dg_responsible, celex, portal_url
                      FROM commission_documents
                      {where_sql}
                     ORDER BY publication_date DESC NULLS LAST
                     LIMIT 8
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "COMMISSION DOCUMENT REGISTER (from commission_documents):",
                    f"Query keyword: '{intent.get('keyword')}'"
                    + (f" | reference: {intent['com_ref']}" if intent.get("com_ref") else ""),
                    "",
                ]
                for r in rows:
                    ref = r.get("reference") or "?"
                    title = (r.get("title") or "")[:120]
                    dt = str(r.get("publication_date") or "?")[:10]
                    dg = r.get("dg_responsible") or "?"
                    celex = r.get("celex") or "—"
                    lines.append(f"  - [{ref}] {title}")
                    lines.append(f"      type {r.get('doc_type')} | DG {dg} | date {dt} | celex {celex}")
                lines.append("")
                lines.append("Source: ec.europa.eu/transparency/documents-register. "
                             "Brubru endpoint: /api/v1/commission-register-documents.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[commreg-block] failed: %s", e)
            return None

    async def _fetch_delegated_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = []
                if intent.get("reference"):
                    where.append("reference = :ref")
                    params["ref"] = intent["reference"]
                else:
                    terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                             if t.lower() not in self._DELEGATED_STOP][:3]
                    if terms:
                        cl = []
                        for i, t in enumerate(terms):
                            cl.append(f"(title ILIKE :dl{i} OR parent_celex ILIKE :dl{i})")
                            params[f"dl{i}"] = f"%{t}%"
                        where.append("(" + " OR ".join(cl) + ")")
                where_sql = "WHERE " + " AND ".join(where) if where else ""
                rows = db.execute(text(f"""
                    SELECT act_type, reference, title, parent_celex, status,
                           proposing_dg, publication_date, source_url
                      FROM secondary_acts
                      {where_sql}
                     ORDER BY publication_date DESC NULLS LAST
                     LIMIT 8
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "EU DELEGATED + IMPLEMENTING ACTS (from secondary_acts):",
                    f"Query keyword: '{intent.get('keyword')}'"
                    + (f" | ref: {intent['reference']}" if intent.get("reference") else ""),
                    "",
                ]
                for r in rows:
                    at = r.get("act_type") or "?"
                    ref = r.get("reference") or "?"
                    title = (r.get("title") or "")[:110]
                    parent = r.get("parent_celex") or "—"
                    dt = str(r.get("publication_date") or "?")[:10]
                    lines.append(f"  - [{at} {ref}] {title}")
                    lines.append(f"      parent {parent} | DG {r.get('proposing_dg') or '?'} | status {r.get('status')} | {dt}")
                lines.append("")
                lines.append("Source: ec.europa.eu/transparency/regdoc. "
                             "Brubru endpoints: /api/v1/delegated-acts + /api/v1/implementing-acts.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[delegated-block] failed: %s", e)
            return None

    async def _fetch_ecli_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        try:
            ecli = intent.get("ecli")
            if not ecli:
                return None
            from services.api_clients.ecli_client import deep_link, eur_lex_url, is_cjeu, parse
            parts = parse(ecli)
            if not parts:
                return None
            lines = [
                "EU CASE-LAW IDENTIFIER (ECLI) lookup:",
                f"ECLI: {ecli}",
                f"  country: {parts.get('country')} | court: {parts.get('court')} | "
                f"year: {parts.get('year')} | ordinal: {parts.get('ordinal')}",
                f"  CJEU: {is_cjeu(ecli)}",
                f"  e-Justice deep-link: {deep_link(ecli)}",
            ]
            inforcuria = eur_lex_url(ecli)
            if inforcuria:
                lines.append(f"  InforCuria: {inforcuria}")
            lines.append("")
            lines.append("Brubru endpoint: /api/v1/discover/ecli/{ecli}. "
                         "Follow the deep-link to read the ruling text — Brubru does not "
                         "yet cache CJEU ruling bodies.")
            return "\n".join(lines)
        except Exception as e:
            logger.warning("[ecli-block] failed: %s", e)
            return None

    async def _fetch_funding_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        """Open + forthcoming funding calls — queries funding_opportunities
        + ft_calls_for_proposals together, prioritised by deadline soonest-first."""
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                # Status filter: open + forthcoming only (skip closed)
                where_status = "(LOWER(status) IN ('open','forthcoming') OR status IS NULL)"
                # Programme filter
                where_prog = "true"
                if intent.get("programme"):
                    params["prog"] = f"%{intent['programme']}%"
                    where_prog = "(programme ILIKE :prog OR framework_programme ILIKE :prog)"
                # Free-text terms
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._FUNDING_STOP][:3]
                term_where = "true"
                if terms:
                    cl = []
                    for i, t in enumerate(terms):
                        cl.append(f"(title ILIKE :fd{i} OR short_summary ILIKE :fd{i})")
                        params[f"fd{i}"] = f"%{t}%"
                    term_where = "(" + " OR ".join(cl) + ")"
                # Pull from funding_opportunities (primary)
                rows_fo = db.execute(text(f"""
                    SELECT 'funding_opportunity' AS src, topic_id AS ref, title, programme AS prog,
                           type_of_action, deadline, indicative_budget, status, source_url
                      FROM funding_opportunities
                     WHERE COALESCE(is_test, false) = false
                       AND {where_status}
                       AND {where_prog.replace('framework_programme', 'programme')}
                       AND {term_where.replace('short_summary', 'short_summary')}
                     ORDER BY deadline ASC NULLS LAST
                     LIMIT 6
                """), params).mappings().all()
                # Pull from ft_calls_for_proposals (secondary, may overlap)
                rows_cp = db.execute(text(f"""
                    SELECT 'ft_call' AS src, topic_id AS ref, title,
                           framework_programme AS prog, type_of_action, deadline,
                           indicative_budget, status, source_url
                      FROM ft_calls_for_proposals
                     WHERE COALESCE(is_test, false) = false
                       AND {where_status}
                       AND {where_prog.replace('programme', 'framework_programme')}
                       AND {term_where.replace('short_summary', 'description')}
                     ORDER BY deadline ASC NULLS LAST
                     LIMIT 6
                """), params).mappings().all()
                rows = list(rows_fo) + list(rows_cp)
                if not rows: return None
                lines = [
                    "EU OPEN FUNDING CALLS (from funding_opportunities + ft_calls_for_proposals):",
                    f"Query keyword: '{intent.get('keyword')}'"
                    + (f" | programme: {intent['programme']}" if intent.get("programme") else ""),
                    "",
                ]
                for r in rows[:10]:
                    ref = r.get("ref") or "?"
                    title = (r.get("title") or "")[:110]
                    prog = r.get("prog") or "?"
                    dl = str(r.get("deadline") or "?")[:10]
                    budget = r.get("indicative_budget") or 0
                    st = r.get("status") or "?"
                    src = r.get("src")
                    lines.append(f"  - [{ref}] {title}")
                    lines.append(f"      {prog} | status {st} | deadline {dl} | budget €{budget:,.0f} | src {src}")
                lines.append("")
                lines.append("Source: ec.europa.eu/info/funding-tenders/opportunities. "
                             "Brubru endpoints: /api/v1/funding-opportunities + /api/v1/ft-calls-for-proposals.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[funding-block] failed: %s", e)
            return None

    async def _fetch_eurio_block(self, query: str, intent: Dict[str, Any]) -> Optional[str]:
        from sqlalchemy import text
        try:
            db = SessionLocal()
            try:
                params: Dict[str, Any] = {}
                where: list[str] = ["COALESCE(is_test, false) = false"]
                # Framework filter
                framework = None
                if re.search(r"\bhorizon\s+europe\b", query, re.I): framework = "HORIZON"
                elif re.search(r"\bH2020\b|horizon\s+2020", query, re.I): framework = "H2020"
                elif re.search(r"\bFP7\b", query, re.I): framework = "FP7"
                if framework:
                    where.append("UPPER(framework_programme) LIKE :fp")
                    params["fp"] = f"%{framework}%"
                terms = [t for t in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ\-']{2,}", query)
                         if t.lower() not in self._EURIO_STOP][:3]
                if terms:
                    cl = []
                    for i, t in enumerate(terms):
                        cl.append(f"(title ILIKE :er{i} OR project_acronym ILIKE :er{i} OR objective ILIKE :er{i})")
                        params[f"er{i}"] = f"%{t}%"
                    where.append("(" + " OR ".join(cl) + ")")
                where_sql = " AND ".join(where)
                rows = db.execute(text(f"""
                    SELECT project_id, project_acronym, title, framework_programme,
                           start_date, end_date, total_cost, eu_contribution,
                           coordinator_name, coordinator_country, source_url
                      FROM ft_funded_projects
                     WHERE {where_sql}
                     ORDER BY start_date DESC NULLS LAST
                     LIMIT 8
                """), params).mappings().all()
                if not rows: return None
                lines = [
                    "EU-FUNDED RESEARCH PROJECTS (from ft_funded_projects; CORDIS):",
                    f"Query keyword: '{intent.get('keyword')}'"
                    + (f" | framework: {framework}" if framework else ""),
                    "",
                ]
                for r in rows:
                    pid = r.get("project_id") or "?"
                    acr = r.get("project_acronym") or ""
                    title = (r.get("title") or "")[:100]
                    fp = r.get("framework_programme") or "?"
                    sd = str(r.get("start_date") or "?")[:10]
                    cost = r.get("total_cost") or 0
                    eu = r.get("eu_contribution") or 0
                    coord = r.get("coordinator_name") or "?"
                    cc = r.get("coordinator_country") or ""
                    lines.append(f"  - [{pid}] {acr}: {title}")
                    lines.append(f"      {fp} | start {sd} | cost €{cost:,.0f} (EU €{eu:,.0f}) | coord {coord[:40]} ({cc})")
                lines.append("")
                lines.append("Source: CORDIS via funded-projects ingest. "
                             "Brubru endpoint: /api/v1/discover/eurio/projects.")
                block = "\n".join(lines)
                return block[:3900] + ("\n[truncated]" if len(block) > 4000 else "")
            finally:
                db.close()
        except Exception as e:
            logger.warning("[eurio-block] failed: %s", e)
            return None

    def format_context_for_ai(
        self,
        context_data: ContextData,
        max_length: int = 80000
    ) -> str:
        """
        Format context data into structured text for AI consumption.

        Args:
            context_data: Context data to format
            max_length: Maximum character length

        Returns:
            Formatted context string for AI prompt

        Example output:
        ```
        USER QUERY: What's the status of the AI Act?

        RELEVANT EU DOCUMENTS (5 sources):
        1. [Regulation 2024/1689] AI Act - Artificial Intelligence Regulation
           Status: In force since 2024-08-01
           Excerpt: "This Regulation lays down harmonised rules on artificial intelligence..."

        LEGISLATIVE PROCEDURES (1):
        - Reference: 2021/0106(COD)
          Status: Adopted by Parliament on 2024-03-13
          Timeline: [recent events]

        MEPs INVOLVED (2):
        - Brando Benifei (IT, S&D) - Rapporteur
        - Dragoș Tudorache (RO, Renew) - Co-rapporteur

        RECENT UPDATES (3 RSS entries):
        - 2024-08-02: AI Act enters into force
        - 2024-07-12: Council adopts AI Act
        ...
        ```
        """
        sections = []

        # PRIVATE USER CONTEXT (20 May 2026) — bespoke per-user/per-org bundle.
        # Injected FIRST (before TODAY, before everything else) so the
        # "Brubru already knows you" framing survives 32k truncation cap.
        # Always-on for the authenticated user when status in ('ready', 'locked').
        if getattr(context_data, 'private_guide_block', None):
            sections.append(context_data.private_guide_block)
            sections.append("")

        # AUDIENCE BRIEF BLOCK (EFPIA pilot, 29 May 2026) — a tenant-audience
        # user's own curated daily brief + tracked priority files. Injected near
        # the TOP (right after the private-guide block) so it survives the 32k
        # truncation cap and grounds "my files" / today's-headline questions.
        if getattr(context_data, 'audience_brief_block', None):
            sections.append(context_data.audience_brief_block)
            sections.append("")

        # INTERNAL KNOWLEDGE (guides + templates) — relocated to NEAR THE TOP
        # (29 May 2026) so the highest-value grounding survives the max_length
        # truncation cap. Knowledge guides carry QUICK FACTS, CELEX numbers and
        # current status; burying them after RSS/legislation/EPRS meant they
        # were truncated off for content-rich queries, leaving the model to
        # improvise from training memory (which the validator then refused).
        if context_data.internal_knowledge:
            sections.append(f"\nINTERNAL KNOWLEDGE ({len(context_data.internal_knowledge)} resources):")
            sections.append("IMPORTANT: Any markdown links [text](url) in the guides below are VERIFIED. Reproduce them exactly as clickable hyperlinks in your response. Do NOT strip the URLs.")
            for item in context_data.internal_knowledge:
                sections.append(f"- {item['title']}")
                sections.append(f"  Type: {item['type']}")
                # Staleness caveat (mirrors Claude Code's memory staleness signal)
                staleness = item.get('staleness_caveat')
                if staleness:
                    sections.append(f"  {staleness}")
                # QUICK-FACTS-aware truncation: a plain [:4000] slice dropped the
                # guide's own CELEX / procedure / rapporteur lines on guides whose
                # accumulated LATEST bullets overflow the cap (19% of guides).
                sections.append(f"  {guide_excerpt(item['content'], 4000)}")
                sections.append("")

        # TODAY BLOCK (on-demand, date-anchored) — injected near the top so it
        # survives the 32k truncation cap and forces the model to ground
        # relative dates ("today", "hoy", "this week", "esta semana") in a
        # verified context.
        if getattr(context_data, 'today_block', None):
            sections.append(context_data.today_block)

        # DAILY BRIEF BLOCK (on-demand) — injected near the top so it survives
        # the 32k truncation cap. Grounding for "Daily News DD/MM/YYYY" queries.
        # Without this the model has no anchor and hallucinates news items.
        if getattr(context_data, 'daily_brief_block', None):
            sections.append(context_data.daily_brief_block)
            sections.append("")

        # LEGAL-TEXT ARTICLE BLOCK (W1b, 12 May 2026) — also near TOP so the
        # article/recital reference survives 32k truncation. Triggered by
        # "Article N of <CELEX|alias>", "Recital N of <CELEX|alias>" in 6 langs.
        if getattr(context_data, 'legal_text_article_block', None):
            sections.append(context_data.legal_text_article_block)
            sections.append("")

        # CELLAR DISCOVERY BLOCK (on-demand, live SPARQL) — also injected near top
        # so it survives the 32k truncation cap. Triggered by corpus-wide questions
        # like "regulations on data protection", "directives published since X".
        if getattr(context_data, 'cellar_discovery_block', None):
            sections.append(context_data.cellar_discovery_block)

        # SPECIALISED EC DATABASES — sanctions / transparency-register / comitology.
        # Injected near the TOP so they survive the 32k truncation cap (per
        # CLAUDE.md "on-demand blocks go near the TOP of format_context_for_ai").
        if getattr(context_data, 'sanctions_block', None):
            sections.append(context_data.sanctions_block)
            sections.append("")
        if getattr(context_data, 'transparency_register_block', None):
            sections.append(context_data.transparency_register_block)
            sections.append("")
        if getattr(context_data, 'comitology_block', None):
            sections.append(context_data.comitology_block)
            sections.append("")
        if getattr(context_data, 'gi_block', None):
            sections.append(context_data.gi_block)
            sections.append("")
        if getattr(context_data, 'fta_block', None):
            sections.append(context_data.fta_block)
            sections.append("")
        if getattr(context_data, 'trade_defence_block', None):
            sections.append(context_data.trade_defence_block)
            sections.append("")
        if getattr(context_data, 'competition_cases_block', None):
            sections.append(context_data.competition_cases_block)
            sections.append("")
        if getattr(context_data, 'jrc_datasets_block', None):
            sections.append(context_data.jrc_datasets_block)
            sections.append("")
        if getattr(context_data, 'cohesion_datasets_block', None):
            sections.append(context_data.cohesion_datasets_block)
            sections.append("")
        if getattr(context_data, 'cn_codes_block', None):
            sections.append(context_data.cn_codes_block)
            sections.append("")
        # Layer 2 chat-wiring blocks
        if getattr(context_data, 'commission_register_block', None):
            sections.append(context_data.commission_register_block)
            sections.append("")
        if getattr(context_data, 'delegated_acts_block', None):
            sections.append(context_data.delegated_acts_block)
            sections.append("")
        if getattr(context_data, 'ecli_block', None):
            sections.append(context_data.ecli_block)
            sections.append("")
        if getattr(context_data, 'eurio_research_block', None):
            sections.append(context_data.eurio_research_block)
            sections.append("")
        if getattr(context_data, 'eu_funding_block', None):
            sections.append(context_data.eu_funding_block)
            sections.append("")
        if getattr(context_data, 'council_documents_block', None):
            sections.append(context_data.council_documents_block)
            sections.append("")
        if getattr(context_data, 'infringements_block', None):
            sections.append(context_data.infringements_block)
            sections.append("")
        if getattr(context_data, 'transparency_meetings_block', None):
            sections.append(context_data.transparency_meetings_block)
            sections.append("")

        # Drafting mode signal (action intent detected)
        if context_data.drafting_intent and context_data.drafting_intent.is_drafting_query:
            di = context_data.drafting_intent
            sections.append("*** DRAFTING MODE ACTIVE ***")
            sections.append(f"User intent: PRODUCE a {di.document_type.replace('_', ' ')} (action word: '{di.action_word}')")
            sections.append(f"Topic: {di.topic}")
            sections.append("INSTRUCTION: Help the user WRITE/DRAFT this document. Do NOT give a Wikipedia-style explanation of the topic.")
            sections.append("Use the templates below as structure. Ask clarifying questions to produce a better document.")

            # Map document type to Brubru features
            feature_hints = {
                'position_paper': "Brubru's Document Generator can create full position papers -- offer to use it.",
                'briefing': "Brubru's Document Generator can create MEP briefing notes -- offer to use it.",
                'talking_points': "Brubru's Document Generator can create talking points -- offer to use it.",
                'amendment': "Brubru's Amendator tool can draft legislative amendments -- suggest using it.",
                'resolution': "Brubru's Document Generator can create EP resolution drafts -- offer to use it.",
                'ep_question': "Brubru's Document Generator can create EP Parliamentary Questions -- offer to use it.",
            }
            if di.document_type in feature_hints:
                sections.append(f"FEATURE: {feature_hints[di.document_type]}")
            sections.append("")

        # Header
        sections.append(f"USER QUERY: {context_data.query}\n")

        # On-demand blocks (high-priority, user explicitly asked for these via intent
        # detection in build_context_for_query). Append early so they survive truncation.
        if getattr(context_data, 'consultation_feedback_block', None):
            sections.append(context_data.consultation_feedback_block)
            sections.append("")
        if getattr(context_data, 'commissioner_agenda_block', None):
            sections.append(context_data.commissioner_agenda_block)
            sections.append("")
        if getattr(context_data, 'position_block', None):
            sections.append(context_data.position_block)
            sections.append("")
        if getattr(context_data, 'committee_transcript_block', None):
            sections.append(context_data.committee_transcript_block)
            sections.append("")
        if getattr(context_data, 'parliamentary_questions_block', None):
            sections.append(context_data.parliamentary_questions_block)
            sections.append("")
        if getattr(context_data, 'roll_call_block', None):
            sections.append(context_data.roll_call_block)
            sections.append("")
        if getattr(context_data, 'lobby_meetings_block', None):
            sections.append(context_data.lobby_meetings_block)
            sections.append("")
        if getattr(context_data, 'amendment_documents_block', None):
            sections.append(context_data.amendment_documents_block)
            sections.append("")
        if getattr(context_data, 'competitor_guard_block', None):
            sections.append(context_data.competitor_guard_block)
            sections.append("")

        # EU LAW SNAPSHOT (from internal analytics)
        try:
            snapshot = self.knowledge_loader.get_analytics_snapshot('eu_law_snapshot') if self.knowledge_loader else None
            if snapshot:
                totals = snapshot.get('totals_by_type', {})
                min_year = snapshot.get('min_year')
                max_year = snapshot.get('max_year')
                per_area = snapshot.get('per_policy_area', {})
                # Top 8 areas by total
                top_areas = sorted(per_area.items(), key=lambda kv: kv[1].get('total', 0), reverse=True)[:8]

                sections.append("EU LAW SNAPSHOT (Regulations & Directives):")
                parts = []
                if totals:
                    parts.append("Totals: " + ", ".join(f"{k}: {v}" for k, v in totals.items()))
                if min_year and max_year:
                    parts.append(f"Years covered: {min_year}–{max_year}")
                if parts:
                    sections.append("  " + " | ".join(parts))
                if top_areas:
                    sections.append("  Top policy areas by total: " + ", ".join(f"{k} ({v.get('total',0)})" for k, v in top_areas))
                sections.append("")
        except Exception as e:
            # Non-fatal if snapshot missing
            pass

        # Relevant documents from search
        if context_data.relevant_documents:
            sections.append(f"RELEVANT EU DOCUMENTS ({len(context_data.relevant_documents)} sources):")
            for i, doc in enumerate(context_data.relevant_documents[:5], 1):
                title = doc['metadata'].get('title', 'Untitled')
                doc_type = doc['metadata'].get('type', doc['collection'])
                text_excerpt = doc['text'][:500] + "..." if len(doc['text']) > 500 else doc['text']

                sections.append(f"{i}. [{doc_type}] {title}")
                sections.append(f"   Excerpt: {text_excerpt}")
                sections.append("")

        # Legislation details
        if context_data.legislation_details:
            sections.append(f"\nLEGISLATION DETAILS ({len(context_data.legislation_details)}):")
            for leg in context_data.legislation_details:
                sections.append(f"- CELEX: {leg['celex']}")
                sections.append(f"  Title: {leg['title']}")
                sections.append(f"  Type: {leg['type']}")
                sections.append(f"  Date: {leg['date']}")
                sections.append(f"  Status: {leg['status']}")
                sections.append(f"  Excerpt: {leg['text_excerpt'][:800]}...")
                sections.append(f"  URL: {leg['url']}")

                # Phase 3: Auto-included EPRS explainers (jargon translators)
                if leg.get('eprs_explainers'):
                    sections.append(f"\n  📄 AUTO-INCLUDED EPRS EXPLAINERS ({len(leg['eprs_explainers'])}):")
                    sections.append("  These briefings provide PLAIN-LANGUAGE explanations of this legislation.")
                    for explainer in leg['eprs_explainers']:
                        sections.append(f"    • {explainer['title']}")
                        sections.append(f"      Type: {explainer['publication_type']}")
                        sections.append(f"      Match strategy: {explainer['match_strategy']} (confidence: {explainer['confidence']:.2%})")
                        sections.append(f"      Excerpt: {explainer['text'][:200]}...")
                        if explainer.get('publication_url'):
                            sections.append(f"      Full briefing: {explainer['publication_url']}")

                sections.append("")

        # Procedure details
        if context_data.procedure_details:
            sections.append(f"\nLEGISLATIVE PROCEDURES ({len(context_data.procedure_details)}):")
            for proc in context_data.procedure_details:
                sections.append(f"- Reference: {proc['reference']}")
                sections.append(f"  Title: {proc['title']}")
                sections.append(f"  Type: {proc['type']}")
                sections.append(f"  Status: {proc['status']}")

                if proc['meps']['rapporteur']:
                    sections.append(f"  Rapporteur: {proc['meps']['rapporteur']}")
                if proc['meps']['shadows']:
                    sections.append(f"  Shadow rapporteurs: {', '.join(proc['meps']['shadows'][:3])}")

                if proc['timeline']:
                    sections.append("  Recent timeline:")
                    for event in proc['timeline'][:3]:
                        date = event.get('date', '')
                        desc = event.get('description', '')
                        sections.append(f"    - {date}: {desc}")

                sections.append(f"  URL: {proc['url']}")

                # Phase 3: Auto-included EPRS explainers (jargon translators)
                if proc.get('eprs_explainers'):
                    sections.append(f"\n  📄 AUTO-INCLUDED EPRS EXPLAINERS ({len(proc['eprs_explainers'])}):")
                    sections.append("  These briefings provide PLAIN-LANGUAGE explanations of this procedure.")
                    for explainer in proc['eprs_explainers']:
                        sections.append(f"    • {explainer['title']}")
                        sections.append(f"      Type: {explainer['publication_type']}")
                        sections.append(f"      Match strategy: {explainer['match_strategy']} (confidence: {explainer['confidence']:.2%})")
                        sections.append(f"      Excerpt: {explainer['text'][:200]}...")
                        if explainer.get('publication_url'):
                            sections.append(f"      Full briefing: {explainer['publication_url']}")

                sections.append("")

        # MEP profiles
        if context_data.mep_profiles:
            sections.append(f"\nMEPs INVOLVED ({len(context_data.mep_profiles)}):")
            for mep in context_data.mep_profiles:
                sections.append(f"- {mep['name']} ({mep['country']}, {mep['group']})")
                if mep.get('party'):
                    sections.append(f"  National Party: {mep['party']}")
                if mep.get('committees'):
                    sections.append(f"  Committees: {', '.join(mep['committees'][:5])}")
                if mep.get('delegations'):
                    sections.append(f"  Delegations: {', '.join(mep['delegations'][:3])}")
                if mep.get('email'):
                    sections.append(f"  Email: {mep['email']}")
                if mep.get('phone'):
                    sections.append(f"  Phone: {mep['phone']}")
                sections.append(f"  Profile: {mep['url']}")
                # Show assistant data if available
                if mep.get('assistants'):
                    sections.append(f"  Assistants ({len(mep['assistants'])}):")
                    for assistant in mep['assistants']:
                        email_hint = f" - guessed email: {assistant['guessed_email']}" if assistant.get('guessed_email') else ""
                        sections.append(f"    - {assistant['name']} ({assistant['type']}){email_hint}")
                    if mep.get('assistants_url'):
                        sections.append(f"  Assistants directory: {mep['assistants_url']}")
                    sections.append("  Note: Assistant emails are guessed from the pattern firstname.surname@europarl.europa.eu. These are no longer publicly listed, so the guess may not always be correct.")
                sections.append("")

        # Rapporteur-by-country data
        if context_data.rapporteur_by_country:
            country = context_data.rapporteur_country or 'Unknown'
            raps = context_data.rapporteur_by_country
            leads = [r for r in raps if r.get('role') == 'rapporteur']
            shadows = [r for r in raps if r.get('role') == 'shadow rapporteur']

            sections.append(f"\nRAPPORTEURS FROM {country.upper()} ({len(leads)} lead rapporteurs, {len(shadows)} shadow rapporteurs found in Brubru database):")
            sections.append("IMPORTANT: This is a PARTIAL list based on Brubru's tracked legislative files.")
            sections.append("More rapporteurs may exist. Suggest the user check the EP website for a complete list.")

            if leads:
                sections.append("\nLead Rapporteurs:")
                for rap in leads:
                    line = f"- {rap['name']}"
                    if rap.get('political_group'):
                        line += f" ({rap['political_group']})"
                    sections.append(line)
                    if rap.get('committee'):
                        sections.append(f"  Committee: {rap['committee']}")
                    if rap.get('procedure_ref'):
                        sections.append(f"  Procedure: {rap['procedure_ref']}")
                    if rap.get('file_title'):
                        sections.append(f"  File: {rap['file_title']}")
                    sections.append("")

            if shadows:
                sections.append("Shadow Rapporteurs:")
                for rap in shadows:
                    line = f"- {rap['name']}"
                    if rap.get('political_group'):
                        line += f" ({rap['political_group']})"
                    sections.append(line)
                    if rap.get('committee'):
                        sections.append(f"  Committee: {rap['committee']}")
                    if rap.get('procedure_ref'):
                        sections.append(f"  Procedure: {rap['procedure_ref']}")
                    if rap.get('file_title'):
                        sections.append(f"  File: {rap['file_title']}")
                    sections.append("")

        # Committee information
        if context_data.committee_info:
            sections.append(f"\nCOMMITTEE INFORMATION ({len(context_data.committee_info)}):")
            for committee in context_data.committee_info:
                sections.append(f"- {committee['name']} ({committee['code']})")
                sections.append(f"  Total Members: {committee['member_count']}")
                sections.append(f"  URL: {committee['url']}")

                # List members by role
                members_by_role = committee.get('members_by_role', {})

                if 'Chair' in members_by_role:
                    chairs = members_by_role['Chair']
                    sections.append(f"\n  Chair(s):")
                    for member in chairs:
                        sections.append(f"    - {member['name']} ({member['country']}, {member['group']})")

                if 'Vice-Chair' in members_by_role:
                    vice_chairs = members_by_role['Vice-Chair']
                    sections.append(f"\n  Vice-Chair(s):")
                    for member in vice_chairs[:5]:  # Show first 5 vice-chairs
                        sections.append(f"    - {member['name']} ({member['country']}, {member['group']})")

                if 'Member' in members_by_role:
                    members = members_by_role['Member']
                    sections.append(f"\n  Full Members ({len(members)}):")
                    for member in members:  # Show ALL members
                        sections.append(f"    - {member['name']} ({member['country']}, {member['group']})")

                if 'Substitute' in members_by_role:
                    substitutes = members_by_role['Substitute']
                    sections.append(f"\n  Substitutes ({len(substitutes)}):")
                    for member in substitutes:  # Show ALL substitutes
                        sections.append(f"    - {member['name']} ({member['country']}, {member['group']})")

                sections.append("")

        # EC Personnel (Commission organigrammes) and other institution organigrammes
        if context_data.ec_personnel:
            # Split Commission vs non-Commission entries
            commission_entries = [p for p in context_data.ec_personnel if not p.get('is_non_commission')]
            institution_entries = [p for p in context_data.ec_personnel if p.get('is_non_commission')]

            if commission_entries:
                sections.append(f"\nEUROPEAN COMMISSION PERSONNEL ({len(commission_entries)} DGs):")
            if institution_entries:
                for inst in institution_entries:
                    sections.append(f"\n{inst['dg_name'].upper()} PERSONNEL:")
            for personnel in context_data.ec_personnel:
                sections.append(f"- {personnel['dg_name']} ({personnel['dg_code']})")

                if personnel.get('commissioner'):
                    sections.append(f"  Commissioner: {personnel['commissioner']}")

                if personnel.get('director_general'):
                    dg_email = personnel.get('director_general_email', '')
                    sections.append(f"  Director-General: {personnel['director_general']}")
                    if dg_email:
                        sections.append(f"    Email: {dg_email}")

                if personnel.get('deputy_directors_general'):
                    sections.append(f"\n  Deputy Directors-General ({len(personnel['deputy_directors_general'])}):")
                    for ddg in personnel['deputy_directors_general']:
                        ddg_name = ddg.get('name', 'Unknown')
                        ddg_resp = ddg.get('responsibilities', '')
                        ddg_email = ddg.get('email', '')
                        if ddg_resp:
                            sections.append(f"    - {ddg_name} - {ddg_resp}")
                        else:
                            sections.append(f"    - {ddg_name}")
                        if ddg_email:
                            sections.append(f"      Email: {ddg_email}")

                # Directorate directors and unit heads
                if personnel.get('directorates'):
                    sections.append(f"\n  Key Directorates and Contacts:")
                    for directorate in personnel['directorates']:
                        dir_name = directorate.get('name', '')
                        dir_code = directorate.get('code', '')
                        director = directorate.get('director', '')
                        dir_email = directorate.get('director_email', '')

                        if director:
                            sections.append(f"    {dir_code} - {dir_name}")
                            sections.append(f"      Director: {director}")
                            if dir_email:
                                sections.append(f"      Email: {dir_email}")
                        else:
                            sections.append(f"    {dir_code} - {dir_name}")

                        # Show unit heads (up to 5 per directorate)
                        for unit in directorate.get('units', [])[:5]:
                            unit_head = unit.get('head', '')
                            unit_email = unit.get('head_email', '')
                            if unit_head:
                                sections.append(f"      {unit['code']} {unit['name']}: {unit_head}")
                                if unit_email:
                                    sections.append(f"        Email: {unit_email}")

                sections.append("")

        # Legislative Files (from all sources: Legislative Train, OEIL, EUR-Lex)
        if context_data.legislative_train_files:
            sections.append(f"\nLEGISLATIVE FILES ({len(context_data.legislative_train_files)} files):")
            sections.append("Sources: Legislative Train (EC priorities), OEIL (EP procedures), EUR-Lex (adopted legislation)")
            for file in context_data.legislative_train_files:
                # Show source and priority if available
                if file.get('train_priority'):
                    sections.append(f"\n- Priority {file['train_priority']}: {file['train_name']}")
                else:
                    sections.append(f"\n- Source: {file.get('source', 'Unknown')}")
                sections.append(f"  File: {file['file_title']}")
                sections.append(f"  Status: {file['current_status']}")
                if file.get('is_blocked'):
                    sections.append(f"  [!] BLOCKED - {file['days_in_current_status']} days in current status")
                elif file.get('days_in_current_status'):
                    sections.append(f"  Days in current status: {file['days_in_current_status']}")
                if file.get('first_seen'):
                    sections.append(f"  Added to Brubru: {file['first_seen'][:10]}")
                if file.get('committees'):
                    sections.append(f"  Committees: {', '.join(file['committees'][:3])}")
                if file.get('oeil_ref'):
                    sections.append(f"  OEIL procedure: {file['oeil_ref']}")
                if file.get('celex_numbers'):
                    sections.append(f"  CELEX: {', '.join(file['celex_numbers'][:3])}")
                if file.get('description'):
                    sections.append(f"  Description: {file['description']}")
                # EP Legislative Train editorial state-of-play narrative (the
                # analytic context OEIL lacks). Authoritative EP source — safe to
                # ground answers on "where does this file stand / why does it matter".
                if file.get('legislative_train_summary'):
                    sections.append(f"  Legislative Train state of play: {file['legislative_train_summary']}")
                # Real roll-call results (committee + plenary) when Brubru has them.
                if file.get('vote_summary'):
                    sections.append(f"  EP vote results (roll-call): {file['vote_summary']}")

                # Available procedural actions for data-driven follow-ups
                if file.get('available_actions'):
                    actions = file['available_actions']
                    action_lines = []

                    if actions.get('rapporteur_name'):
                        rapp = actions['rapporteur_name']
                        group = actions.get('rapporteur_group') or ''
                        comm = actions.get('rapporteur_committee') or ''
                        action_lines.append(f"Rapporteur: {rapp} ({group}) in {comm}")

                    if actions.get('has_draft_report'):
                        comm = actions.get('draft_report_committee') or ''
                        date = actions.get('draft_report_date') or ''
                        action_lines.append(f"Draft report available ({comm}, {date})")

                    if actions.get('has_amendments'):
                        count = actions.get('amendment_count_hint', 0)
                        action_lines.append(f"MEP amendments tabled ({count} document(s))")

                    if actions.get('has_committee_report'):
                        action_lines.append("Committee report tabled for plenary")

                    if actions.get('has_committee_vote'):
                        date = actions.get('committee_vote_date') or ''
                        action_lines.append(f"Committee vote held ({date})")

                    if actions.get('has_plenary_vote'):
                        date = actions.get('plenary_vote_date') or ''
                        action_lines.append(f"Plenary vote held ({date})")

                    if actions.get('has_plenary_debate'):
                        action_lines.append("Plenary debate held")

                    if actions.get('has_committee_opinions'):
                        comms = ', '.join(actions['has_committee_opinions'])
                        action_lines.append(f"Committee opinions from: {comms}")

                    if actions.get('shadow_rapporteurs'):
                        shadows = ', '.join(
                            f"{s['name']} ({s['group']})"
                            for s in actions['shadow_rapporteurs'][:5]
                        )
                        action_lines.append(f"Shadow rapporteurs: {shadows}")

                    if actions.get('has_celex'):
                        action_lines.append("Legal text available (can draft amendments in Amendator)")

                    if actions.get('upcoming_events'):
                        for ev in actions['upcoming_events']:
                            action_lines.append(f"Upcoming: {ev['event_type']} ({ev['date']})")

                    # Document Gateway: actual document references with URLs
                    if actions.get('key_documents'):
                        action_lines.append("DOCUMENT GATEWAY (present these links to users who ask for texts):")
                        for doc in actions['key_documents']:
                            ref = doc.get('reference', '')
                            url = doc.get('url', '')
                            dtype = doc.get('type_text', doc.get('type', ''))
                            date = doc.get('date', '')
                            comm = doc.get('committee', '')
                            parts = [f"{dtype}" if dtype else '', f"{ref}" if ref else '', f"({comm})" if comm else '', f"[{date}]" if date else '']
                            label = ' '.join(p for p in parts if p)
                            action_lines.append(f"  {label}: {url}")

                    if action_lines:
                        sections.append("  AVAILABLE DATA FOR THIS FILE:")
                        for line in action_lines:
                            sections.append(f"    - {line}")

            sections.append("")

        # Recent RSS updates
        if context_data.recent_rss_entries:
            sections.append(f"\nRECENT UPDATES ({len(context_data.recent_rss_entries)} RSS entries):")
            for entry in context_data.recent_rss_entries[:10]:
                sections.append(f"- {entry['published']}: {entry['title']}")
                sections.append(f"  {entry['summary']}")
                sections.append(f"  Source: {entry['source']} | {entry['link']}")
                sections.append("")

        # Internal knowledge (templates, guides) is rendered NEAR THE TOP now
        # (right after the audience-brief block) so the highest-value grounding
        # always survives the max_length truncation cap. See the relocated block
        # above. Previously rendered here (after RSS/legislation/etc.), which
        # meant guides were truncated off for content-rich queries -- the AMR /
        # Health Security Committee refusals on 29 May 2026 traced to exactly
        # this: context hit the 32k cap before reaching the guides.

        # CELLAR on-demand legislation (EuroVoc fallback when no guides match)
        if context_data.cellar_legislation:
            sections.append(f"\nCELLAR LEGISLATION (EuroVoc topic match, {len(context_data.cellar_legislation)} results):")
            sections.append("These are recent EU legal acts matching the query topic from CELLAR SPARQL.")
            sections.append("Source tier: 1 (official EUR-Lex/CELLAR data).\n")
            for item in context_data.cellar_legislation:
                celex = item.get('celex', 'N/A')
                title = item.get('title', 'No English title')
                date = item.get('date', 'N/A')
                keyword = item.get('eurovoc_keyword', '')
                sections.append(f"- CELEX: {celex}")
                if title:
                    sections.append(f"  Title: {title[:200]}")
                sections.append(f"  Date: {date}")
                if keyword:
                    sections.append(f"  Topic: {keyword}")
                # ELI permalink (stable; constructed from a clean sector-3 CELEX, no fetch).
                # Prefer the ELI when citing — it dereferences to the consolidated version
                # and survives the act-by-act OJ change. See guide finding_and_citing_eu_law.
                _eli = item.get('eli')
                if not _eli and isinstance(celex, str):
                    _m = re.match(r'^3(\d{4})([RLD])(\d{4})$', celex)
                    if _m:
                        _t = {'R': 'reg', 'L': 'dir', 'D': 'dec'}[_m.group(2)]
                        _eli = f"http://data.europa.eu/eli/{_t}/{_m.group(1)}/{int(_m.group(3))}/oj"
                if _eli:
                    sections.append(f"  ELI (stable link): {_eli}")
                sections.append(f"  EUR-Lex: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}")
                sections.append("")

        # Phase 2: EPRS Publications (plain-language explainers)
        if context_data.eprs_publications:
            sections.append(f"\nEPRS RESEARCH & BRIEFINGS ({len(context_data.eprs_publications)}):")
            sections.append("IMPORTANT: These are plain-language EXPLANATIONS of EU legislation.")
            sections.append("Use these to explain complex legal text in understandable terms.\n")
            for pub in context_data.eprs_publications:
                sections.append(f"- {pub['title']}")
                sections.append(f"  Type: {pub['publication_type']}")
                sections.append(f"  Excerpt: {pub['text'][:800]}...")
                if pub.get('related_celex'):
                    sections.append(f"  Explains legislation: {', '.join(pub['related_celex'][:3])}")
                if pub.get('related_procedures'):
                    sections.append(f"  Related procedures: {', '.join(pub['related_procedures'][:3])}")
                if pub.get('publication_url'):
                    sections.append(f"  Full briefing: {pub['publication_url']}")
                sections.append("")

        # Phase 5: AI-Generated Briefings (smart summaries)
        if context_data.ai_generated_briefings:
            sections.append(f"\n🤖 AI-GENERATED LEGISLATIVE BRIEFINGS ({len(context_data.ai_generated_briefings)}):")
            sections.append("These are Claude-generated EPRS-style briefings for legislation without human-written briefings.")
            sections.append("Use these as plain-language explanations where no EPRS publication exists.\n")
            for briefing in context_data.ai_generated_briefings:
                sections.append(f"- {briefing['title']}")
                sections.append(f"  For: CELEX {briefing['celex']}")
                sections.append(f"  Summary: {briefing['summary']}")
                sections.append(f"\n  Key Points:")
                for point in briefing['key_points'][:5]:  # Show first 5 points
                    sections.append(f"    • {point}")
                sections.append(f"\n  Main Provisions: {briefing['main_provisions'][:400]}...")
                if briefing.get('background'):
                    sections.append(f"  Background: {briefing['background'][:200]}...")
                sections.append(f"  Confidence: {briefing['confidence_score']:.0%}")
                sections.append(f"  Generated: {briefing['generated_at']}")
                sections.append("")

        # Local EU Laws Database (28K+ laws from LEG_2025-11, TSVECTOR-ranked)
        if context_data.local_eu_laws:
            sections.append(f"\nEU LAWS DATABASE ({len(context_data.local_eu_laws)} relevant laws from Brubru's EU legislation database):")
            sections.append("These are adopted EU laws matched by full-text relevance ranking.")
            sections.append("Present their CELEX numbers and titles to the user. Mention related citations.\n")

            for law in context_data.local_eu_laws:
                celex = law.get('celex', 'N/A')
                title = law.get('title', '')
                sections.append(f"- CELEX: {celex}")
                sections.append(f"  Title: {title[:200]}..." if len(title) > 200 else f"  Title: {title}")
                sections.append(f"  Type: {law.get('doc_type', 'N/A')} | Date: {law.get('date', 'N/A')}")

                if law.get('policy_area'):
                    sections.append(f"  Policy Area: {law['policy_area']}")

                if law.get('citations'):
                    citations_list = law['citations'][:5]
                    sections.append(f"  Cites: {', '.join(str(c) for c in citations_list)}")

                if celex and celex != 'N/A':
                    sections.append(f"  EUR-Lex: https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}")

                # Recital-article linking (TF-IDF; only appears when user mentions a specific article)
                ral = law.get('recital_article_links')
                if ral:
                    sections.append("  Recital-to-article links (TF-IDF cosine; cite in 'Justification' when drafting amendments):")
                    for entry in ral:
                        recital_cites = ", ".join(
                            f"recital {r['recital_number']} (score {r['score']:.2f}): {r['snippet']}"
                            for r in entry.get('recitals', [])[:3]
                        )
                        sections.append(f"    {entry['article']} -> {recital_cites}")

                # Defined terms (Article 3/4 definitions whose term appears in the query)
                dts = law.get('defined_terms')
                if dts:
                    sections.append("  Statutory definitions (from this law -- use them verbatim when answering):")
                    for entry in dts:
                        pt = f"({entry['point']})" if entry.get('point') else ""
                        sections.append(
                            f"    {entry['article']}{pt} '{entry['term']}' means: {entry['definition'][:300]}"
                        )

                sections.append("")

        # EU institutional source search (Tavily fallback, scoped to .europa.eu + policy media)
        if context_data.eu_institutional_results:
            sections.append(f"\nEU INSTITUTIONAL SOURCES ({len(context_data.eu_institutional_results)} results):")
            sections.append("These results come from official EU institutional websites and trusted policy media.")
            sections.append("IMPORTANT: When citing these results, ALWAYS name the source explicitly")
            sections.append("(e.g., 'According to Bruegel...', 'Euractiv reports that...', 'The European Parliament published...').")
            sections.append("Include the URL so the user can verify.\n")

            for result in context_data.eu_institutional_results:
                source_name = result.get('source_name', 'Unknown')
                sections.append(f"- [{source_name}] {result['title']}")
                if result.get('published_date'):
                    sections.append(f"  Published: {result['published_date']}")
                sections.append(f"  {result['content'][:600]}")
                sections.append(f"  URL: {result['url']}")
                sections.append("")

        # EP plenary debate transcript (CRE)
        if context_data.plenary_debate_transcript:
            sections.append(f"\n{context_data.plenary_debate_transcript}")
            sections.append("")

        # (On-demand blocks moved earlier to survive truncation)

        # Real-time web search results (Tavily)
        if context_data.web_search_results:
            sections.append(f"\nREAL-TIME WEB SEARCH ({len(context_data.web_search_results)} results):")
            sections.append("Current news and web content that may not yet be in structured EU databases.\n")

            for result in context_data.web_search_results:
                if result.get('source') == 'tavily_ai_answer':
                    # AI-generated summary. Capped like every other web result:
                    # this was the ONLY block in the whole context injected
                    # untruncated, and on 7 Aug 2026 it reached 20,426
                    # characters, 5,106 tokens, 42% of the entire context, on a
                    # question about the Critical Medicines Act rapporteur that
                    # Brubru answers from its own verified guides.
                    #
                    # That is the lowest-trust source in the hierarchy taking
                    # the largest share of the budget, and it compounds: the
                    # extra tokens push the request past the fast providers'
                    # rate limits onto Mistral, which reads roughly 30% of the
                    # context, so the verified guides are the first thing lost.
                    # A fabricated MEP voting record earlier the same day cited
                    # a "WEB SUMMARY" entry as its source.
                    _summary = (result.get('content') or '')[:1500]
                    sections.append(f"WEB SUMMARY (unverified web content, lowest source tier):")
                    sections.append(f"  {_summary}")
                    sections.append("")
                else:
                    # Regular web result
                    sections.append(f"- {result['title']}")
                    if result.get('published_date'):
                        sections.append(f"  Published: {result['published_date']}")
                    sections.append(f"  {result['content'][:500]}...")
                    sections.append(f"  Source: {result['url']}")
                    sections.append("")

        # Beresol open reports and monitors (Brubru's company)
        if context_data.beresol_content:
            sections.append(f"\nBERESOL OPEN REPORTS & MONITORS ({len(context_data.beresol_content)} items):")
            sections.append("IMPORTANT: These are open reports and monitors published by Beresol, Brubru's company.")
            sections.append("When referencing this content, mention it comes from Beresol: https://beresol.eu/public-affairs\n")

            for item in context_data.beresol_content:
                if item.get('type') == 'beresol_report':
                    sections.append(f"OPEN REPORT: {item['title']}")
                    if item.get('subtitle'):
                        sections.append(f"  Subtitle: {item['subtitle']}")
                    sections.append(f"  Author: {item['author']}")
                    if item.get('date'):
                        sections.append(f"  Date: {item['date']}")
                    sections.append(f"  Policy Area: {item['policy_area']}")

                    if item.get('executive_summary'):
                        sections.append(f"\n  Executive Summary:")
                        sections.append(f"  {item['executive_summary'][:1500]}...")

                    if item.get('key_findings'):
                        sections.append(f"\n  Key Findings:")
                        sections.append(f"  {item['key_findings'][:1000]}...")

                    if item.get('content_excerpt'):
                        sections.append(f"\n  Content Excerpt:")
                        sections.append(f"  {item['content_excerpt'][:2500]}...")

                    if item.get('keywords'):
                        sections.append(f"\n  Keywords: {', '.join(item['keywords'][:10])}")

                    sections.append(f"\n  Source: {item['source']}")
                    sections.append(f"  Full report: {item['source_url']}")
                    sections.append("")

                elif item.get('type') == 'beresol_monitor':
                    sections.append(f"MONITOR: {item['name']}")
                    sections.append(f"  Description: {item['description']}")
                    sections.append(f"  Policy Area: {item['policy_area']}")
                    if item.get('keywords'):
                        sections.append(f"  Keywords: {', '.join(item['keywords'][:8])}")
                    sections.append(f"  Source: {item['source']}")
                    sections.append(f"  More info: {item['source_url']}")
                    sections.append("")

        # EP Committee Work in Progress
        if context_data.committee_work_items:
            sections.append(f"\nEP COMMITTEE WORK IN PROGRESS ({len(context_data.committee_work_items)} items):")
            sections.append("Source: European Parliament committee work-in-progress pages")
            sections.append("Note: COD (ordinary legislative) procedures have highest relevance (100), INI (own-initiative) lowest (40)\n")

            for item in context_data.committee_work_items:
                sections.append(f"- {item['title']}")
                sections.append(f"  Committee: {item['committee_name']} ({item['committee_code']})")
                sections.append(f"  Procedure: {item['procedure_ref']} ({item['procedure_type']})")
                sections.append(f"  Role: {item['committee_role']}, Relevance: {item['relevance_score']}")
                if item.get('rapporteur'):
                    sections.append(f"  Rapporteur: {item['rapporteur']}")
                sections.append(f"  Status: {item['status']}")
                if item.get('oeil_url'):
                    sections.append(f"  OEIL: {item['oeil_url']}")
                if item.get('description'):
                    sections.append(f"  Description: {item['description'][:400]}...")
                sections.append("")

        # EP Committee Meeting Minutes
        if context_data.committee_minutes:
            sections.append(f"\nEP COMMITTEE MEETING MINUTES ({len(context_data.committee_minutes)} items):")
            sections.append("Source: European Parliament published committee meeting minutes (official records)")
            sections.append("Note: Minutes contain attendance, agenda items discussed, votes taken, and decisions adopted\n")

            for item in context_data.committee_minutes:
                sections.append(f"- {item['title']}")
                sections.append(f"  Committee: {item['committee_code']}")
                sections.append(f"  Meeting: {item['meeting_date']}")
                if item.get('publication_date'):
                    sections.append(f"  Published: {item['publication_date']}")
                if item.get('pdf_url'):
                    sections.append(f"  PDF: {item['pdf_url']}")
                if item.get('votes'):
                    for vote in item['votes'][:5]:
                        sections.append(f"  Vote: {vote.get('subject', 'N/A')} - FOR:{vote.get('for', '?')} AGAINST:{vote.get('against', '?')} ABSTAIN:{vote.get('abstain', '?')}")
                if item.get('full_text'):
                    sections.append(f"  Content excerpt: {item['full_text'][:800]}")
                sections.append("")

        # EC Public Consultations (Have Your Say portal)
        if context_data.public_consultations:
            sections.append(f"\nEC PUBLIC CONSULTATIONS ({len(context_data.public_consultations)} items):")
            sections.append("Source: European Commission 'Have Your Say' portal")
            sections.append("Note: Shows open consultations where citizens and stakeholders can participate in EU policy-making\n")

            for item in context_data.public_consultations:
                sections.append(f"- {item['title']}")
                sections.append(f"  Type: {item['consultation_type']}, Status: {item['status']}")
                if item.get('dg_name'):
                    sections.append(f"  DG: {item['dg_name']} ({item['dg_responsible']})")
                if item.get('policy_areas'):
                    sections.append(f"  Policy Areas: {', '.join(item['policy_areas'][:3])}")
                if item.get('end_date'):
                    deadline_info = f"  Deadline: {item['end_date'][:10]}"
                    if item.get('days_remaining') is not None:
                        if item['days_remaining'] < 0:
                            deadline_info += " (CLOSED)"
                        elif item['days_remaining'] == 0:
                            deadline_info += " (TODAY!)"
                        elif item['days_remaining'] <= 7:
                            deadline_info += f" ({item['days_remaining']} days left - CLOSING SOON!)"
                        else:
                            deadline_info += f" ({item['days_remaining']} days left)"
                    sections.append(deadline_info)
                if item.get('feedback_count', 0) > 0:
                    sections.append(f"  Responses received: {item['feedback_count']}")
                if item.get('description'):
                    sections.append(f"  Description: {item['description'][:400]}...")
                if item.get('portal_url'):
                    sections.append(f"  Have Your Say: {item['portal_url']}")
                sections.append("")

        # EC Commission Documents (Yellow/Blue tier)
        if context_data.commission_documents:
            sections.append(f"\nCOMMISSION DOCUMENTS ({len(context_data.commission_documents)} items):")
            sections.append("Source: EC Register of Commission Documents (Yellow/Blue tier)")
            sections.append("Note: Official EC legislative proposals, staff working documents, and joint documents\n")

            for item in context_data.commission_documents:
                doc_type = item.get('doc_type', 'COM')
                sections.append(f"- [{doc_type}] {item['title']}")
                if item.get('common_name'):
                    sections.append(f"  Also known as: {item['common_name']}")
                sections.append(f"  Reference: {item['reference']}")
                if item.get('dg_responsible'):
                    sections.append(f"  DG: {item['dg_responsible']}")
                if item.get('procedure_ref'):
                    sections.append(f"  Procedure: {item['procedure_ref']}")
                if item.get('publication_date'):
                    sections.append(f"  Date: {item['publication_date'][:10]}")
                if item.get('portal_url'):
                    sections.append(f"  URL: {item['portal_url']}")
                sections.append("")

        # EU Calendar Events (institutional calendar with exact dates)
        if context_data.eu_calendar_events:
            sections.append(f"\nEU INSTITUTIONAL CALENDAR ({len(context_data.eu_calendar_events)} events):")
            sections.append("Source: Official EU institutional calendars (exact dates -- prioritise over RSS/news)\n")
            for event in context_data.eu_calendar_events:
                inst = event.get('institution', 'Unknown')
                sections.append(f"- {inst}: {event['title']}")
                date_str = event.get('start_date', '')
                time_str = event.get('start_time')
                if time_str:
                    sections.append(f"  Date: {date_str} {time_str}")
                elif event.get('all_day'):
                    sections.append(f"  Date: {date_str} (all day)")
                else:
                    sections.append(f"  Date: {date_str}")
                if event.get('end_date') and event['end_date'] != event.get('start_date'):
                    sections.append(f"  End date: {event['end_date']}")
                sections.append(f"  Type: {event.get('event_type', 'unknown')}")
                if event.get('council_configuration'):
                    sections.append(f"  Council configuration: {event['council_configuration']}")
                if event.get('ep_committee_code'):
                    sections.append(f"  Committee: {event['ep_committee_code']}")
                if event.get('description'):
                    desc = event['description'][:300]
                    sections.append(f"  Details: {desc}")
                if event.get('agenda_url'):
                    sections.append(f"  Agenda: {event['agenda_url']}")
                if event.get('source_url'):
                    sections.append(f"  Source: {event['source_url']}")
                if event.get('procedure_refs'):
                    sections.append(f"  Procedures: {', '.join(event['procedure_refs'])}")
                sections.append("")

        # MEP Amendments (scraped EP committee amendments)
        if context_data.mep_amendments_summary:
            for summary in context_data.mep_amendments_summary:
                proc = summary['procedure_reference']
                total = summary['total']
                sections.append(f"\nMEP AMENDMENTS FOR {proc} ({total} total):")
                sections.append(f"  By group: {summary['group_summary']}")

                if summary.get('top_elements'):
                    contested = ', '.join(
                        f"{e['reference']} ({e['count']})"
                        for e in summary['top_elements'][:5]
                    )
                    sections.append(f"  Most contested: {contested}")

                if summary.get('key_amendments'):
                    sections.append("  Key amendments:")
                    for am in summary['key_amendments']:
                        text_preview = am['proposed_text'][:100] + '...' if len(am['proposed_text']) > 100 else am['proposed_text']
                        sections.append(
                            f"    - AM {am['number']} by {am['authors']} ({am['group']}): "
                            f"{am['element']} - {am['type']} - \"{text_preview}\""
                        )

                sections.append(f"  Fetch more: POST /api/mep-amendments/fetch/{proc}")
                sections.append("")

        # MCP Toolbox supplementary results
        if context_data.toolbox_results:
            sections.append(f"\nSUPPLEMENTARY DATABASE RESULTS ({len(context_data.toolbox_results)} items):")
            sections.append("Source: MCP Toolbox for Databases\n")
            for item in context_data.toolbox_results:
                source_type = item.get('source_type', 'unknown')
                if source_type == 'toolbox_texts_adopted':
                    sections.append(f"- [Adopted Text] {item.get('title', '')}")
                    sections.append(f"  Reference: {item.get('ta_reference', '')}, Type: {item.get('text_type', '')}")
                    if item.get('adoption_date'):
                        sections.append(f"  Adopted: {item['adoption_date'][:10]}")
                    if item.get('procedure_ref'):
                        sections.append(f"  Procedure: {item['procedure_ref']}")
                elif source_type == 'toolbox_carriage':
                    sections.append(f"- [Legislative File] {item.get('title', '')}")
                    sections.append(f"  Status: {item.get('status', '')}, Committee: {item.get('committee', '')}")
                    if item.get('oeil_ref'):
                        sections.append(f"  OEIL: {item['oeil_ref']}")
                    if item.get('summary'):
                        sections.append(f"  Summary: {item['summary'][:400]}")
                else:
                    sections.append(f"- {item.get('title', str(item))}")
                sections.append("")

        # Org intelligence (aggregated user profile for personalisation)
        if context_data.org_intelligence:
            oi = context_data.org_intelligence
            parts = []
            if oi.get('sector'):
                country_str = f" ({oi['country']})" if oi.get('country') else ""
                parts.append(f"Organisation: {oi['sector']}{country_str}")
            if oi.get('policy_areas'):
                parts.append(f"Policy focus: {', '.join(oi['policy_areas'][:5])}")
            if oi.get('tracked_files'):
                parts.append(f"Currently tracking: {', '.join(oi['tracked_files'][:5])}")
            if oi.get('amended_files'):
                parts.append(f"Has drafted amendments to: {', '.join(oi['amended_files'][:3])}")
            if oi.get('top_topics'):
                top = sorted(oi['top_topics'], key=oi['top_topics'].get, reverse=True)[:5]
                parts.append(f"Frequent topics: {', '.join(top)}")
            if parts:
                sections.append("\nUSER PROFILE:")
                sections.append("Tailor your response to this user's policy focus and institutional needs.\n")
                for p in parts:
                    sections.append(f"- {p}")
                sections.append("")

        # User uploaded documents (personalised reference material)
        if context_data.user_uploaded_documents:
            sections.append(f"\nUSER UPLOADED DOCUMENTS ({len(context_data.user_uploaded_documents)}):")
            sections.append("Reference material the user has uploaded. Use this to personalise your response.\n")
            for doc in context_data.user_uploaded_documents:
                sections.append(f"- {doc.get('title', 'Untitled')} ({doc.get('original_filename', 'unknown file')})")
                excerpt = doc.get('content_excerpt', '')
                if excerpt:
                    sections.append(f"  Content: {excerpt[:1500]}")
                sections.append("")

        # Reference data (calendars, institutions)
        if context_data.reference_data_context:
            sections.append("\nREFERENCE DATA:")
            sections.append(context_data.reference_data_context)
            sections.append("")

        # Phase 8: Tender context (Tenderator integration)
        if context_data.tender_context and context_data.tender_context.formatted_context:
            sections.append("\n" + context_data.tender_context.formatted_context)
            sections.append("")

        # Build full context
        full_context = "\n".join(sections)

        # Truncate if too long
        if len(full_context) > max_length:
            full_context = full_context[:max_length] + "\n\n[Context truncated due to length]"

        return full_context

    async def build_context_with_citations(
        self,
        user_message: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Tuple[str, List[Dict[str, str]]]:
        """
        Build context and return with citation metadata.

        DEPRECATED, 6 August 2026. Do NOT call this from a chat path.

        It takes no `user_id`, so everything personalised is silently dropped:
        the private-guide block (gated on user_id in build_context_for_query),
        tracked-procedure awareness, and analytics attribution. It also returns
        only a formatted STRING, so the caller loses the structured ContextData
        that guide-document link injection and MEP linkification need.

        Both chat() and chat_stream() now call build_context_for_query(...) +
        format_context_for_ai(...) + _build_citations_from_context(...) so the
        two paths cannot drift again. Kept only for non-chat callers; use the
        three-call form for anything user-facing.

        Args:
            user_message: User query
            conversation_history: Previous messages

        Returns:
            Tuple of (formatted_context, citations_list)
            Citations list contains source metadata for footnotes
        """
        # Build context data
        context_data = await self.build_context_for_query(
            user_message=user_message,
            conversation_history=conversation_history
        )

        # Format context
        formatted_context = self.format_context_for_ai(context_data)

        # Build citations list
        citations = []

        # Add search results (Tier 4 - curated knowledge)
        for doc in context_data.relevant_documents:
            citations.append({
                'type': 'search_result',
                'title': doc['metadata'].get('title', 'Untitled'),
                'url': doc['metadata'].get('url', ''),
                'source': doc['collection'],
                'score': doc['score'],
                'source_tier': get_source_tier('search_result'),
                'last_verified': doc['metadata'].get('date', None)
            })

        # Add legislation (Tier 1 - official legal text)
        for leg in context_data.legislation_details:
            citations.append({
                'type': 'legislation',
                'title': leg['title'],
                'celex': leg['celex'],
                'url': leg['url'],
                'date': leg['date'],
                'source_tier': get_source_tier('legislation'),
                'last_verified': leg.get('date')
            })

        # Add procedures (Tier 2 - legislative observatory)
        for proc in context_data.procedure_details:
            citations.append({
                'type': 'procedure',
                'title': proc['title'],
                'reference': proc['reference'],
                'url': proc['url'],
                'status': proc['status'],
                'source_tier': get_source_tier('procedure'),
                'last_verified': proc.get('last_updated')
            })

        # Add MEPs (Tier 2 - official EP data)
        for mep in context_data.mep_profiles:
            citations.append({
                'type': 'mep',
                'name': mep['name'],
                'country': mep['country'],
                'url': mep['url'],
                'source_tier': get_source_tier('mep'),
                'last_verified': None  # MEP data is typically current
            })

        # Add RSS (Tier 3 - news/updates)
        for entry in context_data.recent_rss_entries:
            citations.append({
                'type': 'news',
                'title': entry['title'],
                'url': entry['link'],
                'published': entry['published'],
                'source': entry['source'],
                'source_tier': get_source_tier('news'),
                'last_verified': entry['published']
            })

        # Add web search results (Tier 5 - real-time web, needs verification)
        for result in context_data.web_search_results:
            if result.get('source') != 'tavily_ai_answer':  # Skip AI summary
                citations.append({
                    'type': 'web_search',
                    'title': result['title'],
                    'url': result['url'],
                    'published': result.get('published_date'),
                    'source': 'tavily',
                    'source_tier': get_source_tier('web_search'),
                    'last_verified': result.get('published_date')
                })

        # Add Beresol content (Tier 4 - curated analysis from Brubru's company)
        for item in context_data.beresol_content:
            if item.get('type') == 'beresol_report':
                citations.append({
                    'type': 'beresol_report',
                    'title': item['title'],
                    'author': item['author'],
                    'url': item['source_url'],
                    'date': item.get('date'),
                    'policy_area': item['policy_area'],
                    'source': item['source'],
                    'publisher': item['publisher'],
                    'source_tier': get_source_tier('beresol_report'),
                    'last_verified': item.get('date'),
                    'note': 'Open report published by Beresol, Brubru\'s company'
                })
            elif item.get('type') == 'beresol_monitor':
                citations.append({
                    'type': 'beresol_monitor',
                    'title': item['name'],
                    'url': item['source_url'],
                    'description': item['description'],
                    'policy_area': item['policy_area'],
                    'source': item['source'],
                    'publisher': item['publisher'],
                    'source_tier': get_source_tier('beresol_monitor'),
                    'last_verified': None,
                    'note': 'Monitor published by Beresol, Brubru\'s company'
                })

        # Add EU Calendar events (Tier 2 - official institutional calendar)
        for event in (context_data.eu_calendar_events or []):
            citations.append({
                'type': 'eu_calendar',
                'title': event.get('title', 'Unknown event'),
                'institution': event.get('institution', ''),
                'date': event.get('start_date'),
                'url': event.get('source_url') or event.get('agenda_url', ''),
                'event_type': event.get('event_type', ''),
                'source_tier': get_source_tier('eu_calendar'),
                'last_verified': event.get('start_date'),
            })

        # Phase 8: Add tender citations (Tier 4 - official but domain-specific)
        if context_data.tender_context:
            for tender in context_data.tender_context.tenders:
                citations.append({
                    'type': 'tender',
                    'title': tender.get('title', 'Unknown tender'),
                    'publication_number': tender.get('publication_number', ''),
                    'url': tender.get('ted_url', ''),
                    'buyer_country': tender.get('buyer_country', ''),
                    'value': tender.get('estimated_value'),
                    'source_tier': get_source_tier('tender'),
                    'last_verified': tender.get('publication_date')
                })
            for match in context_data.tender_context.user_matches:
                tender = match.get('tender', {})
                citations.append({
                    'type': 'tender_match',
                    'title': tender.get('title', 'Unknown tender'),
                    'publication_number': tender.get('publication_number', ''),
                    'url': tender.get('ted_url', ''),
                    'match_score': match.get('match_score'),
                    'source_tier': get_source_tier('tender_match'),
                    'last_verified': tender.get('publication_date')
                })

        return formatted_context, citations


# Global singleton
_context_builder: Optional[ContextBuilder] = None


def get_context_builder(
    hybrid_search: Optional[HybridSearch] = None,
    metadata_extractor: Optional[MetadataExtractor] = None,
    eurlex_client: Optional[EURLexClient] = None,
    oeil_client: Optional[OEILClient] = None,
    parliament_client: Optional[EuropeanParliamentClient] = None,
    rss_manager: Optional[Any] = None  # RSSManager not yet implemented
) -> ContextBuilder:
    """
    Get global context builder instance.

    Args:
        hybrid_search: Hybrid search service
        metadata_extractor: Entity extraction service
        eurlex_client: EUR-Lex API client
        oeil_client: OEIL API client
        parliament_client: Parliament API client
        rss_manager: RSS manager

    Returns:
        ContextBuilder instance
    """
    global _context_builder

    if _context_builder is None:
        _context_builder = ContextBuilder(
            hybrid_search=hybrid_search or get_hybrid_search(),
            metadata_extractor=metadata_extractor or get_metadata_extractor(),
            eurlex_client=eurlex_client,
            oeil_client=oeil_client,
            parliament_client=parliament_client,
            rss_manager=rss_manager
        )

    return _context_builder
