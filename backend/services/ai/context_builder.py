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
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import date, datetime, timedelta
from dataclasses import dataclass

from services.search.hybrid_search import HybridSearch, get_hybrid_search
from services.indexing.metadata_extractor import MetadataExtractor, get_metadata_extractor
from services.indexing.eprs_indexer import EPRSIndexer, get_eprs_indexer  # Phase 2: EPRS search
from services.matching.eprs_matcher import EPRSMatcher, get_eprs_matcher  # Phase 3: Auto-matching
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
        'resolution': 9, 'report': 8, 'letter': 8,
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
        eprs_indexer: Optional[EPRSIndexer] = None,  # Phase 2: EPRS search
        eprs_matcher: Optional[EPRSMatcher] = None,  # Phase 3: Auto-matching
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
        self.eprs_indexer = eprs_indexer or get_eprs_indexer()  # Phase 2
        self.eprs_matcher = eprs_matcher or get_eprs_matcher()  # Phase 3
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

        # 1. Semantic/hybrid search for relevant documents
        search_results = await self.hybrid_search.search(
            query=user_message,
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

        # 2. Extract entities from query
        entities = self.extract_entities(user_message)

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

        # Legislative Train files (always run)
        tasks.append(self._fetch_legislative_train_files(query=user_message, entities=entities))

        # Internal knowledge base (always run)
        tasks.append(self._query_internal_knowledge(user_message, drafting_intent=drafting_intent))

        # EPRS publications (always run)
        tasks.append(self._search_eprs_publications(query=user_message, entities=entities))

        # Local EU laws database (always run)
        tasks.append(self._fetch_eu_laws_from_database(query=user_message, entities=entities))

        # Helper functions for empty results
        async def empty_result():
            return []

        async def empty_tuple_result():
            return ([], [])

        # RSS entries (conditional)
        if use_rss and self.rss_manager:
            tasks.append(self._fetch_recent_rss(query=user_message, entities=entities, days=self.rss_lookback_days))
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
            tasks.append(self._fetch_web_search(query=user_message))
        else:
            tasks.append(empty_result())

        # Beresol open reports and monitors (Brubru's company)
        if self.beresol_loader:
            tasks.append(self._fetch_beresol_content(query=user_message))
        else:
            tasks.append(empty_result())

        # EP Committee Work in Progress items
        tasks.append(self._fetch_committee_work_items(query=user_message, entities=entities))

        # EP Committee Meeting Minutes
        tasks.append(self._fetch_committee_minutes(query=user_message, entities=entities))

        # Phase 9: Fetch EC Public Consultations (Have Your Say portal)
        tasks.append(self._fetch_public_consultations(query=user_message, entities=entities))

        # EC Commission Documents (Yellow/Blue tier only)
        tasks.append(self._fetch_commission_documents(query=user_message, entities=entities, user_id=user_id))

        # MCP Toolbox supplementary DB queries (non-blocking)
        tasks.append(self._fetch_via_toolbox(query=user_message, entities=entities))

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
        tasks.append(self._fetch_eu_calendar_events(query=user_message, entities=entities))

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

        commissioner_agenda_block = post_map.get('commissioner_agenda')
        position_block = post_map.get('position')
        committee_transcript_block = post_map.get('committee_transcript')

        # Build reference data context (synchronous, fast)
        reference_data_context = self._build_reference_data_context(user_message)

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
            reference_data_context=reference_data_context,
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

        return ExtractedEntities(
            celex_numbers=extracted['celex_numbers'],
            procedure_references=extracted['procedure_references'],
            mep_names=extracted['mep_mentions'],
            committee_codes=[c['code'] for c in extracted['committees']],
            article_references=extracted['articles'],
            policy_areas=policy_areas,
            dg_codes=dg_codes,
            assistant_intent=assistant_intent
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
                if self.auto_include_explainers:
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
            try:
                procedure = await self.oeil_client.get_procedure(proc_ref)

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
                    'url': f"https://oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do?reference={proc_ref}"
                }

                # Phase 3: Auto-include EPRS explainers (prioritize "At a Glance")
                if self.auto_include_explainers:
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

                details.append(proc_detail)

                logger.debug(f"Fetched procedure: {proc_ref}")

            except Exception as e:
                logger.error(f"Failed to fetch procedure {proc_ref}: {str(e)}")

        return details

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

            # Trigger-matched guides get a bonus
            if guide.get('trigger_matched'):
                score += 2.0

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
                    'description': carriage.description[:300] if carriage.description else None
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
                    'procedure_type': item.procedure_type.value if item.procedure_type else 'INI',
                    'committee_role': item.committee_role.value if item.committee_role else 'lead',
                    'relevance_score': item.relevance_score,
                    'rapporteur': item.rapporteur_name,
                    'status': item.status.value if item.status else 'unknown',
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
        if len(eprs_results) < self.max_eprs_results:
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
    # On-demand: EP committee meeting transcripts (AI-transcribed)
    # ------------------------------------------------------------------

    # Known EP committee codes for direct match in queries
    EP_COMMITTEE_CODES = {
        "AFCO", "AFET", "AGRI", "BUDG", "CONT", "CULT", "DEVE", "DROI", "ECON",
        "EMPL", "ENVI", "FEMM", "FISC", "IMCO", "INTA", "ITRE", "JURI", "LIBE",
        "PECH", "PETI", "REGI", "SEDE", "TRAN", "PANA", "SANT",
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

        try:
            # Try calendar context
            calendar_context = self.reference_data_service.build_calendar_context(query)
            if calendar_context:
                context_parts.append(calendar_context)

            # Try institution context
            institution_context = self.reference_data_service.build_institution_context(query)
            if institution_context:
                context_parts.append(institution_context)

            if context_parts:
                return "\n\n".join(context_parts)

        except Exception as e:
            logger.error(f"Failed to build reference data context: {str(e)}")

        return None

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
        Fetch user's uploaded documents marked for AI context inclusion.
        Scores by keyword relevance to the query and returns top matches.
        """
        if not user_id:
            return []

        try:
            from models.user_document import UserDocument

            db = SessionLocal()
            docs = db.query(UserDocument).filter(
                UserDocument.user_id == user_id,
                UserDocument.document_type == 'uploaded',
                UserDocument.include_in_ai_context == True,
                UserDocument.content != None,
            ).order_by(UserDocument.updated_at.desc()).limit(10).all()

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

                results.append({
                    'id': str(doc.id),
                    'title': doc.title,
                    'original_filename': doc.original_filename,
                    'content_excerpt': (doc.content or '')[:2000],
                    'relevance_score': score,
                    'source_type': 'user_uploaded',
                })

            results.sort(key=lambda x: x['relevance_score'], reverse=True)
            db.close()

            selected = results[:max_docs]
            if selected:
                logger.info(f"Found {len(selected)} relevant user uploaded documents for context")
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

    def format_context_for_ai(
        self,
        context_data: ContextData,
        max_length: int = 32000
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

        # Internal knowledge (templates, guides)
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
                sections.append(f"  {item['content'][:4000]}")
                sections.append("")

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
            sections.append(f"\nEU LAWS DATABASE ({len(context_data.local_eu_laws)} relevant laws from 28,505 in database):")
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
                    # AI-generated summary
                    sections.append(f"WEB SUMMARY:")
                    sections.append(f"  {result['content']}")
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
