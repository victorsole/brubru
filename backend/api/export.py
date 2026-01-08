"""
Data Export API Endpoints

Provides REST API for exporting user data in various formats.
Part of My EU Bubble - Phase 5: Advanced Features
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
import json

from ..core.database import get_db
from ..models.user import User
from .auth_optional import get_current_user_dev as get_current_user
from ..services.export_service import ExportService

router = APIRouter(prefix="/api/export", tags=["Data Export"])


@router.get("/documents/csv")
async def export_documents_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export all user documents as CSV file.

    Returns CSV file with document metadata and content previews.
    """
    service = ExportService(db)

    try:
        csv_content = service.export_documents_csv(str(current_user.id))

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=brubru_documents.csv"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export documents: {str(e)}"
        )


@router.get("/reading-list/csv")
async def export_reading_list_csv(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export user reading history as CSV file.

    Returns CSV file with reading activity and engagement metrics.
    """
    service = ExportService(db)

    try:
        csv_content = service.export_reading_list_csv(str(current_user.id))

        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=brubru_reading_list.csv"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export reading list: {str(e)}"
        )


@router.get("/analytics/json")
async def export_analytics_json(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export user analytics data as JSON file.

    Returns JSON file with statistics and insights.
    """
    service = ExportService(db)

    try:
        analytics_data = service.export_analytics_json(str(current_user.id))

        json_content = json.dumps(analytics_data, indent=2)

        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=brubru_analytics.json"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export analytics: {str(e)}"
        )


@router.get("/full-data/json")
async def export_full_data_json(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export all user data as comprehensive JSON file.

    Includes:
    - All documents with full content
    - Complete reading history
    - Saved entries
    - Analytics data

    This is a complete data export for backup or migration purposes.
    """
    service = ExportService(db)

    try:
        full_data = service.export_full_data_json(str(current_user.id))

        json_content = json.dumps(full_data, indent=2)

        return Response(
            content=json_content,
            media_type="application/json",
            headers={
                "Content-Disposition": "attachment; filename=brubru_full_export.json"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export full data: {str(e)}"
        )


@router.get("/documents/text")
async def export_documents_text(
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Export document content as plain text file.

    Optionally filter by document type (amendment, analysis, strategy, note).
    """
    service = ExportService(db)

    try:
        text_content = service.export_documents_text(
            str(current_user.id),
            document_type=document_type
        )

        filename = f"brubru_documents_{document_type}.txt" if document_type else "brubru_documents.txt"

        return Response(
            content=text_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export documents as text: {str(e)}"
        )
