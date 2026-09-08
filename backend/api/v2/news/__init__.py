"""
/api/v2/news — every EU body's news in one folder.

A cross-body AGGREGATOR (ingests nothing): a query-time view over the news Brubru
already keeps fresh in economy_items (agencies) and eu_news_items (Commission,
Parliament, Council -- see _INSTITUTIONAL_NEWS), where "News" bundles item_type 'news' and
'press_release' (latest news, press releases, stories, speeches and statements are
all folded into 'news' at ingest). Same proprietary body/family picker as the
events folder. The 5 mandatory datapoints. Scope: read:economy.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List, Optional, Union

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
# Every order carries an `id` tiebreak. Without one, two rows with equal sort
# keys can come back in a different relative order on each call, and LIMIT/OFFSET
# pagination then repeats or skips rows across pages. `title` had no tiebreak; it
# happened to be stable on today's data, which is luck rather than a guarantee,
# and the UNION makes ties more likely because two independent tables interleave.
# `_build_where` filters on coalesce(document_date, creation_date) so an item whose
# upstream feed published no date is still admitted by a dated window. The ORDER BY
# must use the SAME expression, or those rows are admitted and then sorted behind
# every dated row. Measured 8 September 2026: 1,761 of 12,509 news rows (14.1%,
# across 17 bodies) carry no document_date, so a mixed window pushed all of them
# to the last page while reporting them in `total`.
_DATE_SORT = "coalesce(document_date, creation_date)"
_ORDERS = {"recent": f"{_DATE_SORT} DESC NULLS LAST, id DESC",
           "oldest": f"{_DATE_SORT} ASC NULLS LAST, id ASC",
           "title": "title ASC, id ASC"}


class NewsItem(BaseModel):
    id: Union[int, str] = Field(..., description=(
        "Stable Brubru item id (use on the detail endpoint). An INTEGER for agency "
        "items and a UUID STRING for Commission / Parliament / Council items, which "
        "live in a different store. Pass whichever you got through unchanged."))
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
    # 37,573 of 564,719 economy_items rows (6.7%) carry NO document_date,
    # because the upstream feed published none. A bare `document_date >= :since`
    # is NULL for those rows, so every dated window silently dropped 6.7% of the
    # corpus -- including whole bodies whose feeds never carry a date at all.
    # `creation_date` (when Brubru ingested the row) is a fact we actually know,
    # so it is safe to FILTER on. It is deliberately not written into
    # document_date: inventing a publication date we were never given is what
    # feedback_backfill_no_hallucination forbids. The payload still returns
    # document_date as NULL, so the caller can see the date is unknown.
    if since:
        where.append("coalesce(document_date, creation_date) >= :since"); params["since"] = since
    if until:
        where.append("coalesce(document_date, creation_date) <= :until"); params["until"] = until
    if q:
        where.append("search_vector @@ plainto_tsquery('english', :q)"); params["q"] = q
    return " AND ".join(where), params


# ---------------------------------------------------------------------------
# The three institutions that generate most EU news live in a DIFFERENT table
# ---------------------------------------------------------------------------
# `economy_items` has never held a single news row for the Commission, the
# Parliament or the Council -- 12,021 news rows across 72 bodies, and zero for
# those three, ever. The 72 that do produce news are the agencies, so an endpoint
# named `/news/all` was in truth an AGENCY-news aggregator, and MEUB News
# consumed a feed missing the three institutions that generate most EU news.
# Measured on 25 Aug 2026: a direct scrape found 62 Commission items in 24 hours
# while `/api/v2/news/all?days=1` held 4.
#
# The news itself was never missing -- it is in `eu_news_items` (Commission 1,730
# rows, newest today; EP 381; Council 81), written by a different pipeline.
#
# So this unions the two stores at read time rather than copying 2,000+ rows into
# economy_items. Duplicating them would create a second source of truth for the
# same fact, and `dpp_watch.py` already reports the same item appearing three
# times across these two stores.
#
# INVARIANT: only bodies with ZERO news rows in economy_items may appear here, or
# the union double-counts. `tests/test_v2_news_institutional_union.py` asserts it,
# so if a Commission ingestor is ever added to sync_economy.py the test fails and
# tells you to remove the entry rather than silently serving every item twice.
#
# WHICH bodies belong here, decided 8 September 2026 by reading the rows rather than
# the counts. Four bodies satisfied the invariant above and were candidates; only one
# belongs, and the reasons the other three do not are the point:
#
#   fra      ADDED. 64 rows of genuine Fundamental Rights Agency news, all dated, zero
#            news rows in economy_items. (Its scraper is separately broken: newest item
#            31 Dec 2025 while last ingested 26 Aug 2026, i.e. it runs and fetches
#            nothing. That is a scraper defect, not a reason to hide the rows.)
#
#   OUTLET   EXCLUDED, and must stay excluded. 3,158 rows, the largest and freshest
#            news store Brubru holds, and every one is THIRD-PARTY JOURNALISM:
#            Politico Europe 1,691 (including subscriber.politicopro.com, a paid
#            product), Euractiv 830, EU Observer 637. /api/v2/news/all is a METERED
#            endpoint sold to third parties, so unioning these in would redistribute
#            paywalled commercial content to paying customers. A licensing problem, not
#            a coverage gap. Fine for internal review; not fine on the public API.
#
#   FUNDING  EXCLUDED. 773 rows, official EU content from the Funding & Tenders Portal,
#            but they are funding opportunities and they already have their own folder
#            at /api/v2/funding/*. Adding them here would create a second source of
#            truth for the same fact, which is what the union was built to avoid.
#
#   EU       EXCLUDED as a body, because it is not one. 33 rows whose `institution` is
#            the generic literal 'EU' with source_key EC / REGIO / ENV, i.e. Commission
#            news mislabelled at ingest. The fix is to normalise the label to
#            COMMISSION in the ingest, not to publish a body called "EU". Filed.
#
# CODE NORMALISATION, before anyone extends this dict: the two stores punctuate body
# codes differently. eu_news_items writes EULISA and EU-OSHA where economy_items writes
# eu_lisa and eu_osha, so a naive upper() comparison reports "zero economy news rows"
# for a body that has 55. That produced two false positives when this list was first
# measured. Compare on the code with '-' and '_' stripped before trusting the invariant.
_INSTITUTIONAL_NEWS = {
    "commission": "COMMISSION",
    "parliament": "EP",
    "council": "COUNCIL",
    "fra": "FRA",
}

# eu_news_items uses its own item_type vocabulary; map it onto the v2 contract
# (`news` | `press_release`). 'publication' is deliberately excluded: it is a
# document, not news, and belongs to the publications endpoints.
_EU_NEWS_KIND_SQL = (
    "CASE WHEN n.item_type = 'press' THEN 'press_release' ELSE 'news' END"
)
_EU_NEWS_SOURCE_TYPES = ["news", "press", "story"]

# Both halves must expose the SAME column types for UNION ALL, and the two id
# spaces are different types: economy_items.id is an integer, eu_news_items.id is
# a UUID. They are therefore unioned as TEXT and converted back on the way out by
# `_coerce_id`, so an agency item still serialises as the integer callers already
# depend on. (A first cut negated the id to disambiguate, which cannot work on a
# UUID -- `operator does not exist: - uuid`.)
_ECONOMY_COLS = ("id::text AS id, body_code, item_type, title, summary, public_url, "
                 "document_date, creation_date, fetched_at, body_txt, body_html")


def _coerce_id(raw):
    """Digits -> int (agency item); anything else -> str (institutional UUID)."""
    txt = str(raw)
    return int(txt) if txt.isdigit() else txt


def _institutional_sql(codes, kinds, since, until, q):
    """Projection of eu_news_items onto the economy_items news shape.

    Returns (sql, params), or (None, {}) when the requested scope excludes all
    three institutions -- in which case the caller skips the union entirely.
    """
    wanted = {c: inst for c, inst in _INSTITUTIONAL_NEWS.items()
              if codes is None or c in codes}
    if not wanted:
        return None, {}

    # Built from the mapping, so the dict above stays the single source of truth.
    case_body = "CASE n.institution " + " ".join(
        f"WHEN '{inst}' THEN '{code}'" for code, inst in wanted.items()
    ) + " END"

    where = ["n.institution = ANY(:i_insts)", "n.item_type = ANY(:i_srctypes)",
             f"({_EU_NEWS_KIND_SQL}) = ANY(:i_kinds)"]
    params = {"i_insts": list(wanted.values()),
              "i_srctypes": _EU_NEWS_SOURCE_TYPES,
              "i_kinds": list(kinds)}

    # 883 rows across 17 bodies carry news_date IS NULL for every row they have.
    # COALESCE to created_at keeps them visible and orderable -- the same fix
    # api/eu_news.py made on 19 Aug 2026 -- instead of dropping them silently.
    date_expr = "COALESCE(n.news_date::timestamptz, n.created_at)"
    if since:
        where.append(f"{date_expr} >= :i_since"); params["i_since"] = since
    if until:
        where.append(f"{date_expr} <= :i_until"); params["i_until"] = until
    if q:
        # eu_news_items has no tsvector column, so this is ILIKE rather than
        # the FTS the economy half uses. Deliberately not silent about it: see
        # the `search_mode` note in the endpoint description.
        where.append("(n.title ILIKE :i_q OR coalesce(n.summary,'') ILIKE :i_q)")
        params["i_q"] = f"%{q}%"

    sql = (
        f"SELECT n.id::text AS id, {case_body} AS body_code, "
        f"{_EU_NEWS_KIND_SQL} AS item_type, n.title, n.summary, "
        f"n.source_url AS public_url, {date_expr} AS document_date, "
        "n.created_at AS creation_date, "
        # eu_news_items has NO last-fetch column. `scraped_at` exists but the
        # upsert in scripts/sync_dg_news.py only sets it on INSERT and returns
        # "skipped" without touching an unchanged row, so it is first-seen again --
        # the very column confusion this endpoint was corrected for. NULL is the
        # honest answer: we do not know when these bodies were last fetched, and
        # `_classify` must treat unknown as unknown, never as "not fetched".
        "NULL::timestamptz AS fetched_at, "
        # Migration 228 gave eu_news_items real body columns, composed by
        # scripts/backfill_eu_news_bodies.py from the title, summary, institution,
        # date and source link. Before that this served `summary AS body_txt` and a
        # hardcoded NULL body_html, so two of the five mandatory datapoints were
        # absent from this whole half of the corpus: body_html NULL on 100% of
        # 10,143 rows, body_txt empty on 29%.
        #
        # coalesce back to `summary` because a row written by the ingest pipeline
        # since the last backfill run has body_source IS NULL, and serving the
        # summary beats serving nothing. TODO: compose on write in the eu_news
        # ingest so the fallback stops being reachable.
        "coalesce(n.body_txt, n.summary) AS body_txt, n.body_html "
        f"FROM eu_news_items n WHERE {' AND '.join(where)}"
    )
    return sql, params


def _news_source_sql(codes, kinds, since, until, q):
    """The full news corpus: agencies (economy_items) + institutions (eu_news_items)."""
    clause, params = _build_where(codes, kinds, since, until, q)
    econ = f"SELECT {_ECONOMY_COLS} FROM economy_items WHERE {clause}"
    inst_sql, inst_params = _institutional_sql(codes, kinds, since, until, q)
    if inst_sql is None:
        return f"({econ})", params
    return f"({econ} UNION ALL {inst_sql})", {**params, **inst_params}


def _to_item(r, names, *, with_body):
    return NewsItem(
        id=_coerce_id(r.id), body_code=r.body_code, body_name=names.get(r.body_code),
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
                "`/api/v2/news/bodies`, or `/api/v2/news/{id}`.\n\n**Data freshness**\nLive, across both news stores."))
async def directory(request: Request, db: Session = Depends(get_db),
                    user: User = Depends(api_user_with_rate_limit)):
    src, src_params = _news_source_sql(None, _NEWS_TYPES, None, None, None)
    row = db.execute(text(
        "SELECT count(*) total, count(*) FILTER (WHERE item_type='news') n, "
        "count(*) FILTER (WHERE item_type='press_release') pr, "
        "count(distinct body_code) bodies, min(document_date) lo, max(document_date) hi "
        f"FROM {src} u"), src_params).fetchone()
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
                "envelope. Each item carries the 5 datapoints. **`body_txt` / `body_html` are null on the list by default — pass `include_body=true` to get them in bulk**, or call `/api/v2/news/{id}` for one item. Agency items carry the full scraped article; Commission / Parliament / Council items carry the summary the institutional feed publishes, which is the fullest text held for them. "
                "plus body_code, body_name, the policy families and kind. `published_from` / `published_to` "
                "echo the date window actually applied, so you can confirm your filter took "
                "effect.\n\n**Data freshness**\nLive. Agency news comes from Brubru's economy store; Commission, Parliament and Council news is unioned in from the institutional news store, so this feed covers both. Agency items keep their INTEGER `id`; institutional items carry a UUID STRING `id`. Either way, pass the id you were given through to `/api/v2/news/{id}` unchanged. Note `q` is full-text over the agency half and a substring match over the institutional half."))
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
    # See the note in api/v2/economy_endpoints.py: v2 is split between `since`/`until`
    # (332 operations) and `from`/`to` (the cross-body aggregators). An unknown query
    # param is dropped SILENTLY with HTTP 200, so accept both spellings here too.
    since: Optional[date] = Query(None, alias="since", include_in_schema=False),
    until: Optional[date] = Query(None, alias="until", include_in_schema=False),
    q: Optional[str] = Query(None, description="Free-text search over title, summary and body."),
    order: str = Query("recent", description="recent | oldest | title."),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    include_body: bool = Query(
        False,
        description=(
            "Return `body_txt` / `body_html` on every item in the list. Off by "
            "default because a page of full articles is large; there is no other "
            "way to get the body in bulk, so set it to true rather than calling "
            "the detail endpoint once per item."
        ),
    ),
):
    if kind not in _KINDS:
        raise HTTPException(400, f"kind must be one of {sorted(_KINDS)}")
    if order not in _ORDERS:
        raise HTTPException(400, f"order must be one of {sorted(_ORDERS)}")
    # `days` is the window callers reach for first, and it silently did nothing
    # until 28 July 2026: it was never declared, so FastAPI dropped it and the
    # caller got the whole 11,900-item corpus back believing it was filtered.
    # An explicit `from` always wins, so existing callers are unaffected.
    # Accept the house `since`/`until` spelling as an alias. An explicit `from`/`to`
    # still wins, so no existing caller changes behaviour. This is the THIRD instance
    # of the silent-drop bug on this one endpoint: `days` had it until 28 July 2026,
    # `since`/`until` had it until 8 September 2026. See fix #2 in the same session
    # (reject unknown query params) for the systemic answer.
    if from_ is None and since is not None:
        from_ = since
    if to is None and until is not None:
        to = until
    if from_ is None and days is not None:
        from_ = date.today() - timedelta(days=days)
    kinds = _NEWS_TYPES if kind == "all" else [kind]
    codes = _resolve_scope(body, family)
    # Agencies (economy_items) UNION institutions (eu_news_items) -- see
    # _INSTITUTIONAL_NEWS. Before 25 Aug 2026 this read economy_items alone and
    # could not return a single Commission, Parliament or Council item.
    src, params = _news_source_sql(codes, kinds, from_, to, q)
    total = db.execute(text(f"SELECT count(*) FROM {src} u"), params).scalar() or 0
    params2 = {**params, "limit": limit, "offset": (page - 1) * limit}
    rows = db.execute(text(
        f"SELECT * FROM {src} u ORDER BY {_ORDERS[order]} LIMIT :limit OFFSET :offset"),
        params2).fetchall()
    names = _body_names(db)
    # Report the window that was actually applied. These envelope fields existed
    # but were never populated here, so every response claimed a null date range
    # regardless of the filter in force.
    return build_envelope(
        [_to_item(r, names, with_body=include_body) for r in rows], total, page, limit,
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
                "`stale`, `total_items`, `future_dated_items`, the estate counts `bodies_total` / "
                "`bodies_fresh` / `bodies_stale` / `bodies_undated`, `by_body_truncated` (always "
                "false), and `by_body`: EVERY body, stalest first, never truncated. Each body "
                "carries `latest_date` + `age_days` (its newest published item), `last_fetched` "
                "+ `fetch_age_days` (when the cron last touched the body, from `fetched_at`), "
                "`first_seen` (when its newest item was first captured), `undated_items`, a "
                "three-state `state` (fresh | stale | undated) and `likely_cause`.\n\n"
                "The two dates are the point, and `likely_cause` says WHOSE problem it is: "
                "`not_fetched` means the cron is not reaching the body (ours to fix); "
                "`undated_items` means it fetches fine but the items carry no date (ours to fix); "
                "`publisher_quiet` means it fetches fine, the dates are fine, and the SOURCE has "
                "simply published nothing newer (not a defect); `fetch_time_unknown` means the store "
                "behind that body records no last-fetch time, so no verdict is possible. A quiet "
                "agency must not be reported as a broken scraper: read `fetch_age_days` before "
                "debugging anything.\n\n`stale_after_days` (default 3) governs the CORPUS "
                "verdict; `body_stale_after_days` (default 30) governs the per-body one. They are "
                "deliberately different: 3 days answers 'is the feed current', 30 answers 'is this "
                "body broken', and many EU agencies publish monthly.\n\n**Data freshness**\nLive."))
async def latest_news(request: Request,
                      stale_after_days: int = Query(
                          3, ge=1, le=60,
                          description="Age in days beyond which the CORPUS is reported as stale."),
                      body_stale_after_days: int = Query(
                          30, ge=1, le=365,
                          description=(
                              "Age in days beyond which an INDIVIDUAL body is reported as stale. "
                              "Separate from stale_after_days, and much longer, because the two ask "
                              "different questions: 3 days is right for 'is the whole feed current' "
                              "and wrong for 'is this agency broken', since plenty of EU agencies "
                              "publish monthly. Measured in production on 8 September 2026: at 3 days 57 "
                              "of 78 bodies read as stale, at 30 days 18 do, and 18 is the real "
                              "number. A check that cries wolf on 73% of the estate gets ignored. "
                              "Those counts move daily, so treat them as the reason for the default, "
                              "not as a current reading.")),
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
    # Over the SAME union /all serves. Reading economy_items alone made this probe
    # report the agency feed's freshness while calling it the whole corpus -- and
    # `dpp_watch.py` independently read "commission 0 news rows" from it.
    src, src_params = _news_source_sql(None, _NEWS_TYPES, None, None, None)
    row = db.execute(text(
        "SELECT max(document_date) FILTER (WHERE document_date <= now()) AS latest, "
        "       count(*) AS n, "
        "       count(*) FILTER (WHERE document_date > now()) AS future_dated "
        f"FROM {src} u"), src_params).fetchone()
    latest = _as_date(row.latest) if row and row.latest else None
    age = (date.today() - latest).days if latest else None
    # EVERY body, stalest first, and NOT a LIMIT 10.
    #
    # This used to be `ORDER BY max(document_date) DESC LIMIT 10`, which returns the
    # ten FRESHEST bodies. It is the one truncation that cannot ever show a problem:
    # read alone the endpoint reported 0 stale bodies while 20 were over 30 days old,
    # and it hid 64 of 74 bodies with no marker saying so. Any monitoring built on it
    # was blind by construction. 77 bodies is a small payload; return all of them.
    #
    # `last_fetched` is the second anchor: `fetched_at`, NOT `creation_date`.
    #
    # CORRECTED 8 September 2026, same day this endpoint shipped. The first version
    # read `creation_date` and reported 17 bodies as `dead_fetcher`. That was wrong.
    # `scripts/sync_economy.py` upserts with
    #     creation_date = COALESCE(economy_items.creation_date, EXCLUDED.creation_date),
    #     fetched_at    = now()
    # so `creation_date` is FIRST-SEEN and deliberately preserved on conflict, while
    # `fetched_at` is the last time the cron touched the row. An old creation_date
    # therefore means "no NEW item has appeared since then", which is a statement
    # about the PUBLISHER, not about our scraper.
    #
    # Proved by running all 17 ingestors: 16 returned items (cert_eu 27, eismea 60,
    # f4e 157, eea 465, euaa 572) matching the stored row counts, and their
    # `fetched_at` was 0-16 days old. Only `esm` was genuinely broken. Labelling a
    # quiet agency "dead_fetcher" sends someone to debug a scraper that works.
    per_body = db.execute(text(
        "SELECT body_code, "
        "       max(document_date) FILTER (WHERE document_date <= now()) AS latest, "
        "       max(fetched_at) AS last_fetched, "
        "       max(creation_date) AS first_seen, "
        "       count(*) AS n, "
        "       count(*) FILTER (WHERE document_date IS NULL) AS undated "
        f"FROM {src} u GROUP BY body_code "
        "ORDER BY max(document_date) FILTER (WHERE document_date <= now()) "
        "         ASC NULLS FIRST"),
        src_params).fetchall()
    names = _body_names(db)

    def _classify(r):
        """(state, age_days, fetch_age_days, likely_cause).

        Three states, never two: `undated` is not `stale` and must not be reported as
        if it were (feedback_zero_denominator_is_not_a_pass).

        The cause names say who has the problem, which the first version got wrong:
          not_fetched     the CRON has not reached this body -> ours to fix
          undated_items   fetched fine, items carry no date  -> ours to fix
          publisher_quiet fetched fine, dates fine, the SOURCE has published
                          nothing newer -> NOT a defect, do not send anyone to
                          debug a working scraper
        """
        latest_b = _as_date(r.latest) if r.latest else None
        fetched = _as_date(r.last_fetched) if r.last_fetched else None
        age_b = (date.today() - latest_b).days if latest_b else None
        fetch_age = (date.today() - fetched).days if fetched else None
        if latest_b is None:
            state = "undated"
        elif age_b is not None and age_b > body_stale_after_days:
            state = "stale"
        else:
            state = "fresh"
        cause = None
        if fetch_age is None:
            # UNKNOWN, not failing. The institutional half of the union carries no
            # last-fetch column at all, so claiming "not_fetched" here would invent
            # a defect -- the same error, in the other direction, as reading
            # creation_date as an ingestion anchor.
            if state != "fresh":
                cause = "fetch_time_unknown"
        elif fetch_age > body_stale_after_days:
            # The only cause that means OUR ingestion is failing.
            if state != "fresh":
                cause = "not_fetched"
        elif state == "undated":
            cause = "undated_items"
        elif state == "stale":
            cause = "publisher_quiet"
        return state, age_b, fetch_age, cause

    body_rows = []
    counts = {"fresh": 0, "stale": 0, "undated": 0}
    for r in per_body:
        state, age_b, fetch_age, cause = _classify(r)
        counts[state] += 1
        body_rows.append({
            "code": r.body_code, "name": names.get(r.body_code),
            "latest_date": (_as_date(r.latest).isoformat() if r.latest else None),
            "age_days": age_b,
            "last_fetched": (_as_date(r.last_fetched).isoformat() if r.last_fetched else None),
            "fetch_age_days": fetch_age,
            # first_seen is when the NEWEST row was first captured. Kept because it
            # answers "when did this body last publish something new", but it is NOT
            # the ingestion anchor -- reading it as one is what produced the false
            # "17 dead fetchers".
            "first_seen": (_as_date(r.first_seen).isoformat() if r.first_seen else None),
            "item_count": r.n, "undated_items": r.undated,
            "state": state, "likely_cause": cause,
        })
    return {
        "latest_date": latest.isoformat() if latest else None,
        "age_days": age,
        "stale": (age is None or age > stale_after_days),
        "stale_after_days": stale_after_days,
        # Echo BOTH thresholds: `stale` above is judged by the first,
        # every per-body `state`/`likely_cause` by the second. A verdict whose
        # threshold the caller cannot read is not a reproducible verdict.
        "body_stale_after_days": body_stale_after_days,
        "total_items": row.n if row else 0,
        # Non-zero means dates are being scraped from the wrong field somewhere.
        "future_dated_items": (row.future_dated if row else 0),
        # Estate-level counts, so a caller never has to derive them from a
        # truncated list. `stale` above is the CORPUS anchor (one fresh body keeps it
        # false); these are what tell you whether individual bodies are broken.
        "bodies_total": len(body_rows),
        "bodies_fresh": counts["fresh"],
        "bodies_stale": counts["stale"],
        "bodies_undated": counts["undated"],
        # False, always, and present so a consumer can assert on it. The previous
        # LIMIT 10 had no such marker, which is why it read as a complete estate.
        "by_body_truncated": False,
        # Every body, STALEST FIRST (was: the 10 freshest). The order changed
        # deliberately: a monitoring consumer needs the broken ones on top.
        "by_body": body_rows,
    }


@router.get("/bodies", response_model=dict, tags=["v2-news"],
            summary="Pick-list: bodies and policy families with news counts",
            description=(
                "**What it does**\nThe discovery endpoint for the `body` and `family` filters: every body "
                "with news (count + families) and every Brubru policy family (bodies + total count).\n\n"
                "**When to use it**\nTo build a picker, or to see what `family=` expands to.\n\n**Input**\n"
                "No parameters.\n\n**Try it**\n```\nGET /api/v2/news/bodies\n```\n\n**You get back**\n"
                "`{bodies: [...], families: [...]}`.\n\n**Data freshness**\nLive, across both news stores."))
async def bodies_facet(request: Request, db: Session = Depends(get_db),
                       user: User = Depends(api_user_with_rate_limit)):
    # Same union: a body the picker cannot show is a body nobody can filter to.
    src, src_params = _news_source_sql(None, _NEWS_TYPES, None, None, None)
    rows = db.execute(text(
        f"SELECT body_code, count(*) n FROM {src} u GROUP BY body_code"),
        src_params).fetchall()
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
                   item_id: str = PathParam(..., description=(
                       "Brubru item id from the list endpoint: an integer for an agency "
                       "item, a UUID for a Commission / Parliament / Council item.")),
                   db: Session = Depends(get_db),
                   user: User = Depends(api_user_with_rate_limit)):
    # `item_id` is typed str, not int, because the institutional half of the feed
    # is keyed by UUID. NOTE: `/latest` and `/bodies` are literal paths declared
    # BEFORE this route and are matched first -- that ordering was already
    # load-bearing when this was int-typed, and it is more so now that a string
    # id would happily match them. Do not move this route above them.
    if item_id.isdigit():
        r = db.execute(text(
            "SELECT id, body_code, item_type, title, summary, public_url, body_txt, body_html, "
            "document_date, creation_date FROM economy_items "
            "WHERE id = :id AND item_type = ANY(:t)"),
            {"id": int(item_id), "t": _NEWS_TYPES}).fetchone()
    else:
        case_body = "CASE n.institution " + " ".join(
            f"WHEN '{inst}' THEN '{code}'" for code, inst in _INSTITUTIONAL_NEWS.items()
        ) + " END"
        try:
            r = db.execute(text(
                f"SELECT n.id::text AS id, {case_body} AS body_code, {_EU_NEWS_KIND_SQL} AS item_type, "
                "n.title, n.summary, n.source_url AS public_url, "
            # `summary` is the fullest text eu_news_items holds; hardcoding NULL
            # here meant a Commission item could never return a body from ANY
            # route, list or detail. Reported by a partner integrating v2.
            "n.summary AS body_txt, NULL AS body_html, "
                "COALESCE(n.news_date::timestamptz, n.created_at) AS document_date, "
                "n.created_at AS creation_date FROM eu_news_items n "
                "WHERE n.id = :id AND n.institution = ANY(:i) AND n.item_type = ANY(:t)"),
                {"id": item_id, "i": list(_INSTITUTIONAL_NEWS.values()),
                 "t": _EU_NEWS_SOURCE_TYPES}).fetchone()
        except Exception:
            # A malformed UUID is a bad id, not a server fault. Roll back so the
            # session stays usable, then fall through to the 404 below.
            db.rollback()
            r = None
    if r is None:
        raise HTTPException(404, f"No news item with id {item_id}")
    return _to_item(r, _body_names(db), with_body=True)
