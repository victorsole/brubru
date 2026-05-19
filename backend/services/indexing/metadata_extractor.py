"""
Metadata Extractor

Extracts structured metadata from EU documents for enhanced search and filtering.
Part of Phase 13: AI Context Injection - Task 13.2

Extracts:
- Key entities: MEPs, committees, policy areas
- Dates, CELEX numbers, procedure references
- Legal citations: Article X, Directive Y, Regulation Z
- EuroVoc subject matter tags
"""

import logging
import re
from typing import List, Dict, Any, Optional, Set
from datetime import datetime

from knowledge_base.ep_committees import EP_COMMITTEES, EP_COMMITTEE_BY_CODE

logger = logging.getLogger(__name__)


class MetadataExtractor:
    """
    Extract structured metadata from EU documents.

    Capabilities:
    - Entity extraction (MEPs, committees, institutions)
    - Citation detection (CELEX, procedure refs, article numbers)
    - Date extraction (publication, entry into force)
    - Subject classification (EuroVoc domains)
    """

    # Regex patterns for EU-specific entities
    PATTERNS = {
        # CELEX number: 32016R0679 (year=2016, type=R, number=0679)
        'celex': re.compile(r'\b[0-9]{5}[A-Z][0-9]{4,}\b'),

        # Procedure reference: 2021/0106(COD)
        # Note: no trailing \b. The closing `)` is already a non-word
        # character; adding \b would require a following word character,
        # so `2024/0079(COD)` at end of string or before punctuation never
        # matched. Bug caught 19 May 2026 during action-strip debugging.
        'procedure': re.compile(r'\b\d{4}/\d{4}\([A-Z]{2,5}\)'),

        # Article reference: "Article 5", "Art. 12", "Articles 3-7"
        'article': re.compile(r'\b(?:Article|Art\.?)\s+(\d+(?:\s*[-–]\s*\d+)?)\b', re.IGNORECASE),

        # Date patterns: various EU date formats
        'date_dmy': re.compile(r'\b(\d{1,2})[./\s](\d{1,2})[./\s](\d{4})\b'),
        'date_ymd': re.compile(r'\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b'),

        # Committee codes: ENVI, ITRE, LIBE, etc.
        'committee': re.compile(r'\b([A-Z]{4})\b'),

        # Directive/Regulation citations: "Directive 2016/680", "Regulation (EU) 2016/679"
        'directive': re.compile(r'\bDirective\s+(?:\(EU\)\s+)?(\d{4}/\d+)\b', re.IGNORECASE),
        'regulation': re.compile(r'\bRegulation\s+(?:\(EU\)\s+)?(\d{4}/\d+)\b', re.IGNORECASE),
    }

    # Known EU committees (all 26, sourced from ep_committees.py)
    EU_COMMITTEES = {c.code: c.name for c in EP_COMMITTEES}

    # Reverse lookup: natural language names -> committee code
    # Maps lowercase keywords to committee codes for conversational matching
    _COMMITTEE_NAME_LOOKUP: Dict[str, str] = {}
    for _c in EP_COMMITTEES:
        # Full name: "Committee on Environment, Public Health and Food Safety" -> ENVI
        _COMMITTEE_NAME_LOOKUP[_c.full_name.lower()] = _c.code
        # Short name: "Environment, Public Health and Food Safety" -> ENVI
        _COMMITTEE_NAME_LOOKUP[_c.name.lower()] = _c.code
        # First word of short name as keyword: "environment" -> ENVI
        _first_word = _c.name.split(',')[0].split(' and ')[0].strip().lower()
        if len(_first_word) > 4:  # Avoid short ambiguous words
            _COMMITTEE_NAME_LOOKUP[_first_word] = _c.code

    # Additional common shorthand/colloquial names
    _COMMITTEE_NAME_LOOKUP.update({
        'foreign affairs': 'AFET',
        'human rights': 'DROI',
        'defence': 'SEDE',
        'security': 'SEDE',
        'development': 'DEVE',
        'trade': 'INTA',
        'international trade': 'INTA',
        'budget': 'BUDG',
        'budgets': 'BUDG',
        'budgetary control': 'CONT',
        'economic affairs': 'ECON',
        'monetary affairs': 'ECON',
        'employment': 'EMPL',
        'social affairs': 'EMPL',
        'environment': 'ENVI',
        'public health': 'SANT',
        'health': 'SANT',
        'industry': 'ITRE',
        'research': 'ITRE',
        'energy': 'ITRE',
        'internal market': 'IMCO',
        'consumer protection': 'IMCO',
        'transport': 'TRAN',
        'tourism': 'TRAN',
        'regional development': 'REGI',
        'cohesion': 'REGI',
        'agriculture': 'AGRI',
        'fisheries': 'PECH',
        'culture': 'CULT',
        'education': 'CULT',
        'legal affairs': 'JURI',
        'civil liberties': 'LIBE',
        'justice': 'LIBE',
        'home affairs': 'LIBE',
        'constitutional affairs': 'AFCO',
        "women's rights": 'FEMM',
        'gender equality': 'FEMM',
        'petitions': 'PETI',
        'housing': 'HOUS',
        'urban development': 'HOUS',
        'tax': 'FISC',
        'taxation': 'FISC',
        'tax matters': 'FISC',
    })

    # EuroVoc top-level domains (simplified)
    EUROVOC_DOMAINS = [
        'politics', 'international relations', 'European Union', 'law',
        'economics', 'trade', 'finance', 'social affairs', 'education',
        'communications', 'science', 'business and competition',
        'employment and working conditions', 'transport', 'environment',
        'agriculture', 'agri-foodstuffs', 'production', 'energy',
        'industry', 'geography', 'international organisations'
    ]

    def __init__(self):
        """Initialize metadata extractor"""
        logger.info("Initialized MetadataExtractor")

    def extract_all(self, text: str) -> Dict[str, Any]:
        """
        Extract all metadata from text.

        Args:
            text: Document text

        Returns:
            Dictionary with all extracted metadata:
            {
                'celex_numbers': [...],
                'procedure_references': [...],
                'articles': [...],
                'dates': [...],
                'committees': [...],
                'directives': [...],
                'regulations': [...],
                'mep_mentions': [...],
                'eurovoc_domains': [...]
            }
        """
        return {
            'celex_numbers': self.extract_celex_numbers(text),
            'procedure_references': self.extract_procedure_references(text),
            'articles': self.extract_article_references(text),
            'dates': self.extract_dates(text),
            'committees': self.extract_committees(text),
            'directives': self.extract_directive_citations(text),
            'regulations': self.extract_regulation_citations(text),
            'mep_mentions': self.extract_mep_mentions(text),
            'eurovoc_domains': self.classify_eurovoc(text)
        }

    def extract_celex_numbers(self, text: str) -> List[str]:
        """
        Extract CELEX numbers from text.

        Args:
            text: Document text

        Returns:
            List of CELEX numbers (e.g., ['32016R0679', '32018R1807'])
        """
        matches = self.PATTERNS['celex'].findall(text)
        # Remove duplicates and sort
        return sorted(list(set(matches)))

    def extract_procedure_references(self, text: str) -> List[str]:
        """
        Extract OEIL procedure references.

        Args:
            text: Document text

        Returns:
            List of procedure references (e.g., ['2021/0106(COD)'])
        """
        matches = self.PATTERNS['procedure'].findall(text)
        return sorted(list(set(matches)))

    def extract_article_references(self, text: str) -> List[str]:
        """
        Extract Article references.

        Args:
            text: Document text

        Returns:
            List of article numbers (e.g., ['5', '12', '3-7'])
        """
        matches = self.PATTERNS['article'].findall(text)
        # Remove duplicates
        return sorted(list(set(matches)))

    def extract_dates(self, text: str) -> List[Dict[str, str]]:
        """
        Extract dates from text.

        Args:
            text: Document text

        Returns:
            List of dates with format info:
            [
                {'date': '2016-04-27', 'original': '27/04/2016'},
                ...
            ]
        """
        dates = []
        seen = set()

        # Extract DD/MM/YYYY format
        for match in self.PATTERNS['date_dmy'].finditer(text):
            day, month, year = match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day))
                date_str = date_obj.strftime('%Y-%m-%d')
                if date_str not in seen:
                    dates.append({
                        'date': date_str,
                        'original': match.group(0)
                    })
                    seen.add(date_str)
            except ValueError:
                pass

        # Extract YYYY-MM-DD format
        for match in self.PATTERNS['date_ymd'].finditer(text):
            year, month, day = match.groups()
            try:
                date_obj = datetime(int(year), int(month), int(day))
                date_str = date_obj.strftime('%Y-%m-%d')
                if date_str not in seen:
                    dates.append({
                        'date': date_str,
                        'original': match.group(0)
                    })
                    seen.add(date_str)
            except ValueError:
                pass

        return sorted(dates, key=lambda x: x['date'])

    def extract_committees(self, text: str) -> List[Dict[str, str]]:
        """
        Extract EU committee mentions from both codes and natural language.

        Detects:
        - Literal 4-letter codes: "ENVI", "ITRE"
        - Natural language: "environment committee", "the ENVI committee"
        - Conversational: "committee on environment", "transport and tourism"
        - Contextual: "committee responsible for health"

        Args:
            text: Document text

        Returns:
            List of committees:
            [
                {'code': 'ENVI', 'name': 'Environment, Public Health and Food Safety'},
                ...
            ]
        """
        committees = []
        seen = set()

        # 1. Match literal 4-letter committee codes (existing logic)
        matches = self.PATTERNS['committee'].findall(text)
        for code in matches:
            if code in self.EU_COMMITTEES and code not in seen:
                committees.append({
                    'code': code,
                    'name': self.EU_COMMITTEES[code]
                })
                seen.add(code)

        # 2. Match natural language committee names
        text_lower = text.lower()

        # Pattern: "X committee" or "committee on X" or "committee for X"
        committee_context_patterns = [
            re.compile(r'(\w[\w\s,\'-]{3,40}?)\s+committee\b', re.IGNORECASE),
            re.compile(r'\bcommittee\s+(?:on|for|of)\s+([\w\s,\'-]{3,50}?)(?:\.|,|\?|$|\band\b)', re.IGNORECASE),
        ]

        for pattern in committee_context_patterns:
            for match in pattern.finditer(text):
                phrase = match.group(1).strip().lower()
                # Look up in reverse map
                if phrase in self._COMMITTEE_NAME_LOOKUP:
                    code = self._COMMITTEE_NAME_LOOKUP[phrase]
                    if code not in seen:
                        committees.append({
                            'code': code,
                            'name': self.EU_COMMITTEES[code]
                        })
                        seen.add(code)

        # 3. Direct keyword matching against known committee names
        # Sort by length descending so longer matches take priority
        # Use word boundary regex to avoid substring false positives (e.g., "culture" in "agriculture")
        for name, code in sorted(self._COMMITTEE_NAME_LOOKUP.items(), key=lambda x: -len(x[0])):
            if len(name) > 5 and code not in seen:
                if re.search(r'\b' + re.escape(name) + r'\b', text_lower):
                    committees.append({
                        'code': code,
                        'name': self.EU_COMMITTEES[code]
                    })
                    seen.add(code)

        return committees

    def extract_directive_citations(self, text: str) -> List[str]:
        """
        Extract Directive citations.

        Args:
            text: Document text

        Returns:
            List of directive references (e.g., ['2016/680'])
        """
        matches = self.PATTERNS['directive'].findall(text)
        return sorted(list(set(matches)))

    def extract_regulation_citations(self, text: str) -> List[str]:
        """
        Extract Regulation citations.

        Args:
            text: Document text

        Returns:
            List of regulation references (e.g., ['2016/679'])
        """
        matches = self.PATTERNS['regulation'].findall(text)
        return sorted(list(set(matches)))

    # Assistant-intent keywords
    ASSISTANT_INTENT_KEYWORDS = [
        'assistant', 'assistants', 'apa', 'apas',
        'accredited parliamentary assistant',
        'accredited assistant', 'parliamentary assistant',
        'who works for', 'who assists', 'staff of',
        'team of', 'office of', 'cabinet of',
    ]

    # Common false positives for MEP name extraction
    _MEP_NAME_BLACKLIST = {
        'Member States', 'European Union', 'Official Journal',
        'European Parliament', 'European Commission', 'European Council',
        'Council of the European Union', 'Court of Justice',
        'European Central Bank', 'European Court',
        'United Nations', 'United States', 'United Kingdom',
        'EU Law', 'EU Policy', 'EU Budget', 'EU Trade',
        'EU Bubble', 'EU Calendar', 'EU Legislation',
        'Public Affairs', 'Public Health', 'Public Consultation',
        'Internal Market', 'Single Market', 'Green Deal',
        'Common Agricultural', 'Foreign Affairs', 'Legal Affairs',
        'Civil Liberties', 'Regional Development',
        'Dear Colleague', 'Best Regards', 'Kind Regards',
        'Please Note', 'See Also', 'For Example',
        'New York', 'San Francisco', 'Los Angeles',
    }

    # Prefix words that should never start an MEP name
    _MEP_NAME_BAD_PREFIXES = {'EU ', 'The ', 'This ', 'That ', 'What ', 'How ', 'My ', 'Our '}

    def extract_mep_mentions(self, text: str) -> List[str]:
        """
        Extract MEP name mentions from text.

        Detects MEP names in various conversational patterns:
        - "MEP Antonio Decaro"
        - "rapporteur Decaro"
        - "what has Decaro said about..."
        - "Decaro (IT)"
        - "tell me about Antonio Decaro"
        - "LASTNAME in uppercase" (EP convention: "DECARO")

        Args:
            text: Document text

        Returns:
            List of potential MEP names
        """
        patterns = [
            # MEP followed by capitalized name (case-insensitive for "mep")
            re.compile(r'\bMEPs?\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b'),
            # "rapporteur/shadow rapporteur Name"
            re.compile(r'\b(?:rapporteur|shadow rapporteur)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', re.IGNORECASE),
            # Name followed by country in parentheses: "Decaro (IT)"
            re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*\([A-Z]{2}\)\b'),
            # "assistant(s) of/to/for [MEP] Name"
            re.compile(r'\bassistants?\s+(?:of|to|for)\s+(?:MEP\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', re.IGNORECASE),
            # "who works/assists/helps for/with [MEP] Name"
            re.compile(r'\bwho\s+(?:works|assists|helps)\s+(?:for|with)\s+(?:MEP\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', re.IGNORECASE),
            # "Name's assistant(s)" (possessive)
            re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\'s?\s+assistants?\b'),
            # "staff/team/office/cabinet of [MEP] Name"
            re.compile(r'\b(?:staff|team|office|cabinet)\s+of\s+(?:MEP\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b', re.IGNORECASE),

            # --- New broader patterns ---

            # "tell me about / what about / who is / information on [Name]"
            re.compile(r'\b(?:tell me about|what about|who is|information on|info on|details on|profile of)\s+(?:MEP\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', re.IGNORECASE),
            # "what has/did Name said/done/voted" (supports single surname)
            re.compile(r'\bwhat\s+(?:has|did|does)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:said|done|voted|proposed|written|stated)\b', re.IGNORECASE),
            # "Name's position/vote/stance/opinion" (supports single surname)
            re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\'s?\s+(?:position|vote|stance|opinion|view|amendment|report|speech)\b'),
            # "position/vote/stance of Name"
            re.compile(r'\b(?:position|vote|stance|opinion|view|amendment|report)\s+of\s+(?:MEP\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', re.IGNORECASE),
            # "chair/vice-chair/coordinator Name" (supports single surname)
            re.compile(r'\b(?:chair(?:wo)?man|vice[- ]?chair|coordinator|president|vice[- ]?president|questor|chair)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', re.IGNORECASE),
            # "Name, the rapporteur/chair/MEP" (supports single surname)
            re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+(?:the\s+)?(?:rapporteur|shadow rapporteur|chair|coordinator|MEP)\b', re.IGNORECASE),
            # EP convention: UPPERCASE LASTNAME (at least 3 chars, not a known acronym)
            re.compile(r'\b(?:MEP|rapporteur|chair|coordinator|vice-chair)\s+([A-Z]{3,}(?:\s+[A-Z]{3,})*)\b'),
            # "by Name" in legislative context (supports single surname)
            re.compile(r'\b(?:report|amendment|proposal|motion|opinion)\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', re.IGNORECASE),
            # "Name (EPP/S&D/Renew/ECR/Greens/Left/PfE/NI/ESN)" (supports single surname)
            re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*\((?:EPP|S&D|Renew|ECR|Greens?(?:/EFA)?|The Left|GUE/NGL|PfE|NI|ESN|ID)\)', re.IGNORECASE),
        ]

        names = set()
        for pattern in patterns:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                # Filter out common false positives
                if (len(name) > 3
                        and name not in self._MEP_NAME_BLACKLIST
                        and not any(name.startswith(p) for p in self._MEP_NAME_BAD_PREFIXES)):
                    names.add(name)

        return sorted(list(names))

    def detect_assistant_intent(self, text: str) -> bool:
        """
        Detect whether the user is asking about MEP assistants.

        Args:
            text: User query text

        Returns:
            True if the query relates to MEP assistants
        """
        text_lower = text.lower()
        return any(kw in text_lower for kw in self.ASSISTANT_INTENT_KEYWORDS)

    def classify_eurovoc(self, text: str) -> List[str]:
        """
        Classify text by EuroVoc domains (simplified keyword matching).

        In production, this would use:
        - EuroVoc API for official classification
        - ML model trained on EuroVoc taxonomy
        - SPARQL queries against EuroVoc RDF

        Args:
            text: Document text

        Returns:
            List of relevant EuroVoc domains
        """
        text_lower = text.lower()
        domains = []

        # Simple keyword matching (production would be more sophisticated)
        domain_keywords = {
            'politics': ['election', 'parliament', 'vote', 'political', 'democracy'],
            'European Union': ['eu ', 'european union', 'commission', 'council', 'member state'],
            'law': ['legal', 'legislation', 'regulation', 'directive', 'court', 'judgment'],
            'economics': ['economic', 'economy', 'gdp', 'fiscal', 'monetary'],
            'trade': ['trade', 'import', 'export', 'customs', 'tariff'],
            'environment': ['environment', 'climate', 'pollution', 'emission', 'biodiversity'],
            'energy': ['energy', 'renewable', 'electricity', 'gas', 'coal', 'nuclear'],
            'agriculture': ['agricult', 'farm', 'crop', 'livestock', 'rural'],
            'transport': ['transport', 'aviation', 'railway', 'maritime', 'mobility'],
            'social affairs': ['social', 'welfare', 'pension', 'healthcare'],
            'employment and working conditions': ['employment', 'worker', 'labour', 'workplace'],
            'education': ['education', 'school', 'university', 'training', 'student'],
            'science': ['research', 'science', 'innovation', 'technology'],
            'finance': ['finance', 'bank', 'credit', 'investment', 'budget'],
            'industry': ['industry', 'manufacturing', 'production'],
            'international relations': ['international', 'foreign', 'diplomatic', 'treaty']
        }

        for domain, keywords in domain_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                domains.append(domain)

        return domains

    def extract_policy_areas(self, text: str) -> List[str]:
        """
        Extract policy area tags from text.

        Args:
            text: Document text

        Returns:
            List of policy areas
        """
        # Similar to EuroVoc but more specific policy areas
        policy_keywords = {
            'Artificial Intelligence': ['artificial intelligence', 'ai act', 'machine learning', 'neural network'],
            'Data Protection': ['data protection', 'gdpr', 'privacy', 'personal data'],
            'Digital Services': ['digital service', 'dsa ', 'dma ', 'platform regulation'],
            'Climate Change': ['climate change', 'global warming', 'paris agreement', 'net zero'],
            'Migration': ['migration', 'asylum', 'refugee', 'border control'],
            'Energy Transition': ['energy transition', 'renewable energy', 'decarbonization'],
            'Agriculture': ['agriculture', 'agricultural', 'agrifood', 'agri-food', 'farming',
                            'common agricultural policy', 'cap ', 'farm to fork', 'rural development'],
            'Trade Policy': ['trade agreement', 'wto', 'trade policy'],
            'Financial Regulation': ['banking union', 'financial regulation', 'fintech'],
            'Competition Policy': ['antitrust', 'merger', 'state aid', 'competition law']
        }

        text_lower = text.lower()
        areas = []

        for area, keywords in policy_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                areas.append(area)

        return areas

    def extract_legal_basis(self, text: str) -> List[str]:
        """
        Extract legal basis references (e.g., "Article 114 TFEU").

        Args:
            text: Document text

        Returns:
            List of legal basis references
        """
        # Pattern: "Article X TFEU/TEU"
        pattern = re.compile(r'\bArticle\s+(\d+(?:\s*[a-z])?)\s+(TFEU|TEU)\b', re.IGNORECASE)
        matches = pattern.findall(text)

        return [f"Article {num} {treaty}" for num, treaty in matches]

    def extract_metadata_for_legislation(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract comprehensive metadata from legislation document.

        Args:
            document: Document dict with 'text' and existing 'metadata'

        Returns:
            Enhanced metadata dict
        """
        text = document.get('text', '')
        existing_metadata = document.get('metadata', {})

        extracted = self.extract_all(text)

        # Merge with existing metadata
        enhanced_metadata = {
            **existing_metadata,
            'extracted_celex': extracted['celex_numbers'],
            'extracted_procedures': extracted['procedure_references'],
            'articles': extracted['articles'],
            'dates': [d['date'] for d in extracted['dates']],
            'committees': [c['code'] for c in extracted['committees']],
            'directive_citations': extracted['directives'],
            'regulation_citations': extracted['regulations'],
            'eurovoc_domains': extracted['eurovoc_domains'],
            'policy_areas': self.extract_policy_areas(text),
            'legal_basis': self.extract_legal_basis(text)
        }

        return enhanced_metadata

    def extract_metadata_for_mep(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from MEP profile.

        Args:
            profile: MEP profile dict

        Returns:
            Enhanced metadata
        """
        text = profile.get('text', '')
        existing_metadata = profile.get('metadata', {})

        # Extract committee mentions
        committees = self.extract_committees(text)

        # Extract policy areas based on committee work
        policy_areas = self.extract_policy_areas(text)

        enhanced_metadata = {
            **existing_metadata,
            'committees': [c['code'] for c in committees],
            'policy_areas': policy_areas
        }

        return enhanced_metadata

    def extract_metadata_for_procedure(self, procedure: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract metadata from OEIL procedure.

        Args:
            procedure: Procedure dict

        Returns:
            Enhanced metadata
        """
        text = procedure.get('text', '')
        existing_metadata = procedure.get('metadata', {})

        extracted = self.extract_all(text)

        enhanced_metadata = {
            **existing_metadata,
            'celex_numbers': extracted['celex_numbers'],
            'articles': extracted['articles'],
            'committees': [c['code'] for c in extracted['committees']],
            'mep_mentions': extracted['mep_mentions'],
            'policy_areas': self.extract_policy_areas(text),
            'eurovoc_domains': extracted['eurovoc_domains']
        }

        return enhanced_metadata


# Global singleton
_metadata_extractor: Optional[MetadataExtractor] = None


def get_metadata_extractor() -> MetadataExtractor:
    """Get global metadata extractor instance"""
    global _metadata_extractor
    if _metadata_extractor is None:
        _metadata_extractor = MetadataExtractor()
    return _metadata_extractor
