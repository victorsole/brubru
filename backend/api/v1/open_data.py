"""
/api/v1/open-data/* — data.europa.eu open data (EU Publications Office portal).

Backed by ``open_data_datasets`` + ``open_data_catalogues`` (migration 112),
ingested by ``scripts/sync_open_data.py`` from the data.europa.eu open JSON API.

    /open-data/datasets             search EU datasets (DCAT) with download links
    /open-data/high-value-datasets  the High-Value Datasets subset (Open Data Directive)
    /open-data/catalogues           the ~90 EU + member-state data catalogues

Every row carries the five mandatory v1 datapoints; the dataset body lists the
metadata + the direct distribution download URLs.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional, List, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from core.database import get_db
from models.open_data import OpenDataDataset, OpenDataCatalogue
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope


datasets_router = APIRouter(prefix="/open-data/datasets", tags=["v1-open-data-datasets"])
hvd_router = APIRouter(prefix="/open-data/high-value-datasets", tags=["v1-open-data-high-value-datasets"])
catalogues_router = APIRouter(prefix="/open-data/catalogues", tags=["v1-open-data-catalogues"])


def _DESC(what: str, when: str, inp: str, gives: str, example: str) -> str:
    return f"""**What it does**
{what}

**When to use it**
{when}

**Input**
{inp}

**Try it**
```
{example}
```

**You get back**
{gives} The five envelope datapoints are filled: `public_url` (the data.europa.eu page), `body_txt`/`body_html` (metadata + download links), `document_date`, `creation_date`.

**Data freshness**
Synced from the data.europa.eu open JSON API (no scraping). Bodies are composed at ingest, so the API never calls data.europa.eu on the request path."""


# --------------------------------------------------------------------------- #
# Schemas                                                                     #
# --------------------------------------------------------------------------- #
class OpenDataDatasetItem(BaseModel):
    id: str
    dataset_id: str
    title: str
    description: Optional[str] = None
    publisher: Optional[str] = None
    catalogue: Optional[str] = None
    country: Optional[str] = None
    country_code: Optional[str] = None
    themes: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    formats: List[str] = Field(default_factory=list)
    is_hvd: bool = False
    distributions: List[Any] = Field(default_factory=list, description="[{format, url, title}] direct download links.")
    issued: Optional[date] = None
    # 5 datapoints
    public_url: Optional[str] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = Field(None, description="Last modified date.")
    creation_date: Optional[datetime] = None


class OpenDataCatalogueItem(BaseModel):
    id: str
    catalogue_id: str
    title: Optional[str] = None
    country: Optional[str] = None
    dataset_count: Optional[int] = None
    public_url: Optional[str] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = None
    creation_date: Optional[datetime] = None


def _to_dataset(r: OpenDataDataset) -> OpenDataDatasetItem:
    return OpenDataDatasetItem(
        id=str(r.id), dataset_id=r.dataset_id, title=r.title, description=r.description,
        publisher=r.publisher, catalogue=r.catalogue, country=r.country, country_code=r.country_code,
        themes=list(r.themes or []), keywords=list(r.keywords or []), formats=list(r.formats or []),
        is_hvd=bool(r.is_hvd), distributions=list(r.distributions or []), issued=r.issued,
        public_url=r.public_url, body_txt=r.body_txt, body_html=r.body_html,
        document_date=r.modified, creation_date=r.first_seen,
    )


def _to_catalogue(r: OpenDataCatalogue) -> OpenDataCatalogueItem:
    return OpenDataCatalogueItem(
        id=str(r.id), catalogue_id=r.catalogue_id, title=r.title, country=r.country,
        dataset_count=r.dataset_count, public_url=r.public_url,
        body_txt=r.body_txt, body_html=r.body_html,
        document_date=None, creation_date=r.first_seen,
    )


def _dataset_query(db, *, q, publisher, theme, country, format, catalogue, hvd,
                   published_from, published_to):
    query = db.query(OpenDataDataset)
    f = []
    if hvd is not None:
        f.append(OpenDataDataset.is_hvd.is_(bool(hvd)))
    if q:
        like = f"%{q}%"
        f.append(or_(OpenDataDataset.title.ilike(like),
                     OpenDataDataset.description.ilike(like),
                     OpenDataDataset.keywords.any(q)))
    if publisher:
        f.append(OpenDataDataset.publisher.ilike(f"%{publisher}%"))
    if theme:
        f.append(OpenDataDataset.themes.any(theme))
    if country:
        f.append(OpenDataDataset.country_code == country.lower())
    if format:
        f.append(OpenDataDataset.formats.any(format.upper()))
    if catalogue:
        f.append(OpenDataDataset.catalogue == catalogue)
    if published_from:
        f.append(OpenDataDataset.modified >= published_from)
    if published_to:
        f.append(OpenDataDataset.modified <= published_to)
    if f:
        query = query.filter(and_(*f))
    return query


# --------------------------------------------------------------------------- #
# 1. Datasets                                                                 #
# --------------------------------------------------------------------------- #
@datasets_router.get(
    "",
    response_model=PaginatedResponse[OpenDataDatasetItem],
    summary="EU open datasets — search data.europa.eu (with direct download links)",
    description=_DESC(
        "Searches the European Union open-data portal (data.europa.eu) — datasets published by EU institutions and member states, each with its publisher, catalogue, themes, formats, the High-Value-Dataset flag, and direct distribution download URLs.",
        "To find and pull EU open data on any policy topic — the single biggest EU open-data catalogue (1.9M+ datasets), with machine-readable download links per dataset.",
        "- `q` — full-text search over title / description / keywords.\n- `publisher` — substring match on the publisher.\n- `theme` — DCAT theme / category.\n- `country` — ISO country code of the publishing portal (e.g. `de`, `fr`).\n- `format` — distribution format (CSV, JSON, XML, ...).\n- `catalogue` — catalogue id.\n- `hvd` — true = only High-Value Datasets.\n- `published_from`, `published_to` — bound on the last-modified date.\n- `limit` (default 25, max 100), `page` (1-indexed).",
        "A `PaginatedResponse[OpenDataDatasetItem]`; each item carries `distributions` (download URLs), `formats`, `is_hvd`, `publisher`, `catalogue`, `themes`.",
        "GET /api/v1/open-data/datasets?q=air+quality&format=CSV",
    ),
)
async def list_datasets(
    request: Request,
    q: Optional[str] = Query(None),
    publisher: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
    catalogue: Optional[str] = Query(None),
    hvd: Optional[bool] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[OpenDataDatasetItem]:
    query = _dataset_query(db, q=q, publisher=publisher, theme=theme, country=country,
                           format=format, catalogue=catalogue, hvd=hvd,
                           published_from=published_from, published_to=published_to)
    total = query.count()
    rows = (query.order_by(OpenDataDataset.modified.desc().nullslast(),
                           OpenDataDataset.first_seen.desc())
            .offset((page - 1) * limit).limit(limit).all())
    data = [_to_dataset(r) for r in rows]
    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        op_core_title="EU open datasets", op_core_type="open dataset",
        op_core_identifier=str(request.url),
    )


@datasets_router.get(
    "/{item_id}",
    response_model=OpenDataDatasetItem,
    summary="One EU open dataset by id — full metadata + download links",
    description="Fetch a single data.europa.eu dataset by its Brubru UUID, with the full DCAT metadata and all distribution download URLs. 404 with `reason_code: not_found` if absent.",
)
async def get_dataset(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> OpenDataDatasetItem:
    row = db.query(OpenDataDataset).filter(OpenDataDataset.id == item_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No dataset with id {item_id}"})
    return _to_dataset(row)


# --------------------------------------------------------------------------- #
# 2. High-Value Datasets                                                      #
# --------------------------------------------------------------------------- #
@hvd_router.get(
    "",
    response_model=PaginatedResponse[OpenDataDatasetItem],
    summary="EU High-Value Datasets (Open Data Directive)",
    description=_DESC(
        "Returns the High-Value Datasets — the category the EU Open Data Directive designates as having high reuse potential (geospatial, earth observation/environment, meteorological, statistics, companies, mobility) — a filtered view of the open-data catalogue.",
        "To find the EU datasets the law itself flags as the most valuable to reuse, with their download links.",
        "- `q`, `publisher`, `theme`, `country`, `format`, `catalogue` — same as the datasets endpoint.\n- `published_from`, `published_to`.\n- `limit` (default 25, max 100), `page`.",
        "A `PaginatedResponse[OpenDataDatasetItem]` of High-Value Datasets (all `is_hvd=true`).",
        "GET /api/v1/open-data/high-value-datasets?theme=geospatial",
    ),
)
async def list_high_value_datasets(
    request: Request,
    q: Optional[str] = Query(None),
    publisher: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    format: Optional[str] = Query(None),
    catalogue: Optional[str] = Query(None),
    published_from: Optional[date] = Query(None),
    published_to: Optional[date] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[OpenDataDatasetItem]:
    query = _dataset_query(db, q=q, publisher=publisher, theme=theme, country=country,
                           format=format, catalogue=catalogue, hvd=True,
                           published_from=published_from, published_to=published_to)
    total = query.count()
    rows = (query.order_by(OpenDataDataset.modified.desc().nullslast())
            .offset((page - 1) * limit).limit(limit).all())
    data = [_to_dataset(r) for r in rows]
    return build_envelope(
        data, total=total, page=page, limit=limit,
        published_from=published_from, published_to=published_to,
        op_core_title="EU High-Value Datasets", op_core_type="high-value dataset",
        op_core_identifier=str(request.url),
    )


# --------------------------------------------------------------------------- #
# 3. Catalogues                                                               #
# --------------------------------------------------------------------------- #
@catalogues_router.get(
    "",
    response_model=PaginatedResponse[OpenDataCatalogueItem],
    summary="EU open-data catalogues — the data.europa.eu catalogue directory",
    description=_DESC(
        "Returns the data catalogues federated by data.europa.eu — the ~90 EU institution and member-state open-data catalogues (including the EU Legal Data Space ELDS and the Public Procurement Data Space PPDS).",
        "As a reference list of the data sources data.europa.eu aggregates, to scope a dataset search by `catalogue`.",
        "- `q` — substring match on the catalogue id / title.\n- `limit` (default 50, max 100), `page`.",
        "A `PaginatedResponse[OpenDataCatalogueItem]`.",
        "GET /api/v1/open-data/catalogues?q=eurostat",
    ),
)
async def list_data_catalogues(
    request: Request,
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[OpenDataCatalogueItem]:
    query = db.query(OpenDataCatalogue)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(OpenDataCatalogue.catalogue_id.ilike(like),
                                 OpenDataCatalogue.title.ilike(like)))
    total = query.count()
    rows = query.order_by(OpenDataCatalogue.catalogue_id).offset((page - 1) * limit).limit(limit).all()
    data = [_to_catalogue(r) for r in rows]
    return build_envelope(
        data, total=total, page=page, limit=limit,
        op_core_title="EU open-data catalogues", op_core_type="data catalogue",
        op_core_identifier=str(request.url),
    )


@catalogues_router.get(
    "/{item_id}",
    response_model=OpenDataCatalogueItem,
    summary="One EU open-data catalogue by id",
    description="Fetch a single data.europa.eu catalogue by its Brubru UUID. 404 with `reason_code: not_found` if absent.",
)
async def get_data_catalogue(
    item_id: str, user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> OpenDataCatalogueItem:
    row = db.query(OpenDataCatalogue).filter(OpenDataCatalogue.id == item_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No catalogue with id {item_id}"})
    return _to_catalogue(row)
