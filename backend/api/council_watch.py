"""
Council Watch API (MEUB Section 3) - what the Council of the EU is doing on the
user's topics, through the shared Policy-Interest lens.

A unified timeline of Council activity: configuration MEETINGS (from the calendar,
PI-matched by Council configuration) + OUTCOMES / press (from the EU news feed,
PI-matched by keyword). Complements the Votes tab (how member states voted) and
My EU Calendar (when). Read: Yellow+. No Anthropic.
"""

from __future__ import annotations

import logging
import re
from datetime import date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.eu_calendar import EUCalendarEvent
from models.eu_news_item import EuNewsItem
from models.ep_vote import EpVote
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import (
    committees_for_interests, council_configs_for_interests, keywords_for_interests,
)
from services.linking.emeeting_links import council_watch_documents
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/council-watch", tags=["Council Watch"])

_COUNCIL_INST = ("COUNCIL", "EUROPEAN_COUNCIL")


def _require_yellow(user: User):
    if not user or user.subscription_tier == "white":
        raise HTTPException(status_code=403, detail="Council Watch requires Yellow or Blue tier.")


def _pi(user: User):
    interests = _interest_list(user)
    return (council_configs_for_interests(interests) if interests else set(),
            keywords_for_interests(interests) if interests else set())


def _meeting_items(db, user, my_interests, search) -> List[dict]:
    q = db.query(EUCalendarEvent).filter(EUCalendarEvent.institution.in_(_COUNCIL_INST))
    if my_interests:
        configs, kws = _pi(user)
        clauses = []
        if configs:
            clauses.append(EUCalendarEvent.council_configuration.in_(list(configs)))
        for kw in kws:
            clauses.append(EUCalendarEvent.title.ilike(f"%{kw}%"))
        if clauses:
            q = q.filter(or_(*clauses))
    if search:
        q = q.filter(EUCalendarEvent.title.ilike(f"%{search}%"))
    rows = q.order_by(EUCalendarEvent.start_date.desc()).limit(120).all()
    return [{
        "kind": "meeting",
        "date": r.start_date.isoformat() if r.start_date else None,
        "title": r.title,
        "configuration": r.council_configuration,
        "summary": r.description,
        "url": r.agenda_url or r.source_url,
        "institution": r.institution.value if hasattr(r.institution, "value") else r.institution,
    } for r in rows]


def _outcome_items(db, user, my_interests, search) -> List[dict]:
    q = db.query(EuNewsItem).filter(EuNewsItem.institution == "COUNCIL")
    if my_interests:
        _configs, kws = _pi(user)
        if kws:
            clauses = []
            for kw in kws:
                clauses.append(EuNewsItem.title.ilike(f"%{kw}%"))
                clauses.append(EuNewsItem.summary.ilike(f"%{kw}%"))
            q = q.filter(or_(*clauses))
    if search:
        q = q.filter(EuNewsItem.title.ilike(f"%{search}%"))
    rows = q.order_by(EuNewsItem.news_date.desc()).limit(80).all()
    return [{
        "kind": "outcome",
        "date": r.news_date.isoformat() if r.news_date else None,
        "title": r.title,
        "configuration": None,
        "summary": r.summary,
        "url": r.source_url,
        "image_url": r.image_url,
    } for r in rows]


def _document_items(db, user, my_interests, search) -> List[dict]:
    """Council texts transmitted to EP committees (eMeeting `council_document`):
    the Council's decisions under consent procedures, its first-reading positions,
    its budget position. Lens: the committees and keywords of the user's interests."""
    committees, kws = set(), set()
    if my_interests:
        interests = _interest_list(user)
        if interests:
            committees = committees_for_interests(interests)
            kws = keywords_for_interests(interests)
    rows = council_watch_documents(db, committees, kws, search, limit=80)
    return [{
        "kind": "document",
        "date": r["meeting_date"].isoformat() if r["meeting_date"] else None,
        "title": r["title"] or r["item_title"] or r["reference"] or "Council document",
        "configuration": None,
        "summary": r["item_title"] if r["item_title"] and r["item_title"] != r["title"] else None,
        "url": r["url"],
        "reference": r["reference"],
        "committee": r["committee_code"],
        "procedure_ref": r["procedure_ref"],
        "is_pdf": bool(r["is_pdf"]),
    } for r in rows]


# Council configuration code -> the name its agendas are headed with.
_CONFIG_NAME = {
    "AGRIFISH": "Agriculture and Fisheries", "COMPET": "Competitiveness",
    "ECOFIN": "Economic and Financial Affairs", "EPSCO": "Employment, Social Policy",
    "ENVI": "Environment", "ENV": "Environment", "EYCS": "Education, Youth, Culture",
    "EDUC": "Education, Youth, Culture", "FAC": "Foreign Affairs", "GAC": "General Affairs",
    "JHA": "Justice and Home Affairs", "TTE": "Transport, Telecommunications and Energy",
}


def _register_items(db, user, my_interests, search) -> List[dict]:
    """The Council's OWN register (28 Sep 2026): working-party meeting notices,
    Council and Coreper agendas and standard documents, discovered by reference on
    data.consilium (scripts/discover_council_documents.py). The layer below the
    ministerial meetings: which working party meets on what, and when.

    Lens: a keyword of the user's interests in the title or the document text (an
    agenda names its files in its items), or one of the user's Council
    configurations (its heading name, or its code in the document header)."""
    from sqlalchemy import text as _text
    where = ["source_slug = 'consilium_register'", "category = 'document'"]
    params: dict = {}
    if my_interests:
        configs, kws = _pi(user)
        lens = []
        # Word-boundary regex, not ILIKE: on full document text the keyword "sme"
        # matched inside "assessment", so every Council document passed every lens
        # (28 Sep 2026). \y is PostgreSQL's boundary (\b is a backspace there).
        # Boundary at the start only, so stems ("industr") still match; at both
        # ends for keywords deliberately padded with spaces (" ai ").
        alts = []
        for kw in sorted(kws):
            core = re.escape(kw.strip().lower())
            if not core:
                continue
            alts.append(rf"\y{core}\y" if kw != kw.strip() else rf"\y{core}")
        if alts:
            lens.append("(title ~* :kwrx OR html_content ~* :kwrx)")
            params["kwrx"] = "(" + "|".join(alts) + ")"
        for j, code in enumerate(sorted(configs)):
            lens.append(f"(html_content ILIKE :cc{j} OR title ILIKE :cn{j})")
            params[f"cc{j}"] = f"%OJ CONS {code}%"
            params[f"cn{j}"] = f"%{_CONFIG_NAME.get(code, code)}%"
        if not lens:
            return []
        where.append("(" + " OR ".join(lens) + ")")
    if search:
        where.append("(title ILIKE :s OR external_id ILIKE :s)")
        params["s"] = f"%{search}%"
    rows = db.execute(_text(f"""
        SELECT external_id, title, url, published_date, extra_metadata->>'meeting_date' AS meeting_date,
               left(coalesce(summary, ''), 600) AS summary, html_content
          FROM institutional_publications
         WHERE {' AND '.join(where)}
         ORDER BY coalesce((extra_metadata->>'meeting_date')::date, published_date) DESC NULLS LAST, external_id
         LIMIT 2000"""), params).mappings().all()
    if my_interests:
        # SQL finds candidates; relevance is decided here. Council documents are long
        # and span many topics, so interest words are common in their text ("economic"
        # in 43% of them, "environment" 34%): a keyword must be in the TITLE, or the
        # document must be one of the user's Council configurations, or its text must
        # carry at least three distinct keywords (the rule the PQ digest uses).
        configs, kws = _pi(user)
        rxs = [re.compile(r"\b" + re.escape(k.strip().lower()) + (r"\b" if k != k.strip() else ""))
               for k in kws if k.strip()]
        cfg = [(f"oj cons {c.lower()}", _CONFIG_NAME.get(c, c).lower()) for c in configs]

        def relevant(r) -> bool:
            title = (r["title"] or "").lower()
            body = (r["html_content"] or "").lower()
            if any(rx.search(title) for rx in rxs):
                return True
            if any(code in body[:3000] or name in title for code, name in cfg):
                return True
            # Only in SHORT documents (notices, agendas, short notes), where every term
            # is an agenda item. A long report mentions everything: a 72,000-character
            # macro-financial assistance paper reached a copper refiner on "energy",
            # "emission" and "nature". Long documents must match on their title.
            return len(body) < 15000 and sum(1 for rx in rxs if rx.search(body)) >= 3

        rows = [r for r in rows if relevant(r)]
    out = []
    for r in rows:          # the list endpoint paginates; the KPI counts the true total
        when = r["meeting_date"] or (r["published_date"].isoformat() if r["published_date"] else None)
        out.append({
            "kind": "register",
            "date": (when or "")[:10] or None,
            # Listing-route titles carry page furniture ("... Also available in: BG SV").
            "title": re.sub(r"\s+Also available in:.*$", "", r["title"] or "").strip() or r["external_id"],
            "configuration": None,
            "summary": r["summary"] or None,
            "url": r["url"],
            "reference": r["external_id"],
            "meeting_date": r["meeting_date"],
            "is_pdf": bool(r["url"] and r["url"].endswith("/pdf")),
        })
    return out


@router.get("")
def list_activity(
    my_interests: bool = Query(True),
    kind: str = Query("all", description="all | meeting | outcome | document | register"),
    search: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unified Council activity feed (meetings, outcomes, Council documents and the Council's own register), PI-filtered, newest first."""
    _require_yellow(user)
    items: List[dict] = []
    if kind in ("all", "meeting"):
        items += _meeting_items(db, user, my_interests, search)
    if kind in ("all", "outcome"):
        items += _outcome_items(db, user, my_interests, search)
    if kind in ("all", "document"):
        items += _document_items(db, user, my_interests, search)
    if kind in ("all", "register"):
        items += _register_items(db, user, my_interests, search)
    items.sort(key=lambda x: x["date"] or "", reverse=True)
    pi_active = my_interests and bool(any(_pi(user)))
    return {"total": len(items), "pi_active": pi_active,
            "items": items[offset:offset + limit]}


class SummariseRequest(BaseModel):
    title: str
    summary: Optional[str] = None
    kind: str = "meeting"
    configuration: Optional[str] = None
    lang: str = "en"


_SUM_CACHE: dict = {}  # content-hash -> summary (in-process)


@router.post("/summarise")
async def summarise(
    payload: SummariseRequest,
    user: User = Depends(get_current_user),
):
    """AI 'what this means' for a Council item, in the user's language. Qwen via HF
    (NO Anthropic). Cached in-process by content + language."""
    _require_yellow(user)
    from services.transcript_summary_service import LANG_NAMES
    lang = (payload.lang or "en").lower()
    lname = LANG_NAMES.get(lang, "English")
    import hashlib
    key = hashlib.md5(f"{payload.title}|{payload.summary}|{lang}".encode("utf-8")).hexdigest()
    if key in _SUM_CACHE:
        return {"summary": _SUM_CACHE[key], "lang": lang, "cached": True}

    kind = {"meeting": "meeting",
            "document": "document transmitted to the European Parliament (such as a "
                        "Council decision, a first-reading position or its budget position)",
            "register": "document from its public register (a working party's notice of "
                        "meeting and agenda, a Council or Coreper agenda, or a standard document)",
            }.get(payload.kind, "outcome / press item")
    cfg = f" ({payload.configuration} configuration)" if payload.configuration else ""
    prompt = (
        f"This is a Council of the EU {kind}{cfg}. In 2-3 sentences, written in "
        f"{lname}, explain what it concerns and why it matters for an EU policy "
        "professional. Be concrete and factual; no preamble, no quotes.\n\n"
        f"Title: {payload.title}\n\nDetails: {(payload.summary or '')[:3000]}"
    )
    try:
        from services.ai.huggingface_service import get_huggingface_service
        out = await get_huggingface_service().chat_completion(
            model="Qwen/Qwen3-30B-A3B-Instruct-2507:featherless-ai",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=220, temperature=0.2,
        )
        out = (out or "").strip()
    except Exception as e:
        logger.warning("[council-watch] summarise failed: %s", e)
        out = None
    if not out:
        # Hugging Face is out of credits (HTTP 402 since ~24 Sep 2026), which made this
        # button fail for every item. The chat chain's open-model lanes take over.
        import services.ai.multi_provider_service as mps
        for name in ("CerebrasProvider", "GeminiProvider", "MistralProvider", "ScalewayProvider"):
            try:
                prov = getattr(mps, name)()
                if not prov.is_available:
                    continue
                resp = await prov.generate(system_prompt="You explain EU Council documents plainly.",
                                           messages=[{"role": "user", "content": prompt}],
                                           max_tokens=260, temperature=0.2)
                out = (getattr(resp, "message", "") or "").strip()
                if out:
                    break
            except Exception as e:  # noqa: BLE001
                logger.info("[council-watch] %s failed: %s", name, str(e)[:120])
    if not out:
        raise HTTPException(status_code=502, detail="Could not generate summary.")
    _SUM_CACHE[key] = out
    return {"summary": out, "lang": lang, "cached": False}


@router.get("/permreps")
def permreps(user: User = Depends(get_current_user)):
    """The 27 Member State Permanent Representations to the EU (+ Catalonia) - the
    member states' working level at the Council. Curated directory, links only."""
    _require_yellow(user)
    from knowledge_base.permanent_representations import PERMREPS
    return {"items": PERMREPS, "total": sum(1 for p in PERMREPS if not p.get("region"))}


@router.get("/stats")
def stats(
    my_interests: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """KPIs for the Council Watch dashboard."""
    _require_yellow(user)
    configs, _kws = _pi(user)
    meetings = _meeting_items(db, user, my_interests, None)
    outcomes = _outcome_items(db, user, my_interests, None)
    today = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=90)).isoformat()
    upcoming = sum(1 for m in meetings if (m["date"] or "") >= today)
    recent_outcomes = sum(1 for o in outcomes if (o["date"] or "") >= cutoff)
    council_votes = db.query(func.count(EpVote.id)).filter(EpVote.level == "council").scalar() or 0
    council_documents = len(_document_items(db, user, my_interests, None))
    register_items = _register_items(db, user, my_interests, None)
    upcoming_register = sum(1 for r in register_items if (r["meeting_date"] or "") >= today)
    # configurations present in the user's meeting set
    present_configs = sorted({m["configuration"] for m in meetings if m["configuration"]})
    return {
        "pi_active": my_interests and bool(configs),
        "upcoming_meetings": upcoming,
        "total_meetings": len(meetings),
        "recent_outcomes": recent_outcomes,
        "your_configurations": present_configs,
        "council_votes": int(council_votes),
        "council_documents": council_documents,
        "register_documents": len(register_items),
        "register_upcoming": upcoming_register,
    }
