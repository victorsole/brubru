"""
/api/v1/texts-adopted — EP plenary adopted texts (resolutions, legislative acts, decisions).
/api/v1/texts-submitted — EP plenary texts submitted (tabled for debate/vote).

Backed by the texts_adopted table populated by texts_adopted_sync_service.
Texts-submitted is a sibling endpoint surfacing rows that have not yet been
adopted (no adoption_date) — useful for partners tracking the plenary pipeline.
"""

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.text_adopted import TextAdopted
from models.user import User

from ._body import body_from_pdf_text, body_threshold_param, deprecated_body
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)


texts_adopted_router = APIRouter(prefix="/texts-adopted", tags=["v1-texts-adopted"])
texts_submitted_router = APIRouter(prefix="/texts-submitted", tags=["v1-texts-submitted"])


class TextItem(BaseModel):
    id: str
    ta_reference: str
    title: str
    description: Optional[str] = None
    text_type: Optional[str] = None
    procedure_ref: Optional[str] = None
    parliamentary_term: int = 10
    adoption_date: Optional[datetime] = None
    committees: list = Field(default_factory=list)
    rapporteur_name: Optional[str] = None
    rapporteur_mep_id: Optional[str] = None
    celex_number: Optional[str] = None
    vote_results: Optional[dict] = None
    related_documents: list = Field(default_factory=list)
    source_url: Optional[str] = None
    full_text_url: Optional[str] = None
    pdf_url: Optional[str] = None
    last_updated: Optional[datetime] = None
    # Body fields composed from `full_text` (PDF-extracted plain text from
    # doceo PDF). PDF-sourced rows return body_html=null per the contract.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # Deprecated alias kept one release; equals body_text. Same for
    # has_full_text → has_body.
    has_full_text: bool = False
    full_text: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints.
    public_url: Optional[str] = Field(None, description="Citizen URL — full_text_url / pdf_url / source_url fallback chain.")
    document_date: Optional[date] = Field(None, description="Adoption date (date-only view of adoption_date).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this row (alias of last_updated).")


def _row_to_item(
    r: TextAdopted,
    body_threshold: int = 500,
) -> TextItem:
    body_html, body_text, has_body = body_from_pdf_text(r.full_text, threshold=body_threshold)
    # Tier-2 fallback when full_text is null (typical for /texts-submitted —
    # tabled but not yet adopted, so no PDF to extract). Compose body from
    # the structured row: title + procedure + committees + rapporteur + dates.
    if not body_text:
        import html as _html
        lines_txt = [r.title or "?"]
        parts_html = [f"<h2>{_html.escape(r.title or '?')}</h2>"]
        kv: list = []
        if r.ta_reference: kv.append(("TA reference", r.ta_reference))
        if r.text_type: kv.append(("Type", r.text_type.value if hasattr(r.text_type, "value") else str(r.text_type)))
        if r.procedure_ref: kv.append(("Procedure", r.procedure_ref))
        if r.adoption_date: kv.append(("Adopted", str(r.adoption_date)))
        if r.committees: kv.append(("Committees", ", ".join(r.committees)))
        if r.rapporteur_name: kv.append(("Rapporteur", r.rapporteur_name))
        if r.celex_number: kv.append(("CELEX", r.celex_number))
        for k, v in kv:
            lines_txt.append(f"{k}: {v}")
            parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
        body_text = "\n".join(lines_txt)
        body_html = "<article>" + "".join(parts_html) + "</article>" if parts_html else None
    # public_url ladder. EUR-Lex CELEX page when available is the safest
    # choice — no CloudFront WAF challenge (doceo URLs typically return 202
    # to server-side anonymous requests). Falls back to full_text_url / pdf_url
    # / source_url. Last-resort: the texts-submitted listing page itself,
    # which always 200s, so a citizen click never lands on the EP "URL does
    # not exist" fallback.
    if r.celex_number:
        public_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{r.celex_number}"
    else:
        public_url = (
            r.full_text_url
            or r.pdf_url
            or r.source_url
            or "https://www.europarl.europa.eu/plenary/en/texts-submitted.html"
        )
    return TextItem(
        id=str(r.id),
        ta_reference=r.ta_reference,
        title=r.title,
        description=r.description,
        text_type=r.text_type.value if hasattr(r.text_type, "value") else (str(r.text_type) if r.text_type else None),
        procedure_ref=r.procedure_ref,
        parliamentary_term=int(r.parliamentary_term or 10),
        adoption_date=r.adoption_date,
        committees=list(r.committees or []),
        rapporteur_name=r.rapporteur_name,
        rapporteur_mep_id=r.rapporteur_mep_id,
        celex_number=r.celex_number,
        vote_results=r.vote_results if isinstance(r.vote_results, dict) else None,
        related_documents=list(r.related_documents or []) if r.related_documents else [],
        source_url=r.source_url,
        full_text_url=r.full_text_url,
        pdf_url=r.pdf_url,
        last_updated=r.last_updated,
        has_body=has_body,
        body_html=body_html,
        body_txt=body_text,
        # Deprecated aliases kept one release.
        has_full_text=has_body,
        full_text=body_text,
        # 5 mandatory datapoints
        public_url=public_url,
        document_date=r.adoption_date.date() if hasattr(r.adoption_date, "date") and r.adoption_date else None,
        creation_date=r.last_updated,
    )


def _validate_date_params(
    published_from, published_to, published_end,
    updated_from, updated_to, updated_end,
):
    if published_end and published_to and published_end != published_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: published_to={published_to} and published_end={published_end}.",
            "reason_code": "conflicting_params",
        })
    if published_end and not published_to:
        published_to = published_end
    if published_from and published_to and published_from > published_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Invalid date range: published_from={published_from} after published_to={published_to}.",
            "reason_code": "invalid_date_range",
        })
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
            "reason_code": "conflicting_params",
        })
    if updated_end and not updated_to:
        updated_to = updated_end
    return published_to, updated_to


@texts_adopted_router.get(
    "",
    response_model=PaginatedResponse[TextItem],
    summary="EP plenary texts that have been adopted — resolutions, legislative resolutions, decisions",
    description="""**What it does**
Returns every text adopted by the European Parliament in plenary session — legislative resolutions (the EP's formal positions on legislation), non-legislative resolutions (own-initiative + topical), decisions, recommendations. Each row carries the TA reference (e.g. `P10_TA(2025)0042`), the title, text type, procedure ref + parliamentary term, lead committee, rapporteur, adoption date, vote tallies, and the full-text URL.

**When to use it**
The authoritative record of what the EP has decided in plenary. Use to track positions on co-decision files (legislative_resolution), trace the EP's stance on a topic (resolution), or build a plenary outcomes dashboard. Pair with `/api/v1/texts-submitted` to see the pipeline from tabled → adopted.

**Input**
- `q` — substring on title + description.
- `text_type` — `resolution` / `legislative_resolution` / `decision` / `recommendation` / `other`.
- `procedure_ref` — OEIL reference.
- `parliamentary_term` — EP term (e.g. 10 for current, 9 for 2019-2024).
- `committee` — lead committee code.
- `rapporteur_mep_id` — filter to one rapporteur's adopted texts.
- `published_from`, `published_to` (and `published_end` alias) — adoption_date filter.
- `updated_from`, `updated_to` (and `updated_end` alias) — incremental sync.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/texts-adopted?text_type=legislative_resolution&committee=ENVI
GET /api/v1/texts-adopted?procedure_ref=2024/0079(COD)
```

**You get back**
A `PaginatedResponse[TextItem]` envelope. Each item carries `ta_reference`, `title`, `text_type`, `procedure_ref`, `parliamentary_term`, `committees`, `rapporteur_mep_id`, `rapporteur_name`, `adoption_date`, vote tallies, `full_text_url`, plus the 5 envelope-level datapoints.

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) via RSS from europarl.europa.eu/plenary/en/texts-adopted.html. Texts appear within hours of plenary adoption.""",
)
async def list_texts_adopted(
    request: Request,
    q: Optional[str] = Query(None, description="Substring on title + description"),
    text_type: Optional[str] = Query(None, description="resolution | legislative_resolution | decision | recommendation | other"),
    procedure_ref: Optional[str] = Query(None),
    parliamentary_term: Optional[int] = Query(None, description="EP term, e.g. 9, 10"),
    committee: Optional[str] = Query(None),
    rapporteur_mep_id: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None, description="adoption_date >= value"),
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
) -> PaginatedResponse[TextItem]:
    published_to, updated_to = _validate_date_params(
        published_from, published_to, published_end,
        updated_from, updated_to, updated_end,
    )

    query = db.query(TextAdopted).filter(TextAdopted.adoption_date.isnot(None))
    filters = []
    if text_type:
        filters.append(TextAdopted.text_type == text_type.lower())
    if procedure_ref:
        filters.append(TextAdopted.procedure_ref == procedure_ref)
    if parliamentary_term is not None:
        filters.append(TextAdopted.parliamentary_term == parliamentary_term)
    if committee:
        filters.append(TextAdopted.committees.any(committee.upper()))
    if rapporteur_mep_id:
        filters.append(TextAdopted.rapporteur_mep_id == rapporteur_mep_id)
    if published_from:
        filters.append(TextAdopted.adoption_date >= published_from)
    if published_to:
        filters.append(TextAdopted.adoption_date <= datetime.combine(published_to, datetime.max.time()))
    if updated_from:
        filters.append(TextAdopted.last_updated >= updated_from)
    if updated_to:
        filters.append(TextAdopted.last_updated <= updated_to)
    if q:
        like = f"%{q}%"
        filters.append(or_(TextAdopted.title.ilike(like), TextAdopted.description.ilike(like)))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    if updated_from or updated_to:
        order_col = TextAdopted.last_updated.desc().nullslast()
    else:
        order_col = TextAdopted.adoption_date.desc().nullslast()
    rows = query.order_by(order_col).offset((page - 1) * limit).limit(limit).all()

    # Declare the corpus bounds (D2). Until 27 Aug 2026 this corpus opened on
    # 20 January 2026 and said nothing about it, so the EP's 26 November 2025
    # resolution on protecting minors online fell before the first row and every
    # search for it returned a clean, confident zero -- indistinguishable from
    # "no such text exists". Computed from the data, not hardcoded, so it cannot
    # rot as the backfill extends.
    cov = db.query(
        func.min(TextAdopted.adoption_date), func.max(TextAdopted.adoption_date)
    ).one()

    return build_envelope(
        [_row_to_item(r, body_threshold=body_threshold) for r in rows],
        total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        updated_from=updated_from, updated_to=updated_to,
        coverage_from=(cov[0].date() if cov and cov[0] else None),
        coverage_to=(cov[1].date() if cov and cov[1] else None),
        coverage_note=(
            "Adopted texts scraped from the Parliament's plenary TOC pages. "
            "coverage_from is the earliest text held, NOT the start of the "
            "parliamentary term: a search that returns nothing for a date before "
            "it means the corpus does not reach back that far, not that the "
            "Parliament adopted nothing."
        ),
    )


@texts_adopted_router.get(
    "/{ta_reference}",
    response_model=TextItem,
    summary="Look up one EP plenary-adopted text by its TA reference (e.g. P10_TA(2025)0042)",
    description="""**What it does**
Fetches a single EP plenary-adopted text by its TA reference. Returns the same shape as the list endpoint, including the full-text URL and body composition.

**When to use it**
After locating a text via the list endpoint, use this for the deep-link. Common pattern in chat answers when a user references a specific P10_TA number.

**Input**
- `ta_reference` (path) — the TA reference (format: `P<TERM>_TA(<YEAR>)<NUMBER>`, e.g. `P10_TA(2025)0042`). The `:path` matcher accepts parentheses verbatim.

**Try it**
```
GET /api/v1/texts-adopted/P10_TA(2025)0042
```

**You get back**
A single `TextItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same as the list endpoint — synced every 6 hours from europarl.europa.eu/plenary/en/texts-adopted.html.""",
)
async def get_text_adopted_detail(
    ta_reference: str,
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> TextItem:
    r = db.query(TextAdopted).filter(TextAdopted.ta_reference == ta_reference).first()
    if not r:
        raise HTTPException(status_code=404, detail={
            "error": f"TA reference {ta_reference} not found",
            "reason_code": "not_found",
            "resource": "text_adopted",
            "id": ta_reference,
        })
    return _row_to_item(r, body_threshold=body_threshold)


@texts_submitted_router.get(
    "",
    response_model=PaginatedResponse[TextItem],
    summary="EP plenary texts tabled but NOT YET adopted — the upcoming-vote pipeline",
    description="""**What it does**
Returns EP plenary texts that have been formally tabled for vote but not yet adopted (no adoption_date). Sibling endpoint to `/texts-adopted` — the same row "moves" from submitted to adopted when the plenary vote concludes. Each row carries the procedure ref, title, text type, parliamentary term, lead committee, rapporteur, the tabling date, and the doceo URL.

**When to use it**
For advocacy work focused on upcoming plenary votes — see what's coming next week, identify which committees have files in the pipeline, or filter by rapporteur to track an MEP's pending plenary texts. Pair with `/api/v1/calendar?event_type=PLENARY` to know WHEN each text is expected to be voted.

**Input**
Same shape as `/texts-adopted` — `q`, `text_type`, `procedure_ref`, `parliamentary_term`, `committee`, `rapporteur_mep_id`, date filters, incremental sync, pagination.

**Try it**
```
GET /api/v1/texts-submitted?committee=LIBE&parliamentary_term=10
GET /api/v1/texts-submitted?text_type=legislative_resolution
```

**You get back**
A `PaginatedResponse[TextItem]` envelope — same shape as `/texts-adopted`'s response, but with `adoption_date` null on every row (texts are pre-adoption).

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from europarl.europa.eu/plenary/en/texts-submitted.html. New tablings appear on doceo within hours; the 6h sync catches them.""",
)
async def list_texts_submitted(
    request: Request,
    q: Optional[str] = Query(None),
    text_type: Optional[str] = Query(None),
    procedure_ref: Optional[str] = Query(None),
    parliamentary_term: Optional[int] = Query(None),
    committee: Optional[str] = Query(None),
    updated_from: Optional[datetime] = Query(None),
    updated_to: Optional[datetime] = Query(None),
    updated_end: Optional[datetime] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TextItem]:
    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(status_code=422, detail={
            "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
            "reason_code": "conflicting_params",
        })
    if updated_end and not updated_to:
        updated_to = updated_end

    # Texts-submitted = rows in the same table without an adoption_date yet.
    query = db.query(TextAdopted).filter(TextAdopted.adoption_date.is_(None))
    filters = []
    if text_type:
        filters.append(TextAdopted.text_type == text_type.lower())
    if procedure_ref:
        filters.append(TextAdopted.procedure_ref == procedure_ref)
    if parliamentary_term is not None:
        filters.append(TextAdopted.parliamentary_term == parliamentary_term)
    if committee:
        filters.append(TextAdopted.committees.any(committee.upper()))
    if updated_from:
        filters.append(TextAdopted.last_updated >= updated_from)
    if updated_to:
        filters.append(TextAdopted.last_updated <= updated_to)
    if q:
        like = f"%{q}%"
        filters.append(or_(TextAdopted.title.ilike(like), TextAdopted.description.ilike(like)))
    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    rows = (
        query.order_by(TextAdopted.last_updated.desc().nullslast())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    return build_envelope(
        [_row_to_item(r, body_threshold=body_threshold) for r in rows],
        total=total, page=page, limit=limit,
        updated_from=updated_from, updated_to=updated_to,
    )
