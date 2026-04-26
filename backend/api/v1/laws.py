"""
/api/v1/laws — EU legislation from the eu_laws corpus (28,500+ laws).

Wraps the TSVECTOR-backed eu_laws table with canonical filters:
    celex, doc_type, policy_area, q (full-text), published_from, published_to.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.eu_law import EULaw
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/laws", tags=["v1-laws"])


class LawItem(BaseModel):
    celex: Optional[str] = None
    title: Optional[str] = None
    doc_type: Optional[str] = None
    adopted_on: Optional[date] = Field(None, description="Adoption / publication date")
    oj_reference: Optional[str] = None
    policy_area: Optional[str] = None
    legal_basis: list = Field(default_factory=list)
    eurlex_url: Optional[str] = None


def _eurlex_url(celex: Optional[str]) -> Optional[str]:
    if not celex:
        return None
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


@router.get(
    "",
    response_model=PaginatedResponse[LawItem],
    summary="Search adopted EU legislation",
    description=(
        "Full-text search across 28,500+ adopted EU laws. Filters by CELEX, doc type, "
        "policy area, and publication-date range. Powered by PostgreSQL TSVECTOR."
    ),
)
async def list_laws(
    request: Request,
    q: Optional[str] = Query(None, description="Full-text search (title + subject matter)"),
    celex: Optional[str] = Query(None, description="Exact CELEX filter"),
    doc_type: Optional[str] = Query(None, description="Document type (Regulation, Directive, Decision, ...)"),
    policy_area: Optional[str] = Query(None, description="Policy area slug"),
    published_from: Optional[date] = Query(None, description="Lower bound — laws with adoption date >= value (YYYY-MM-DD)"),
    published_to: Optional[date] = Query(None, description="Upper bound — laws with adoption date <= value (YYYY-MM-DD). Preferred name."),
    published_end: Optional[date] = Query(None, description="Alias of published_to for GovClipping compatibility. If both are sent with different values, returns 422."),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync lower bound — rows with updated_at >= value. Returns rows ordered by updated_at desc when set."),
    updated_to: Optional[datetime] = Query(None, description="Incremental sync upper bound — rows with updated_at <= value."),
    updated_end: Optional[datetime] = Query(None, description="Alias of updated_to (GovClipping-compatible). 422 if both differ."),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LawItem]:
    # published_end is an alias of published_to (GovClipping-compatible).
    # If both are passed with different values, reject with 422.
    if published_end and published_to and published_end != published_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Conflicting upper-bound parameters: published_to={published_to} and published_end={published_end}. They are aliases of the same bound; pass only one, or pass matching values.",
                "reason_code": "conflicting_params",
            },
        )
    if published_end and not published_to:
        published_to = published_end

    if published_from and published_to and published_from > published_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Invalid date range: published_from={published_from} is after published_to={published_to}.",
                "reason_code": "invalid_date_range",
            },
        )

    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
                "reason_code": "conflicting_params",
            },
        )
    if updated_end and not updated_to:
        updated_to = updated_end
    if updated_from and updated_to and updated_from > updated_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Invalid date range: updated_from={updated_from} is after updated_to={updated_to}.",
                "reason_code": "invalid_date_range",
            },
        )

    query = db.query(EULaw)

    filters = []
    if celex:
        filters.append(EULaw.celex == celex.upper())
    if doc_type:
        filters.append(func.lower(EULaw.doc_type_normalized) == doc_type.lower())
    if policy_area:
        filters.append(EULaw.policy_area == policy_area)
    if published_from:
        filters.append(EULaw.date >= published_from)
    if published_to:
        filters.append(EULaw.date <= published_to)
    if updated_from:
        filters.append(EULaw.updated_at >= updated_from)
    if updated_to:
        filters.append(EULaw.updated_at <= updated_to)

    if q:
        # Use search_vector if available, fall back to ILIKE on title
        ts_query = func.plainto_tsquery("english", q)
        filters.append(
            or_(
                EULaw.search_vector.op("@@")(ts_query),
                EULaw.title.ilike(f"%{q}%"),
            )
        )

    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    # When the partner is doing incremental sync, sort by updated_at desc so
    # they see freshly-updated rows first. Otherwise fall back to adoption date.
    if updated_from or updated_to:
        order_col = EULaw.updated_at.desc().nullslast()
    else:
        order_col = EULaw.date.desc().nullslast()
    rows = (
        query.order_by(order_col)
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    data = [
        LawItem(
            celex=r.celex,
            title=r.title,
            doc_type=r.doc_type_normalized or r.doc_type,
            adopted_on=r.date,
            oj_reference=r.oj_reference,
            policy_area=r.policy_area,
            legal_basis=list(r.legal_basis or []),
            eurlex_url=_eurlex_url(r.celex),
        )
        for r in rows
    ]

    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        published_from=published_from,
        published_to=published_to,
        updated_from=updated_from,
        updated_to=updated_to,
    )


@router.get(
    "/{celex}",
    response_model=LawItem,
    summary="EU law metadata detail by CELEX",
    description=(
        "Returns the full metadata for one EU law identified by CELEX. "
        "Companion to /laws/{celex}/text which returns the full body. "
        "Use this when you only need bibliographic fields (title, doc_type, "
        "policy_area, legal_basis, oj_reference, adoption date)."
    ),
)
async def get_law_detail(
    celex: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> LawItem:
    # CELEX can collide across LEG corpus dumps (e.g. an annex or related
    # joint-declaration re-uses the parent's CELEX). Prefer the row whose
    # title starts with the doc_type word ("Regulation"/"Directive"/...) which
    # is the canonical originator, then fall back to lowest id (earliest
    # ingestion = canonical entry in 99% of cases).
    upper_celex = celex.upper()
    candidates = (
        db.query(EULaw)
        .filter(EULaw.celex == upper_celex)
        .order_by(EULaw.id.asc())
        .all()
    )
    r = None
    if candidates:
        # Prefer titles that start with the normalised doc_type
        for cand in candidates:
            dt = (cand.doc_type_normalized or cand.doc_type or "").strip()
            if dt and (cand.title or "").lower().startswith(dt.lower()):
                r = cand
                break
        if r is None:
            r = candidates[0]
    if not r:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"CELEX {celex} not found",
                "reason_code": "not_found",
                "resource": "law",
                "id": celex,
            },
        )
    return LawItem(
        celex=r.celex,
        title=r.title,
        doc_type=r.doc_type_normalized or r.doc_type,
        adopted_on=r.date,
        oj_reference=r.oj_reference,
        policy_area=r.policy_area,
        legal_basis=list(r.legal_basis or []),
        eurlex_url=_eurlex_url(r.celex),
    )


class LawTextResponse(BaseModel):
    celex: str
    title: Optional[str] = None
    doc_type: Optional[str] = None
    adopted_on: Optional[date] = None
    format: str = Field(..., description="xml | plain")
    content: str
    content_length: int
    eurlex_url: Optional[str] = None


@router.get(
    "/{celex}/text",
    response_model=LawTextResponse,
    summary="Full text of a specific EU law",
    description=(
        "Returns the full text of an adopted EU law by CELEX identifier. "
        "Tries local Formex XML cache first; falls back to EUR-Lex Cellar API "
        "(publications.europa.eu/resource/celex/{celex}). "
        "Default format is 'plain' (whitespace-normalised); pass ?format=xml for raw markup."
    ),
)
async def get_law_text(
    celex: str,
    format: str = Query("plain", pattern="^(plain|xml)$"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> LawTextResponse:
    from pathlib import Path
    import re

    row = db.query(EULaw).filter(EULaw.celex == celex.upper()).first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"CELEX {celex} not found", "reason_code": "not_found", "resource": "law", "id": celex},
        )

    xml_path = row.xml_path or ""
    raw = ""
    # Prefer local LEG corpus if deployed
    if xml_path:
        repo_root = Path(__file__).resolve().parents[3]
        full_path = repo_root / xml_path
        if full_path.exists():
            raw = full_path.read_text(encoding="utf-8", errors="ignore")

    # Fallback to EUR-Lex Cellar API (works on prod where LEG XML isn't shipped)
    if not raw:
        import httpx
        cellar_url = f"https://publications.europa.eu/resource/celex/{row.celex}"
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as hc:
                resp = await hc.get(cellar_url, headers={"Accept": "application/xhtml+xml, text/html", "Accept-Language": "eng"})
                if resp.status_code == 200 and resp.text:
                    raw = resp.text
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Cellar fetch failed for {row.celex}: {exc}")

    if not raw:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Text unavailable for CELEX {celex}", "reason_code": "text_unavailable", "resource": "law", "id": celex},
        )
    if format == "plain":
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
    else:
        text = raw

    return LawTextResponse(
        celex=row.celex,
        title=row.title,
        doc_type=row.doc_type_normalized or row.doc_type,
        adopted_on=row.date,
        format=format,
        content=text,
        content_length=len(text),
        eurlex_url=_eurlex_url(row.celex),
    )
