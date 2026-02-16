"""
User Documents API Router

FastAPI endpoints for managing user documents in My EU Bubble.
Part of My EU Bubble - Phase 2: User Content Repository

Endpoints:
- POST /api/documents - Create document
- GET /api/documents - List user's documents
- GET /api/documents/{id} - Get specific document
- PATCH /api/documents/{id} - Update document
- DELETE /api/documents/{id} - Delete document
- POST /api/documents/{id}/version - Create new version
- GET /api/documents/{id}/versions - Get document versions
- GET /api/documents/stats - Get document statistics
"""

import logging
from typing import List, Optional
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func

from models.user import User
from models.user_document import UserDocument
from models.amendment import Amendment
from schemas.user_document_schemas import (
    UserDocumentCreate,
    UserDocumentUpdate,
    UserDocumentResponse,
    UserDocumentListResponse,
    DocumentFilterParams,
    DocumentStatsResponse,
    DocumentVersionResponse,
    AmendmentCreate,
    AnalysisCreate,
    StrategyCreate,
    NoteCreate,
)
from core.database import get_db
from api.auth_optional import get_current_user_dev as get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/documents",
    tags=["User Documents"],
    responses={404: {"description": "Not found"}}
)


# ============================================================================
# Document CRUD Operations
# ============================================================================

@router.post(
    "",
    response_model=UserDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create document",
    description="Create a new document (amendment, analysis, strategy, or note)"
)
async def create_document(
    document: UserDocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserDocumentResponse:
    """
    Create a new user document.

    Automatically extracts policy areas from content if not provided.
    """
    try:
        # Create document
        new_doc = UserDocument(
            user_id=current_user.id,
            document_type=document.document_type,
            title=document.title,
            content=document.content,
            celex_number=document.celex_number,
            procedure_reference=document.procedure_reference,
            policy_areas=document.policy_areas,
            tags=document.tags,
            is_private=document.is_private,
            # Type-specific fields
            amendment_target=document.amendment_target if hasattr(document, 'amendment_target') else None,
            amendment_justification=document.amendment_justification if hasattr(document, 'amendment_justification') else None,
            amendment_status=document.amendment_status if hasattr(document, 'amendment_status') else None,
            executive_summary=document.executive_summary if hasattr(document, 'executive_summary') else None,
            methodology=document.methodology if hasattr(document, 'methodology') else None,
            conclusions=document.conclusions if hasattr(document, 'conclusions') else None,
            recommendations=document.recommendations if hasattr(document, 'recommendations') else None,
            objectives=document.objectives if hasattr(document, 'objectives') else None,
            action_plan=document.action_plan if hasattr(document, 'action_plan') else None,
            timeline=document.timeline if hasattr(document, 'timeline') else None,
            stakeholders=document.stakeholders if hasattr(document, 'stakeholders') else None,
            metadata=document.metadata if hasattr(document, 'metadata') else None,
        )

        db.add(new_doc)
        db.commit()
        db.refresh(new_doc)

        logger.info(f"User {current_user.email} created document: {new_doc.title}")

        # Create response with computed fields
        response = UserDocumentResponse.from_orm(new_doc)
        response.word_count = new_doc.word_count

        return response

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document: {str(e)}"
        )


@router.get(
    "",
    response_model=UserDocumentListResponse,
    summary="List documents",
    description="Get user's documents with filtering and pagination"
)
async def list_documents(
    document_type: Optional[str] = Query(None, description="Filter by type"),
    policy_areas: Optional[List[str]] = Query(None, description="Filter by policy areas"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags"),
    search: Optional[str] = Query(None, max_length=200, description="Search in title and content"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserDocumentListResponse:
    """List user's documents with filters"""
    try:
        # Build query
        query = db.query(UserDocument).filter(UserDocument.user_id == current_user.id)

        # Apply filters
        if document_type:
            query = query.filter(UserDocument.document_type == document_type)

        if policy_areas:
            # Filter documents that have any of the specified policy areas
            for area in policy_areas:
                query = query.filter(UserDocument.policy_areas.contains([area]))

        if tags:
            # Filter documents that have any of the specified tags
            for tag in tags:
                query = query.filter(UserDocument.tags.contains([tag]))

        if search:
            # Search in title and content
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    UserDocument.title.ilike(search_pattern),
                    UserDocument.content.ilike(search_pattern)
                )
            )

        # Order by updated_at
        query = query.order_by(UserDocument.updated_at.desc())

        # Get total count
        total = query.count()

        # Apply pagination
        documents = query.offset(offset).limit(limit).all()

        # Build response with computed fields
        doc_responses = []
        for doc in documents:
            doc_response = UserDocumentResponse.from_orm(doc)
            doc_response.word_count = doc.word_count
            doc_responses.append(doc_response)

        return UserDocumentListResponse(
            documents=doc_responses,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(documents)) < total
        )

    except Exception as e:
        logger.error(f"Failed to list documents: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list documents: {str(e)}"
        )


@router.get(
    "/{document_id}",
    response_model=UserDocumentResponse,
    summary="Get document",
    description="Get specific document by ID"
)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserDocumentResponse:
    """Get specific document"""
    try:
        document = db.query(UserDocument).filter(
            and_(
                UserDocument.id == document_id,
                UserDocument.user_id == current_user.id
            )
        ).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Increment view count
        document.increment_view_count()
        db.commit()

        # Build response
        response = UserDocumentResponse.from_orm(document)
        response.word_count = document.word_count

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get document: {str(e)}"
        )


@router.patch(
    "/{document_id}",
    response_model=UserDocumentResponse,
    summary="Update document",
    description="Update document fields"
)
async def update_document(
    document_id: UUID,
    updates: UserDocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserDocumentResponse:
    """Update document"""
    try:
        document = db.query(UserDocument).filter(
            and_(
                UserDocument.id == document_id,
                UserDocument.user_id == current_user.id
            )
        ).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Update fields
        update_data = updates.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(document, field, value)

        db.commit()
        db.refresh(document)

        logger.info(f"User {current_user.email} updated document: {document.title}")

        # Build response
        response = UserDocumentResponse.from_orm(document)
        response.word_count = document.word_count

        return response

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update document: {str(e)}"
        )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete document",
    description="Delete document permanently"
)
async def delete_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete document"""
    try:
        document = db.query(UserDocument).filter(
            and_(
                UserDocument.id == document_id,
                UserDocument.user_id == current_user.id
            )
        ).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # If uploaded document, also clean up filesystem storage
        if document.document_type == 'uploaded' and document.storage_document_id:
            try:
                from services.storage.document_storage import get_document_storage
                doc_storage = get_document_storage()
                doc_storage.delete_document(document.storage_document_id)
                logger.info(f"Cleaned up filesystem for upload {document.storage_document_id}")
            except Exception as storage_err:
                logger.warning(f"Failed to clean up filesystem storage: {storage_err}")

        db.delete(document)
        db.commit()

        logger.info(f"User {current_user.email} deleted document: {document.title}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete document: {str(e)}"
        )


# ============================================================================
# Version Control
# ============================================================================

@router.post(
    "/{document_id}/version",
    response_model=UserDocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new version",
    description="Create a new version of the document"
)
async def create_document_version(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> UserDocumentResponse:
    """Create new version of document"""
    try:
        document = db.query(UserDocument).filter(
            and_(
                UserDocument.id == document_id,
                UserDocument.user_id == current_user.id
            )
        ).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Create new version
        new_version = document.create_new_version(db)
        db.commit()
        db.refresh(new_version)

        logger.info(f"User {current_user.email} created version {new_version.version} of document: {document.title}")

        # Build response
        response = UserDocumentResponse.from_orm(new_version)
        response.word_count = new_version.word_count

        return response

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to create document version: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create version: {str(e)}"
        )


@router.get(
    "/{document_id}/versions",
    response_model=List[DocumentVersionResponse],
    summary="Get document versions",
    description="Get all versions of a document"
)
async def get_document_versions(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> List[DocumentVersionResponse]:
    """Get all versions of document"""
    try:
        # Get the document
        document = db.query(UserDocument).filter(
            and_(
                UserDocument.id == document_id,
                UserDocument.user_id == current_user.id
            )
        ).first()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found"
            )

        # Get all versions (documents with this parent_document_id or this document itself)
        versions = db.query(UserDocument).filter(
            and_(
                UserDocument.user_id == current_user.id,
                or_(
                    UserDocument.id == document_id,
                    UserDocument.parent_document_id == document_id
                )
            )
        ).order_by(UserDocument.version.asc()).all()

        return [DocumentVersionResponse.from_orm(v) for v in versions]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document versions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get versions: {str(e)}"
        )


# ============================================================================
# Statistics
# ============================================================================

@router.get(
    "/stats/summary",
    response_model=DocumentStatsResponse,
    summary="Get document statistics",
    description="Get statistics about user's documents"
)
async def get_document_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> DocumentStatsResponse:
    """Get document statistics"""
    try:
        # Total documents
        total = db.query(UserDocument).filter(
            UserDocument.user_id == current_user.id
        ).count()

        # By type
        by_type_query = db.query(
            UserDocument.document_type,
            func.count(UserDocument.id).label('count')
        ).filter(
            UserDocument.user_id == current_user.id
        ).group_by(UserDocument.document_type).all()

        by_type = {doc_type: count for doc_type, count in by_type_query}

        # By policy area
        policy_area_query = db.query(
            func.unnest(UserDocument.policy_areas).label('policy_area'),
            func.count().label('count')
        ).filter(
            UserDocument.user_id == current_user.id
        ).group_by('policy_area').order_by(func.count().desc()).limit(10).all()

        by_policy_area = {area: count for area, count in policy_area_query if area}

        # Total word count
        documents = db.query(UserDocument).filter(
            UserDocument.user_id == current_user.id
        ).all()
        total_words = sum(doc.word_count for doc in documents)

        # Most viewed
        most_viewed = db.query(UserDocument).filter(
            UserDocument.user_id == current_user.id
        ).order_by(UserDocument.view_count.desc()).limit(5).all()

        most_viewed_responses = []
        for doc in most_viewed:
            doc_response = UserDocumentResponse.from_orm(doc)
            doc_response.word_count = doc.word_count
            most_viewed_responses.append(doc_response)

        # Count amendments from the amendments table (not user_document)
        logger.info(f"📊 Getting stats for user: {current_user.email} (ID: {current_user.id})")
        total_amendments = db.query(Amendment).filter(
            Amendment.user_id == current_user.id
        ).count()
        logger.info(f"📊 Found {total_amendments} amendments for user {current_user.email}")

        return DocumentStatsResponse(
            total_documents=total,
            by_type=by_type,
            by_policy_area=by_policy_area,
            total_amendments=total_amendments,
            total_analyses=by_type.get('analysis', 0),
            total_strategies=by_type.get('strategy', 0),
            total_notes=by_type.get('note', 0),
            total_uploaded=by_type.get('uploaded', 0),
            total_word_count=total_words,
            most_viewed_documents=most_viewed_responses
        )

    except Exception as e:
        logger.error(f"Failed to get document stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get statistics: {str(e)}"
        )
