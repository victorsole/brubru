"""
Stakeholder Mapping API (MEUB Section 4 - Strategy).

A PI-aware actor graph around a tracked file (file mode) or the user's whole
portfolio (PI-overview, the default). Read: authenticated. No Anthropic.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.legislative_train import LegislativeCarriage, UserCarriageTrack
from knowledge_base.eu_calendar_institutions import COUNCIL_CONFIGURATIONS, COMMISSION_DG_NAME
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import (
    PI_TO_COMMITTEES, PI_TO_DGS, keywords_for_interests, dgs_for_interests,
)
from services.strategy import stakeholder_map
from services.strategy.stakeholder_map import _domains_for_committee, dg_contacts, _MEP_URL, _WIW_URL
from .auth import get_current_user

_BRUSSELS = ("(head_office_city ILIKE '%brussel%' OR head_office_city ILIKE '%bruxelles%' "
             "OR eu_office_city ILIKE '%brussel%' OR eu_office_city ILIKE '%bruxelles%')")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/stakeholders", tags=["Stakeholder Mapping"])


def _tracked_carriages(db: Session, user: User) -> List[LegislativeCarriage]:
    cids = [t.carriage_id for t in
            db.query(UserCarriageTrack).filter(UserCarriageTrack.user_id == user.id).all()]
    if not cids:
        return []
    return db.query(LegislativeCarriage).filter(LegislativeCarriage.id.in_(cids)).all()


def _pi_matched_carriages(db: Session, pi_domains: List[str], limit: int = 12) -> List[LegislativeCarriage]:
    committees = {c for d in pi_domains for c in PI_TO_COMMITTEES.get(d, [])}
    if not committees:
        return db.query(LegislativeCarriage).limit(limit).all()
    return (db.query(LegislativeCarriage)
            .filter(LegislativeCarriage.lead_committee.in_(list(committees)))
            .limit(limit).all())


@router.get("/graph", summary="Stakeholder map: actor graph for a file or your whole portfolio")
def stakeholder_graph(
    file: Optional[str] = Query(None, description="OEIL procedure ref or carriage id (file mode)"),
    my_interests: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns {nodes, edges, counts, focus}. Default (no ``file``) is the PI-overview:
    the union of key actors across your tracked files, deduped, with recurrence-weighted
    relevance. Pass ``file`` for the file-centric map (rapporteur, shadows, committees,
    lead DG + Who-is-Who officials, Council configuration, and the organisations that
    lobbied or filed positions on it)."""
    pi_domains = _interest_list(current_user) if my_interests else []

    if file:
        carriage = (db.query(LegislativeCarriage)
                    .filter((LegislativeCarriage.oeil_procedure_ref == file) |
                            (LegislativeCarriage.file_id == file))
                    .first())
        if not carriage:
            try:
                carriage = db.query(LegislativeCarriage).filter(LegislativeCarriage.id == file).first()
            except Exception:
                carriage = None
        if not carriage:
            return {"mode": "file", "focus": {"id": file, "label": file}, "pi_active": bool(pi_domains),
                    "nodes": [], "edges": [], "counts": {}, "sources_used": [], "not_found": True}
        return stakeholder_map.file_graph(db, carriage, pi_domains)

    carriages = _tracked_carriages(db, current_user) or _pi_matched_carriages(db, pi_domains)
    return stakeholder_map.pi_graph(db, carriages, pi_domains)


@router.get("/files", summary="Stakeholder map: the files you can focus the map on")
def stakeholder_files(
    my_interests: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The files the user can pick as the map focus. my_interests=true -> tracked
    (fallback PI-matched) files; my_interests=false -> a broader set across the corpus."""
    pi_domains = _interest_list(current_user) if my_interests else []
    carriages = _tracked_carriages(db, current_user) if my_interests else []
    tracked = bool(carriages)
    if not carriages:
        carriages = _pi_matched_carriages(db, pi_domains, limit=12 if my_interests else 40)
    return {
        "tracked": tracked,
        "files": [{
            "ref": c.oeil_procedure_ref or c.file_id,
            "title": c.title,
            "committee": c.lead_committee,
            "status": getattr(c.current_status, "value", None),
        } for c in carriages if (c.oeil_procedure_ref or c.file_id)],
    }


@router.get("/contacts", summary="Stakeholder map: who to contact in the Commission (Cards view)")
def stakeholder_contacts(
    file: Optional[str] = Query(None),
    dg: Optional[str] = Query(None),
    my_interests: bool = Query(True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The Commission contact hierarchy (Department -> Directorate -> Unit ->
    Head of Unit + email). For one DG (dg=), the DG relevant to a file (file=), or
    the user's interests. Units relevant to the policy area flagged and sorted first.
    All names/emails are verbatim from the EU Who-is-Who directory."""
    if dg:
        tree = dg_contacts(dg, [])  # whole DG, no relevance filter (directory browse)
        return {"dgs": [tree] if tree else [], "pi_active": False}

    pi = _interest_list(current_user) if my_interests else []

    if file:
        carriage = (db.query(LegislativeCarriage)
                    .filter((LegislativeCarriage.oeil_procedure_ref == file) |
                            (LegislativeCarriage.file_id == file)).first())
        if not carriage:
            return {"dgs": []}
        domains = _domains_for_committee(carriage.lead_committee) or pi
        dg_codes = [d for dom in domains for d in PI_TO_DGS.get(dom, [])][:3]
        keywords = list(keywords_for_interests(domains))
    else:
        dg_codes = list(dgs_for_interests(pi))[:6]
        keywords = list(keywords_for_interests(pi))

    seen, out = set(), []
    for code in dg_codes:
        if code in seen:
            continue
        seen.add(code)
        tree = dg_contacts(code, keywords)
        if tree:
            out.append(tree)
    return {"dgs": out, "pi_active": bool(pi)}


@router.get("/strategy-draft", summary="Auto-assemble an advocacy-strategy draft for a file")
def strategy_draft(
    file: str = Query(..., description="OEIL procedure ref or carriage id"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """A pre-filled strategy draft (title, objective, markdown content, file anchor,
    stakeholders) assembled from the file's Stakeholder Map: decision-makers, who to
    contact in the Commission, and who supports / opposes / wants amendments. Feeds
    the Strategy Docs "Build from file" flow."""
    carriage = (db.query(LegislativeCarriage)
                .filter((LegislativeCarriage.oeil_procedure_ref == file) |
                        (LegislativeCarriage.file_id == file)).first())
    if not carriage:
        raise HTTPException(status_code=404, detail="File not found")
    pi = _interest_list(current_user)
    return stakeholder_map.strategy_draft(db, carriage, pi)


@router.get("/directory", summary="Stakeholder map: browse ALL stakeholders (Cards 'All' mode)")
def stakeholder_directory(
    section: str = Query(..., description="stakeholder | ep | ec | council | file"),
    q: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The full directory for the 'All' scope (no PI filter). Sections:
    stakeholder = Brussels-HQ Transparency Register orgs; ep = MEPs (from the
    lobby-meeting data); ec = Commission DGs; council = Council configurations;
    file = legislative files. Items are returned in the same node shape the Cards
    use, so the same card + drawer render them. Paginated; supports a search q."""
    term = (q or "").strip()
    off = (page - 1) * page_size

    if section == "stakeholder":
        where = _BRUSSELS
        params: dict = {}
        if term:
            where += " AND (original_name ILIKE :q OR acronym ILIKE :q)"
            params["q"] = f"%{term}%"
        total = db.execute(text(f"SELECT count(*) FROM eu_transparency_register WHERE {where}"), params).scalar() or 0
        rows = db.execute(text(
            f"SELECT identification_code, original_name, acronym, website_url, public_url, "
            f"registration_category, head_office_city, eu_office_city FROM eu_transparency_register "
            f"WHERE {where} ORDER BY original_name LIMIT :lim OFFSET :off"),
            {**params, "lim": page_size, "off": off}).fetchall()
        items = [{
            "id": f"org:{r.identification_code}", "type": "org", "institution": "stakeholder",
            "label": r.acronym or (r.original_name or "")[:60], "sublabel": r.registration_category,
            "relevance": 0.5, "url": r.public_url or r.website_url,
            "meta": {"full_name": r.original_name, "tr_number": r.identification_code,
                     "website": r.website_url, "hq_city": r.head_office_city or r.eu_office_city,
                     "is_brussels": True, "category": r.registration_category, "kind": "directory"},
        } for r in rows]

    elif section == "ep":
        where = "mep_id IS NOT NULL"
        params = {}
        if term:
            where += " AND mep_name ILIKE :q"
            params["q"] = f"%{term}%"
        total = db.execute(text(f"SELECT count(distinct mep_id) FROM mep_lobby_meetings WHERE {where}"), params).scalar() or 0
        rows = db.execute(text(
            f"SELECT mep_id, max(mep_name) AS name, max(committee) AS committee "
            f"FROM mep_lobby_meetings WHERE {where} GROUP BY mep_id ORDER BY name LIMIT :lim OFFSET :off"),
            {**params, "lim": page_size, "off": off}).fetchall()
        items = [{
            "id": f"mep:{r.mep_id}", "type": "mep", "institution": "ep",
            "label": r.name or f"MEP {r.mep_id}", "sublabel": r.committee or "Member of Parliament",
            "relevance": 0.5, "url": _MEP_URL.format(id=r.mep_id), "meta": {"committee": r.committee},
        } for r in rows]

    elif section == "council":
        rows = [(c, n) for c, n in COUNCIL_CONFIGURATIONS.items()
                if not term or term.lower() in f"{c} {n}".lower()]
        total = len(rows)
        items = [{
            "id": f"council:{c}", "type": "council_config", "institution": "council",
            "label": c, "sublabel": n, "relevance": 0.5,
            "url": "https://www.consilium.europa.eu/en/council-eu/configurations/", "meta": {},
        } for c, n in rows[off:off + page_size]]

    elif section == "ec":
        rows = [(c, n) for c, n in sorted(COMMISSION_DG_NAME.items())
                if not term or term.lower() in f"{c} {n}".lower()]
        total = len(rows)
        items = [{
            "id": f"dg:{c}", "type": "dg", "institution": "ec", "label": c, "sublabel": n,
            "relevance": 0.5, "url": _WIW_URL.format(dg=c), "meta": {},
        } for c, n in rows[off:off + page_size]]

    elif section == "file":
        qry = db.query(LegislativeCarriage)
        if term:
            qry = qry.filter(LegislativeCarriage.title.ilike(f"%{term}%"))
        total = qry.count()
        rows = qry.order_by(LegislativeCarriage.title).limit(page_size).offset(off).all()
        items = [{
            "id": f"file:{c.oeil_procedure_ref or c.file_id}", "type": "file", "institution": "file",
            "label": c.title or c.oeil_procedure_ref or "File", "sublabel": c.oeil_procedure_ref,
            "relevance": 0.5,
            "url": (f"https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={c.oeil_procedure_ref}"
                    if c.oeil_procedure_ref else None),
            "meta": {"committee": c.lead_committee},
        } for c in rows]

    else:
        return {"section": section, "total": 0, "page": page, "page_size": page_size, "items": []}

    return {"section": section, "total": total, "page": page, "page_size": page_size, "items": items}
