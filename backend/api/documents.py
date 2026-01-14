"""
Documents API

Handle document upload, EUR-Lex fetching, and document retrieval.
"""

import logging
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.storage.document_storage import get_document_storage
from services.document_processing.pdf_processor import PDFProcessor
from services.document_processing.docx_processor import get_docx_processor
from services.document_processing.url_parser import get_url_parser
from services.api_clients.eurlex_client import EURLexClient
from services.scrapers.eurlex_scraper import get_eurlex_scraper
from services.parsers.eurlex_parser import EurlexParser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents")


# Request/Response Models

class FetchEURLexRequest(BaseModel):
    """Request to fetch document from EUR-Lex"""
    url: Optional[str] = Field(None, description="EUR-Lex URL")
    celex: Optional[str] = Field(None, description="CELEX number")
    format: str = Field('html', description="Document format: html, pdf, xml")
    language: str = Field('EN', description="Language code")


class ParseEURLexURLResponse(BaseModel):
    """Response with parsed EUR-Lex URL"""
    celex: Optional[str]
    language: str
    format: str
    valid: bool
    url_type: Optional[str]
    original_url: str
    error: Optional[str] = None


class DocumentMetadata(BaseModel):
    """Document metadata response"""
    document_id: str
    filename: str
    content_type: str
    file_size: int
    status: str
    created_at: str
    has_processed_content: bool


class DocumentContentResponse(BaseModel):
    """Document content response"""
    document_id: str
    filename: str
    text: str
    metadata: dict
    structure: Optional[dict] = None
    tables: Optional[List[dict]] = None
    quality: str


# API Endpoints

@router.post("/upload", response_model=DocumentMetadata)
async def upload_document(
    file: UploadFile = File(...),
) -> JSONResponse:
    """
    Upload and process a document (PDF, DOCX, DOC).

    Returns document metadata with processing status.
    """
    try:
        logger.info(f"Uploading document: {file.filename}")

        # Validate file type
        allowed_types = {
            'application/pdf': '.pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
            'application/msword': '.doc',
        }

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}. "
                       f"Supported types: PDF, DOCX, DOC"
            )

        # Read file content
        file_content = await file.read()

        if len(file_content) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(
                status_code=400,
                detail="File size exceeds 10MB limit"
            )

        # Store document
        storage = get_document_storage()
        document_id = storage.store_document(
            file_content=file_content,
            filename=file.filename,
            content_type=file.content_type,
            user_id=None  # TODO: Get from auth
        )

        # Process document based on type
        processed_content = None

        if file.content_type == 'application/pdf':
            # Process PDF
            pdf_processor = PDFProcessor()
            processed_content = await pdf_processor.process_pdf_from_bytes(file_content)

        elif file.content_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/msword']:
            # Process DOCX
            docx_processor = get_docx_processor()
            processed_content = docx_processor.process_docx_from_bytes(
                file_content,
                filename=file.filename
            )

        # Store processed content
        if processed_content:
            storage.store_processed_content(document_id, processed_content)

        # Get final document metadata
        document = storage.get_document(document_id)

        if not document:
            raise HTTPException(status_code=500, detail="Failed to retrieve document")

        logger.info(f"Successfully uploaded and processed document: {document_id}")

        return JSONResponse(
            status_code=200,
            content={
                'document_id': document['document_id'],
                'filename': document['filename'],
                'content_type': document['content_type'],
                'file_size': document['file_size'],
                'status': document['status'],
                'created_at': document['created_at'],
                'has_processed_content': document['has_processed_content']
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fetch-eurlex", response_model=DocumentContentResponse)
async def fetch_eurlex_document(request: FetchEURLexRequest) -> JSONResponse:
    """
    Fetch document from EUR-Lex by URL or CELEX number.

    Returns processed document content.
    """
    try:
        logger.info(f"Fetching EUR-Lex document: URL={request.url}, CELEX={request.celex}")

        # Extract CELEX from URL if provided
        celex = request.celex

        if request.url and not celex:
            url_parser = get_url_parser()
            parsed = url_parser.parse_eurlex_url(request.url)

            if not parsed.get('valid'):
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid EUR-Lex URL: {parsed.get('error')}"
                )

            celex = parsed['celex']
            request.language = parsed.get('language', request.language)
            request.format = parsed.get('format', request.format)

        if not celex:
            raise HTTPException(
                status_code=400,
                detail="Either 'url' or 'celex' must be provided"
            )

        # Fetch document from EUR-Lex
        scraper = get_eurlex_scraper()
        document_obj = await scraper.get_document_by_celex(celex)

        if not document_obj:
            raise HTTPException(
                status_code=404,
                detail=f"Document not found: {celex}"
            )

        # Convert LegislativeDocument to dict
        document_data = document_obj.model_dump() if hasattr(document_obj, 'model_dump') else document_obj.dict()

        # Generate document ID for EUR-Lex fetched documents
        document_id = f"eurlex-{celex}"

        # Extract text from document
        text = document_data.get('text_content', '')
        if not text:
            text = document_data.get('summary', '')

        # Fetch HTML and parse legislative structure
        legislative_structure = None
        try:
            eurlex_client = EURLexClient()
            html_content = await eurlex_client.get_document_html(celex, request.language)

            if html_content:
                parser = EurlexParser()
                parsed = parser.parse_html(html_content)

                # Convert parsed document to frontend format
                elements = []

                # Add recitals
                for recital in parsed.recitals:
                    elements.append({
                        'type': 'recital',
                        'number': recital.number,
                        'text': recital.text,
                        'level': 0
                    })

                # Add articles
                for article in parsed.articles:
                    # Add article title/header
                    elements.append({
                        'type': 'article',
                        'number': article.number,
                        'text': article.title or f"Article {article.number}",
                        'title': article.title,
                        'level': 0
                    })

                if elements:
                    legislative_structure = {
                        'elements': elements,
                        'title': parsed.title or document_data.get('title', ''),
                        'celex': parsed.celex or celex
                    }
                    logger.info(f"Parsed {len(parsed.recitals)} recitals and {len(parsed.articles)} articles from {celex}")

            await eurlex_client.close()
        except Exception as e:
            logger.warning(f"Failed to parse legislative structure: {str(e)}")

        # Build response
        response_data = {
            'document_id': document_id,
            'filename': f"{celex}.html",
            'text': text,
            'metadata': {
                'celex': celex,
                'title': document_data.get('title', ''),
                'date': str(document_data.get('date_published', '')) if document_data.get('date_published') else '',
                'type': document_data.get('document_type', ''),
                'language': request.language,
                'source': 'EUR-Lex',
                'subjects': document_data.get('subjects', [])
            },
            'structure': {'legislative_structure': legislative_structure} if legislative_structure else None,
            'tables': None,
            'quality': 'high' if len(text) > 1000 else 'medium'
        }

        logger.info(f"Successfully fetched EUR-Lex document: {celex}")

        return JSONResponse(status_code=200, content=response_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching EUR-Lex document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/parse-eurlex-url", response_model=ParseEURLexURLResponse)
async def parse_eurlex_url(url: str = Query(..., description="EUR-Lex URL to parse")) -> JSONResponse:
    """
    Parse EUR-Lex URL to extract CELEX number and metadata.

    Useful for validating URLs before fetching.
    """
    try:
        logger.info(f"Parsing EUR-Lex URL: {url}")

        url_parser = get_url_parser()
        parsed = url_parser.parse_eurlex_url(url)

        return JSONResponse(status_code=200, content=parsed)

    except Exception as e:
        logger.error(f"Error parsing EUR-Lex URL: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}", response_model=DocumentMetadata)
async def get_document_metadata(document_id: str) -> JSONResponse:
    """
    Get document metadata by ID.
    """
    try:
        storage = get_document_storage()
        document = storage.get_document(document_id)

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        return JSONResponse(
            status_code=200,
            content={
                'document_id': document['document_id'],
                'filename': document['filename'],
                'content_type': document['content_type'],
                'file_size': document['file_size'],
                'status': document['status'],
                'created_at': document['created_at'],
                'has_processed_content': document['has_processed_content']
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(document_id: str) -> JSONResponse:
    """
    Get document full content (text, structure, metadata).
    """
    try:
        storage = get_document_storage()
        document = storage.get_document(document_id)

        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        if not document.get('has_processed_content'):
            raise HTTPException(
                status_code=400,
                detail="Document has not been processed yet"
            )

        processed = document['processed_content']

        return JSONResponse(
            status_code=200,
            content={
                'document_id': document['document_id'],
                'filename': document['filename'],
                'text': processed.get('text', ''),
                'metadata': processed.get('metadata', {}),
                'structure': processed.get('structure'),
                'tables': processed.get('tables'),
                'quality': processed.get('quality', 'unknown')
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(document_id: str) -> JSONResponse:
    """
    Delete document by ID.
    """
    try:
        storage = get_document_storage()
        deleted = storage.delete_document(document_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Document not found")

        return JSONResponse(
            status_code=200,
            content={'message': 'Document deleted successfully'}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_documents(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of documents")
) -> JSONResponse:
    """
    List uploaded documents.
    """
    try:
        storage = get_document_storage()
        documents = storage.list_documents(limit=limit)

        return JSONResponse(
            status_code=200,
            content={'documents': documents, 'total': len(documents)}
        )

    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
