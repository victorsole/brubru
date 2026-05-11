"""
/api/v1/commission-register-documents — Commission Document Register surface.

Exposes the existing commission_documents table (528 rows: 246 OJ, 151 COM,
116 SWD, 15 JOIN). Returns raw PDF URLs where available + portal_url +
source_url for partners who want the actual PDF asset, not just the landing
page.

Source: ec.europa.eu/transparency/documents-register/
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.commission_document import CommissionDocument
from models.user import User

from ._body import (
    DEFAULT_HAS_BODY_THRESHOLD,
    body_from_pdf_text,
    body_threshold_param,
    deprecated_body,
)
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/commission-register-documents", tags=["v1-commission-register"])


class CommissionRegisterItem(BaseModel):
    id: str
    reference: str
    title: str
    doc_type: str
    document_register_category: Optional[str] = None  # AGENDA_COM_MEETING / TENTAT_AGENDA_COM_MEETING / PV / OPIN_IMPACT_ASSESS / OJ
    dg_responsible: Optional[str] = None
    procedure_ref: Optional[str] = None
    celex: Optional[str] = None
    common_name: Optional[str] = None
    languages: list = Field(default_factory=list)

    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(
        None,
        description=(
            "Canonical citizen-facing URL. Fallback chain: portal_url → "
            "EUR-Lex citizen URL derived from CELEX → source_url → pdf_url."
        ),
    )
    body_txt: Optional[str] = Field(
        None,
        description="Plain-text body of the document (extracted from PDF or Cellar XHTML).",
    )
    body_html: Optional[str] = Field(
        None,
        description=(
            "HTML body (Cellar XHTML manifestation, EN). Null for PDF-only "
            "acts where Cellar has no XHTML representation."
        ),
    )
    document_date: Optional[date] = Field(
        None,
        description="The document's adoption / publication date.",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru first ingested this row (first_seen).",
    )

    # Legacy / kept-for-compat fields (still useful for partners)
    portal_url: Optional[str] = None  # Landing page (EUR-Lex or RegDoc)
    pdf_url: Optional[str] = None     # Direct PDF asset (when available)
    source_url: Optional[str] = None  # Commission Transparency Register origin
    publication_date: Optional[datetime] = None  # Deprecated alias of document_date — kept one release
    last_updated: Optional[datetime] = None
    has_body: bool = False
    body: Optional[str] = None  # Deprecated alias kept one release


_EURLEX_PUBLIC_URL = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def _derive_public_url(r: CommissionDocument) -> Optional[str]:
    """Canonical citizen-facing URL fallback chain."""
    if r.portal_url:
        return r.portal_url
    if r.celex:
        return _EURLEX_PUBLIC_URL.format(celex=r.celex)
    if r.source_url:
        return r.source_url
    if r.pdf_url:
        return r.pdf_url
    return None


def _row_to_item(
    r: CommissionDocument,
    body_threshold: int = DEFAULT_HAS_BODY_THRESHOLD,
) -> CommissionRegisterItem:
    # Derive a fallback PDF URL via EUR-Lex's PDF endpoint — it returns 202
    # while building the PDF then 200 on retry. Valid for any adopted CELEX.
    pdf = r.pdf_url
    if pdf is None and r.celex:
        pdf = f"https://eur-lex.europa.eu/legal-content/EN/TXT/PDF/?uri=CELEX:{r.celex}"
    # body_html now sourced from the new column (Cellar XHTML manifestation)
    # rather than being forced to None. body_text comes from the existing
    # text_body column.
    body_html_value = getattr(r, "body_html", None)
    body_text_value = r.text_body
    has_body = bool(
        (body_text_value and len(body_text_value) >= body_threshold)
        or (body_html_value and len(body_html_value) >= body_threshold)
    )
    # publication_date is a datetime; convert to date for document_date
    doc_date = None
    if r.publication_date:
        doc_date = r.publication_date.date() if hasattr(r.publication_date, "date") else r.publication_date
    return CommissionRegisterItem(
        id=str(r.id),
        reference=r.reference,
        title=r.title,
        doc_type=r.doc_type.value if hasattr(r.doc_type, "value") else str(r.doc_type),
        document_register_category=r.document_register_category,
        dg_responsible=r.dg_responsible,
        procedure_ref=r.procedure_ref,
        celex=r.celex,
        common_name=r.common_name,
        languages=list(r.languages or []),
        # The 5 mandatory datapoints
        public_url=_derive_public_url(r),
        body_txt=body_text_value,
        body_html=body_html_value,
        document_date=doc_date,
        creation_date=r.first_seen,
        # Kept fields
        portal_url=r.portal_url,
        pdf_url=pdf,
        source_url=r.source_url,
        publication_date=r.publication_date,
        last_updated=r.last_updated,
        has_body=has_body,
        body=deprecated_body(body_text_value, body_html_value),
    )


@router.get(
    "",
    response_model=PaginatedResponse[CommissionRegisterItem],
    summary="Commission Document Register (COM, SWD, OJ, PV, agendas, opinions)",
    description=(
        "All documents from the Commission Transparency Register, including "
        "College of Commissioners agendas (AGENDA_COM_MEETING), tentative "
        "agendas (TENTAT_AGENDA_COM_MEETING), College minutes (PV), RSB "
        "opinions on impact assessments, and the underlying COM/SWD/JOIN "
        "files. Each row exposes the direct PDF URL where available, "
        "falling back to the Cellar resolver for adopted acts with a CELEX "
        "(returns the canonical EN PDF)."
    ),
)
async def list_commission_register_documents(
    request: Request,
    q: Optional[str] = Query(None, description="Substring on title + reference"),
    doc_type: Optional[str] = Query(None, description="COM | SWD | SEC | C | JOIN | OJ | PV"),
    document_register_category: Optional[str] = Query(None, description="AGENDA_COM_MEETING | TENTAT_AGENDA_COM_MEETING | PV | OPIN_IMPACT_ASSESS | IMPACT_ASSESS | OJ"),
    dg_responsible: Optional[str] = Query(None),
    procedure_ref: Optional[str] = Query(None),
    celex: Optional[str] = Query(None),
    has_pdf: Optional[bool] = Query(None, description="If true, only rows with a PDF URL"),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    published_end: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CommissionRegisterItem]:
    if published_end and published_to and published_end != published_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: published_to={published_to} and published_end={published_end}.",
            "reason_code": "conflicting_params",
        })
    if published_end and not published_to:
        published_to = published_end
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
            "reason_code": "conflicting_params",
        })
    if updated_end and not updated_to:
        updated_to = updated_end

    query = db.query(CommissionDocument)
    filters = []
    if doc_type:
        filters.append(CommissionDocument.doc_type == doc_type.upper())
    if document_register_category:
        filters.append(CommissionDocument.document_register_category == document_register_category.upper())
    if dg_responsible:
        filters.append(CommissionDocument.dg_responsible == dg_responsible.upper())
    if procedure_ref:
        filters.append(CommissionDocument.procedure_ref == procedure_ref)
    if celex:
        filters.append(CommissionDocument.celex == celex.upper())
    if has_pdf is True:
        filters.append(or_(CommissionDocument.pdf_url.isnot(None), CommissionDocument.celex.isnot(None)))
    elif has_pdf is False:
        filters.append(and_(CommissionDocument.pdf_url.is_(None), CommissionDocument.celex.is_(None)))
    if published_from:
        filters.append(CommissionDocument.publication_date >= published_from)
    if published_to:
        filters.append(CommissionDocument.publication_date <= datetime.combine(published_to, datetime.max.time()))
    if updated_from:
        filters.append(CommissionDocument.last_updated >= updated_from)
    if updated_to:
        filters.append(CommissionDocument.last_updated <= updated_to)
    if q:
        like = f"%{q}%"
        filters.append(or_(
            CommissionDocument.title.ilike(like),
            CommissionDocument.reference.ilike(like),
        ))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    if updated_from or updated_to:
        order_col = CommissionDocument.last_updated.desc().nullslast()
    else:
        order_col = CommissionDocument.publication_date.desc().nullslast()
    rows = query.order_by(order_col).offset((page - 1) * limit).limit(limit).all()

    return build_envelope(
        [_row_to_item(r, body_threshold=body_threshold) for r in rows],
        total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
    )


@router.get(
    "/{reference:path}",
    response_model=CommissionRegisterItem,
    summary="Single Commission document by reference (e.g. COM(2025) 87)",
)
async def get_commission_register_detail(
    reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CommissionRegisterItem:
    r = db.query(CommissionDocument).filter(CommissionDocument.reference == reference).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Commission document {reference} not found",
            "reason_code": "not_found",
            "resource": "commission_document",
            "id": reference,
        })
    return _row_to_item(r, body_threshold=body_threshold)
