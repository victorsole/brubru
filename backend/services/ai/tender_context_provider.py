"""
Tender Context Provider for AI Chat

Provides tender-related context injection for Brubru AI chat.
Part of Tenderator Phase 8: Chat Integration.

Features:
- Detects tender-related queries (intent detection)
- Fetches relevant tender data for AI context
- Formats tender information for AI consumption
- Supports natural language tender queries:
  - "Find tenders for IT services in France"
  - "What are my matched tenders this week?"
  - "Explain tender 1776-2025"
  - "What documents do I need for this tender?"
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from sqlalchemy.orm import Session
from sqlalchemy import func

from core.database import SessionLocal
from models.tender import Tender, TenderProfile, TenderMatch
from services.tenders.tender_service import TenderService
from services.tenders.dg_grow_enrichment import DGGrowEnrichment
from services.tenders.vocabulary import contract_nature_label, procedure_label

logger = logging.getLogger(__name__)


@dataclass
class TenderIntent:
    """Detected tender-related intent from query"""
    is_tender_query: bool
    intent_type: str  # search, explain, match, checklist, compare, help
    confidence: float

    # Extracted parameters
    publication_number: Optional[str] = None
    tender_id: Optional[int] = None
    search_query: Optional[str] = None
    countries: Optional[List[str]] = None
    cpv_sectors: Optional[List[str]] = None
    value_range: Optional[Tuple[float, float]] = None


@dataclass
class TenderContextData:
    """Tender context data for AI"""
    intent: TenderIntent
    tenders: List[Dict[str, Any]]
    user_matches: List[Dict[str, Any]]
    user_profile: Optional[Dict[str, Any]]
    statistics: Optional[Dict[str, Any]]
    checklist_info: Optional[Dict[str, Any]]
    formatted_context: str
    # EU funding calls (ft_calls_for_proposals) and decentralised-agency
    # procurement (economy_items). Both were invisible to Chat: this provider
    # only ever read the `tenders` table, so a question about an open EIC
    # Accelerator call retrieved nothing while the call sat in the database and
    # rendered on the Tenderator two clicks away.
    funding_calls: List[Dict[str, Any]] = field(default_factory=list)
    agency_opportunities: List[Dict[str, Any]] = field(default_factory=list)


# Intent patterns for tender-related queries
TENDER_INTENT_PATTERNS = {
    'search': [
        r'find\s+tenders?\s+(?:for|about|related\s+to)',
        r'search\s+(?:for\s+)?tenders?',
        r'show\s+(?:me\s+)?tenders?\s+(?:for|in|about)',
        r'tenders?\s+(?:for|in|about|related)',
        r'procurement\s+(?:for|in|about)',
        r'public\s+contracts?\s+(?:for|in|about)',
        r'what\s+tenders?\s+(?:are\s+)?(?:available|open)',
    ],
    'explain': [
        r'explain\s+tender',
        r'what\s+is\s+tender\s+\d+',
        r'tell\s+me\s+about\s+tender',
        r'details?\s+(?:of|for|about)\s+tender',
        r'tender\s+\d{1,6}[-/]\d{4}',  # Publication number pattern
        r'summarize\s+(?:the\s+)?tender',
    ],
    'match': [
        r'(?:my|matched|recommended)\s+tenders?',
        r'tenders?\s+matched\s+(?:to|for)\s+me',
        r'what\s+tenders?\s+match\s+(?:my|me)',
        r'tenders?\s+this\s+week',
        r'new\s+tenders?\s+(?:for\s+me)?',
        r'tenders?\s+i\s+should\s+(?:bid|apply)',
    ],
    'checklist': [
        r'documents?\s+(?:needed|required)\s+(?:for|to)',
        # "what documents do I need for this tender" put "do i need" between
        # "documents" and "for", so the old alternation could never match it:
        # it required (documents|do i need) to be followed IMMEDIATELY by
        # for/to. Split into two patterns that each describe one phrasing.
        r'what\s+documents?\s+(?:do\s+i\s+)?(?:need|require)',
        r'what\s+do\s+i\s+need\s+(?:for|to)',
        r'espd\s+(?:checklist|requirements?|documents?)',
        r'bid\s+(?:preparation|documents?|checklist)',
        r'tender\s+requirements?',
        r'how\s+(?:to|do\s+i)\s+(?:apply|bid)',
    ],
    # EU grant funding, which is not procurement and did not share its
    # vocabulary. "What EIC Accelerator funding is open for startups" matched
    # none of the patterns above, so the provider never ran and Chat answered
    # about open calls with no rows in front of it. These patterns are what
    # route a funding question to the ft_calls_for_proposals lookup.
    'funding': [
        r'\b(?:calls?|call)\s+for\s+proposals?',
        r'\bfunding\s+(?:call|opportunit|programme|program|scheme|window)',
        r'\b(?:is|are)\s+there\s+(?:any\s+)?(?:eu\s+)?funding',
        r'\bfunding\s+for\b',
        r'\b(?:grant|grants)\b.*\b(?:open|available|apply|deadline|call)',
        r'\b(?:open|available|upcoming)\b.*\b(?:grant|grants|funding|call)',
        r'\bapply\s+for\s+(?:eu\s+)?(?:funding|a\s+grant|grants)',
        r'\b(?:eic|eit|horizon|erasmus|life|cerv|interreg|cef)\b.*'
        r'\b(?:call|funding|grant|deadline|cut-?off|apply|open)',
        r'\b(?:accelerator|pathfinder|transition|seal\s+of\s+excellence)\b',
        r'\bwork\s+programme\b.*\b(?:call|budget|topic)',
        r'\btopic\s+id\b',
    ],
    'compare': [
        r'compare\s+tenders?',
        r'difference\s+between\s+tenders?',
        r'which\s+tender\s+(?:is\s+)?better',
        r'tenders?\s+comparison',
    ],
    'help': [
        r'help\s+(?:me\s+)?(?:with\s+)?tenders?',
        r'how\s+(?:does|do)\s+tenders?\s+work',
        r'what\s+is\s+(?:a\s+)?tender(?:ator)?',
        r'tender\s+(?:advice|guidance|tips?)',
        r'bidding\s+(?:advice|guidance|tips?)',
    ],
}

# Country name to ISO code mapping (partial)
COUNTRY_MAPPINGS = {
    'france': 'FR', 'french': 'FR',
    'germany': 'DE', 'german': 'DE',
    'spain': 'ES', 'spanish': 'ES',
    'italy': 'IT', 'italian': 'IT',
    'belgium': 'BE', 'belgian': 'BE',
    'netherlands': 'NL', 'dutch': 'NL',
    'poland': 'PL', 'polish': 'PL',
    'portugal': 'PT', 'portuguese': 'PT',
    'austria': 'AT', 'austrian': 'AT',
    'sweden': 'SE', 'swedish': 'SE',
    'denmark': 'DK', 'danish': 'DK',
    'finland': 'FI', 'finnish': 'FI',
    'ireland': 'IE', 'irish': 'IE',
    'greece': 'GR', 'greek': 'GR',
    'czech': 'CZ', 'czechia': 'CZ', 'czech republic': 'CZ',
    'romania': 'RO', 'romanian': 'RO',
    'hungary': 'HU', 'hungarian': 'HU',
    'bulgaria': 'BG', 'bulgarian': 'BG',
    'croatia': 'HR', 'croatian': 'HR',
    'slovakia': 'SK', 'slovak': 'SK',
    'slovenia': 'SI', 'slovenian': 'SI',
    'lithuania': 'LT', 'lithuanian': 'LT',
    'latvia': 'LV', 'latvian': 'LV',
    'estonia': 'EE', 'estonian': 'EE',
    'cyprus': 'CY', 'cypriot': 'CY',
    'malta': 'MT', 'maltese': 'MT',
    'luxembourg': 'LU', 'luxembourgish': 'LU',
}

# Sector keywords to CPV code prefixes
SECTOR_MAPPINGS = {
    'it': '72', 'software': '72', 'technology': '72', 'digital': '72', 'computer': '72',
    'construction': '45', 'building': '45', 'infrastructure': '45',
    'healthcare': '85', 'health': '85', 'medical': '33', 'pharma': '33',
    'transport': '60', 'logistics': '63', 'shipping': '60',
    'consulting': '79', 'consultancy': '79', 'advisory': '79',
    'training': '80', 'education': '80', 'e-learning': '80',
    'security': '79', 'cybersecurity': '72',
    'environment': '90', 'waste': '90', 'cleaning': '90',
    'energy': '09', 'electricity': '65', 'renewable': '09',
    'food': '15', 'catering': '55',
    'communication': '64', 'telecom': '64', 'marketing': '79',
    'research': '73', 'r&d': '73', 'innovation': '73',
    'engineering': '71', 'architectural': '71', 'design': '71',
    'legal': '79', 'law': '79',
    'financial': '66', 'banking': '66', 'insurance': '66',
    'printing': '79', 'publishing': '22',
}


class TenderContextProvider:
    """
    Provides tender-related context for AI chat integration.

    Detects tender intents in user queries and fetches relevant
    tender data to inject into the AI context.
    """

    def __init__(self, db: Optional[Session] = None):
        """
        Initialize tender context provider.

        Args:
            db: Database session (optional, will create if needed)
        """
        self._db = db
        self._own_db = False

    def _get_db(self) -> Session:
        """Get database session"""
        if self._db is None:
            self._db = SessionLocal()
            self._own_db = True
        return self._db

    def close(self):
        """Close database session if owned"""
        if self._own_db and self._db:
            self._db.close()

    def detect_tender_intent(self, query: str) -> TenderIntent:
        """
        Detect if query is tender-related and extract intent.

        Args:
            query: User query text

        Returns:
            TenderIntent with detected type and parameters
        """
        query_lower = query.lower()

        # Check for tender-related keywords first. This gate runs BEFORE the
        # pattern table, so vocabulary missing here makes the patterns
        # unreachable no matter how well they are written -- which is why
        # "what EIC Accelerator funding is open for startups" retrieved nothing:
        # EU grant funding is not procurement and shares none of its words.
        tender_keywords = ['tender', 'procurement', 'bid', 'contract', 'espd', 'tenderator', 'cpv']
        funding_phrases = [
            'call for proposal', 'calls for proposal', 'funding', 'grant',
            'seal of excellence', 'work programme', 'work program', 'topic id',
            'co-financing', 'cofinancing', 'subsidy', 'subsidies',
            'horizon europe', 'erasmus+', 'creative europe', 'digital europe',
        ]
        # Short, ambiguous tokens need a word boundary: a bare "eic" substring
        # also matches "deicing", and "life" matches "lifetime".
        funding_tokens = r'\b(?:eic|eit|cordis|sedia|ipa|ndici|interreg|cef|cerv|life|amif|isf|eu4health)\b'

        # A TED publication number is itself a tender keyword. It was only
        # looked for AFTER this gate, so "Details for 123/2024" -- which
        # contains no procurement vocabulary at all -- was rejected outright and
        # the extraction below never ran. Three digits minimum and a plausible
        # year, so ordinary dates like "10/2024" do not qualify.
        pub_match = re.search(r'\b(\d{3,6})[-/]((?:19|20)\d{2})\b', query)

        has_tender_keyword = (
            any(kw in query_lower for kw in tender_keywords)
            or any(kw in query_lower for kw in funding_phrases)
            or re.search(funding_tokens, query_lower) is not None
            or pub_match is not None
        )

        if not has_tender_keyword:
            return TenderIntent(
                is_tender_query=False,
                intent_type='none',
                confidence=0.0
            )

        # Detect intent type.
        #
        # Confidence used to be len(pattern)/100, which ranks by how verbosely a
        # regex happens to be written rather than by how much of the question it
        # explains. "New tenders for me this week" lost to a search pattern
        # because that pattern's SOURCE was longer, not because it fitted
        # better. Score on the span matched in the QUERY, and break ties by
        # specificity: an explicit ask ("my matched tenders", "what documents do
        # I need") beats the generic search and help catch-alls.
        _INTENT_PRIORITY = {
            'explain': 6, 'checklist': 5, 'match': 4,
            'funding': 3, 'compare': 2, 'search': 1, 'help': 0,
        }
        detected_type = 'help'  # Default
        max_confidence = 0.0
        best_rank = (-1.0, -1)   # (matched span, priority)

        for intent_type, patterns in TENDER_INTENT_PATTERNS.items():
            for pattern in patterns:
                found = re.search(pattern, query_lower)
                if not found:
                    continue
                span = len(found.group(0))
                rank = (float(span), _INTENT_PRIORITY.get(intent_type, 0))
                if rank > best_rank:
                    best_rank = rank
                    detected_type = intent_type
                    # A longer, more specific hit is a more confident read, but
                    # never certainty: 0.95 stays reserved for an explicit
                    # publication number below.
                    max_confidence = min(0.9, 0.55 + span / 60)

        # A query that cleared the keyword gate is a tender query even when no
        # pattern describes it; it just lands on 'help'. Reporting 0.0 for
        # something we accepted is a contradiction the caller cannot act on.
        if max_confidence == 0.0:
            max_confidence = 0.5

        # Extract publication number if present (matched above, before the gate)
        publication_number = None
        if pub_match:
            publication_number = f"{pub_match.group(1)}-{pub_match.group(2)}"
            detected_type = 'explain'
            max_confidence = 0.95

        # Extract countries and sectors on WORD BOUNDARIES, not substrings.
        # SECTOR_MAPPINGS contains 'it' (IT services, CPV 72), and a plain
        # substring test finds it inside "with", "security", "digital" and
        # "monitoring" -- so "help me with tenders" was classified as an IT
        # query and searched CPV 72. Two-letter keys make this certain rather
        # than unlucky.
        def _mentions(term: str) -> bool:
            return re.search(rf"\b{re.escape(term)}\b", query_lower) is not None

        countries = []
        for country_name, code in COUNTRY_MAPPINGS.items():
            if _mentions(country_name) and code not in countries:
                countries.append(code)

        cpv_sectors = []
        for sector_keyword, cpv_prefix in SECTOR_MAPPINGS.items():
            if _mentions(sector_keyword) and cpv_prefix not in cpv_sectors:
                cpv_sectors.append(cpv_prefix)

        # Extract value range (simple patterns)
        value_range = None
        value_match = re.search(r'(?:under|below|less\s+than|max(?:imum)?)\s*[€$]?\s*(\d+(?:[,.\d]*)?)\s*(?:k|m|million|thousand)?', query_lower)
        if value_match:
            value_str = value_match.group(1).replace(',', '')
            try:
                max_value = float(value_str)
                if 'million' in query_lower or 'm' in value_match.group(0):
                    max_value *= 1_000_000
                elif 'k' in value_match.group(0) or 'thousand' in query_lower:
                    max_value *= 1_000
                value_range = (0, max_value)
            except ValueError:
                pass

        # Extract search query (remaining meaningful words). 'funding' needs one
        # too: it is what grounds the ft_calls_for_proposals lookup, and without
        # it every funding question would retrieve the same undifferentiated
        # first-N open calls regardless of what was asked.
        search_query = None
        if detected_type in ('search', 'funding'):
            search_query = re.sub(
                r'\b(find|search|show|tenders?|for|me|in|about|procurement|contracts?|'
                r'what|which|are|there|is|open|available|the|any|can|i|apply|to|do|how|'
                r'call|calls|proposals?|funding|grants?|deadline)\b',
                '',
                query_lower
            ).strip()
            if len(search_query) < 3:
                search_query = None

        return TenderIntent(
            is_tender_query=True,
            intent_type=detected_type,
            confidence=max_confidence,
            publication_number=publication_number,
            search_query=search_query,
            countries=countries if countries else None,
            cpv_sectors=cpv_sectors if cpv_sectors else None,
            value_range=value_range
        )

    async def fetch_tender_context(
        self,
        intent: TenderIntent,
        user_id: Optional[str] = None,
        limit: int = 5
    ) -> TenderContextData:
        """
        Fetch tender context based on detected intent.

        Args:
            intent: Detected tender intent
            user_id: User ID for personalized data
            limit: Maximum number of results

        Returns:
            TenderContextData with relevant tender information
        """
        db = self._get_db()
        service = TenderService(db)

        tenders = []
        user_matches = []
        user_profile = None
        statistics = None
        checklist_info = None

        try:
            # Fetch based on intent type
            if intent.intent_type == 'explain' and intent.publication_number:
                # Get specific tender
                tender = service.get_tender_by_publication(intent.publication_number)
                if tender:
                    tenders = [self._format_tender(tender)]

            elif intent.intent_type == 'match' and user_id:
                # Get user's matched tenders
                matches = service.get_user_matches(
                    user_id=user_id,
                    include_dismissed=False,
                    limit=limit
                )
                for match in matches:
                    tender = service.get_tender(match.tender_id)
                    if tender:
                        user_matches.append({
                            'match_score': match.match_score,
                            'match_reasons': match.match_reasons,
                            'is_saved': match.is_saved,
                            'tender': self._format_tender(tender)
                        })

                # Get user profile. users.id is a UUID, so int(user_id) raised
                # ValueError on every call; the outer except swallowed it and
                # the profile was silently never loaded, which is why Chat never
                # knew what sector the user was in.
                profile = db.query(TenderProfile).filter(
                    TenderProfile.user_id == user_id
                ).first()
                if profile:
                    user_profile = self._format_profile(profile)

            elif intent.intent_type == 'search':
                # Search tenders
                search_tenders = service.search_tenders(
                    query=intent.search_query,
                    countries=intent.countries,
                    cpv_codes=intent.cpv_sectors,
                    max_value=intent.value_range[1] if intent.value_range else None,
                    status='open',
                    limit=limit
                )
                tenders = [self._format_tender(t) for t in search_tenders]

            elif intent.intent_type == 'checklist':
                # Get ESPD checklist information
                checklist_info = self._get_checklist_template()

            elif intent.intent_type == 'help':
                # General help - include statistics
                statistics = await self._get_statistics(db)

            # Always include some statistics for context
            if statistics is None:
                statistics = await self._get_statistics(db)

        except Exception as e:
            logger.error(f"Failed to fetch tender context: {e}")

        # EU funding calls + agency procurement. Outside the try above on
        # purpose: a failure in the TED branch used to take the whole context
        # down with it, and these two have their own fail-soft handling.
        # Only look when the question is actually about funding or is specific
        # enough to search on. Without this, a bare "help me with tenders" pulled
        # three unrelated open calls into the prompt: budget spent on noise, and
        # an invitation for the model to answer with whatever happened to be
        # nearest the top.
        keywords = self._context_keywords(intent)
        wants_funding = intent.intent_type in ('funding', 'search', 'match') or bool(keywords)
        funding_calls = self._fetch_funding_calls(db, keywords, limit) if wants_funding else []
        agency_opportunities = (
            self._fetch_agency_opportunities(db, keywords, limit) if wants_funding else []
        )

        # Format context for AI
        formatted_context = self._format_context_for_ai(
            intent=intent,
            tenders=tenders,
            user_matches=user_matches,
            user_profile=user_profile,
            statistics=statistics,
            checklist_info=checklist_info,
            funding_calls=funding_calls,
            agency_opportunities=agency_opportunities,
        )

        return TenderContextData(
            intent=intent,
            tenders=tenders,
            user_matches=user_matches,
            user_profile=user_profile,
            statistics=statistics,
            checklist_info=checklist_info,
            formatted_context=formatted_context,
            funding_calls=funding_calls,
            agency_opportunities=agency_opportunities,
        )

    def _fetch_funding_calls(self, db, keywords: List[str], limit: int) -> List[Dict[str, Any]]:
        """Open EU funding calls matching the query, from ft_calls_for_proposals.

        This is the table behind the Tenderator's "Calls for proposals" chip and
        the EIC lens. Chat could not see it at all, which is the retrieval gap
        that turns into invented answers: asked about an open Accelerator cut-off
        the model had no rows to ground on.
        """
        from sqlalchemy import text as _sql
        params: Dict[str, Any] = {"lim": limit}
        where = ["is_test = FALSE", "(deadline IS NULL OR deadline >= now())"]
        if keywords:
            ors = []
            for i, kw in enumerate(keywords[:6]):
                ors.append(f"(title ILIKE :kw{i} OR description ILIKE :kw{i} OR topic_id ILIKE :kw{i})")
                params[f"kw{i}"] = f"%{kw}%"
            where.append("(" + " OR ".join(ors) + ")")
        try:
            rows = db.execute(_sql(
                "SELECT topic_id, title, description, status, deadline, "
                "       indicative_budget, budget_currency, framework_programme, source_url "
                "FROM ft_calls_for_proposals "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY deadline ASC NULLS LAST LIMIT :lim"
            ), params).fetchall()
            return [
                {
                    "topic_id": r.topic_id,
                "title": r.title,
                "description": (r.description or "")[:300] or None,
                "status": r.status,
                "deadline": r.deadline.isoformat() if r.deadline else None,
                "budget": float(r.indicative_budget) if r.indicative_budget else None,
                "currency": r.budget_currency or "EUR",
                    "programme": r.framework_programme,
                    "source_url": r.source_url,
                }
                for r in rows
            ]
        except Exception as exc:
            # Fail soft: the caller renders a "none on file" block, which is a
            # safe answer. Raising here would take the whole chat turn down.
            logger.warning("funding-call context fetch failed: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
            return []

    def _fetch_agency_opportunities(self, db, keywords: List[str], limit: int) -> List[Dict[str, Any]]:
        """Open procurement run by decentralised EU bodies (economy_items)."""
        from sqlalchemy import text as _sql
        params: Dict[str, Any] = {
            "lim": limit,
            "types": ["tender", "grant", "eoi_call", "startup_funding", "framework"],
        }
        where = ["item_type = ANY(:types)", "(document_date IS NULL OR document_date >= now())"]
        if keywords:
            ors = []
            for i, kw in enumerate(keywords[:6]):
                ors.append(f"(title ILIKE :akw{i} OR summary ILIKE :akw{i} OR body_code ILIKE :akw{i})")
                params[f"akw{i}"] = f"%{kw}%"
            where.append("(" + " OR ".join(ors) + ")")
        try:
            rows = db.execute(_sql(
                "SELECT body_code, item_type, title, summary, document_date, public_url "
                "FROM economy_items "
                f"WHERE {' AND '.join(where)} "
                "ORDER BY document_date ASC NULLS LAST LIMIT :lim"
            ), params).fetchall()
            return [
                {
                    "body": (r.body_code or "").upper(),
                "kind": r.item_type,
                "title": r.title,
                "summary": (r.summary or "")[:300] or None,
                    "deadline": r.document_date.isoformat() if r.document_date else None,
                    "source_url": r.public_url,
                }
                for r in rows
            ]
        except Exception as exc:
            logger.warning("agency-opportunity context fetch failed: %s", exc)
            try:
                db.rollback()
            except Exception:
                pass
            return []

    @staticmethod
    def _context_keywords(intent: TenderIntent) -> List[str]:
        """Search terms to ground the funding lookups on."""
        words: List[str] = []
        if intent.search_query:
            words += [w for w in re.split(r"[^\w-]+", intent.search_query) if len(w) > 3]
        if intent.cpv_sectors:
            words += list(intent.cpv_sectors)
        # De-duplicate, preserve order.
        seen, out = set(), []
        for w in words:
            key = w.lower()
            if key not in seen:
                seen.add(key)
                out.append(w)
        return out

    def _format_tender(self, tender: Tender) -> Dict[str, Any]:
        """Format tender for context"""
        return {
            'id': tender.id,
            'publication_number': tender.publication_number,
            'title': tender.title,
            'buyer_name': tender.official_name,  # Map to official_name
            'buyer_country': tender.buyer_country,
            'estimated_value': tender.estimated_value,
            'currency': tender.estimated_value_currency,  # Map to estimated_value_currency
            'cpv_main': tender.cpv_main,
            'procedure_type': tender.procedure_type,
            'procedure_label': procedure_label(tender.procedure_type),
            'contract_nature_label': contract_nature_label(tender.contract_nature),
            'submission_deadline': tender.submission_deadline.isoformat() if tender.submission_deadline else None,
            'status': tender.status,
            'description': tender.description[:500] if tender.description else None,
            'sme_suitability_score': tender.sme_suitability_score,
            'ted_url': f"https://ted.europa.eu/en/notice/-/detail/{tender.publication_number}"
        }

    def _format_profile(self, profile: TenderProfile) -> Dict[str, Any]:
        """Format user profile for context"""
        return {
            'company_name': profile.company_name,
            'company_size': profile.company_size,
            'cpv_categories': profile.cpv_categories,
            'countries_of_interest': profile.countries_of_interest,
            'max_tender_value': profile.max_tender_value,
            'min_deadline_days': profile.min_deadline_days
        }

    def _get_checklist_template(self) -> Dict[str, Any]:
        """Get ESPD checklist template"""
        return {
            'parts': [
                {
                    'name': 'Part III: Exclusion Grounds',
                    'categories': [
                        {
                            'code': 'A',
                            'name': 'Criminal Convictions',
                            'items': [
                                'Self-declaration: No convictions for participation in criminal organization',
                                'Self-declaration: No convictions for corruption',
                                'Self-declaration: No convictions for fraud',
                                'Self-declaration: No convictions for terrorist offences',
                                'Self-declaration: No convictions for money laundering'
                            ]
                        },
                        {
                            'code': 'B',
                            'name': 'Payment of Taxes and Social Security',
                            'items': [
                                'Tax compliance certificate or declaration',
                                'Social security payments certificate',
                                'Certificate from tax authority'
                            ]
                        },
                        {
                            'code': 'C',
                            'name': 'Insolvency and Conflicts',
                            'items': [
                                'Declaration: Not in bankruptcy proceedings',
                                'Declaration: Not in liquidation',
                                'Declaration: No grave professional misconduct'
                            ]
                        }
                    ]
                },
                {
                    'name': 'Part IV: Selection Criteria',
                    'categories': [
                        {
                            'code': 'A',
                            'name': 'Suitability',
                            'items': [
                                'Trade/professional register extract',
                                'Authorization/license (if required)',
                                'Professional qualification certificates'
                            ]
                        },
                        {
                            'code': 'B',
                            'name': 'Economic & Financial Standing',
                            'items': [
                                'Annual financial statements (last 3 years)',
                                'Bank statement or financial reference',
                                'Professional indemnity insurance certificate',
                                'Turnover declaration'
                            ]
                        },
                        {
                            'code': 'C',
                            'name': 'Technical & Professional Ability',
                            'items': [
                                'List of reference projects (last 3-5 years)',
                                'Key personnel CVs',
                                'Technical equipment list',
                                'Quality management certificates (ISO 9001)',
                                'Environmental certificates (ISO 14001)',
                                'Information security certificates (ISO 27001)'
                            ]
                        }
                    ]
                }
            ],
            'tips': [
                'Start preparation at least 30 days before deadline',
                'Gather all certificates early - some take weeks to obtain',
                'Check if electronic signatures are accepted',
                'Review tender-specific requirements carefully',
                'Consider consortium/subcontracting if lacking certain qualifications'
            ]
        }

    async def _get_statistics(self, db: Session) -> Dict[str, Any]:
        """Get tender statistics"""
        try:
            total_tenders = db.query(Tender).count()
            open_tenders = db.query(Tender).filter(Tender.status == 'open').count()

            week_ago = datetime.utcnow() - timedelta(days=7)
            new_this_week = db.query(Tender).filter(
                Tender.publication_date >= week_ago
            ).count()

            avg_value = db.query(func.avg(Tender.estimated_value)).filter(
                Tender.estimated_value.isnot(None),
                Tender.status == 'open'
            ).scalar()

            return {
                'total_tenders': total_tenders,
                'open_tenders': open_tenders,
                'new_this_week': new_this_week,
                'average_value': float(avg_value) if avg_value else None
            }
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {}

    def _format_context_for_ai(
        self,
        intent: TenderIntent,
        tenders: List[Dict[str, Any]],
        user_matches: List[Dict[str, Any]],
        user_profile: Optional[Dict[str, Any]],
        statistics: Optional[Dict[str, Any]],
        checklist_info: Optional[Dict[str, Any]],
        funding_calls: Optional[List[Dict[str, Any]]] = None,
        agency_opportunities: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Format tender context for AI consumption"""
        sections = []

        sections.append("=" * 60)
        sections.append("TENDERATOR: EU PUBLIC PROCUREMENT DATA")
        sections.append("=" * 60)

        # Intent info
        sections.append(f"\nDETECTED INTENT: {intent.intent_type.upper()}")
        sections.append(f"Confidence: {intent.confidence:.0%}")

        if intent.publication_number:
            sections.append(f"Publication Number: {intent.publication_number}")
        if intent.countries:
            sections.append(f"Countries: {', '.join(intent.countries)}")
        if intent.cpv_sectors:
            sections.append(f"CPV Sectors: {', '.join(intent.cpv_sectors)}")

        # Statistics
        if statistics:
            sections.append(f"\nTENDER DATABASE STATISTICS:")
            sections.append(f"- Total tenders tracked: {statistics.get('total_tenders', 'N/A')}")
            sections.append(f"- Currently open: {statistics.get('open_tenders', 'N/A')}")
            sections.append(f"- New this week: {statistics.get('new_this_week', 'N/A')}")
            if statistics.get('average_value'):
                sections.append(f"- Average value: EUR {statistics['average_value']:,.0f}")

        # User profile
        if user_profile:
            sections.append(f"\nUSER'S TENDER PROFILE:")
            sections.append(f"- Company: {user_profile.get('company_name', 'N/A')}")
            sections.append(f"- Size: {user_profile.get('company_size', 'N/A')}")
            sections.append(f"- Sectors: {', '.join(user_profile.get('cpv_categories', []))}")
            sections.append(f"- Target countries: {', '.join(user_profile.get('countries_of_interest', []))}")
            if user_profile.get('max_tender_value'):
                sections.append(f"- Max value preference: EUR {user_profile['max_tender_value']:,.0f}")

        # Matched tenders
        if user_matches:
            sections.append(f"\nUSER'S MATCHED TENDERS ({len(user_matches)}):")
            for i, match in enumerate(user_matches, 1):
                tender = match['tender']
                sections.append(f"\n{i}. {tender['title'][:100]}...")
                sections.append(f"   Match Score: {match['match_score']}%")
                sections.append(f"   Country: {tender['buyer_country']}")
                sections.append(f"   Value: EUR {tender['estimated_value']:,.0f}" if tender.get('estimated_value') else "   Value: Not specified")
                sections.append(f"   Deadline: {tender.get('submission_deadline', 'N/A')}")
                sections.append(f"   Status: {tender['status']}")
                if match.get('match_reasons'):
                    sections.append(f"   Match reasons: {', '.join(match['match_reasons'][:3])}")
                sections.append(f"   TED URL: {tender['ted_url']}")

        # Search results
        elif tenders:
            sections.append(f"\nTENDER SEARCH RESULTS ({len(tenders)}):")
            for i, tender in enumerate(tenders, 1):
                sections.append(f"\n{i}. {tender['title'][:100]}...")
                sections.append(f"   Publication: {tender['publication_number']}")
                sections.append(f"   Buyer: {tender['buyer_name']} ({tender['buyer_country']})")
                sections.append(f"   Value: EUR {tender['estimated_value']:,.0f}" if tender.get('estimated_value') else "   Value: Not specified")
                sections.append(
                    f"   Procedure: {tender.get('procedure_label') or tender.get('procedure_type') or 'Not stated'}"
                )
                sections.append(f"   Deadline: {tender.get('submission_deadline', 'N/A')}")
                sections.append(f"   CPV: {tender['cpv_main']}")
                if tender.get('sme_suitability_score'):
                    sections.append(f"   SME Suitability: {tender['sme_suitability_score']}%")
                if tender.get('description'):
                    sections.append(f"   Description: {tender['description'][:200]}...")
                sections.append(f"   TED URL: {tender['ted_url']}")

        # EU funding calls (F&T portal). Emitted whenever the question was about
        # funding, INCLUDING when nothing matched: a block that says "nothing on
        # file" is what stops the model filling the silence with a plausible
        # topic id and a plausible cut-off date. Omitted entirely for questions
        # that were never about funding, so the prompt budget goes elsewhere.
        asked_about_funding = intent.intent_type in ('funding', 'search', 'match')
        if funding_calls or asked_about_funding:
            sections.append("\nEU FUNDING CALLS ON FILE (Funding & Tenders Portal):")
        if funding_calls:
            for i, call in enumerate(funding_calls, 1):
                sections.append(f"\n{i}. {(call['title'] or '')[:120]}")
                sections.append(f"   Topic ID: {call.get('topic_id') or 'Not stated'}")
                sections.append(f"   Programme period: {call.get('programme') or 'Not stated'}")
                sections.append(f"   Status: {call.get('status') or 'Not stated'}")
                sections.append(f"   Deadline: {call.get('deadline') or 'Not stated'}")
                if call.get("budget"):
                    sections.append(f"   Indicative budget: {call['currency']} {call['budget']:,.0f}")
                if call.get("source_url"):
                    sections.append(f"   Call page: {call['source_url']}")
        elif asked_about_funding:
            sections.append(
                "- None on file matching this question. Say so plainly. Do NOT "
                "invent a topic ID, a cut-off date or a budget: send the user to "
                "the Tenderator (https://brubru.beresol.eu/tenderator) or to the "
                "Funding and Tenders Portal instead."
            )

        # Decentralised-agency procurement.
        if agency_opportunities or asked_about_funding:
            sections.append("\nEU AGENCY PROCUREMENT ON FILE:")
        if agency_opportunities:
            for i, item in enumerate(agency_opportunities, 1):
                sections.append(f"\n{i}. {(item['title'] or '')[:120]}")
                sections.append(f"   Body: {item.get('body') or 'Not stated'}")
                sections.append(f"   Kind: {item.get('kind') or 'Not stated'}")
                sections.append(f"   Deadline: {item.get('deadline') or 'Not stated'}")
                if item.get("source_url"):
                    sections.append(f"   Notice: {item['source_url']}")
        else:
            sections.append(
                "- None on file matching this question. Say so plainly rather "
                "than describing a notice that is not listed here."
            )

        # Checklist info
        if checklist_info:
            sections.append(f"\nESPD DOCUMENT CHECKLIST:")
            sections.append("The European Single Procurement Document (ESPD) requires these standard documents:")
            for part in checklist_info['parts']:
                sections.append(f"\n{part['name']}:")
                for category in part['categories']:
                    sections.append(f"  {category['code']}. {category['name']}:")
                    for item in category['items'][:3]:  # Show first 3
                        sections.append(f"     - {item}")
                    if len(category['items']) > 3:
                        sections.append(f"     ... and {len(category['items']) - 3} more")

            sections.append("\nQUICK TIPS:")
            for tip in checklist_info['tips'][:3]:
                sections.append(f"- {tip}")

        # DG GROW sector intelligence
        dg_grow_context = self._get_dg_grow_context(intent, tenders, user_profile)
        if dg_grow_context:
            sections.append(dg_grow_context)

        sections.append("\n" + "=" * 60)
        sections.append("Use this tender data to help the user. Reference specific")
        sections.append("tenders by their publication numbers. Provide actionable advice.")
        sections.append("=" * 60)

        return "\n".join(sections)


    def _get_dg_grow_context(
        self,
        intent: TenderIntent,
        tenders: List[Dict[str, Any]],
        user_profile: Optional[Dict[str, Any]],
    ) -> str:
        """
        Get DG GROW sector intelligence for AI context.
        Adds notified bodies, regulatory risks, and ecosystem data.
        """
        try:
            db = self._get_db()
            enrichment = DGGrowEnrichment(db)

            # Determine CPV codes to look up
            cpv_codes = set()
            if intent.cpv_sectors:
                cpv_codes.update(intent.cpv_sectors)
            if user_profile and user_profile.get("cpv_categories"):
                cpv_codes.update(user_profile["cpv_categories"])
            for tender in tenders[:3]:
                if tender.get("cpv_main"):
                    cpv_codes.add(tender["cpv_main"][:2])

            if not cpv_codes:
                return ""

            # Get context for the primary CPV code
            primary_cpv = list(cpv_codes)[0]
            return enrichment.format_sector_context_for_ai(primary_cpv)

        except Exception as e:
            logger.debug(f"DG GROW context enrichment failed: {e}")
            return ""


# Global singleton
_tender_context_provider: Optional[TenderContextProvider] = None


def get_tender_context_provider() -> TenderContextProvider:
    """Get global tender context provider instance"""
    global _tender_context_provider
    if _tender_context_provider is None:
        _tender_context_provider = TenderContextProvider()
    return _tender_context_provider
