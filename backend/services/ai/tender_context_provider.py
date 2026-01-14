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
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

from core.database import SessionLocal
from models.tender import Tender, TenderProfile, TenderMatch
from services.tenders.tender_service import TenderService

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
        r'what\s+(?:documents?|do\s+i\s+need)\s+(?:for|to)',
        r'espd\s+(?:checklist|requirements?|documents?)',
        r'bid\s+(?:preparation|documents?|checklist)',
        r'tender\s+requirements?',
        r'how\s+(?:to|do\s+i)\s+(?:apply|bid)',
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

        # Check for tender-related keywords first
        tender_keywords = ['tender', 'procurement', 'bid', 'contract', 'espd', 'tenderator', 'cpv']
        has_tender_keyword = any(kw in query_lower for kw in tender_keywords)

        if not has_tender_keyword:
            return TenderIntent(
                is_tender_query=False,
                intent_type='none',
                confidence=0.0
            )

        # Detect intent type
        detected_type = 'help'  # Default
        max_confidence = 0.0

        for intent_type, patterns in TENDER_INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    # Calculate confidence based on pattern specificity
                    pattern_len = len(pattern)
                    confidence = min(0.95, 0.5 + (pattern_len / 100))

                    if confidence > max_confidence:
                        max_confidence = confidence
                        detected_type = intent_type

        # Extract publication number if present
        publication_number = None
        pub_match = re.search(r'(\d{1,6})[-/](\d{4})', query)
        if pub_match:
            publication_number = f"{pub_match.group(1)}-{pub_match.group(2)}"
            detected_type = 'explain'
            max_confidence = 0.95

        # Extract countries
        countries = []
        for country_name, code in COUNTRY_MAPPINGS.items():
            if country_name in query_lower:
                if code not in countries:
                    countries.append(code)

        # Extract sectors/CPV categories
        cpv_sectors = []
        for sector_keyword, cpv_prefix in SECTOR_MAPPINGS.items():
            if sector_keyword in query_lower:
                if cpv_prefix not in cpv_sectors:
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

        # Extract search query (remaining meaningful words)
        search_query = None
        if detected_type == 'search':
            # Remove intent keywords and extract what they're searching for
            search_query = re.sub(
                r'(find|search|show|tenders?|for|me|in|about|procurement|contracts?)',
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

                # Get user profile
                profile = db.query(TenderProfile).filter(
                    TenderProfile.user_id == int(user_id)
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

        # Format context for AI
        formatted_context = self._format_context_for_ai(
            intent=intent,
            tenders=tenders,
            user_matches=user_matches,
            user_profile=user_profile,
            statistics=statistics,
            checklist_info=checklist_info
        )

        return TenderContextData(
            intent=intent,
            tenders=tenders,
            user_matches=user_matches,
            user_profile=user_profile,
            statistics=statistics,
            checklist_info=checklist_info,
            formatted_context=formatted_context
        )

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
        checklist_info: Optional[Dict[str, Any]]
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
                sections.append(f"   Procedure: {tender['procedure_type']}")
                sections.append(f"   Deadline: {tender.get('submission_deadline', 'N/A')}")
                sections.append(f"   CPV: {tender['cpv_main']}")
                if tender.get('sme_suitability_score'):
                    sections.append(f"   SME Suitability: {tender['sme_suitability_score']}%")
                if tender.get('description'):
                    sections.append(f"   Description: {tender['description'][:200]}...")
                sections.append(f"   TED URL: {tender['ted_url']}")

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

        sections.append("\n" + "=" * 60)
        sections.append("Use this tender data to help the user. Reference specific")
        sections.append("tenders by their publication numbers. Provide actionable advice.")
        sections.append("=" * 60)

        return "\n".join(sections)


# Global singleton
_tender_context_provider: Optional[TenderContextProvider] = None


def get_tender_context_provider() -> TenderContextProvider:
    """Get global tender context provider instance"""
    global _tender_context_provider
    if _tender_context_provider is None:
        _tender_context_provider = TenderContextProvider()
    return _tender_context_provider
