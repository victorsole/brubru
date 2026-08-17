"""
/api/v2/news — every EU body's news in one folder.

A cross-body AGGREGATOR (ingests nothing): a query-time view over the news Brubru
already keeps fresh in economy_items, where "News" bundles item_type 'news' and
'press_release' (latest news, press releases, stories, speeches and statements are
all folded into 'news' at ingest). Same proprietary body/family picker as the
events folder. The 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
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

router = APIRouter(prefix="/news", tags=["v2-news"])

_NEWS_TYPES = ["news", "press_release"]
_KINDS = {"news", "press_release", "all"}
_ORDERS = {"recent": "document_date DESC NULLS LAST, id DESC",
           "oldest": "document_date ASC NULLS LAST, id ASC",
           "title": "title ASC"}


class NewsItem(BaseModel):
    id: int = Field(..., description="Stable Brubru item id (use on the detail endpoint).")
    body_code: str = Field(..., description="Canonical body code the item belongs to.")
    body_name: Optional[str] = Field(None, description="Human-readable body name.")
    families: List[str] = Field(default_factory=list, description="Brubru policy families this body belongs to.")
    kind: str = Field(..., description="news | press_release.")
    title: str
    summary: Optional[str] = None
    public_url: Optional[str] = Field(None, description="Canonical URL on the source website.")
    body_txt: Optional[str] = Field(None, description="Plain-text body (full on detail; null on list).")
    body_html: Optional[str] = Field(None, description="HTML body (full on detail; null on list).")
    document_date: Optional[datetime] = Field(None, description="The item's own published date.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested the item.")


class NewsBody(BaseModel):
    code: str
    name: Optional[str] = None
    families: List[str] = Field(default_factory=list)
    item_count: int = 0


class NewsFamily(BaseModel):
    slug: str
    label: str
    bodies: List[str]
    item_count: int = 0


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


def _build_where(codes, kinds, since, until, q):
    where = ["item_type = ANY(:types)"]
    params = {"types": kinds}
    if codes is not None:
        where.append("body_code = ANY(:codes)"); params["codes"] = list(codes)
    if since:
        where.append("document_date >= :since"); params["since"] = since
    if until:
        where.append("document_date <= :until"); params["until"] = until
    if q:
        where.append("search_vector @@ plainto_tsquery('english', :q)"); params["q"] = q
    return " AND ".join(where), params


def _to_item(r, names, *, with_body):
    return NewsItem(
        id=r.id, body_code=r.body_code, body_name=names.get(r.body_code),
        families=families_for_body(r.body_code), kind=r.item_type, title=r.title, summary=r.summary,
        public_url=r.public_url, document_date=r.document_date, creation_date=r.creation_date,
        body_txt=(getattr(r, "body_txt", None) if with_body else None),
        body_html=(getattr(r, "body_html", None) if with_body else None),
    )


class NewsDirectory(BaseModel):
    total_items: int
    news: int
    press_releases: int
    bodies_with_news: int
    families: int
    earliest: Optional[datetime] = None
    latest: Optional[datetime] = None


@router.get("", response_model=NewsDirectory, tags=["v2-news"],
            summary="News folder directory — every EU body's news, aggregated",
            description=(
                "**What it does**\nOne-call overview of the cross-body news feed: totals by kind, bodies "
                "and policy families covered, and the date span.\n\n**When to use it**\nBefore querying, "
                "to see the shape of what is there.\n\n**Input**\nNo parameters.\n\n**Try it**\n```\n"
                "GET /api/v2/news\n```\n\n**You get back**\nA summary object. Then call `/api/v2/news/all`, "
                "`/api/v2/news/bodies`, or `/api/v2/news/{id}`.\n\n**Data freshness**\nLive from economy_items."))
async def directory(request: Request, db: Session = Depends(get_db),
                    user: User = Depends(api_user_with_rate_limit)):
    row = db.execute(text(
        "SELECT count(*) total, count(*) FILTER (WHERE item_type='news') n, "
        "count(*) FILTER (WHERE item_type='press_release') pr, "
        "count(distinct body_code) bodies, min(document_date) lo, max(document_date) hi "
        "FROM economy_items WHERE item_type = ANY(:t)"), {"t": _NEWS_TYPES}).fetchone()
    return NewsDirectory(total_items=row.total, news=row.n, press_releases=row.pr,
                         bodies_with_news=row.bodies, families=len(FAMILIES),
                         earliest=row.lo, latest=row.hi)


@router.get("/all", response_model=PaginatedResponse[NewsItem], tags=["v2-news"],
            summary="All news, all bodies (pick your scope)",
            description=(
                "**What it does**\nThe unified news feed across every EU body, newest first. 'News' "
                "bundles latest news, press releases, stories, speeches and statements.\n\n**When to use "
                "it**\nOne call for 'all news from the bodies I care about'. Scope with `body` "
                "(comma-separated codes) and/or `family` (a Brubru policy family); omit both for every "
                "body.\n\n**Input**\n`body`, `family`, `kind` (news | press_release | all), `from` / `to` "
                "(YYYY-MM-DD), `days` (shorthand for the last N days; ignored when `from` is given), "
                "`q` (free text), `order` (recent | oldest | title), `page`, `limit` (max "
                "100).\n\n**Try it**\n```\nGET /api/v2/news/all?days=3\n"
                "GET /api/v2/news/all?family=finance-economy&order=recent\n"
                "GET /api/v2/news/all?body=commission,ecb&q=inflation\n```\n\n**You get back**\nA paginated "
                "envelope. Each item carries the 5 datapoints (`body_txt` / `body_html` null on the list), "
                "plus body_code, body_name, the policy families and kind. `published_from` / `published_to` "
                "echo the date window actually applied, so you can confirm your filter took "
                "effect.\n\n**Data freshness**\nLive from economy_items."))
async def list_news(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    body: Optional[str] = Query(None, description="Comma-separated body codes (e.g. commission,ecb,cedefop)."),
    family: Optional[str] = Query(None, description="Comma-separated Brubru policy family slugs (see /api/v2/news/bodies)."),
    kind: str = Query("all", description="news | press_release | all."),
    from_: Optional[date] = Query(None, alias="from", description="Only items on/after this date (YYYY-MM-DD)."),
    to: Optional[date] = Query(None, description="Only items on/before this date (YYYY-MM-DD)."),
    days: Optional[int] = Query(None, ge=1, le=3650, description="Shorthand for a recent window: only items from the last N days. Ignored if `from` is given."),
    q: Optional[str] = Query(None, description="Free-text search over title, summary and body."),
    order: str = Query("recent", description="recent | oldest | title."),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    if kind not in _KINDS:
        raise HTTPException(400, f"kind must be one of {sorted(_KINDS)}")
    if order not in _ORDERS:
        raise HTTPException(400, f"order must be one of {sorted(_ORDERS)}")
    # `days` is the window callers reach for first, and it silently did nothing
    # until 28 July 2026: it was never declared, so FastAPI dropped it and the
    # caller got the whole 11,900-item corpus back believing it was filtered.
    # An explicit `from` always wins, so existing callers are unaffected.
    if from_ is None and days is not None:
        from_ = date.today() - timedelta(days=days)
    kinds = _NEWS_TYPES if kind == "all" else [kind]
    codes = _resolve_scope(body, family)
    clause, params = _build_where(codes, kinds, from_, to, q)
    total = db.execute(text(f"SELECT count(*) FROM economy_items WHERE {clause}"), params).scalar() or 0
    params2 = {**params, "limit": limit, "offset": (page - 1) * limit}
    rows = db.execute(text(
        "SELECT id, body_code, item_type, title, summary, public_url, document_date, creation_date "
        f"FROM economy_items WHERE {clause} ORDER BY {_ORDERS[order]} LIMIT :limit OFFSET :offset"),
        params2).fetchall()
    names = _body_names(db)
    # Report the window that was actually applied. These envelope fields existed
    # but were never populated here, so every response claimed a null date range
    # regardless of the filter in force.
    return build_envelope(
        [_to_item(r, names, with_body=False) for r in rows], total, page, limit,
        published_from=from_, published_to=to,
    )


@router.get("/latest", response_model=dict, tags=["v2-news"],
            summary="How fresh is the news data?",
            description=(
                "**What it does**\nReports the newest ingested news date, overall and per body, so you "
                "can tell whether the feed is current before you trust an empty result.\n\n"
                "**When to use it**\nWhen a date-filtered query on `/api/v2/news/all` comes back empty. "
                "An empty window plus a stale `latest_date` here means the ingestion is behind, not that "
                "nothing happened.\n\n**Input**\n`stale_after_days` (optional, default 3) - how many days "
                "old the newest item may be before this endpoint reports `stale: true`.\n\n**Try it**\n"
                "```\nGET /api/v2/news/latest\n```\n\n**You get back**\n`latest_date`, `age_days`, "
                "`stale`, `total_items`, and `by_body` (the ten most recently updated bodies with their "
                "newest date).\n\n**Data freshness**\nLive."))
async def latest_news(request: Request,
                      stale_after_days: int = Query(
                          3, ge=1, le=60,
                          description="Age in days beyond which the feed is reported as stale."),
                      db: Session = Depends(get_db),
                      user: User = Depends(api_user_with_rate_limit)):
    """Freshness probe for the cross-body news feed.

    Declared BEFORE `/{item_id}` on purpose: FastAPI matches routes in
    declaration order, so a literal path registered after the int-typed
    parameter route would be swallowed by it. Until 5 Aug 2026 this endpoint
    did not exist at all, and `GET /api/v2/news/latest` fell through to
    `/{item_id}`, returning a Pydantic int-parsing error. The /news skill
    documents this path as its staleness guard, so the guard was unusable.
    """
    def _as_date(v):
        """economy_items.document_date is timestamptz, so max() hands back a
        datetime. Subtracting that from date.today() raises TypeError, which is
        how the first cut of this endpoint 500'd in production on 5 Aug 2026."""
        return v.date() if isinstance(v, datetime) else v

    # The freshness anchor must IGNORE future-dated rows. Many bodies publish
    # calls for expression of interest, dynamic purchasing systems and research
    # projects whose scraped "date" is a DEADLINE or project end, not a
    # publication date -- on 17 Aug 2026 there were 1,486 such rows across 44
    # bodies, the furthest dated 2031. Taking a bare max() let one of them set
    # latest_date to a future day, making age_days negative and `stale` False
    # for ever. The guard reported a clean bill of health while ingestion had
    # been dead for four days. A monitoring check that cannot fail is worse
    # than no check, so the anchor is now the newest row that is not in the
    # future, and the bad rows are reported instead of silently swallowed.
    row = db.execute(text(
        "SELECT max(document_date) FILTER (WHERE document_date <= now()) AS latest, "
        "       count(*) AS n, "
        "       count(*) FILTER (WHERE document_date > now()) AS future_dated "
        "FROM economy_items WHERE item_type = ANY(:t)"), {"t": _NEWS_TYPES}).fetchone()
    latest = _as_date(row.latest) if row and row.latest else None
    age = (date.today() - latest).days if latest else None
    per_body = db.execute(text(
        "SELECT body_code, max(document_date) AS latest, count(*) AS n FROM economy_items "
        "WHERE item_type = ANY(:t) AND document_date IS NOT NULL AND document_date <= now() "
        "GROUP BY body_code ORDER BY max(document_date) DESC LIMIT 10"),
        {"t": _NEWS_TYPES}).fetchall()
    names = _body_names(db)
    return {
        "latest_date": latest.isoformat() if latest else None,
        "age_days": age,
        "stale": (age is None or age > stale_after_days),
        "stale_after_days": stale_after_days,
        "total_items": row.n if row else 0,
        # Non-zero means dates are being scraped from the wrong field somewhere.
        "future_dated_items": (row.future_dated if row else 0),
        "by_body": [
            {"code": r.body_code, "name": names.get(r.body_code),
             "latest_date": _as_date(r.latest).isoformat() if r.latest else None,
             "item_count": r.n}
            for r in per_body
        ],
    }


@router.get("/bodies", response_model=dict, tags=["v2-news"],
            summary="Pick-list: bodies and policy families with news counts",
            description=(
                "**What it does**\nThe discovery endpoint for the `body` and `family` filters: every body "
                "with news (count + families) and every Brubru policy family (bodies + total count).\n\n"
                "**When to use it**\nTo build a picker, or to see what `family=` expands to.\n\n**Input**\n"
                "No parameters.\n\n**Try it**\n```\nGET /api/v2/news/bodies\n```\n\n**You get back**\n"
                "`{bodies: [...], families: [...]}`.\n\n**Data freshness**\nLive."))
async def bodies_facet(request: Request, db: Session = Depends(get_db),
                       user: User = Depends(api_user_with_rate_limit)):
    rows = db.execute(text(
        "SELECT body_code, count(*) n FROM economy_items WHERE item_type = ANY(:t) GROUP BY body_code"),
        {"t": _NEWS_TYPES}).fetchall()
    by_body = {r.body_code: r.n for r in rows}
    names = _body_names(db)
    bodies = [NewsBody(code=c, name=names.get(c), families=families_for_body(c), item_count=n)
              for c, n in sorted(by_body.items(), key=lambda kv: -kv[1])]
    fams = []
    for slug, f in FAMILIES.items():
        member = set(f["bodies"])
        fams.append(NewsFamily(slug=slug, label=f["label"], bodies=f["bodies"],
                               item_count=sum(n for c, n in by_body.items() if c in member)))
    fams.sort(key=lambda x: -x.item_count)
    return {"bodies": [b.model_dump() for b in bodies], "families": [f.model_dump() for f in fams]}


@router.get("/{item_id}", response_model=NewsItem, tags=["v2-news"],
            summary="One news item (full body)",
            description=(
                "**What it does**\nReturns one news item in full, including `body_txt` / `body_html`.\n\n"
                "**When to use it**\nAfter finding an id on `/api/v2/news/all`.\n\n**Input**\n`item_id` — "
                "the Brubru item id from the list endpoint.\n\n**Try it**\n```\nGET /api/v2/news/12345\n```\n\n"
                "**You get back**\nA single item with the full 5-datapoint contract.\n\n**Data freshness**\n"
                "Live."))
async def get_news(request: Request,
                   item_id: int = PathParam(..., description="Brubru item id from the list endpoint."),
                   db: Session = Depends(get_db),
                   user: User = Depends(api_user_with_rate_limit)):
    r = db.execute(text(
        "SELECT id, body_code, item_type, title, summary, public_url, body_txt, body_html, "
        "document_date, creation_date FROM economy_items "
        "WHERE id = :id AND item_type = ANY(:t)"), {"id": item_id, "t": _NEWS_TYPES}).fetchone()
    if r is None:
        raise HTTPException(404, f"No news item with id {item_id}")
    return _to_item(r, _body_names(db), with_body=True)
