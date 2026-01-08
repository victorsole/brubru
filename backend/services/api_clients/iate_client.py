"""
IATE API Client

IATE (Interactive Terminology for Europe) is the EU's terminology database:
- 8+ million terms in 24 EU languages
- Domain-specific terminology
- Multilingual translations
- Term reliability ratings
- Context and usage notes

Documentation:
- IATE Portal: https://iate.europa.eu/
- API: https://iate.europa.eu/em-api/
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from .base_api_client import BaseAPIClient, AuthType, ResponseFormat

logger = logging.getLogger(__name__)


class IATEDomain(Enum):
    """IATE subject domains"""
    AGRICULTURE = "01"
    FISHERIES = "02"
    ENVIRONMENT = "15"
    ENERGY = "17"
    INDUSTRY = "18"
    TRANSPORT = "19"
    ECONOMICS = "20"
    FINANCE = "21"
    TRADE = "22"
    EDUCATION = "23"
    CULTURE = "24"
    SOCIAL_AFFAIRS = "25"
    HEALTH = "26"
    LAW = "27"
    POLITICS = "28"
    INTERNATIONAL_RELATIONS = "29"
    DEFENSE = "30"
    EU_INSTITUTIONS = "31"
    INFORMATION_TECHNOLOGY = "32"


class IATEReliability(Enum):
    """Term reliability codes"""
    RELIABLE = "3"  # Verified by terminologist
    RELIABLE_WITHOUT_VERIFICATION = "2"  # From reliable source
    NOT_RELIABLE = "1"  # Needs verification


class IATEClient(BaseAPIClient):
    """
    Client for IATE terminology database

    Features:
    - Term search in 24 languages
    - Domain-specific terminology
    - Multilingual translations
    - Term metadata and reliability
    - Usage context and notes
    """

    BASE_URL = "https://iate.europa.eu/em-api"
    SEARCH_ENDPOINT = "/entries"
    TERM_ENDPOINT = "/entry"

    # 24 EU languages + Catalan
    SUPPORTED_LANGUAGES = [
        "bg", "cs", "da", "de", "el", "en", "es", "et", "fi", "fr",
        "ga", "hr", "hu", "it", "lt", "lv", "mt", "nl", "pl", "pt",
        "ro", "sk", "sl", "sv", "ca"
    ]

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        timeout: int = 30
    ):
        """
        Initialize IATE client

        Args:
            endpoint_url: Override base URL
            timeout: Request timeout
        """
        base_url = endpoint_url or self.BASE_URL
        super().__init__(
            base_url=base_url,
            auth_type=AuthType.NONE,  # Public API
            timeout=timeout
        )

        logger.info("Initialized IATE terminology client")

    async def search_terms(
        self,
        query: str,
        source_language: str = "en",
        target_language: Optional[str] = None,
        domain: Optional[IATEDomain] = None,
        reliability: Optional[IATEReliability] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search terminology entries

        Args:
            query: Search term
            source_language: Source language code (en, fr, de, etc.)
            target_language: Target language for translations
            domain: Filter by domain
            reliability: Filter by reliability level
            limit: Maximum results

        Returns:
            List of terminology entries
        """
        if source_language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported source language: {source_language}")

        if target_language and target_language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported target language: {target_language}")

        logger.info(f"Searching IATE terms: {query} ({source_language} -> {target_language or 'all'})")

        params = {
            "query": query,
            "source_lang": source_language,
            "limit": limit,
            "offset": 0
        }

        if target_language:
            params["target_lang"] = target_language

        if domain:
            params["domain"] = domain.value

        if reliability:
            params["reliability"] = reliability.value

        try:
            response = await self.get(
                self.SEARCH_ENDPOINT,
                params=params,
                response_format=ResponseFormat.JSON
            )

            data = response.json()
            entries = []

            if "items" in data:
                for item in data["items"]:
                    entries.append({
                        "id": item.get("id"),
                        "term": item.get("term"),
                        "language": item.get("language"),
                        "domain": item.get("domain"),
                        "subdomain": item.get("subdomain"),
                        "reliability": item.get("reliability"),
                        "definition": item.get("definition"),
                        "context": item.get("context"),
                        "translations": item.get("translations", {})
                    })

            logger.info(f"Found {len(entries)} IATE entries")
            return entries

        except Exception as e:
            logger.error(f"IATE search failed: {str(e)}")
            return []

    async def get_term_by_id(
        self,
        term_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get full term entry by ID

        Args:
            term_id: IATE term identifier

        Returns:
            Complete term entry with all languages
        """
        logger.info(f"Fetching IATE term: {term_id}")

        try:
            response = await self.get(
                f"{self.TERM_ENDPOINT}/{term_id}",
                response_format=ResponseFormat.JSON
            )

            term_data = response.json()

            return {
                "id": term_data.get("id"),
                "domains": term_data.get("domains", []),
                "subdomains": term_data.get("subdomains", []),
                "languages": term_data.get("languages", {}),
                "definitions": term_data.get("definitions", {}),
                "contexts": term_data.get("contexts", {}),
                "notes": term_data.get("notes", {}),
                "sources": term_data.get("sources", []),
                "reliability": term_data.get("reliability"),
                "last_updated": term_data.get("last_updated")
            }

        except Exception as e:
            logger.error(f"Failed to fetch IATE term {term_id}: {str(e)}")
            return None

    async def translate_term(
        self,
        term: str,
        source_language: str,
        target_language: str,
        domain: Optional[IATEDomain] = None
    ) -> List[Dict[str, Any]]:
        """
        Get translations for a specific term

        Args:
            term: Term to translate
            source_language: Source language code
            target_language: Target language code
            domain: Filter by domain

        Returns:
            List of translations with context
        """
        logger.info(f"Translating '{term}' from {source_language} to {target_language}")

        entries = await self.search_terms(
            query=term,
            source_language=source_language,
            target_language=target_language,
            domain=domain,
            limit=20
        )

        translations = []
        for entry in entries:
            if target_language in entry.get("translations", {}):
                target_terms = entry["translations"][target_language]

                for target_term in target_terms:
                    translations.append({
                        "source": term,
                        "target": target_term.get("term"),
                        "domain": entry.get("domain"),
                        "reliability": entry.get("reliability"),
                        "definition": target_term.get("definition"),
                        "context": target_term.get("context")
                    })

        logger.info(f"Found {len(translations)} translations")
        return translations

    async def get_domain_terms(
        self,
        domain: IATEDomain,
        language: str = "en",
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get terms for a specific domain

        Args:
            domain: Subject domain
            language: Language code
            limit: Maximum results

        Returns:
            List of domain-specific terms
        """
        logger.info(f"Fetching terms for domain: {domain.name}")

        params = {
            "domain": domain.value,
            "language": language,
            "limit": limit,
            "offset": 0
        }

        try:
            response = await self.get(
                self.SEARCH_ENDPOINT,
                params=params,
                response_format=ResponseFormat.JSON
            )

            data = response.json()
            terms = []

            if "items" in data:
                for item in data["items"]:
                    terms.append({
                        "id": item.get("id"),
                        "term": item.get("term"),
                        "definition": item.get("definition"),
                        "reliability": item.get("reliability")
                    })

            logger.info(f"Found {len(terms)} terms for {domain.name}")
            return terms

        except Exception as e:
            logger.error(f"Domain terms fetch failed: {str(e)}")
            return []

    async def search_multilingual(
        self,
        query: str,
        languages: List[str],
        domain: Optional[IATEDomain] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search for term in multiple languages simultaneously

        Args:
            query: Search term
            languages: List of language codes
            domain: Filter by domain

        Returns:
            Dictionary with results per language
        """
        logger.info(f"Multilingual search for '{query}' in {len(languages)} languages")

        results = {}

        for lang in languages:
            if lang not in self.SUPPORTED_LANGUAGES:
                logger.warning(f"Skipping unsupported language: {lang}")
                continue

            entries = await self.search_terms(
                query=query,
                source_language=lang,
                domain=domain,
                limit=10
            )

            results[lang] = entries

        return results

    async def get_term_with_all_translations(
        self,
        term: str,
        source_language: str = "en",
        domain: Optional[IATEDomain] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get a term with translations in all supported languages

        Args:
            term: Term to look up
            source_language: Source language
            domain: Filter by domain

        Returns:
            Term with all available translations
        """
        logger.info(f"Fetching complete multilingual entry for '{term}'")

        entries = await self.search_terms(
            query=term,
            source_language=source_language,
            domain=domain,
            limit=1
        )

        if not entries:
            return None

        # Get full entry with all languages
        entry_id = entries[0].get("id")
        if entry_id:
            return await self.get_term_by_id(entry_id)

        return None

    async def verify_translation(
        self,
        source_term: str,
        target_term: str,
        source_language: str,
        target_language: str
    ) -> Dict[str, Any]:
        """
        Verify if a translation is correct according to IATE

        Args:
            source_term: Source term
            target_term: Target term to verify
            source_language: Source language code
            target_language: Target language code

        Returns:
            Verification result with reliability
        """
        logger.info(f"Verifying translation: {source_term} ({source_language}) -> {target_term} ({target_language})")

        translations = await self.translate_term(
            term=source_term,
            source_language=source_language,
            target_language=target_language
        )

        # Check if target_term is in official translations
        is_valid = False
        reliability = None
        context = None

        for trans in translations:
            if trans["target"].lower() == target_term.lower():
                is_valid = True
                reliability = trans.get("reliability")
                context = trans.get("context")
                break

        return {
            "is_valid": is_valid,
            "reliability": reliability,
            "context": context,
            "alternatives": [t["target"] for t in translations[:5]],
            "total_alternatives": len(translations)
        }

    async def health_check(self) -> bool:
        """
        Check if IATE API is accessible

        Returns:
            True if healthy
        """
        try:
            # Try a simple search
            response = await self.get(
                self.SEARCH_ENDPOINT,
                params={"query": "environment", "source_lang": "en", "limit": 1},
                response_format=ResponseFormat.JSON
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return False
