"""
EPRS Content Enricher

Phase 1: Full Content Extraction Pipeline
Enriches EPRS publications by combining RSS metadata with PDF content extraction.

This module serves as a blueprint for enriching other EU institutional
research publications (JRC, Commission studies, etc.)

Process:
1. Take RSS feed entry with basic metadata
2. Download and extract PDF content
3. Extract entities (CELEX numbers, procedures, MEPs, committees)
4. Parse document structure
5. Return enriched EPRSPublication
"""

import logging
import re
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

from schemas.scrapers.scraper_schemas import (
    EPRSPublication,
    EPRSPublicationType,
    EPRSExtractionResult,
    EPRSSection
)
from .pdf_processor import PDFProcessor, PDFContent

logger = logging.getLogger(__name__)


class EPRSContentEnricher:
    """
    Enricher for EPRS Think Tank publications.

    Takes RSS metadata and combines with PDF content extraction
    to create fully enriched EPRSPublication objects.

    Usage:
        enricher = EPRSContentEnricher()

        # From RSS entry
        publication = await enricher.enrich_from_rss(
            title="AI Act - At a Glance",
            link="https://...",
            pdf_url="https://.../document.pdf",
            published_date=datetime.now(),
            categories=["LIBE", "AI"]
        )

        # Full enrichment
        result = await enricher.enrich_publication(publication)
    """

    def __init__(
        self,
        pdf_processor: Optional[PDFProcessor] = None,
        download_dir: Optional[Path] = None
    ):
        """
        Initialize EPRS enricher.

        Args:
            pdf_processor: PDFProcessor instance (creates if None)
            download_dir: Directory for downloaded PDFs
        """
        self.pdf_processor = pdf_processor or PDFProcessor(download_dir=download_dir)
        logger.info("Initialized EPRSContentEnricher")

    async def enrich_from_rss(
        self,
        title: str,
        link: str,
        pdf_url: Optional[str] = None,
        published_date: Optional[datetime] = None,
        summary: Optional[str] = None,
        categories: Optional[List[str]] = None,
        author: Optional[str] = None
    ) -> EPRSPublication:
        """
        Create EPRSPublication from RSS feed data.

        Args:
            title: Publication title
            link: HTML page URL
            pdf_url: PDF download URL (extracted from enclosures or link)
            published_date: Publication date
            summary: Short summary from RSS
            categories: RSS categories/tags
            author: Author name

        Returns:
            EPRSPublication with basic metadata (not yet enriched)
        """
        # Generate publication ID from URL
        publication_id = self._generate_publication_id(link)

        # Detect publication type from title/categories
        pub_type = self._detect_publication_type(title, categories or [])

        # Parse authors
        authors = [author] if author else []

        # Create base publication
        publication = EPRSPublication(
            source="think_tank_rss",
            source_url=link,
            publication_id=publication_id,
            title=title,
            publication_type=pub_type,
            html_url=link,
            pdf_url=pdf_url,
            authors=authors,
            publication_date=published_date,
            summary=summary,
            categories=categories or [],
            is_processed=False
        )

        logger.debug(f"Created EPRSPublication from RSS: {title}")
        return publication

    async def enrich_publication(
        self,
        publication: EPRSPublication,
        download_pdf: bool = True,
        extract_entities: bool = True
    ) -> EPRSExtractionResult:
        """
        Fully enrich EPRS publication with PDF content and entity extraction.

        Args:
            publication: Base publication (from RSS)
            download_pdf: Download and process PDF
            extract_entities: Extract entities from content

        Returns:
            EPRSExtractionResult with enriched publication
        """
        start_time = datetime.now()
        errors = []
        warnings = []

        try:
            # Phase 1: PDF Content Extraction
            if download_pdf and publication.pdf_url:
                logger.info(f"Processing PDF for: {publication.title}")

                try:
                    pdf_content = await self.pdf_processor.process_pdf_from_url(
                        url=str(publication.pdf_url),
                        extract_tables=True,
                        extract_sections=True
                    )

                    # Populate publication with PDF content
                    publication.full_text = pdf_content.full_text
                    publication.word_count = pdf_content.word_count
                    publication.page_count = pdf_content.metadata.page_count
                    publication.extraction_quality = pdf_content.extraction_quality
                    publication.has_full_text = len(pdf_content.full_text) > 100
                    publication.has_tables = len(pdf_content.tables) > 0

                    # Convert sections
                    publication.sections = [
                        {
                            'heading': s.heading,
                            'content': s.content,
                            'page_number': s.page_number,
                            'level': s.level,
                            'word_count': len(s.content.split())
                        }
                        for s in pdf_content.sections
                    ]

                    # Store references
                    publication.references = pdf_content.references

                    # Update metadata from PDF if missing
                    if not publication.authors and pdf_content.metadata.author:
                        publication.authors = [pdf_content.metadata.author]

                    if not publication.publication_date and pdf_content.metadata.creation_date:
                        publication.publication_date = pdf_content.metadata.creation_date

                    logger.info(
                        f"PDF processed: {pdf_content.word_count} words, "
                        f"{len(pdf_content.sections)} sections, "
                        f"quality={pdf_content.extraction_quality}"
                    )

                except Exception as e:
                    error_msg = f"PDF processing failed: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    publication.extraction_quality = "low"

            # Phase 2: Entity Extraction
            if extract_entities and publication.full_text:
                logger.debug("Extracting entities from publication")

                try:
                    # Extract CELEX numbers
                    publication.related_celex_numbers = self._extract_celex_numbers(
                        publication.full_text
                    )

                    # Extract procedure references
                    publication.related_procedures = self._extract_procedure_references(
                        publication.full_text
                    )

                    # Extract MEP names (basic pattern matching)
                    publication.related_meps = self._extract_mep_names(
                        publication.full_text
                    )

                    # Extract committee codes
                    publication.committees = self._extract_committee_codes(
                        publication.full_text,
                        publication.categories
                    )

                    # Detect policy areas
                    publication.policy_areas = self._detect_policy_areas(
                        publication.title,
                        publication.summary or "",
                        publication.categories
                    )

                    # Extract key findings (from conclusions section)
                    publication.key_findings = self._extract_key_findings(
                        publication.sections
                    )

                    logger.info(
                        f"Entities extracted: {len(publication.related_celex_numbers)} CELEX, "
                        f"{len(publication.related_procedures)} procedures, "
                        f"{len(publication.related_meps)} MEPs"
                    )

                except Exception as e:
                    warning_msg = f"Entity extraction partial failure: {str(e)}"
                    warnings.append(warning_msg)
                    logger.warning(warning_msg)

            # Mark as processed
            publication.is_processed = True
            publication.processed_at = datetime.now()

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()

            result = EPRSExtractionResult(
                publication=publication,
                extraction_quality=publication.extraction_quality or "medium",
                errors=errors,
                warnings=warnings,
                processing_time_seconds=processing_time
            )

            logger.info(
                f"Publication enriched: {publication.title} "
                f"(processed in {processing_time:.2f}s, quality={result.extraction_quality})"
            )

            return result

        except Exception as e:
            error_msg = f"Publication enrichment failed: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)

            processing_time = (datetime.now() - start_time).total_seconds()

            return EPRSExtractionResult(
                publication=publication,
                extraction_quality="low",
                errors=errors,
                warnings=warnings,
                processing_time_seconds=processing_time
            )

    def _generate_publication_id(self, url: str) -> str:
        """Generate unique publication ID from URL"""
        import hashlib
        # Extract path component or use hash
        if 'epthinktank.eu' in url:
            # Extract slug from URL
            match = re.search(r'epthinktank\.eu/([^/]+)/?$', url)
            if match:
                return match.group(1)

        # Fallback: hash URL
        return hashlib.md5(url.encode()).hexdigest()[:12]

    def _detect_publication_type(
        self,
        title: str,
        categories: List[str]
    ) -> EPRSPublicationType:
        """
        Detect publication type from title and categories.

        Args:
            title: Publication title
            categories: RSS categories

        Returns:
            EPRSPublicationType
        """
        title_lower = title.lower()

        # Check title for type indicators
        if 'at a glance' in title_lower or 'at-a-glance' in title_lower:
            return EPRSPublicationType.AT_A_GLANCE

        if 'briefing' in title_lower:
            return EPRSPublicationType.BRIEFING

        if 'in-depth analysis' in title_lower or 'in depth analysis' in title_lower:
            return EPRSPublicationType.IN_DEPTH_ANALYSIS

        if 'study' in title_lower or 'research' in title_lower:
            return EPRSPublicationType.STUDY

        # Check categories
        for cat in categories:
            cat_lower = cat.lower()
            if 'briefing' in cat_lower:
                return EPRSPublicationType.BRIEFING
            if 'study' in cat_lower:
                return EPRSPublicationType.STUDY

        return EPRSPublicationType.OTHER

    def _extract_celex_numbers(self, text: str) -> List[str]:
        """Extract CELEX numbers from text"""
        # CELEX pattern: 32024R1689, etc.
        pattern = r'\b\d{1,2}[A-Z]{1,2}\d{4}[A-Z]{1,2}\d{4}\b'
        matches = re.findall(pattern, text)
        return sorted(list(set(matches)))

    def _extract_procedure_references(self, text: str) -> List[str]:
        """Extract legislative procedure references"""
        # Pattern: 2021/0106(COD)
        pattern = r'\b\d{4}/\d{4}\([A-Z]{3,4}\)\b'
        matches = re.findall(pattern, text)
        return sorted(list(set(matches)))

    def _extract_mep_names(self, text: str) -> List[str]:
        """
        Extract MEP names from text (basic pattern matching).

        Note: This is simplified. Phase 3 will use NER and MEP database matching.
        """
        mep_names = []

        # Pattern: "MEP Name" or "rapporteur Name"
        # Look for capitalized names near MEP-related keywords
        mep_keywords = [
            r'MEP\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'rapporteur\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'shadow rapporteur\s+([A-Z][a-z]+\s+[A-Z][a-z]+)',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+)\s+\(MEP\)',
        ]

        for pattern in mep_keywords:
            matches = re.findall(pattern, text, re.IGNORECASE)
            mep_names.extend(matches)

        return sorted(list(set(mep_names)))[:10]  # Limit to 10

    def _extract_committee_codes(
        self,
        text: str,
        categories: List[str]
    ) -> List[str]:
        """Extract EP committee codes"""
        committees = set()

        # EP committee codes
        committee_codes = [
            'AFET', 'DROI', 'SEDE', 'DEVE', 'INTA', 'BUDG', 'CONT',
            'ECON', 'EMPL', 'ENVI', 'ITRE', 'IMCO', 'TRAN', 'REGI',
            'AGRI', 'PECH', 'CULT', 'JURI', 'LIBE', 'AFCO', 'FEMM', 'PETI'
        ]

        # Find in text
        for code in committee_codes:
            if re.search(rf'\b{code}\b', text):
                committees.add(code)

        # Find in categories
        for cat in categories:
            cat_upper = cat.upper()
            for code in committee_codes:
                if code in cat_upper:
                    committees.add(code)

        return sorted(list(committees))

    def _detect_policy_areas(
        self,
        title: str,
        summary: str,
        categories: List[str]
    ) -> List[str]:
        """Detect policy areas from title, summary, and categories"""
        policy_areas = set()

        text = f"{title} {summary}".lower()

        # Policy area keywords
        policy_keywords = {
            'agriculture': ['agriculture', 'farming', 'agri'],
            'climate': ['climate', 'environment', 'green deal'],
            'digital': ['digital', 'technology', 'ai', 'data'],
            'economy': ['economy', 'economic', 'finance', 'monetary'],
            'energy': ['energy', 'renewable', 'fossil'],
            'foreign_affairs': ['foreign', 'external', 'diplomacy'],
            'health': ['health', 'medical', 'pandemic'],
            'justice': ['justice', 'judicial', 'legal'],
            'migration': ['migration', 'asylum', 'border'],
            'security': ['security', 'defense', 'defence'],
            'trade': ['trade', 'commerce', 'tariff'],
            'transport': ['transport', 'mobility', 'aviation'],
        }

        for area, keywords in policy_keywords.items():
            for keyword in keywords:
                if keyword in text:
                    policy_areas.add(area)
                    break

        # Also check categories
        for cat in categories:
            cat_lower = cat.lower()
            for area, keywords in policy_keywords.items():
                if any(k in cat_lower for k in keywords):
                    policy_areas.add(area)

        return sorted(list(policy_areas))

    def _extract_key_findings(self, sections: List[Dict[str, Any]]) -> List[str]:
        """
        Extract key findings from conclusions/summary sections.

        Args:
            sections: Document sections

        Returns:
            List of key finding statements
        """
        key_findings = []

        # Look for conclusions/summary sections
        conclusion_keywords = ['conclusion', 'summary', 'key findings', 'main findings']

        for section in sections:
            heading = section.get('heading', '').lower()

            # Check if this is a conclusions section
            if any(keyword in heading for keyword in conclusion_keywords):
                content = section.get('content', '')

                # Split into sentences and take substantive ones
                sentences = re.split(r'[.!?]+', content)

                for sentence in sentences:
                    sentence = sentence.strip()
                    # Keep sentences that are substantive (not too short/long)
                    if 50 < len(sentence) < 500:
                        key_findings.append(sentence)

                # Limit to 5 key findings
                break

        return key_findings[:5]


# Convenience function for quick enrichment
async def enrich_eprs_publication(
    title: str,
    link: str,
    pdf_url: Optional[str] = None,
    **kwargs
) -> EPRSExtractionResult:
    """
    Convenience function to enrich EPRS publication in one step.

    Args:
        title: Publication title
        link: HTML URL
        pdf_url: PDF download URL
        **kwargs: Additional metadata (published_date, summary, categories, author)

    Returns:
        EPRSExtractionResult with fully enriched publication
    """
    enricher = EPRSContentEnricher()

    # Create base publication from RSS data
    publication = await enricher.enrich_from_rss(
        title=title,
        link=link,
        pdf_url=pdf_url,
        **kwargs
    )

    # Fully enrich with PDF content
    result = await enricher.enrich_publication(publication)

    return result
