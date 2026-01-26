"""
Document Generation API

API endpoints for generating EU advocacy documents.
Priority #3: Position Paper Generator
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from api.auth_optional import get_current_user_dev as get_current_user
from models.user import User
from models.user_document import UserDocument
from schemas.document_generation import (
    GeneratePositionPaperRequest,
    GenerateMEPBriefingRequest,
    GenerateTalkingPointsRequest,
    GeneratedDocument,
    ExportDocumentRequest,
)
from services.ai.document_generator import get_document_generator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["Document Generation"])


@router.post("/position-paper", response_model=GeneratedDocument)
async def generate_position_paper(
    request: GeneratePositionPaperRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """
    Generate a position paper for EU advocacy.

    Takes organisation details, position stance, and key asks to generate
    a professional position paper following EU advocacy conventions.
    """
    try:
        logger.info(f"User {current_user.id} generating position paper for: {request.legislation_title}")

        # Get legislative context if file ID provided
        legislative_context = None
        if request.legislative_file_id:
            # TODO: Fetch from legislative tracker
            pass

        # Generate document
        generator = get_document_generator()
        document = await generator.generate_position_paper(
            request=request,
            legislative_context=legislative_context
        )

        # Optionally save to user documents
        user_doc = UserDocument(
            user_id=current_user.id,
            document_type="strategy",  # Position papers are strategy docs
            title=document.title,
            content=document.content,
            procedure_reference=request.procedure_reference,
            celex_number=request.celex_number,
            policy_areas=[],  # Could extract from legislation
            tags=["position_paper", "generated"],
            doc_metadata={
                "generated": True,
                "generator_version": "1.0",
                "position": request.position,
                "key_asks": [ask.summary for ask in request.key_asks],
                "organisation_type": request.organisation_type,
                "tone": request.tone,
            }
        )
        db.add(user_doc)
        db.commit()

        logger.info(f"Position paper generated and saved: {user_doc.id}")

        return JSONResponse(
            status_code=200,
            content={
                "document_type": document.document_type,
                "title": document.title,
                "content": document.content,
                "sections": document.sections,
                "word_count": document.word_count,
                "language": document.language,
                "document_id": str(user_doc.id),
                "editable_sections": document.editable_sections,
            }
        )

    except Exception as e:
        logger.error(f"Error generating position paper: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mep-briefing", response_model=GeneratedDocument)
async def generate_mep_briefing(
    request: GenerateMEPBriefingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """
    Generate an MEP briefing note.

    Creates a concise, targeted briefing note for engaging with
    a specific Member of the European Parliament.
    """
    try:
        logger.info(f"User {current_user.id} generating MEP briefing for: {request.mep_name}")

        generator = get_document_generator()
        document = await generator.generate_mep_briefing(request=request)

        # Save to user documents
        user_doc = UserDocument(
            user_id=current_user.id,
            document_type="note",
            title=document.title,
            content=document.content,
            procedure_reference=request.procedure_reference,
            policy_areas=[],
            tags=["mep_briefing", "generated", request.mep_name.lower().replace(" ", "_")],
            doc_metadata={
                "generated": True,
                "generator_version": "1.0",
                "mep_name": request.mep_name,
                "political_group": request.political_group,
                "the_ask": request.the_ask,
            }
        )
        db.add(user_doc)
        db.commit()

        logger.info(f"MEP briefing generated and saved: {user_doc.id}")

        return JSONResponse(
            status_code=200,
            content={
                "document_type": document.document_type,
                "title": document.title,
                "content": document.content,
                "sections": document.sections,
                "word_count": document.word_count,
                "language": document.language,
                "document_id": str(user_doc.id),
                "editable_sections": document.editable_sections,
            }
        )

    except Exception as e:
        logger.error(f"Error generating MEP briefing: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/talking-points", response_model=GeneratedDocument)
async def generate_talking_points(
    request: GenerateTalkingPointsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """
    Generate talking points for a meeting.

    Creates structured talking points, Q&A preparation, and
    key messages for advocacy meetings.
    """
    try:
        logger.info(f"User {current_user.id} generating talking points for: {request.meeting_with}")

        generator = get_document_generator()
        document = await generator.generate_talking_points(request=request)

        # Save to user documents
        user_doc = UserDocument(
            user_id=current_user.id,
            document_type="note",
            title=document.title,
            content=document.content,
            procedure_reference=request.procedure_reference,
            policy_areas=[],
            tags=["talking_points", "generated", "meeting"],
            doc_metadata={
                "generated": True,
                "generator_version": "1.0",
                "meeting_with": request.meeting_with,
                "meeting_institution": request.meeting_institution,
                "meeting_purpose": request.meeting_purpose,
            }
        )
        db.add(user_doc)
        db.commit()

        logger.info(f"Talking points generated and saved: {user_doc.id}")

        return JSONResponse(
            status_code=200,
            content={
                "document_type": document.document_type,
                "title": document.title,
                "content": document.content,
                "sections": document.sections,
                "word_count": document.word_count,
                "language": document.language,
                "document_id": str(user_doc.id),
                "editable_sections": document.editable_sections,
            }
        )

    except Exception as e:
        logger.error(f"Error generating talking points: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_document(
    request: ExportDocumentRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Export a generated document to Word or PDF format.

    Currently supports DOCX export. PDF support coming soon.
    """
    try:
        logger.info(f"User {current_user.id} exporting document: {request.document_title}")

        if request.export_format == "pdf":
            raise HTTPException(
                status_code=501,
                detail="PDF export not yet implemented. Please use DOCX format."
            )

        # TODO: Implement DOCX export using python-docx
        # For now, return the markdown content
        raise HTTPException(
            status_code=501,
            detail="Document export feature coming soon. Please copy the content manually."
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
