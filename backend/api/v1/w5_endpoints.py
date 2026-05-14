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
    summary="EU in-house research publications — Parliament, Commission, Council, Court of Auditors",
    description="""**What it does**
Returns a unified feed of research publications from the five major EU in-house research services: (1) EPRS — the European Parliament's Research Service, (2) STOA — Panel for the Future of Science and Technology (also EP), (3) JRC — Joint Research Centre (Commission's in-house science service), (4) ART — Analysis and Research Team (Council Secretariat), (5) ECA — European Court of Auditors. Each row carries the source, the publication title and type, the authors, the summary, the policy-area tags, related procedures + CELEX cross-references, and both HTML + PDF URLs.

**When to use it**
Research outputs from these five services are the highest-quality input into EU policymaking before formal proposals drop — they signal what the EP / Commission / Council think is policy-relevant. Use this endpoint to monitor a specific service (filter by `source`), search for research on a topic (`q`), or cross-reference a regulation (`celex`) with the research that anticipated it.

**Input**
- `source` — `eprs` / `stoa` / `jrc` / `art` / `eca`.
- `q` — substring search on title + summary.
- `publication_type` — service-specific (e.g. `briefing`, `study`, `at-a-glance`, `in-depth_analysis`).
- `committee` — 4-letter EP committee code (for EPRS/STOA, the requesting committee).
- `procedure_ref` — OEIL reference for cross-linked publications.
- `celex` — CELEX cross-link.
- `published_from`, `published_to` — date filter.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/research-publications?source=jrc&q=climate
GET /api/v1/research-publications?committee=ENVI&published_from=2026-01-01
```

**You get back**
A `PaginatedResponse[ResearchPublicationItem]` envelope. Each item carries `source`, `publication_id`, `title`, `publication_type`, `publication_date`, `authors`, `summary`, `policy_areas`, `committees`, `related_celex_numbers`, `related_procedures`, `html_url`, `pdf_url`, `last_updated`.

**Data freshness**
Synced once per week (Sunday 05:00 UTC, weekly tier) — STOA/JRC/ART publish a handful of pieces per week each. EPRS is currently fully populated; STOA/JRC/ART/ECA are tracked via the `source` field as ingestion ships. Backed by `backend/scripts/sync_eprs_publications.py` + future `sync_research.py`.""",
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
    """Return the citizen URL for an official. ONLY the cached bio_url —
    we don't synthesise fallbacks because every alternative we tried just
    lands on the generic Whoiswho landing page (the SPA is fully JS-rendered
    and the search query string is decorative on first load). Honest null
    until a Whoiswho re-scrape populates bio_url for every official."""
    return r.bio_url or None


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
    summary="EU officials directory — who runs each institution, DG, cabinet (Whoiswho)",
    description="""**What it does**
Returns a directory of EU officials across the institutional landscape — Commissioners, Heads of Cabinet, Directors-General, Deputy DGs, Directors, Heads of Unit — sourced from the Publications Office's Whoiswho directory. Each row carries the official's name, title, role, institution / DG / cabinet, country of nationality, posting city, contact details (email / phone when public), bio page URL, photo, portfolio, and active-status flag. Scrape-noise rows (filter-bar labels, postal-address artifacts, alternate-script duplicates) are filtered out at query time.

**When to use it**
To find the right contact for an outreach campaign ("who heads the AI unit in DG CNECT?"), build an org-chart visualisation, or look up who recently moved to a new role. The bio URLs deep-link to the official's Whoiswho page where the full posting history is available.

**Input**
- `institution_slug` — e.g. `european-commission`, `european-parliament`.
- `dg` — DG code uppercased (e.g. `COMP`, `CLIMA`).
- `cabinet` — cabinet name (e.g. `Ribera`).
- `country` — ISO-2 of nationality.
- `is_active` — boolean (defaults to true; pass `false` to include retired officials).
- `q` — substring search on name + role + title.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/officials?dg=COMP&q=director
GET /api/v1/officials?institution_slug=european-parliament&country=NL
```

**You get back**
A `PaginatedResponse[OfficialItem]` envelope sorted alphabetically by name. Each item carries `slug`, `name`, `title`, `role`, `institution_slug`, `dg`, `cabinet`, `country`, `city`, `email`, `phone`, `bio_url`, `photo_url`, `portfolio`, `policy_areas`, `is_active`, plus a composed `body_txt`/`body_html` (full contact-card) and the 5 envelope-level datapoints (`public_url = bio_url`).

**Data freshness**
Synced once per month (1st of month, 02:00 UTC, monthly tier) from op.europa.eu/en/web/who-is-who. Senior officials change at cabinet reshuffles (once per Von der Leyen term) + a handful of mid-cycle moves; monthly sync is enough. Scraper queued for full re-ingest; current data reflects a partial backfill.""",
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


@officials_router.get(
    "/{slug}",
    response_model=OfficialItem,
    summary="Look up one EU official by their slug — full contact card with photo + portfolio",
    description="""**What it does**
Fetches a single EU official by their stable slug. Returns the same shape as the list endpoint, including the composed contact-card body and the link to their Whoiswho bio page.

**When to use it**
After locating an official via the list endpoint, use this to fetch the full record (with photo + composed body) for embedding in a contact card or briefing note.

**Input**
- `slug` (path) — stable slug for the official (returned in `slug` from the list endpoint, derived from name + role).

**Try it**
```
GET /api/v1/officials/jean-eric-paquet-director-general-dg-rtd
```

**You get back**
A single `OfficialItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — monthly 1st-of-month 02:00 UTC sync from op.europa.eu/en/web/who-is-who.""",
)
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
    summary="EU public procurement tenders (TED — Tenders Electronic Daily)",
    description="""**What it does**
Returns public-procurement tender notices from TED (Tenders Electronic Daily) — the EU's official journal for procurement, where every supplement to the OJ for above-threshold contracts is published. Covers tenders from the Commission, EP, Council, agencies, and Member State buyers obliged to publish at EU level. Each row carries the publication number, the title + description, the buying authority, the procedure type, the CPV codes (Common Procurement Vocabulary), the estimated value, the publication date, the submission deadline, lots information, and an SME-suitability score.

**When to use it**
For consultancies / SMEs looking for EU funding opportunities — filter by `cpv_main` for your sector, set `min_value` / `max_value` for relevant contract sizes, and use `deadline_from` / `deadline_to` to scope to bidding-feasible windows. The `sme_suitability_score` (0-1) is Brubru's heuristic on how SME-friendly a tender is based on value + lots + complexity.

**Input**
- `q` — substring search on title + description + summary.
- `buyer_country` — ISO-2.
- `procedure_type` — TED procedure type code.
- `contract_nature` — `works` / `supplies` / `services`.
- `cpv_main`, `cpv_code` — CPV filter.
- `form_type` — TED form code (F02 / F03 / F14 / etc).
- `min_value`, `max_value` — estimated-value range in EUR.
- `deadline_from`, `deadline_to` — submission_deadline window.
- `published_from`, `published_to` — publication date window.
- `updated_from` — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/tenders?cpv_main=72000000&min_value=50000
GET /api/v1/tenders?buyer_country=BE&contract_nature=services
```

**You get back**
A `PaginatedResponse[TenderItem]` envelope. Each item carries `publication_number`, `notice_id`, `form_type`, `title`, `description`, `official_name`, `buyer_country`, `procedure_type`, `cpv_codes`, `cpv_main`, `contract_nature`, `estimated_value` + `estimated_value_currency`, `publication_date`, `submission_deadline`, `has_lots`, `lot_count`, `ted_url`, `summary`, `sme_suitability_score`, `status`, `last_synced_at`, `updated_at`.

**Data freshness**
Synced once per day at 04:00 UTC (daily tier) from ted.europa.eu — TED publishes daily by definition (the "Daily" in the name). Backed by `backend/scripts/backfill_tenders_description.py`.""",
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
    summary="Look up one TED tender by its internal numeric id",
    description="""**What it does**
Fetches a single TED tender by its Brubru-internal integer id. Returns the same shape as the list endpoint, including CPV codes + lot details + the TED URL for the official notice.

**When to use it**
After locating a tender via the list endpoint, use this to fetch the full record (with description + all CPV codes) for embedding in a bid-tracker UI.

**Input**
- `tender_id` (path) — Brubru integer id (returned in `id` from the list endpoint).

**Try it**
```
GET /api/v1/tenders/12345
```

**You get back**
A single `TenderItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — daily 04:00 UTC sync from ted.europa.eu.""",
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
