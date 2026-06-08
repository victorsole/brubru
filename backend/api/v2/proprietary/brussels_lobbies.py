"""
Brussels lobbies source — /api/v2/proprietary/brussels-lobbies/*.

Brubru-proprietary product: a single ranked feed of what every Brussels-based EU
Transparency Register organisation is publishing. Nobody else aggregates this.

NATIVE — backed by brussels_lobby_profiles + brussels_lobby_news_items
(migration 117), derived from the official register (eu_transparency_register)
enriched with per-org news detection (RSS / Atom / sitemap / validated path
probe — services/scrapers/brussels_lobby_news.py + scripts/sync_brussels_lobbies.py).

Two resources:
    GET /brussels-lobbies            ranked org directory (type, profile, news flags)
    GET /brussels-lobbies/{code}/news  news/update items for one org
    GET /brussels-lobbies/types      org-type facet (helper for the directory filter)

Scope: read:proprietary. Structure contract identical to v1.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/brussels-lobbies", tags=["v2-proprietary-brussels-lobbies"])

_ORG_TYPES = {
    "ngo", "trade_association", "company", "think_tank", "consultancy", "law_firm",
    "trade_union", "academic", "religious", "public_authority", "third_country",
    "self_employed", "other",
}
_ORDERS = {"recent", "costs", "name"}


# --------------------------------------------------------------------------- #
# Response shapes                                                             #
# --------------------------------------------------------------------------- #

class _DataPoints(BaseModel):
    """The 5 mandatory Brubru datapoints — present even when null."""
    public_url: Optional[str] = Field(None, description="EU Transparency Register detail page for the organisation.")
    body_txt: Optional[str] = Field(None, description="Plain-text profile composition.")
    body_html: Optional[str] = Field(None, description="HTML profile composition.")
    document_date: Optional[date] = Field(None, description="Date of the organisation's most recent news item.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru last refreshed this profile row.")


class BrusselsLobby(_DataPoints):
    identification_code: str = Field(..., description="EU Transparency Register identification code.")
    original_name: Optional[str] = Field(None, description="Registered organisation name.")
    acronym: Optional[str] = None
    org_type: Optional[str] = Field(None, description="Normalised type: ngo / trade_association / company / think_tank / consultancy / law_firm / trade_union / academic / religious / public_authority / third_country / self_employed / other.")
    eutr_section: Optional[str] = Field(None, description="Official EUTR section (I–VI).")
    registration_category: Optional[str] = Field(None, description="Raw EUTR registration category.")
    for_profit: Optional[bool] = None
    is_global_corp: bool = Field(False, description="Multinational whose website newsroom is likely global PR, not EU-affairs news.")
    office_basis: Optional[str] = Field(None, description="Why it is Brussels-based: eu_office / head_office / both.")
    head_office_city: Optional[str] = None
    head_office_country: Optional[str] = None
    website_url: Optional[str] = None

    # The three requested flags + news availability
    has_org_data: bool = Field(True, description="Register profile data is present (always true).")
    has_news_data: bool = Field(False, description="The organisation publishes discoverable news/updates.")
    news_status: str = Field("unknown", description="active / none / blocked / error / unknown.")
    news_source_kind: Optional[str] = Field(None, description="rss / atom / sitemap / html.")
    news_feed_url: Optional[str] = Field(None, description="Discovered feed or news-index URL.")
    last_item_date: Optional[datetime] = Field(None, description="Timestamp of the most recent news item.")
    item_count: int = Field(0, description="Number of news items stored for this org.")

    # Influence signals
    ep_accredited_number: Optional[int] = None
    members_fte: Optional[float] = None
    costs_max: Optional[float] = Field(None, description="Upper bound of declared annual lobbying costs (EUR).")
    interests: list[str] = Field(default_factory=list, description="Declared policy areas of interest.")


class LobbyNewsItem(_DataPoints):
    identification_code: str
    title: Optional[str] = None
    summary: Optional[str] = None
    item_url: Optional[str] = None
    published_at: Optional[datetime] = None
    source_kind: Optional[str] = Field(None, description="rss / atom / sitemap / html.")


class OrgTypeFacet(BaseModel):
    org_type: Optional[str]
    eutr_section: Optional[str]
    organisations: int
    with_news: int


# --------------------------------------------------------------------------- #
# Row -> model                                                                #
# --------------------------------------------------------------------------- #

def _to_lobby(r) -> BrusselsLobby:
    li = r.get("last_item_date")
    return BrusselsLobby(
        identification_code=r["identification_code"],
        original_name=r.get("original_name"),
        acronym=r.get("acronym"),
        org_type=r.get("org_type"),
        eutr_section=r.get("eutr_section"),
        registration_category=r.get("registration_category"),
        for_profit=r.get("for_profit"),
        is_global_corp=bool(r.get("is_global_corp")),
        office_basis=r.get("office_basis"),
        head_office_city=r.get("head_office_city"),
        head_office_country=r.get("head_office_country"),
        website_url=r.get("website_url"),
        has_org_data=bool(r.get("has_org_data")),
        has_news_data=bool(r.get("has_news_data")),
        news_status=r.get("news_status") or "unknown",
        news_source_kind=r.get("news_source_kind"),
        news_feed_url=r.get("news_feed_url"),
        last_item_date=li,
        item_count=int(r.get("item_count") or 0),
        ep_accredited_number=r.get("ep_accredited_number"),
        members_fte=float(r["members_fte"]) if r.get("members_fte") is not None else None,
        costs_max=float(r["costs_max"]) if r.get("costs_max") is not None else None,
        interests=list(r.get("interests") or []),
        # 5 datapoints
        public_url=r.get("public_url"),
        body_txt=r.get("body_txt"),
        body_html=r.get("body_html"),
        document_date=li.date() if hasattr(li, "date") and li else None,
        creation_date=r.get("updated_at"),
    )


# --------------------------------------------------------------------------- #
# Directory                                                                   #
# --------------------------------------------------------------------------- #

@router.get(
    "",
    response_model=PaginatedResponse[BrusselsLobby],
    summary="Brussels lobbies — ranked directory of who is publishing what",
    description="""**What it does**
Returns a ranked directory of every **Brussels-based** organisation in the EU Transparency Register, enriched with whether that organisation actually publishes news/updates on its own website and when it last did. "Brussels-based" means it declares an EU office or a head office in Brussels. Each row carries its normalised type (NGO, trade association, company, think tank, consultancy, law firm, trade union, academic, religious, public authority, third-country entity), its register profile, and its news-availability flags. This view does not exist anywhere else.

**When to use it**
- Monitor what the Brussels advocacy ecosystem is saying, in one ranked feed.
- Find the most active lobbies on a policy area, or the freshest publishers in a given type.
- Pick an organisation, then read its items via `/brussels-lobbies/{code}/news`.

**Input**
- `q` — substring over organisation name + acronym.
- `org_type` — one of: ngo, trade_association, company, think_tank, consultancy, law_firm, trade_union, academic, religious, public_authority, third_country, self_employed, other.
- `eutr_section` — official EUTR section I–VI.
- `for_profit` (bool), `has_news` (bool — keep only orgs that publish news), `exclude_global_corp` (bool — drop multinationals' global newsrooms).
- `interest` — substring on the declared policy-interest list.
- `country` — head-office country (exact, case-insensitive).
- `min_costs` — minimum upper-bound declared lobbying costs (EUR).
- `order` — `recent` (default, freshest news first), `costs` (biggest spenders), `name`.
- `limit` (1–200, default 50), `page` (1-indexed).

**Try it**
```
GET /api/v2/proprietary/brussels-lobbies?has_news=true&order=recent
GET /api/v2/proprietary/brussels-lobbies?org_type=trade_association&interest=climate
```

**You get back**
A `PaginatedResponse[BrusselsLobby]`. Each item: identification code, name, acronym, org_type, eutr_section, for_profit, is_global_corp, office_basis, head office, website, the three flags (`has_org_data`, `has_news_data`, plus `news_status`), news source kind + feed URL + last-item date + item count, influence signals (EP passes, FTE, costs, interests), and the 5 datapoints (the composed profile body, register URL, last-item date).

**Data freshness**
Profiles refresh daily from the Transparency Register XML; news detection runs on a tiered crawl (RSS / Atom / sitemap / validated path probe).""",
)
async def list_brussels_lobbies(
    request: Request,
    q: Optional[str] = Query(None),
    org_type: Optional[str] = Query(None),
    eutr_section: Optional[str] = Query(None),
    for_profit: Optional[bool] = Query(None),
    has_news: Optional[bool] = Query(None),
    exclude_global_corp: Optional[bool] = Query(None),
    interest: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    min_costs: Optional[float] = Query(None),
    order: str = Query("recent"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[BrusselsLobby]:
    if org_type and org_type not in _ORG_TYPES:
        raise HTTPException(status_code=400, detail={
            "error": f"Unknown org_type {org_type!r}", "reason_code": "invalid_parameter",
            "valid_values": sorted(_ORG_TYPES)})
    if order not in _ORDERS:
        raise HTTPException(status_code=400, detail={
            "error": f"Unknown order {order!r}", "reason_code": "invalid_parameter",
            "valid_values": sorted(_ORDERS)})

    where: list[str] = []
    params: dict = {}
    if q:
        where.append("(original_name ILIKE :q OR acronym ILIKE :q)"); params["q"] = f"%{q}%"
    if org_type:
        where.append("org_type = :org_type"); params["org_type"] = org_type
    if eutr_section:
        where.append("eutr_section = :section"); params["section"] = eutr_section.upper()
    if for_profit is not None:
        where.append("for_profit = :fp"); params["fp"] = for_profit
    if has_news is not None:
        where.append("has_news_data = :hn"); params["hn"] = has_news
    if exclude_global_corp:
        where.append("is_global_corp = false")
    if interest:
        where.append("EXISTS (SELECT 1 FROM unnest(interests) i WHERE i ILIKE :interest)")
        params["interest"] = f"%{interest}%"
    if country:
        where.append("UPPER(head_office_country) = UPPER(:country)"); params["country"] = country
    if min_costs is not None:
        where.append("costs_max >= :min_costs"); params["min_costs"] = min_costs
    where_sql = "WHERE " + " AND ".join(where) if where else ""

    order_sql = {
        "recent": "last_item_date DESC NULLS LAST, costs_max DESC NULLS LAST",
        "costs": "costs_max DESC NULLS LAST, last_item_date DESC NULLS LAST",
        "name": "original_name ASC",
    }[order]

    total = int(db.execute(
        text(f"SELECT COUNT(*) FROM brussels_lobby_profiles {where_sql}"), params).scalar() or 0)
    offset = (page - 1) * limit
    rows = db.execute(text(f"""
        SELECT identification_code, original_name, acronym, org_type, eutr_section,
               registration_category, for_profit, is_global_corp, office_basis,
               head_office_city, head_office_country, website_url,
               has_org_data, has_news_data, news_status, news_source_kind, news_feed_url,
               last_item_date, item_count, ep_accredited_number, members_fte, costs_max,
               interests, public_url, body_txt, body_html, updated_at
          FROM brussels_lobby_profiles
          {where_sql}
         ORDER BY {order_sql}
         LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset}).mappings().all()

    items = [_to_lobby(r) for r in rows]
    return build_envelope(
        items=items, total=total, page=page, limit=limit,
        op_core_title="Brussels lobbies",
        op_core_type="Interest representative (Brussels-based)",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "/api/v2/proprietary/brussels-lobbies/{code}/news",
            "/api/v2/proprietary/brussels-lobbies/types",
        ],
    )


# --------------------------------------------------------------------------- #
# Types facet                                                                 #
# --------------------------------------------------------------------------- #

@router.get(
    "/types",
    response_model=list[OrgTypeFacet],
    summary="Brussels lobbies — organisation-type breakdown",
    description="""**What it does**
Returns each organisation type with how many Brussels-based orgs it has and how many of those publish discoverable news. Powers the directory's type filter.

**When to use it**
Build a type picker, or get a one-glance view of which parts of the Brussels ecosystem are most active online.

**Input**
None.

**Try it**
```
GET /api/v2/proprietary/brussels-lobbies/types
```

**You get back**
A flat list of `OrgTypeFacet` (org_type, eutr_section, organisations, with_news) sorted by organisation count.

**Data freshness**
Recomputed live from brussels_lobby_profiles.""",
)
async def list_types(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> list[OrgTypeFacet]:
    rows = db.execute(text("""
        SELECT org_type, MIN(eutr_section) AS eutr_section,
               COUNT(*) AS organisations,
               COUNT(*) FILTER (WHERE has_news_data) AS with_news
          FROM brussels_lobby_profiles
         GROUP BY org_type
         ORDER BY organisations DESC
    """)).mappings().all()
    return [OrgTypeFacet(org_type=r["org_type"], eutr_section=r["eutr_section"],
                         organisations=int(r["organisations"]), with_news=int(r["with_news"]))
            for r in rows]


# --------------------------------------------------------------------------- #
# Per-org news                                                                #
# --------------------------------------------------------------------------- #

@router.get(
    "/{code}/news",
    response_model=PaginatedResponse[LobbyNewsItem],
    summary="Brussels lobby — news / update items for one organisation",
    description="""**What it does**
Returns the dated news/update items Brubru has detected on one Brussels lobby's own website, newest first. Items come from the organisation's RSS/Atom feed or sitemap; organisations whose news section is HTML-only return an empty list while still being flagged as publishing news in the directory (use `news_feed_url` there to link out).

**When to use it**
- Read what a specific lobby has published recently.
- Build a per-organisation activity timeline.

**Input**
- `code` (path) — EU Transparency Register identification code (from the directory).
- `since` (date, optional) — only items published on/after this date.
- `limit` (1–100, default 50), `page` (1-indexed).

**Try it**
```
GET /api/v2/proprietary/brussels-lobbies/03543031681-83/news
```

**You get back**
A `PaginatedResponse[LobbyNewsItem]`: title, summary, item URL, published_at, source kind, and the 5 datapoints (item URL as public_url, composed body, published date).

**Data freshness**
Refreshed on the tiered news-detection crawl.""",
)
async def get_lobby_news(
    request: Request,
    code: str = PathParam(..., description="Transparency Register identification code."),
    since: Optional[date] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LobbyNewsItem]:
    exists = db.execute(text(
        "SELECT 1 FROM brussels_lobby_profiles WHERE identification_code = :c LIMIT 1"
    ), {"c": code}).first()
    if not exists:
        raise HTTPException(status_code=404, detail={
            "error": f"Brussels lobby '{code}' not found.", "reason_code": "not_found"})

    where = ["identification_code = :c"]
    params: dict = {"c": code}
    if since:
        where.append("published_at >= :since"); params["since"] = since
    where_sql = "WHERE " + " AND ".join(where)

    total = int(db.execute(text(
        f"SELECT COUNT(*) FROM brussels_lobby_news_items {where_sql}"), params).scalar() or 0)
    offset = (page - 1) * limit
    rows = db.execute(text(f"""
        SELECT identification_code, title, summary, item_url, published_at,
               source_kind, public_url, body_txt, body_html, fetched_at
          FROM brussels_lobby_news_items
          {where_sql}
         ORDER BY published_at DESC NULLS LAST, id DESC
         LIMIT :limit OFFSET :offset
    """), {**params, "limit": limit, "offset": offset}).mappings().all()

    items = []
    for r in rows:
        pa = r.get("published_at")
        items.append(LobbyNewsItem(
            identification_code=r["identification_code"],
            title=r.get("title"), summary=r.get("summary"), item_url=r.get("item_url"),
            published_at=pa, source_kind=r.get("source_kind"),
            public_url=r.get("public_url") or r.get("item_url"),
            body_txt=r.get("body_txt"), body_html=r.get("body_html"),
            document_date=pa.date() if hasattr(pa, "date") and pa else None,
            creation_date=r.get("fetched_at"),
        ))
    return build_envelope(
        items=items, total=total, page=page, limit=limit,
        op_core_title="Brussels lobby news items",
        op_core_type="News item",
        op_core_identifier=str(request.url),
        op_core_referenced_by=["/api/v2/proprietary/brussels-lobbies"],
    )
