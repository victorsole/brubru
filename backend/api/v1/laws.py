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
    text_url: Optional[str] = Field(None, description="Brubru endpoint for the full body (XML or plain text). Call this URL to retrieve the actual law content.")
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of eurlex_url).")
    body_txt: Optional[str] = Field(None, description="Null on list — call /laws/{celex}/text for the body.")
    body_html: Optional[str] = Field(None, description="Null on list — call /laws/{celex}/text for the body.")
    document_date: Optional[date] = Field(None, description="Adoption / publication date (alias of adopted_on).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this CELEX (eu_laws.created_at).")


def _eurlex_url(celex: Optional[str]) -> Optional[str]:
    if not celex:
        return None
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


@router.get(
    "",
    response_model=PaginatedResponse[LawItem],
    summary="Search adopted EU legislation — 8,710 distinct laws across 28,513 OJ publications",
    description="""**What it does**
Full-text search over Brubru's mirror of adopted EU legislation — the LEG_2025-11 bulk export from the Publications Office, covering 8,710 distinct laws across 28,513 Official Journal publications. Each row carries the EU's legal identifier, the document type (regulation / directive / decision / recommendation / opinion / communication / agreement), the title + subject matter, the policy area, the publication date, the CELEX number, and a link to the EUR-Lex canonical URL.

**When to use it**
The single highest-traffic Brubru endpoint — used to find specific acts (e.g. "the AI Act"), enumerate laws by topic (e.g. all environment regulations from 2024), or build a partner integration that needs the live adopted-legislation corpus. Pair with `/api/v1/laws/{celex}/text` for the full legal text body. For procedures still in negotiation, use `/api/v1/procedures` instead.

**Input**
- `q` — full-text search on title + subject matter (PostgreSQL TSVECTOR).
- `celex` — exact match on the legal identifier (the CELEX number).
- `doc_type` — `regulation` / `directive` / `decision` / `recommendation` / `opinion` / etc. See `/api/v1/document-types` for the live distinct list.
- `policy_area` — single tag (see `/api/v1/policy-areas`).
- `published_from`, `published_to` — date filter on `published_date`.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/laws?q=AI%20Act&limit=10
GET /api/v1/laws?doc_type=regulation&policy_area=environment&published_from=2024-01-01
```

**You get back**
A `PaginatedResponse[LawItem]` envelope. Each item carries `celex`, `title`, `doc_type`, `subject_matter`, `policy_area`, `published_date`, `eur_lex_url`, `oj_reference`, and the 5 envelope-level datapoints.

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from EUR-Lex RSS feeds + Cellar SPARQL sector-3 (secondary acts). New regulations + directives published in the Official Journal L-series appear in our mirror within the same day they hit EUR-Lex.""",
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
    include_orphans: bool = Query(False, description="Include rows that have no CELEX (orphaned annexes / recitals from Formex parsing). Default false — they have no useful identifier and produce all-null rows."),
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
    # Default: hide rows that have no CELEX. These are mostly orphaned annexes
    # / recitals from older Formex parses where the parser failed to bind the
    # part to its parent. Surfacing them produces all-null /laws rows that
    # confuse partners. Pass include_orphans=true to opt back in.
    if not include_orphans:
        filters.append(EULaw.celex.isnot(None))
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
            text_url=f"/api/v1/laws/{r.celex}/text" if r.celex else None,
            public_url=_eurlex_url(r.celex),
            document_date=r.date,
            creation_date=r.created_at,
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
        # Phase 3 — OP Core Metadata enrichment.
        op_core_title="EU legislation listing",
        op_core_type="EU legislation",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "https://brubru.beresol.eu/api/v1/discover/cellar/recent",
            "https://brubru.beresol.eu/api/v1/discover/cellar/celex/{celex}/relationships",
            "https://brubru.beresol.eu/api/v1/vocabularies/modification-types",
        ],
    )


@router.get(
    "/{celex}",
    response_model=LawItem,
    summary="Look up one adopted EU law by its legal identifier — metadata only (no body)",
    description="""**What it does**
Returns the bibliographic metadata for one adopted EU law identified by its CELEX (the EU's stable legal identifier — e.g. `32024R1689` for the AI Act). Returns title, document type, adoption date, OJ reference, policy area, legal basis array, EUR-Lex URL, and a relative URL to the text endpoint.

**When to use it**
When you only need bibliographic fields (title, doc_type, policy_area, legal_basis, oj_reference, adoption date) and not the full body — significantly faster than `/{celex}/text` because it doesn't fetch the body. Pair with `/api/v1/laws/{celex}/text` when you need the actual legal text.

**Input**
- `celex` (path) — the EU legal identifier. Case-insensitive; we uppercase internally. Format: 5 digits + 1-2 letters + 4 digits (e.g. `32024R1689`, `52026PC0321`).

**Try it**
```
GET /api/v1/laws/32024R1689
GET /api/v1/laws/32016R0679
```

**You get back**
A `LawItem` with `celex`, `title`, `doc_type` (normalised), `adopted_on`, `oj_reference`, `policy_area`, `legal_basis[]`, `eurlex_url`, `text_url` (relative URL to the text endpoint), plus the 5 envelope-level datapoints. HTTP 404 with `reason_code: not_found` if the CELEX isn't in our mirror.

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from EUR-Lex RSS feeds + Cellar SPARQL sector-3.""",
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
        text_url=f"/api/v1/laws/{r.celex}/text" if r.celex else None,
        public_url=_eurlex_url(r.celex),
        document_date=r.date,
        creation_date=r.created_at,
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
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of eurlex_url).")
    body_txt: Optional[str] = Field(None, description="Plain-text body — populated when format=plain (mirrors `content`).")
    body_html: Optional[str] = Field(None, description="HTML/XHTML body — populated when format=xml (mirrors `content`).")
    document_date: Optional[date] = Field(None, description="Adoption / publication date (alias of adopted_on).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this CELEX.")


@router.get(
    "/{celex}/text",
    response_model=LawTextResponse,
    summary="Full text of one adopted EU law — plain text or raw XML",
    description="""**What it does**
Returns the full legal text of an adopted EU law identified by its CELEX. Tries the local Formex V4 XML cache first (28,513 files from the LEG_2025-11 bulk export); falls back to live fetch from Cellar (`publications.europa.eu/resource/celex/{celex}` with `Accept: application/xhtml+xml`). Returns the body as either whitespace-normalised plain text (default) or raw markup.

**When to use it**
When you need the actual legal text — for citation, full-text analysis, or feeding into a downstream LLM context. The local Formex cache is fast (~50ms); Cellar fallback is slower (~2-3s) but always works for any post-1952 CELEX. For pre-parsed structured access (recital ↔ article mapping, definition extraction), use the `/api/v1/legal-text/*` endpoints instead.

**Input**
- `celex` (path) — EU legal identifier (case-insensitive).
- `format` — `plain` (default, whitespace-normalised) or `xml` (raw Formex markup).

**Try it**
```
GET /api/v1/laws/32024R1689/text
GET /api/v1/laws/32016R0679/text?format=xml
```

**You get back**
A `LawTextResponse` with `celex`, `title`, `doc_type`, `adopted_on`, `format`, `content` (the actual text), `content_length`, `eurlex_url`, plus the 5 envelope-level datapoints (`body_txt` mirrors `content` when format=plain, `body_html` when format=xml).

**Data freshness**
Live pass-through (the local Formex cache is regenerated quarterly from the LEG_YYYY-MM bulk export). For acts NOT in the local cache, the live Cellar fetch always reflects the latest published text — but the Publications Office is the slow-changing authoritative source: once an act is published in the OJ, its text doesn't change (only consolidations get new CELEX numbers).""",
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
        public_url=_eurlex_url(row.celex),
        body_txt=text if format == "plain" else None,
        body_html=text if format == "xml" else None,
        document_date=row.date,
        creation_date=row.created_at,
    )
