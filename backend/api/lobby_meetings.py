"""
Lobby Meetings API (MEUB Section 3) - the Commission Transparency Register, through
the shared Policy-Interest lens.

"Who is lobbying the Commission on your topics, and whom did they meet?" Each row is
a published meeting between a Commission cabinet/DG/Commissioner and an external
interest representative. PI match = the host DG (shared DG taxonomy) OR a PI keyword
in the subject. Ships a dashboard (KPIs + top organisations + top DGs + monthly
activity) over the same filtered set. Read: Yellow+. No Anthropic.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func, distinct
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.w4_entities import TransparencyMeeting as TM
from models.mep_lobby_meeting import MepLobbyMeeting as MLM
from knowledge_base.eu_calendar_institutions import COMMISSION_DG_NAME
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import (
    dgs_for_interests, keywords_for_interests, committees_for_interests,
)
from services.transparency_register_match import match_org
from services.scrapers.mep_lobby_meetings_scraper import norm_org
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lobby-meetings", tags=["Lobby Meetings"])

# The pre-2023 ec.europa.eu/transparencyregister/...displaylobbyist.do path is DEAD
# (404). The register moved to transparency-register.europa.eu; this search-by-id
# page resolves (200).
_TR_PUBLIC = ("https://transparency-register.europa.eu/searchregister-or-update/"
              "search-register_en?searchtext={id}")


def _require_yellow(user: User):
    if not user or user.subscription_tier == "white":
        raise HTTPException(status_code=403, detail="Lobby Meetings require Yellow or Blue tier.")


def _filtered_query(db: Session, user: User, my_interests: bool,
                    dg: Optional[str], search: Optional[str],
                    date_from: Optional[date], date_to: Optional[date]):
    """Base query with PI lens + manual filters. Returns (query, pi_active)."""
    q = db.query(TM)
    pi_active = False
    if my_interests:
        interests = _interest_list(user)
        if interests:
            dgs = dgs_for_interests(interests)
            kws = keywords_for_interests(interests)
            clauses = []
            if dgs:
                clauses.append(TM.host_dg.in_(list(dgs)))
            for kw in kws:
                clauses.append(TM.subject.ilike(f"%{kw}%"))
            if clauses:
                q = q.filter(or_(*clauses))
                pi_active = True
    if dg:
        codes = [c.strip().upper() for c in dg.split(",") if c.strip()]
        if codes:
            q = q.filter(TM.host_dg.in_(codes))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(TM.subject.ilike(like), TM.organisation_met.ilike(like)))
    if date_from:
        q = q.filter(TM.meeting_date >= date_from)
    if date_to:
        q = q.filter(TM.meeting_date <= date_to)
    return q, pi_active


def _dg_name(code: Optional[str]) -> Optional[str]:
    return COMMISSION_DG_NAME.get(code) if code else None


def _enrich_org(item: dict, db: Session) -> dict:
    """Attach the org's own website + register profile from the Transparency Register
    (be careful: only well-formed URLs survive _valid_url). Prefer the matched register
    profile, fall back to the search-by-id page."""
    rec = match_org(item.get("organisation_met") or item.get("organisation"),
                    db, item.get("transparency_register_id"))
    if rec:
        item["org_website"] = rec.get("website")
        item["org_register_url"] = rec.get("register_url") or item.get("transparency_register_url")
        item["org_category"] = rec.get("category")
        item["org_country"] = rec.get("country")
        item["org_fte"] = rec.get("fte")
        item["org_ep_passes"] = rec.get("ep_passes")
    else:
        item["org_website"] = None
        item["org_register_url"] = item.get("transparency_register_url")
    return item


def _summary(r: TM) -> dict:
    return {
        "id": str(r.id),
        "meeting_date": r.meeting_date.isoformat() if r.meeting_date else None,
        "host_name": r.host_name,
        "host_role": r.host_role,
        "host_dg": r.host_dg,
        "host_dg_name": _dg_name(r.host_dg),
        "host_cabinet": r.host_cabinet,
        "subject": r.subject,
        "organisation_met": r.organisation_met,
        "transparency_register_id": r.transparency_register_id,
        "transparency_register_url": (_TR_PUBLIC.format(id=r.transparency_register_id)
                                      if r.transparency_register_id else None),
        "representatives": r.representatives,
        "location": r.location,
        "source_url": r.source_url,
    }


@router.get("")
def list_meetings(
    my_interests: bool = Query(True),
    dg: Optional[str] = Query(None, description="Host DG code(s), comma-separated"),
    search: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """PI-filtered list of Commission lobby meetings (newest first)."""
    _require_yellow(user)
    q, pi_active = _filtered_query(db, user, my_interests, dg, search, date_from, date_to)
    total = q.count()
    rows = q.order_by(TM.meeting_date.desc()).offset(offset).limit(limit).all()
    items = [_enrich_org(_summary(r), db) for r in rows]
    return {"total": total, "pi_active": pi_active, "items": items}


@router.get("/stats")
def stats(
    my_interests: bool = Query(True),
    dg: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dashboard aggregations over the same filtered set: KPIs + top organisations
    + top DGs + monthly activity."""
    _require_yellow(user)
    q, pi_active = _filtered_query(db, user, my_interests, dg, search, date_from, date_to)

    total = q.count()
    distinct_orgs = q.with_entities(func.count(distinct(TM.organisation_met))).scalar() or 0
    distinct_dgs = q.with_entities(func.count(distinct(TM.host_dg))).scalar() or 0
    since = date.today() - timedelta(days=90)
    recent = q.with_entities(func.count()).filter(TM.meeting_date >= since).scalar() or 0

    top_orgs = [
        {"organisation": o, "count": c}
        for o, c in q.with_entities(TM.organisation_met, func.count().label("c"))
        .group_by(TM.organisation_met).order_by(func.count().desc()).limit(10).all()
    ]
    top_dgs = [
        {"dg": d, "dg_name": _dg_name(d), "count": c}
        for d, c in q.with_entities(TM.host_dg, func.count().label("c"))
        .filter(TM.host_dg.isnot(None))
        .group_by(TM.host_dg).order_by(func.count().desc()).limit(8).all()
    ]
    month = func.to_char(TM.meeting_date, "YYYY-MM")
    monthly = [
        {"month": m, "count": c}
        for m, c in q.with_entities(month.label("m"), func.count().label("c"))
        .group_by(month).order_by(month).all()
    ]
    # keep the last 12 months for the sparkline
    monthly = monthly[-12:]

    return {
        "pi_active": pi_active,
        "total": total,
        "distinct_organisations": int(distinct_orgs),
        "distinct_dgs": int(distinct_dgs),
        "recent_90d": int(recent),
        "top_organisations": top_orgs,
        "top_dgs": top_dgs,
        "monthly": monthly,
    }


# ---------------------------------------------------------------------------
# Parliament side: MEP lobby meetings (OEIL Transparency + MEP profiles)
# ---------------------------------------------------------------------------

def _mlm_query(db: Session, user: User, my_interests: bool,
               committee: Optional[str], search: Optional[str]):
    """MEP-meetings query with the PI lens (committee crosswalk) + filters."""
    q = db.query(MLM)
    pi_active = False
    if my_interests:
        interests = _interest_list(user)
        if interests:
            coms = committees_for_interests(interests)
            kws = keywords_for_interests(interests)
            clauses = []
            if coms:
                clauses.append(MLM.committee.in_(list(coms)))
            for kw in kws:
                clauses.append(MLM.organisation.ilike(f"%{kw}%"))
            if clauses:
                q = q.filter(or_(*clauses))
                pi_active = True
    if committee:
        codes = [c.strip().upper() for c in committee.split(",") if c.strip()]
        if codes:
            q = q.filter(MLM.committee.in_(codes))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(MLM.organisation.ilike(like), MLM.mep_name.ilike(like),
                         MLM.procedure_ref.ilike(like)))
    return q, pi_active


def _mlm_summary(r: MLM) -> dict:
    proc = r.procedure_ref
    return {
        "id": str(r.id),
        "meeting_date": r.meeting_date.isoformat() if r.meeting_date else None,
        "mep_id": r.mep_id,
        "mep_name": r.mep_name,
        "role": r.role,
        "committee": r.committee,
        "procedure_ref": proc,
        "procedure_url": (f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={proc}"
                          if proc else None),
        "organisation": r.organisation,
        "org_website": r.org_website,
        "org_register_url": r.org_register_url,
        "transparency_register_id": r.transparency_register_id,
        "source": r.source,
        "source_url": r.source_url,
    }


@router.get("/parliament")
def list_parliament(
    my_interests: bool = Query(True),
    committee: Optional[str] = Query(None, description="Committee code(s), comma-separated"),
    search: Optional[str] = Query(None),
    limit: int = Query(80, ge=1, le=300),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """PI-filtered MEP lobby meetings (rapporteur/shadow meetings with interest
    representatives), unioned from OEIL Transparency + MEP profiles, newest first."""
    _require_yellow(user)
    q, pi_active = _mlm_query(db, user, my_interests, committee, search)
    total = q.count()
    rows = q.order_by(MLM.meeting_date.desc().nullslast()).offset(offset).limit(limit).all()
    distinct_meps = q.with_entities(func.count(distinct(MLM.mep_id))).scalar() or 0
    distinct_orgs = q.with_entities(func.count(distinct(MLM.organisation_norm))).scalar() or 0
    top_orgs = [
        {"organisation": o, "count": c}
        for o, c in q.with_entities(MLM.organisation, func.count().label("c"))
        .group_by(MLM.organisation).order_by(func.count().desc()).limit(10).all()
    ]
    return {
        "total": total, "pi_active": pi_active,
        "distinct_meps": int(distinct_meps), "distinct_organisations": int(distinct_orgs),
        "top_organisations": top_orgs,
        "items": [_mlm_summary(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Comparison: who lobbied both branches vs one only (the Venn)
# ---------------------------------------------------------------------------

@router.get("/comparison")
def comparison(
    my_interests: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cross-branch footprint: organisations that lobbied BOTH the Commission and the
    Parliament on the user's topics, vs Commission-only and Parliament-only. Matched on
    the normalised organisation name. No causation/assessment claims (parked)."""
    _require_yellow(user)

    cq, pi_active = _filtered_query(db, user, my_interests, None, None, None, None)
    pq, _ = _mlm_query(db, user, my_interests, None, None)

    # Commission side: split multi-org meetings, normalise each in Python (no norm column).
    comm: dict[str, dict] = {}
    for org, c in (cq.with_entities(TM.organisation_met, func.count().label("c"))
                   .filter(TM.organisation_met.isnot(None))
                   .group_by(TM.organisation_met).all()):
        for piece in _split_orgs(org):
            n = norm_org(piece)
            if not n:
                continue
            e = comm.setdefault(n, {"display": piece, "commission": 0})
            e["commission"] += int(c)

    # Parliament side: split too (usually single), normalise each.
    ep: dict[str, dict] = {}
    for org, c in (pq.with_entities(MLM.organisation, func.count().label("c"))
                   .group_by(MLM.organisation).all()):
        for piece in _split_orgs(org):
            key = norm_org(piece)
            if not key:
                continue
            e = ep.setdefault(key, {"display": piece, "parliament": 0})
            e["parliament"] += int(c)

    both_keys = set(comm) & set(ep)
    comm_only = set(comm) - both_keys
    ep_only = set(ep) - both_keys

    both = sorted(
        [{"organisation": comm[k]["display"], "commission": comm[k]["commission"],
          "parliament": ep[k]["parliament"],
          "total": comm[k]["commission"] + ep[k]["parliament"]} for k in both_keys],
        key=lambda x: x["total"], reverse=True)[:40]
    commission_only = sorted(
        [{"organisation": comm[k]["display"], "commission": comm[k]["commission"]} for k in comm_only],
        key=lambda x: x["commission"], reverse=True)[:20]
    parliament_only = sorted(
        [{"organisation": ep[k]["display"], "parliament": ep[k]["parliament"]} for k in ep_only],
        key=lambda x: x["parliament"], reverse=True)[:20]

    return {
        "pi_active": pi_active,
        "counts": {
            "both": len(both_keys),
            "commission_only": len(comm_only),
            "parliament_only": len(ep_only),
            "commission_total": len(comm),
            "parliament_total": len(ep),
        },
        "both": both,
        "commission_only": commission_only,
        "parliament_only": parliament_only,
    }


# ---------------------------------------------------------------------------
# Tier-0 footprint: factual engagement signals (NO success/causation verdicts).
# Access depth, competitive balance, declared spend. The "assessment" of whether
# lobbying worked is deliberately NOT here - it belongs in Section 4 (Analysis &
# Strategy), built on a positions layer. See feedback memory on lobbying assessment.
# ---------------------------------------------------------------------------

# Register category -> coarse competitive-balance type (note the double-space
# "Companies  groups" duplicate spelling in the source data).
_BALANCE_TYPE = {
    "Non-governmental organisations, platforms and networks and similar": "NGOs & civil society",
    "Trade and business associations": "Business associations",
    "Companies  groups": "Companies",
    "Companies & groups": "Companies",
    "Trade unions and professional associations": "Trade unions",
    "Professional consultancies": "Consultancies & law firms",
    "Law firms": "Consultancies & law firms",
    "Think tanks and research institutions": "Think tanks & academia",
    "Academic institutions": "Think tanks & academia",
    "Associations and networks of public authorities": "Public & mixed entities",
    "Other organisations, public or mixed entities": "Public & mixed entities",
    "Organisations representing churches and religious communities": "Other",
    "Self-employed individuals": "Other",
    "Entities, offices or networks established by third countries": "Other",
}


def _balance_type(cat: Optional[str]) -> str:
    if not cat:
        return "Unknown"
    return _BALANCE_TYPE.get(cat.strip(), "Other")


def _split_orgs(s: Optional[str]) -> List[str]:
    """A Commission meeting's organisation_met field often lists several orgs, one per
    line (e.g. 'BDI,\\nBUSINESSEUROPE,\\nMEDEF'). Split into individual participants so
    each can be matched + counted. EP rows are usually single but split cleanly too."""
    if not s:
        return []
    parts = [p.strip().rstrip(",").strip() for p in s.replace("\r", "\n").split("\n")]
    return [p for p in parts if p]


# EP access depth from the meeting role. Returns (level, is_staff). "level" is the
# seniority of who they reached; is_staff means they met the office's staff, not the
# principal - a genuine depth distinction the published data exposes.
_ACCESS_RANK = {"rapporteur": 4, "opinion_rapporteur": 3, "shadow": 3, "chair": 2, "member": 1}
_ACCESS_LABEL = {
    "rapporteur": "Rapporteur (pen-holder)", "opinion_rapporteur": "Opinion rapporteur",
    "shadow": "Shadow rapporteur", "chair": "Committee/Delegation chair", "member": "Member",
}


def _ep_access(role: Optional[str]):
    r = (role or "").lower()
    staff = "staff" in r
    if "rapporteur for opinion" in r:
        level = "opinion_rapporteur"
    elif "shadow" in r:
        level = "shadow"
    elif "rapporteur" in r:
        level = "rapporteur"
    elif "chair" in r:
        level = "chair"
    else:
        level = "member"
    return level, staff


@router.get("/footprint")
def footprint(
    my_interests: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tier-0 engagement footprint over the PI-filtered set (both branches): declared
    spend leaders, competitive balance (org-type mix), and EP access depth. Factual
    only - no success or causation is implied."""
    _require_yellow(user)

    cq, pi_active = _filtered_query(db, user, my_interests, None, None, None, None)
    pq, _ = _mlm_query(db, user, my_interests, None, None)

    # One record per organisation, keyed by register id (fallback: normalised name),
    # carrying both-branch meeting counts + register metadata (spend, category).
    orgs: dict[str, dict] = {}

    def _key_rec(name, tr_id):
        rec = match_org(name, db, tr_id)
        key = (rec["tr_id"] if rec and rec.get("tr_id") else None) or norm_org(name or "")
        if not key:
            return None, None
        o = orgs.get(key)
        if o is None:
            o = orgs[key] = {
                "organisation": (rec["name"] if rec else name), "commission": 0, "parliament": 0,
                "category": rec.get("category") if rec else None,
                "balance_type": _balance_type(rec.get("category") if rec else None),
                "costs_min": rec.get("costs_min") if rec else None,
                "costs_max": rec.get("costs_max") if rec else None,
                "fte": rec.get("fte") if rec else None,
                "website": rec.get("website") if rec else None,
                "register_url": rec.get("register_url") if rec else None,
                "tr_id": rec.get("tr_id") if rec else None,
                "reached_rapporteur": False, "best_access": 0,
            }
        return key, o

    for org, c in (cq.with_entities(TM.organisation_met, func.count().label("c"))
                   .filter(TM.organisation_met.isnot(None))
                   .group_by(TM.organisation_met).all()):
        for piece in _split_orgs(org):       # one meeting can list several orgs
            _, o = _key_rec(piece, None)
            if o:
                o["commission"] += int(c)

    access_dist = Counter()       # level -> direct count
    access_staff = Counter()      # level -> staff-only count
    for org, role, c in (pq.with_entities(MLM.organisation, MLM.role, func.count().label("c"))
                         .group_by(MLM.organisation, MLM.role).all()):
        level, staff = _ep_access(role)
        (access_staff if staff else access_dist)[level] += int(c)
        for piece in _split_orgs(org):
            _, o = _key_rec(piece, None)
            if o:
                o["parliament"] += int(c)
                if not staff:
                    o["best_access"] = max(o["best_access"], _ACCESS_RANK[level])
                    if level == "rapporteur":
                        o["reached_rapporteur"] = True

    all_orgs = list(orgs.values())
    spend_leaders = sorted([o for o in all_orgs if o.get("costs_max")],
                           key=lambda x: (x["costs_max"] or 0), reverse=True)[:12]
    cat_counter = Counter(o["balance_type"] for o in all_orgs)
    category_mix = [{"type": k, "count": v} for k, v in cat_counter.most_common()]
    deepest = sorted([o for o in all_orgs if o["reached_rapporteur"]],
                     key=lambda x: (x["parliament"], x["commission"]), reverse=True)[:12]

    access_depth = [
        {"level": lvl, "label": _ACCESS_LABEL[lvl],
         "direct": access_dist.get(lvl, 0), "staff": access_staff.get(lvl, 0)}
        for lvl in ["rapporteur", "opinion_rapporteur", "shadow", "chair", "member"]
        if access_dist.get(lvl, 0) or access_staff.get(lvl, 0)
    ]

    return {
        "pi_active": pi_active,
        "total_organisations": len(all_orgs),
        "spend_leaders": [{
            "organisation": o["organisation"], "costs_min": o["costs_min"], "costs_max": o["costs_max"],
            "fte": o["fte"], "category": o["category"], "website": o["website"],
            "register_url": o["register_url"], "tr_id": o["tr_id"],
            "commission": o["commission"], "parliament": o["parliament"],
        } for o in spend_leaders],
        "category_mix": category_mix,
        "access_depth": access_depth,
        "deepest_access": [{
            "organisation": o["organisation"], "reached_rapporteur": o["reached_rapporteur"],
            "parliament": o["parliament"], "commission": o["commission"],
            "website": o["website"], "tr_id": o["tr_id"],
        } for o in deepest],
    }


@router.get("/org")
def org_footprint(
    name: Optional[str] = Query(None),
    tr_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """One organisation's cross-branch footprint: its Commission + Parliament meetings,
    the DGs/MEPs/dossiers it engaged, register identity (spend, category, website), and a
    monthly timeline. Factual footprint only - no verdict on outcomes."""
    _require_yellow(user)
    if not (name or tr_id):
        raise HTTPException(status_code=400, detail="Provide name or tr_id.")

    rec = match_org(name, db, tr_id)
    nm = norm_org(name or (rec["name"] if rec else ""))

    # Commission meetings: organisation_met packs multiple orgs + has no register id,
    # so fetch candidates by substring then confirm via split + normalised-name match.
    like_token = (rec["name"] if rec else name) or ""
    cand = (db.query(TM).filter(TM.organisation_met.ilike(f"%{like_token}%"))
            .order_by(TM.meeting_date.desc()).limit(500).all())
    comm_rows = [r for r in cand if any(norm_org(p) == nm for p in _split_orgs(r.organisation_met))]

    # Parliament meetings (match on normalised name, or tr_id).
    pq = db.query(MLM)
    conds = [MLM.organisation_norm == nm]
    if tr_id:
        conds.append(MLM.transparency_register_id == tr_id)
    pq = pq.filter(or_(*conds))
    ep_rows = pq.order_by(MLM.meeting_date.desc().nullslast()).limit(200).all()

    dgs = sorted({r.host_dg for r in comm_rows if r.host_dg})
    meps = {}
    for r in ep_rows:
        if r.mep_name:
            meps.setdefault(r.mep_name, r.role)
    dossiers = sorted({r.procedure_ref for r in ep_rows if r.procedure_ref})

    # Combined monthly timeline.
    months = Counter()
    for r in comm_rows + ep_rows:
        if r.meeting_date:
            months[r.meeting_date.strftime("%Y-%m")] += 1
    timeline = [{"month": m, "count": c} for m, c in sorted(months.items())][-18:]

    best = 0
    reached_rapporteur = False
    for r in ep_rows:
        lvl, staff = _ep_access(r.role)
        if not staff:
            best = max(best, _ACCESS_RANK[lvl])
            if lvl == "rapporteur":
                reached_rapporteur = True

    return {
        "organisation": rec["name"] if rec else name,
        "identity": {
            "tr_id": rec.get("tr_id") if rec else tr_id,
            "website": rec.get("website") if rec else None,
            "register_url": rec.get("register_url") if rec else None,
            "category": rec.get("category") if rec else None,
            "balance_type": _balance_type(rec.get("category") if rec else None),
            "country": rec.get("country") if rec else None,
            "fte": rec.get("fte") if rec else None,
            "costs_min": rec.get("costs_min") if rec else None,
            "costs_max": rec.get("costs_max") if rec else None,
        },
        "commission_count": len(comm_rows),
        "parliament_count": len(ep_rows),
        "reached_rapporteur": reached_rapporteur,
        "best_access_label": _ACCESS_LABEL.get(
            {4: "rapporteur", 3: "shadow", 2: "chair", 1: "member"}.get(best), None) if best else None,
        "dgs_met": [{"code": d, "name": _dg_name(d)} for d in dgs],
        "meps_met": [{"name": k, "role": v} for k, v in meps.items()],
        "dossiers": dossiers,
        "timeline": timeline,
        "commission_meetings": [{
            "meeting_date": r.meeting_date.isoformat() if r.meeting_date else None,
            "host_dg": r.host_dg, "host_name": r.host_name, "subject": r.subject,
        } for r in comm_rows[:60]],
        "parliament_meetings": [{
            "meeting_date": r.meeting_date.isoformat() if r.meeting_date else None,
            "mep_name": r.mep_name, "role": r.role, "committee": r.committee,
            "procedure_ref": r.procedure_ref,
            "procedure_url": (f"https://oeil.europarl.europa.eu/oeil/en/procedure-file?reference={r.procedure_ref}"
                              if r.procedure_ref else None),
        } for r in ep_rows[:60]],
    }
