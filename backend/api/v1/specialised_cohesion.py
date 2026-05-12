"""
/api/v1/specialised/cohesion-datasets — DG REGIO Cohesion Open Data catalog.

Backed by eu_cohesion_datasets, populated from Socrata catalog at
cohesiondata.ec.europa.eu/api/views.json. ~1,451 datasets covering ESF+,
ERDF, Cohesion Fund, Just Transition Fund, Interreg, RESTORE, RRF
indicators, allocations, categorisation, mid-term review.

This endpoint exposes the catalogue + dataset descriptions. Partners
follow `api_endpoint` to fetch the actual rows directly from Socrata.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
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

router = APIRouter(prefix="/specialised/cohesion-datasets", tags=["v1-specialised-ec-databases"])


class CohesionListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    socrata_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    download_count: Optional[int] = None
    view_count: Optional[int] = None
    last_updated_at: Optional[datetime] = None
    public_url: Optional[str] = None
    api_endpoint: Optional[str] = None
    has_body: bool = False
    # 5 mandatory Brubru v1 datapoints (public_url already present).
    body_txt: Optional[str] = Field(None, description="Plain-text composition: name + category + tags + counts + last_updated.")
    body_html: Optional[str] = Field(None, description="HTML composition of the same fields.")
    document_date: Optional[date] = Field(None, description="Last update date (date-only view of last_updated_at).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru last refreshed this row.")


class CohesionDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    socrata_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    attribution: Optional[str] = None
    download_count: Optional[int] = None
    view_count: Optional[int] = None
    row_count: Optional[int] = None
    last_updated_at: Optional[datetime] = None
    created_at_src: Optional[datetime] = None
    columns: Optional[list] = None
    public_url: Optional[str] = None
    api_endpoint: Optional[str] = None

    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    body_source: Optional[str] = None
    body: Optional[str] = Field(None, description="DEPRECATED — back-compat alias.")
    fetched_at: Optional[datetime] = None
    # 5 mandatory Brubru v1 datapoints (public_url already present above).
    document_date: Optional[date] = Field(None, description="Dataset last-update date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru last fetched this dataset (alias of fetched_at).")


class CohesionCategoryCount(BaseModel):
    category: Optional[str]
    datasets: int


@router.get(
    "",
    response_model=PaginatedResponse[CohesionListItem],
    summary="DG REGIO Cohesion Open Data datasets",
    description="""**What it does**
Returns the catalogue of datasets published by DG REGIO on the Cohesion Open Data Platform (Socrata-backed at `cohesiondata.ec.europa.eu`). Covers ESF+, ERDF, Cohesion Fund, Just Transition Fund, Interreg, RESTORE, and RRF indicators / allocations / categorisation / mid-term review.

This endpoint is a **catalogue**, not a row store. Each row is a *dataset*. To fetch the actual tabular rows of a given dataset, follow `api_endpoint` (Socrata REST) or `public_url` (HTML viewer).

**When to use it**
- Discovering what cohesion datasets exist before pulling rows.
- Filtering datasets by category (programming period, fund, indicator type).
- Tracking which datasets are most-viewed / recently updated.

**Input**
- `category` (string, optional) — Cohesion Open Data category (e.g. `2021 / 2027 Indicators`, `2014-2020`).
- `tag` (string, optional) — case-insensitive substring on tags.
- `q` (string, optional) — full-text search on name + description.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — kept for parity.

**Try it**
```
GET /api/v1/specialised/cohesion-datasets?category=2021%20%2F%202027%20Indicators&limit=20
```

**You get back**
A paginated envelope of `CohesionListItem` rows — each is a dataset, with the Socrata API endpoint to follow for actual rows.""",
)
async def list_cohesion(
    request: Request,
    category: Optional[str] = Query(None),
    tag: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CohesionListItem]:
    where: list[str] = []
    params: dict = {}
    if category:
        where.append("category = :category"); params["category"] = category
    if tag:
        where.append("EXISTS (SELECT 1 FROM unnest(tags) t WHERE t ILIKE :tag)")
        params["tag"] = f"%{tag}%"
    if q:
        where.append("to_tsvector('english', COALESCE(name,'') || ' ' || COALESCE(description,'')) "
                     "@@ plainto_tsquery('english', :q)")
        params["q"] = q
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total = int(db.execute(
        text(f"SELECT COUNT(*) FROM eu_cohesion_datasets {where_sql}"), params
    ).scalar() or 0)

    offset = (page - 1) * limit
    rows = db.execute(
        text(f"""
            SELECT socrata_id, name, description, category, tags,
                   download_count, view_count, last_updated_at,
                   public_url, api_endpoint, has_body
              FROM eu_cohesion_datasets
              {where_sql}
             ORDER BY view_count DESC NULLS LAST, name
             LIMIT :limit OFFSET :offset
        """),
        {**params, "limit": limit, "offset": offset},
    ).mappings().all()

    def _coh_body(r):
        import html as _html
        name = r.get("name") or r["socrata_id"]
        lines = [name]
        parts_html = [f"<h2>{_html.escape(name)}</h2>"]
        if r.get("description"):
            d = r["description"][:600]
            lines.append(d)
            parts_html.append(f"<p>{_html.escape(d)}</p>")
        for k, v in [
            ("Socrata ID", r["socrata_id"]),
            ("Category", r.get("category")),
            ("Tags", ", ".join(r.get("tags") or []) or None),
            ("Downloads", r.get("download_count")),
            ("Views", r.get("view_count")),
            ("Last updated", r.get("last_updated_at")),
        ]:
            if v is None or v == "": continue
            lines.append(f"{k}: {v}")
            parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
        return "\n".join(lines), "<article>" + "".join(parts_html) + "</article>"

    items = []
    for r in rows:
        bt, bh = _coh_body(r)
        lu = r.get("last_updated_at")
        items.append(CohesionListItem(
            socrata_id=r["socrata_id"],
            name=r.get("name"),
            description=(r.get("description") or "")[:300] or None,
            category=r.get("category"),
            tags=r.get("tags") or [],
            download_count=r.get("download_count"),
            view_count=r.get("view_count"),
            last_updated_at=lu,
            public_url=r.get("public_url"),
            api_endpoint=r.get("api_endpoint"),
            has_body=False,
            body_txt=bt,
            body_html=bh,
            document_date=lu.date() if hasattr(lu, "date") and lu else None,
            creation_date=r.get("fetched_at") or lu,
        ))

    return build_envelope(
        items=items, total=total, page=page, limit=limit,
        op_core_title="DG REGIO Cohesion Open Data datasets",
        op_core_type="Open Data dataset",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "/api/v1/specialised/cohesion-datasets/{socrata_id}",
            "/api/v1/specialised/cohesion-datasets/categories",
        ],
    )


@router.get(
    "/categories",
    response_model=list[CohesionCategoryCount],
    summary="Cohesion datasets by category",
    description="""**What it does**
Returns each Cohesion Open Data category with the count of datasets in it.

**Input**
None.

**Try it**
```
GET /api/v1/specialised/cohesion-datasets/categories
```

**You get back**
A flat list of `CohesionCategoryCount` objects, sorted by dataset count descending.""",
)
async def list_categories(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> list[CohesionCategoryCount]:
    rows = db.execute(text(
        """
        SELECT category, COUNT(*) AS n
          FROM eu_cohesion_datasets
         GROUP BY category
         ORDER BY n DESC
        """
    )).mappings().all()
    return [CohesionCategoryCount(category=r["category"], datasets=int(r["n"])) for r in rows]


@router.get(
    "/{socrata_id}",
    response_model=CohesionDetail,
    summary="Single Cohesion dataset (full metadata + body)",
    description="""**What it does**
Returns the full metadata for one Cohesion dataset, including its column schema, tags, attribution, download / view counts, and the composed body that combines description + tags + columns into a readable article.

**Input**
- `socrata_id` (path) — the Socrata dataset 4x4 ID, e.g. `7twf-r3rc`.
- `body_threshold` (int, default 500).

**Try it**
```
GET /api/v1/specialised/cohesion-datasets/7twf-r3rc
```

**You get back**
A `CohesionDetail` object with all metadata plus the body. Follow `api_endpoint` to fetch the actual rows from Socrata.""",
)
async def get_cohesion(
    request: Request,
    socrata_id: str = Path(..., description="Socrata 4x4 ID, e.g. 7twf-r3rc."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CohesionDetail:
    row = db.execute(text(
        "SELECT * FROM eu_cohesion_datasets WHERE socrata_id = :id LIMIT 1"
    ), {"id": socrata_id}).mappings().first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Dataset '{socrata_id}' not found.", "reason_code": "not_found"},
        )

    body_text = row.get("body_text")
    has_body = bool(body_text and len(body_text) >= body_threshold)

    return CohesionDetail(
        socrata_id=row["socrata_id"],
        name=row.get("name"),
        description=row.get("description"),
        category=row.get("category"),
        tags=row.get("tags") or [],
        attribution=row.get("attribution"),
        download_count=row.get("download_count"),
        view_count=row.get("view_count"),
        row_count=row.get("row_count"),
        last_updated_at=row.get("last_updated_at"),
        created_at_src=row.get("created_at_src"),
        columns=row.get("columns"),
        public_url=row.get("public_url"),
        api_endpoint=row.get("api_endpoint"),
        has_body=has_body,
        body_html=row.get("body_html"),
        body_txt=body_text,
        body_source=row.get("body_source"),
        body=deprecated_body(body_text, row.get("body_html")),
        fetched_at=row.get("fetched_at"),
        # 5 mandatory datapoints
        document_date=row.get("last_updated_at").date() if hasattr(row.get("last_updated_at"), "date") and row.get("last_updated_at") else None,
        creation_date=row.get("fetched_at"),
    )
