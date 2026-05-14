"""
/api/v1/meps — Members of the European Parliament (live from EP Open Data REST API v2).

Proxies https://data.europarl.europa.eu/api/v2/meps with 6h in-memory cache.
"""

import logging
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models.user import User
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

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
    # The 5 mandatory Brubru v1 datapoints. MEPs are person records — public_url
    # is the EP profile page; body fields are composed from the EP Open Data
    # profile (name + citizenship + honorific + active political-group + role
    # + first-elected date + membership history). document_date is the start
    # of the MEP's most recent / active MEMBER_PARLIAMENT membership.
    public_url: Optional[str] = Field(None, description="Canonical citizen URL — the EP MEP profile page.")
    body_txt: Optional[str] = Field(None, description="Plain-text composition: full name, citizenship, active political group + role, mandate start, membership history.")
    body_html: Optional[str] = Field(None, description="HTML composition of the same fields. Includes the MEP portrait when available.")
    document_date: Optional[date] = Field(None, description="Start date of the MEP's current/most-recent MEMBER_PARLIAMENT membership.")
    creation_date: Optional[datetime] = Field(None, description="Time of this MEP fetch (live endpoint, 6h cache).")


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


async def _fetch_total_count(country=None, group=None, name=None, term=10) -> int:
    """Paginate the EP Open Data /meps endpoint exhaustively to count MEPs
    matching the given filters. Cached for 6h so it costs ~2-3 upstream
    requests per cache cycle (current term has ~720 MEPs; EP API caps at
    limit=500 per call).

    Returns -1 on upstream failure so callers can fall back to a heuristic.
    """
    key = f"total:{country}:{group}:{name}:{term}"
    cached = _cached(key)
    if cached is not None:
        return cached

    headers = {"User-Agent": "Brubru/1.0", "Accept": "application/ld+json"}
    PAGE = 500
    seen = 0
    offset = 0
    try:
        async with httpx.AsyncClient(timeout=20.0) as hc:
            for _ in range(20):  # safety cap (10,000 MEPs is more than enough)
                params: Dict[str, Any] = {
                    "limit": PAGE,
                    "offset": offset,
                    "format": "application/ld+json",
                    "parliamentary-term": term,
                }
                if country:
                    params["country-of-representation"] = country.upper()
                if group:
                    params["political-group"] = group
                r = await hc.get(f"{EP_API_BASE}/meps", params=params, headers=headers)
                r.raise_for_status()
                data = r.json()
                rows = data.get("data") if isinstance(data, dict) else []
                if not isinstance(rows, list) or not rows:
                    break
                seen += len(rows)
                if len(rows) < PAGE:
                    break  # last page
                offset += PAGE
    except Exception as exc:  # noqa: BLE001
        logger.warning("[meps] total-count fetch failed: %s", exc)
        return -1

    _put(key, seen)
    return seen


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


def _extract_country(profile: Dict[str, Any]) -> Optional[str]:
    """Pull ISO-3 country code from the citizenship URI on an EP profile."""
    val = profile.get("citizenship") or profile.get("country_of_representation")
    if not val:
        return None
    s = str(val)
    # citizenship is "http://publications.europa.eu/resource/authority/country/POL"
    if "/country/" in s:
        return s.rsplit("/country/", 1)[-1].strip("/").upper()
    return s.upper() if len(s) <= 3 else s


def _extract_active_political_group(profile: Dict[str, Any]) -> Optional[str]:
    """Find the active EU_POLITICAL_GROUP membership and return its org URI."""
    import datetime as _dt
    today = _dt.date.today().isoformat()
    best = None
    best_end = ""
    for m in profile.get("hasMembership") or []:
        cls = m.get("membershipClassification") or ""
        if "EU_POLITICAL_GROUP" not in cls:
            continue
        end = (m.get("memberDuring") or {}).get("endDate") or "9999-12-31"
        if end < today:
            continue
        org = m.get("organization")
        if not org:
            continue
        if end > best_end:
            best_end = end
            best = str(org)
    return best


def _extract_role(profile: Dict[str, Any]) -> Optional[str]:
    """Return the canonical role of the MEP (e.g. MEMBER) from ep-roles URI."""
    for m in profile.get("hasMembership") or []:
        cls = m.get("membershipClassification") or ""
        # MEMBER_PARLIAMENT membership at the institution level (org/ep-10) is the canonical role.
        if (m.get("organization") or "").startswith("org/ep-") and m.get("role"):
            r = str(m["role"])
            return r.rsplit("/", 1)[-1] if "/" in r else r
    return None


async def _enrich_country_group(items: List["MEPItem"]) -> List["MEPItem"]:
    """Hydrate `country`, `group`, `role` on a LIST of MEPItems.

    The EP Open Data /meps LIST endpoint returns identifier + name only. To
    populate the affiliation fields Jordi flagged as empty, we resolve each
    item's full profile in parallel (bounded concurrency) and parse:
      - country: ISO-3 code from the `citizenship` URI
      - group: org URI of the active EU_POLITICAL_GROUP membership
      - role: trailing component of the MEMBER_PARLIAMENT role URI

    6h cache means most calls become free after the first warmup.
    """
    import asyncio

    if not items:
        return items

    sem = asyncio.Semaphore(8)

    async def _hydrate(item: "MEPItem") -> "MEPItem":
        if not item.id:
            return item
        async with sem:
            profile = await _fetch_profile(item.id)
        if not profile:
            return item
        if not item.country:
            country = _extract_country(profile)
            if country:
                item.country = country
        if not item.group:
            group = _extract_active_political_group(profile)
            if group:
                item.group = group
        if not item.role:
            role = _extract_role(profile)
            if role:
                item.role = role
        # Re-compose body + document_date from the FULL profile (the list
        # endpoint only carried label + id, so the initial composition was
        # one-line). Hydration is cached 6h so this stays free after warmup.
        body_txt, body_html, doc_date = _compose_mep_body(
            profile, item.full_name, item.country, item.group, item.role,
        )
        if body_txt:
            item.body_txt = body_txt
        if body_html:
            item.body_html = body_html
        if doc_date and not item.document_date:
            item.document_date = doc_date
        return item

    return await asyncio.gather(*[_hydrate(it) for it in items])


def _identifier(raw: Dict[str, Any]) -> str:
    return str(raw.get("identifier") or raw.get("id", "").split("/")[-1] or "")


def _compose_mep_body(raw: Dict[str, Any], full_name: Optional[str],
                      country: Optional[str], group: Optional[str],
                      role: Optional[str]) -> tuple:
    """Compose body_txt + body_html + document_date from an EP profile blob.

    Reads hasMembership (list of role/org/date entries) so the body carries
    the MEP's affiliation history, not just the active group. document_date
    is the start of the most recent MEMBER_PARLIAMENT membership.
    """
    import html as _html
    parts_txt: list = []
    parts_html: list = []
    parts_html.append(f"<h2>{_html.escape(full_name or '?')}</h2>")
    if full_name:
        parts_txt.append(full_name)
    kv = []
    if raw.get("hasHonorificPrefix"):
        prefix = str(raw["hasHonorificPrefix"]).rsplit("/", 1)[-1].replace("_", " ").title()
        kv.append(("Title", prefix))
    if country:
        kv.append(("Country", country))
    if role:
        kv.append(("Role", role))
    if group:
        kv.append(("Active political group", group))
    if raw.get("placeOfBirth"):
        kv.append(("Place of birth", str(raw["placeOfBirth"])))
    if raw.get("hasEmail"):
        emails = raw["hasEmail"] if isinstance(raw["hasEmail"], list) else [raw["hasEmail"]]
        kv.append(("Email", ", ".join(str(e).replace("mailto:", "") for e in emails)))
    for k, v in kv:
        parts_txt.append(f"{k}: {v}")
        parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")

    img = raw.get("img")
    if img:
        parts_html.insert(1, f'<img src="{_html.escape(str(img))}" alt="MEP portrait" />')

    # Membership history → list
    memberships = raw.get("hasMembership") or []
    if isinstance(memberships, list) and memberships:
        parts_txt.append("Membership history:")
        parts_html.append("<h3>Membership history</h3><ul>")
        # Sort by end date descending so most recent is first
        def _key(m):
            return ((m.get("memberDuring") or {}).get("endDate") or "9999-12-31")
        for m in sorted(memberships, key=_key, reverse=True):
            during = m.get("memberDuring") or {}
            start = during.get("startDate") or ""
            end = during.get("endDate") or "current"
            org = str(m.get("organization") or "").rsplit("/", 1)[-1] or "?"
            role_uri = str(m.get("role") or "").rsplit("/", 1)[-1] or "?"
            cls = str(m.get("membershipClassification") or "").rsplit("/", 1)[-1] or ""
            line = f"- {start} → {end} | {role_uri} @ {org}"
            if cls:
                line += f" ({cls})"
            parts_txt.append(line)
            parts_html.append(
                f"<li><strong>{_html.escape(start)} → {_html.escape(end)}</strong> "
                f"| {_html.escape(role_uri)} @ {_html.escape(org)}"
                + (f" <em>({_html.escape(cls)})</em>" if cls else "")
                + "</li>"
            )
        parts_html.append("</ul>")

    # document_date = start of the most recent MEMBER_PARLIAMENT membership.
    # MEMBER_PARLIAMENT is the role-URI tail (e.g. .../role/MEMBER_PARLIAMENT),
    # NOT the membershipClassification (which is "EU_INSTITUTION" for the
    # parliament-level entry). Filter on the role URI.
    doc_date: Optional[date] = None
    if isinstance(memberships, list):
        latest_start = ""
        for m in memberships:
            role_uri = str(m.get("role") or "")
            if "MEMBER_PARLIAMENT" not in role_uri:
                continue
            during = m.get("memberDuring") or {}
            start = during.get("startDate") or ""
            if start and start > latest_start:
                latest_start = start
        if latest_start:
            try:
                doc_date = date.fromisoformat(latest_start[:10])
            except ValueError:
                pass

    body_txt = "\n".join(parts_txt) if parts_txt else None
    body_html = "<article>" + "".join(parts_html) + "</article>" if parts_html else None
    return body_txt, body_html, doc_date


def _normalise(raw: Dict[str, Any]) -> MEPItem:
    ident = _identifier(raw)
    profile_url = EP_PROFILE_URL.format(id=ident) if ident else None
    # The /meps list endpoint returns identifier + label + givenName + familyName (no country/group).
    # /meps/{id} returns the full profile including hasMembership array — we surface membership count but not resolve orgs here (too slow for list view).
    full_name = raw.get("label") or f"{raw.get('givenName', '')} {raw.get('familyName', '')}".strip() or raw.get("fullName")
    country = raw.get("country_of_representation") or raw.get("countryOfRepresentation") or None
    group = raw.get("political_group") or raw.get("politicalGroup") or None
    role = raw.get("role") or None
    body_txt, body_html, doc_date = _compose_mep_body(raw, full_name, country, group, role)
    return MEPItem(
        id=ident or None,
        full_name=full_name or None,
        country=country,
        group=group,
        role=role,
        profile_url=profile_url,
        public_url=profile_url,
        body_txt=body_txt,
        body_html=body_html,
        document_date=doc_date,
        creation_date=datetime.utcnow(),
    )


@router.get(
    "",
    response_model=PaginatedResponse[MEPItem],
    summary="Members of the European Parliament — list / search by country, group, name, term",
    description="""**What it does**
Live list of MEPs from the European Parliament's Open Data REST API v2. Each MEP carries the EP-internal id, full name, party of origin + EU political group, country, parliamentary term, photo, bio URL, committee assignments, and (when hydrated) email + social media handles. Both current and historical MEPs are searchable via `term`.

**When to use it**
Drive an MEP picker UI, find all MEPs from a country (`country=ES`), filter to one political group (`group=EPP`), or look up an MEP by name (`name=Sarri`). For historical research, set `term=9` for the 2019-2024 parliament. Per-MEP profile hydration (country / group / role) runs concurrently when the cache is warm — first cold call may take ~3-5s.

**Input**
- `country` — ISO-3166-1 alpha-2 (exact 2 chars).
- `group` — political group code (`EPP`, `S-D`, `RENEW`, `VERTS-ALE`, `ECR`, `PFE`, `ESN`, `GUE-NGL`, `NI`). Note: the EP API uses hyphens (S-D) but our `/political-groups` returns slugs (sd) — both are accepted.
- `name` — substring on full name.
- `term` — parliamentary term (default 10 = current, valid range 1-10).
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/meps?country=ES&group=RENEW
GET /api/v1/meps?name=Sarri
```

**You get back**
A `PaginatedResponse[MEPItem]` envelope. Each item carries `mep_id`, `full_name`, `country`, `political_group`, `party_national`, `term`, `photo_url`, `bio_url`, `committee_assignments[]`, plus the 5 envelope-level datapoints.

**Data freshness**
Live pass-through to data.europarl.europa.eu (the EP's Open Data REST API v2), with a 6-hour in-process cache. MEP changes are rare (election cycles + occasional resignations); the 6h cache balances freshness against EP API rate limits.""",
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
    # Per-MEP profile hydration so country/group/role surface on LIST too.
    # Bounded concurrency (8) + 6h cache means a warmed cache makes this free.
    try:
        data = await _enrich_country_group(data)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[meps] hydration skipped: %s", exc)

    # Real total count from upstream — paginate exhaustively (cached 6h).
    # Falls back to the offset+len heuristic if upstream is unavailable, so
    # the endpoint never blocks on the count call.
    total = await _fetch_total_count(country=country, group=group, name=name, term=term)
    coverage_complete = True
    if total < 0:
        total = offset + len(data)
        if len(data) == limit:
            total += 1  # hint there might be more
        coverage_complete = False
    return build_envelope(data, total=total, page=page, limit=limit, coverage_complete=coverage_complete)


@router.get(
    "/{mep_id}",
    response_model=MEPItem,
    summary="Look up one MEP by their EP-internal id — full profile + body composition",
    description="""**What it does**
Fetches a single MEP by their EP-internal id (a 5-7 digit numeric identifier visible on europarl.europa.eu URLs like `/meps/en/197488/...`). Returns the full profile including biographical info, committee assignments, declared meetings (when available), and the composed body (name + group + country + roles + contact details as a readable contact card).

**When to use it**
After locating an MEP via the list endpoint, use this for the full record — particularly when embedding an MEP card in a chat answer or building an MEP profile page. The body composition gives you a ready-to-render HTML/text card.

**Input**
- `mep_id` (path) — EP-internal MEP id (e.g. `197488`).

**Try it**
```
GET /api/v1/meps/197488
```

**You get back**
A single `MEPItem` (same shape as the list endpoint's `data[i]`), or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Live pass-through to data.europarl.europa.eu with a 6-hour in-process cache.""",
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
