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
        linker = get_amendment_linker(db)

        for amendment_data in batch.amendments:
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

        db.commit()

        # Refresh all amendments
        for amendment in created_amendments:
            db.refresh(amendment)

        logger.info(f"Created {len(created_amendments)} amendments for user {current_user.id}")
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
    description="Generate an amendment suggestion based on policy position and selected legislative text"
)
async def suggest_amendment(
    policy_position: str = Query(..., description="User's policy position or goals"),
    original_text: str = Query(..., description="The legislative text to amend"),
    element_type: str = Query(..., description="Type of element: recital, article, point, etc."),
    element_position: str = Query(..., description="Position reference, e.g., 'Recital 1', 'Article 3'"),
    supporting_context: Optional[str] = Query(None, description="Extracted text from supporting documents"),
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
    from services.ai.multi_provider_service import MultiProviderService

    try:
        ai_service = MultiProviderService()

        system_prompt = """You are an expert EU legislative drafter helping to create amendments to EU legislation.

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

        supporting_section = ""
        if supporting_context:
            # Truncate to avoid excessive token usage
            ctx = supporting_context[:3000]
            supporting_section = f"\n\nSupporting Document Context:\n{ctx}\n"

        user_message = f"""Policy Position: {policy_position}
{supporting_section}
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
        import json
        import re

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

        return {
            "amendment_type": suggestion.get("amendment_type", "modification"),
            "original_text": original_text,
            "proposed_text": suggestion.get("proposed_text", response_text),
            "justification": suggestion.get("justification", ""),
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

    The AI will:
    1. Analyse all provided legislative elements
    2. Consider the user's policy position and any supporting document context
    3. Identify the most impactful elements to amend
    4. Return up to max_suggestions amendment suggestions
    """
    from services.ai.multi_provider_service import MultiProviderService
    import json
    import re

    # Determine max_suggestions based on subscription tier
    tier = current_user.subscription_tier or 'white'
    if tier in ('blue', 'admin'):
        # Blue/Admin: unlimited - suggest for as many elements as provided
        tier_max = len(request.elements)
    elif tier == 'yellow':
        tier_max = 15
    else:
        # White tier
        tier_max = 5

    # Use the lower of user-requested and tier-allowed, or tier default if not specified
    max_suggestions = min(request.max_suggestions, tier_max) if request.max_suggestions else tier_max

    try:
        ai_service = MultiProviderService()

        # Build elements summary for the prompt
        elements_text = ""
        for i, elem in enumerate(request.elements):
            elements_text += f"\n{i+1}. {elem.position} ({elem.element_type}):\n{elem.text}\n"

        system_prompt = f"""You are an expert EU legislative drafter. You will analyse a set of legislative elements and suggest the most impactful amendments based on the user's policy position.

IMPORTANT GUIDELINES:
1. Identify the {max_suggestions} most strategically important elements to amend
2. Prioritise articles over recitals (articles have legal force)
3. Keep each amendment focused and minimal - change only what is necessary
4. Use proper EU legislative language and terminology
5. Ensure amendments are legally coherent
6. Each proposed_text should be a MODIFIED version of the original, not entirely new text
7. For suppressions, set proposed_text to empty string ""

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

        supporting_section = ""
        if request.supporting_context:
            ctx = request.supporting_context[:4000]
            supporting_section = f"\n\nSupporting Document Context (user's policy document):\n{ctx}\n"

        user_message = f"""Policy Position: {request.policy_position}
{supporting_section}
Legislative Elements to Analyse:
{elements_text}

Please identify the {max_suggestions} most impactful amendments to align this legislation with the policy position. Return your suggestions as a JSON array."""

        response = await ai_service.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=4000,
            temperature=0.7
        )

        # Parse the JSON response
        response_text = response.message.strip()

        # Extract JSON from markdown code blocks if present
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response_text)
        if json_match:
            response_text = json_match.group(1)

        # Try to parse JSON array
        try:
            suggestions_raw = json.loads(response_text)
            if not isinstance(suggestions_raw, list):
                suggestions_raw = [suggestions_raw]
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse batch suggestion JSON: {response_text[:200]}")
            suggestions_raw = []

        # Build element lookup for original text
        element_lookup = {elem.position: elem.text for elem in request.elements}

        suggestions = []
        for item in suggestions_raw[:max_suggestions]:
            pos = item.get("element_position", "")
            suggestions.append(BatchSuggestionItem(
                element_position=pos,
                amendment_type=item.get("amendment_type", "modification"),
                original_text=item.get("original_text", element_lookup.get(pos, "")),
                proposed_text=item.get("proposed_text", ""),
                justification=item.get("justification", "")
            ))

        return BatchSuggestionResponse(
            suggestions=suggestions,
            ai_provider=response.provider,
            ai_model=response.model
        )

    except Exception as e:
        logger.error(f"Error generating batch amendment suggestions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate amendment suggestions: {str(e)}"
        )
