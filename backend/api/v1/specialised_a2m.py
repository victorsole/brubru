"""
/api/v1/specialised/access2markets — Access2Markets reference data.

Source APIs discovered via Playwright network capture:
  - https://webgate.ec.europa.eu/flows/public/v1/countries   (countries / MSes)
  - https://webgate.ec.europa.eu/flows/public/v1/lastupdate  (data freshness)
  - https://webgate.ec.europa.eu/nomen/public/v2/nomenclature/products  (Combined Nomenclature)

Live pass-through wrapper exposes the reference data needed to filter
the actual trade-flows view (tariffs / quotas / countries / products).

For trade-flow STATISTICS rows themselves, partners follow the A2M
public-facing UI at trade.ec.europa.eu/access-to-markets — the
underlying timeseries API requires per-call POST bodies with full
product + country + period selectors and is not yet wired up here.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict

from models.user import User

from ._body import body_threshold_param  # parity import
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/specialised/access2markets", tags=["v1-specialised-ec-databases"])

FLOWS_BASE = "https://webgate.ec.europa.eu/flows/public/v1"
NOMEN_BASE = "https://webgate.ec.europa.eu/nomen/public/v2"
UA = "Brubru/1.0 (proxy via brubru-production.up.railway.app)"


def _get(url: str) -> Any:
    req = urllib_request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib_request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib_error.HTTPError as e:
        raise HTTPException(status_code=502, detail={
            "error": f"Access2Markets upstream returned HTTP {e.code}",
            "reason_code": "upstream_error",
        })
    except urllib_error.URLError as e:
        raise HTTPException(status_code=504, detail={
            "error": f"Access2Markets upstream unreachable: {e.reason}",
            "reason_code": "upstream_unreachable",
        })


# ─────────────────────── response shapes ─────────────────────────────────


class CountryItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    code: str
    name: str
    iso: Optional[str] = None
    is_eu_ms: bool = False


class ProductItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    code: str
    description: Optional[str] = None
    level: Optional[int] = None
    parent_code: Optional[str] = None


class FreshnessInfo(BaseModel):
    last_update: Optional[str] = None


# ─────────────────────── endpoints ───────────────────────────────────────


@router.get(
    "/countries",
    response_model=PaginatedResponse[CountryItem],
    summary="Access2Markets countries (EU MSes + partners)",
    description="""**What it does**
Returns the country reference list used by the Access2Markets trade-statistics tool. Live pass-through to `webgate.ec.europa.eu/flows/public/v1/countries`. Each row has a 4-digit numeric DG TAXUD code, common English name, and ISO-2 country code.

**When to use it**
- Building a country picker for trade-flow queries.
- Mapping DG TAXUD's internal 4-digit code to ISO-2.

**Input**
- `eu_ms_only` (bool, optional) — true to return only the 27 EU Member States.
- `limit` (int, 1–500, default 250), `page` (int, default 1).

**Try it**
```
GET /api/v1/specialised/access2markets/countries?eu_ms_only=true
```

**You get back**
A paginated envelope of `CountryItem` rows.""",
)
async def list_countries(
    request: Request,
    eu_ms_only: bool = Query(False),
    limit: int = Query(250, ge=1, le=500),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),  # parity
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CountryItem]:
    # Pull both lists once so we can flag EU MSes accurately
    ms_url = f"{FLOWS_BASE}/countries?onlyMS=true&lang=EN&includeUK=false"
    full_url = f"{FLOWS_BASE}/countries?lang=EN&includeUK=false"

    if eu_ms_only:
        raw = _get(ms_url)
        ms_isos = {(c.get("iso") or "").upper() for c in raw if isinstance(c, dict)}
        items_all = raw
    else:
        ms_isos = {(c.get("iso") or "").upper() for c in _get(ms_url) if isinstance(c, dict)}
        items_all = _get(full_url)

    items_all = items_all or []
    total = len(items_all)
    offset = (page - 1) * limit
    items = [
        CountryItem(
            code=c.get("code") or "?",
            name=c.get("name") or "?",
            iso=c.get("iso"),
            is_eu_ms=(c.get("iso") or "").upper() in ms_isos,
        )
        for c in items_all[offset:offset + limit]
        if isinstance(c, dict)
    ]

    return build_envelope(items=items, total=total, page=page, limit=limit,
        op_core_title="Access2Markets countries", op_core_type="Country",
        op_core_identifier=str(request.url))


@router.get(
    "/products",
    response_model=PaginatedResponse[ProductItem],
    summary="Access2Markets Combined Nomenclature (CN) products",
    description="""**What it does**
Returns the EU Combined Nomenclature (CN) tree used by Access2Markets. Live pass-through to `webgate.ec.europa.eu/nomen/public/v2/nomenclature/products`. The CN classifies traded goods by 8-digit codes that aggregate under HS chapters (2-digit) and headings (4-digit).

**When to use it**
- Building a product picker for trade queries.
- Looking up the CN code for a product description.

**Input**
- `q` (string, optional) — case-insensitive substring on description.
- `level` (int, optional) — 2 (chapter), 4 (heading), 6 (sub-heading), 8 (CN code).
- `limit` (int, 1–500, default 100), `page` (int, default 1).

**Try it**
```
GET /api/v1/specialised/access2markets/products?q=wine&level=4
```

**You get back**
A paginated envelope of `ProductItem` rows.""",
)
async def list_products(
    request: Request,
    q: Optional[str] = Query(None),
    level: Optional[int] = Query(None, ge=2, le=10),
    limit: int = Query(100, ge=1, le=500),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),  # parity
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[ProductItem]:
    raw = _get(f"{NOMEN_BASE}/nomenclature/products?lang=EN")
    # Response is a list of nodes with {code, description, level, parentCode}
    nodes = raw if isinstance(raw, list) else (raw.get("nodes") or [])

    def matches(n: dict) -> bool:
        if q and q.lower() not in (n.get("description", "") or "").lower():
            return False
        if level is not None and int(n.get("level", -1) or -1) != level:
            return False
        return True

    filtered = [n for n in nodes if isinstance(n, dict) and matches(n)]
    total = len(filtered)
    offset = (page - 1) * limit
    items = [
        ProductItem(
            code=n.get("code") or "?",
            description=n.get("description"),
            level=n.get("level"),
            parent_code=n.get("parentCode"),
        )
        for n in filtered[offset:offset + limit]
    ]

    return build_envelope(items=items, total=total, page=page, limit=limit,
        op_core_title="Access2Markets CN products", op_core_type="CN product",
        op_core_identifier=str(request.url))


@router.get(
    "/last-update",
    response_model=FreshnessInfo,
    summary="Access2Markets data freshness",
    description="""**What it does**
Returns the timestamp of the most recent data refresh in the Access2Markets backend.

**Try it**
```
GET /api/v1/specialised/access2markets/last-update
```""",
)
async def last_update(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
) -> FreshnessInfo:
    raw = _get(f"{FLOWS_BASE}/lastupdate")
    return FreshnessInfo(last_update=str(raw) if not isinstance(raw, dict) else raw.get("lastUpdate"))
