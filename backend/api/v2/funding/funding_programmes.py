"""EU funding programmes directory — /api/v2/funding/programmes.

The Commission's own classification of the 2021-2027 EU funding programmes
(6 MFF headings -> clusters -> programmes), with Brubru's coverage for each:
whether it is `covered` (and via which endpoint or the F&T calls feed), a `gap`,
or `skipped`. The single source of truth for "all EU funds" — Tenderator iterates
it to know the universe and where each fund's data lives.

Config-driven (backend/config/funding_programmes.json), refreshed when the EC
list changes. Follows the v2 item contract (5 datapoints + composed body).
Source: https://commission.europa.eu/funding-and-tenders/find-funding/eu-funding-programmes_en
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import Field
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from .cohesion_finances import _DataPoints

router = APIRouter()

_CONFIG = Path(__file__).resolve().parents[3] / "config" / "funding_programmes.json"
_EC_URL = "https://commission.europa.eu/funding-and-tenders/find-funding/eu-funding-programmes_en"


def _load() -> list[dict]:
    return json.loads(_CONFIG.read_text(encoding="utf-8")).get("programmes", [])


def _compose_body(p: dict) -> tuple[str, str]:
    cov = p["coverage"]
    if cov == "covered":
        how = (f"via the Brubru endpoint {p['endpoint']}" if p.get("endpoint")
               else "via the Funding & Tenders calls feed (/api/v2/funding/ft-calls-for-proposals)")
        cov_txt = f"Covered by Brubru {how}."
    elif cov == "gap":
        cov_txt = "Not yet covered by Brubru."
    else:
        cov_txt = "Deliberately not covered."
    txt = (f"{p['programme']} ({p['acronym']}). EC classification: heading "
           f"\"{p['heading']}\", cluster \"{p['cluster']}\". {cov_txt} Source: {p['source']}.")
    html = (f"<article><h3>{p['programme']} ({p['acronym']})</h3>"
            f"<p>EC heading: <strong>{p['heading']}</strong> &middot; cluster: {p['cluster']}.</p>"
            f"<p>{cov_txt}</p><p>Data source: {p['source']}.</p></article>")
    return txt, html


class ProgrammeItem(_DataPoints):
    programme: str
    acronym: str
    heading: str = Field(..., description="One of the 6 EC MFF headings.")
    cluster: str
    coverage: str = Field(..., description="covered | gap | skipped")
    via: Optional[str] = Field(None, description="endpoint | ft_calls | null")
    endpoint: Optional[str] = Field(None, description="The Brubru endpoint path, when covered by a dedicated endpoint.")
    source: str = Field(..., description="Where the data comes from / why it is a gap.")


def _to_item(p: dict, *, with_body: bool) -> ProgrammeItem:
    bt, bh = _compose_body(p)
    return ProgrammeItem(
        programme=p["programme"], acronym=p["acronym"], heading=p["heading"],
        cluster=p["cluster"], coverage=p["coverage"], via=p.get("via"),
        endpoint=p.get("endpoint"), source=p["source"],
        public_url=_EC_URL, body_txt=(bt if with_body else None),
        body_html=(bh if with_body else None),
    )


@router.get(
    "/programmes",
    response_model=PaginatedResponse[ProgrammeItem],
    tags=["v2-funding"],
    summary="EU funding programmes directory — the EC classification + Brubru coverage",
    description="""**What it does**
Returns the European Commission's own classification of the 2021-2027 EU funding programmes — the **6 MFF headings** (Single Market/Innovation/Digital; Cohesion and Values; Natural Resources and Environment; Migration and Border Management; Security and Defence; Neighbourhood and the World) broken into clusters and programmes — with **Brubru's coverage** for each: `covered` (and via which dedicated endpoint or the F&T calls feed), `gap`, or `skipped`.

**When to use it**
The single source of truth for "every EU fund". Iterate it to know the full universe of programmes and, for each, exactly where Brubru's data lives (which endpoint) or that it is a known gap. Built for Tenderator and any client that needs the canonical fund taxonomy.

**Input**
- `heading` — substring on the EC heading (e.g. `Cohesion`, `Natural Resources`).
- `cluster` — substring on the EC cluster.
- `coverage` — `covered` | `gap` | `skipped`.
- `q` — substring on the programme name, acronym or body.
- `limit` (default 100, max 200), `page` (1-indexed).

**Try it**
```
GET /api/v2/funding/programmes
GET /api/v2/funding/programmes?coverage=covered
GET /api/v2/funding/programmes?heading=Natural Resources
```

**You get back**
A `PaginatedResponse[ProgrammeItem]`. Each item carries `programme`, `acronym`, `heading`, `cluster`, `coverage`, `via`, `endpoint` (the Brubru path when covered by a dedicated endpoint), `source`, plus the 5 datapoints (`public_url` is the EC programmes page; `body_txt`/`body_html` null on the list — fetch the detail endpoint).

**Data freshness**
Static reference, updated when the Commission's programme list changes (config: `funding_programmes.json`).""",
)
async def list_programmes(
    request: Request,
    heading: Optional[str] = Query(None, description="EC heading substring"),
    cluster: Optional[str] = Query(None, description="EC cluster substring"),
    coverage: Optional[str] = Query(None, description="covered | gap | skipped"),
    q: Optional[str] = Query(None, description="Substring on programme name / acronym / body"),
    limit: int = Query(100, ge=1, le=200),
    include_body: bool = Query(
        False,
        description=(
            "Return `body_txt` / `body_html` on every item in the list. Off by "
            "default because bodies dominate the payload, but without it the "
            "only route to the text is one detail call PER ITEM, which is not "
            "a usable way to ingest a feed."
        ),
    ),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[ProgrammeItem]:
    progs = _load()
    if heading:
        progs = [p for p in progs if heading.lower() in p["heading"].lower()]
    if cluster:
        progs = [p for p in progs if cluster.lower() in p["cluster"].lower()]
    if coverage:
        progs = [p for p in progs if p["coverage"] == coverage.lower()]
    if q:
        ql = q.lower()
        progs = [p for p in progs if ql in p["programme"].lower() or ql in p["acronym"].lower() or ql in p["source"].lower()]
    total = len(progs)
    window = progs[(page - 1) * limit: (page - 1) * limit + limit]
    items = [_to_item(p, with_body=include_body) for p in window]
    return build_envelope(
        items, total=total, page=page, limit=limit,
        op_core_title="EU funding programmes directory (EC classification)",
        op_core_type="dataset", op_core_identifier="brubru:funding-programmes",
    )


@router.get(
    "/programmes/{acronym}",
    response_model=ProgrammeItem,
    tags=["v2-funding"],
    summary="Look up one EU funding programme in the classification",
    description="""**What it does**
Returns one EU funding programme from the EC classification by its acronym, with the full `body_txt` + `body_html`.

**Input**
- `acronym` (path) — e.g. `ERDF`, `Horizon Europe`, `EAGF`.

**Try it**
```
GET /api/v2/funding/programmes/ERDF
```

**You get back**
A single `ProgrammeItem` with the body populated, or HTTP 404 with `reason_code: not_found`.""",
)
async def get_programme(
    acronym: str = PathParam(..., description="Programme acronym, e.g. ERDF"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ProgrammeItem:
    for p in _load():
        if p["acronym"].lower() == acronym.lower():
            return _to_item(p, with_body=True)
    raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No programme with acronym {acronym}"})
