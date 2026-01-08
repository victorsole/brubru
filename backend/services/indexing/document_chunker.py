"""
Document Chunker

Phase 2: Vector Database Population
Intelligently chunks documents for optimal vector search retrieval.

Chunking strategies:
- Section-based: Split by document sections (headings)
- Paragraph-based: Split by paragraphs with overlap
- Semantic: Split by meaning (future enhancement)
- Hybrid: Combine multiple strategies

This module is reusable for EPRS, JRC, and other EU institutional publications.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """
    Single chunk of a document for vector indexing.

    A chunk represents a semantic unit of text (section, paragraph, etc.)
    that will be embedded and stored separately in the vector database.
    """
    chunk_id: str  # Unique identifier for this chunk
    text: str  # The actual text content
    chunk_index: int  # Position in document (0-based)
    chunk_type: str  # 'section', 'paragraph', 'full_document', etc.

    # Metadata for filtering and context
    document_id: str  # Parent document ID
    heading: Optional[str] = None  # Section heading if applicable
    page_number: Optional[int] = None  # Page number if available

    # Character positions in original document
    char_start: int = 0
    char_end: int = 0

    # Chunk stats
    word_count: int = 0
    char_count: int = 0

    # Additional metadata
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

        # Calculate stats if not provided
        if self.word_count == 0:
            self.word_count = len(self.text.split())

        if self.char_count == 0:
            self.char_count = len(self.text)


class DocumentChunker:
    """
    Intelligent document chunker for optimal vector search.

    Strategies:
    1. Section-based: Split by document structure (headings)
    2. Paragraph-based: Split into paragraphs with overlap
    3. Fixed-size: Split by character/word count (fallback)
    4. Hybrid: Intelligently combine strategies

    Usage:
        chunker = DocumentChunker()

        # Section-based (best for structured documents)
        chunks = chunker.chunk_by_sections(
            document_id="eprs_123",
            sections=[
                {"heading": "Introduction", "content": "...", "page": 1},
                {"heading": "Key Findings", "content": "...", "page": 5}
            ]
        )

        # Paragraph-based (best for unstructured text)
        chunks = chunker.chunk_by_paragraphs(
            document_id="eprs_456",
            text="Long document text...",
            max_chunk_size=1000,
            overlap=100
        )
    """

    def __init__(
        self,
        max_chunk_size: int = 1000,  # characters
        min_chunk_size: int = 100,   # characters
        overlap_size: int = 100      # characters
    ):
        """
        Initialize document chunker.

        Args:
            max_chunk_size: Maximum characters per chunk
            min_chunk_size: Minimum characters per chunk
            overlap_size: Overlap between chunks (for context)
        """
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_size = overlap_size

        logger.info(
            f"Initialized DocumentChunker "
            f"(max={max_chunk_size}, min={min_chunk_size}, overlap={overlap_size})"
        )

    def chunk_by_sections(
        self,
        document_id: str,
        sections: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Chunk document by sections (best for structured documents).

        Each section becomes a chunk. If a section is too large, it's split.

        Args:
            document_id: Unique document identifier
            sections: List of sections with:
                - heading: Section heading
                - content: Section text
                - page_number: Page number (optional)
            metadata: Additional metadata to attach to all chunks

        Returns:
            List of DocumentChunk objects

        Example:
            sections = [
                {"heading": "Introduction", "content": "...", "page_number": 1},
                {"heading": "Main Findings", "content": "...", "page_number": 3}
            ]
            chunks = chunker.chunk_by_sections("doc_123", sections)
        """
        chunks = []
        char_position = 0

        for section_idx, section in enumerate(sections):
            heading = section.get('heading', f'Section {section_idx + 1}')
            content = section.get('content', '')
            page_number = section.get('page_number')

            if not content or len(content) < self.min_chunk_size:
                logger.debug(f"Skipping small section: {heading}")
                continue

            # If section is small enough, create one chunk
            if len(content) <= self.max_chunk_size:
                chunk = DocumentChunk(
                    chunk_id=f"{document_id}_section_{section_idx}",
                    text=content,
                    chunk_index=len(chunks),
                    chunk_type="section",
                    document_id=document_id,
                    heading=heading,
                    page_number=page_number,
                    char_start=char_position,
                    char_end=char_position + len(content),
                    metadata=metadata or {}
                )
                chunks.append(chunk)
                char_position += len(content)

            else:
                # Section too large, split into sub-chunks
                logger.debug(f"Splitting large section: {heading} ({len(content)} chars)")

                sub_chunks = self._split_text(
                    text=content,
                    base_chunk_id=f"{document_id}_section_{section_idx}",
                    document_id=document_id,
                    heading=heading,
                    page_number=page_number,
                    start_index=len(chunks),
                    char_offset=char_position,
                    metadata=metadata
                )

                chunks.extend(sub_chunks)
                char_position += len(content)

        logger.info(f"Created {len(chunks)} section-based chunks for {document_id}")
        return chunks

    def chunk_by_paragraphs(
        self,
        document_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        max_chunk_size: Optional[int] = None,
        overlap: Optional[int] = None
    ) -> List[DocumentChunk]:
        """
        Chunk document by paragraphs (best for unstructured text).

        Paragraphs are grouped to approach max_chunk_size with overlap.

        Args:
            document_id: Unique document identifier
            text: Full document text
            metadata: Additional metadata
            max_chunk_size: Override default max chunk size
            overlap: Override default overlap size

        Returns:
            List of DocumentChunk objects
        """
        max_size = max_chunk_size or self.max_chunk_size
        overlap_size = overlap or self.overlap_size

        # Split by paragraphs (double newline)
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]

        chunks = []
        current_chunk_text = []
        current_char_count = 0
        char_position = 0

        for para_idx, para in enumerate(paragraphs):
            para_length = len(para)

            # If adding this paragraph would exceed max_size, create chunk
            if current_chunk_text and (current_char_count + para_length > max_size):
                # Create chunk from accumulated paragraphs
                chunk_text = '\n\n'.join(current_chunk_text)

                chunk = DocumentChunk(
                    chunk_id=f"{document_id}_para_{len(chunks)}",
                    text=chunk_text,
                    chunk_index=len(chunks),
                    chunk_type="paragraph",
                    document_id=document_id,
                    char_start=char_position - current_char_count,
                    char_end=char_position,
                    metadata=metadata or {}
                )
                chunks.append(chunk)

                # Keep last paragraph for overlap
                if overlap_size > 0 and current_chunk_text:
                    overlap_text = current_chunk_text[-1]
                    current_chunk_text = [overlap_text]
                    current_char_count = len(overlap_text)
                else:
                    current_chunk_text = []
                    current_char_count = 0

            # Add paragraph to current chunk
            current_chunk_text.append(para)
            current_char_count += para_length
            char_position += para_length

        # Add final chunk
        if current_chunk_text:
            chunk_text = '\n\n'.join(current_chunk_text)

            chunk = DocumentChunk(
                chunk_id=f"{document_id}_para_{len(chunks)}",
                text=chunk_text,
                chunk_index=len(chunks),
                chunk_type="paragraph",
                document_id=document_id,
                char_start=char_position - current_char_count,
                char_end=char_position,
                metadata=metadata or {}
            )
            chunks.append(chunk)

        logger.info(f"Created {len(chunks)} paragraph-based chunks for {document_id}")
        return chunks

    def chunk_full_document(
        self,
        document_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Store entire document as single chunk (for small documents).

        Args:
            document_id: Unique document identifier
            text: Full document text
            metadata: Additional metadata

        Returns:
            List containing single DocumentChunk
        """
        if len(text) > self.max_chunk_size:
            logger.warning(
                f"Document {document_id} ({len(text)} chars) exceeds max_chunk_size. "
                f"Consider using chunk_by_sections or chunk_by_paragraphs instead."
            )

        chunk = DocumentChunk(
            chunk_id=f"{document_id}_full",
            text=text,
            chunk_index=0,
            chunk_type="full_document",
            document_id=document_id,
            char_start=0,
            char_end=len(text),
            metadata=metadata or {}
        )

        logger.info(f"Created full document chunk for {document_id}")
        return [chunk]

    def _split_text(
        self,
        text: str,
        base_chunk_id: str,
        document_id: str,
        heading: Optional[str] = None,
        page_number: Optional[int] = None,
        start_index: int = 0,
        char_offset: int = 0,
        metadata: Optional[Dict[str, Any]] = None
    ) -> List[DocumentChunk]:
        """
        Split text into fixed-size chunks with overlap.

        Helper method for splitting large sections.
        """
        chunks = []
        text_length = len(text)
        position = 0
        chunk_count = 0

        while position < text_length:
            # Calculate chunk end position
            end_position = min(position + self.max_chunk_size, text_length)

            # Try to break at sentence boundary (period + space)
            if end_position < text_length:
                # Look for sentence end within last 20% of chunk
                search_start = int(position + self.max_chunk_size * 0.8)
                search_text = text[search_start:end_position]

                sentence_end = search_text.rfind('. ')
                if sentence_end != -1:
                    end_position = search_start + sentence_end + 2  # Include period and space

            # Extract chunk text
            chunk_text = text[position:end_position].strip()

            if len(chunk_text) >= self.min_chunk_size:
                chunk = DocumentChunk(
                    chunk_id=f"{base_chunk_id}_sub_{chunk_count}",
                    text=chunk_text,
                    chunk_index=start_index + chunk_count,
                    chunk_type="section_split",
                    document_id=document_id,
                    heading=heading,
                    page_number=page_number,
                    char_start=char_offset + position,
                    char_end=char_offset + end_position,
                    metadata=metadata or {}
                )
                chunks.append(chunk)
                chunk_count += 1

            # Move position forward with overlap
            position = end_position - self.overlap_size

            # Prevent infinite loop
            if position <= 0:
                position = end_position

        return chunks
