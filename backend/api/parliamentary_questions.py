"""
Parliamentary Questions API (MEUB Section 3) - written + oral questions tabled by
MEPs, surfaced through the shared Policy-Interest lens.

The pain this kills: instead of going to the EP plenary questions SPA, typing a
topic, wading through hundreds of results, opening a question and then Googling
the author's MEP profile, a user opens this tab and sees - pre-filtered to their
Policy Interests - every question tabled on their topics, each with the author MEP
(profile link), the institution it targets, the official answer when it lands, and
an AI "why this matters" line.

Data: parliamentary_questions table (models.w4_entities.ParliamentaryQuestion),
sourced from the EP Open Data API. PI match = keyword on subject + question text
(committees/EuroVoc are not classified on EP question records), plus the asking
MEPs' committees when known. Read: Yellow+. AI one-liner: Mistral (NO Anthropic).
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.w4_entities import ParliamentaryQuestion
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import keywords_for_interests
from services.tracking.tracked_lens import tracked_anchors
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/parliamentary-questions", tags=["Parliamentary Questions"])

_MEP_BASE = "https://www.europarl.europa.eu/meps/en"
_AI_CACHE: dict = {}  # question_reference -> {lang: one_liner}  (in-process)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_yellow(user: User):
    if not user or user.subscription_tier == "white":
        raise HTTPException(status_code=403, detail="Parliamentary Questions require Yellow or Blue tier.")


def _is_blue(user: User) -> bool:
    return bool(user and (user.subscription_tier == "blue" or user.role == "admin"))


def _mep_profile_url(mep_id: Optional[str], name: Optional[str]) -> Optional[str]:
    """Deterministic EP MEP profile URL from id + name (the link the doceo page hides)."""
    if not mep_id:
        return None
    slug = re.sub(r"\s+", "_", (name or "").strip().upper()) or "MEP"
    return f"{_MEP_BASE}/{mep_id}/{slug}/home"


def _meps(r: ParliamentaryQuestion) -> List[dict]:
    """Author cards: pair ids with names where possible; build profile links."""
    ids = list(r.asking_mep_ids or [])
    names = list(r.asking_mep_names or [])
    out = []
    for i, name in enumerate(names):
        mid = ids[i] if i < len(ids) else None
        out.append({"id": mid, "name": name, "profile_url": _mep_profile_url(mid, name)})
    # ids without a paired name (rare)
    for mid in ids[len(names):]:
        out.append({"id": mid, "name": None, "profile_url": _mep_profile_url(mid, None)})
    return out


def _apply_pi(query, user: User):
    """Shared MEUB PI lens. A question matches when its subject/text mentions a PI
    keyword. (EP question records carry no EuroVoc/committee classification, so the
    keyword match on subject + question text is the reliable signal - the same
    approach used for EC Consultations.) Returns (query, pi_active)."""
    interests = _interest_list(user)
    if not interests:
        return query, False
    kws = keywords_for_interests(interests)
    if not kws:
        return query, False
    clauses = []
    for kw in kws:
        like = f"%{kw}%"
        clauses.append(ParliamentaryQuestion.subject.ilike(like))
        clauses.append(ParliamentaryQuestion.text_question.ilike(like))
    return query.filter(or_(*clauses)), True


def _clean_question_text(raw: Optional[str]) -> Optional[str]:
    """Strip the doceo boilerplate from a stored question dump, leaving just the
    body. The header (Question for written answer / reference / 'to the' /
    addressee / Rule N / author / group) and the trailing 'Submitted:' line are
    already shown structurally in the modal, so we drop everything up to and
    including the Subject line, and merge lone numbered markers (1. 2.) with the
    text that follows."""
    if not raw:
        return raw
    lines = [ln.strip() for ln in raw.split("\n")]
    start = 0
    for i, ln in enumerate(lines):
        if ln.lower().startswith("subject:"):
            start = i + 1 if len(ln) > len("subject:") + 1 else i + 2
            break
    body: List[str] = []
    for ln in lines[start:]:
        if not ln:
            continue
        if re.match(r"^submitted\s*:", ln, re.I):
            break
        body.append(ln)
    merged: List[str] = []
    i = 0
    while i < len(body):
        if re.match(r"^\(?\d+\.?\)?$", body[i]) and i + 1 < len(body):  # lone "1." / "(1)"
            merged.append(f"{body[i]} {body[i + 1]}")
            i += 2
        else:
            merged.append(body[i])
            i += 1
    return "\n".join(merged).strip() or raw.strip()


def _clean_answer_text(raw: Optional[str]) -> Optional[str]:
    """Light clean for the Commission answer: drop empty lines + merge numbered
    markers. Keeps the 'Answer given by ...' attribution line (informative)."""
    if not raw:
        return raw
    lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
    merged: List[str] = []
    i = 0
    while i < len(lines):
        if re.match(r"^\(?\d+\.?\)?$", lines[i]) and i + 1 < len(lines):
            merged.append(f"{lines[i]} {lines[i + 1]}")
            i += 2
        else:
            merged.append(lines[i])
            i += 1
    return "\n".join(merged).strip() or raw.strip()


def _summary(r: ParliamentaryQuestion, tracked_procs: set = frozenset(),
             tracked_celex: set = frozenset()) -> dict:
    answered = bool(r.text_answer and len(r.text_answer.strip()) > 10)
    return {
        "reference": r.question_reference,
        "matches_tracked": bool((r.procedure_ref and r.procedure_ref in tracked_procs)
                                or (set(r.related_celex or []) & tracked_celex)),
        "type": r.question_type.value if hasattr(r.question_type, "value") else r.question_type,
        "subject": r.subject,
        "submitted_date": r.submitted_date.isoformat() if r.submitted_date else None,
        "answered_date": r.answered_date.isoformat() if r.answered_date else None,
        "meps": _meps(r),
        "answering_institution": r.answering_institution,
        "answering_commissioner": r.answering_commissioner,
        "related_celex": list(r.related_celex or []),
        "procedure_ref": r.procedure_ref,
        "source_url": r.source_url,
        "answer_url": r.answer_url,
        "answered": answered,
    }


# ---------------------------------------------------------------------------
# List + new-count
# ---------------------------------------------------------------------------

@router.get("")
def list_questions(
    my_interests: bool = Query(True, description="Restrict to the user's Policy Interests"),
    my_files: bool = Query(False, description="Restrict to questions touching files you track"),
    question_type: Optional[str] = Query(None, description="written|oral|priority|question_time"),
    answered: Optional[bool] = Query(None, description="Filter answered / awaiting answer"),
    search: Optional[str] = Query(None),
    sort_by: str = Query("date", description="date | relevance"),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """PI-filtered list of parliamentary questions (the user's topics, newest first)."""
    _require_yellow(user)
    tracked = tracked_anchors(db, str(user.id)) if user else {}
    tracked_procs = tracked.get("procedures", set())
    tracked_celex = tracked.get("celex", set())
    q = db.query(ParliamentaryQuestion)
    pi_active = False
    if my_interests:
        q, pi_active = _apply_pi(q, user)
    if my_files and (tracked_procs or tracked_celex):
        conds = []
        if tracked_procs:
            conds.append(ParliamentaryQuestion.procedure_ref.in_(list(tracked_procs)))
        if tracked_celex:
            cx = sorted(tracked_celex)
            arr = ", ".join(f":rc_{i}" for i in range(len(cx)))
            conds.append(text(f"related_celex && ARRAY[{arr}]::text[]")
                         .bindparams(**{f"rc_{i}": c for i, c in enumerate(cx)}))
        if conds:
            q = q.filter(or_(*conds))
    if question_type:
        q = q.filter(ParliamentaryQuestion.question_type == question_type.lower())
    if answered is True:
        q = q.filter(ParliamentaryQuestion.text_answer.isnot(None),
                     func.length(ParliamentaryQuestion.text_answer) > 10)
    elif answered is False:
        q = q.filter(or_(ParliamentaryQuestion.text_answer.is_(None),
                         func.length(func.coalesce(ParliamentaryQuestion.text_answer, "")) <= 10))
    if search:
        like = f"%{search}%"
        q = q.filter(or_(ParliamentaryQuestion.subject.ilike(like),
                         ParliamentaryQuestion.text_question.ilike(like)))
    total = q.count()
    q = q.order_by(ParliamentaryQuestion.submitted_date.desc().nullslast())
    rows = q.offset(offset).limit(limit).all()
    return {"total": total, "pi_active": pi_active,
            "files_active": bool(my_files and (tracked_procs or tracked_celex)),
            "has_tracked_files": bool(tracked_procs or tracked_celex),
            "items": [_summary(r, tracked_procs, tracked_celex) for r in rows]}


@router.get("/new-count")
def new_count(
    days: int = Query(7, ge=1, le=60),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """How many PI-matching questions were tabled in the last `days` - drives the
    'N new on your interests' warn badge."""
    _require_yellow(user)
    since = date.today() - timedelta(days=days)
    q = db.query(ParliamentaryQuestion).filter(ParliamentaryQuestion.submitted_date >= since)
    q, pi_active = _apply_pi(q, user)
    return {"count": q.count(), "days": days, "pi_active": pi_active}


# ---------------------------------------------------------------------------
# Detail + AI one-liner
# ---------------------------------------------------------------------------

@router.get("/{reference:path}")
def get_question(
    reference: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _require_yellow(user)
    r = db.query(ParliamentaryQuestion).filter(
        ParliamentaryQuestion.question_reference == reference).first()
    if not r:
        raise HTTPException(status_code=404, detail="Question not found.")
    out = _summary(r)
    out.update({
        "text_question": _clean_question_text(r.text_question),
        "text_answer": _clean_answer_text(r.text_answer),
        "parliamentary_term": r.parliamentary_term,
        "committees": list(r.committees or []),
        "ai_explainer": (_AI_CACHE.get(r.question_reference) or {}).get("en"),
    })
    return out


@router.post("/{reference:path}/explain")
async def explain_question(
    reference: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """One-line 'why this matters' for a question (Mistral, NO Anthropic). Cached."""
    _require_yellow(user)
    r = db.query(ParliamentaryQuestion).filter(
        ParliamentaryQuestion.question_reference == reference).first()
    if not r:
        raise HTTPException(status_code=404, detail="Question not found.")
    cached = (_AI_CACHE.get(reference) or {}).get("en")
    if cached:
        return {"reference": reference, "explainer": cached, "cached": True}
    text = (_clean_question_text(r.text_question) or r.subject or "")[:4000]
    prompt = (
        "In ONE sentence (max 35 words), explain why this European Parliament "
        "question matters for a policy professional - the concrete issue and stake. "
        "British English, no preamble, no quotes.\n\n"
        f"Subject: {r.subject}\n\nQuestion: {text}"
    )
    explainer = None
    try:
        # Qwen via HF (non-chat OSS path) - guarantees NO Anthropic, unlike the
        # multi-provider chain which can fall back to Claude when Mistral 401s.
        from services.ai.huggingface_service import get_huggingface_service
        hf = get_huggingface_service()
        explainer = await hf.chat_completion(
            model="Qwen/Qwen3-30B-A3B-Instruct-2507:featherless-ai",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=90, temperature=0.2,
        )
        explainer = (explainer or "").strip()
    except Exception as e:
        logger.warning("[parl-q] explain failed for %s: %s", reference, e)
    if not explainer:
        raise HTTPException(status_code=502, detail="Could not generate explainer.")
    _AI_CACHE.setdefault(reference, {})["en"] = explainer
    return {"reference": reference, "explainer": explainer, "cached": False}
