"""
Tender Files API  container endpoints for Tender Docs.

Each tender_file groups all user_documents that make up ONE EU funding
application (e.g. one EIC Accelerator submission). The Part B narrative,
pitch deck, video script, FTO note etc. all hang off the same tender_file
via user_documents.tender_file_id.

Endpoints under /api/tender-files:
- POST   /                 create a tender_file (seeds first doc from template)
- GET    /                 list user's tender_files
- GET    /{id}             detail with embedded documents
- PATCH  /{id}             update title / status / funding_mode / deadline
- DELETE /{id}             delete (cascades to user_documents via SET NULL)
- POST   /{id}/documents   add another doc-kind to the file from the template

Shipped 16 Jun 2026 with Tender Docs v1.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from api.auth_optional import get_current_user_dev as get_current_user
from models.user import User
from models.tender_file import TenderFile
from models.user_document import UserDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tender-files", tags=["Tender Docs"])

# Templates live next to KB guides; loaded on-demand + cached.
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "knowledge_base" / "funding_templates"
_TEMPLATE_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_template(template_id: str) -> Dict[str, Any]:
    """Load a template JSON by id. Caches in-process."""
    if template_id in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[template_id]
    path = _TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Funding template '{template_id}' not found",
        )
    with path.open() as fh:
        data = json.load(fh)
    _TEMPLATE_CACHE[template_id] = data
    return data


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TenderFileCreate(BaseModel):
    title: str = Field(..., max_length=500)
    template_id: str = Field(..., description="One of the JSON template ids in knowledge_base/funding_templates/")
    topic_id: Optional[str] = None
    topic_variant: Optional[str] = None
    funding_mode: Optional[str] = Field(None, description="'grant-only' | 'equity-only' | 'blended'")
    deadline_iso: Optional[datetime] = None
    tender_track_id: Optional[UUID] = None
    extra: Optional[Dict[str, Any]] = None
    seed_first_doc: bool = Field(True, description="If true, automatically create the first doc-of-the-file from the template")


class TenderFilePatch(BaseModel):
    title: Optional[str] = Field(None, max_length=500)
    status: Optional[str] = Field(None, description="'drafting' | 'ready-to-submit' | 'submitted' | 'won' | 'lost' | 'seal-of-excellence'")
    funding_mode: Optional[str] = None
    topic_id: Optional[str] = None
    topic_variant: Optional[str] = None
    deadline_iso: Optional[datetime] = None
    extra: Optional[Dict[str, Any]] = None


class DocumentAddRequest(BaseModel):
    kind: str = Field(..., description="Document kind to add from the template (e.g. 'tender_pitch_deck')")


class TenderFileResponse(BaseModel):
    id: str
    title: str
    programme: str
    sub_instrument: Optional[str] = None
    stage: Optional[str] = None
    topic_id: Optional[str] = None
    topic_variant: Optional[str] = None
    funding_mode: Optional[str] = None
    deadline_iso: Optional[str] = None
    status: str
    template_id: str
    scaffold_version: str
    tender_track_id: Optional[str] = None
    extra: Dict[str, Any] = {}
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    documents: Optional[List[Dict[str, Any]]] = None
    template: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_STATUSES = {"drafting", "ready-to-submit", "submitted", "won", "lost", "seal-of-excellence"}
VALID_FUNDING_MODES = {"grant-only", "equity-only", "blended"}


def _make_doc_title(template: Dict[str, Any], file_title: str, doc_kind: str) -> str:
    """Build the in-app title for a doc inside a tender_file."""
    # Find the doc entry in the template
    for doc in template.get("documents", []):
        if doc.get("kind") == doc_kind:
            return f"{file_title}  {doc.get('title', doc_kind)}"
    return f"{file_title}  {doc_kind}"


def _seed_document(
    db: Session,
    user_id: UUID,
    tender_file: TenderFile,
    template: Dict[str, Any],
    doc_spec: Dict[str, Any],
) -> UserDocument:
    """
    Create a user_document row seeded from a template doc spec.
    Tags carry the doc kind + the funding-doc family marker so the
    documents_tab + strategy_docs filters surface it correctly.
    """
    kind = doc_spec.get("kind", "tender_application_full")
    title = _make_doc_title(template, tender_file.title, kind)

    # Initial content is empty; section-by-section AI drafting happens later.
    # We DO seed a minimal markdown skeleton with section headings so the
    # user immediately sees the structure on first open.
    sections_md = []
    for section in doc_spec.get("sections", []) or []:
        sections_md.append(f"## {section.get('label', section.get('id', 'Section'))}")
        for sub in section.get("sub", []) or []:
            sections_md.append(f"### {sub.get('label', sub.get('id', 'Subsection'))}")
            sections_md.append("")  # paragraph placeholder
    content_skeleton = "\n\n".join(sections_md) if sections_md else ""

    doc = UserDocument(
        user_id=user_id,
        document_type="note",
        title=title,
        content=content_skeleton,
        celex_number=None,
        procedure_reference=tender_file.topic_id,
        tags=[kind, "funding_doc", "tender_doc"],
        doc_metadata={
            "kind_family": "funding",
            "programme": tender_file.programme,
            "sub_instrument": tender_file.sub_instrument,
            "stage": tender_file.stage,
            "topic_id": tender_file.topic_id,
            "funding_mode": tender_file.funding_mode,
            "template_id": tender_file.template_id,
            "scaffold_version": tender_file.scaffold_version,
            "doc_kind": kind,
            "ai_disclosure_required": bool(doc_spec.get("ai_disclosure_required")),
            "page_limit": doc_spec.get("page_limit"),
            "render": doc_spec.get("render", "ai-narrative"),
        },
        include_in_ai_context=False,
    )
    doc.tender_file_id = tender_file.id
    db.add(doc)
    db.flush()
    return doc


def _embed_documents(db: Session, tender_file: TenderFile) -> List[Dict[str, Any]]:
    """Fetch all user_documents attached to a tender_file."""
    rows = db.query(UserDocument).filter(
        UserDocument.tender_file_id == tender_file.id
    ).order_by(UserDocument.created_at.asc()).all()
    return [
        {
            "id": str(r.id),
            "document_type": r.document_type,
            "title": r.title,
            "tags": r.tags or [],
            "doc_metadata": r.doc_metadata or {},
            "word_count": r.word_count,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=TenderFileResponse,
    summary="Create a new Tender File",
    description=(
        "**What it does**\n"
        "Creates a tender_file container row + (optionally) seeds the first "
        "document from the chosen funding template. The first doc gets a "
        "markdown skeleton mirroring the template's section structure so the "
        "user lands inside a guided draft rather than a blank page.\n\n"
        "**When to use it**\n"
        "When a user clicks 'Start a Tender Doc' on the Tenderator surface, "
        "or when Chat hands off via deep-link.\n\n"
        "**Input**\n"
        "title, template_id (required), funding_mode + topic_id + deadline optional.\n\n"
        "**You get back**\n"
        "The tender_file row + the seeded document (if seed_first_doc=true)."
    ),
)
async def create_tender_file(
    payload: TenderFileCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a tender_file + seed its first doc."""
    if payload.funding_mode and payload.funding_mode not in VALID_FUNDING_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"funding_mode must be one of {sorted(VALID_FUNDING_MODES)}",
        )

    template = _load_template(payload.template_id)

    tf = TenderFile(
        user_id=current_user.id,
        title=payload.title.strip(),
        programme=template.get("programme") or "EIC",
        sub_instrument=template.get("sub_instrument"),
        stage=template.get("stage"),
        topic_id=payload.topic_id or template.get("topic_id_default"),
        topic_variant=payload.topic_variant,
        funding_mode=payload.funding_mode or template.get("funding_mode_default"),
        deadline_iso=payload.deadline_iso,
        status="drafting",
        template_id=payload.template_id,
        scaffold_version=template.get("scaffold_version", "unknown"),
        tender_track_id=payload.tender_track_id,
        extra=payload.extra or {},
    )
    db.add(tf)
    db.flush()  # so tf.id is populated

    seeded_doc_ids: List[str] = []
    if payload.seed_first_doc:
        docs = template.get("documents", [])
        if docs:
            # Seed the FIRST doc (typically the Part B narrative). The user
            # can add additional docs from the file editor via POST /{id}/documents.
            seeded = _seed_document(db, current_user.id, tf, template, docs[0])
            seeded_doc_ids.append(str(seeded.id))

    db.commit()
    db.refresh(tf)

    response = TenderFileResponse(**tf.to_dict())
    response.documents = _embed_documents(db, tf)
    response.template = template
    logger.info(
        "[TenderFiles] Created %s template=%s programme=%s user=%s seeded_docs=%d",
        tf.id, payload.template_id, tf.programme, current_user.id, len(seeded_doc_ids),
    )
    return response


@router.get(
    "/",
    response_model=List[TenderFileResponse],
    summary="List my Tender Files",
)
async def list_tender_files(
    programme: Optional[str] = None,
    sub_instrument: Optional[str] = None,
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tender_files for the current user with optional filters."""
    qry = db.query(TenderFile).filter(TenderFile.user_id == current_user.id)
    if programme:
        qry = qry.filter(TenderFile.programme == programme)
    if sub_instrument:
        qry = qry.filter(TenderFile.sub_instrument == sub_instrument)
    if status_filter:
        qry = qry.filter(TenderFile.status == status_filter)
    rows = qry.order_by(TenderFile.updated_at.desc()).all()

    out: List[TenderFileResponse] = []
    for tf in rows:
        # For list view we embed the doc count + last doc title only (lightweight)
        doc_count = db.query(UserDocument).filter(
            UserDocument.tender_file_id == tf.id
        ).count()
        resp = TenderFileResponse(**tf.to_dict())
        resp.documents = []  # not embedded in list
        resp.extra = {**(resp.extra or {}), "doc_count": doc_count}
        out.append(resp)
    return out


@router.get(
    "/{file_id}",
    response_model=TenderFileResponse,
    summary="Get a Tender File with embedded documents + template",
)
async def get_tender_file(
    file_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tf = db.query(TenderFile).filter(
        TenderFile.id == file_id, TenderFile.user_id == current_user.id
    ).first()
    if not tf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender file not found")
    template = _load_template(tf.template_id)
    response = TenderFileResponse(**tf.to_dict())
    response.documents = _embed_documents(db, tf)
    response.template = template
    return response


@router.patch(
    "/{file_id}",
    response_model=TenderFileResponse,
    summary="Update a Tender File (title / status / funding_mode / deadline / topic)",
)
async def patch_tender_file(
    file_id: UUID,
    patch: TenderFilePatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tf = db.query(TenderFile).filter(
        TenderFile.id == file_id, TenderFile.user_id == current_user.id
    ).first()
    if not tf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender file not found")

    if patch.status is not None and patch.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"status must be one of {sorted(VALID_STATUSES)}",
        )
    if patch.funding_mode is not None and patch.funding_mode not in VALID_FUNDING_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"funding_mode must be one of {sorted(VALID_FUNDING_MODES)}",
        )

    if patch.title is not None:
        tf.title = patch.title.strip()
    if patch.status is not None:
        tf.status = patch.status
    if patch.funding_mode is not None:
        tf.funding_mode = patch.funding_mode
    if patch.topic_id is not None:
        tf.topic_id = patch.topic_id
    if patch.topic_variant is not None:
        tf.topic_variant = patch.topic_variant
    if patch.deadline_iso is not None:
        tf.deadline_iso = patch.deadline_iso
    if patch.extra is not None:
        tf.extra = {**(tf.extra or {}), **patch.extra}

    db.commit()
    db.refresh(tf)

    response = TenderFileResponse(**tf.to_dict())
    response.documents = _embed_documents(db, tf)
    response.template = _load_template(tf.template_id)
    return response


@router.delete(
    "/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a Tender File (its docs are detached, not deleted)",
)
async def delete_tender_file(
    file_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tf = db.query(TenderFile).filter(
        TenderFile.id == file_id, TenderFile.user_id == current_user.id
    ).first()
    if not tf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender file not found")
    db.delete(tf)
    db.commit()
    return None


@router.post(
    "/{file_id}/documents",
    summary="Attach an additional document kind to a Tender File from its template",
)
async def add_document_to_file(
    file_id: UUID,
    payload: DocumentAddRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    tf = db.query(TenderFile).filter(
        TenderFile.id == file_id, TenderFile.user_id == current_user.id
    ).first()
    if not tf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tender file not found")

    template = _load_template(tf.template_id)
    doc_spec = next(
        (d for d in template.get("documents", []) if d.get("kind") == payload.kind),
        None,
    )
    if not doc_spec:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Template '{tf.template_id}' has no doc kind '{payload.kind}'",
        )

    seeded = _seed_document(db, current_user.id, tf, template, doc_spec)
    db.commit()
    db.refresh(seeded)
    return {
        "id": str(seeded.id),
        "title": seeded.title,
        "tags": seeded.tags or [],
        "doc_metadata": seeded.doc_metadata or {},
        "created_at": seeded.created_at.isoformat() if seeded.created_at else None,
    }
