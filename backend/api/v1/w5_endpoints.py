"""
W5 P2 endpoints: /research-publications (unified), /officials, /tenders.

- /research-publications  — unified EPRS + STOA + JRC + ART + ECA. Backed by
                            eprs_publications today; STOA/JRC/ART/ECA tracked
                            via the `source` filter when ingested.
- /officials              — EU Who is Who registry.
- /tenders                — TED public-procurement notices (existing tenders table).
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.eprs_publication import EPRSPublication
from models.eu_official import EUOfficial
from models.tender import Tender
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

research_router = APIRouter(prefix="/research-publications", tags=["v1-research-publications"])
officials_router = APIRouter(prefix="/officials", tags=["v1-officials"])
tenders_router = APIRouter(prefix="/tenders", tags=["v1-tenders"])


# ============================================================================
# /research-publications — unified EPRS + STOA + JRC + ART + ECA
# ============================================================================


class ResearchPublicationItem(BaseModel):
    id: str
    source: str  # eprs | stoa | jrc | art | eca
    publication_id: Optional[str] = None
    title: str
    publication_type: Optional[str] = None
    publication_date: Optional[datetime] = None
    authors: list = Field(default_factory=list)
    summary: Optional[str] = None
    policy_areas: list = Field(default_factory=list)
    committees: list = Field(default_factory=list)
    related_celex_numbers: list = Field(default_factory=list)
    related_procedures: list = Field(default_factory=list)
    html_url: Optional[str] = None
    pdf_url: Optional[str] = None
    last_updated: Optional[datetime] = None


@research_router.get(
    "",
    response_model=PaginatedResponse[ResearchPublicationItem],
    summary="Unified EU institutional research publications (EPRS + STOA + JRC + ART + ECA)",
    description=(
        "EPRS today, STOA/JRC/ART/ECA queued. The `source` filter selects between "
        "European Parliamentary Research Service (eprs), STOA Panel for the Future "
        "of Science and Technology (stoa), Joint Research Centre (jrc), Council "
        "Analysis and Research Team (art), or European Court of Auditors (eca)."
    ),
)
async def list_research_publications(
    request: Request,
    source: Optional[str] = Query(None, description="eprs | stoa | jrc | art | eca"),
    q: Optional[str] = Query(None),
    publication_type: Optional[str] = Query(None),
    committee: Optional[str] = Query(None),
    procedure_ref: Optional[str] = Query(None),
    celex: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ResearchPublicationItem]:
    # All four sources (eprs, stoa, jrc, art, eca) live in eprs_publications,
    # discriminated by the `source` column (migration 041).
    query = db.query(EPRSPublication)
    filters = []
    if source:
        filters.append(EPRSPublication.source == source.lower())
    if publication_type:
        filters.append(EPRSPublication.publication_type == publication_type.lower())
    if committee:
        filters.append(EPRSPublication.committees.any(committee.upper()))
    if procedure_ref:
        filters.append(EPRSPublication.related_procedures.any(procedure_ref))
    if celex:
        filters.append(EPRSPublication.related_celex_numbers.any(celex.upper()))
    if published_from:
        filters.append(EPRSPublication.publication_date >= published_from)
    if published_to:
        filters.append(EPRSPublication.publication_date <= published_to)
    if updated_from:
        filters.append(EPRSPublication.last_updated >= updated_from)
    if q:
        like = f"%{q}%"
        filters.append(or_(EPRSPublication.title.ilike(like), EPRSPublication.summary.ilike(like)))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(EPRSPublication.publication_date.desc().nullslast())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data = [
        ResearchPublicationItem(
            id=str(r.id), source=getattr(r, "source", "eprs") or "eprs",
            publication_id=r.publication_id, title=r.title,
            publication_type=r.publication_type.value if hasattr(r.publication_type, "value") else (str(r.publication_type) if r.publication_type else None),
            publication_date=r.publication_date,
            authors=list(r.authors or []), summary=r.summary,
            policy_areas=list(r.policy_areas or []), committees=list(r.committees or []),
            related_celex_numbers=list(r.related_celex_numbers or []),
            related_procedures=list(r.related_procedures or []),
            html_url=r.html_url, pdf_url=r.pdf_url, last_updated=r.last_updated,
        )
        for r in rows
    ]
    return build_envelope(data, total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to,
                          updated_from=updated_from)


# ============================================================================
# /officials — EU Who is Who
# ============================================================================


class OfficialItem(BaseModel):
    id: str
    slug: str
    name: str
    title: Optional[str] = None
    role: Optional[str] = None
    institution_slug: str
    dg: Optional[str] = None
    cabinet: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    bio_url: Optional[str] = None
    photo_url: Optional[str] = None
    portfolio: Optional[str] = None
    policy_areas: list = Field(default_factory=list)
    is_active: bool = True
    last_updated: Optional[datetime] = None
    # The 5 mandatory Brubru v1 datapoints. Officials are person records,
    # not documents — public_url is the bio page; body_txt/html are composed
    # from name + title + role + institution + DG + cabinet + portfolio +
    # contact details; document_date is null (people aren't dated);
    # creation_date stamps the API call.
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — the bio page (or Whoiswho profile).")
    body_txt: Optional[str] = Field(None, description="Plain-text composition: name + title + role + institution + DG + cabinet + portfolio + contact details.")
    body_html: Optional[str] = Field(None, description="HTML composition of the same fields. Includes the photo when available.")
    document_date: Optional[date] = Field(None, description="Null — officials are not dated documents.")
    creation_date: Optional[datetime] = Field(None, description="Time of this fetch.")


def _official_public_url(r) -> Optional[str]:
    """Return the citizen URL for an official. Prefer the cached bio_url; fall
    back to a Whoiswho search URL keyed on the name (always lands on a useful
    EU directory page that lists the person). Returns None only when even the
    name is missing — a defensive edge case for noise rows."""
    if r.bio_url:
        return r.bio_url
    if not r.name:
        return None
    from urllib.parse import quote_plus
    return f"https://op.europa.eu/en/web/who-is-who/search?text={quote_plus(r.name)}"


def _compose_official_body(r) -> tuple:
    """Compose body_txt + body_html from an EUOfficial row. No upstream HTTP."""
    import html as _html
    parts_txt: list = []
    parts_html: list = []
    parts_html.append(f"<h2>{_html.escape(r.name or '?')}</h2>")
    if r.photo_url:
        parts_html.append(f'<img src="{_html.escape(r.photo_url)}" alt="Official portrait" />')
    if r.name:
        parts_txt.append(r.name)
    kv = []
    if r.title:
        kv.append(("Title", r.title))
    if r.role:
        kv.append(("Role", r.role))
    if r.institution_slug:
        kv.append(("Institution", r.institution_slug))
    if r.dg:
        kv.append(("Directorate-General", r.dg))
    if r.cabinet:
        kv.append(("Cabinet", r.cabinet))
    if r.portfolio:
        kv.append(("Portfolio", r.portfolio))
    if r.country:
        kv.append(("Country", r.country))
    if r.city:
        kv.append(("City", r.city))
    if r.email:
        kv.append(("Email", r.email))
    if r.phone:
        kv.append(("Phone", r.phone))
    if r.policy_areas:
        kv.append(("Policy areas", ", ".join(r.policy_areas)))
    for k, v in kv:
        parts_txt.append(f"{k}: {v}")
        parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
    body_txt = "\n".join(parts_txt) if parts_txt else None
    body_html = "<article>" + "".join(parts_html) + "</article>" if parts_html else None
    return body_txt, body_html


@officials_router.get(
    "",
    response_model=PaginatedResponse[OfficialItem],
    summary="EU officials registry (Who is Who)",
    description=(
        "Officials registry across institutions: heads of unit, directors, "
        "directors-general, cabinet members, etc. Source: op.europa.eu/en/web/who-is-who. "
        "Scraper queued; endpoint returns empty until ingested."
    ),
)
async def list_officials(
    request: Request,
    institution_slug: Optional[str] = Query(None),
    dg: Optional[str] = Query(None),
    cabinet: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(True),
    q: Optional[str] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[OfficialItem]:
    query = db.query(EUOfficial)
    # Filter out scrape-noise rows. The original Whoiswho JSON-LD scrape
    # picked up several patterns of non-person text:
    #   1. "— Committees Afet, Sede,"  (filter-bar UI label)
    #   2. "(postal office Box: ...)"  (institution header rendered as name)
    #   3. "(NATURE & Circular"        (truncated section heading)
    #   4. "(Έλενα Κουντουρα)"          (alternate-script name shown in
    #                                    parentheses next to the real Latin
    #                                    name; produces duplicate rows for
    #                                    the same person)
    # Hide all of those by default. The underlying rows stay in DB so a
    # future PDF-based re-ingest from the Publications Office Whoiswho
    # PDFs (op.europa.eu/webpub/wiw/pdf/EUWhoiswho_*_EN.pdf) can replace
    # them cleanly.
    filters = [
        ~EUOfficial.name.op("~")(r"^[—–\-]"),
        ~EUOfficial.name.op("~")(r"^[a-z]"),
        # Names starting with "(" are the noise patterns 2/3/4 above.
        ~EUOfficial.name.op("~")(r"^\("),
        # Defensive: explicit "postal office" / "Postal address" matches
        # in case the leading paren is stripped somewhere upstream.
        ~EUOfficial.name.ilike("%postal office%"),
        ~EUOfficial.name.ilike("%Postal address%"),
        func.length(EUOfficial.name) >= 4,
    ]
    if institution_slug:
        filters.append(EUOfficial.institution_slug == institution_slug)
    if dg:
        filters.append(EUOfficial.dg == dg.upper())
    if cabinet:
        filters.append(EUOfficial.cabinet == cabinet)
    if country:
        filters.append(EUOfficial.country == country.upper())
    if is_active is not None:
        filters.append(EUOfficial.is_active == is_active)
    if q:
        like = f"%{q}%"
        filters.append(or_(EUOfficial.name.ilike(like), EUOfficial.role.ilike(like), EUOfficial.title.ilike(like)))
    if updated_from:
        filters.append(EUOfficial.last_updated >= updated_from)
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = query.order_by(EUOfficial.name.asc()).offset((page - 1) * limit).limit(limit).all()
    now = datetime.utcnow()
    data: list = []
    for r in rows:
        body_txt, body_html = _compose_official_body(r)
        data.append(OfficialItem(
            id=str(r.id), slug=r.slug, name=r.name, title=r.title, role=r.role,
            institution_slug=r.institution_slug, dg=r.dg, cabinet=r.cabinet,
            country=r.country, city=r.city, email=r.email, phone=r.phone,
            bio_url=r.bio_url, photo_url=r.photo_url,
            portfolio=r.portfolio, policy_areas=list(r.policy_areas or []),
            is_active=bool(r.is_active), last_updated=r.last_updated,
            # 5 mandatory datapoints
            public_url=_official_public_url(r),
            body_txt=body_txt,
            body_html=body_html,
            creation_date=now,
        ))
    return build_envelope(data, total=total, page=page, limit=limit, updated_from=updated_from)


@officials_router.get("/{slug}", response_model=OfficialItem, summary="Single official by slug")
async def get_official_detail(
    slug: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> OfficialItem:
    r = db.query(EUOfficial).filter(EUOfficial.slug == slug).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Official slug={slug} not found",
            "reason_code": "not_found",
            "resource": "official",
            "id": slug,
        })
    body_txt, body_html = _compose_official_body(r)
    return OfficialItem(
        id=str(r.id), slug=r.slug, name=r.name, title=r.title, role=r.role,
        institution_slug=r.institution_slug, dg=r.dg, cabinet=r.cabinet,
        country=r.country, city=r.city, email=r.email, phone=r.phone,
        bio_url=r.bio_url, photo_url=r.photo_url,
        portfolio=r.portfolio, policy_areas=list(r.policy_areas or []),
        is_active=bool(r.is_active), last_updated=r.last_updated,
        public_url=r.bio_url,
        body_txt=body_txt,
        body_html=body_html,
        creation_date=datetime.utcnow(),
    )


# ============================================================================
# /tenders — TED public procurement
# ============================================================================


class TenderItem(BaseModel):
    id: int
    publication_number: str
    notice_id: Optional[str] = None
    form_type: Optional[str] = None
    title: str
    description: Optional[str] = None
    official_name: Optional[str] = None
    buyer_country: Optional[str] = None
    procedure_type: Optional[str] = None
    cpv_codes: list = Field(default_factory=list)
    cpv_main: Optional[str] = None
    contract_nature: Optional[str] = None
    estimated_value: Optional[float] = None
    estimated_value_currency: str = "EUR"
    publication_date: Optional[datetime] = None
    submission_deadline: Optional[datetime] = None
    has_lots: bool = False
    lot_count: Optional[int] = None
    ted_url: Optional[str] = None
    summary: Optional[str] = None
    sme_suitability_score: Optional[float] = None
    status: Optional[str] = None
    last_synced_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@tenders_router.get(
    "",
    response_model=PaginatedResponse[TenderItem],
    summary="EU public-procurement tenders (TED)",
    description=(
        "Tender notices from Tenders Electronic Daily. Filterable by buyer "
        "country, CPV codes, procedure type, contract nature, value range, "
        "publication and submission dates."
    ),
)
async def list_tenders(
    request: Request,
    q: Optional[str] = Query(None, description="Substring on title + description + summary"),
    buyer_country: Optional[str] = Query(None, description="ISO 3166-1 alpha-2"),
    procedure_type: Optional[str] = Query(None),
    contract_nature: Optional[str] = Query(None, description="works | supplies | services"),
    cpv_main: Optional[str] = Query(None),
    cpv_code: Optional[str] = Query(None, description="Match any CPV in cpv_codes"),
    form_type: Optional[str] = Query(None),
    min_value: Optional[float] = Query(None),
    max_value: Optional[float] = Query(None),
    deadline_from: Optional[date] = Query(None, description="submission_deadline >= value"),
    deadline_to: Optional[date] = Query(None),
    published_from: Optional[date] = Query(None, description="publication_date >= value"),
    published_to: Optional[date] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TenderItem]:
    query = db.query(Tender)
    filters = []
    if buyer_country:
        filters.append(Tender.buyer_country == buyer_country.upper())
    if procedure_type:
        filters.append(Tender.procedure_type == procedure_type)
    if contract_nature:
        filters.append(Tender.contract_nature == contract_nature.lower())
    if cpv_main:
        filters.append(Tender.cpv_main == cpv_main)
    if cpv_code:
        filters.append(Tender.cpv_codes.any(cpv_code))
    if form_type:
        filters.append(Tender.form_type == form_type)
    if min_value is not None:
        filters.append(Tender.estimated_value >= min_value)
    if max_value is not None:
        filters.append(Tender.estimated_value <= max_value)
    if deadline_from:
        filters.append(Tender.submission_deadline >= deadline_from)
    if deadline_to:
        filters.append(Tender.submission_deadline <= deadline_to)
    if published_from:
        filters.append(Tender.publication_date >= published_from)
    if published_to:
        filters.append(Tender.publication_date <= published_to)
    if updated_from:
        filters.append(Tender.updated_at >= updated_from)
    if q:
        like = f"%{q}%"
        filters.append(or_(
            Tender.title.ilike(like), Tender.description.ilike(like), Tender.summary.ilike(like),
        ))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(Tender.publication_date.desc().nullslast())
        .offset((page - 1) * limit).limit(limit).all()
    )
    data = [
        TenderItem(
            id=r.id, publication_number=r.publication_number, notice_id=r.notice_id,
            form_type=r.form_type, title=r.title, description=r.description,
            official_name=r.official_name, buyer_country=r.buyer_country,
            procedure_type=r.procedure_type, cpv_codes=list(r.cpv_codes or []),
            cpv_main=r.cpv_main, contract_nature=r.contract_nature,
            estimated_value=r.estimated_value, estimated_value_currency=r.estimated_value_currency or "EUR",
            publication_date=r.publication_date, submission_deadline=r.submission_deadline,
            has_lots=bool(r.has_lots), lot_count=r.lot_count, ted_url=r.ted_url,
            summary=r.summary, sme_suitability_score=r.sme_suitability_score,
            status=r.status, last_synced_at=r.last_synced_at, updated_at=r.updated_at,
        )
        for r in rows
    ]
    return build_envelope(data, total=total, page=page, limit=limit,
                          published_from=published_from, published_to=published_to,
                          updated_from=updated_from)


@tenders_router.get(
    "/{tender_id}",
    response_model=TenderItem,
    summary="Single tender detail by id",
)
async def get_tender_detail(
    tender_id: int,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> TenderItem:
    r = db.query(Tender).filter(Tender.id == tender_id).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"Tender id={tender_id} not found",
            "reason_code": "not_found",
            "resource": "tender",
            "id": str(tender_id),
        })
    return TenderItem(
        id=r.id, publication_number=r.publication_number, notice_id=r.notice_id,
        form_type=r.form_type, title=r.title, description=r.description,
        official_name=r.official_name, buyer_country=r.buyer_country,
        procedure_type=r.procedure_type, cpv_codes=list(r.cpv_codes or []),
        cpv_main=r.cpv_main, contract_nature=r.contract_nature,
        estimated_value=r.estimated_value, estimated_value_currency=r.estimated_value_currency or "EUR",
        publication_date=r.publication_date, submission_deadline=r.submission_deadline,
        has_lots=bool(r.has_lots), lot_count=r.lot_count, ted_url=r.ted_url,
        summary=r.summary, sme_suitability_score=r.sme_suitability_score,
        status=r.status, last_synced_at=r.last_synced_at, updated_at=r.updated_at,
    )
