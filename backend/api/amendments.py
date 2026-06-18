"""
Amendments API Router

FastAPI endpoints for managing legislative amendments in the Amendator feature.

Endpoints:
- POST /api/amendments - Create single amendment
- POST /api/amendments/batch - Create multiple amendments
- GET /api/amendments - List user's amendments
- GET /api/amendments/{id} - Get specific amendment
- PUT /api/amendments/{id} - Update amendment
- DELETE /api/amendments/{id} - Delete amendment
- GET /api/amendments/stats - Get amendment statistics
- GET /api/amendments/export/{format} - Export amendments
"""

import logging
from typing import List, Optional
from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func

from models.user import User
from models.amendment import Amendment
from schemas.amendment_schemas import (
    AmendmentCreate,
    AmendmentUpdate,
    AmendmentResponse,
    AmendmentListResponse,
    AmendmentBatchCreate,
    AmendmentStats,
    BatchSuggestionRequest,
    BatchSuggestionResponse,
    BatchSuggestionItem,
    ImproveTextRequest,
    ImproveTextResponse,
    JustifyRequest,
    JustifyResponse,
    AnalyseArticleRequest,
    AnalyseArticleResponse,
)
from core.database import get_db
from api.auth_optional import get_current_user_dev as get_current_user
from services.amendator.amendment_export_service import get_export_service
from services.amendator.amendment_linker import get_amendment_linker

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/amendments",
    tags=["Amendments"],
    responses={404: {"description": "Not found"}}
)


# ============================================================================
# Amendment CRUD Operations
# ============================================================================

@router.post(
    "",
    response_model=AmendmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create amendment",
    description="Create a new legislative amendment"
)
async def create_amendment(
    amendment: AmendmentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AmendmentResponse:
    """
    Create a new amendment.
    """
    try:
        new_amendment = Amendment(
            user_id=current_user.id,
            document_id=amendment.document_id,
            document_filename=amendment.document_filename,
            element_index=amendment.element_index,
            element_type=amendment.element_type,
            element_number=amendment.element_number,
            position_text=amendment.position_text,
            amendment_type=amendment.amendment_type,
            original_text=amendment.original_text,
            proposed_text=amendment.proposed_text,
            insert_after=amendment.insert_after,
            justification=amendment.justification,
            group_label=amendment.group_label,
            author=amendment.author,
            amendment_number=amendment.amendment_number,
            status=amendment.status,
        )

        # Auto-link to tracked carriage if CELEX matches
        linker = get_amendment_linker(db)
        linker.auto_link_amendment(new_amendment)

        db.add(new_amendment)
        db.commit()
        db.refresh(new_amendment)

        logger.info(f"Created amendment {new_amendment.id} for user {current_user.id}")
        return new_amendment

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating amendment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create amendment: {str(e)}"
        )


@router.post(
    "/batch",
    response_model=List[AmendmentResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create multiple amendments",
    description="Create multiple amendments at once (batch operation)"
)
async def create_amendments_batch(
    batch: AmendmentBatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[AmendmentResponse]:
    """
    Create multiple amendments in a single request.
    """
    try:
        created_amendments = []
        failed_indices = []
        linker = get_amendment_linker(db)

        # Idempotent batch save. The editor re-sends its whole working set on
        # every "Save" click, so without a dedup guard repeated saves create
        # duplicate rows (observed: 3 amendments -> 5 rows). Skip any incoming
        # amendment that is byte-identical to one already persisted for this
        # user+document, and dedup within the batch itself. A genuinely
        # different amendment on the same element (different text) still saves.
        def _content_key(element_index, amendment_type, position_text, original_text, proposed_text):
            return (
                element_index,
                amendment_type,
                (position_text or ''),
                (original_text or ''),
                (proposed_text or ''),
            )

        existing_rows = db.query(Amendment).filter(
            Amendment.user_id == current_user.id,
            Amendment.document_id == batch.document_id,
        ).all()
        seen_keys = {
            _content_key(a.element_index, a.amendment_type, a.position_text, a.original_text, a.proposed_text)
            for a in existing_rows
        }
        skipped = 0

        for idx, amendment_data in enumerate(batch.amendments):
            key = _content_key(
                amendment_data.element_index,
                amendment_data.amendment_type,
                amendment_data.position_text,
                amendment_data.original_text,
                amendment_data.proposed_text,
            )
            if key in seen_keys:
                skipped += 1
                continue
            seen_keys.add(key)
            try:
                new_amendment = Amendment(
                    user_id=current_user.id,
                    document_id=batch.document_id,
                    document_filename=batch.document_filename,
                    element_index=amendment_data.element_index,
                    element_type=amendment_data.element_type,
                    element_number=amendment_data.element_number,
                    position_text=amendment_data.position_text,
                    amendment_type=amendment_data.amendment_type,
                    original_text=amendment_data.original_text,
                    proposed_text=amendment_data.proposed_text,
                    insert_after=amendment_data.insert_after,
                    justification=amendment_data.justification,
                    group_label=amendment_data.group_label,
                    author=amendment_data.author,
                    amendment_number=amendment_data.amendment_number,
                    status=amendment_data.status,
                )
                # Auto-link to tracked carriage if CELEX matches
                linker.auto_link_amendment(new_amendment)
                db.add(new_amendment)
                created_amendments.append(new_amendment)
            except Exception as item_error:
                logger.warning(f"Failed to create amendment at index {idx}: {str(item_error)}")
                failed_indices.append(idx)

        if created_amendments:
            db.commit()
            for amendment in created_amendments:
                db.refresh(amendment)

        if failed_indices:
            logger.warning(f"Batch: {len(created_amendments)} created, {len(failed_indices)} failed (indices: {failed_indices})")

        logger.info(
            f"Batch save user {current_user.id}: {len(created_amendments)} created, "
            f"{skipped} skipped as duplicates"
        )
        return created_amendments

    except Exception as e:
        db.rollback()
        logger.error(f"Error creating batch amendments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create amendments: {str(e)}"
        )


@router.get(
    "",
    response_model=AmendmentListResponse,
    summary="List amendments",
    description="Get list of user's amendments with optional filters"
)
async def list_amendments(
    document_id: Optional[str] = Query(None, description="Filter by document ID"),
    carriage_id: Optional[UUID] = Query(None, description="Filter by linked carriage ID"),
    celex: Optional[str] = Query(None, description="Filter by CELEX number"),
    status: Optional[str] = Query(None, description="Filter by status"),
    amendment_type: Optional[str] = Query(None, description="Filter by amendment type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AmendmentListResponse:
    """
    Get list of user's amendments with pagination and filtering.
    """
    try:
        # Build query
        query = select(Amendment).where(Amendment.user_id == current_user.id)

        # Apply filters
        if document_id:
            query = query.where(Amendment.document_id == document_id)
        if carriage_id:
            query = query.where(Amendment.carriage_id == carriage_id)
        if celex:
            # Match both 'celex' and 'eurlex-celex' formats
            query = query.where(
                (Amendment.document_id == celex) | (Amendment.document_id == f'eurlex-{celex}')
            )
        if status:
            query = query.where(Amendment.status == status)
        if amendment_type:
            query = query.where(Amendment.amendment_type == amendment_type)

        # Order by creation date (newest first)
        query = query.order_by(Amendment.created_at.desc())

        # Get total count
        count_query = select(func.count()).select_from(Amendment).where(Amendment.user_id == current_user.id)
        if document_id:
            count_query = count_query.where(Amendment.document_id == document_id)
        if carriage_id:
            count_query = count_query.where(Amendment.carriage_id == carriage_id)
        if celex:
            count_query = count_query.where(
                (Amendment.document_id == celex) | (Amendment.document_id == f'eurlex-{celex}')
            )
        if status:
            count_query = count_query.where(Amendment.status == status)
        if amendment_type:
            count_query = count_query.where(Amendment.amendment_type == amendment_type)

        total = db.execute(count_query).scalar()

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        amendments = db.execute(query).scalars().all()

        return AmendmentListResponse(
            amendments=amendments,
            total=total,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"Error listing amendments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list amendments: {str(e)}"
        )


@router.get(
    "/{amendment_id}",
    response_model=AmendmentResponse,
    summary="Get amendment",
    description="Get a specific amendment by ID"
)
async def get_amendment(
    amendment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AmendmentResponse:
    """
    Get a specific amendment by ID.
    """
    try:
        query = select(Amendment).where(
            and_(
                Amendment.id == amendment_id,
                Amendment.user_id == current_user.id
            )
        )
        amendment = db.execute(query).scalar_one_or_none()

        if not amendment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Amendment not found"
            )

        return amendment

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting amendment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get amendment: {str(e)}"
        )


@router.put(
    "/{amendment_id}",
    response_model=AmendmentResponse,
    summary="Update amendment",
    description="Update an existing amendment"
)
async def update_amendment(
    amendment_id: UUID,
    amendment_update: AmendmentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AmendmentResponse:
    """
    Update an existing amendment.
    """
    try:
        # Get amendment
        query = select(Amendment).where(
            and_(
                Amendment.id == amendment_id,
                Amendment.user_id == current_user.id
            )
        )
        amendment = db.execute(query).scalar_one_or_none()

        if not amendment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Amendment not found"
            )

        # Update fields
        update_data = amendment_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(amendment, field, value)

        db.commit()
        db.refresh(amendment)

        logger.info(f"Updated amendment {amendment_id} for user {current_user.id}")
        return amendment

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating amendment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update amendment: {str(e)}"
        )


@router.delete(
    "/{amendment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete amendment",
    description="Delete an amendment"
)
async def delete_amendment(
    amendment_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete an amendment.
    """
    try:
        # Get amendment
        query = select(Amendment).where(
            and_(
                Amendment.id == amendment_id,
                Amendment.user_id == current_user.id
            )
        )
        amendment = db.execute(query).scalar_one_or_none()

        if not amendment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Amendment not found"
            )

        db.delete(amendment)
        db.commit()

        logger.info(f"Deleted amendment {amendment_id} for user {current_user.id}")
        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting amendment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete amendment: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=AmendmentStats,
    summary="Get amendment statistics",
    description="Get statistics about user's amendments"
)
async def get_amendment_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> AmendmentStats:
    """
    Get statistics about user's amendments.
    """
    try:
        # Total count
        total_query = select(func.count()).select_from(Amendment).where(Amendment.user_id == current_user.id)
        total = db.execute(total_query).scalar()

        # By status
        status_query = select(
            Amendment.status,
            func.count(Amendment.id)
        ).where(Amendment.user_id == current_user.id).group_by(Amendment.status)
        by_status = dict(db.execute(status_query).all())

        # By type
        type_query = select(
            Amendment.amendment_type,
            func.count(Amendment.id)
        ).where(Amendment.user_id == current_user.id).group_by(Amendment.amendment_type)
        by_type = dict(db.execute(type_query).all())

        # By document
        document_query = select(
            Amendment.document_id,
            func.count(Amendment.id)
        ).where(Amendment.user_id == current_user.id).group_by(Amendment.document_id)
        by_document = dict(db.execute(document_query).all())

        return AmendmentStats(
            total=total,
            by_status=by_status,
            by_type=by_type,
            by_document=by_document
        )

    except Exception as e:
        logger.error(f"Error getting amendment stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get amendment stats: {str(e)}"
        )


@router.get(
    "/export/{document_id}",
    summary="Export amendments to DOCX",
    description="Export all amendments for a document to DOCX format"
)
async def export_amendments(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export all amendments for a document to DOCX format.
    """
    try:
        # Get all amendments for this document
        query = select(Amendment).where(
            and_(
                Amendment.document_id == document_id,
                Amendment.user_id == current_user.id
            )
        ).order_by(Amendment.element_index)

        amendments = db.execute(query).scalars().all()

        if not amendments:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No amendments found for this document"
            )

        # Convert to dict format
        amendments_dict = [amendment.to_dict() for amendment in amendments]

        # Get document filename from first amendment
        document_filename = amendments[0].document_filename if amendments else None

        # Get export service
        export_service = get_export_service()

        # Generate DOCX file
        filepath = export_service.export_amendments_to_docx(
            amendments=amendments_dict,
            document_celex=document_id,
            user_id=str(current_user.id),
            subscription_tier=current_user.subscription_tier,
            document_filename=document_filename
        )

        # Return file for download
        return FileResponse(
            path=str(filepath),
            filename=filepath.name,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            headers={
                "Content-Disposition": f"attachment; filename={filepath.name}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting amendments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export amendments: {str(e)}"
        )


# ============================================================================
# Law Integration Endpoints
# ============================================================================

@router.get(
    "/law/{celex}",
    summary="Get law for amendment",
    description="Get EU law details for amending"
)
async def get_law_for_amendment(
    celex: str,
    article: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get EU law structure for amendment drafting.

    Returns articles, recitals, and annexes that can be amended.
    If article is specified, returns just that article's content.
    """
    from services.parsers import EurlexFetcher

    try:
        fetcher = EurlexFetcher(db=db)
        result = await fetcher.get_law(celex)

        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Law {celex} not found"
            )

        # If specific article requested, filter
        if article:
            matching_articles = [
                a for a in result.articles
                if str(a.get('number', '')) == str(article)
            ]
            return {
                'celex': result.celex,
                'title': result.title,
                'articles': matching_articles,
            }

        # Return full structure for amendment drafting
        return {
            'celex': result.celex,
            'title': result.title,
            'short_title': result.short_title,
            'doc_type': result.doc_type,
            'date': result.date.isoformat() if result.date else None,
            'source': result.source,
            'articles': [
                {
                    'number': a.get('number'),
                    'title': a.get('title', ''),
                    'has_content': bool(a.get('html') or a.get('paragraphs')),
                }
                for a in result.articles
            ],
            'recitals': [
                {'number': r.get('number'), 'text': r.get('text', '')[:200] + '...'}
                for r in result.recitals[:20]  # First 20 recitals
            ],
            'annexes': [
                {'id': a.get('id'), 'title': a.get('title', '')}
                for a in result.annexes
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting law {celex}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve law: {str(e)}"
        )


@router.post(
    "/resolve-citations",
    summary="Resolve CELEX citations",
    description="Extract and resolve CELEX references from text"
)
async def resolve_citations(
    text: str = Query(..., description="Text containing CELEX references"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Extract CELEX numbers from text and resolve them to law details.

    Useful for:
    - Auto-linking citations in amendments
    - Verifying legal basis references
    - Finding related legislation
    """
    import re
    from services.eu_law_search import EULawSearchService

    try:
        # Extract CELEX patterns
        celex_pattern = re.compile(r'\b(\d{5}[A-Z]\d{4})\b')
        found_celex = celex_pattern.findall(text)

        if not found_celex:
            return {'citations': [], 'message': 'No CELEX numbers found'}

        # Deduplicate
        unique_celex = list(set(found_celex))

        # Resolve each
        search_service = EULawSearchService(db)
        citations = []

        for celex in unique_celex[:10]:  # Max 10 citations
            result = search_service.get_by_celex(celex)
            if result:
                citations.append(result.to_dict())
            else:
                citations.append({
                    'celex': celex,
                    'title': None,
                    'found': False,
                    'eurlex_url': f'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}'
                })

        return {
            'citations': citations,
            'total_found': len(found_celex),
            'unique_resolved': len(citations)
        }

    except Exception as e:
        logger.error(f"Error resolving citations: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve citations: {str(e)}"
        )


# ============================================================================
# AI Amendment Suggestion Endpoint
# ============================================================================

@router.post(
    "/suggest",
    summary="AI-powered amendment suggestion",
    description=(
        "**What it does**\n\n"
        "Suggests an amendment to one selected legislative element that advances your policy position.\n\n"
        "**When to use it**\n\n"
        "When you have picked a recital, article, or paragraph and want a drafted change plus a justification.\n\n"
        "**Input**\n\n"
        "Your policy position, the element's original text, its type and position, and optionally the CELEX, "
        "element index, article number, supporting-document context, and the document's article numbers "
        "(for reference checking).\n\n"
        "**Try it**\n\n"
        "Select an article, enter a one-line policy aim, and read back the proposed text with fidelity badges.\n\n"
        "**You get back**\n\n"
        "The amendment type, proposed text, justification, a deterministic validation block, and the AI provider and model."
    ),
)
async def suggest_amendment(
    policy_position: str = Query(..., description="User's policy position or goals"),
    original_text: str = Query(..., description="The legislative text to amend"),
    element_type: str = Query(..., description="Type of element: recital, article, point, etc."),
    element_position: str = Query(..., description="Position reference, e.g., 'Recital 1', 'Article 3'"),
    supporting_context: Optional[str] = Query(None, description="Extracted text from supporting documents"),
    celex: Optional[str] = Query(None, description="CELEX of the loaded law, used to inject drafting context"),
    element_index: Optional[int] = Query(None, description="Index of the element in the full loaded document, for reliable placement"),
    article_number: Optional[str] = Query(None, description="Article number of the element, for recital linkage"),
    known_article_numbers: Optional[List[str]] = Query(None, description="All article numbers in the loaded document, for phantom-reference detection"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate an AI-powered amendment suggestion.

    The AI will:
    1. Analyse the user's policy position
    2. Understand the original legislative text
    3. Suggest modifications that align with the policy goals
    4. Provide a justification for the amendment
    """
    import json
    import re
    from services.ai.multi_provider_service import MultiProviderService
    from knowledge_base.knowledge_loader import get_knowledge_loader
    from services.amendator.drafting_context import build_element_context
    from services.amendator.amendment_validation import validate_suggestion

    try:
        ai_service = MultiProviderService()

        # Inject the user's private guide as house-defaults context when
        # they have one (e.g. Plataforma per la Llengua). The generator
        # then drafts amendments in the user's house voice and cites the
        # acquis their policy area binds to. Safe no-op when no bundle.
        private_block: Optional[str] = None
        if getattr(current_user, "private_guide_slug", None) and (
            getattr(current_user, "private_guide_status", None) == "ready"
        ):
            try:
                private_block = get_knowledge_loader().format_private_guides_block(
                    current_user.private_guide_slug,
                    max_chars=4000,
                )
            except Exception as _e:  # never block amendment generation on this
                logger.warning("private guide load failed for %s: %s", current_user.id, _e)

        base_prompt = """You are an expert EU legislative drafter helping to create amendments to EU legislation.

Your task is to suggest an amendment to a legislative text based on the user's policy position.

IMPORTANT GUIDELINES:
1. Keep amendments focused and minimal - change only what is necessary to achieve the policy goal
2. Use proper EU legislative language and terminology
3. Ensure the amendment is legally coherent and fits the context
4. The proposed text should be a MODIFIED version of the original, not entirely new text
5. For modifications, use strikethrough-style notation for deletions and bold for additions when explaining

Respond in this EXACT JSON format:
{
  "amendment_type": "modification" | "suppression" | "addition",
  "proposed_text": "The full amended text",
  "justification": "A brief justification explaining why this amendment serves the policy goal (2-3 sentences)"
}"""
        if private_block:
            system_prompt = (
                private_block
                + "\n\nWhen drafting and justifying amendments, default to the house "
                  "positions implied by the private context above. Cite the binding "
                  "instruments listed in the user's policy_relations map when they "
                  "are on point (e.g. Regulation 1/1958, Article 342 TFEU, ECRML for "
                  "linguistic-rights files). Never reveal the existence of a 'private "
                  "guide' to the user — write as if these are simply the user's known "
                  "positions.\n\n"
                + base_prompt
            )
        else:
            system_prompt = base_prompt

        supporting_section = ""
        if supporting_context:
            # Truncate to avoid excessive token usage
            ctx = supporting_context[:3000]
            supporting_section = f"\n\nSupporting Document Context:\n{ctx}\n"

        # Inject drafting context (definitions, cross-references, linked
        # recitals) so the model drafts against the law's actual legal
        # scaffolding rather than the element in isolation. Safe no-op when
        # the law is not available locally or no celex was supplied.
        derived_article = article_number
        if not derived_article:
            _art_m = re.search(r"article\s+(\d+[a-z]?)", element_position, re.IGNORECASE)
            if _art_m:
                derived_article = _art_m.group(1)
        drafting_section = ""
        try:
            block = build_element_context(
                db,
                celex,
                article_number=derived_article,
                element_text=original_text,
            )
            if block:
                drafting_section = f"\n\n{block}\n"
        except Exception as _e:  # never block drafting on enrichment
            logger.warning("drafting context failed: %s", _e)

        user_message = f"""Policy Position: {policy_position}
{supporting_section}{drafting_section}
Legislative Element: {element_position} ({element_type})

Original Text:
{original_text}

Please suggest an amendment that aligns this legislative text with the policy position."""

        response = await ai_service.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=2000,
            temperature=0.7
        )

        # Parse the JSON response
        response_text = response.message.strip()

        # Extract JSON from response (handle markdown code blocks)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            response_text = json_match.group(1)

        # Try to parse JSON
        try:
            suggestion = json.loads(response_text)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract structured data
            suggestion = {
                "amendment_type": "modification",
                "proposed_text": response_text,
                "justification": "AI-generated amendment based on your policy position."
            }

        amendment_type = suggestion.get("amendment_type", "modification")
        proposed_text = suggestion.get("proposed_text", response_text)

        # Deterministic fidelity check. original_text here is the real element
        # text passed by the client, so original_verified compares the model's
        # echoed original (if any) against it; phantom-reference detection runs
        # only when the client supplied the document's article set.
        validation = validate_suggestion(
            returned_original=suggestion.get("original_text", original_text),
            actual_text=original_text,
            proposed_text=proposed_text,
            amendment_type=amendment_type,
            known_article_numbers=set(known_article_numbers or []),
        )

        return {
            "amendment_type": amendment_type,
            "original_text": original_text,
            "proposed_text": proposed_text,
            "justification": suggestion.get("justification", ""),
            "element_index": element_index,
            "element_position": element_position,
            "validation": validation,
            "ai_provider": response.provider,
            "ai_model": response.model
        }

    except Exception as e:
        logger.error(f"Error generating amendment suggestion: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate amendment suggestion: {str(e)}"
        )


@router.post(
    "/suggest-batch",
    response_model=BatchSuggestionResponse,
    summary="Document-wide AI amendment suggestions",
    description="Analyse multiple legislative elements and suggest the most impactful amendments"
)
async def suggest_batch_amendments(
    request: BatchSuggestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered amendment suggestions for an entire document.

    Uses chunked parallel AI calls to ensure full-document coverage:
    1. Split elements into chunks (recitals + groups of ~15 articles)
    2. Fire parallel AI calls per chunk
    3. Merge results into a single response
    """
    from services.ai.multi_provider_service import MultiProviderService
    from services.amendator.drafting_context import build_document_definitions_block
    from services.amendator.amendment_validation import validate_suggestion
    import asyncio
    import json
    import re

    # Determine max_suggestions based on subscription tier
    tier = current_user.subscription_tier or 'white'
    if tier in ('blue', 'admin'):
        tier_max = min(30, len(request.elements))
    elif tier == 'yellow':
        tier_max = 15
    else:
        tier_max = 5

    max_suggestions = min(request.max_suggestions, tier_max) if request.max_suggestions else tier_max

    # --- Chunk elements by type for coherent grouping ---
    recitals = [e for e in request.elements if e.element_type == 'recital']
    non_recitals = [e for e in request.elements if e.element_type != 'recital']

    chunks = []
    if recitals:
        chunks.append(recitals)

    # Split non-recitals into groups of ~15, keeping article sub-elements together
    CHUNK_SIZE = 15
    current_chunk = []
    for elem in non_recitals:
        current_chunk.append(elem)
        if len(current_chunk) >= CHUNK_SIZE and elem.element_type == 'article':
            chunks.append(current_chunk)
            current_chunk = []
    if current_chunk:
        # Merge small trailing chunk with previous if too small
        if len(current_chunk) < 5 and len(chunks) > 0:
            chunks[-1].extend(current_chunk)
        else:
            chunks.append(current_chunk)

    # If only one small chunk, just use it directly
    if not chunks:
        chunks = [list(request.elements)]

    # --- Allocate suggestions per chunk proportionally ---
    total_elements = sum(len(c) for c in chunks)
    chunk_targets = []
    allocated = 0
    for i, chunk in enumerate(chunks):
        if i == len(chunks) - 1:
            target = max_suggestions - allocated
        else:
            target = max(2, round(max_suggestions * len(chunk) / total_elements))
        chunk_targets.append(target)
        allocated += target

    # --- Build per-chunk AI call coroutines ---
    ai_service = MultiProviderService()

    supporting_section = ""
    if request.supporting_context:
        ctx = request.supporting_context[:4000]
        supporting_section = f"\n\nSupporting Document Context (user's policy document):\n{ctx}\n"

    # Document-level defined-terms glossary, injected once into every chunk so
    # batch suggestions stay consistent with the law's own definitions. Safe
    # no-op when the law is unavailable locally or has no extractable terms.
    definitions_section = ""
    try:
        defs_block = build_document_definitions_block(db, request.celex)
        if defs_block:
            definitions_section = f"\n\n{defs_block}\n"
    except Exception as _e:
        logger.warning("batch drafting context failed: %s", _e)

    async def _generate_for_chunk(chunk_elements, target_count):
        """Generate amendment suggestions for a single chunk of elements."""
        elements_text = ""
        for i, elem in enumerate(chunk_elements):
            elements_text += f"\n{i+1}. {elem.position} ({elem.element_type}):\n{elem.text}\n"

        system_prompt = f"""You are an expert EU legislative drafter. You will analyse a set of legislative elements and suggest amendments based on the user's policy position.

IMPORTANT GUIDELINES:
1. You MUST suggest exactly {target_count} amendments - no fewer
2. Prioritise articles over recitals (articles have legal force)
3. Keep each amendment focused and minimal - change only what is necessary
4. Use proper EU legislative language and terminology
5. Ensure amendments are legally coherent
6. Each proposed_text should be a MODIFIED version of the original, not entirely new text
7. For suppressions, set proposed_text to empty string ""
8. Amend as many different elements as possible from the list provided

Respond in this EXACT JSON format (an array of objects):
[
  {{
    "element_position": "Article 5",
    "amendment_type": "modification",
    "original_text": "The original text...",
    "proposed_text": "The amended text...",
    "justification": "Brief justification (2-3 sentences)"
  }}
]

Return ONLY the JSON array, no additional text."""

        user_message = f"""Policy Position: {request.policy_position}
{supporting_section}{definitions_section}
Legislative Elements to Analyse:
{elements_text}

You MUST return exactly {target_count} amendments as a JSON array."""

        response = await ai_service.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=4000,
            temperature=0.7
        )

        # Parse JSON response - handle multiple formats
        response_text = response.message.strip()

        # Try 1: Extract from markdown code fences (with closing fence)
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            response_text = json_match.group(1)

        # Try 2: Extract JSON array directly (handles truncated fences or raw JSON)
        if not response_text.startswith('['):
            array_match = re.search(r'(\[[\s\S]*)', response_text)
            if array_match:
                response_text = array_match.group(1)

        # Try 3: If JSON array is truncated (no closing ]), try to fix it
        response_text = response_text.strip()
        if response_text.startswith('[') and not response_text.endswith(']'):
            # Find last complete object (ending with })
            last_brace = response_text.rfind('}')
            if last_brace > 0:
                response_text = response_text[:last_brace + 1] + ']'

        try:
            suggestions_raw = json.loads(response_text)
            if not isinstance(suggestions_raw, list):
                suggestions_raw = [suggestions_raw]
        except json.JSONDecodeError:
            print(f"[AMENDATOR] Failed to parse chunk JSON: {response_text[:300]}")
            suggestions_raw = []

        return suggestions_raw, response.provider, response.model

    # --- Fire parallel AI calls ---
    print(f"[AMENDATOR] Batch suggest: user={current_user.email} tier={tier}, {len(request.elements)} elements, {len(chunks)} chunks, targets={chunk_targets}, max={max_suggestions}")

    try:
        tasks = [
            _generate_for_chunk(chunk, target)
            for chunk, target in zip(chunks, chunk_targets)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # --- Merge results ---
        element_lookup = {elem.position: elem.text for elem in request.elements}
        position_to_index = {
            elem.position: elem.element_index
            for elem in request.elements
            if elem.element_index is not None
        }
        known_articles = set(request.known_article_numbers or [])
        all_suggestions = []
        provider = "unknown"
        model = "unknown"

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"[AMENDATOR] Chunk {i+1}/{len(chunks)} failed: {result}")
                continue

            suggestions_raw, chunk_provider, chunk_model = result
            provider = chunk_provider
            model = chunk_model

            for item in suggestions_raw:
                pos = item.get("element_position", "")
                # Force the real element text when we know it, so the diff the
                # user reviews is always against the genuine baseline, never a
                # model paraphrase.
                actual_text = element_lookup.get(pos)
                if actual_text is None:
                    actual_text = item.get("original_text", "")
                amendment_type = item.get("amendment_type", "modification")
                proposed_text = item.get("proposed_text", "")
                validation = validate_suggestion(
                    returned_original=item.get("original_text", actual_text),
                    actual_text=actual_text,
                    proposed_text=proposed_text,
                    amendment_type=amendment_type,
                    known_article_numbers=known_articles,
                )
                all_suggestions.append(BatchSuggestionItem(
                    element_position=pos,
                    amendment_type=amendment_type,
                    original_text=actual_text,
                    proposed_text=proposed_text,
                    justification=item.get("justification", ""),
                    element_index=position_to_index.get(pos),
                    validation=validation,
                ))

        # Cap at max_suggestions
        all_suggestions = all_suggestions[:max_suggestions]

        if not all_suggestions:
            # All chunks failed
            raise Exception("All AI chunk calls failed to produce suggestions")

        print(f"[AMENDATOR] Batch suggest complete: {len(all_suggestions)} suggestions from {len(chunks)} chunks via {provider}")

        return BatchSuggestionResponse(
            suggestions=all_suggestions,
            ai_provider=provider,
            ai_model=model
        )

    except Exception as e:
        logger.error(f"Error generating batch amendment suggestions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate amendment suggestions: {str(e)}"
        )


# ============================================================================
# AI AMENDMENT TEXT IMPROVEMENT
# ============================================================================

@router.post(
    "/improve",
    response_model=ImproveTextResponse,
    summary="AI-powered amendment text improvement",
    description="Polish and improve user-drafted amendment text using EU legislative conventions"
)
async def improve_amendment_text(
    request: ImproveTextRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Improve user-drafted amendment text with AI polishing.

    The AI will:
    1. Polish language to use proper EU legislative jargon
    2. Incorporate context from the user's uploaded documents
    3. Align with the user's policy preferences
    4. Preserve the user's intent and policy direction
    """
    from services.ai.multi_provider_service import MultiProviderService
    from models.user_document import UserDocument
    import json
    import re

    # Tier gating: Yellow and above only
    tier = current_user.subscription_tier or 'white'
    if tier == 'white':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI text improvement requires a Yellow or Blue subscription"
        )

    try:
        ai_service = MultiProviderService()

        # --- Gather user context ---

        # 1. Policy interests
        policy_interests = current_user.policy_interests_list or []

        # 2. User's most recent documents (max 3, capped at 2000 chars total)
        user_docs = db.query(UserDocument).filter(
            and_(
                UserDocument.user_id == current_user.id,
                UserDocument.content.isnot(None)
            )
        ).order_by(UserDocument.updated_at.desc()).limit(3).all()

        doc_context_parts = []
        total_chars = 0
        for doc in user_docs:
            snippet = (doc.content or "")[:700]
            if total_chars + len(snippet) > 2000:
                snippet = snippet[:2000 - total_chars]
            if snippet:
                doc_context_parts.append(f"[{doc.title}]: {snippet}")
                total_chars += len(snippet)
            if total_chars >= 2000:
                break
        doc_context = "\n".join(doc_context_parts)

        # --- Build AI prompt ---

        system_prompt = """You are an expert EU legislative drafter. Your task is to IMPROVE existing amendment text drafted by the user.

GUIDELINES:
1. Polish the text to use proper EU legislative jargon, formal terminology, and standard phrasing
2. Maintain the user's intent and policy direction - do NOT change the substance
3. Ensure legal precision, clarity, and consistency with EU legislative conventions
4. Fix any grammar, awkward phrasing, or informal language
5. If user context documents are provided, align terminology with them
6. Keep the text concise - legislative text should be unambiguous but not verbose

Respond in this EXACT JSON format:
{
  "improved_text": "The polished amendment text",
  "changes_summary": "Brief description of improvements made (1 sentence)"
}"""

        # Build user message with all available context
        sections = [
            f"Element: {request.element_position} ({request.element_type})",
            f"Amendment type: {request.amendment_type}",
        ]
        if request.original_text:
            sections.append(f"Original legislative text:\n{request.original_text[:1000]}")
        if request.document_title:
            sections.append(f"Document: {request.document_title}")
        if policy_interests:
            sections.append(f"User's policy interests: {', '.join(policy_interests)}")
        if doc_context:
            sections.append(f"User's reference documents:\n{doc_context}")
        sections.append(f"User's drafted text to improve:\n{request.drafted_text[:3000]}")

        user_message = "\n\n".join(sections)

        print(f"[AMENDATOR] Improve text: user={current_user.email} tier={tier}, "
              f"element={request.element_position}, type={request.amendment_type}, "
              f"docs={len(user_docs)}, interests={len(policy_interests)}")

        # --- Call AI ---
        response = await ai_service.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1500,
            temperature=0.3
        )

        provider = response.provider
        model = response.model
        raw_response = response.message.strip()

        # --- Parse response ---
        # Try JSON extraction (handle markdown code blocks)
        json_text = raw_response
        code_block_match = re.search(r'```(?:json)?\s*(.*?)```', raw_response, re.DOTALL)
        if code_block_match:
            json_text = code_block_match.group(1).strip()

        try:
            parsed = json.loads(json_text)
            improved_text = parsed.get("improved_text", raw_response)
            changes_summary = parsed.get("changes_summary", "Text polished with EU legislative conventions")
        except json.JSONDecodeError:
            # Fallback: treat entire response as improved text
            improved_text = raw_response
            changes_summary = "Text polished with EU legislative conventions"

        print(f"[AMENDATOR] Improve complete: provider={provider}, model={model}")

        return ImproveTextResponse(
            improved_text=improved_text,
            changes_summary=changes_summary,
            ai_provider=provider,
            ai_model=model
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error improving amendment text: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to improve text: {str(e)}"
        )


# ============================================================================
# AI JUSTIFICATION + ARTICLE ANALYSIS
# (ported from the former Anthropic-only AIAmendmentGenerator onto the shared
#  free open-model chain; that dead class was removed.)
# ============================================================================

@router.post(
    "/justify",
    response_model=JustifyResponse,
    summary="AI-drafted amendment justification",
    description=(
        "**What it does**\n\n"
        "Drafts a short, EP-style justification explaining why a proposed amendment is needed.\n\n"
        "**When to use it**\n\n"
        "After you have an original and a proposed text and want a persuasive rationale to table with the amendment.\n\n"
        "**Input**\n\n"
        "The original text, the proposed text, the amendment type, and optionally your policy rationale.\n\n"
        "**Try it**\n\n"
        "Send a modification with a one-line policy rationale and read back the drafted justification.\n\n"
        "**You get back**\n\n"
        "A 2 to 3 paragraph justification plus the AI provider and model used."
    ),
)
async def justify_amendment(
    request: JustifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a justification for an amendment on the free open-model chain."""
    from services.ai.multi_provider_service import MultiProviderService

    system_prompt = (
        "You are an expert in EU legislative affairs. Write a clear, persuasive "
        "justification for a legislative amendment in formal EU drafting language. "
        "Use British English. Do not use em-dashes. Do not use emojis. Return only "
        "the justification prose, no headings, no preamble."
    )
    user_message = (
        f"Amendment type: {request.amendment_type}\n"
        f"Element: {request.element_position or '(unspecified)'}\n\n"
        f"Original text:\n{request.original_text or '(none)'}\n\n"
        f"Proposed text:\n{request.proposed_text or '(none)'}\n\n"
        f"Policy rationale: {request.policy_rationale or '(infer from the change)'}\n\n"
        "Write a justification (2 to 3 paragraphs) covering why the amendment is "
        "necessary, what it improves, and how it aligns with EU policy objectives."
    )

    try:
        ai_service = MultiProviderService()
        response = await ai_service.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1000,
            temperature=0.5,
        )
        text = (response.message or "").strip().replace("—", "-").replace("–", "-")
        if not text:
            raise HTTPException(status_code=502, detail="The model returned no text. Please try again.")
        return JustifyResponse(
            justification=text,
            ai_provider=response.provider,
            ai_model=response.model,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating justification: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate justification: {str(e)}",
        )


@router.post(
    "/analyse-article",
    response_model=AnalyseArticleResponse,
    summary="AI analysis of an article for amendment opportunities",
    description=(
        "**What it does**\n\n"
        "Reads one article and points out its key provisions, ambiguities, and where amendments could improve it.\n\n"
        "**When to use it**\n\n"
        "Before drafting, to scope where an article is worth amending.\n\n"
        "**Input**\n\n"
        "The article text, its position reference, and optionally the CELEX of the loaded law for added context.\n\n"
        "**Try it**\n\n"
        "Send an article body and read back the structured analysis.\n\n"
        "**You get back**\n\n"
        "A plain-language analysis plus the AI provider and model used."
    ),
)
async def analyse_article(
    request: AnalyseArticleRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Analyse an article for amendment opportunities on the free open-model chain."""
    import re as _re
    from services.ai.multi_provider_service import MultiProviderService
    from services.amendator.drafting_context import build_element_context

    derived_article = None
    _m = _re.search(r"article\s+(\d+[a-z]?)", request.article_position, _re.IGNORECASE)
    if _m:
        derived_article = _m.group(1)

    drafting_section = ""
    try:
        block = build_element_context(
            db,
            request.celex,
            article_number=derived_article,
            element_text=request.article_text,
        )
        if block:
            drafting_section = f"\n\n{block}\n"
    except Exception as _e:
        logger.warning("analyse-article drafting context failed: %s", _e)

    system_prompt = (
        "You are an expert in EU legislative drafting and analysis. Analyse the "
        "article and identify, as concise bullet points under clear headings: key "
        "provisions; potential issues or ambiguities; amendment opportunities; and "
        "related articles or acts to consider. Use British English. Do not use "
        "em-dashes. Do not use emojis."
    )
    user_message = (
        f"Article: {request.article_position}{drafting_section}\n\n"
        f"Text:\n{request.article_text}"
    )

    try:
        ai_service = MultiProviderService()
        response = await ai_service.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=1500,
            temperature=0.4,
        )
        text = (response.message or "").strip().replace("—", "-").replace("–", "-")
        if not text:
            raise HTTPException(status_code=502, detail="The model returned no text. Please try again.")
        return AnalyseArticleResponse(
            analysis=text,
            ai_provider=response.provider,
            ai_model=response.model,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analysing article: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to analyse article: {str(e)}",
        )
