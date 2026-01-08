"""
Citation & Source Tracking

Track sources used in AI responses and generate proper footnotes.
Part of Phase 13: AI Context Injection - Task 13.7

Features:
- Track which sources were used in AI responses
- Generate formatted footnotes
- Link citations to source documents
- Support multiple citation formats (IEEE, APA, MLA, Chicago)
- Deduplicate citations
"""

import logging
import re
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Citation:
    """Single citation"""
    id: int  # Citation number [1], [2], etc.
    type: str  # 'legislation', 'procedure', 'mep', 'news'
    title: str
    url: str
    metadata: Dict[str, Any]  # Additional info (date, CELEX, etc.)


class CitationTracker:
    """
    Track citations and generate footnotes for AI responses.

    Usage:
    1. Add sources used during context building
    2. Parse AI response for citation markers [1], [2], etc.
    3. Generate formatted footnotes
    4. Return response with proper citations
    """

    # Citation format templates
    FORMATS = {
        'ieee': {
            'legislation': '[{id}] {title}, CELEX:{celex}, {date}. Available: {url}',
            'procedure': '[{id}] {title}, Procedure {reference}, {status}. Available: {url}',
            'mep': '[{id}] {name}, Member of the European Parliament ({country}). Available: {url}',
            'news': '[{id}] "{title}", {source}, {published}. Available: {url}',
            'default': '[{id}] {title}. Available: {url}'
        },
        'apa': {
            'legislation': '{title}. ({date}). CELEX:{celex}. Retrieved from {url}',
            'procedure': '{title}. ({date}). Procedure {reference}. Retrieved from {url}',
            'mep': '{name}. Member of the European Parliament, {country}. Retrieved from {url}',
            'news': '{title}. ({published}). {source}. {url}',
            'default': '{title}. Retrieved from {url}'
        }
    }

    def __init__(self, format: str = 'ieee'):
        """
        Initialize citation tracker.

        Args:
            format: Citation format ('ieee', 'apa')
        """
        self.format = format
        self.citations: List[Citation] = []
        self._citation_map: Dict[str, int] = {}  # source_id -> citation_number

        logger.debug(f"Initialized CitationTracker (format={format})")

    def add_source(
        self,
        source_id: str,
        source_type: str,
        title: str,
        url: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Add a source and get its citation number.

        Args:
            source_id: Unique source identifier
            source_type: Type of source
            title: Source title
            url: Source URL
            metadata: Additional metadata

        Returns:
            Citation number (1-indexed)

        Example:
            >>> tracker.add_source(
            ...     source_id='32016R0679',
            ...     source_type='legislation',
            ...     title='General Data Protection Regulation',
            ...     url='https://eur-lex.europa.eu/...',
            ...     metadata={'celex': '32016R0679', 'date': '2016-04-27'}
            ... )
            1
        """
        # Check if already added
        if source_id in self._citation_map:
            return self._citation_map[source_id]

        # Create new citation
        citation_number = len(self.citations) + 1

        citation = Citation(
            id=citation_number,
            type=source_type,
            title=title,
            url=url,
            metadata=metadata or {}
        )

        self.citations.append(citation)
        self._citation_map[source_id] = citation_number

        logger.debug(f"Added citation [{citation_number}]: {title}")

        return citation_number

    def add_sources_batch(
        self,
        sources: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Add multiple sources at once.

        Args:
            sources: List of source dicts with keys:
                - id: Source ID
                - type: Source type
                - title: Title
                - url: URL
                - metadata: Additional metadata

        Returns:
            Dict mapping source_id to citation_number
        """
        citation_map = {}

        for source in sources:
            source_id = source.get('id', '')
            if not source_id:
                continue

            citation_num = self.add_source(
                source_id=source_id,
                source_type=source.get('type', 'default'),
                title=source.get('title', 'Untitled'),
                url=source.get('url', ''),
                metadata=source.get('metadata', {})
            )

            citation_map[source_id] = citation_num

        logger.info(f"Added {len(citation_map)} sources in batch")

        return citation_map

    def format_citation(self, citation: Citation) -> str:
        """
        Format a single citation.

        Args:
            citation: Citation to format

        Returns:
            Formatted citation string
        """
        format_templates = self.FORMATS.get(self.format, self.FORMATS['ieee'])
        template = format_templates.get(citation.type, format_templates['default'])

        # Build format params
        params = {
            'id': citation.id,
            'title': citation.title,
            'url': citation.url,
            **citation.metadata
        }

        try:
            formatted = template.format(**params)
            return formatted
        except KeyError as e:
            # Missing field, use default format
            logger.warning(f"Missing field {e} for citation {citation.id}, using default format")
            return f"[{citation.id}] {citation.title}. Available: {citation.url}"

    def generate_footnotes(self) -> str:
        """
        Generate formatted footnotes section.

        Returns:
            Formatted footnotes string

        Example output:
        ```
        SOURCES

        [1] General Data Protection Regulation, CELEX:32016R0679, 2016-04-27. Available: https://...
        [2] Artificial Intelligence Act, Procedure 2021/0106(COD), Adopted. Available: https://...
        [3] Brando Benifei, Member of the European Parliament (IT). Available: https://...
        ```
        """
        if not self.citations:
            return ""

        lines = ["SOURCES\n"]

        for citation in self.citations:
            formatted = self.format_citation(citation)
            lines.append(formatted)

        return "\n".join(lines)

    def parse_citation_markers(self, text: str) -> List[int]:
        """
        Extract citation markers from text.

        Args:
            text: Text with citation markers like [1], [2], etc.

        Returns:
            List of citation numbers found

        Example:
            >>> tracker.parse_citation_markers("The GDPR [1] regulates data [2].")
            [1, 2]
        """
        # Find all [N] patterns
        pattern = r'\[(\d+)\]'
        matches = re.findall(pattern, text)

        citation_numbers = [int(m) for m in matches]
        return sorted(set(citation_numbers))

    def get_used_citations(self, text: str) -> List[Citation]:
        """
        Get only citations that are actually used in text.

        Args:
            text: Text with citation markers

        Returns:
            List of citations that appear in text
        """
        used_numbers = self.parse_citation_markers(text)
        used_citations = [
            c for c in self.citations
            if c.id in used_numbers
        ]

        return used_citations

    def format_response_with_citations(
        self,
        response_text: str,
        include_unused: bool = False
    ) -> str:
        """
        Format complete response with citations.

        Args:
            response_text: AI response text with [1], [2] markers
            include_unused: Include all citations, even unused ones

        Returns:
            Complete text with response + footnotes

        Example:
            >>> formatted = tracker.format_response_with_citations(
            ...     response_text="The AI Act [1] was adopted in 2024 [2]."
            ... )
            >>> print(formatted)
            The AI Act [1] was adopted in 2024 [2].

            SOURCES
            [1] Artificial Intelligence Act, CELEX:32024R1689...
            [2] "AI Act enters into force", European Parliament, 2024-08-01...
        """
        if include_unused:
            # Use all citations
            footnotes = self.generate_footnotes()
        else:
            # Only include used citations
            used_citations = self.get_used_citations(response_text)

            if not used_citations:
                return response_text

            # Generate footnotes for used citations only
            lines = ["SOURCES\n"]
            for citation in used_citations:
                formatted = self.format_citation(citation)
                lines.append(formatted)

            footnotes = "\n".join(lines)

        # Combine response with footnotes
        return f"{response_text}\n\n{footnotes}"

    def get_citation_by_id(self, citation_id: int) -> Optional[Citation]:
        """
        Get citation by ID.

        Args:
            citation_id: Citation number

        Returns:
            Citation or None if not found
        """
        for citation in self.citations:
            if citation.id == citation_id:
                return citation

        return None

    def get_citation_metadata(self) -> List[Dict[str, Any]]:
        """
        Get all citation metadata.

        Returns:
            List of citation dicts
        """
        return [
            {
                'id': c.id,
                'type': c.type,
                'title': c.title,
                'url': c.url,
                'metadata': c.metadata
            }
            for c in self.citations
        ]

    def clear(self):
        """Clear all citations"""
        self.citations.clear()
        self._citation_map.clear()
        logger.debug("Citations cleared")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get citation statistics.

        Returns:
            Stats dict
        """
        type_counts = {}
        for citation in self.citations:
            type_counts[citation.type] = type_counts.get(citation.type, 0) + 1

        return {
            'total_citations': len(self.citations),
            'by_type': type_counts,
            'format': self.format
        }


def create_citation_from_search_result(
    result: Dict[str, Any],
    citation_id: int
) -> Citation:
    """
    Create citation from search result.

    Args:
        result: Search result dict
        citation_id: Citation number

    Returns:
        Citation object
    """
    metadata = result.get('metadata', {})

    return Citation(
        id=citation_id,
        type=result.get('collection', 'unknown'),
        title=metadata.get('title', result.get('text', '')[:100]),
        url=metadata.get('url', ''),
        metadata=metadata
    )


def create_citation_from_legislation(
    legislation: Dict[str, Any],
    citation_id: int
) -> Citation:
    """
    Create citation from legislation data.

    Args:
        legislation: Legislation dict
        citation_id: Citation number

    Returns:
        Citation object
    """
    return Citation(
        id=citation_id,
        type='legislation',
        title=legislation.get('title', ''),
        url=legislation.get('url', ''),
        metadata={
            'celex': legislation.get('celex', ''),
            'date': legislation.get('date', ''),
            'type': legislation.get('type', '')
        }
    )


def create_citation_from_procedure(
    procedure: Dict[str, Any],
    citation_id: int
) -> Citation:
    """
    Create citation from procedure data.

    Args:
        procedure: Procedure dict
        citation_id: Citation number

    Returns:
        Citation object
    """
    return Citation(
        id=citation_id,
        type='procedure',
        title=procedure.get('title', ''),
        url=procedure.get('url', ''),
        metadata={
            'reference': procedure.get('reference', ''),
            'status': procedure.get('status', ''),
            'date': procedure.get('date', '')
        }
    )


def create_citation_from_mep(
    mep: Dict[str, Any],
    citation_id: int
) -> Citation:
    """
    Create citation from MEP data.

    Args:
        mep: MEP dict
        citation_id: Citation number

    Returns:
        Citation object
    """
    return Citation(
        id=citation_id,
        type='mep',
        title=mep.get('name', ''),
        url=mep.get('url', ''),
        metadata={
            'name': mep.get('name', ''),
            'country': mep.get('country', ''),
            'party': mep.get('party', ''),
            'group': mep.get('group', '')
        }
    )
