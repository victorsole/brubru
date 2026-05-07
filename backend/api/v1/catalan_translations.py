"""
/api/v1/catalan-translations — open data: the EU acquis in Catalan.

OPEN-SOURCE / FREE TIER
========================
Unlike the rest of /api/v1/*, this surface is NOT gated by X-API-Key.
The underlying corpus is published under the MIT licence (see the
landing page footer at https://brubru.beresol.eu/legislacio-ue-catala/);
gating it would be at odds with that licence. Free public endpoints
share the global rate-limit middleware; no per-key tier is enforced.

The /api/v1/catalan-translations namespace exposes the binding-law
subset of the corpus only — sector-3 acts whose CELEX matches
``^3[0-9]{4}[RLD][0-9]{4}$`` (Regulations, Directives, Decisions). The
257 OJ C/L-series fragments imported under the broader sweep are
filtered out at SQL level until the audit pipeline reclassifies them.

Endpoints
---------
- GET  /api/v1/catalan-translations            List + filter (paginated)
- GET  /api/v1/catalan-translations/stats      Aggregate counts
- GET  /api/v1/catalan-translations/{celex}    Single record (?body=html opt-in)

Created: 7 May 2026 — Dia d'Europa launch.
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.catalan_translation import CatalanTranslation

from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalan-translations", tags=["v1-catalan-translations"])

# Binding-law CELEX (sector 3, forms R/L/D). Matches the filter we put on
# batch_catalan_translate.py --binding-only. Excludes OJ C/L-series notice
# fragments imported beyond the canonical 8,710 set.
BINDING_CELEX_SQL = r"^3\d{4}[RLD]\d{4}$"

LANDING_BASE = "https://brubru.beresol.eu/legislacio-ue-catala/"
EURLEX_BASE = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"

# On-disk path to rendered Catalan HTML (used when ?body=html is requested
# on the single-record endpoint).
DISK_TRANSLATIONS_DIR = (
    Path(__file__).resolve().parents[3] / "data" / "legislacio-ue-catala"
)


# --------------------------------------------------------------------------- #
# Pydantic schemas                                                            #
# --------------------------------------------------------------------------- #

class CatalanTranslationItem(BaseModel):
    """One translated EU legal act in Catalan."""

    model_config = ConfigDict(from_attributes=True)

    celex: str = Field(..., description="CELEX identifier (sector 3, form R/L/D).")
    oj_reference: Optional[str] = Field(None, description="Official Journal reference (L-series).")
    doc_type: Optional[str] = Field(None, description="regulation | directive | decision | delegated | implementing | treaty")
    short_name: Optional[str] = Field(None, description="Common short name where known (GDPR, AI Act, MiFID II...).")
    title_ca: Optional[str] = Field(None, description="Title in Catalan.")
    title_en: Optional[str] = Field(None, description="Title in English (source).")
    category: Optional[str] = Field(None, description="Brubru top-level category (Catalan).")
    category_en: Optional[str] = Field(None, description="Brubru top-level category (English).")
    subcategory: Optional[str] = Field(None, description="More granular tag where assigned.")
    articles_count: Optional[int] = None
    recitals_count: Optional[int] = None
    html_size_bytes: Optional[int] = None
    engine: Optional[str] = Field(None, description="Translation engine: softcatala (NMT) or sonnet (Claude).")
    source_format: Optional[str] = Field(None, description="Source XML format — currently 'formex' (Formex V4).")
    ca_url: str = Field(..., description="Canonical Catalan HTML rendering on brubru.beresol.eu.")
    source_eurlex_url: str = Field(..., description="EUR-Lex landing page for the original act (multilingual).")
    translated_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CatalanTranslationDetail(CatalanTranslationItem):
    """Single-record response — extends the list item with optional body inlining."""

    body_html: Optional[str] = Field(
        None,
        description="Rendered Catalan HTML body. Populated only when ?body=html is requested. "
        "May be omitted if the file is missing on disk.",
    )


class CategoryCount(BaseModel):
    category: Optional[str]
    category_en: Optional[str]
    count: int


class DocTypeCount(BaseModel):
    doc_type: Optional[str]
    count: int


class EngineCount(BaseModel):
    engine: Optional[str]
    count: int


class CatalanStats(BaseModel):
    """Aggregate counts over the binding-law subset."""

    total: int = Field(..., description="Total binding-law translations available.")
    target: int = Field(8710, description="Canonical EU binding-law count we converge to.")
    coverage_pct: float = Field(..., description="100 * total / target, capped at 100.")
    by_doc_type: list[DocTypeCount]
    by_category: list[CategoryCount]
    by_engine: list[EngineCount]
    last_translated_at: Optional[datetime] = None
    licence: str = Field("MIT", description="Translations are MIT-licensed; redistribution permitted with attribution.")


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _ca_url(celex: str) -> str:
    return f"{LANDING_BASE}{celex}/"


def _eurlex_url(celex: str) -> str:
    return f"{EURLEX_BASE}{celex}"


def _row_to_item(row: CatalanTranslation) -> CatalanTranslationItem:
    return CatalanTranslationItem(
        celex=row.celex,
        oj_reference=row.oj_reference,
        doc_type=row.doc_type,
        short_name=row.short_name,
        title_ca=row.title_ca,
        title_en=row.title_en,
        category=row.category,
        category_en=row.category_en,
        subcategory=row.subcategory,
        articles_count=row.articles_count,
        recitals_count=row.recitals_count,
        html_size_bytes=row.html_size_bytes,
        engine=row.engine,
        source_format=row.source_format,
        ca_url=_ca_url(row.celex),
        source_eurlex_url=_eurlex_url(row.celex),
        translated_at=row.translated_at,
        updated_at=row.updated_at,
    )


def _binding_law_filter(query):
    """Apply the binding-law CELEX filter at SQL level.

    Hides the 257 OJ C/L-series notice fragments imported beyond the
    canonical 8,710 set — we don't promote those to the paid v1 surface
    until the audit pipeline reclassifies them.
    """
    return query.filter(
        and_(
            CatalanTranslation.file_type == "main",
            CatalanTranslation.celex.op("~")(BINDING_CELEX_SQL),
        )
    )


# --------------------------------------------------------------------------- #
# Endpoints                                                                   #
# --------------------------------------------------------------------------- #

@router.get(
    "",
    response_model=PaginatedResponse[CatalanTranslationItem],
    summary="List EU binding laws translated into Catalan",
    description=(
        "Open dataset (MIT). Paginated catalogue of binding EU legal acts "
        "(Regulations, Directives, Decisions) translated into Catalan by "
        "Brubru using the Softcatalà NMT engine. Updated daily.\n\n"
        "**No API key required.** Subject to the global rate limit.\n\n"
        "Filter combinations are AND-ed. Pass `q` for a substring search "
        "across the Catalan title, English title, short name, and CELEX."
    ),
)
async def list_catalan_translations(
    request: Request,
    q: Optional[str] = Query(None, description="Substring search across title_ca, title_en, short_name, celex."),
    celex: Optional[str] = Query(None, description="Exact CELEX filter."),
    doc_type: Optional[str] = Query(None, description="regulation | directive | decision | delegated | implementing | treaty."),
    category: Optional[str] = Query(None, description="Brubru category (Catalan name) — see /stats for the full list."),
    category_en: Optional[str] = Query(None, description="Brubru category (English name)."),
    engine: Optional[str] = Query(None, description="softcatala | sonnet"),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync — rows with updated_at >= value."),
    updated_to: Optional[datetime] = Query(None, description="Incremental sync upper bound — rows with updated_at <= value."),
    limit: int = Query(50, ge=1, le=200, description="Items per page (default 50, max 200)."),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CatalanTranslationItem]:
    qry = _binding_law_filter(db.query(CatalanTranslation))

    if q:
        term = f"%{q}%"
        qry = qry.filter(
            or_(
                CatalanTranslation.title_ca.ilike(term),
                CatalanTranslation.title_en.ilike(term),
                CatalanTranslation.short_name.ilike(term),
                CatalanTranslation.celex.ilike(term),
            )
        )
    if celex:
        qry = qry.filter(CatalanTranslation.celex == celex)
    if doc_type:
        qry = qry.filter(CatalanTranslation.doc_type == doc_type)
    if category:
        qry = qry.filter(CatalanTranslation.category == category)
    if category_en:
        qry = qry.filter(CatalanTranslation.category_en == category_en)
    if engine:
        qry = qry.filter(CatalanTranslation.engine == engine)
    if updated_from:
        qry = qry.filter(CatalanTranslation.updated_at >= updated_from)
    if updated_to:
        qry = qry.filter(CatalanTranslation.updated_at <= updated_to)

    total = qry.count()
    rows = (
        qry.order_by(CatalanTranslation.celex.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    items = [_row_to_item(r) for r in rows]

    return build_envelope(
        items=items,
        total=total,
        page=page,
        limit=limit,
        updated_from=updated_from,
        updated_to=updated_to,
        op_core_title="EU binding-law corpus translated into Catalan (Brubru, MIT)",
        op_core_type="EU legislation translation catalogue",
        op_core_identifier=str(request.url),
        op_core_language="ca",
        op_core_referenced_by=[
            "https://brubru.beresol.eu/legislacio-ue-catala/",
            "/api/v1/laws",
        ],
    )


@router.get(
    "/stats",
    response_model=CatalanStats,
    summary="Catalan translations — aggregate counts",
    description=(
        "Counts grouped by doc_type, category, and engine. Useful for a status "
        "dashboard or to verify ingestion before pulling pages."
    ),
)
async def catalan_translations_stats(db: Session = Depends(get_db)) -> CatalanStats:
    base = _binding_law_filter(db.query(CatalanTranslation))
    total = base.count()

    by_doc = (
        _binding_law_filter(db.query(CatalanTranslation.doc_type, func.count().label("n")))
        .group_by(CatalanTranslation.doc_type)
        .order_by(func.count().desc())
        .all()
    )
    by_cat = (
        _binding_law_filter(
            db.query(
                CatalanTranslation.category,
                CatalanTranslation.category_en,
                func.count().label("n"),
            )
        )
        .group_by(CatalanTranslation.category, CatalanTranslation.category_en)
        .order_by(func.count().desc())
        .all()
    )
    by_eng = (
        _binding_law_filter(db.query(CatalanTranslation.engine, func.count().label("n")))
        .group_by(CatalanTranslation.engine)
        .order_by(func.count().desc())
        .all()
    )
    last_translated = base.with_entities(func.max(CatalanTranslation.translated_at)).scalar()

    target = 8710
    coverage = min(100.0, round(100.0 * total / target, 2)) if target else 0.0

    return CatalanStats(
        total=total,
        target=target,
        coverage_pct=coverage,
        by_doc_type=[DocTypeCount(doc_type=d[0], count=d[1]) for d in by_doc],
        by_category=[
            CategoryCount(category=c[0], category_en=c[1], count=c[2]) for c in by_cat
        ],
        by_engine=[EngineCount(engine=e[0], count=e[1]) for e in by_eng],
        last_translated_at=last_translated,
        licence="MIT",
    )


@router.get(
    "/{celex}",
    response_model=CatalanTranslationDetail,
    summary="Single Catalan translation by CELEX",
    description=(
        "Single record. Pass `?body=html` to inline the rendered Catalan HTML "
        "body. Otherwise the response carries metadata only and the consumer "
        "fetches `ca_url` directly."
    ),
)
async def get_catalan_translation(
    celex: str,
    body: Optional[str] = Query(None, description="Set to 'html' to inline the rendered HTML body."),
    db: Session = Depends(get_db),
) -> CatalanTranslationDetail:
    if not re.match(BINDING_CELEX_SQL.replace(r"\d", r"[0-9]"), celex):
        raise HTTPException(
            status_code=404,
            detail=f"CELEX {celex} is outside the binding-law corpus (sector 3, forms R/L/D).",
        )

    row = (
        db.query(CatalanTranslation)
        .filter(
            CatalanTranslation.celex == celex,
            CatalanTranslation.file_type == "main",
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"No Catalan translation for CELEX {celex}.")

    base = _row_to_item(row).model_dump()
    detail = CatalanTranslationDetail(**base, body_html=None)

    if body and body.lower() == "html":
        html_path = DISK_TRANSLATIONS_DIR / celex / "index.html"
        if html_path.is_file():
            try:
                detail.body_html = html_path.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                logger.warning("Could not read %s: %s", html_path, e)
        # If the file is missing on disk we leave body_html=None and let the
        # consumer fall back to ca_url. Don't 500 over an inlining miss.

    return detail
