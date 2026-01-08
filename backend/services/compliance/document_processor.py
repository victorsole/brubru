"""
Document Processor Service

Extracts text from uploaded PDF/DOCX/TXT documents for compliance analysis.
"""

import logging
from typing import List, Dict, Optional
from pathlib import Path
import tempfile

# Document parsing libraries
try:
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """
    Processes uploaded company documents and extracts text content.
    
    Supports:
    - PDF (via pypdf)
    - DOCX (via python-docx)
    - TXT (plain text)
    """
    
    def __init__(self):
        if not PYPDF_AVAILABLE:
            logger.warning("pypdf not installed. PDF processing will fail.")
        if not DOCX_AVAILABLE:
            logger.warning("python-docx not installed. DOCX processing will fail.")
    
    def process_document(self, file_path: str) -> Dict[str, any]:
        """
        Extract text and metadata from a document.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dict with:
            - text: Full text content
            - chunks: Text split into chunks (for embedding)
            - metadata: Document metadata
        """
        file_path = Path(file_path)
        extension = file_path.suffix.lower()
        
        if extension == '.pdf':
            return self._process_pdf(file_path)
        elif extension in ['.docx', '.doc']:
            return self._process_docx(file_path)
        elif extension == '.txt':
            return self._process_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {extension}")
    
    def _process_pdf(self, file_path: Path) -> Dict:
        """Extract text from PDF using pypdf."""
        if not PYPDF_AVAILABLE:
            raise RuntimeError("pypdf not installed. Install with: pip install pypdf")
        
        try:
            text_parts = []
            
            with open(file_path, 'rb') as file:
                pdf_reader = pypdf.PdfReader(file)
                num_pages = len(pdf_reader.pages)
                
                for page_num in range(num_pages):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)
            
            full_text = '\n\n'.join(text_parts)
            chunks = self._chunk_text(full_text)
            
            return {
                'text': full_text,
                'chunks': chunks,
                'metadata': {
                    'file_type': 'pdf',
                    'pages': num_pages,
                    'char_count': len(full_text)
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing PDF {file_path}: {str(e)}")
            raise
    
    def _process_docx(self, file_path: Path) -> Dict:
        """Extract text from DOCX using python-docx."""
        if not DOCX_AVAILABLE:
            raise RuntimeError("python-docx not installed. Install with: pip install python-docx")
        
        try:
            doc = Document(file_path)
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
            full_text = '\n\n'.join(paragraphs)
            chunks = self._chunk_text(full_text)
            
            return {
                'text': full_text,
                'chunks': chunks,
                'metadata': {
                    'file_type': 'docx',
                    'paragraphs': len(paragraphs),
                    'char_count': len(full_text)
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing DOCX {file_path}: {str(e)}")
            raise
    
    def _process_txt(self, file_path: Path) -> Dict:
        """Extract text from TXT file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                full_text = file.read()
            
            chunks = self._chunk_text(full_text)
            
            return {
                'text': full_text,
                'chunks': chunks,
                'metadata': {
                    'file_type': 'txt',
                    'char_count': len(full_text)
                }
            }
            
        except Exception as e:
            logger.error(f"Error processing TXT {file_path}: {str(e)}")
            raise
    
    def _chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks for semantic search.
        
        Args:
            text: Full text to chunk
            chunk_size: Target chunk size in characters
            overlap: Overlap between chunks
            
        Returns:
            List of text chunks
        """
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('.')
                last_newline = chunk.rfind('\n')
                break_point = max(last_period, last_newline)
                
                if break_point > chunk_size * 0.7:  # At least 70% of chunk_size
                    chunk = chunk[:break_point + 1]
                    end = start + break_point + 1
            
            chunks.append(chunk.strip())
            start = end - overlap
        
        return chunks
