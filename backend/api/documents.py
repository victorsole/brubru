"""
Documents API

Handle document upload, EUR-Lex fetching, and document retrieval.
"""

import logging
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import httpx
import re

from api.auth_optional import get_current_user_dev as get_current_user
from models.user import User
from services.storage.document_storage import get_document_storage
from services.ai.multi_provider_service import get_multi_provider_service
from services.document_processing.pdf_processor import PDFProcessor
from services.document_processing.docx_processor import get_docx_processor
from services.document_processing.url_parser import get_url_parser
from services.api_clients.eurlex_client import EURLexClient
from services.scrapers.eurlex_scraper import get_eurlex_scraper
from services.parsers.eurlex_parser import EurlexParser, parse_com_document_text, parse_article_structure
from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage

logger = logging.getLogger(__name__)


def expand_articles_to_elements(articles, recitals=None) -> List[dict]:
    """
    Expand parsed articles into flat elements for the Amendator UI.

    Each paragraph and subparagraph becomes a separate amendable cell.
    """
    elements = []

    # Add recitals first
    if recitals:
        for recital in recitals:
            elements.append({
                'type': 'recital',
                'number': recital.number if hasattr(recital, 'number') else str(recital.get('number', '')),
                'text': recital.text if hasattr(recital, 'text') else recital.get('text', ''),
                'level': 0
            })

    # Add articles - expand into separate amendable elements
    for article in articles:
        article_number = article.number if hasattr(article, 'number') else article.get('number', '')
        article_title = article.title if hasattr(article, 'title') else article.get('title', '')
        article_intro = article.intro_text if hasattr(article, 'intro_text') else article.get('intro_text', '')
        article_paragraphs = article.paragraphs if hasattr(article, 'paragraphs') else article.get('paragraphs', [])
        article_text = article.text if hasattr(article, 'text') else article.get('text', '')

        # 1. Article title element (if article has a title)
        if article_title:
            elements.append({
                'type': 'article_title',
                'number': article_number,
                'text': article_title,
                'article_number': article_number,
                'level': 0
            })

        # 2. Article intro text (text before first paragraph)
        if article_intro:
            elements.append({
                'type': 'article_intro',
                'number': article_number,
                'text': article_intro,
                'article_number': article_number,
                'level': 0
            })

        # 3. Each paragraph as separate element
        for para in article_paragraphs:
            para_number = para.number if hasattr(para, 'number') else para.get('number', '')
            para_text = para.text if hasattr(para, 'text') else para.get('text', '')
            para_subparagraphs = para.subparagraphs if hasattr(para, 'subparagraphs') else para.get('subparagraphs', [])

            elements.append({
                'type': 'paragraph',
                'number': para_number,
                'text': para_text,
                'article_number': article_number,
                'level': 1
            })

            # 4. Each subparagraph as separate element
            for subpara in para_subparagraphs:
                subpara_number = subpara.number if hasattr(subpara, 'number') else subpara.get('number', '')
                subpara_text = subpara.text if hasattr(subpara, 'text') else subpara.get('text', '')

                elements.append({
                    'type': 'subparagraph',
                    'number': subpara_number,
                    'text': subpara_text,
                    'article_number': article_number,
                    'paragraph_number': para_number,
                    'level': 2
                })

        # If no paragraphs were extracted, add the full article text
        if not article_paragraphs and not article_intro:
            text = article_text if article_text else f"Article {article_number}"
            elements.append({
                'type': 'article',
                'number': article_number,
                'text': text,
                'title': article_title,
                'level': 0
            })

    return elements


def parse_text_as_legislative(text: str, celex: str = "") -> Optional[dict]:
    """
    Try to parse plain text as legislative document structure.

    Returns legislative_structure dict if successful, None if text doesn't look legislative.
    """
    if not text or len(text) < 500:
        return None

    # Check if this looks like legislative text (has Article patterns)
    article_pattern = re.compile(r'(?:^|\n)\s*Article\s+(\d+[a-z]?)\b', re.IGNORECASE)
    article_matches = list(article_pattern.finditer(text))

    if len(article_matches) < 2:
        # Doesn't look like legislative text
        return None

    # Try to parse using COM document parser (handles both proposals and general legislative text)
    try:
        parsed = parse_com_document_text(text, celex)

        if parsed.articles:
            elements = expand_articles_to_elements(parsed.articles, parsed.recitals)

            if elements:
                return {
                    'elements': elements,
                    'title': parsed.title or '',
                    'celex': celex,
                    'source': 'uploaded-document'
                }
    except Exception as e:
        logger.warning(f"Failed to parse text as legislative: {str(e)}")

    return None


def is_waf_blocked(html_content: Optional[str]) -> bool:
    """Check if the response is a WAF challenge page."""
    if not html_content:
        return True
    if len(html_content) < 3000 and 'awsWafCookieDomainList' in html_content:
        return True
    if 'challenge.js' in html_content and 'AwsWafIntegration' in html_content:
        return True
    return False


def _waf_browser_fetch_eurlex_html(celex: str, language: str = "EN") -> Optional[str]:
    """
    Fetch the EUR-Lex HTML manifestation through the Playwright WAF browser.

    httpx requests to eur-lex are WAF-walled (challenge page), which is why the
    pipeline otherwise falls back to the noisy EP RegData PDF for Commission
    proposals. The real rendered HTML is clean (proper recital/article markup),
    so try it before the PDF fallback. Synchronous (Playwright) — call via
    asyncio.to_thread so it does not block the event loop.
    """
    try:
        from services.scrapers.waf_browser_fetcher import WafBrowserFetcher
        url = f"https://eur-lex.europa.eu/legal-content/{(language or 'EN').upper()}/TXT/HTML/?uri=CELEX:{celex}"
        with WafBrowserFetcher() as fetcher:
            res = fetcher.fetch(url, expand_accordions=False)
        html = res.html or None
        return html if (html and not is_waf_blocked(html)) else None
    except Exception as exc:  # noqa: BLE001 - best-effort enrichment
        logger.warning(f"WAF browser fetch failed for {celex}: {exc}")
        return None


def build_ep_regdata_url(celex: str, language: str = "EN") -> Optional[str]:
    """
    Build European Parliament RegData URL for COM documents.

    CELEX format for COM documents: 5YYYYPCnnnn (e.g., 52025PC0543)
    RegData URL format: https://www.europarl.europa.eu/RegData/docs_autres_institutions/
                        commission_europeenne/com/YYYY/nnnn/COM_COM(YYYY)nnnn_EN.pdf
    """
    # Match COM document CELEX: 5YYYYPCnnnn
    match = re.match(r'^5(\d{4})PC(\d+)$', celex)
    if not match:
        return None

    year = match.group(1)
    number = match.group(2).zfill(4)  # Pad to 4 digits

    return (
        f"https://www.europarl.europa.eu/RegData/docs_autres_institutions/"
        f"commission_europeenne/com/{year}/{number}/COM_COM({year}){number}_{language}.pdf"
    )


def get_title_from_tracked_files(celex: str) -> Optional[str]:
    """
    Look up document title from tracked legislative files by CELEX number.
    """
    try:
        db = SessionLocal()
        carriage = db.query(LegislativeCarriage).filter(
            LegislativeCarriage.celex_numbers.contains([celex])
        ).first()
        db.close()

        if carriage:
            return carriage.title
        return None
    except Exception as e:
        logger.debug(f"Could not look up title for {celex}: {str(e)}")
        return None


async def fetch_com_document_from_ep(celex: str, language: str = "EN") -> Optional[dict]:
    """
    Fetch COM document PDF from European Parliament RegData as fallback.

    Returns processed document content or None if not available.
    """
    url = build_ep_regdata_url(celex, language)
    if not url:
        logger.debug(f"CELEX {celex} is not a COM document, skipping EP RegData fallback")
        return None

    logger.info(f"Trying EP RegData fallback for {celex}: {url}")

    try:
        # First verify the URL returns a PDF
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.head(url)

            if response.status_code != 200:
                logger.warning(f"EP RegData returned {response.status_code} for {celex}")
                return None

        # Process the PDF from URL
        pdf_processor = PDFProcessor()
        pdf_content = await pdf_processor.process_pdf_from_url(url)

        if pdf_content and pdf_content.full_text:
            logger.info(f"Successfully processed {pdf_content.word_count} words from EP RegData for {celex}")
            return {
                'text': pdf_content.full_text,
                'metadata': {
                    'title': pdf_content.metadata.title,
                    'author': pdf_content.metadata.author,
                    'page_count': pdf_content.metadata.page_count,
                },
                'word_count': pdf_content.word_count,
                'quality': pdf_content.extraction_quality,
                'source': 'EP-RegData',
                'source_url': url
            }

        return None

    except Exception as e:
        logger.error(f"Failed to fetch from EP RegData for {celex}: {str(e)}")
        return None

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
    current_user: User = Depends(get_current_user),
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
            user_id=str(current_user.id) if current_user else None
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

        # Create a user_documents record to bridge file uploads with My EU Bubble
        user_document_id = None
        if current_user:
            try:
                from models.user_document import UserDocument

                db = SessionLocal()
                extracted_text = ""
                if processed_content:
                    extracted_text = processed_content.get('text', '') or ''

                user_doc = UserDocument(
                    user_id=current_user.id,
                    document_type='uploaded',
                    title=file.filename,
                    content=extracted_text[:100000] if extracted_text else None,
                    storage_document_id=document_id,
                    original_filename=file.filename,
                    file_content_type=file.content_type,
                    file_size_bytes=len(file_content),
                    include_in_ai_context=True,
                )
                db.add(user_doc)
                db.commit()
                db.refresh(user_doc)
                user_document_id = str(user_doc.id)
                logger.info(f"Created user_document {user_document_id} for upload {document_id}")
                db.close()
            except Exception as e:
                logger.warning(f"Failed to create user_document for upload {document_id}: {e}")

        return JSONResponse(
            status_code=200,
            content={
                'document_id': document['document_id'],
                'user_document_id': user_document_id,
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
        ep_regdata_fallback_used = False

        try:
            eurlex_client = EURLexClient()
            html_content = await eurlex_client.get_document_html(celex, request.language)
            await eurlex_client.close()

            # Check if WAF blocked the request
            if is_waf_blocked(html_content):
                # Try the Playwright WAF browser first — it returns the real,
                # clean EUR-Lex HTML. This avoids the garbled EP RegData PDF
                # fallback for Commission proposals (PC) and other WAF-walled docs.
                logger.warning(f"EUR-Lex WAF blocked request for {celex}, trying WAF browser")
                import asyncio
                html_content = await asyncio.to_thread(
                    _waf_browser_fetch_eurlex_html, celex, request.language
                )

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

                # Add articles - expand into separate amendable elements
                for article in parsed.articles:
                    # 1. Article title element (if article has a title)
                    if article.title:
                        elements.append({
                            'type': 'article_title',
                            'number': article.number,
                            'text': article.title,
                            'article_number': article.number,
                            'level': 0
                        })

                    # 2. Article intro text (text before first paragraph)
                    if article.intro_text:
                        elements.append({
                            'type': 'article_intro',
                            'number': article.number,
                            'text': article.intro_text,
                            'article_number': article.number,
                            'level': 0
                        })

                    # 3. Each paragraph as separate element
                    for para in article.paragraphs:
                        # Add the paragraph itself
                        elements.append({
                            'type': 'paragraph',
                            'number': para.number,
                            'text': para.text,
                            'article_number': article.number,
                            'level': 1
                        })

                        # 4. Each subparagraph as separate element
                        for subpara in para.subparagraphs:
                            elements.append({
                                'type': 'subparagraph',
                                'number': subpara.number,
                                'text': subpara.text,
                                'article_number': article.number,
                                'paragraph_number': para.number,
                                'level': 2
                            })

                    # If no paragraphs were extracted, add the full article text
                    if not article.paragraphs and not article.intro_text:
                        article_text = article.text if article.text else f"Article {article.number}"
                        elements.append({
                            'type': 'article',
                            'number': article.number,
                            'text': article_text,
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

        except Exception as e:
            logger.warning(f"Failed to parse legislative structure from EUR-Lex: {str(e)}")

        # Fallback to EP RegData for COM documents if EUR-Lex failed
        if not legislative_structure:
            ep_fallback = await fetch_com_document_from_ep(celex, request.language)
            if ep_fallback:
                ep_regdata_fallback_used = True
                fallback_text = ep_fallback.get('text', '')
                text = fallback_text or text

                # Parse the COM document text to extract recitals and articles
                if fallback_text:
                    parsed = parse_com_document_text(fallback_text, celex)

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

                    # Add articles - expand into separate amendable elements
                    for article in parsed.articles:
                        # 1. Article title element (if article has a title)
                        if article.title:
                            elements.append({
                                'type': 'article_title',
                                'number': article.number,
                                'text': article.title,
                                'article_number': article.number,
                                'level': 0
                            })

                        # 2. Article intro text (text before first paragraph)
                        if article.intro_text:
                            elements.append({
                                'type': 'article_intro',
                                'number': article.number,
                                'text': article.intro_text,
                                'article_number': article.number,
                                'level': 0
                            })

                        # 3. Each paragraph as separate element
                        for para in article.paragraphs:
                            elements.append({
                                'type': 'paragraph',
                                'number': para.number,
                                'text': para.text,
                                'article_number': article.number,
                                'level': 1
                            })

                            # 4. Each subparagraph as separate element
                            for subpara in para.subparagraphs:
                                elements.append({
                                    'type': 'subparagraph',
                                    'number': subpara.number,
                                    'text': subpara.text,
                                    'article_number': article.number,
                                    'paragraph_number': para.number,
                                    'level': 2
                                })

                        # If no paragraphs were extracted, add the full article text
                        if not article.paragraphs and not article.intro_text:
                            article_text = article.text if article.text else f"Article {article.number}"
                            elements.append({
                                'type': 'article',
                                'number': article.number,
                                'text': article_text,
                                'title': article.title,
                                'level': 0
                            })

                    if elements:
                        # Get title from parsed document, EP fallback, or document_data
                        fallback_title = parsed.title or ep_fallback.get('metadata', {}).get('title') or document_data.get('title', '')

                        legislative_structure = {
                            'elements': elements,
                            'title': fallback_title,
                            'celex': celex,
                            'source': 'EP-RegData (PDF)'
                        }
                        logger.info(f"Parsed {len(parsed.recitals)} recitals and {len(parsed.articles)} articles from EP RegData PDF for {celex}")

        # Get title - prefer parsed title, fall back to scraper title, then tracked files
        document_title = ''
        if legislative_structure and legislative_structure.get('title'):
            document_title = legislative_structure.get('title')
        if not document_title:
            document_title = document_data.get('title', '')
        if not document_title or document_title == 'Unknown Title':
            tracked_title = get_title_from_tracked_files(celex)
            if tracked_title:
                document_title = tracked_title
                # Also update the legislative_structure title if it exists
                if legislative_structure:
                    legislative_structure['title'] = tracked_title

        # Build response
        response_data = {
            'document_id': document_id,
            'filename': f"{celex}.pdf" if ep_regdata_fallback_used else f"{celex}.html",
            'text': text,
            'metadata': {
                'celex': celex,
                'title': document_title,
                'date': str(document_data.get('date_published', '')) if document_data.get('date_published') else '',
                'type': document_data.get('document_type', ''),
                'language': request.language,
                'source': 'EP-RegData' if ep_regdata_fallback_used else 'EUR-Lex',
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


# ---------------------------------------------------------------------------
# In-editor AI co-writer (Phase 3) -- Mistral-first via the multi-provider chain
# ---------------------------------------------------------------------------

# Non-chat tooling: routes through MultiProviderService at the default
# prefer_claude=False, so Mistral is primary (Claude only as automatic fallback).
AI_ASSIST_ACTIONS = {
    "rewrite": "Rewrite the passage to read more clearly and professionally, keeping its meaning and roughly its length.",
    "shorten": "Make the passage more concise without losing essential meaning.",
    "expand": "Expand the passage with relevant detail, keeping the same voice and intent.",
    "formalise": "Rewrite the passage in a more formal, institutional register suitable for EU policy work.",
    "simplify": "Rewrite the passage in plain language a non-specialist can understand, without losing the substance.",
    "continue": "Continue writing naturally from where the passage ends, adding one short coherent paragraph.",
}

AI_ASSIST_LANGUAGES = {
    "en": "British English",
    "es": "Spanish",
    "ca": "Catalan",
    "fr": "French",
    "it": "Italian",
    "nl": "Dutch",
}


class AiAssistRequest(BaseModel):
    action: str
    text: str
    doc_title: Optional[str] = None
    target_language: Optional[str] = None


@router.post("/ai-assist", summary="In-editor AI co-writer (Mistral-first)")
async def ai_assist(
    req: AiAssistRequest,
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Rewrite / shorten / formalise / translate a selected passage. Returns only the edited text."""
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="No text supplied.")

    if req.action == "translate":
        lang = AI_ASSIST_LANGUAGES.get((req.target_language or "en").lower(), "British English")
        instruction = f"Translate the passage faithfully into {lang}. Preserve meaning, tone and any markdown formatting."
    else:
        instruction = AI_ASSIST_ACTIONS.get(req.action)
        if not instruction:
            raise HTTPException(status_code=400, detail=f"Unknown action: {req.action}")

    system_prompt = (
        "You are an expert EU public affairs editor helping a user refine a document. "
        "Edit the passage the user selected and return ONLY the edited passage: no preamble, "
        "no explanation, no surrounding quotation marks. Preserve any markdown formatting. "
        "Use British English. Do not use em-dashes. Be specific and avoid hedging."
    )
    user_message = (
        f"{instruction}\n\n"
        f"Document title: {req.doc_title or '(untitled)'}\n\n"
        f"Passage:\n{req.text}"
    )

    try:
        service = get_multi_provider_service()
        # prefer_claude defaults to False -> Mistral primary, Claude as fallback.
        response = await service.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1500,
            temperature=0.4,
        )
        result = (response.message or "").strip()
        # Strip wrapping quotes the model sometimes adds, and scrub dashes.
        if len(result) >= 2 and result[0] in "\"'" and result[-1] == result[0]:
            result = result[1:-1].strip()
        result = result.replace("—", "-").replace("–", "-")
        if not result:
            raise HTTPException(status_code=502, detail="The model returned no text. Please try again.")
        return JSONResponse({"result": result, "provider": getattr(response, "provider", None)})
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("AI assist failed")
        raise HTTPException(status_code=500, detail=f"AI assist failed: {exc}")


# ---------------------------------------------------------------------------
# Inline image assets for the document editor (Phase 2)
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_TYPES = {
    'image/png': '.png',
    'image/jpeg': '.jpg',
    'image/gif': '.gif',
    'image/webp': '.webp',
}
MAX_ASSET_BYTES = 5 * 1024 * 1024


@router.post("/assets", summary="Upload an inline image for the editor")
async def upload_asset(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
) -> JSONResponse:
    """Store an inline editor image and return a stable absolute URL to embed in markdown."""
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only PNG, JPEG, GIF or WebP images are allowed.")
    data = await file.read()
    if len(data) > MAX_ASSET_BYTES:
        raise HTTPException(status_code=400, detail="Image exceeds the 5 MB limit.")
    storage = get_document_storage()
    asset_id = storage.store_document(
        file_content=data,
        filename=file.filename or f"image{ALLOWED_IMAGE_TYPES[file.content_type]}",
        content_type=file.content_type,
        user_id=str(getattr(current_user, 'id', '') or ''),
        metadata={'kind': 'editor_image'},
    )
    # Absolute URL built from the serving host, so it resolves across origins
    # (frontend and backend are on different domains in production). Force https for
    # non-local hosts: behind Railway's TLS proxy request.base_url can be http://,
    # which a browser would block as mixed content on an https page.
    base = str(request.base_url).rstrip('/')
    if base.startswith('http://') and not any(h in base for h in ('localhost', '127.0.0.1')):
        base = 'https://' + base[len('http://'):]
    return JSONResponse({"asset_id": asset_id, "url": f"{base}/api/documents/assets/{asset_id}"})


@router.get("/assets/{asset_id}", summary="Serve an inline editor image")
async def serve_asset(asset_id: str) -> Response:
    """Serve a stored inline image. Public by unguessable id so <img> tags can load it."""
    storage = get_document_storage()
    content = storage.get_document_content(asset_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    meta = storage.get_document(asset_id) or {}
    if meta.get('custom_metadata', {}).get('kind') != 'editor_image':
        raise HTTPException(status_code=404, detail="Asset not found")
    content_type = meta.get('content_type', 'application/octet-stream')
    return Response(
        content=content,
        media_type=content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.get("/storage/{document_id}", response_model=DocumentMetadata)
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


@router.get("/storage/{document_id}/content", response_model=DocumentContentResponse)
async def get_document_content(document_id: str) -> JSONResponse:
    """
    Get document full content (text, structure, metadata).

    For uploaded legislative documents, this will automatically detect and parse
    the document structure (articles, paragraphs, subparagraphs) so each element
    can be individually amended in the Amendator UI.
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
        text = processed.get('text', '')
        structure = processed.get('structure')

        # If no legislative_structure exists, try to detect and parse legislative text
        if not structure or not structure.get('legislative_structure'):
            legislative_structure = parse_text_as_legislative(text)

            if legislative_structure:
                structure = {'legislative_structure': legislative_structure}
                logger.info(f"Detected and parsed legislative structure in uploaded document {document_id}")

        return JSONResponse(
            status_code=200,
            content={
                'document_id': document['document_id'],
                'filename': document['filename'],
                'text': text,
                'metadata': processed.get('metadata', {}),
                'structure': structure,
                'tables': processed.get('tables'),
                'quality': processed.get('quality', 'unknown')
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document content: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/storage/{document_id}")
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
