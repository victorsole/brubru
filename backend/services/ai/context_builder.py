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
from datetime import datetime, timedelta
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
    'who should i contact', 'who to contact', 'who to talk to',
    'who is responsible', 'who is in charge', 'who handles',
    'who deals with', 'contact person', 'point of contact',
    'who can i reach', 'who works on', 'who do i contact',
    'who should i reach out to', 'who should i write to',
]


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

    # Metadata
    query: str
    search_time_ms: float
    total_sources: int

    # Phase 8: Tender data (Tenderator integration) - optional, must come after required fields
    tender_context: Optional[TenderContextData] = None


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

        # 3. Run all async operations in parallel for maximum speed
        # This reduces total wait time from sum(times) to max(time)

        # Prepare tasks to run concurrently
        tasks = []

        # Legislative Train files (always run)
        tasks.append(self._fetch_legislative_train_files(query=user_message, entities=entities))

        # Internal knowledge base (always run)
        tasks.append(self._query_internal_knowledge(user_message))

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
            if not entities.dg_codes:
                query_lower = user_message.lower()
                is_contact_query = any(kw in query_lower for kw in CONTACT_INTENT_PHRASES)
                if is_contact_query:
                    for keyword, dg_list in POLICY_TO_DG.items():
                        if re.search(r'\b' + re.escape(keyword) + r'\b', query_lower):
                            entities.dg_codes.extend(
                                dg for dg in dg_list if dg not in entities.dg_codes
                            )

            if entities.dg_codes:
                tasks.append(self._fetch_ec_personnel(entities.dg_codes[:self.max_live_api_calls]))
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

        # MEP amendments (scraped EP committee amendments)
        if entities.procedure_references or entities.mep_names:
            tasks.append(self._fetch_mep_amendments(
                entities.procedure_references,
                mep_names=entities.mep_names,
            ))
        else:
            tasks.append(empty_result())

        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Unpack results (order matches task addition)
        legislative_train_files = results[0] if not isinstance(results[0], Exception) else []
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

        # Unpack Public Consultations (index 14)
        public_consultations = results[14] if not isinstance(results[14], Exception) else []

        # Unpack Commission Documents (index 15)
        commission_documents = results[15] if not isinstance(results[15], Exception) else []

        # Unpack MCP Toolbox results (index 16)
        toolbox_results = results[16] if not isinstance(results[16], Exception) else []

        # Unpack User Uploaded Documents (index 17)
        user_uploaded_documents = results[17] if not isinstance(results[17], Exception) else []

        # Unpack MEP Amendments summary (index 18)
        mep_amendments_summary = results[18] if not isinstance(results[18], Exception) else []

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
            len(mep_amendments_summary)  # MEP amendments
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
            public_consultations=public_consultations,  # EC Public Consultations
            commission_documents=commission_documents,  # EC Commission Documents
            toolbox_results=toolbox_results,  # MCP Toolbox supplementary
            user_uploaded_documents=user_uploaded_documents,  # User uploaded documents
            mep_amendments_summary=mep_amendments_summary,  # MEP amendments
            tender_context=tender_context,  # Phase 8: Tender data
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
            f"{len(mep_amendments_summary)} MEP amendments) in {search_time:.2f}ms"
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
                                'id': mep_id,
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
        dg_codes: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch European Commission personnel information from organigrammes.

        Includes director-general, deputy DGs, directorate directors, and unit heads
        with standard EC email format (firstname.lastname@ec.europa.eu).

        Args:
            dg_codes: List of DG codes (e.g., ['GROW', 'CLIMA'])

        Returns:
            List of EC personnel information dictionaries
        """
        personnel_data = []

        def _generate_ec_email(name: str) -> str:
            """Generate standard EC email from name (firstname.lastname@ec.europa.eu)"""
            if not name or name in ('Not shown', 'Vacant', 'Unknown'):
                return ''
            parts = name.strip().split()
            if len(parts) < 2:
                return ''
            first = parts[0].lower().replace('é', 'e').replace('è', 'e').replace('ë', 'e').replace('ö', 'o').replace('ü', 'u').replace('ñ', 'n').replace('á', 'a').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ç', 'c')
            last = parts[-1].lower().replace('é', 'e').replace('è', 'e').replace('ë', 'e').replace('ö', 'o').replace('ü', 'u').replace('ñ', 'n').replace('á', 'a').replace('í', 'i').replace('ó', 'o').replace('ú', 'u').replace('ç', 'c')
            return f"{first}.{last}@ec.europa.eu"

        for dg_code in dg_codes:
            try:
                # Get full organigramme (not just summary)
                org = self.knowledge_loader.get_dg_organigramme(dg_code)

                if not org:
                    logger.warning(f"No organigramme data found for DG {dg_code}")
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
        query: str
    ) -> List[Dict[str, Any]]:
        """
        Query internal knowledge base (templates, guides).

        Args:
            query: User query

        Returns:
            List of relevant internal knowledge documents
        """
        knowledge_items = []

        try:
            query_lower = query.lower()

            # Search guides first (reference knowledge)
            # These contain EU jargon, resources, tips for working with APAs, etc.
            matching_guides = self.knowledge_loader.search_guides(query)

            if matching_guides:
                for guide in matching_guides[:self.max_internal_knowledge_results]:
                    guide_content = self.knowledge_loader.get_guide(guide['id'])
                    if guide_content:
                        knowledge_items.append({
                            'type': 'guide',
                            'name': guide['id'],
                            'title': guide['title'],
                            'content': guide_content[:3000],  # Guides can be longer
                            'full_length': len(guide_content),
                            'snippet': guide.get('snippet', '')
                        })

                logger.debug(f"Found {len(matching_guides)} guide matches for query: {query}")

            # Also search templates (document templates)
            matching_templates = self.knowledge_loader.search_templates(query)

            if matching_templates:
                remaining_slots = self.max_internal_knowledge_results - len(knowledge_items)
                for template_name in matching_templates[:remaining_slots]:
                    template_content = self.knowledge_loader.get_template(template_name)
                    if template_content:
                        # Extract title
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

            db.close()

            logger.debug(f"Found {len(train_files)} legislative files for query")
            return train_files

        except Exception as e:
            logger.error(f"Failed to fetch legislative files: {str(e)}")
            return []

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
            now = datetime.now()
            for item in results:
                days_remaining = None
                is_closing_soon = False
                if item.end_date:
                    days_remaining = (item.end_date - now).days
                    is_closing_soon = days_remaining <= 7 and days_remaining >= 0

                consultations.append({
                    'source_type': 'public_consultation',
                    'consultation_id': item.consultation_id,
                    'title': item.title,
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

    async def _fetch_eu_laws_from_database(
        self,
        query: str,
        entities: ExtractedEntities
    ) -> List[Dict[str, Any]]:
        """
        Fetch EU laws from local LEG_2025-11 database.

        This provides FASTER and MORE COMPREHENSIVE access to EU laws:
        - 50k+ laws indexed locally
        - Full-text search capabilities
        - Instant access without API rate limits
        - Links to related laws

        Args:
            query: User query
            entities: Extracted entities (CELEX, policy areas, etc.)

        Returns:
            List of relevant EU laws with full text
        """
        from services.law_database.law_indexer import get_law_indexer

        laws = []

        try:
            law_indexer = get_law_indexer()

            # Priority 1: Direct CELEX lookup
            if entities.celex_numbers:
                for celex in entities.celex_numbers[:3]:  # Max 3 CELEX lookups
                    law = await law_indexer.get_law_by_celex(celex)
                    if law:
                        # Get full text
                        full_text = await law_indexer.get_law_full_text(law['uuid'])

                        laws.append({
                            'celex': celex,
                            'title': law['title'],
                            'doc_type': law['doc_type'],
                            'date': law['date'],
                            'oj_reference': law.get('oj_reference'),
                            'policy_area': law.get('policy_area'),
                            'text_excerpt': full_text[:2000] if full_text else '',
                            'full_text': full_text[:15000] if full_text else '',  # For AI processing
                            'legal_basis': law.get('legal_basis', []),
                            'citations': law.get('citations', []),
                            'source': 'local_database',
                            'uuid': law['uuid']
                        })

                        logger.debug(f"Found law in local database: {celex}")

            # Priority 2: Semantic search if no direct CELEX match
            if not laws:
                search_filters = {}

                # Filter by policy area if detected
                if entities.policy_areas:
                    search_filters['policy_area'] = entities.policy_areas[0]

                # Search local database
                search_results = await law_indexer.search_laws(
                    query=query,
                    filters=search_filters,
                    limit=5  # Max 5 search results
                )

                for result in search_results:
                    # Get full text
                    full_text = await law_indexer.get_law_full_text(result['uuid'])

                    laws.append({
                        'celex': result.get('celex'),
                        'title': result['title'],
                        'doc_type': result['doc_type'],
                        'date': result.get('date'),
                        'oj_reference': result.get('oj_reference'),
                        'policy_area': result.get('policy_area'),
                        'text_excerpt': full_text[:2000] if full_text else '',
                        'full_text': full_text[:15000] if full_text else '',
                        'source': 'local_database_search',
                        'uuid': result['uuid']
                    })

                logger.debug(f"Found {len(search_results)} laws via search")

            logger.info(f"Fetched {len(laws)} laws from local database")

        except Exception as e:
            logger.error(f"Failed to fetch from local EU laws database: {str(e)}")
            # Don't fail context building if local database is unavailable

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

        Args:
            query: User query
            entities: Extracted entities (to help with filtering)

        Returns:
            List of relevant EPRS publications
        """
        eprs_results = []

        try:
            # Build filters based on extracted entities
            filters = {}

            # Filter by policy areas if detected
            if entities.policy_areas:
                # Use first policy area for filtering
                filters['policy_areas'] = entities.policy_areas[0]

            # Filter by committees if detected
            if entities.committee_codes:
                filters['committees'] = entities.committee_codes[0]

            # Search EPRS publications
            search_results = await self.eprs_indexer.search(
                query=query,
                limit=self.max_eprs_results,
                filters=filters if filters else None
            )

            # Format results
            for result in search_results:
                metadata = result.get('metadata', {})

                eprs_results.append({
                    'chunk_id': result.get('id'),
                    'text': result.get('text', '')[:500],  # Excerpt
                    'title': metadata.get('title', 'Unknown'),
                    'publication_type': metadata.get('publication_type', 'unknown'),
                    'publication_url': metadata.get('html_url'),
                    'pdf_url': metadata.get('pdf_url'),
                    'related_celex': metadata.get('related_celex_numbers', '').split(',') if metadata.get('related_celex_numbers') else [],
                    'related_procedures': metadata.get('related_procedures', '').split(',') if metadata.get('related_procedures') else [],
                    'policy_areas': metadata.get('policy_areas', '').split(',') if metadata.get('policy_areas') else [],
                    'distance': result.get('distance')
                })

            if eprs_results:
                logger.debug(f"Found {len(eprs_results)} relevant EPRS publications for query")
            else:
                logger.debug("No EPRS publications found for query")

        except Exception as e:
            logger.error(f"Failed to search EPRS publications: {str(e)}")

        return eprs_results

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

        # Header
        sections.append(f"USER QUERY: {context_data.query}\n")

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
                    sections.append(f"\n  Members ({len(members)}):")
                    for member in members[:10]:  # Show first 10 members
                        sections.append(f"    - {member['name']} ({member['country']}, {member['group']})")
                    if len(members) > 10:
                        sections.append(f"    ... and {len(members) - 10} more members")

                sections.append("")

        # EC Personnel (Commission organigrammes)
        if context_data.ec_personnel:
            sections.append(f"\nEUROPEAN COMMISSION PERSONNEL ({len(context_data.ec_personnel)} DGs):")
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
            for item in context_data.internal_knowledge:
                sections.append(f"- {item['title']}")
                sections.append(f"  Type: {item['type']}")
                sections.append(f"  {item['content'][:1000]}...")
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

        # NEW: Local EU Laws Database (50k+ laws from LEG_2025-11)
        if context_data.local_eu_laws:
            sections.append(f"\nLOCAL EU LAWS DATABASE ({len(context_data.local_eu_laws)} laws):")
            sections.append("IMPORTANT: These laws are from the comprehensive local database of 50k+ EU laws.")
            sections.append("You have access to FULL LEGAL TEXT, not just excerpts from APIs.")
            sections.append("Use this for detailed legal analysis and precise answers.\n")

            for law in context_data.local_eu_laws:
                sections.append(f"- CELEX: {law.get('celex', 'N/A')}")
                sections.append(f"  Title: {law['title'][:200]}..." if len(law['title']) > 200 else f"  Title: {law['title']}")
                sections.append(f"  Type: {law['doc_type']}")
                sections.append(f"  Date: {law.get('date', 'N/A')}")

                if law.get('oj_reference'):
                    sections.append(f"  Official Journal: {law['oj_reference']}")

                if law.get('policy_area'):
                    sections.append(f"  Policy Area: {law['policy_area']}")

                # Show legal relationships
                if law.get('legal_basis'):
                    basis_list = law['legal_basis'][:3]  # First 3
                    sections.append(f"  Legal Basis: {', '.join(basis_list)}")
                    if len(law.get('legal_basis', [])) > 3:
                        sections.append(f"    ... and {len(law['legal_basis']) - 3} more")

                if law.get('citations'):
                    citations_list = law['citations'][:5]  # First 5
                    sections.append(f"  Cites: {', '.join(citations_list)}")
                    if len(law.get('citations', [])) > 5:
                        sections.append(f"    ... and {len(law['citations']) - 5} more")

                # Show text excerpt
                excerpt = law.get('text_excerpt', '')
                if excerpt:
                    sections.append(f"  Excerpt: {excerpt[:1000]}...")

                # Indicate full text is available
                full_text_len = len(law.get('full_text', ''))
                if full_text_len > 0:
                    sections.append(f"  [FULL TEXT AVAILABLE: {full_text_len:,} characters]")

                sections.append(f"  Source: {law.get('source', 'local_database')}")
                sections.append("")

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
