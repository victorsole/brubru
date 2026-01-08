"""
PDF Processing Service using pdfminer.six

Lightweight PDF text extraction for handling large documents.
Uses pdfminer.six (pure Python, no dependency conflicts).
"""

import logging
from typing import Optional, Dict, Any
import pypdfium2 as pdfium
from pdfminer.high_level import extract_text

logger = logging.getLogger(__name__)


class PDFProcessor:
    """
    Process PDF documents with pdfminer.six for text extraction.

    Features:
    - Page count detection (pypdfium2)
    - Text extraction (pdfminer.six)
    - Handles large documents (>100 pages)
    - No dependency conflicts
    """

    # Claude's PDF page limit
    CLAUDE_PDF_PAGE_LIMIT = 100

    def __init__(self):
        """Initialize PDF processor."""
        logger.info("PDFProcessor initialized with pdfminer.six")

    def get_page_count(self, pdf_path: str) -> int:
        """
        Get the number of pages in a PDF.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Number of pages, or 0 if error
        """
        try:
            pdf = pdfium.PdfDocument(pdf_path)
            page_count = len(pdf)
            pdf.close()
            logger.info(f"PDF has {page_count} pages: {pdf_path}")
            return page_count
        except Exception as e:
            logger.error(f"Failed to get page count for {pdf_path}: {str(e)}")
            return 0

    def exceeds_claude_limit(self, pdf_path: str) -> bool:
        """
        Check if PDF exceeds Claude's 100-page limit.

        Args:
            pdf_path: Path to PDF file

        Returns:
            True if PDF has more than 100 pages
        """
        page_count = self.get_page_count(pdf_path)
        return page_count > self.CLAUDE_PDF_PAGE_LIMIT

    def extract_text(self, pdf_path: str) -> Dict[str, Any]:
        """
        Extract text from PDF using pdfminer.six.

        Args:
            pdf_path: Path to PDF file

        Returns:
            Dict with:
                - text: Extracted text
                - page_count: Number of pages
                - success: Whether extraction succeeded
        """
        try:
            page_count = self.get_page_count(pdf_path)
            logger.info(f"Extracting text from {page_count}-page PDF: {pdf_path}")

            # Extract text using pdfminer.six
            text = extract_text(pdf_path)

            logger.info(f"Successfully extracted {len(text)} chars from PDF")

            return {
                'text': text,
                'page_count': page_count,
                'success': True
            }

        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {str(e)}")
            return {
                'text': '',
                'page_count': 0,
                'success': False,
                'error': str(e)
            }

    def should_extract_text(self, pdf_path: str) -> bool:
        """
        Determine if we should extract text instead of sending PDF directly.

        Returns True if PDF has more than 100 pages (exceeds Claude limit).

        Args:
            pdf_path: Path to PDF file

        Returns:
            True if should extract text, False if can send PDF directly
        """
        return self.exceeds_claude_limit(pdf_path)


# Global singleton
_pdf_processor: Optional[PDFProcessor] = None


def get_pdf_processor() -> PDFProcessor:
    """Get global PDF processor instance."""
    global _pdf_processor

    if _pdf_processor is None:
        _pdf_processor = PDFProcessor()

    return _pdf_processor
