"""
"What touched your workspace" digest (Phase 4 — the linking-layer capstone).

For a user, computes the cross-surface connections to the files they track and
the areas they follow — votes on their dossiers, OJ acts on their laws, MEP
questions on their files, news in their areas — by query-time anchor
intersection (no stored link table; pull, not push). Each section is fail-soft:
one bad query never breaks the digest.

Reuses the tracked-file anchor set (services/tracking/tracked_lens). Hard
sections key on procedure/CELEX (assertions); the news section is the softer
policy-area overlap.
"""

import logging
from datetime import date, timedelta
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.tracked_lens import tracked_anchors

logger = logging.getLogger(__name__)

NEWS_WINDOW_DAYS = 14
LIMIT = 5


def _q(db: Session, sql: str, params: dict) -> List[dict]:
    try:
        return [dict(r) for r in db.execute(text(sql), params).mappings().all()]
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("digest section failed: %s", exc)
        db.rollback()
        return []


def _dedupe(items: List[dict]) -> List[dict]:
    """Collapse rows that render identically.

    One file can carry several roll-call votes, and one committee meeting
    several documents of the same kind, so the raw rows produced repeated
    lines: "Political repression and humanitarian situation in Cuba" twice in
    a row, "Amendments: Generational renewal in agriculture" twice. The digest
    is a glance, not a log — the drill-through goes to the full surface — so
    only the first (most recent, since every query orders by date DESC) line
    of each title is kept.
    """
    seen = set()
    out: List[dict] = []
    for item in items:
        key = " ".join((item.get("title") or "").lower().split())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def workspace_digest(db: Session, user) -> dict:
    """Sections of items touching the user's tracked files / interests."""
    interests = list(_interest_list(user))
    tracked = tracked_anchors(db, str(user.id)) if user else {}
    procs = sorted(tracked.get("procedures", set()))
    celex = sorted(tracked.get("celex", set()))
    tracked_pa = sorted(tracked.get("policy_areas", set()))

    sections: List[dict] = []

    # 1. Votes on dossiers you track (hard).
    if procs:
        rows = _q(db,
            """
            SELECT title, procedure_ref, level, vote_date::text AS d, source_url
            FROM ep_roll_call_votes
            WHERE procedure_ref = ANY(:procs)
            ORDER BY vote_date DESC NULLS LAST LIMIT :lim
            """, {"procs": procs, "lim": LIMIT})
        if rows:
            sections.append({
                "key": "votes", "label": "Votes on files you track",
                "drill": "/my-eu-bubble?tab=votes",
                "items": [{"title": r["title"], "date": r["d"], "ref": r["procedure_ref"],
                           "url": r["source_url"]} for r in rows],
            })

    # 2. Official Journal acts touching your files (hard: CELEX or procedure).
    if celex or procs:
        rows = _q(db,
            """
            SELECT title, celex, oj_date::text AS d, eurlex_url
            FROM oj_entries
            WHERE (celex = ANY(:celex)) OR (matched_procedure_ref = ANY(:procs))
            ORDER BY oj_date DESC NULLS LAST LIMIT :lim
            """, {"celex": celex or [""], "procs": procs or [""], "lim": LIMIT})
        if rows:
            sections.append({
                "key": "oj", "label": "Official Journal on files you track",
                "drill": "/my-eu-bubble?tab=oj",
                "items": [{"title": r["title"], "date": r["d"], "ref": r["celex"],
                           "url": r["eurlex_url"]} for r in rows],
            })

    # 3. MEP questions on your files (hard: procedure or related CELEX).
    if procs or celex:
        rows = _q(db,
            """
            SELECT subject AS title, question_reference AS ref, submitted_date::text AS d, source_url
            FROM parliamentary_questions
            WHERE (procedure_ref = ANY(:procs))
               OR (related_celex && ARRAY[:c0]::text[] AND :has_celex)
            ORDER BY submitted_date DESC NULLS LAST LIMIT :lim
            """,
            # related_celex overlap built below when celex present; keep the
            # query simple/safe by parametrising the first CELEX + a guard.
            {"procs": procs or [""], "c0": (celex[0] if celex else ""),
             "has_celex": bool(celex), "lim": LIMIT})
        if rows:
            sections.append({
                "key": "questions", "label": "Questions on files you track",
                "drill": "/my-eu-bubble?tab=parliamentary_questions",
                "items": [{"title": r["title"], "date": r["d"], "ref": r["ref"],
                           "url": r["source_url"]} for r in rows],
            })

    # 3b. EP committee meeting DOCUMENTS on dossiers you track (hard: procedure
    # join to ep_emeeting_documents — the classified draft reports, amendments,
    # voting lists, compromise amendments, with direct PDF links). doc_kind is
    # the classified type. See memory/reference_ep_emeeting.md.
    if procs:
        kind_label = {
            "draft_report": "Draft report", "amendment": "Amendments",
            "voting_list": "Voting list", "compromise_amendments": "Compromise amendments",
            "report": "Report", "adopted_text": "Adopted text",
            "opinion": "Opinion", "draft_opinion": "Draft opinion", "agenda": "Agenda",
        }
        keys = ", ".join(f":ed{i}" for i in range(len(procs)))
        params = {f"ed{i}": p for i, p in enumerate(procs)}
        params["lim"] = LIMIT
        rows = _q(db,
            f"""
            SELECT doc_kind, title, item_title, committee_code, procedure_ref,
                   meeting_date::text AS d, pdf_url, source_url
            FROM ep_emeeting_documents
            WHERE procedure_ref = ANY(ARRAY[{keys}])
              AND doc_kind IN ('draft_report','amendment','voting_list','compromise_amendments',
                               'report','adopted_text','opinion','draft_opinion')
            ORDER BY meeting_date DESC NULLS LAST LIMIT :lim
            """, params)
        if rows:
            sections.append({
                "key": "emeeting",
                "label": "Committee documents on files you track",
                "drill": "/my-eu-bubble?tab=my_files",
                "items": [{
                    "title": f"{kind_label.get(r['doc_kind'], r['doc_kind'])}: "
                             f"{r['item_title'] or r['title'] or r['committee_code']}",
                    "date": r["d"],
                    "ref": r["procedure_ref"],
                    "url": r["pdf_url"] or r["source_url"],
                } for r in rows],
            })

    # 4. News in your areas / about files you track (soft: policy-area overlap).
    if tracked_pa or interests:
        areas = tracked_pa or interests
        cutoff = (date.today() - timedelta(days=NEWS_WINDOW_DAYS)).isoformat()
        keys = ", ".join(f":a{i}" for i in range(len(areas)))
        params = {f"a{i}": a for i, a in enumerate(areas)}
        params.update({"cutoff": cutoff, "lim": LIMIT})
        rows = _q(db,
            f"""
            SELECT title, news_date::text AS d, source_url
            FROM eu_news_items
            WHERE policy_areas::text[] && ARRAY[{keys}]::text[]
              AND news_date >= :cutoff
            ORDER BY news_date DESC NULLS LAST LIMIT :lim
            """, params)
        if rows:
            sections.append({
                "key": "news",
                "label": "News in your areas" if not tracked_pa else "News about files you track",
                "drill": "/my-eu-bubble?tab=news",
                "items": [{"title": r["title"], "date": r["d"], "url": r["source_url"]} for r in rows],
            })

    for section in sections:
        section["items"] = _dedupe(section["items"])

    return {
        "has_tracked_files": bool(procs or celex or tracked_pa),
        "sections": sections,
    }
