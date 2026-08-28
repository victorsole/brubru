"""Cohesion / structural funds — per-fund finance & allocation endpoints.

/api/v2/funding/<fund>            — list (cheap; body null)
/api/v2/funding/<fund>/{id}       — one allocation row in full (body_txt + body_html)

Backed by ``eu_cohesion_finances`` (DG REGIO Cohesion Open Data Platform, Socrata
dataset 9qee-iv7c, "2021-2027 Financial Plan details by year"). Each row is one
programme (CCI) x financial-allocation-category, with the annual 2021-2027
breakdown + the total EU allocation.

Follows the standard v2 item contract: every item carries the 5 datapoints
(public_url, body_txt, body_html, document_date, creation_date); body is full on
the detail endpoint and null on the list. Built one fund at a time via the
``register_fund`` factory.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

router = APIRouter()


class _DataPoints(BaseModel):
    """The 5 mandatory Brubru datapoints — present even when null."""
    public_url: Optional[str] = Field(None, description="Canonical URL of the fund's Cohesion Open Data page.")
    body_txt: Optional[str] = Field(None, description="Plain-text body (full on detail; null on list).")
    body_html: Optional[str] = Field(None, description="HTML body (full on detail; null on list).")
    document_date: Optional[datetime] = Field(None, description="The programme's status / adoption date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested the row.")


class CohesionFinanceItem(_DataPoints):
    id: int = Field(..., description="Stable Brubru row id (use it on the detail endpoint).")
    fund: str
    ms: Optional[str] = None
    cci: Optional[str] = None
    cci_title: Optional[str] = None
    dg: Optional[str] = None
    status: Optional[str] = None
    status_date: Optional[date] = None
    financial_allocation_category: Optional[str] = None
    y2021: Optional[float] = None
    y2022: Optional[float] = None
    y2023: Optional[float] = None
    y2024: Optional[float] = None
    y2025: Optional[float] = None
    y2026: Optional[float] = None
    y2027: Optional[float] = None
    total_non_flexible_amount: Optional[float] = None
    total_flexible_amount: Optional[float] = None
    total: Optional[float] = None
    share_of_fa_in_total: Optional[float] = None


_STRUCT = (
    "fund, ms, cci, cci_title, dg, status, status_date, financial_allocation_category, "
    "y2021, y2022, y2023, y2024, y2025, y2026, y2027, "
    "total_non_flexible_amount, total_flexible_amount, total, share_of_fa_in_total"
)
_LIST_COLS = f"id, public_url, document_date, created_at AS creation_date, {_STRUCT}"
_DETAIL_COLS = f"id, public_url, body_txt, body_html, document_date, created_at AS creation_date, {_STRUCT}"


def _row_to_item(r, *, with_body: bool) -> CohesionFinanceItem:
    d = dict(r)
    if not with_body:
        d["body_txt"] = None
        d["body_html"] = None
    return CohesionFinanceItem(**d)


def register_fund(*, slug: str, fund_code: str, fund_name: str, blurb: str, tag: str = "v2-funding") -> None:
    """Add list `GET /api/v2/funding/<slug>` + detail `GET /api/v2/funding/<slug>/{id}`."""

    @router.get(
        f"/{slug}",
        response_model=PaginatedResponse[CohesionFinanceItem],
        tags=[tag],
        summary=f"{fund_name} ({fund_code}) — 2021-2027 financial plan by programme",
        description=f"""**What it does**
Lists the 2021-2027 financial allocations of the **{fund_name} ({fund_code})**, one row per operational programme (CCI) and financial-allocation category. {blurb} Each row carries the Member State, programme title and status, lead DG, the year-by-year breakdown (2021-2027) and the total EU allocation, plus the 5 datapoints (`body_txt`/`body_html` are null here — fetch the detail endpoint for the full body).

**When to use it**
To see how much {fund_code} money each Member State and programme is allocated and how it is profiled across the years. This is the allocation (planning) side.

**Input**
- `ms` — Member State ISO code (e.g. `PL`, `ES`, `DE`).
- `status` — programme status substring (e.g. `Adopted`).
- `q` — substring on the programme title or the composed body.
- `limit` (default 50, max 200), `page` (1-indexed).

**Try it**
```
GET /api/v2/funding/{slug}
GET /api/v2/funding/{slug}?ms=ES
```

**You get back**
A `PaginatedResponse[CohesionFinanceItem]` envelope sorted by total allocation. Each item carries `id`, `public_url`, `document_date`, `creation_date`, the structured fields (`fund`, `ms`, `cci`, `cci_title`, `y2021`..`y2027`, `total`, ...) and `body_txt`/`body_html` = null. Use the detail endpoint for the full body.

**Data freshness**
Synced weekly (Sunday 05:00 UTC) from the DG REGIO Cohesion Open Data Platform (`cohesiondata.ec.europa.eu`, dataset 9qee-iv7c).""",
    )
    async def list_fund(  # noqa: ANN202
        request: Request,
        ms: Optional[str] = Query(None, description="Member State ISO code"),
        status: Optional[str] = Query(None, description="Programme status substring"),
        q: Optional[str] = Query(None, description="Substring on the programme title or body"),
        limit: int = Query(50, ge=1, le=200),
        page: int = Query(1, ge=1),
        include_body: bool = Query(
            False,
            description=(
                "Return `body_txt` / `body_html` on every item in the list. Off by "
                "default because bodies dominate the payload, but without it the "
                "only route to the text is one detail call PER ITEM, which is not "
                "a usable way to ingest a feed."
            ),
        ),
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> PaginatedResponse[CohesionFinanceItem]:
        where = ["fund = :fund"]
        params: dict = {"fund": fund_code}
        if ms:
            where.append("ms ILIKE :ms"); params["ms"] = ms
        if status:
            where.append("status ILIKE :status"); params["status"] = f"%{status}%"
        if q:
            where.append("(cci_title ILIKE :q OR body_txt ILIKE :q)"); params["q"] = f"%{q}%"
        where_sql = " AND ".join(where)

        total = db.execute(text(f"SELECT COUNT(*) FROM eu_cohesion_finances WHERE {where_sql}"), params).scalar() or 0
        params2 = {**params, "limit": limit, "offset": (page - 1) * limit}
        rows = db.execute(
            text(f"SELECT {_DETAIL_COLS if include_body else _LIST_COLS} FROM eu_cohesion_finances WHERE {where_sql} "
                 f"ORDER BY total DESC NULLS LAST, cci LIMIT :limit OFFSET :offset"), params2,
        ).mappings().all()
        items = [_row_to_item(r, with_body=include_body) for r in rows]
        return build_envelope(
            items, total=total, page=page, limit=limit,
            op_core_title=f"{fund_name} ({fund_code}) 2021-2027 financial plan",
            op_core_type="dataset", op_core_identifier=f"cohesiondata:9qee-iv7c:{fund_code}",
        )

    @router.get(
        f"/{slug}/{{row_id}}",
        response_model=CohesionFinanceItem,
        tags=[tag],
        summary=f"Look up one {fund_code} allocation row in full",
        description=f"""**What it does**
Returns one {fund_name} ({fund_code}) financial-plan row by its Brubru id, including the full `body_txt` + `body_html`.

**When to use it**
After locating a programme allocation via the list endpoint, fetch the full record (with the composed human-readable body).

**Input**
- `row_id` (path) — the `id` from the list endpoint.

**Try it**
```
GET /api/v2/funding/{slug}/123
```

**You get back**
A single `CohesionFinanceItem` with `body_txt` + `body_html` populated, or HTTP 404 with `reason_code: not_found`.

**Data freshness**
Same weekly sync as the list endpoint.""",
    )
    async def get_fund_row(  # noqa: ANN202
        row_id: int = Path(..., description="Brubru row id from the list endpoint"),
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> CohesionFinanceItem:
        r = db.execute(
            text(f"SELECT {_DETAIL_COLS} FROM eu_cohesion_finances WHERE id = :id AND fund = :fund"),
            {"id": row_id, "fund": fund_code},
        ).mappings().fetchone()
        if not r:
            raise HTTPException(status_code=404, detail={"reason_code": "not_found", "message": f"No {fund_code} row with id {row_id}"})
        return _row_to_item(r, with_body=True)


# ---- Registered funds (one line per fund; built one at a time) ----
register_fund(
    slug="erdf", fund_code="ERDF",
    fund_name="European Regional Development Fund",
    blurb="The ERDF is the EU's largest cohesion instrument, co-financing regional "
          "competitiveness, innovation, the green and digital transition and connectivity.",
)
register_fund(
    slug="esf-plus", fund_code="ESF",
    fund_name="European Social Fund Plus",
    blurb="The ESF+ is the EU's main instrument for investing in people — employment, "
          "skills, social inclusion, and support for young people and children "
          "(Socrata fund code 'ESF').",
)
register_fund(
    slug="cohesion-fund", fund_code="CF",
    fund_name="Cohesion Fund",
    blurb="The Cohesion Fund supports Member States with a GNI per head below 90% of the "
          "EU average, financing trans-European transport networks and environment / "
          "climate infrastructure.",
)
register_fund(
    slug="jtf", fund_code="JTF",
    fund_name="Just Transition Fund",
    blurb="The JTF is the key instrument of the Just Transition Mechanism, supporting the "
          "territories most affected by the move to climate neutrality through economic "
          "diversification, reskilling and clean-energy investment.",
)
register_fund(
    slug="interreg", fund_code="INTERREG",
    fund_name="Interreg (European Territorial Cooperation)",
    blurb="Interreg funds cross-border, transnational and interregional cooperation "
          "programmes. Sourced from the dedicated Interreg allocation dataset "
          "(programme x strand), as it is barely present in the national-plan data.",
)
register_fund(
    slug="emfaf", fund_code="EMFAF",
    fund_name="European Maritime, Fisheries and Aquaculture Fund",
    blurb="The EMFAF supports the EU's common fisheries policy, the sustainable blue "
          "economy, and coastal and inland fishing communities.",
)
register_fund(
    slug="amif", fund_code="AMIF",
    fund_name="Asylum, Migration and Integration Fund",
    blurb="The AMIF (DG HOME) supports the common European asylum system, legal migration "
          "and integration, and returns. Shared-management allocations per Member State.",
)
register_fund(
    slug="isf", fund_code="ISF",
    fund_name="Internal Security Fund",
    blurb="The ISF (DG HOME) supports police cooperation, the fight against serious and "
          "organised crime and terrorism, and crisis management across Member States.",
)
