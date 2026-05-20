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
    GenerateResolutionRequest,
    GenerateEPQuestionRequest,
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


@router.post("/resolution", response_model=GeneratedDocument)
async def generate_resolution(
    request: GenerateResolutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """
    Generate a European Parliament Resolution draft.

    Creates a resolution following the exact EP format:
    opening, having regards, whereas recitals, numbered resolution points,
    and closing instruction to the President.
    """
    try:
        logger.info(f"User {current_user.id} generating EP resolution on: {request.topic}")

        generator = get_document_generator()
        document = await generator.generate_resolution(request=request)

        # Save to user documents as note with resolution tags
        user_doc = UserDocument(
            user_id=current_user.id,
            document_type="note",
            title=document.title,
            content=document.content,
            procedure_reference=request.procedure_reference,
            policy_areas=[],
            tags=["resolution", "generated"],
            doc_metadata={
                "generated": True,
                "generator_version": "1.0",
                "topic": request.topic,
                "key_demands": request.key_demands or [],
            }
        )
        db.add(user_doc)
        db.commit()

        logger.info(f"EP resolution generated and saved: {user_doc.id}")

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
        logger.error(f"Error generating EP resolution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ep-question", response_model=GeneratedDocument)
async def generate_ep_question(
    request: GenerateEPQuestionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> JSONResponse:
    """
    Generate a European Parliament written question.

    Creates a written parliamentary question following the exact EP format:
    title, header block, evidence-based context, bridge phrase, and numbered sub-questions.
    """
    try:
        logger.info(f"User {current_user.id} generating EP question on: {request.topic}")

        generator = get_document_generator()
        document = await generator.generate_ep_question(request=request)

        # Save to user documents as ep_question
        user_doc = UserDocument(
            user_id=current_user.id,
            document_type="note",
            title=document.title,
            content=document.content,
            procedure_reference=request.procedure_reference,
            celex_number=request.celex_number,
            policy_areas=[request.policy_area] if request.policy_area else [],
            tags=["ep_question", "generated", request.question_type],
            doc_metadata={
                "generated": True,
                "generator_version": "1.0",
                "document_subtype": "ep_question",
                "topic": request.topic,
                "addressee": request.addressee,
                "question_type": request.question_type,
                "tone": request.tone,
                "num_sub_questions": request.num_sub_questions,
            }
        )
        db.add(user_doc)
        db.commit()

        logger.info(f"EP question generated and saved: {user_doc.id}")

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
        logger.error(f"Error generating EP question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export")
async def export_document(
    request: ExportDocumentRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Export an unsaved markdown draft to DOCX or PDF.

    For documents already persisted in My EU Bubble, use
    GET /api/documents/{id}/export?format=docx|pdf instead.
    """
    from fastapi.responses import StreamingResponse
    import io, re
    from services.document_generation.document_exporter import export_docx, export_pdf

    logger.info(
        f"User {current_user.id} exporting draft '{request.document_title}' as {request.export_format}"
    )

    try:
        if request.export_format == "pdf":
            payload = export_pdf(request.document_title, request.document_content)
            media = "application/pdf"
            ext = "pdf"
        else:
            payload = export_docx(request.document_title, request.document_content)
            media = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = "docx"

        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", request.document_title.strip())[:80] or "document"
        filename = f"{slug}.{ext}"

        return StreamingResponse(
            io.BytesIO(payload),
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
