"""
Cross-body public-consultations aggregator — the comprehensive part of
/api/v2/consultations.

A query-time UNION of the two consultation stores Brubru keeps fresh:
  - public_consultations : the EC "Have Your Say" register PLUS the decentralised
                           agency consultations it mirrors (the rich source: status,
                           closing date, responsible DG, policy areas, feedback counts).
  - economy_items        : item_type 'consultation' / 'public_consultation' — catches
                           bodies not in the register (e.g. EDPB), deduped by URL.

"On demand" = pick the scope: a list of bodies, a proprietary policy `family`
(e.g. finance-economy), an institution (European Commission / an agency), or
everything. Endpoints: directory, /all, /bodies (pick-list), /{id} (detail).
Scope: read:economy.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from services.economy.body_families import (
    FAMILIES, bodies_for_family, families_for_body, CALENDAR_ONLY_BODY_NAMES,
)

router = APIRouter()

_WHENS = {"open", "closed", "all"}
_ORDERS = {"recent", "oldest", "title"}


class ConsultationItem(BaseModel):
    id: str = Field(..., description="Aggregator id (source-prefixed: 'h<uuid>' Have Your Say register, 'e<n>' economy).")
    body_code: str = Field(..., description="Canonical body code running the consultation.")
    body_name: Optional[str] = None
    families: List[str] = Field(default_factory=list, description="Brubru policy families this body belongs to.")
    institution: Optional[str] = Field(None, description="European Commission or the decentralised agency.")
    title: str
    summary: Optional[str] = None
    consultation_type: Optional[str] = Field(None, description="public_consultation | initiative | call_for_evidence.")
    status: Optional[str] = Field(None, description="open | closed | outcome_published.")
    dg: Optional[str] = Field(None, description="Responsible Commission DG (Have Your Say).")
    policy_areas: Optional[list] = None
    feedback_count: Optional[int] = None
    public_url: Optional[str] = None
    body_txt: Optional[str] = Field(None, description="Plain-text body (full on detail; null on list).")
    body_html: Optional[str] = Field(None, description="HTML body (full on detail; null on list).")
    document_date: Optional[datetime] = Field(None, description="The consultation's closing date.")
    creation_date: Optional[datetime] = None


def _body_names(db: Session) -> dict:
    names = dict(CALENDAR_ONLY_BODY_NAMES)
    for r in db.execute(text("SELECT code, name FROM economy_bodies")).fetchall():
        names.setdefault(r.code, r.name)
    return names


def _resolve_scope(bodies, family):
    codes: set[str] = set()
    if family:
        for slug in [s.strip() for s in family.split(",") if s.strip()]:
            codes |= bodies_for_family(slug)
    if bodies:
        codes |= {b.strip() for b in bodies.split(",") if b.strip()}
    return codes or None


def _aware(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fetch(db, *, codes, institution, status, since, until, q, with_body=False):
    out = []
    is_comm = bool(institution) and "commission" in institution.lower()
    specific_status = bool(status) and status != "all"
    # 1) public_consultations — the rich register (Have Your Say + agency mirror)
    where, params = ["1=1"], {}
    if codes is not None:
        where.append("lower(coalesce(source_body,'commission')) = ANY(:codes)")
        params["codes"] = list(codes)
    if is_comm:
        where.append("source_body IS NULL")
    elif institution:
        where.append("lower(source_body) = :inst"); params["inst"] = institution.lower()
    if specific_status:
        where.append("status = :st"); params["st"] = status
    if since:
        where.append("end_date >= :since"); params["since"] = since
    if until:
        where.append("end_date <= :until"); params["until"] = until
    if q:
        where.append("(title ILIKE :q OR short_title ILIKE :q OR description ILIKE :q)"); params["q"] = f"%{q}%"
    cols = ("id, title, short_title, description, consultation_type, status, dg_responsible, "
            "policy_areas, end_date, first_seen, portal_url, feedback_url, feedback_count, source_body")
    if with_body:
        cols += ", objectives, outcome_summary"
    for r in db.execute(text(f"SELECT {cols} FROM public_consultations WHERE {' AND '.join(where)} LIMIT 4000"), params):
        body = (r.source_body or "commission").lower()
        inst = "European Commission" if not r.source_body else (r.source_body or "").upper()
        body_txt = body_html = None
        if with_body:
            parts = [r.description, getattr(r, "objectives", None), getattr(r, "outcome_summary", None)]
            body_txt = "\n\n".join(p for p in parts if p) or r.short_title or r.title
            body_html = f"<article><h3>{r.title}</h3>" + "".join(f"<p>{p}</p>" for p in parts if p) + "</article>"
        out.append({
            "id": f"h{r.id}", "body_code": body, "institution": inst, "title": r.title,
            "summary": r.short_title or (r.description[:300] if r.description else None),
            "consultation_type": r.consultation_type, "status": r.status, "dg": r.dg_responsible,
            "policy_areas": list(r.policy_areas) if r.policy_areas else None,
            "feedback_count": r.feedback_count, "public_url": r.portal_url or r.feedback_url,
            "document_date": _aware(datetime.combine(r.end_date, datetime.min.time()) if r.end_date else None),
            "creation_date": _aware(r.first_seen), "body_txt": body_txt, "body_html": body_html,
        })

    # 2) economy_items — only for bodies NOT in the register (e.g. EDPB, ECB-SSM).
    # public_consultations is authoritative for the bodies it carries (richer + a
    # structured status), so excluding those bodies avoids double-counting and the
    # store-vs-store status drift, independent of any URL-form differences.
    hys_bodies = {r[0] for r in db.execute(text(
        "SELECT DISTINCT lower(coalesce(source_body,'commission')) FROM public_consultations")).fetchall()}
    ew = ["item_type IN ('consultation','public_consultation')", "lower(body_code) <> ALL(:hys)"]
    ep = {"hys": list(hys_bodies)}
    if codes is not None:
        ew.append("body_code = ANY(:codes)"); ep["codes"] = list(codes)
    if since:
        ew.append("document_date >= :since"); ep["since"] = since
    if until:
        ew.append("document_date <= :until"); ep["until"] = until
    if q:
        ew.append("search_vector @@ plainto_tsquery('english', :q)"); ep["q"] = q
    if specific_status:
        ew.append("summary ILIKE :st"); ep["st"] = f"%{status}%"  # economy rows carry status in the summary
    if is_comm:
        ew.append("1=0")  # economy rows are agency-run, never the Commission
    elif institution:
        ew.append("lower(body_code) = :ibody"); ep["ibody"] = institution.lower()
    ecols = "id, body_code, title, summary, public_url, document_date, creation_date" + (", body_txt, body_html" if with_body else "")
    for r in db.execute(text(f"SELECT {ecols} FROM economy_items WHERE {' AND '.join(ew)} LIMIT 4000"), ep):
        out.append({
            "id": f"e{r.id}", "body_code": r.body_code, "institution": r.body_code.upper(), "title": r.title,
            "summary": r.summary, "consultation_type": "public_consultation", "status": None, "dg": None,
            "policy_areas": None, "feedback_count": None, "public_url": r.public_url,
            "document_date": _aware(r.document_date), "creation_date": _aware(r.creation_date),
            "body_txt": getattr(r, "body_txt", None) if with_body else None,
            "body_html": getattr(r, "body_html", None) if with_body else None,
        })
    return out


def _to_item(it, names, *, with_body):
    return ConsultationItem(
        id=it["id"], body_code=it["body_code"], body_name=names.get(it["body_code"]) or it["body_code"].upper(),
        families=families_for_body(it["body_code"]), institution=it["institution"], title=it["title"],
        summary=it["summary"], consultation_type=it["consultation_type"], status=it["status"], dg=it["dg"],
        policy_areas=it["policy_areas"], feedback_count=it["feedback_count"], public_url=it["public_url"],
        document_date=it["document_date"], creation_date=it["creation_date"],
        body_txt=(it["body_txt"] if with_body else None), body_html=(it["body_html"] if with_body else None),
    )


class ConsultationsDirectory(BaseModel):
    total_consultations: int
    open: int
    closed: int
    bodies_with_consultations: int
    families: int
    by_institution: dict


def build_directory(db) -> "ConsultationsDirectory":
    """Directory payload — registered on the parent (prefixed) router in __init__."""
    items = _fetch(db, codes=None, institution=None, status=None, since=None, until=None, q=None)
    by_inst: dict = {}
    for it in items:
        by_inst[it["institution"]] = by_inst.get(it["institution"], 0) + 1
    return ConsultationsDirectory(
        total_consultations=len(items),
        open=sum(1 for it in items if it["status"] == "open"),
        closed=sum(1 for it in items if it["status"] in ("closed", "outcome_published")),
        bodies_with_consultations=len({it["body_code"] for it in items}),
        families=len(FAMILIES),
        by_institution=dict(sorted(by_inst.items(), key=lambda kv: -kv[1])),
    )


@router.get("/all", response_model=PaginatedResponse[ConsultationItem], tags=["v2-consultations"],
            summary="All public consultations, all bodies (pick your scope)",
            description=(
                "**What it does**\nEvery EU public consultation in one feed — the Commission's Have Your "
                "Say register and the decentralised agency consultations — newest closing date first.\n\n"
                "**When to use it**\n'Show me every open consultation from the bodies I care about'. Scope "
                "with `body` (comma codes) and/or `family` (a Brubru policy family); `status=open` for live "
                "ones.\n\n**Input**\n`body`, `family`, `institution` (European Commission | an agency), "
                "`status` (open | closed | all), `from` / `to` (YYYY-MM-DD on the closing date), `q`, "
                "`order` (recent | oldest | title), `page`, `limit`.\n\n**Try it**\n```\nGET /api/v2/consultations/all?status=open\n"
                "GET /api/v2/consultations/all?family=finance-economy&status=open\nGET /api/v2/consultations/all?body=echa,ema\n```\n\n"
                "**You get back**\nA paginated envelope. Each carries body_code, body_name, policy families, "
                "institution, consultation_type, status, responsible DG, policy areas, feedback count, the "
                "closing date and the link (body_txt/html on the detail endpoint).\n\n**Data freshness**\n"
                "Live union of public_consultations + economy_items."))
async def consultations_all(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    body: Optional[str] = Query(None, description="Comma-separated body codes (e.g. echa,ema,commission)."),
    family: Optional[str] = Query(None, description="Comma-separated Brubru policy family slugs (see /api/v2/consultations/bodies)."),
    institution: Optional[str] = Query(None, description="European Commission, or an agency acronym."),
    status: Optional[str] = Query(None, description="open | closed | all."),
    from_: Optional[date] = Query(None, alias="from", description="Closing date on/after (YYYY-MM-DD)."),
    to: Optional[date] = Query(None, description="Closing date on/before (YYYY-MM-DD)."),
    q: Optional[str] = Query(None, description="Free-text search over title and summary."),
    order: str = Query("recent", description="recent | oldest | title."),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    if status and status not in _WHENS:
        raise HTTPException(400, f"status must be one of {sorted(_WHENS)}")
    if order not in _ORDERS:
        raise HTTPException(400, f"order must be one of {sorted(_ORDERS)}")
    codes = _resolve_scope(body, family)
    items = _fetch(db, codes=codes, institution=institution, status=status, since=from_, until=to, q=q)
    far_past = datetime(1, 1, 1, tzinfo=timezone.utc); far_future = datetime(9999, 1, 1, tzinfo=timezone.utc)
    if order == "title":
        items.sort(key=lambda it: (it["title"] or "").lower())
    elif order == "oldest":
        items.sort(key=lambda it: it["document_date"] or far_future)
    else:
        items.sort(key=lambda it: it["document_date"] or far_past, reverse=True)
    total = len(items)
    window = items[(page - 1) * limit: (page - 1) * limit + limit]
    names = _body_names(db)
    return build_envelope([_to_item(it, names, with_body=False) for it in window], total, page, limit)


@router.get("/bodies", response_model=dict, tags=["v2-consultations"],
            summary="Pick-list: bodies and policy families with consultation counts",
            description=(
                "**What it does**\nThe discovery endpoint for the `body` and `family` filters: every body "
                "running consultations (count + families) and every Brubru policy family (bodies + total "
                "count).\n\n**When to use it**\nTo build a picker.\n\n**Input**\nNo parameters.\n\n**Try it**\n```\n"
                "GET /api/v2/consultations/bodies\n```\n\n**You get back**\n`{bodies: [...], families: [...]}`.\n\n"
                "**Data freshness**\nLive."))
async def bodies_facet(request: Request, db: Session = Depends(get_db),
                       user: User = Depends(api_user_with_rate_limit)):
    items = _fetch(db, codes=None, institution=None, status=None, since=None, until=None, q=None)
    names = _body_names(db)
    by_body: dict = {}
    for it in items:
        by_body[it["body_code"]] = by_body.get(it["body_code"], 0) + 1
    bodies = [{"code": c, "name": names.get(c) or c.upper(), "families": families_for_body(c), "consultation_count": n}
              for c, n in sorted(by_body.items(), key=lambda kv: -kv[1])]
    fams = []
    for slug, f in FAMILIES.items():
        member = set(f["bodies"])
        fams.append({"slug": slug, "label": f["label"], "bodies": f["bodies"],
                     "consultation_count": sum(n for c, n in by_body.items() if c in member)})
    fams.sort(key=lambda x: -x["consultation_count"])
    return {"bodies": bodies, "families": fams}


@router.get("/{consultation_id}", response_model=ConsultationItem, tags=["v2-consultations"],
            summary="One public consultation (full body)",
            description=(
                "**What it does**\nReturns one consultation in full, including objectives and outcome "
                "summary where the register has them.\n\n**When to use it**\nAfter finding an id on "
                "`/api/v2/consultations/all`.\n\n**Input**\n`consultation_id` — the source-prefixed "
                "aggregator id (`h<uuid>` or `e<n>`).\n\n**Try it**\n```\nGET /api/v2/consultations/h<uuid>\n```\n\n"
                "**You get back**\nA single consultation with the full record.\n\n**Data freshness**\nLive."))
async def get_consultation(request: Request,
                           consultation_id: str = PathParam(..., description="Prefixed id: 'h<uuid>' or 'e<n>'."),
                           db: Session = Depends(get_db),
                           user: User = Depends(api_user_with_rate_limit)):
    names = _body_names(db)
    if consultation_id.startswith("h"):
        r = db.execute(text(
            "SELECT id, title, short_title, description, consultation_type, status, dg_responsible, "
            "policy_areas, end_date, first_seen, portal_url, feedback_url, feedback_count, source_body, "
            "objectives, outcome_summary FROM public_consultations WHERE id = :id"),
            {"id": consultation_id[1:]}).fetchone()
        if r:
            body = (r.source_body or "commission").lower()
            parts = [r.description, r.objectives, r.outcome_summary]
            it = {"id": consultation_id, "body_code": body,
                  "institution": "European Commission" if not r.source_body else r.source_body.upper(),
                  "title": r.title, "summary": r.short_title or (r.description[:300] if r.description else None),
                  "consultation_type": r.consultation_type, "status": r.status, "dg": r.dg_responsible,
                  "policy_areas": list(r.policy_areas) if r.policy_areas else None,
                  "feedback_count": r.feedback_count, "public_url": r.portal_url or r.feedback_url,
                  "document_date": _aware(datetime.combine(r.end_date, datetime.min.time()) if r.end_date else None),
                  "creation_date": _aware(r.first_seen),
                  "body_txt": "\n\n".join(p for p in parts if p) or r.title,
                  "body_html": f"<article><h3>{r.title}</h3>" + "".join(f"<p>{p}</p>" for p in parts if p) + "</article>"}
            return _to_item(it, names, with_body=True)
    elif consultation_id.startswith("e") and consultation_id[1:].isdigit():
        r = db.execute(text(
            "SELECT id, body_code, title, summary, public_url, body_txt, body_html, document_date, creation_date "
            "FROM economy_items WHERE id = :id AND item_type IN ('consultation','public_consultation')"),
            {"id": int(consultation_id[1:])}).fetchone()
        if r:
            it = {"id": consultation_id, "body_code": r.body_code, "institution": r.body_code.upper(),
                  "title": r.title, "summary": r.summary, "consultation_type": "public_consultation",
                  "status": None, "dg": None, "policy_areas": None, "feedback_count": None,
                  "public_url": r.public_url, "document_date": _aware(r.document_date),
                  "creation_date": _aware(r.creation_date), "body_txt": r.body_txt, "body_html": r.body_html}
            return _to_item(it, names, with_body=True)
    raise HTTPException(404, f"No consultation with id {consultation_id}")
