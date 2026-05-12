"""
/api/v1/specialised/competition-cases — DG COMP cases (state aid, antitrust, merger).

Live pass-through to the EU Corporate Search backend discovered via
Playwright network capture:
  https://api.tech.ec.europa.eu/search-api/prod/rest/search

Public apiKey CS_PROD_ODSE_PROD is baked into the SPA (publicly visible
and meant for consumption). ~1,019,531 attachments across ~250,000
distinct cases as of 2026-05.

Live pass-through is the honest design choice — 1M+ rows is too many to
backfill, and the upstream API is fast (sub-second response) and stable.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any, Optional
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._body import body_threshold_param, deprecated_body
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/specialised/competition-cases", tags=["v1-specialised-ec-databases"])

UPSTREAM_BASE = "https://api.tech.ec.europa.eu/search-api/prod/rest/search"
API_KEY = "CS_PROD_ODSE_PROD"  # public — baked into the SPA
CASE_FRONTEND_TPL = "https://competition-cases.ec.europa.eu/cases/{case_number}"
UA = "Brubru/1.0 (proxy via brubru-production.up.railway.app)"


# ─────────────────────── upstream client ─────────────────────────────────


def _upstream_search(text: str, page_number: int, page_size: int,
                     case_instrument: Optional[str] = None,
                     group_by_case: bool = True) -> dict[str, Any]:
    """POST a search request to the EU Corporate Search backend."""
    qs = {
        "text": text,
        "pageNumber": str(page_number),
        "pageSize": str(page_size),
        "apiKey": API_KEY,
    }
    if group_by_case:
        qs["groupByField"] = "caseNumber"
    url = f"{UPSTREAM_BASE}?{urllib_parse.urlencode(qs)}"

    req = urllib_request.Request(url, method="POST", headers={
        "User-Agent": UA, "Accept": "application/json",
    })
    try:
        with urllib_request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib_error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            pass
        logger.warning("DG COMP upstream HTTP %s: %s", e.code, body)
        raise HTTPException(status_code=502, detail={
            "error": f"DG COMP upstream returned HTTP {e.code}",
            "reason_code": "upstream_error",
            "upstream_body": body,
        })
    except urllib_error.URLError as e:
        raise HTTPException(status_code=504, detail={
            "error": f"DG COMP upstream unreachable: {e.reason}",
            "reason_code": "upstream_unreachable",
        })


# ─────────────────────── response shapes ─────────────────────────────────


class CompetitionCaseItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    case_number: Optional[str] = None
    case_title: Optional[str] = None
    case_instrument: Optional[str] = Field(None, description="SA / M / AT — state aid, merger, antitrust.")
    case_dg: Optional[str] = None
    member_state: Optional[str] = None
    case_aid_category: Optional[str] = None
    case_objectives: Optional[list[str]] = None
    case_simplified_procedure: Optional[bool] = None
    case_cartel: Optional[bool] = None
    case_initiation_date: Optional[datetime] = None
    case_notification_date: Optional[datetime] = None
    case_measure_start_date: Optional[datetime] = None
    case_last_update_date: Optional[datetime] = None
    primary_attachment_reference: Optional[str] = None
    primary_attachment_url: Optional[str] = None
    public_url: Optional[str] = None
    has_body: bool = False
    # 5 mandatory Brubru v1 datapoints (public_url already present).
    body_txt: Optional[str] = Field(None, description="Plain-text composition: title + instrument + DG + member state + aid category + objectives + dates.")
    body_html: Optional[str] = Field(None, description="HTML composition of the same fields.")
    document_date: Optional[date] = Field(None, description="Last update date (date-only).")
    creation_date: Optional[datetime] = Field(None, description="Initiation date.")


def _flatten(meta_value: Any) -> Optional[str]:
    """Corporate-search puts most fields in single-element arrays."""
    if meta_value is None:
        return None
    if isinstance(meta_value, list):
        return meta_value[0] if meta_value else None
    return meta_value


def _to_dt(s: Any) -> Optional[datetime]:
    if not s:
        return None
    if isinstance(s, list):
        s = s[0] if s else None
    if not s:
        return None
    try:
        # 2023-01-04T23:00:00.000+0000  →  drop tz suffix for naive parsing
        return datetime.fromisoformat(str(s).replace("+0000", "+00:00").split(".")[0])
    except Exception:
        return None


def _to_bool(s: Any) -> Optional[bool]:
    if s is None:
        return None
    if isinstance(s, list):
        s = s[0] if s else None
    if isinstance(s, str):
        return s.lower() == "true"
    return None


def _row_from_search_hit(hit: dict) -> CompetitionCaseItem:
    meta = hit.get("metadata") or {}
    case_number = _flatten(meta.get("caseNumber") or [hit.get("groupById")])
    title = _flatten(meta.get("caseTitle")) or _flatten(meta.get("caseOriginalTitle"))
    last_upd = _to_dt(meta.get("caseLastUpdateDate"))
    initiation = _to_dt(meta.get("caseInitiationDate"))
    import html as _html
    lines = [title or case_number or "?"]
    parts_html = [f"<h2>{_html.escape(title or case_number or '?')}</h2>"]
    for k, v in [
        ("Case number", case_number),
        ("Instrument", _flatten(meta.get("caseInstrument"))),
        ("DG", _flatten(meta.get("caseDg"))),
        ("Member state", _flatten(meta.get("caseMemberState"))),
        ("Aid category", _flatten(meta.get("caseAidCategory"))),
        ("Objectives", ", ".join(meta.get("caseObjectives") or []) if isinstance(meta.get("caseObjectives"), list) else None),
        ("Initiation date", initiation),
        ("Last update", last_upd),
    ]:
        if not v: continue
        lines.append(f"{k}: {v}")
        parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
    return CompetitionCaseItem(
        case_number=case_number,
        case_title=title,
        case_instrument=_flatten(meta.get("caseInstrument")),
        case_dg=_flatten(meta.get("caseDg")),
        member_state=_flatten(meta.get("caseMemberState")),
        case_aid_category=_flatten(meta.get("caseAidCategory")),
        case_objectives=meta.get("caseObjectives") if isinstance(meta.get("caseObjectives"), list) else None,
        case_simplified_procedure=_to_bool(meta.get("caseSimplifiedProcedure")),
        case_cartel=_to_bool(meta.get("caseCartel")),
        case_initiation_date=initiation,
        case_notification_date=_to_dt(meta.get("caseNotificationDate")),
        case_measure_start_date=_to_dt(meta.get("caseMeasureStartDate")),
        case_last_update_date=last_upd,
        primary_attachment_reference=hit.get("reference"),
        primary_attachment_url=_flatten(meta.get("attachmentLink")),
        public_url=CASE_FRONTEND_TPL.format(case_number=case_number) if case_number else None,
        has_body=False,
        # 5 mandatory datapoints
        body_txt="\n".join(lines),
        body_html="<article>" + "".join(parts_html) + "</article>",
        document_date=last_upd.date() if last_upd else None,
        creation_date=initiation or last_upd,
    )


# ─────────────────────── list endpoint ───────────────────────────────────


@router.get(
    "",
    response_model=PaginatedResponse[CompetitionCaseItem],
    summary="DG COMP competition cases (state aid, antitrust, merger) — live pass-through",
    description="""**What it does**
Returns DG COMP competition cases by querying the EU Corporate Search backend directly. Covers state aid (SA), merger control (M) and antitrust (AT) cases — over 1 million attachments across ~250,000 distinct cases.

Live pass-through to `api.tech.ec.europa.eu/search-api/prod/rest/search`. Results are **grouped by `caseNumber`** so each row represents one case (its primary attachment metadata).

**When to use it**
- Tracking state-aid notifications and decisions.
- Researching merger reviews and antitrust prohibitions.
- Cross-referencing cases by Member State or aid category.

**Input**
- `q` (string, optional) — Lucene-style search. Default `*` (everything).
- `case_instrument` (string, optional) — `SA` (state aid), `M` (merger), `AT` (antitrust). Currently filtered at retrieve-time on `caseInstrument` metadata.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — contract parity.

**Try it**
```
GET /api/v1/specialised/competition-cases?case_instrument=SA&limit=20
GET /api/v1/specialised/competition-cases?q=microsoft
```

**You get back**
A paginated envelope of `CompetitionCaseItem` rows: case_number, case_title, instrument, DG, Member State, aid category, dates, primary attachment URL, public case URL. `has_body` is False on list rows.""",
)
async def list_cases(
    request: Request,
    q: str = Query("*", description="Lucene query, default '*' = all."),
    case_instrument: Optional[str] = Query(None, regex="^(SA|M|AT)$"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),  # parity
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CompetitionCaseItem]:
    text = q
    if case_instrument:
        text = f'({text}) AND caseInstrument:"{case_instrument}"'
    upstream = _upstream_search(text=text, page_number=page, page_size=limit, group_by_case=True)
    total = int(upstream.get("totalResults") or 0)
    hits = upstream.get("results") or []

    items = [_row_from_search_hit(h) for h in hits]

    return build_envelope(
        items=items, total=total, page=page, limit=limit,
        coverage_complete=False,
        op_core_title="DG COMP competition cases",
        op_core_type="Competition case",
        op_core_identifier=str(request.url),
    )


@router.get(
    "/{case_number}",
    response_model=CompetitionCaseItem,
    summary="Single competition case by case number",
    description="""**What it does**
Returns the case-level metadata for a specific DG COMP case (e.g. `SA.105841`, `M.10999`, `AT.40437`). Live pass-through query that filters the search backend by `caseNumber`.

**Input**
- `case_number` (path) — e.g. `SA.105841`.

**Try it**
```
GET /api/v1/specialised/competition-cases/SA.105841
```""",
)
async def get_case(
    request: Request,
    case_number: str = Path(..., description="Case number, e.g. SA.105841 or M.10999."),
    user: User = Depends(api_user_with_rate_limit),
) -> CompetitionCaseItem:
    upstream = _upstream_search(
        text=f'caseNumber:"{case_number}"',
        page_number=1, page_size=1, group_by_case=False,
    )
    hits = upstream.get("results") or []
    if not hits:
        raise HTTPException(status_code=404, detail={
            "error": f"Case '{case_number}' not found.",
            "reason_code": "not_found",
        })
    return _row_from_search_hit(hits[0])
