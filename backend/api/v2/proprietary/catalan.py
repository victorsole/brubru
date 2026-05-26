"""
Catalan translations source — /api/v2/proprietary/catalan/*.

Backend: Brubru's translation of the EU binding-law acquis into Catalan
(Softcatalà NMT, with a Claude Sonnet high-quality opt-in). Metadata lives in
the catalan_translations table; the rendered HTML lives on SiteGround.

LIVE — delegates to the v1 handlers in api.v1.catalan_translations (single
source of truth). Note: the v1 surface is open data (MIT, ungated); this v2
mirror sits behind the standard API-key contract (auth + scope + billing) for
consistency with the rest of v2. The ungated v1 endpoints remain available for
licence-faithful open redistribution.

Scope: read:laws (same mapping as the v1 catalan-translations surface).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from api.v1 import catalan_translations as _v1
from api.v1._body import body_threshold_param
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1.catalan_translations import (
    CatalanStats,
    CatalanTranslationDetail,
    CatalanTranslationItem,
)

router = APIRouter(prefix="/catalan", tags=["v2-proprietary-catalan"])


@router.get(
    "",
    response_model=PaginatedResponse[CatalanTranslationItem],
    summary="List EU binding laws translated into Catalan — the whole corpus, filterable",
    description="""**What it does**
Returns a paginated catalogue of binding EU legal acts (Regulations, Directives, Decisions) translated into Catalan by Brubru. With no filters this enumerates the **entire** binding-law corpus (thousands of acts), page by page.

**When to use it**
Browse, search, or sync the Catalan corpus — populate a search index, build a per-category dashboard, or pull updates incrementally with `updated_from`.

**Input**
- `q` — substring search across `title_ca`, `title_en`, `short_name`, `celex` (e.g. `GDPR`).
- `celex` — exact CELEX filter (e.g. `32016R0679`).
- `doc_type` — long form (`regulation`/`directive`/`decision`/`delegated`/`implementing`) or CELEX shorthand (`R`/`L`/`D`).
- `category` / `category_en` — exact name or slug (see `/catalan/stats` for names).
- `engine` — `softcatala` (default) or `sonnet`.
- `updated_from` / `updated_to` — incremental sync over `updated_at`.
- `limit` (1-200, default 50), `page` (1-indexed).

**Try it**
```
GET /api/v2/proprietary/catalan?q=GDPR&limit=3
GET /api/v2/proprietary/catalan?doc_type=R&limit=50
```

**You get back**
A `PaginatedResponse[CatalanTranslationItem]`. Per row: `celex`, `doc_type`, `short_name`, `title_ca`, `title_en`, `category`/`category_en`, `articles_count`, `recitals_count`, `html_size_bytes`, `engine`, `ca_url` (the canonical render on brubru.beresol.eu), `source_eurlex_url`, timestamps.

**Data freshness**
Brubru-curated (MIT-licensed). New translations are added via the `/catalan` skill; daily disk-to-DB sync keeps the table current.""",
)
async def list_catalan(
    request: Request,
    q: Optional[str] = Query(None, description="Substring search across title_ca, title_en, short_name, celex."),
    celex: Optional[str] = Query(None, description="Exact CELEX filter."),
    doc_type: Optional[str] = Query(None, description="regulation | directive | decision | delegated | implementing (or R/L/D shorthand)."),
    category: Optional[str] = Query(None, description="Brubru category (Catalan name) — see /catalan/stats."),
    category_en: Optional[str] = Query(None, description="Brubru category (English name)."),
    engine: Optional[str] = Query(None, description="softcatala | sonnet"),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync — rows with updated_at >= value."),
    updated_to: Optional[datetime] = Query(None, description="Incremental sync upper bound — rows with updated_at <= value."),
    limit: int = Query(50, ge=1, le=200, description="Items per page (default 50, max 200)."),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CatalanTranslationItem]:
    return await _v1.list_catalan_translations(
        request, q=q, celex=celex, doc_type=doc_type, category=category, category_en=category_en,
        engine=engine, updated_from=updated_from, updated_to=updated_to, limit=limit, page=page, db=db,
    )


@router.get(
    "/stats",
    response_model=CatalanStats,
    summary="Catalan translations — aggregate counts (coverage, by doc_type / category / engine)",
    description="""**What it does**
Returns aggregate counts of Catalan-translated EU acts grouped by `doc_type`, `category` (Catalan + English), and `engine`, plus the canonical 8,710 target and current coverage percentage.

**When to use it**
Build a coverage dashboard, verify ingestion before pulling pages, or discover the canonical category names to use as filters on the list endpoint.

**Input**
No parameters.

**Try it**
```
GET /api/v2/proprietary/catalan/stats
```

**You get back**
`CatalanStats`: `total`, `target` (8,710), `coverage_pct`, `by_doc_type[]`, `by_category[]` (use these names for the `category`/`category_en` filters), `by_engine[]`, `last_translated_at`, `licence` (`MIT`).

**Data freshness**
Live aggregate query over the `catalan_translations` table on each request.""",
)
async def catalan_stats(
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CatalanStats:
    return await _v1.catalan_translations_stats(db=db)


@router.get(
    "/{celex}",
    response_model=CatalanTranslationDetail,
    response_model_exclude_none=False,
    summary="One Catalan translation by CELEX — optional inlined body",
    description="""**What it does**
Returns one Catalan-translated EU act by its CELEX number, optionally with the full rendered body inlined.

**When to use it**
When you have a CELEX and want the Catalan translation's metadata, optionally with the rendered HTML body for display or downstream processing.

**Input**
- `celex` (path) — CELEX (sector 3, forms R/L/D), e.g. `32016R0679` (GDPR), `32024R1689` (AI Act).
- `body=html` (optional) — inlines the rendered Catalan HTML into `body_html` and a stripped plain-text version into `body_txt`.
- `body_threshold` (optional, default 500) — minimum char length for `has_body=true`.

**Try it**
```
GET /api/v2/proprietary/catalan/32016R0679
GET /api/v2/proprietary/catalan/32016R0679?body=html
```

**You get back**
All list fields plus `has_body`, `body_html`, `body_txt` (the last two only when `?body=html`). HTTP 404 when the CELEX is outside the binding-law corpus or has no Catalan translation yet.

**Data freshness**
Brubru-curated (MIT). Generated by the `/catalan` skill; new translations land via daily disk-to-DB sync.""",
)
async def get_catalan(
    celex: str,
    body: str = Query("html", description="`html` (default) inlines the rendered Catalan body; any other value returns metadata only."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CatalanTranslationDetail:
    # v2 populates body_html + body_txt by default (served from the DB cache).
    return await _v1.get_catalan_translation(celex, body=body, body_threshold=body_threshold, db=db)
