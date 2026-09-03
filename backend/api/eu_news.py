"""
MEUB News API — EU institutional news, PI-filterable, image-rich.

Reads eu_news_items (migration 101). Powers the Section-1 "News" tab: a featured
hero + a card feed. Phase-1 aligned: filtering goes through the shared PI-filter
builder (services/tracking/pi_filter.py) over the now-populated `policy_areas`
join key (+ DG + keyword recall), and a "My Tracked Files" lens flags/keeps news
topically related to the files the user follows (tracked_lens). Two registers:
`matches_interests` (soft, your Policy Interests) and `matches_tracked` (the
files you track).
"""

import logging
import re
from datetime import date as _date
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Date, func, or_, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from models.eu_news_item import EuNewsItem
from services.tracking.tracked_files_seeder import _interest_list
from services.tracking.pi_committee_crosswalk import dgs_for_interests, keywords_for_interests
from services.tracking.pi_filter import AnchorSpec, build_pi_clause
from services.tracking.tracked_lens import tracked_anchors
from knowledge_base.eu_calendar_institutions import COMMISSION_DG_NAME
from .auth_optional import get_current_user_optional

logger = logging.getLogger(__name__)

_EPOCH = _date(1970, 1, 1)  # sort sentinel for a row with neither date

router = APIRouter(prefix="/api/eu-news", tags=["EU News"])

# News exposes policy_areas (the canonical join key) + a DG + free text.
NEWS_SPEC = AnchorSpec(
    policy_areas_col="policy_areas",
    dg_col="commission_dg",
    keyword_cols=("title", "summary"),
)


def _soft_match(item: EuNewsItem, interests: set, dgs: set, keywords: List[str]) -> Optional[str]:
    """Why this item is in the user's interests (soft register), or None."""
    overlap = set(item.policy_areas or []) & interests
    if overlap:
        return "In your interests: " + ", ".join(sorted(overlap))
    if item.commission_dg and item.commission_dg in dgs:
        return f"Matches a department you follow ({item.commission_dg})"
    hay = f"{item.title or ''} {item.summary or ''}".lower()
    if any(k in hay for k in keywords):
        return "Mentions a topic in your interests"
    return None


def _tracked_match(item: EuNewsItem, tracked_pa: set) -> Optional[str]:
    """Why this item relates to a file the user tracks (hard-ish register), or None."""
    overlap = set(item.policy_areas or []) & tracked_pa
    if overlap:
        return "Related to files you track: " + ", ".join(sorted(overlap))
    return None


def _item_dict(e: EuNewsItem, interests: set, dgs: set, keywords: List[str], tracked_pa: set) -> dict:
    soft = _soft_match(e, interests, dgs, keywords)
    hard = _tracked_match(e, tracked_pa)
    return {
        "id": str(e.id),
        "title": e.title,
        "summary": e.summary,
        "news_date": e.news_date.isoformat() if e.news_date else None,
        # Internal ordering key ONLY -- mirrors the coalesce the list query uses.
        # Not a publication date and never rendered: `news_date` stays null when
        # the upstream feed carried no date (feedback_backfill_no_hallucination).
        "_order_date": (e.news_date or (e.created_at.date() if e.created_at else None)),
        "institution": e.institution,
        "commission_dg": e.commission_dg,
        "dg_name": COMMISSION_DG_NAME.get(e.commission_dg) if e.commission_dg else None,
        "item_type": e.item_type,
        "source_key": e.source_key,
        "policy_areas": list(e.policy_areas or []),
        "image_url": e.image_url,
        "source_url": e.source_url,
        "matches_interests": bool(soft),
        "interest_reason": soft,
        "matches_tracked": bool(hard),
        "tracked_reason": hard,
    }


@router.get("/items", summary="EU institutional news feed",
            description=(
                "**What it does**\nReturns the aggregated EU institutional news feed "
                "(Commission hub + every DG/agency newsroom + Parliament + outlets), "
                "image-rich and sorted newest-first, with a featured set for the hero.\n\n"
                "**When to use it**\nThe MEUB 'News' tab.\n\n"
                "**Input**\n`my_interests=true` keeps only news in your Policy Interests; "
                "`my_files=true` keeps only news related to the files you track; "
                "`institution`; `commission_dg`; `item_type`; `search`; `limit`/`offset`.\n\n"
                "**You get back**\nNews cards (title, summary, image, DG, date, areas, link) "
                "each flagged with why it matches your interests / tracked files, plus "
                "facets and a featured list."))
def list_news(
    my_interests: bool = Query(False),
    my_files: bool = Query(False),
    institution: Optional[str] = Query(None),
    commission_dg: Optional[str] = Query(None),
    item_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    try:
        interests = set(_interest_list(current_user)) if current_user else set()
        dgs = dgs_for_interests(interests)
        keywords = sorted(keywords_for_interests(interests))
        tracked = tracked_anchors(db, str(current_user.id)) if current_user else {}
        tracked_pa = tracked.get("policy_areas", set())

        q = db.query(EuNewsItem)

        # Soft register: Policy Interests, via the shared builder (policy_areas primary).
        if my_interests and interests:
            sql, params = build_pi_clause(interests, NEWS_SPEC, pfx="pi")
            if sql != "TRUE":
                q = q.filter(text(sql).bindparams(**params))

        # Hard register: My Tracked Files lens (topical overlap with tracked files).
        if my_files and tracked_pa:
            q = q.filter(text("policy_areas::text[] && ARRAY[" +
                              ", ".join(f":tf_{i}" for i in range(len(tracked_pa))) +
                              "]::text[]").bindparams(**{f"tf_{i}": pa for i, pa in enumerate(sorted(tracked_pa))}))

        if institution:
            q = q.filter(EuNewsItem.institution == institution)
        if commission_dg:
            q = q.filter(EuNewsItem.commission_dg == commission_dg)
        if item_type:
            q = q.filter(EuNewsItem.item_type == item_type)
        if search:
            q = q.filter(or_(EuNewsItem.title.ilike(f"%{search}%"),
                             EuNewsItem.summary.ilike(f"%{search}%")))

        total = q.count()
        # Order by the publication date when we have one, and by when we first
        # saw the item when we do not.
        #
        # Why (found in /news, 19 Aug 2026): `nullslast()` pushed every undated
        # row to the very end of every page, so 601 rows across 17 bodies
        # (EIB, EIT, CoR, Europol, ESMA, ENISA, ECHA, EUIPO, ACER, CdT, CPVO,
        # ECDC, CEPOL, EUAA, Eurojust, EU-OSHA, Ombudsman) were invisible in
        # practice. ECHA was among them, so the day the ELV Regulation produced
        # its first implementing workstream, that story could not appear in MEUB
        # News at all.
        #
        # They are undated because THE UPSTREAM FEEDS CARRY NO DATE. Verified by
        # parsing them: the Europol and ESMA entries contain only <title>,
        # <link> and <description> -- no pubDate, no published, no updated, no
        # dc:date. The parser is correct; there is nothing to parse.
        #
        # `created_at` is a fact we actually know (when the row was ingested),
        # so it is safe to ORDER by. It is deliberately NOT written into
        # `news_date`: inventing a publication date we were never given is the
        # thing feedback_backfill_no_hallucination forbids. The payload keeps
        # news_date null so the UI can say the date is unknown.
        rows = (q.order_by(func.coalesce(
                    EuNewsItem.news_date,
                    func.cast(EuNewsItem.created_at, Date),
                ).desc())
                .offset(offset).limit(limit).all())
        # Defensive: collapse rows sharing a canonical article URL (cross-listed).
        seen: set = set()
        uniq = []
        for e in rows:
            key = e.source_url or str(e.id)
            if key in seen:
                continue
            seen.add(key)
            uniq.append(e)
        items = [_item_dict(e, interests, dgs, keywords, tracked_pa) for e in uniq]

        # Featured: most recent items with an image, PI-matching first.
        featured = [i for i in items if i["image_url"]]
        featured = sorted(
            featured,
            key=lambda i: (i["matches_interests"], i["_order_date"] or _EPOCH),
            reverse=True,
        )[:5]

        dg_counts = dict(db.query(EuNewsItem.commission_dg, func.count(EuNewsItem.id))
                         .filter(EuNewsItem.commission_dg.isnot(None))
                         .group_by(EuNewsItem.commission_dg).all())
        type_counts = dict(db.query(EuNewsItem.item_type, func.count(EuNewsItem.id))
                           .group_by(EuNewsItem.item_type).all())
        inst_counts = dict(db.query(EuNewsItem.institution, func.count(EuNewsItem.id))
                           .filter(EuNewsItem.institution.isnot(None))
                           .group_by(EuNewsItem.institution).all())

        for _i in items:
            _i.pop("_order_date", None)
        for _i in featured:
            _i.pop("_order_date", None)

        return {
            "items": items,
            "featured": featured,
            "total": total,
            "pi_active": bool(my_interests and interests),
            "files_active": bool(my_files and tracked_pa),
            "has_tracked_files": bool(tracked_pa),
            "facets": {
                "institution": {k: int(v) for k, v in sorted(inst_counts.items(), key=lambda kv: -kv[1])},
                "commission_dg": {k: int(v) for k, v in sorted(dg_counts.items(), key=lambda kv: -kv[1])},
                "item_type": {k or "other": int(v) for k, v in type_counts.items()},
            },
        }
    except Exception as e:
        logger.exception(f"news list failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load news")


@router.get("/my-keywords", summary="My Policy-Interest keywords",
            description="Lowercase topic keywords from the user's Policy Interests, "
                        "used to flag news that matches their interests.")
async def my_keywords(current_user: Optional[User] = Depends(get_current_user_optional)):
    interests = _interest_list(current_user) if current_user else []
    return {"keywords": sorted(keywords_for_interests(interests)), "dgs": sorted(dgs_for_interests(interests))}


# --------------------------------------------------------------------------- #
# Stakeholders feed — the Brussels-lobbies moat, session-authed for MEUB.      #
# Same response contract as /items so the News tab renders it unchanged.       #
# Reads brussels_lobby_news_items + brussels_lobby_profiles (migration 117);   #
# the paid external door is /api/v2/proprietary/brussels-lobbies.              #
# --------------------------------------------------------------------------- #

_SIX_LANGS = {"en", "es", "ca", "fr", "it", "nl"}

# Friendly labels live in the frontend; the API returns the raw normalised type.
_ORG_TYPE_LABEL = {
    "ngo": "NGO", "trade_association": "Trade association", "company": "Company",
    "think_tank": "Think tank", "consultancy": "Consultancy", "law_firm": "Law firm",
    "trade_union": "Trade union", "academic": "Academic", "religious": "Religious",
    "public_authority": "Public authority", "third_country": "Third-country entity",
    "self_employed": "Self-employed", "other": "Other",
}


_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_text(s: Optional[str], limit: Optional[int] = None) -> Optional[str]:
    """Strip HTML tags + entities and collapse whitespace from feed text."""
    if not s:
        return None
    import html
    t = html.unescape(_TAG_RE.sub(" ", s))
    t = _WS_RE.sub(" ", t).strip()
    if not t:
        return None
    if limit and len(t) > limit:
        t = t[:limit].rsplit(" ", 1)[0] + "…"
    return t


def _stakeholder_dict(r, interests: set, keywords: List[str], trans: Optional[dict] = None) -> dict:
    """Map a lobby news item (+ its org profile) into the News-tab card shape.

    `trans` (when present) is a cached translation for the requested UI language —
    used for foreign items so the card reads in the user's language.
    """
    org_interests = set(r.get("interests") or [])
    detected = r.get("detected_lang")
    if trans and (trans.get("title") or trans.get("summary")):
        title = _clean_text(trans.get("title"), 180) or _clean_text(r.get("title"), 180)
        summary = _clean_text(trans.get("summary"), 300)
        translated_from = detected
    else:
        title = _clean_text(r.get("title"), 180)
        summary = _clean_text(r.get("summary"), 300)
        translated_from = None
    img = (r.get("image_url") or "").strip() or None
    overlap = {i for i in org_interests if i in interests}
    hay = f"{title or ''} {summary or ''}".lower()
    soft = None
    if overlap:
        soft = "In your interests: " + ", ".join(sorted(overlap))
    elif any(k in hay for k in keywords):
        soft = "Mentions a topic in your interests"
    # Date-only string (matches the institutional feed + the frontend date parser).
    # Fall back to the crawl date so an item always shows a date, never "Invalid date".
    dt = r.get("published_at") or r.get("fetched_at")
    news_date = dt.date().isoformat() if dt else None
    org_type = r.get("org_type")
    org_type_label = _ORG_TYPE_LABEL.get(org_type, org_type) or "Organisation"
    # Never let the numeric register code surface as a label: always resolve a name.
    org_name = r.get("original_name") or r.get("acronym") or org_type_label
    return {
        "id": str(r.get("id")),
        "title": title,
        "summary": summary,
        "news_date": news_date,
        # institution carries the org_type so the shared facet filter works as-is.
        "institution": org_type,
        "commission_dg": None,
        "dg_name": org_name,                         # card source label = org name (guaranteed)
        "item_type": None,                           # source_kind (rss/sitemap) is not a user tag
        "source_key": None,                          # do not display the register code
        "org_code": r.get("identification_code"),    # non-displayed key for future deep-link
        "policy_areas": sorted(org_interests),
        "image_url": img,
        "source_url": r.get("item_url"),
        "matches_interests": bool(soft),
        "interest_reason": soft,
        "matches_tracked": False,
        "tracked_reason": None,
        "org_type_label": org_type_label,
        "detected_lang": detected,
        "translated_from": translated_from,
    }


@router.get("/stakeholders", summary="Brussels stakeholders news feed",
            description=(
                "**What it does**\nReturns what the Brussels advocacy ecosystem is "
                "publishing on its own websites: every Brussels-based EU Transparency "
                "Register organisation (NGO, trade association, company, think tank, "
                "consultancy, law firm, ...), newest-first, in the same card shape as "
                "the institutional feed. This is the other half of 'News' — what the "
                "bubble is saying, not what the institutions are doing.\n\n"
                "**When to use it**\nThe MEUB 'News' tab, 'Brussels stakeholders' "
                "segment. The paid external API door is "
                "`/api/v2/proprietary/brussels-lobbies`.\n\n"
                "**Input**\n`my_interests=true` keeps only orgs whose declared policy "
                "interests overlap yours; `institution` filters by normalised org type; "
                "`search`; `include_global_corp=true` re-includes multinationals' global "
                "newsrooms (excluded by default); `limit`/`offset`.\n\n"
                "**You get back**\nThe same News-card shape (title, summary, date, "
                "source = org name, link), each flagged against your interests, plus an "
                "org-type facet."))
async def list_stakeholder_news(
    my_interests: bool = Query(False),
    institution: Optional[str] = Query(None, description="Normalised org type (ngo, trade_association, ...)."),
    search: Optional[str] = Query(None),
    include_global_corp: bool = Query(False),
    lang: str = Query("en", description="UI language; foreign items are served translated into it."),
    limit: int = Query(60, ge=1, le=200),
    offset: int = Query(0, ge=0),
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: Session = Depends(get_db),
):
    lang = (lang or "en").lower()[:5]
    try:
        interests = set(_interest_list(current_user)) if current_user else set()
        keywords = sorted(keywords_for_interests(interests))

        # Quality guard: drop path-fragment / too-short titles that slip through the crawl.
        where = ["n.title IS NOT NULL", "n.title NOT LIKE '/%'", "length(n.title) >= 12"]
        params: dict = {}
        if not include_global_corp:
            where.append("p.is_global_corp = false")
        if institution:
            where.append("p.org_type = :org_type"); params["org_type"] = institution
        if search:
            where.append("(n.title ILIKE :s OR n.summary ILIKE :s)"); params["s"] = f"%{search}%"
        # Soft Policy-Interest filter: org interests overlap OR keyword in title/summary.
        if my_interests and (interests or keywords):
            clauses = []
            if interests:
                clauses.append("EXISTS (SELECT 1 FROM unnest(p.interests) oi "
                               "WHERE oi = ANY(:pi_list))")
                params["pi_list"] = sorted(interests)
            if keywords:
                clauses.append("(n.title ILIKE ANY(:kw) OR n.summary ILIKE ANY(:kw))")
                params["kw"] = [f"%{k}%" for k in keywords]
            if clauses:
                where.append("(" + " OR ".join(clauses) + ")")
        where_sql = "WHERE " + " AND ".join(where)

        total = int(db.execute(text(
            f"""SELECT COUNT(*) FROM brussels_lobby_news_items n
                JOIN brussels_lobby_profiles p ON p.identification_code = n.identification_code
                {where_sql}"""), params).scalar() or 0)

        rows = db.execute(text(f"""
            SELECT n.id, n.title, n.summary, n.item_url, n.published_at, n.fetched_at,
                   n.source_kind, n.detected_lang, n.image_url,
                   p.identification_code, p.original_name, p.acronym,
                   p.org_type, p.interests
              FROM brussels_lobby_news_items n
              JOIN brussels_lobby_profiles p ON p.identification_code = n.identification_code
              {where_sql}
             ORDER BY n.published_at DESC NULLS LAST, n.id DESC
             LIMIT :limit OFFSET :offset
        """), {**params, "limit": limit, "offset": offset}).mappings().all()

        # Collapse rows sharing a canonical item URL (cross-listed / re-crawled).
        seen: set = set()
        deduped = []
        for r in rows:
            key = r.get("item_url") or str(r.get("id"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(r)

        # Foreign items (detected lang not in our 6) get served in the UI language.
        trans_map: dict = {}
        if lang in _SIX_LANGS:
            foreign_ids = [r["id"] for r in deduped
                           if r.get("detected_lang") and r["detected_lang"] not in _SIX_LANGS]
            if foreign_ids:
                trows = db.execute(text("""
                    SELECT news_item_id, title, summary
                      FROM brussels_lobby_news_translations
                     WHERE lang = :lang AND news_item_id = ANY(:ids)
                """), {"lang": lang, "ids": foreign_ids}).mappings().all()
                trans_map = {tr["news_item_id"]: dict(tr) for tr in trows}

        items = [_stakeholder_dict(r, interests, keywords, trans_map.get(r["id"]))
                 for r in deduped]

        # Org-type facet (over the whole register, not just this page) for the filter.
        type_rows = db.execute(text("""
            SELECT p.org_type, COUNT(*) AS n
              FROM brussels_lobby_news_items ni
              JOIN brussels_lobby_profiles p ON p.identification_code = ni.identification_code
             WHERE p.is_global_corp = false AND ni.title IS NOT NULL
                   AND ni.title NOT LIKE '/%' AND length(ni.title) >= 12
             GROUP BY p.org_type ORDER BY n DESC
        """)).mappings().all()

        return {
            "items": items,
            "featured": [],  # lobby items are text-first; no hero, the News tab handles it
            "total": total,
            "pi_active": bool(my_interests and (interests or keywords)),
            "files_active": False,
            "has_tracked_files": False,
            "facets": {
                "institution": {r["org_type"]: int(r["n"]) for r in type_rows if r["org_type"]},
                "commission_dg": {},
                "item_type": {},
            },
            "org_type_labels": _ORG_TYPE_LABEL,
        }
    except Exception as e:
        logger.exception(f"stakeholder news list failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to load stakeholder news")
