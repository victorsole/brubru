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
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import Field
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from api.v1._change_window import UpperBoundDatetime, validate_window
from .cohesion_finances import _DataPoints
from services.funding.shared_fields import cut_summary, with_body_names

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
    act = p.get("founding_act")
    act_txt = (f" Established by {act['title']}, published in the Official Journal on {act['published']}."
               if act else f" {p.get('founding_act_note') or ''}".rstrip())
    txt = (f"{p['programme']} ({p['acronym']}), {p.get('period') or ''}. EC classification: heading "
           f"\"{p['heading']}\", cluster \"{p['cluster']}\".{act_txt} {cov_txt} Source: {p['source']}.")
    html = (f"<article><h3>{p['programme']} ({p['acronym']})</h3>"
            f"<p>EC heading: <strong>{p['heading']}</strong> &middot; cluster: {p['cluster']}"
            f" &middot; period: {p.get('period') or ''}.</p>"
            + (f"<p>Established by {act['title']}, published in the Official Journal on {act['published']}.</p>"
               if act else (f"<p>{p['founding_act_note']}</p>" if p.get("founding_act_note") else ""))
            + f"<p>{cov_txt}</p><p>Data source: {p['source']}.</p></article>")
    return txt, html


class ProgrammeItem(_DataPoints):
    # Its own descriptions, not the cohesion lists' it inherited ("the programme's status /
    # adoption date", "the row's page on Cohesion Open Data"), which described nothing here.
    public_url: Optional[str] = Field(None, description="The programme's own page on the Commission's website (its funding or application page).")
    document_date: Optional[datetime] = Field(None, description=(
        "The Official Journal publication date of the act that established the programme, read at "
        "Cellar (Horizon Europe: Regulation (EU) 2021/695, OJ L 170, 12.5.2021). The act is named in "
        "the body. Null only for the Common Foreign and Security Policy, which no act establishes."))
    creation_date: Optional[datetime] = Field(None, description="When Brubru compiled the directory: the list's own date, the same on every programme.")
    updated_date: Optional[datetime] = Field(None, description="When the directory was last revised, the same on every programme (filter with updated_from / updated_to).")
    # The funding standard's shared fields (28 Oct 2026): a programme has no status, and Brubru holds no budget for it.
    item_type: str = Field("programme", description="Always programme.")
    title: Optional[str] = Field(None, description="The programme's name (as programme).")
    summary: Optional[str] = Field(None, description="The start of the body, cut at a word end near 300 characters.")
    status: Optional[str] = Field(None, description="Always null.")
    body_code: str = Field("commission", description="commission: the European Commission's classification and pages.")
    body_name: Optional[str] = Field(None, description="The body's name, as Brubru's directory of EU bodies gives it for body_code.")
    amount_eur: Optional[float] = Field(None, description="Always null: Brubru holds no budget per programme.")
    programme: str
    acronym: str
    period: Optional[str] = Field(None, description="The programming period, as the Funding & Tenders Portal groups programmes (e.g. 2021-2027).")
    heading: str = Field(..., description="One of the 6 EC MFF headings.")
    cluster: str
    coverage: str = Field(..., description="covered | gap | skipped")
    via: Optional[str] = Field(None, description="endpoint | ft_calls | null")
    endpoint: Optional[str] = Field(None, description="The Brubru endpoint path, when covered by a dedicated endpoint.")
    source: str = Field(..., description="Where the data comes from / why it is a gap.")


def _config_dates() -> tuple:
    """(created, updated) of the programme list: the config's own $created / $updated."""
    d = json.loads(_CONFIG.read_text(encoding="utf-8"))
    def _d(v):
        try:
            return datetime.fromisoformat(v).replace(tzinfo=timezone.utc) if v else None
        except ValueError:
            return None
    return _d(d.get("$created")), _d(d.get("$updated"))


def _published(p: dict) -> Optional[datetime]:
    """The founding act's OJ publication day (config `founding_act.published`, read at Cellar)."""
    act = p.get("founding_act") or {}
    try:
        return datetime.fromisoformat(act["published"]).replace(tzinfo=timezone.utc) if act.get("published") else None
    except ValueError:
        return None


def _to_item(p: dict, *, with_body: bool) -> ProgrammeItem:
    bt, bh = _compose_body(p)
    created, updated = _config_dates()
    return ProgrammeItem(
        title=p["programme"], summary=cut_summary(bt),
        programme=p["programme"], acronym=p["acronym"], heading=p["heading"],
        cluster=p["cluster"], coverage=p["coverage"], via=p.get("via"), period=p.get("period"),
        endpoint=p.get("endpoint"), source=p["source"],
        # The programme's own page (until 20 Oct 2026 every programme linked the same EC
        # list page); the list page when a programme has none.
        public_url=p.get("apply_url") or _EC_URL, body_txt=(bt if with_body else None),
        body_html=(bh if with_body else None),
        # The list was compiled on $created and last revised on $updated (it is a reference
        # file, not a feed): both were null on every programme until 20 Oct 2026.
        creation_date=created, updated_date=updated,
        document_date=_published(p),
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
- `period` — the programming period, e.g. `2021-2027`.
- `q` — substring on the programme name, acronym or body.
- `created_from` / `created_to`, `updated_from` / `updated_to` — incremental sync on the list's own dates (every programme carries them): the whole list when it was revised in the window, nothing otherwise.
- `limit` (default 50, max 200), `page` (1-indexed), `include_body` (default true).

**Try it**
```
GET /api/v2/funding/programmes
GET /api/v2/funding/programmes?coverage=covered
GET /api/v2/funding/programmes?heading=Natural Resources
```

**You get back**
A `PaginatedResponse[ProgrammeItem]`. Each item carries `programme`, `acronym`, `period`, `heading`, `cluster`, `coverage`, `via`, `endpoint` (the Brubru path when covered by a dedicated endpoint), `source`, plus the 5 datapoints (`document_date` is the OJ publication of the act that established the programme; `public_url` is the programme's own page on the Commission's website; `body_txt`/`body_html` on the list unless `include_body=false`).

**Data freshness**
Static reference, updated when the Commission's programme list changes (config: `funding_programmes.json`).""",
)
async def list_programmes(
    request: Request,
    heading: Optional[str] = Query(None, description="EC heading substring"),
    cluster: Optional[str] = Query(None, description="EC cluster substring"),
    coverage: Optional[str] = Query(None, description="covered | gap | skipped"),
    period: Optional[str] = Query(None, description="Programming period, e.g. 2021-2027 (as the Funding & Tenders Portal groups programmes)."),
    q: Optional[str] = Query(None, description="Substring on programme name / acronym / body"),
    created_from: Optional[datetime] = Query(None, description="List compiled on or after (ISO date or datetime, UTC): every programme carries the list's own dates."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="List compiled on or before; a bare date covers the whole day."),
    updated_from: Optional[datetime] = Query(None, description="List last revised on or after (ISO date or datetime, UTC). The incremental-sync filter."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="List last revised on or before; a bare date covers the whole day."),
    limit: int = Query(50, ge=1, le=200),
    include_body: bool = Query(
        True,
        description=(
            "Return `body_txt` / `body_html` on every item in the list (default true, "
            "the funding standard)."
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
    if period:
        progs = [p for p in progs if (p.get("period") or "").replace(" ", "") == period.replace(" ", "")]
    if q:
        ql = q.lower()
        progs = [p for p in progs if ql in p["programme"].lower() or ql in p["acronym"].lower() or ql in p["source"].lower()]
    # The change window: every programme carries the list's own $created / $updated, so a
    # window either keeps the whole list or none of it, which is what a sync needs to know.
    w = validate_window(created_from, created_to, updated_from, updated_to)
    created, updated = _config_dates()
    for key, value, keep in (("created_from", created, lambda v, b: v >= b), ("created_to", created, lambda v, b: v <= b),
                             ("updated_from", updated, lambda v, b: v >= b), ("updated_to", updated, lambda v, b: v <= b)):
        if w[key] is not None and (value is None or not keep(value, w[key])):
            progs = []
    total = len(progs)
    page_rows = progs[(page - 1) * limit: (page - 1) * limit + limit]
    items = with_body_names(db, [_to_item(p, with_body=include_body) for p in page_rows])
    return build_envelope(
        items, total=total, page=page, limit=limit,
        updated_from=w["updated_from"], updated_to=w["updated_to"],
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
            return with_body_names(db, [_to_item(p, with_body=True)])[0]
    raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No programme with acronym {acronym}"})
