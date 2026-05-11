"""
/api/v1/specialised/jrc-datasets — JRC Data Catalogue index.

The JRC catalogue at data.jrc.ec.europa.eu is a Blazor Server SPA
behind Imperva: all `/api/*` paths and machine-readable distribution
formats (RDF/XML/TTL/JSON-LD) are WAF-blocked (HTTP 200 + 245-byte
"Request Rejected" body). The only viable path is Playwright DOM
scraping.

This endpoint exposes the catalogue index (UUID, title, public URL)
backfilled by `backfill_eu_jrc_datasets.py`. Per-dataset detail
(description, distributions, publisher, dates) requires a slower
per-dataset Playwright fetch and is loaded lazily.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._body import body_threshold_param, deprecated_body
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/specialised/jrc-datasets", tags=["v1-specialised-ec-databases"])


class JrcDatasetItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    uuid: str
    title: Optional[str] = None
    description: Optional[str] = None
    publisher: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    modified: Optional[datetime] = None
    public_url: str
    has_body: bool = False


class JrcDatasetDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    uuid: str
    title: Optional[str] = None
    description: Optional[str] = None
    publisher: Optional[str] = None
    keywords: list[str] = Field(default_factory=list)
    issued: Optional[datetime] = None
    modified: Optional[datetime] = None
    distributions: Optional[list[dict]] = None
    public_url: str
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    body_source: Optional[str] = None
    body: Optional[str] = Field(None, description="DEPRECATED — back-compat alias.")
    fetched_at: Optional[datetime] = None


@router.get(
    "",
    response_model=PaginatedResponse[JrcDatasetItem],
    summary="JRC Data Catalogue index (scraped via Playwright)",
    description="""**What it does**
Returns the index of datasets published in the JRC Data Catalogue at `data.jrc.ec.europa.eu`. Each row is a single dataset with its UUID, title, keywords (when extracted), and the public URL.

The catalogue site is a Blazor Server SPA behind Imperva — all REST/RDF endpoints are WAF-blocked. We populate this table by **DOM-scraping** the rendered listing pages via Playwright. New datasets propagate to this index after the periodic re-scrape.

**When to use it**
- Discovering JRC scientific datasets (earth observation, environment, urban, demography, energy modelling, etc.).
- Building a JRC dataset picker for cross-portfolio research.

**Input**
- `q` (string, optional) — full-text search on title.
- `keyword` (string, optional) — exact tag match.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — parity.

**Try it**
```
GET /api/v1/specialised/jrc-datasets?q=fire&limit=20
```

**You get back**
A paginated envelope of `JrcDatasetItem` rows. Follow `public_url` for the canonical JRC dataset page.""",
)
async def list_datasets(
    request: Request,
    q: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[JrcDatasetItem]:
    where: list[str] = []
    params: dict = {}
    if q:
        where.append("to_tsvector('english', COALESCE(title,'')) @@ plainto_tsquery('english', :q)")
        params["q"] = q
    if keyword:
        where.append(":keyword = ANY(keywords)"); params["keyword"] = keyword
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total = int(db.execute(text(f"SELECT COUNT(*) FROM eu_jrc_datasets {where_sql}"), params).scalar() or 0)

    offset = (page - 1) * limit
    rows = db.execute(text(f"""
        SELECT uuid, title, description, publisher, keywords, modified, public_url, has_body
          FROM eu_jrc_datasets
          {where_sql}
         ORDER BY modified DESC NULLS LAST, title
         LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset}).mappings().all()

    items = [JrcDatasetItem(
        uuid=r["uuid"], title=r.get("title"),
        description=(r.get("description") or "")[:300] or None,
        publisher=r.get("publisher"),
        keywords=r.get("keywords") or [],
        modified=r.get("modified"),
        public_url=r["public_url"], has_body=False,
    ) for r in rows]

    return build_envelope(items=items, total=total, page=page, limit=limit,
        op_core_title="JRC Data Catalogue", op_core_type="JRC dataset",
        op_core_identifier=str(request.url),
        op_core_referenced_by=["/api/v1/specialised/jrc-datasets/{uuid}"])


@router.get(
    "/{uuid}",
    response_model=JrcDatasetDetail,
    summary="Single JRC dataset by UUID",
    description="""**What it does**
Returns the stored record for one JRC dataset. When the per-dataset detail scrape has run, the response also includes description, distributions list, publisher and dates. Until then, only the catalog-listing fields (title + URL) are populated.

**Input**
- `uuid` (path) — JRC dataset UUID (visible in the public URL).
- `body_threshold` (int, default 500).

**Try it**
```
GET /api/v1/specialised/jrc-datasets/fe46e164-241f-40c0-9614-442c6e25d380
```""",
)
async def get_dataset(
    request: Request,
    uuid: str = Path(..., description="JRC dataset UUID."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> JrcDatasetDetail:
    row = db.execute(text("SELECT * FROM eu_jrc_datasets WHERE uuid = :uuid LIMIT 1"),
                     {"uuid": uuid}).mappings().first()
    if not row:
        raise HTTPException(status_code=404,
            detail={"error": f"Dataset '{uuid}' not found.", "reason_code": "not_found"})

    body_text = row.get("body_text")
    has_body = bool(body_text and len(body_text) >= body_threshold)

    return JrcDatasetDetail(
        uuid=row["uuid"],
        title=row.get("title"),
        description=row.get("description"),
        publisher=row.get("publisher"),
        keywords=row.get("keywords") or [],
        issued=row.get("issued"),
        modified=row.get("modified"),
        distributions=row.get("distributions"),
        public_url=row["public_url"],
        has_body=has_body,
        body_html=row.get("body_html"),
        body_txt=body_text,
        body_source=row.get("body_source"),
        body=deprecated_body(body_text, row.get("body_html")),
        fetched_at=row.get("fetched_at"),
    )
