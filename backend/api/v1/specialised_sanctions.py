"""
/api/v1/specialised/sanctions — EU Restrictive Measures (CFSP financial sanctions).

Wave 1 of the "Specialised EC Databases" collection. Backed by the
``eu_sanctions`` table which is itself populated from the public CSV
consolidated list at webgate.ec.europa.eu/fsd/fsf.

The endpoint surfaces ~6,000 entities (persons, companies, vessels)
covered by EU sanctions across 30+ programmes (UKR, IRN, BLR, SYR,
TERR, etc.) — one row per (entity, programme).

Endpoints:
    GET /api/v1/specialised/sanctions             — list with filters
    GET /api/v1/specialised/sanctions/{eu_ref_num} — detail by EU ref number
    GET /api/v1/specialised/sanctions/programmes  — distinct programmes (with counts)
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._body import body_threshold_param, compose_html_from_sections, deprecated_body
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/specialised/sanctions", tags=["v1-specialised-ec-databases"])


# ----------------------------- response shapes -----------------------------


class SanctionListItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entity_logical_id: int
    eu_ref_num: Optional[str] = Field(None, description="EU reference number (e.g. EU.27.28). Use this as the path id for the detail endpoint when present.")
    subject_type: str = Field(..., description="P = natural person; E = legal entity / vessel / aircraft.")
    programme: str = Field(..., description="CFSP sanctions programme code (e.g. UKR, IRN, BLR, TERR).")
    full_name: Optional[str] = None
    legal_basis_title: Optional[str] = None
    legal_basis_publication_date: Optional[date] = None
    legal_basis_url: Optional[str] = None
    citizenships: list[str] = Field(default_factory=list)
    date_file: Optional[date] = Field(None, description="Date this row was last refreshed in the upstream consolidated list.")


class SanctionDetail(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    entity_logical_id: int
    eu_ref_num: Optional[str] = None
    subject_type: str
    programme: str

    full_name: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    title: Optional[str] = None
    function: Optional[str] = None

    aliases: list[dict[str, Any]] = Field(default_factory=list)
    addresses: list[dict[str, Any]] = Field(default_factory=list)
    birth_details: list[dict[str, Any]] = Field(default_factory=list)
    identification_documents: list[dict[str, Any]] = Field(default_factory=list)
    citizenships: list[str] = Field(default_factory=list)

    legal_basis_title: Optional[str] = None
    legal_basis_publication_date: Optional[date] = None
    legal_basis_url: Optional[str] = None
    remark: Optional[str] = None
    date_file: Optional[date] = None

    has_body: bool = False
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    body: Optional[str] = Field(None, description="DEPRECATED — back-compat alias for body_text or body_html.")


class ProgrammeCount(BaseModel):
    programme: str
    persons: int
    entities: int
    total: int


# ----------------------------- helpers -----------------------------


def _row_to_list_item(row: dict) -> SanctionListItem:
    return SanctionListItem(
        entity_logical_id=row["entity_logical_id"],
        eu_ref_num=row.get("eu_ref_num"),
        subject_type=row["subject_type"],
        programme=row["programme"],
        full_name=row.get("full_name"),
        legal_basis_title=row.get("legal_basis_title"),
        legal_basis_publication_date=row.get("legal_basis_publication_date"),
        legal_basis_url=row.get("legal_basis_url"),
        citizenships=row.get("citizenships") or [],
        date_file=row.get("date_file"),
    )


def _format_alias(a: dict) -> str:
    name = a.get("whole_name") or " ".join(filter(None, [a.get("first_name"), a.get("middle_name"), a.get("last_name")]))
    extras = []
    if a.get("language"):
        extras.append(a["language"])
    if a.get("gender"):
        extras.append({"M": "male", "F": "female"}.get(a["gender"], a["gender"]))
    return f"{name} ({', '.join(extras)})" if extras else name


def _format_address(a: dict) -> str:
    parts = [a.get("number"), a.get("street"), a.get("zipcode"), a.get("city"), a.get("country"), a.get("other")]
    return ", ".join(p for p in parts if p)


def _format_birth(b: dict) -> str:
    parts = []
    if b.get("date"):
        parts.append(b["date"])
    if b.get("place"):
        parts.append(b["place"])
    if b.get("country"):
        parts.append(b["country"])
    return ", ".join(parts) if parts else "—"


def _format_id(d: dict) -> str:
    parts = []
    if d.get("number"):
        parts.append(d["number"])
    if d.get("country"):
        parts.append(f"({d['country']})")
    return " ".join(parts) if parts else "—"


def _build_detail_body(row: dict, threshold: int) -> tuple[Optional[str], Optional[str], bool]:
    """Compose the structured fields into a single HTML/text body."""
    sections: list[tuple[str, Any]] = []

    if row.get("full_name"):
        sections.append(("Identity", row["full_name"]))
    if row.get("function"):
        sections.append(("Function", row["function"]))
    if row.get("title"):
        sections.append(("Title", row["title"]))

    aliases = row.get("aliases") or []
    if aliases:
        sections.append(("Known aliases", "\n".join(_format_alias(a) for a in aliases)))

    addresses = row.get("addresses") or []
    if addresses:
        sections.append(("Known addresses", "\n".join(_format_address(a) for a in addresses)))

    births = row.get("birth_details") or []
    if births:
        sections.append(("Birth details", "\n".join(_format_birth(b) for b in births)))

    citizenships = row.get("citizenships") or []
    if citizenships:
        sections.append(("Citizenship(s)", ", ".join(citizenships)))

    ids = row.get("identification_documents") or []
    if ids:
        sections.append(("Identification documents", "\n".join(_format_id(d) for d in ids)))

    if row.get("legal_basis_title"):
        leba = row["legal_basis_title"]
        if row.get("legal_basis_publication_date"):
            leba += f" — published {row['legal_basis_publication_date']}"
        sections.append(("Legal basis", leba))

    if row.get("remark"):
        sections.append(("Remarks", row["remark"]))

    return compose_html_from_sections(sections, threshold=threshold)


# ----------------------------- list -----------------------------


@router.get(
    "",
    response_model=PaginatedResponse[SanctionListItem],
    summary="EU restrictive measures (sanctioned persons and entities)",
    description="""**What it does**
Returns sanctioned persons and entities listed under the EU's Common Foreign and Security Policy (CFSP) restrictive-measures regimes. One row per (entity, sanctions programme). Sourced from the official consolidated CSV (~42,000 sub-rows aggregated into ~6,000 canonical records).

**When to use it**
- Trade-compliance teams running know-your-customer / anti-money-laundering checks against the EU sanctions list.
- Journalists tracking who is on which programme (UKR / IRN / BLR / SYR / TERR / etc.).
- Researchers analysing the legal-basis evolution of EU sanctions over time.

**Input**
- `programme` (string, optional) — filter to one programme (e.g. `UKR`, `IRN`, `BLR`, `TERR`).
- `subject_type` (string, optional) — `P` (person) or `E` (entity).
- `name_q` (string, optional) — case-insensitive search on `full_name` (uses Postgres `ILIKE`).
- `citizenship` (string, optional) — ISO-2 country code; matches any entry in the row's `citizenships` array.
- `limit` (int, 1–200, default 50), `page` (int, default 1).
- `body_threshold` (int, default 500) — kept for contract parity; the list endpoint never embeds the body.

**Try it**
```
GET /api/v1/specialised/sanctions?programme=UKR&limit=20
```

**You get back**
A paginated envelope of `SanctionListItem` rows: entity logical id, EU reference number, subject type, programme, primary name, legal basis (title + publication date + URL), citizenships array, last refresh date.""",
)
async def list_sanctions(
    request: Request,
    programme: Optional[str] = Query(None, description="Sanctions programme code (e.g. UKR, IRN, BLR)."),
    subject_type: Optional[str] = Query(None, regex="^[PE]$", description="P = person, E = entity."),
    name_q: Optional[str] = Query(None, description="Case-insensitive substring on full_name."),
    citizenship: Optional[str] = Query(None, description="ISO-2 country code (matches any element of citizenships[])."),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    body_threshold: int = Depends(body_threshold_param),  # parity
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SanctionListItem]:
    where: list[str] = []
    params: dict = {}
    if programme:
        where.append("programme = :programme")
        params["programme"] = programme.upper()
    if subject_type:
        where.append("subject_type = :subject_type")
        params["subject_type"] = subject_type
    if name_q:
        where.append("full_name ILIKE :name_q")
        params["name_q"] = f"%{name_q}%"
    if citizenship:
        where.append(":citizenship = ANY(citizenships)")
        params["citizenship"] = citizenship.upper()

    where_sql = "WHERE " + " AND ".join(where) if where else ""

    total_row = db.execute(
        text(f"SELECT COUNT(*) AS n FROM eu_sanctions {where_sql}"), params
    ).first()
    total = int(total_row.n) if total_row else 0

    offset = (page - 1) * limit
    query = text(
        f"""
        SELECT entity_logical_id, eu_ref_num, subject_type, programme,
               full_name, legal_basis_title, legal_basis_publication_date,
               legal_basis_url, citizenships, date_file
          FROM eu_sanctions
          {where_sql}
         ORDER BY date_file DESC NULLS LAST, full_name ASC NULLS LAST
         LIMIT :limit OFFSET :offset
        """
    )
    rows = db.execute(query, {**params, "limit": limit, "offset": offset}).mappings().all()

    items = [_row_to_list_item(dict(r)) for r in rows]

    return build_envelope(
        items=items,
        total=total,
        page=page,
        limit=limit,
        op_core_title="EU restrictive measures (sanctions)",
        op_core_type="Sanctioned entity",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "/api/v1/specialised/sanctions/{eu_ref_num}",
            "/api/v1/specialised/sanctions/programmes",
        ],
    )


# ----------------------------- programmes meta -----------------------------


@router.get(
    "/programmes",
    response_model=list[ProgrammeCount],
    summary="EU sanctions programmes (with counts)",
    description="""**What it does**
Lists every distinct sanctions programme present in the dataset, with the count of sanctioned persons (subject_type=P) and entities (subject_type=E) on each. Useful for building a programme picker UI.

**When to use it**
- Populating a dropdown of available sanctions regimes.
- Quick sanity check that the dataset is current after a backfill.

**Input**
None (the endpoint always returns the full programme list).

**Try it**
```
GET /api/v1/specialised/sanctions/programmes
```

**You get back**
A flat list of `ProgrammeCount` objects: programme, persons, entities, total. Sorted by total descending.""",
)
async def list_programmes(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> list[ProgrammeCount]:
    rows = db.execute(text(
        """
        SELECT programme,
               COUNT(*) FILTER (WHERE subject_type = 'P') AS persons,
               COUNT(*) FILTER (WHERE subject_type = 'E') AS entities,
               COUNT(*) AS total
          FROM eu_sanctions
         GROUP BY programme
         ORDER BY total DESC
        """
    )).mappings().all()
    return [
        ProgrammeCount(
            programme=r["programme"],
            persons=int(r["persons"] or 0),
            entities=int(r["entities"] or 0),
            total=int(r["total"] or 0),
        )
        for r in rows
    ]


# ----------------------------- detail -----------------------------


@router.get(
    "/{eu_ref_num}",
    response_model=SanctionDetail,
    summary="Single sanctioned entity by EU reference number",
    description="""**What it does**
Returns the full record for one sanctioned entity, identified by its EU reference number (e.g. `EU.27.28`). Includes every aggregated alias, address, birth detail, identification document and citizenship — plus the `body_html` / `body_text` composition for human-readable consumption.

**When to use it**
- You followed an entity from the list endpoint and need the complete dossier.
- You need the structured `aliases` and `identification_documents` for a screening tool.

**Input**
- `eu_ref_num` (path) — the EU reference number, e.g. `EU.27.28`.
- `body_threshold` (int, default 500) — minimum char length of the composed `body_text` to set `has_body=True`.

**Try it**
```
GET /api/v1/specialised/sanctions/EU.27.28
```

**You get back**
A `SanctionDetail` object with all canonical fields plus the JSON arrays for aliases / addresses / birth details / IDs / citizenships, the legal basis, the upstream remark, and the body fields composed from the structured data.""",
)
async def get_sanction(
    request: Request,
    eu_ref_num: str = Path(..., description="EU reference number (e.g. EU.27.28)."),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> SanctionDetail:
    row = db.execute(text(
        """
        SELECT *
          FROM eu_sanctions
         WHERE eu_ref_num = :ref
         LIMIT 1
        """
    ), {"ref": eu_ref_num}).mappings().first()

    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Sanction with EU reference '{eu_ref_num}' not found.", "reason_code": "not_found"},
        )

    record = dict(row)
    body_html, body_text, has_body = _build_detail_body(record, threshold=body_threshold)

    return SanctionDetail(
        entity_logical_id=record["entity_logical_id"],
        eu_ref_num=record.get("eu_ref_num"),
        subject_type=record["subject_type"],
        programme=record["programme"],
        full_name=record.get("full_name"),
        first_name=record.get("first_name"),
        middle_name=record.get("middle_name"),
        last_name=record.get("last_name"),
        gender=record.get("gender"),
        title=record.get("title"),
        function=record.get("function"),
        aliases=record.get("aliases") or [],
        addresses=record.get("addresses") or [],
        birth_details=record.get("birth_details") or [],
        identification_documents=record.get("identification_documents") or [],
        citizenships=record.get("citizenships") or [],
        legal_basis_title=record.get("legal_basis_title"),
        legal_basis_publication_date=record.get("legal_basis_publication_date"),
        legal_basis_url=record.get("legal_basis_url"),
        remark=record.get("remark"),
        date_file=record.get("date_file"),
        has_body=has_body,
        body_html=body_html,
        body_text=body_text,
        body=deprecated_body(body_text, body_html),
    )
