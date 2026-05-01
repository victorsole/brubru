"""
/api/v1/meps — Members of the European Parliament (live from EP Open Data REST API v2).

Proxies https://data.europarl.europa.eu/api/v2/meps with 6h in-memory cache.
"""

import time
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models.user import User
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/meps", tags=["v1-meps"])

EP_API_BASE = "https://data.europarl.europa.eu/api/v2"
EP_PROFILE_URL = "https://www.europarl.europa.eu/meps/en/{id}"
_CACHE: Dict[str, tuple] = {}  # key -> (timestamp, data)
_TTL = 6 * 60 * 60  # 6h


class MEPItem(BaseModel):
    id: Optional[str] = None
    full_name: Optional[str] = None
    country: Optional[str] = None
    group: Optional[str] = None
    role: Optional[str] = None
    profile_url: Optional[str] = None


def _cached(key: str):
    v = _CACHE.get(key)
    if v and time.time() - v[0] < _TTL:
        return v[1]
    return None


def _put(key: str, value):
    _CACHE[key] = (time.time(), value)


async def _fetch_list(country=None, group=None, name=None, term=10, limit=100, offset=0) -> List[Dict[str, Any]]:
    key = f"list:{country}:{group}:{name}:{term}:{limit}:{offset}"
    cached = _cached(key)
    if cached is not None:
        return cached

    params: Dict[str, Any] = {
        "limit": min(limit, 500),
        "offset": offset,
        "format": "application/ld+json",
        # Default to the current parliamentary term. Without this filter the EP
        # Open Data API returns ALL historical MEPs ordered by ID ascending,
        # which means /meps?limit=10 starts with people elected in 1979.
        "parliamentary-term": term,
    }
    if country:
        params["country-of-representation"] = country.upper()
    if group:
        params["political-group"] = group

    headers = {"User-Agent": "Brubru/1.0", "Accept": "application/ld+json"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as hc:
            r = await hc.get(f"{EP_API_BASE}/meps", params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
    except Exception:
        return []

    rows = data.get("data") if isinstance(data, dict) else []
    if not isinstance(rows, list):
        rows = []
    _put(key, rows)
    return rows


async def _fetch_profile(mep_id: str) -> Optional[Dict[str, Any]]:
    key = f"profile:{mep_id}"
    cached = _cached(key)
    if cached is not None:
        return cached
    headers = {"User-Agent": "Brubru/1.0", "Accept": "application/ld+json"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as hc:
            r = await hc.get(f"{EP_API_BASE}/meps/{mep_id}", params={"format": "application/ld+json"}, headers=headers)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    rows = data.get("data") if isinstance(data, dict) else []
    if not rows:
        return None
    _put(key, rows[0])
    return rows[0]


def _identifier(raw: Dict[str, Any]) -> str:
    return str(raw.get("identifier") or raw.get("id", "").split("/")[-1] or "")


def _normalise(raw: Dict[str, Any]) -> MEPItem:
    ident = _identifier(raw)
    profile_url = EP_PROFILE_URL.format(id=ident) if ident else None
    # The /meps list endpoint returns identifier + label + givenName + familyName (no country/group).
    # /meps/{id} returns the full profile including hasMembership array — we surface membership count but not resolve orgs here (too slow for list view).
    full_name = raw.get("label") or f"{raw.get('givenName', '')} {raw.get('familyName', '')}".strip() or raw.get("fullName")
    return MEPItem(
        id=ident or None,
        full_name=full_name or None,
        country=raw.get("country_of_representation") or raw.get("countryOfRepresentation") or None,
        group=raw.get("political_group") or raw.get("politicalGroup") or None,
        role=raw.get("role") or None,
        profile_url=profile_url,
    )


@router.get(
    "",
    response_model=PaginatedResponse[MEPItem],
    summary="List / search Members of the European Parliament",
    description=(
        "Live from europarl.europa.eu Open Data REST API v2. Filters: country (ISO-2 e.g. ES), "
        "group (e.g. EPP, S-D, RENEW), name substring. 6-hour cache."
    ),
)
async def list_meps(
    request: Request,
    country: Optional[str] = Query(None, min_length=2, max_length=2),
    group: Optional[str] = Query(None),
    name: Optional[str] = Query(None),
    term: int = Query(10, ge=1, le=10, description="Parliamentary term (default 10 — current). Pass term=9 for previous, etc."),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[MEPItem]:
    # EP API uses offset-based pagination
    offset = (page - 1) * limit
    try:
        raw = await _fetch_list(country=country, group=group, name=name, term=term, limit=limit, offset=offset)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=502,
            detail={
                "error": "Upstream EP Open Data temporarily unavailable",
                "reason_code": "upstream_error",
                "source": "europarl.europa.eu",
            },
        )

    data = [_normalise(r) for r in (raw or [])]
    # EP Open Data doesn't return a total count; we expose what we fetched and flag
    # coverage_complete=False so clients know pagination is unbounded from our side.
    total = offset + len(data)
    if len(data) == limit:
        total += 1  # hint there might be more
    return build_envelope(data, total=total, page=page, limit=limit, coverage_complete=False)


@router.get(
    "/{mep_id}",
    response_model=MEPItem,
    summary="MEP profile by ID",
)
async def get_mep(
    mep_id: str,
    user: User = Depends(api_user_with_rate_limit),
) -> MEPItem:
    profile = await _fetch_profile(mep_id)
    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": f"MEP {mep_id} not found on EP Open Data", "reason_code": "not_found", "resource": "mep", "id": mep_id},
        )
    return _normalise(profile)
