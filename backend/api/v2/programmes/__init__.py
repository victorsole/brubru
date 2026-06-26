"""
/api/v2/programmes — every EU funding programme, pick-your-scope.

The comprehensive catalogue of EU funding programmes (the 2021-2027 MFF programmes
plus the 10 Joint Undertakings that run Horizon Europe calls), enriched with the
managing institution / body, the responsible DG, programme type, period, indicative
budget, the live "where to apply" portal, and Brubru's own coverage + data endpoint.

"On demand" = pick what you want: a specific programme, every programme run by an
institution (European Commission, a Joint Undertaking, the EEAS, shared management),
or by a specific managing body / DG. Config-driven from config/funding_programmes.json
(the single source of truth shared with /api/v2/funding and Tenderator). Scope: read:economy.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field

from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/programmes", tags=["v2-programmes"])

_CONFIG = Path(__file__).resolve().parents[3] / "config" / "funding_programmes.json"
_EC_URL = "https://commission.europa.eu/funding-and-tenders/find-funding/eu-funding-programmes_en"
_ORDERS = {"budget", "name", "heading"}


def _load() -> list[dict]:
    return json.loads(_CONFIG.read_text(encoding="utf-8")).get("programmes", [])


class Programme(BaseModel):
    programme: str
    acronym: str
    institution: Optional[str] = Field(None, description="Who runs it: European Commission, Joint Undertaking, Member States (shared management), EEAS.")
    managing_body: Optional[str] = Field(None, description="The specific managing body / executive agency / JU.")
    body_code: Optional[str] = Field(None, description="Brubru canonical body code of the managing agency/JU, where applicable.")
    dg: Optional[str] = Field(None, description="Responsible Commission Directorate-General.")
    heading: str = Field(..., description="One of the 6 EC MFF headings.")
    cluster: Optional[str] = None
    programme_type: Optional[str] = Field(None, description="grants | financial-instrument | blended | procurement | prize.")
    period: Optional[str] = None
    budget_eur_bn: Optional[float] = Field(None, description="Indicative 2021-2027 headline allocation in EUR billion (current prices).")
    coverage: Optional[str] = Field(None, description="Brubru coverage: covered | gap | skipped.")
    endpoint: Optional[str] = Field(None, description="Brubru data endpoint for this programme's calls/projects, where covered.")
    apply_url: Optional[str] = Field(None, description="The live portal where applicants find and apply to calls.")
    source: Optional[str] = None
    public_url: Optional[str] = Field(None, description="Canonical URL (the apply portal, else the EC programmes page).")


def _to_item(p: dict) -> Programme:
    return Programme(
        programme=p["programme"], acronym=p["acronym"], institution=p.get("institution"),
        managing_body=p.get("managing_body"), body_code=p.get("body_code"), dg=p.get("dg"),
        heading=p["heading"], cluster=p.get("cluster"), programme_type=p.get("programme_type"),
        period=p.get("period"), budget_eur_bn=p.get("budget_eur_bn"), coverage=p.get("coverage"),
        endpoint=p.get("endpoint"), apply_url=p.get("apply_url"), source=p.get("source"),
        public_url=p.get("apply_url") or _EC_URL,
    )


def _match(p, *, institution, body, dg, heading, cluster, ptype, coverage, q):
    if institution and institution.lower() not in (p.get("institution") or "").lower():
        return False
    if body:
        hay = f"{p.get('body_code') or ''} {p.get('managing_body') or ''}".lower()
        if body.lower() not in hay:
            return False
    if dg and dg.lower() not in (p.get("dg") or "").lower():
        return False
    if heading and heading.lower() not in (p.get("heading") or "").lower():
        return False
    if cluster and cluster.lower() not in (p.get("cluster") or "").lower():
        return False
    if ptype and ptype.lower() != (p.get("programme_type") or "").lower():
        return False
    if coverage and coverage.lower() != (p.get("coverage") or "").lower():
        return False
    if q:
        blob = f"{p['programme']} {p['acronym']} {p.get('managing_body','')} {p.get('dg','')} {p.get('cluster','')}".lower()
        if q.lower() not in blob:
            return False
    return True


class ProgrammesDirectory(BaseModel):
    total_programmes: int
    total_budget_eur_bn: float
    by_institution: dict
    by_heading: dict
    by_type: dict
    by_coverage: dict


@router.get("", response_model=ProgrammesDirectory, tags=["v2-programmes"],
            summary="Funding programmes directory — the whole EU funding universe at a glance",
            description=(
                "**What it does**\nOne-call overview of every EU funding programme: totals and budget by "
                "managing institution, MFF heading, programme type and Brubru coverage.\n\n**When to use "
                "it**\nBefore picking a scope.\n\n**Input**\nNo parameters.\n\n**Try it**\n```\nGET "
                "/api/v2/programmes\n```\n\n**You get back**\nA summary. Then `/api/v2/programmes/all` to "
                "list/filter, `/api/v2/programmes/institutions` for the pick-list, `/api/v2/programmes/"
                "{acronym}` for one programme.\n\n**Data freshness**\nFrom the curated EU funding "
                "programmes catalogue."))
async def directory(request: Request, user: User = Depends(api_user_with_rate_limit)):
    progs = _load()

    def tally(key):
        out: dict = {}
        for p in progs:
            out[p.get(key) or "(unspecified)"] = out.get(p.get(key) or "(unspecified)", 0) + 1
        return dict(sorted(out.items(), key=lambda kv: -kv[1]))

    return ProgrammesDirectory(
        total_programmes=len(progs),
        total_budget_eur_bn=round(sum(p.get("budget_eur_bn") or 0 for p in progs), 1),
        by_institution=tally("institution"), by_heading=tally("heading"),
        by_type=tally("programme_type"), by_coverage=tally("coverage"),
    )


@router.get("/all", response_model=PaginatedResponse[Programme], tags=["v2-programmes"],
            summary="All funding programmes (pick programme / institution / body)",
            description=(
                "**What it does**\nThe full catalogue, filterable. Largest budget first.\n\n**When to use "
                "it**\nPick exactly the slice you want: every programme run by an institution "
                "(`institution=Joint Undertaking`), by a specific body or DG (`body=cinea`, `dg=DG CLIMA`), "
                "in an MFF heading or cluster, of a given type, or just covered ones.\n\n**Input**\n"
                "`institution` (European Commission | Joint Undertaking | Member States | EEAS, substring "
                "ok), `body` (managing body or Brubru body code, e.g. cinea / hadea / hydrogen), `dg`, "
                "`heading`, `cluster`, `type` (grants | financial-instrument | blended | procurement | "
                "prize), `coverage` (covered | gap | skipped), `q` (free text), `order` (budget | name | "
                "heading), `page`, `limit`.\n\n**Try it**\n```\nGET /api/v2/programmes/all?institution=Joint Undertaking\n"
                "GET /api/v2/programmes/all?body=cinea\nGET /api/v2/programmes/all?heading=Cohesion&type=grants\n```\n\n"
                "**You get back**\nA paginated envelope of programmes, each with institution, managing "
                "body, DG, type, period, indicative budget, the apply portal and Brubru's data endpoint "
                "where covered.\n\n**Data freshness**\nCurated catalogue; budgets are indicative 2021-2027 "
                "headline allocations."))
async def list_programmes(
    request: Request,
    user: User = Depends(api_user_with_rate_limit),
    institution: Optional[str] = Query(None, description="Managing institution (substring)."),
    body: Optional[str] = Query(None, description="Managing body or Brubru body code (substring)."),
    dg: Optional[str] = Query(None, description="Responsible Directorate-General (substring)."),
    heading: Optional[str] = Query(None, description="MFF heading (substring)."),
    cluster: Optional[str] = Query(None, description="Cluster (substring)."),
    type: Optional[str] = Query(None, description="Programme type."),
    coverage: Optional[str] = Query(None, description="covered | gap | skipped."),
    q: Optional[str] = Query(None, description="Free-text search."),
    order: str = Query("budget", description="budget | name | heading."),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
):
    if order not in _ORDERS:
        raise HTTPException(400, f"order must be one of {sorted(_ORDERS)}")
    progs = [p for p in _load() if _match(p, institution=institution, body=body, dg=dg,
             heading=heading, cluster=cluster, ptype=type, coverage=coverage, q=q)]
    if order == "budget":
        progs.sort(key=lambda p: p.get("budget_eur_bn") or -1, reverse=True)
    elif order == "name":
        progs.sort(key=lambda p: p["programme"].lower())
    else:
        progs.sort(key=lambda p: (p.get("heading") or "", p["programme"].lower()))
    total = len(progs)
    window = progs[(page - 1) * limit: (page - 1) * limit + limit]
    return build_envelope([_to_item(p) for p in window], total, page, limit)


@router.get("/institutions", response_model=dict, tags=["v2-programmes"],
            summary="Pick-list: institutions, managing bodies and DGs with programme counts",
            description=(
                "**What it does**\nThe discovery endpoint for the `institution`, `body` and `dg` filters: "
                "every managing institution, body and DG that runs a programme, with counts and total "
                "budget.\n\n**When to use it**\nTo build an institution/body picker, or to see who runs "
                "what.\n\n**Input**\nNo parameters.\n\n**Try it**\n```\nGET /api/v2/programmes/institutions\n```\n\n"
                "**You get back**\n`{institutions: [...], bodies: [...], dgs: [...]}`.\n\n**Data freshness**\n"
                "Curated catalogue."))
async def institutions_facet(request: Request, user: User = Depends(api_user_with_rate_limit)):
    progs = _load()

    def group(key):
        agg: dict = {}
        for p in progs:
            k = p.get(key) or "(unspecified)"
            a = agg.setdefault(k, {"name": k, "programme_count": 0, "budget_eur_bn": 0.0})
            a["programme_count"] += 1
            a["budget_eur_bn"] = round(a["budget_eur_bn"] + (p.get("budget_eur_bn") or 0), 1)
        return sorted(agg.values(), key=lambda x: -x["programme_count"])

    bodies = {}
    for p in progs:
        b = p.get("managing_body") or "(unspecified)"
        a = bodies.setdefault(b, {"managing_body": b, "body_code": p.get("body_code"),
                                  "institution": p.get("institution"), "programme_count": 0})
        a["programme_count"] += 1
    return {
        "institutions": group("institution"),
        "bodies": sorted(bodies.values(), key=lambda x: -x["programme_count"]),
        "dgs": group("dg"),
    }


@router.get("/{acronym}", response_model=Programme, tags=["v2-programmes"],
            summary="One funding programme (full record)",
            description=(
                "**What it does**\nReturns one programme in full: managing institution/body, DG, type, "
                "period, indicative budget, the apply portal and Brubru's data endpoint.\n\n**When to use "
                "it**\nAfter finding an acronym on `/api/v2/programmes/all`.\n\n**Input**\n`acronym` — the "
                "programme acronym (e.g. `Horizon Europe`, `LIFE`, `Clean Hydrogen`).\n\n**Try it**\n```\n"
                "GET /api/v2/programmes/LIFE\n```\n\n**You get back**\nA single programme record.\n\n"
                "**Data freshness**\nCurated catalogue."))
async def get_programme(request: Request,
                        acronym: str = PathParam(..., description="Programme acronym."),
                        user: User = Depends(api_user_with_rate_limit)):
    for p in _load():
        if p["acronym"].lower() == acronym.lower():
            return _to_item(p)
    raise HTTPException(404, f"No funding programme with acronym '{acronym}'")
