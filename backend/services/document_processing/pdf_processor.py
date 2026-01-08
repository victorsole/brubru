"""
PDF Processor - Reusable Module for PDF Content Extraction

Phase 1: Full Content Extraction Pipeline
This module provides reusable PDF processing capabilities for:
- EPRS Think Tank publications
- JRC research reports
- Commission studies
- Any EU institutional PDF documents

Features:
- Download PDFs from URLs
- Extract full text content
- Extract metadata (title, author, date)
- Parse document structure (sections, headings)
- Extract tables and data
- Handle multi-language documents
"""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, BinaryIO
from dataclasses import dataclass
import hashlib

import aiohttp
import pypdf
import pdfplumber
import pikepdf

logger = logging.getLogger(__name__)


@dataclass
class PDFMetadata:
    """Extracted PDF metadata"""
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[datetime] = None
    modification_date: Optional[datetime] = None
    page_count: int = 0
    file_size_bytes: int = 0
    language: Optional[str] = None
    keywords: List[str] = None


@dataclass
class PDFSection:
    """Document section with content"""
    heading: str
    content: str
    page_number: int
    level: int  # 1=main heading, 2=subheading, etc.


@dataclass
class PDFContent:
    """Complete extracted PDF content"""
    full_text: str
    metadata: PDFMetadata
    sections: List[PDFSection]
    tables: List[Dict[str, Any]]
    references: List[str]  # Citations, URLs, CELEX numbers found
    word_count: int
    char_count: int
    extraction_quality: str  # 'high', 'medium', 'low'


class PDFProcessor:
    """
    Reusable PDF processor for EU institutional documents.

    Usage:
        processor = PDFProcessor()

        # From URL
        content = await processor.process_pdf_from_url("https://...")

        # From file
        content = await processor.process_pdf_from_file(Path("document.pdf"))

        # Extract specific data
        metadata = await processor.extract_metadata(pdf_path)
        text = await processor.extract_text(pdf_path)
    """

    def __init__(
        self,
        download_dir: Optional[Path] = None,
        timeout: int = 60,
        max_file_size_mb: int = 50
    ):
        """
        Initialize PDF processor.

        Args:
            download_dir: Directory for downloaded PDFs (temp if None)
            timeout: Download timeout in seconds
            max_file_size_mb: Maximum PDF file size in MB
        """
        self.download_dir = download_dir or Path("/tmp/brubru_pdfs")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = timeout
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024

        logger.info(f"Initialized PDFProcessor (download_dir={self.download_dir})")

    async def process_pdf_from_url(
        self,
        url: str,
        extract_tables: bool = False,
        extract_sections: bool = True
    ) -> PDFContent:
        """
        Download and process PDF from URL.

        Args:
            url: PDF URL
            extract_tables: Extract tables from PDF
            extract_sections: Parse document structure

        Returns:
            PDFContent with all extracted data
        """
        logger.info(f"Processing PDF from URL: {url}")

        # Download PDF
        pdf_path = await self.download_pdf(url)

        if not pdf_path:
            raise ValueError(f"Failed to download PDF from {url}")

        # Process downloaded file
        return await self.process_pdf_from_file(
            pdf_path,
            extract_tables=extract_tables,
            extract_sections=extract_sections
        )

    async def process_pdf_from_file(
        self,
        pdf_path: Path,
        extract_tables: bool = False,
        extract_sections: bool = True
    ) -> PDFContent:
        """
        Process PDF file and extract all content.

        Args:
            pdf_path: Path to PDF file
            extract_tables: Extract tables from PDF
            extract_sections: Parse document structure

        Returns:
            PDFContent with all extracted data
        """
        logger.info(f"Processing PDF file: {pdf_path}")

        # Extract metadata
        metadata = await self.extract_metadata(pdf_path)

        # Extract text
        full_text = await self.extract_text(pdf_path)

        # Parse sections
        sections = []
        if extract_sections:
            sections = await self.extract_sections(pdf_path, full_text)

        # Extract tables
        tables = []
        if extract_tables:
            tables = await self.extract_tables(pdf_path)

        # Extract references (CELEX numbers, URLs, citations)
        references = self.extract_references(full_text)

        # Calculate stats
        word_count = len(full_text.split())
        char_count = len(full_text)

        # Assess extraction quality
        quality = self.assess_extraction_quality(full_text, metadata.page_count)

        content = PDFContent(
            full_text=full_text,
            metadata=metadata,
            sections=sections,
            tables=tables,
            references=references,
            word_count=word_count,
            char_count=char_count,
            extraction_quality=quality
        )

        logger.info(
            f"Extracted PDF: {word_count} words, {metadata.page_count} pages, "
            f"{len(sections)} sections, quality={quality}"
        )

        return content

    async def download_pdf(self, url: str) -> Optional[Path]:
        """
        Download PDF from URL to local storage.

        Args:
            url: PDF URL

        Returns:
            Path to downloaded file or None if failed
        """
        try:
            # Generate filename from URL hash
            url_hash = hashlib.md5(url.encode()).hexdigest()
            filename = f"{url_hash}.pdf"
            filepath = self.download_dir / filename

            # Skip if already downloaded
            if filepath.exists():
                logger.debug(f"PDF already downloaded: {filepath}")
                return filepath

            # Download with aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=self.timeout)
                ) as response:
                    response.raise_for_status()

                    # Check file size
                    content_length = response.headers.get('Content-Length')
                    if content_length and int(content_length) > self.max_file_size_bytes:
                        raise ValueError(
                            f"PDF too large: {int(content_length) / 1024 / 1024:.1f}MB "
                            f"(max {self.max_file_size_bytes / 1024 / 1024}MB)"
                        )

                    # Save to file
                    content = await response.read()
                    filepath.write_bytes(content)

                    logger.info(f"Downloaded PDF: {url} -> {filepath}")
                    return filepath

        except Exception as e:
            logger.error(f"Failed to download PDF from {url}: {str(e)}")
            return None

    async def extract_metadata(self, pdf_path: Path) -> PDFMetadata:
        """
        Extract metadata from PDF file.

        Args:
            pdf_path: Path to PDF file

        Returns:
            PDFMetadata object
        """
        try:
            # Use pikepdf for robust metadata extraction
            with pikepdf.open(pdf_path) as pdf:
                meta = pdf.docinfo

                # Extract standard metadata fields
                title = str(meta.get('/Title', '')) if '/Title' in meta else None
                author = str(meta.get('/Author', '')) if '/Author' in meta else None
                subject = str(meta.get('/Subject', '')) if '/Subject' in meta else None
                creator = str(meta.get('/Creator', '')) if '/Creator' in meta else None
                producer = str(meta.get('/Producer', '')) if '/Producer' in meta else None
                keywords_str = str(meta.get('/Keywords', '')) if '/Keywords' in meta else None

                # Parse dates
                creation_date = self._parse_pdf_date(
                    str(meta.get('/CreationDate', '')) if '/CreationDate' in meta else None
                )
                mod_date = self._parse_pdf_date(
                    str(meta.get('/ModDate', '')) if '/ModDate' in meta else None
                )

                # Parse keywords
                keywords = []
                if keywords_str:
                    keywords = [k.strip() for k in keywords_str.split(',')]

                # Get page count
                page_count = len(pdf.pages)

                # Get file size
                file_size = pdf_path.stat().st_size

                return PDFMetadata(
                    title=title,
                    author=author,
                    subject=subject,
                    creator=creator,
                    producer=producer,
                    creation_date=creation_date,
                    modification_date=mod_date,
                    page_count=page_count,
                    file_size_bytes=file_size,
                    keywords=keywords
                )

        except Exception as e:
            logger.error(f"Failed to extract metadata from {pdf_path}: {str(e)}")
            return PDFMetadata(page_count=0, file_size_bytes=pdf_path.stat().st_size)

    async def extract_text(self, pdf_path: Path) -> str:
        """
        Extract full text from PDF.

        Uses pypdf for speed and pdfplumber as fallback for better quality.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Extracted text content
        """
        try:
            # Try pypdf first (fast)
            reader = pypdf.PdfReader(str(pdf_path))
            text_parts = []

            for page in reader.pages:
                text = page.extract_text()
                if text:
                    text_parts.append(text)

            full_text = '\n\n'.join(text_parts)

            # If extraction is poor quality, try pdfplumber (slower but better)
            if len(full_text.strip()) < 100 or self._has_extraction_issues(full_text):
                logger.debug(f"pypdf extraction poor quality, trying pdfplumber: {pdf_path}")
                full_text = await self._extract_text_with_pdfplumber(pdf_path)

            return full_text.strip()

        except Exception as e:
            logger.error(f"Failed to extract text from {pdf_path}: {str(e)}")
            return ""

    async def _extract_text_with_pdfplumber(self, pdf_path: Path) -> str:
        """Extract text using pdfplumber (higher quality, slower)"""
        try:
            text_parts = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)

            return '\n\n'.join(text_parts)
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {str(e)}")
            return ""

    async def extract_sections(
        self,
        pdf_path: Path,
        full_text: Optional[str] = None
    ) -> List[PDFSection]:
        """
        Parse document structure and extract sections.

        Identifies headings and sections based on formatting patterns.

        Args:
            pdf_path: Path to PDF file
            full_text: Pre-extracted text (optional)

        Returns:
            List of PDFSection objects
        """
        if full_text is None:
            full_text = await self.extract_text(pdf_path)

        sections = []

        # Split by double newlines (page/section breaks)
        paragraphs = full_text.split('\n\n')

        current_heading = None
        current_content = []
        current_page = 1

        # Patterns for headings (all caps, numbered sections, etc.)
        heading_patterns = [
            r'^[A-Z\s]{3,}$',  # All caps headings
            r'^\d+\.\s+[A-Z]',  # Numbered sections (1. Introduction)
            r'^[IVX]+\.\s+',  # Roman numerals
        ]

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if paragraph is a heading
            is_heading = False
            for pattern in heading_patterns:
                if re.match(pattern, para) and len(para) < 100:
                    is_heading = True
                    break

            if is_heading:
                # Save previous section
                if current_heading and current_content:
                    sections.append(PDFSection(
                        heading=current_heading,
                        content='\n\n'.join(current_content),
                        page_number=current_page,
                        level=1
                    ))

                # Start new section
                current_heading = para
                current_content = []
            else:
                # Add to current section
                if current_heading:
                    current_content.append(para)

        # Add final section
        if current_heading and current_content:
            sections.append(PDFSection(
                heading=current_heading,
                content='\n\n'.join(current_content),
                page_number=current_page,
                level=1
            ))

        logger.debug(f"Extracted {len(sections)} sections from {pdf_path}")
        return sections

    async def extract_tables(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """
        Extract tables from PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            List of tables (each as dict with rows/columns)
        """
        tables = []

        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_num, page in enumerate(pdf.pages, 1):
                    page_tables = page.extract_tables()

                    for table in page_tables:
                        if table:
                            tables.append({
                                'page': page_num,
                                'rows': len(table),
                                'columns': len(table[0]) if table else 0,
                                'data': table
                            })

            logger.debug(f"Extracted {len(tables)} tables from {pdf_path}")

        except Exception as e:
            logger.error(f"Failed to extract tables from {pdf_path}: {str(e)}")

        return tables

    def extract_references(self, text: str) -> List[str]:
        """
        Extract references, citations, URLs, CELEX numbers from text.

        Args:
            text: Document text

        Returns:
            List of unique references found
        """
        references = set()

        # Extract CELEX numbers
        celex_pattern = r'\b\d{1,2}[A-Z]{1,2}\d{4}[A-Z]{1,2}\d{4}\b'
        celex_matches = re.findall(celex_pattern, text)
        references.update(celex_matches)

        # Extract procedure references
        proc_pattern = r'\b\d{4}/\d{4}\([A-Z]{3,4}\)\b'
        proc_matches = re.findall(proc_pattern, text)
        references.update(proc_matches)

        # Extract URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        url_matches = re.findall(url_pattern, text)
        references.update(url_matches)

        return sorted(list(references))

    def assess_extraction_quality(self, text: str, page_count: int) -> str:
        """
        Assess quality of text extraction.

        Args:
            text: Extracted text
            page_count: Number of pages in PDF

        Returns:
            Quality rating: 'high', 'medium', 'low'
        """
        if not text or page_count == 0:
            return 'low'

        # Calculate chars per page
        chars_per_page = len(text) / page_count if page_count > 0 else 0

        # Check for extraction issues
        if self._has_extraction_issues(text):
            return 'low'

        # High quality: good chars per page, readable text
        if chars_per_page > 1500 and chars_per_page < 8000:
            return 'high'

        # Medium quality: some text but possibly incomplete
        if chars_per_page > 500:
            return 'medium'

        return 'low'

    def _has_extraction_issues(self, text: str) -> bool:
        """Check if extracted text has common issues"""
        if not text:
            return True

        # Too many repeated characters (scanned PDFs)
        if re.search(r'(.)\1{10,}', text):
            return True

        # Too many single-character "words" (broken extraction)
        words = text.split()
        single_char_words = sum(1 for w in words if len(w) == 1)
        if len(words) > 0 and single_char_words / len(words) > 0.3:
            return True

        return False

    def _parse_pdf_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse PDF metadata date format"""
        if not date_str:
            return None

        try:
            # PDF date format: D:YYYYMMDDHHmmSSOHH'mm'
            # Example: D:20240315120000+01'00'
            match = re.match(r"D:(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})", date_str)
            if match:
                year, month, day, hour, minute, second = map(int, match.groups())
                return datetime(year, month, day, hour, minute, second)
        except Exception:
            pass

        return None

    def cleanup_old_downloads(self, days: int = 7):
        """
        Delete downloaded PDFs older than specified days.

        Args:
            days: Delete files older than this many days
        """
        if not self.download_dir.exists():
            return

        cutoff_time = datetime.now().timestamp() - (days * 86400)
        deleted_count = 0

        for pdf_file in self.download_dir.glob("*.pdf"):
            if pdf_file.stat().st_mtime < cutoff_time:
                pdf_file.unlink()
                deleted_count += 1

        if deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old PDF files")
