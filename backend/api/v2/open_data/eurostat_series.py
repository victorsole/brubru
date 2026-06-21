"""
Eurostat statistical time-series: /api/v2/open-data/eurostat-series/*.

Backend: Eurostat's dissemination JSON-stat 2.0 API
(https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}).

Two endpoints:
    /                  list the curated whitelist of sport + health (fitness-relevant) datasets
    /{dataset_code}    fetch one dataset's actual time-series payload (JSON-stat 2.0 verbatim
                       under .payload, plus a small composed summary)

The curated list focuses on what's useful for fitness / sport tech products
(participation, employment, household spend, BMI, overweight). Any other
Eurostat dataset code still works on the detail endpoint, but its metadata
fields (theme, description) will be blank since they are not in our whitelist.

Read-only. Auth + scope + rate limit + per-call euro debit via api_user_with_rate_limit.
Scope: read:publications (open EU data, same as the rest of /open-data/).
"""

from __future__ import annotations

import html as _html
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eurostat-series", tags=["v2-open-data-eurostat-series"])


# --------------------------------------------------------------------------- #
# Curated whitelist (sport + fitness-relevant health)                         #
# --------------------------------------------------------------------------- #

_ESTAT_DATA = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}"
_ESTAT_BROWSER = "https://ec.europa.eu/eurostat/databrowser/view/{code}/default/table?lang=en"

_THEME_SPORT = "Sport and physical activity"
_THEME_HEALTH = "Health, BMI, nutrition"
_THEME_LEISURE = "Household leisure expenditure"

_CURATED: List[Dict[str, Any]] = [
    {
        "code": "ilc_scp03",
        "name": "Persons participating in cultural or sport activities in the last 12 months",
        "theme": _THEME_SPORT,
        "description": "Share of adults reporting participation in cultural or sport activities at given frequencies in the last 12 months, broken down by sex, age, education. The headline EU sport participation series.",
        "unit_hint": "Percentage of population",
    },
    {
        "code": "hlth_ehis_pe9e",
        "name": "Performing health-enhancing physical activity (EHIS)",
        "theme": _THEME_SPORT,
        "description": "Share of population performing health-enhancing aerobic activity, by sex, age and educational attainment. Source: European Health Interview Survey.",
        "unit_hint": "Percentage of population",
    },
    {
        "code": "hlth_ehis_pe2e",
        "name": "Time spent on non-work-related aerobic physical activity (EHIS)",
        "theme": _THEME_SPORT,
        "description": "Time spent per week on non-work-related aerobic activity, by sex, age and educational attainment. Use to track adherence to WHO threshold (>=150 min/week).",
        "unit_hint": "Percentage of population by threshold",
    },
    {
        "code": "hlth_ehis_pe3e",
        "name": "Frequency of non-work-related physical activities (EHIS)",
        "theme": _THEME_SPORT,
        "description": "Share of population by how often they perform non-work-related physical activities (daily, weekly, monthly, never), by sex, age, education.",
        "unit_hint": "Percentage of population",
    },
    {
        "code": "hlth_ehis_pe6e",
        "name": "Walking and cycling at least 30 minutes per day (EHIS)",
        "theme": _THEME_SPORT,
        "description": "Share of population walking or cycling for at least 30 minutes per day, by sex, age and educational attainment. Active transport indicator.",
        "unit_hint": "Percentage of population",
    },
    {
        "code": "cult_emp_sex",
        "name": "Cultural employment by sex (umbrella that includes sport sub-activities)",
        "theme": _THEME_SPORT,
        "description": "Persons employed in cultural sectors (includes sport sub-activities under NACE 93). Closest umbrella series since Eurostat does not disseminate a standalone sport employment dataset.",
        "unit_hint": "Thousands of persons",
    },
    {
        "code": "cult_emp_n2",
        "name": "Cultural employment by NACE Rev. 2",
        "theme": _THEME_SPORT,
        "description": "Cultural employment broken down by NACE Rev. 2 activity codes, by country. Allows isolating the sport-relevant NACE categories.",
        "unit_hint": "Thousands of persons",
    },
    {
        "code": "hbs_str_t211",
        "name": "Structure of household consumption expenditure by COICOP",
        "theme": _THEME_LEISURE,
        "description": "Mean consumption expenditure of households by COICOP purpose, including category 09 (Recreation and culture) which covers gym memberships, sports goods, sports services. By country.",
        "unit_hint": "Per mille of total consumption expenditure",
    },
    {
        "code": "hbs_str_t223",
        "name": "Household consumption by income quintile and COICOP",
        "theme": _THEME_LEISURE,
        "description": "Structure of household consumption expenditure by income quintile and COICOP purpose. Inequality lens on recreation + sport spend.",
        "unit_hint": "Per mille of total consumption expenditure",
    },
    {
        "code": "hlth_ehis_bm1e",
        "name": "Body mass index (BMI) by sex, age and educational attainment (EHIS)",
        "theme": _THEME_HEALTH,
        "description": "Share of population by BMI class (underweight, normal, pre-obese, obese) by sex, age and educational attainment. Direct fitness-product input.",
        "unit_hint": "Percentage of population",
    },
    {
        "code": "hlth_ehis_de2",
        "name": "Body mass index (BMI) by sex, age and income quintile (EHIS)",
        "theme": _THEME_HEALTH,
        "description": "BMI distribution by income quintile, by sex and age. Use this rather than hlth_ehis_bm1e when you want the income lens.",
        "unit_hint": "Percentage of population",
    },
    {
        "code": "hlth_ehis_fv3e",
        "name": "Daily consumption of fruit and vegetables (EHIS)",
        "theme": _THEME_HEALTH,
        "description": "Share of population eating fruit and vegetables daily, by sex, age and educational attainment. Nutrition pillar adjacent to fitness.",
        "unit_hint": "Percentage of population",
    },
]

_CURATED_BY_CODE: Dict[str, Dict[str, Any]] = {row["code"]: row for row in _CURATED}


# --------------------------------------------------------------------------- #
# Pydantic models                                                             #
# --------------------------------------------------------------------------- #


class _DataPoints(BaseModel):
    """The 5 mandatory Brubru v1 datapoints."""
    public_url: Optional[str] = Field(None, description="Eurostat Data Browser URL for the dataset.")
    body_txt: Optional[str] = Field(None, description="Plain-text summary: null on list, populated on detail.")
    body_html: Optional[str] = Field(None, description="HTML summary: null on list, populated on detail.")
    document_date: Optional[date] = Field(None, description="Eurostat reported 'last update' for the dataset, if known.")
    creation_date: Optional[datetime] = Field(None, description="When this API response was generated.")


class EurostatSeriesItem(_DataPoints):
    """One Eurostat sport / health dataset (list or detail shape)."""
    code: str = Field(..., description="Eurostat dataset code, e.g. 'hlth_ehis_pe9e', 'sport_emp_sex'.")
    name: str = Field(..., description="Dataset short name.")
    theme: Optional[str] = Field(None, description="Brubru-curated theme: 'Sport and physical activity', 'Health, BMI, nutrition', 'Household leisure expenditure'.")
    description: Optional[str] = Field(None, description="One-paragraph plain-language description.")
    unit_hint: Optional[str] = Field(None, description="Unit of measurement hint (e.g. 'Percentage of population', 'Thousands of persons').")
    # Detail-only enrichment
    dimensions: Optional[List[Dict[str, Any]]] = Field(None, description="Dimension list with code, name, size, and a short sample of category labels. Detail only.")
    sample_observations: Optional[List[Dict[str, Any]]] = Field(None, description="Up to 10 representative {geo, time, value} observations. Detail only.")
    payload: Optional[Dict[str, Any]] = Field(None, description="Full JSON-stat 2.0 payload from Eurostat: included by default on detail (set `include_payload=false` to omit).")
    payload_truncated: Optional[bool] = Field(None, description="True when `payload` is omitted (`include_payload=false`) or upstream returned an unexpected shape.")


class ThemeFacet(BaseModel):
    theme: str
    dataset_count: int


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


async def _fetch_eurostat(code: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    url = _ESTAT_DATA.format(code=code)
    qp = {"format": "JSON", "lang": "en"}
    if params:
        qp.update(params)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        r = await client.get(url, params=qp)
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"Eurostat dataset '{code}' not found at {url}."})
    if r.status_code >= 500:
        raise HTTPException(status_code=502, detail={"reason_code": "upstream_unavailable", "message": f"Eurostat returned {r.status_code} for '{code}'."})
    if r.status_code != 200:
        raise HTTPException(status_code=r.status_code, detail={"reason_code": "upstream_error", "message": f"Eurostat error {r.status_code} for '{code}'."})
    try:
        return r.json()
    except Exception as e:
        raise HTTPException(status_code=502, detail={"reason_code": "upstream_parse_error", "message": f"Eurostat returned non-JSON for '{code}': {e}"})


def _extract_dimensions(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """JSON-stat 2.0: dimensions live under .dimension keyed by code, with .id giving order."""
    out: List[Dict[str, Any]] = []
    ids = payload.get("id") or []
    sizes = payload.get("size") or []
    dim_map = payload.get("dimension") or {}
    for idx, code in enumerate(ids):
        d = dim_map.get(code) or {}
        cat = (d.get("category") or {})
        labels = cat.get("label") or {}
        # First few category labels for orientation
        label_sample: List[str] = []
        for k, v in list(labels.items())[:8]:
            label_sample.append(f"{k}: {v}")
        out.append({
            "code": code,
            "name": d.get("label") or code,
            "size": sizes[idx] if idx < len(sizes) else None,
            "sample_categories": label_sample,
        })
    return out


def _extract_sample_observations(payload: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
    """
    Pull up to `limit` non-null {geo, time, value} observations from the JSON-stat payload.

    JSON-stat 2.0 stores values in either `.value` as a dict {flat_index: number} or as a
    flat array. We flat-index back to dimension coordinates using `.id` + `.size`, then
    project geo + time when those dims exist (most Eurostat datasets have both).
    """
    out: List[Dict[str, Any]] = []
    ids: List[str] = payload.get("id") or []
    sizes: List[int] = payload.get("size") or []
    dim_map: Dict[str, Any] = payload.get("dimension") or {}
    values = payload.get("value")
    if not ids or not sizes or values is None:
        return out

    def _coord_for(flat: int) -> List[int]:
        coords: List[int] = []
        rem = flat
        for s in reversed(sizes):
            coords.insert(0, rem % s if s else 0)
            rem = rem // s if s else 0
        return coords

    def _label(dim_code: str, pos: int) -> str:
        d = dim_map.get(dim_code) or {}
        cat = d.get("category") or {}
        idx_map = cat.get("index") or {}
        label_map = cat.get("label") or {}
        # JSON-stat index is dict key->position or list of keys; normalise to a list by position
        if isinstance(idx_map, dict):
            ordered = sorted(idx_map.items(), key=lambda kv: kv[1])
            keys = [k for k, _ in ordered]
        elif isinstance(idx_map, list):
            keys = idx_map
        else:
            keys = []
        if pos >= len(keys):
            return ""
        k = keys[pos]
        return label_map.get(k) or k

    def _key(dim_code: str, pos: int) -> str:
        d = dim_map.get(dim_code) or {}
        cat = d.get("category") or {}
        idx_map = cat.get("index") or {}
        if isinstance(idx_map, dict):
            ordered = sorted(idx_map.items(), key=lambda kv: kv[1])
            keys = [k for k, _ in ordered]
        elif isinstance(idx_map, list):
            keys = idx_map
        else:
            keys = []
        return keys[pos] if pos < len(keys) else ""

    iterable: List[Tuple[int, Any]] = []
    if isinstance(values, dict):
        for k, v in values.items():
            try:
                iterable.append((int(k), v))
            except (ValueError, TypeError):
                continue
    elif isinstance(values, list):
        iterable = [(i, v) for i, v in enumerate(values) if v is not None]

    for flat, v in iterable:
        if v is None:
            continue
        coords = _coord_for(flat)
        row: Dict[str, Any] = {"value": v}
        for d_idx, d_code in enumerate(ids):
            row[d_code] = _key(d_code, coords[d_idx]) if d_idx < len(coords) else None
            label_key = f"{d_code}_label"
            row[label_key] = _label(d_code, coords[d_idx]) if d_idx < len(coords) else None
        out.append(row)
        if len(out) >= limit:
            break
    return out


def _parse_extension_update(payload: Dict[str, Any]) -> Optional[date]:
    """Eurostat puts the last-update timestamp under .updated or .extension.updated."""
    upd = payload.get("updated") or (payload.get("extension") or {}).get("updated")
    if not upd or not isinstance(upd, str):
        return None
    try:
        return date.fromisoformat(upd[:10])
    except ValueError:
        return None


def _compose_body(meta: Dict[str, Any], payload: Dict[str, Any], sample: List[Dict[str, Any]], dims: List[Dict[str, Any]]) -> Tuple[str, str]:
    title = payload.get("label") or meta.get("name") or meta["code"]
    src = (payload.get("source") or "")
    upd = payload.get("updated") or ""
    lines: List[str] = [str(title)]
    if meta.get("theme"):
        lines.append(f"Theme: {meta['theme']}")
    if src:
        lines.append(f"Source: {src}")
    if upd:
        lines.append(f"Last update: {upd}")
    if meta.get("unit_hint"):
        lines.append(f"Unit: {meta['unit_hint']}")
    if meta.get("description"):
        lines.append("")
        lines.append(meta["description"])
    if dims:
        lines.append("")
        lines.append(f"Dimensions ({len(dims)}):")
        for d in dims:
            lines.append(f"  - {d['code']} ({d['name']}, size {d['size']})")
    if sample:
        lines.append("")
        lines.append(f"Sample observations ({len(sample)}):")
        for s in sample[:10]:
            geo = s.get("geo_label") or s.get("geo") or ""
            time_ = s.get("time") or ""
            val = s.get("value")
            unit_label = s.get("unit_label") or ""
            extra = f" [{unit_label}]" if unit_label else ""
            lines.append(f"  - {geo} {time_}: {val}{extra}")
    body_txt = "\n".join(lines)
    body_html = "<ul>" + "".join(
        f"<li>{_html.escape(str(line))}</li>" for line in lines if line
    ) + "</ul>"
    return body_txt, body_html


def _to_summary(meta: Dict[str, Any]) -> EurostatSeriesItem:
    return EurostatSeriesItem(
        code=meta["code"],
        name=meta["name"],
        theme=meta.get("theme"),
        description=meta.get("description"),
        unit_hint=meta.get("unit_hint"),
        public_url=_ESTAT_BROWSER.format(code=meta["code"]),
        body_txt=None,
        body_html=None,
        document_date=None,
        creation_date=datetime.utcnow(),
    )


# --------------------------------------------------------------------------- #
# Endpoints                                                                   #
# --------------------------------------------------------------------------- #


@router.get(
    "",
    response_model=PaginatedResponse[EurostatSeriesItem],
    summary="Brubru-curated Eurostat sport + fitness-relevant health datasets (10 series)",
    description="""**What it does**
Returns the curated set of Eurostat dissemination datasets useful for sport, fitness, and physical-activity products: aerobic + muscle-strengthening physical activity frequency, sport employment by sex / age, sport participation by income quintile, household spend on recreation + sport, BMI, daily fruit + vegetable intake, BMI trends. Each item ships its Eurostat code, theme, plain-language description, unit hint, and a public_url pointing at the Eurostat Data Browser.

**When to use it**
To enumerate Brubru's sport + health Eurostat coverage and pick which dataset to fetch in full via `/{dataset_code}`. The Eurostat dissemination API is public + free; Brubru's value here is the curated whitelist (saves you discovering relevant codes manually across thousands of Eurostat datasets) and the unified 5-datapoint contract.

**Input**
- `theme`: filter by curated theme. One of: `Sport and physical activity`, `Health, BMI, nutrition`, `Household leisure expenditure`.
- `q`: case-insensitive substring match on name + description.
- `limit` (1-100, default 50), `page` (1-indexed).

**Try it**
```
GET /api/v2/open-data/eurostat-series
GET /api/v2/open-data/eurostat-series?theme=Sport%20and%20physical%20activity
GET /api/v2/open-data/eurostat-series?q=BMI
```

**You get back**
A `PaginatedResponse[EurostatSeriesItem]` with 10 curated rows. Per item: `code`, `name`, `theme`, `description`, `unit_hint`, plus the 5 datapoints (`public_url` = Eurostat Data Browser; `body_txt` / `body_html` null on list, populated on detail; `document_date` null on list, set from Eurostat 'last update' on detail).

**Data freshness**
The curated whitelist is Brubru-managed. Each dataset's underlying observations come from Eurostat's dissemination API at fetch time on the detail endpoint, so values are always live.""",
)
async def list_eurostat_series(
    request: Request,
    theme: Optional[str] = Query(None, description="Curated theme filter (case-insensitive)."),
    q: Optional[str] = Query(None, description="Free-text filter over name + description."),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[EurostatSeriesItem]:
    rows = list(_CURATED)
    if theme:
        rows = [r for r in rows if (r.get("theme") or "").lower() == theme.lower()]
    if q:
        needle = q.lower()
        rows = [r for r in rows if needle in (r.get("name") or "").lower() or needle in (r.get("description") or "").lower()]
    total = len(rows)
    start = (page - 1) * limit
    end = start + limit
    items = [_to_summary(r) for r in rows[start:end]]
    return build_envelope(
        items=items,
        total=total,
        page=page,
        limit=limit,
        op_core_title="Brubru curated Eurostat sport + health datasets",
        op_core_type="Eurostat dataset list",
        op_core_identifier=str(request.url),
    )


@router.get(
    "/themes",
    response_model=List[ThemeFacet],
    summary="Distinct themes in the Brubru curated Eurostat list (with dataset counts)",
    description="""**What it does**
Returns the distinct themes across the curated Eurostat sport + health dataset list, each with the number of datasets under it. Drives faceted-search UIs.

**When to use it**
To populate a theme picker before calling `/api/v2/open-data/eurostat-series?theme=...`.

**Input**
None.

**Try it**
```
GET /api/v2/open-data/eurostat-series/themes
```

**You get back**
A list of `ThemeFacet` rows: `theme` (string), `dataset_count` (int).""",
)
async def list_themes(
    user: User = Depends(api_user_with_rate_limit),
) -> List[ThemeFacet]:
    counts: Dict[str, int] = {}
    for r in _CURATED:
        t = r.get("theme") or "Uncategorised"
        counts[t] = counts.get(t, 0) + 1
    return [ThemeFacet(theme=t, dataset_count=n) for t, n in sorted(counts.items(), key=lambda kv: -kv[1])]


@router.get(
    "/{dataset_code}",
    response_model=EurostatSeriesItem,
    summary="Fetch one Eurostat dataset's full JSON-stat 2.0 payload + composed summary",
    description="""**What it does**
Fetches a Eurostat dissemination dataset live from `ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}` and returns it under `payload` (verbatim JSON-stat 2.0) alongside Brubru's standard 5-datapoint envelope: a composed `body_txt` / `body_html` summary, the Eurostat Data Browser `public_url`, and `document_date` set from the upstream `updated` timestamp. Up to 10 sample observations are surfaced separately under `sample_observations` for quick orientation, and the dimension list under `dimensions`.

Any Eurostat dataset code works, not only the curated 10; codes outside the whitelist will have empty `theme` / `description` / `unit_hint` but full `payload`, `dimensions`, and `sample_observations`.

**When to use it**
To pull a Eurostat sport / fitness time series into your app (gym memberships, BMI per country, sport employment, physical-activity participation). One round-trip; you can render the verbatim JSON-stat payload yourself or use Brubru's `sample_observations` for a quick chart.

**Input**
- `dataset_code` (path): Eurostat dataset code (e.g. `hlth_ehis_pe9e`, `sport_emp_sex`, `hbs_str_t211`).
- `geo`: filter to a single country (ISO-2 / Eurostat geo code, e.g. `ES`, `FR`, `DE`, `EU27_2020`). Optional.
- `time`: filter to one year (e.g. `2023`). Optional.
- `sex`: filter to one sex code (e.g. `T`, `F`, `M`). Optional, only meaningful for datasets with a sex dimension.
- `include_payload`: include the full JSON-stat 2.0 `payload` (default `true`). Set to `false` to get only the summary + sample (smaller response).

**Try it**
```
GET /api/v2/open-data/eurostat-series/hlth_ehis_pe9e?geo=ES&time=2019
GET /api/v2/open-data/eurostat-series/sport_emp_sex?geo=EU27_2020
GET /api/v2/open-data/eurostat-series/hbs_str_t211?include_payload=false
```

**You get back**
An `EurostatSeriesItem` with `payload` (JSON-stat 2.0), `dimensions`, `sample_observations`, plus the 5 datapoints. 404 with `reason_code: not_found` if Eurostat returns 404. 502 with `reason_code: upstream_unavailable` if Eurostat is down.

**Data freshness**
Live every call. Eurostat's own `updated` field is surfaced as `document_date`.""",
)
async def get_eurostat_series(
    dataset_code: str = Path(..., description="Eurostat dataset code, e.g. 'hlth_ehis_pe9e' or 'sport_emp_sex'."),
    geo: Optional[str] = Query(None, description="Single geo code filter (e.g. ES, FR, EU27_2020)."),
    time: Optional[str] = Query(None, description="Single year filter, e.g. '2023'."),
    sex: Optional[str] = Query(None, description="Single sex code filter, e.g. T, F, M."),
    include_payload: bool = Query(True, description="Include the full JSON-stat 2.0 payload in the response."),
    user: User = Depends(api_user_with_rate_limit),
) -> EurostatSeriesItem:
    meta = _CURATED_BY_CODE.get(dataset_code, {"code": dataset_code, "name": dataset_code})

    params: Dict[str, str] = {}
    if geo:
        params["geo"] = geo
    if time:
        params["time"] = time
    if sex:
        params["sex"] = sex

    payload = await _fetch_eurostat(dataset_code, params or None)
    dims = _extract_dimensions(payload)
    sample = _extract_sample_observations(payload, limit=10)
    body_txt, body_html = _compose_body(meta, payload, sample, dims)
    upd = _parse_extension_update(payload)

    return EurostatSeriesItem(
        code=dataset_code,
        name=meta.get("name") or payload.get("label") or dataset_code,
        theme=meta.get("theme"),
        description=meta.get("description"),
        unit_hint=meta.get("unit_hint"),
        dimensions=dims,
        sample_observations=sample,
        payload=payload if include_payload else None,
        payload_truncated=(not include_payload),
        public_url=_ESTAT_BROWSER.format(code=dataset_code),
        body_txt=body_txt,
        body_html=body_html,
        document_date=upd,
        creation_date=datetime.utcnow(),
    )
