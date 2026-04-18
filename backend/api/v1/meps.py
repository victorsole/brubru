"""
/api/v1/meps — Members of the European Parliament (live from EP Open Data API).

No MEPs table in Brubru's DB today; this endpoint proxies the EP REST API v2
with a 6-hour in-memory cache so partners don't need their own EP integration.
"""

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models.user import User
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/meps", tags=["v1-meps"])

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


async def _fetch_list(country=None, group=None, name=None, limit=100, offset=0) -> List[Dict[str, Any]]:
    from services.api_clients.european_parliament_client import EuropeanParliamentClient

    key = f"list:{country}:{group}:{name}:{limit}:{offset}"
    cached = _cached(key)
    if cached is not None:
        return cached

    client = EuropeanParliamentClient()
    try:
        rows = await client.get_mep_list(country=country, group=group, name=name, limit=limit, offset=offset)
    finally:
        try:
            await client.close()
        except Exception:
            pass
    _put(key, rows)
    return rows


def _normalise(raw: Dict[str, Any]) -> MEPItem:
    # EP REST API v2 returns a nested dict; fields vary over time.
    return MEPItem(
        id=str(raw.get("id") or raw.get("identifier") or raw.get("mep_id") or ""),
        full_name=raw.get("fullName") or raw.get("full_name") or raw.get("name"),
        country=raw.get("country") or raw.get("countryOfRepresentation") or raw.get("country_code"),
        group=raw.get("politicalGroup") or raw.get("political_group") or raw.get("group"),
        role=raw.get("role"),
        profile_url=raw.get("profileUrl") or raw.get("profile_url") or raw.get("europarl_url"),
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
    limit: int = Query(20, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[MEPItem]:
    # EP API uses offset-based pagination
    offset = (page - 1) * limit
    try:
        raw = await _fetch_list(country=country, group=group, name=name, limit=limit, offset=offset)
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
    total = len(data) + offset  # EP API doesn't return total; best-effort
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
    key = f"profile:{mep_id}"
    cached = _cached(key)
    if cached is not None:
        return _normalise(cached)

    from services.api_clients.european_parliament_client import EuropeanParliamentClient
    client = EuropeanParliamentClient()
    try:
        profile = await client.get_mep_profile(mep_id)
    except Exception:
        profile = None
    finally:
        try:
            await client.close()
        except Exception:
            pass

    if not profile:
        raise HTTPException(
            status_code=404,
            detail={"error": "MEP not found", "reason_code": "not_found", "resource": "mep", "id": mep_id},
        )
    _put(key, profile)
    return _normalise(profile)
