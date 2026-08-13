"""
/api/v2/events — every EU body's events in one folder.

A cross-body AGGREGATOR (it ingests nothing): a query-time UNION of the two event
stores Brubru already keeps fresh —
  - economy_items (item_type='event')  : agencies, JUs, ECB, EUIPO, Cedefop, ...
  - eu_calendar_events                 : Commission / Parliament / Council / ... institutional calendar
deduplicated by URL (the calendar copy wins, it is richer), mapped onto one event
envelope with the 5 mandatory datapoints.

"On demand" = the caller picks the scope: a list of bodies, a proprietary policy
`family` (e.g. defence-security-borders), or everything. No new table, no new cron;
freshness comes from each body's existing sync. Scope: read:economy.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
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
    FAMILIES, bodies_for_family, families_for_body, family_label,
    BODY_TO_CAL_INSTITUTION, CAL_INSTITUTION_TO_BODY, CALENDAR_ONLY_BODY_NAMES,
)

router = APIRouter(prefix="/events", tags=["v2-events"])

_SOURCES = {"economy", "calendar", "all"}
_WHENS = {"upcoming", "past", "all"}
_ORDERS = {"recent", "oldest", "title"}


# --------------------------------------------------------------------------- #
# Models                                                                       #
# --------------------------------------------------------------------------- #
class EventItem(BaseModel):
    id: str = Field(..., description="Stable aggregator id (use on the detail endpoint). Prefixed by source: 'e<n>' economy, 'c<uuid>' calendar.")
    body_code: str = Field(..., description="Canonical body code the event belongs to.")
    body_name: Optional[str] = Field(None, description="Human-readable body name.")
    families: List[str] = Field(default_factory=list, description="Brubru policy families this body belongs to.")
    source: str = Field(..., description="Which store the event came from: economy | calendar.")
    title: str
    summary: Optional[str] = None
    event_type: Optional[str] = Field(None, description="Event kind where known (calendar events).")
    venue: Optional[str] = Field(None, description="Venue / location where known.")
    public_url: Optional[str] = Field(None, description="Canonical URL of the event on the source website.")
    body_txt: Optional[str] = Field(None, description="Plain-text body (full on detail; null on list).")
    body_html: Optional[str] = Field(None, description="HTML body (full on detail; null on list).")
    document_date: Optional[datetime] = Field(None, description="The event's own date (start datetime).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested the event.")


class EventBody(BaseModel):
    code: str
    name: Optional[str] = None
    families: List[str] = Field(default_factory=list)
    event_count: int = 0


class EventFamily(BaseModel):
    slug: str
    label: str
    bodies: List[str]
    event_count: int = 0


# --------------------------------------------------------------------------- #
# Body-name lookup (economy_bodies + calendar-only friendly names)             #
# --------------------------------------------------------------------------- #
def _body_names(db: Session) -> dict:
    names = dict(CALENDAR_ONLY_BODY_NAMES)
    for r in db.execute(text("SELECT code, name FROM economy_bodies")).fetchall():
        names.setdefault(r.code, r.name)
    return names


def _cal_dt(start_date, start_time) -> Optional[datetime]:
    if start_date is None:
        return None
    t = start_time or time(0, 0)
    return datetime.combine(start_date, t, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Core fetch: union both stores into a list of unified dicts                   #
# --------------------------------------------------------------------------- #
def _resolve_scope(bodies: Optional[str], family: Optional[str]):
    """Return the canonical body-code set to scope to, or None for 'all bodies'."""
    codes: set[str] = set()
    if family:
        for slug in [s.strip() for s in family.split(",") if s.strip()]:
            codes |= bodies_for_family(slug)
    if bodies:
        codes |= {b.strip() for b in bodies.split(",") if b.strip()}
    return codes or None


def _fetch(db, *, codes, since, until, when, q, sources, with_body=False):
    now = datetime.now(timezone.utc)
    today = now.date()
    out = []

    if "economy" in sources:
        where = ["item_type = 'event'"]
        params = {}
        if codes is not None:
            where.append("body_code = ANY(:codes)")
            params["codes"] = list(codes)
        if since:
            where.append("document_date >= :since"); params["since"] = since
        if until:
            where.append("document_date <= :until"); params["until"] = until
        if when == "upcoming":
            where.append("document_date >= :now"); params["now"] = now
        elif when == "past":
            where.append("document_date < :now"); params["now"] = now
        if q:
            where.append("search_vector @@ plainto_tsquery('english', :q)"); params["q"] = q
        cols = "id, body_code, title, summary, public_url, document_date, creation_date" + (
            ", body_txt, body_html" if with_body else "")
        rows = db.execute(text(
            f"SELECT {cols} FROM economy_items WHERE {' AND '.join(where)} LIMIT 8000"), params).fetchall()
        for r in rows:
            out.append({
                "id": f"e{r.id}", "body_code": r.body_code, "source": "economy",
                "title": r.title, "summary": r.summary, "event_type": None, "venue": None,
                "public_url": r.public_url, "document_date": r.document_date,
                "creation_date": r.creation_date,
                "body_txt": getattr(r, "body_txt", None), "body_html": getattr(r, "body_html", None),
            })

    if "calendar" in sources:
        where = ["1=1"]
        params = {}
        if codes is not None:
            insts = [BODY_TO_CAL_INSTITUTION[c] for c in codes if c in BODY_TO_CAL_INSTITUTION]
            if not insts:
                insts = ["__none__"]
            where.append("institution::text = ANY(:insts)"); params["insts"] = insts
        if since:
            where.append("start_date >= :since"); params["since"] = since
        if until:
            where.append("start_date <= :until"); params["until"] = until
        if when == "upcoming":
            where.append("start_date >= :today"); params["today"] = today
        elif when == "past":
            where.append("start_date < :today"); params["today"] = today
        if q:
            where.append("(title ILIKE :q OR description ILIKE :q)"); params["q"] = f"%{q}%"
        rows = db.execute(text(
            "SELECT id, institution::text AS institution, title, description, source_url, agenda_url, "
            "start_date, start_time, first_seen, event_type::text AS event_type, venue "
            f"FROM eu_calendar_events WHERE {' AND '.join(where)} LIMIT 8000"), params).fetchall()
        for r in rows:
            body = CAL_INSTITUTION_TO_BODY.get(r.institution, (r.institution or "").lower())
            body_html = f"<p>{r.description}</p>" if (with_body and r.description) else None
            out.append({
                "id": f"c{r.id}", "body_code": body, "source": "calendar",
                "title": r.title, "summary": r.description, "event_type": r.event_type, "venue": r.venue,
                "public_url": r.source_url or r.agenda_url, "document_date": _cal_dt(r.start_date, r.start_time),
                "creation_date": r.first_seen,
                "body_txt": (r.description if with_body else None), "body_html": body_html,
            })

    # Dedup carefully. The calendar's source_url is frequently a shared LISTING page
    # (e.g. 210 EP committee events point at one committees URL), so URL is NOT a
    # calendar event identity. Economy URLs, by contrast, are unique per event.
    # So: keep all calendar events; dedup economy internally by URL; and drop an
    # economy event only when its URL matches a UNIQUE calendar URL (a real
    # per-event page = the same event in both stores, calendar wins).
    from collections import Counter
    cal = [it for it in out if it["source"] == "calendar"]
    econ = [it for it in out if it["source"] == "economy"]
    cal_counts = Counter((it["public_url"] or "").rstrip("/").lower() for it in cal if it["public_url"])
    cal_unique = {u for u, n in cal_counts.items() if n == 1}
    deduped = list(cal)
    seen_econ: set = set()
    for it in econ:
        u = (it["public_url"] or "").rstrip("/").lower()
        if u and u in cal_unique:
            continue  # same event already present from the calendar
        if u and u in seen_econ:
            continue  # exact economy-internal duplicate
        if u:
            seen_econ.add(u)
        deduped.append(it)
    return deduped


def _sort_key(order):
    far_past = datetime(1, 1, 1, tzinfo=timezone.utc)
    far_future = datetime(9999, 1, 1, tzinfo=timezone.utc)
    if order == "title":
        return (lambda it: (it["title"] or "").lower()), False
    if order == "oldest":
        return (lambda it: it["document_date"] or far_future), False
    return (lambda it: it["document_date"] or far_past), True  # recent


def _to_item(it, names, *, with_body):
    return EventItem(
        id=it["id"], body_code=it["body_code"], body_name=names.get(it["body_code"]),
        families=families_for_body(it["body_code"]), source=it["source"],
        title=it["title"], summary=it["summary"], event_type=it["event_type"], venue=it["venue"],
        public_url=it["public_url"], document_date=it["document_date"], creation_date=it["creation_date"],
        body_txt=(it["body_txt"] if with_body else None),
        body_html=(it["body_html"] if with_body else None),
    )


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #
class EventsDirectory(BaseModel):
    total_events: int
    upcoming: int
    past: int
    undated: int
    bodies_with_events: int
    families: int
    earliest: Optional[datetime] = None
    latest: Optional[datetime] = None


@router.get("", response_model=EventsDirectory, tags=["v2-events"],
            summary="Events folder directory — every EU body's events, aggregated",
            description=(
                "**What it does**\nOne-call overview of the cross-body events feed: total events, how "
                "many are upcoming vs past vs undated, how many bodies and policy families are covered, "
                "and the date span.\n\n**When to use it**\nBefore querying the feed, to see the shape of "
                "what is there.\n\n**Input**\nNo parameters.\n\n**Try it**\n```\nGET /api/v2/events\n```\n\n"
                "**You get back**\nA summary object. Then call `/api/v2/events/all` to read the feed, "
                "`/api/v2/events/bodies` to see the pick-list, or `/api/v2/events/{id}` for one event.\n\n"
                "**Data freshness**\nLive from economy_items + eu_calendar_events."))
async def directory(request: Request, db: Session = Depends(get_db),
                    user: User = Depends(api_user_with_rate_limit)):
    items = _fetch(db, codes=None, since=None, until=None, when="all", q=None, sources={"economy", "calendar"})
    now = datetime.now(timezone.utc)
    dated = [it["document_date"] for it in items if it["document_date"]]
    return EventsDirectory(
        total_events=len(items),
        upcoming=sum(1 for d in dated if d >= now),
        past=sum(1 for d in dated if d < now),
        undated=len(items) - len(dated),
        bodies_with_events=len({it["body_code"] for it in items}),
        families=len(FAMILIES),
        earliest=min(dated) if dated else None,
        latest=max(dated) if dated else None,
    )


@router.get("/all", response_model=PaginatedResponse[EventItem], tags=["v2-events"],
            summary="All events, all bodies (pick your scope)",
            description=(
                "**What it does**\nThe unified events feed across every EU body, newest first.\n\n"
                "**When to use it**\nOne call for 'all events from the bodies I care about'. Scope it "
                "with `body` (comma-separated codes) and/or `family` (a Brubru policy family, e.g. "
                "`defence-security-borders`); omit both for every body.\n\n**Input**\n`body` "
                "(comma list of body codes), `family` (comma list of family slugs), `when` "
                "(upcoming | past | all), `from` / `to` (YYYY-MM-DD on the event date), `days` (shorthand "
                "window: the next N days when `when=upcoming`, otherwise the last N days), `q` (free text), "
                "`source` (economy | calendar | all), `order` (recent | oldest | title), `page`, `limit` "
                "(max 100).\n\n**Try it**\n```\nGET /api/v2/events/all?when=upcoming&days=14\n"
                "GET /api/v2/events/all?family=defence-security-borders&when=upcoming\n"
                "GET /api/v2/events/all?body=commission,parliament,ecb&order=recent\n```\n\n**You get back**\n"
                "A paginated envelope of events. Each carries the 5 datapoints (`body_txt` / `body_html` "
                "null on the list — fetch the detail endpoint), plus body_code, body_name, the policy "
                "families, source and (for calendar events) event_type and venue. `published_from` / "
                "`published_to` echo the date window actually applied. Undated events sort "
                "last.\n\n**Data freshness**\nLive union of economy_items + eu_calendar_events."))
async def list_events(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    body: Optional[str] = Query(None, description="Comma-separated body codes (e.g. commission,parliament,ecb,sesar)."),
    family: Optional[str] = Query(None, description="Comma-separated Brubru policy family slugs (see /api/v2/events/bodies)."),
    when: str = Query("all", description="upcoming | past | all."),
    from_: Optional[date] = Query(None, alias="from", description="Only events on/after this date (YYYY-MM-DD)."),
    to: Optional[date] = Query(None, description="Only events on/before this date (YYYY-MM-DD)."),
    days: Optional[int] = Query(None, ge=1, le=3650, description="Shorthand window: with when=upcoming, the next N days; otherwise the last N days. Ignored if `from`/`to` already bound that side."),
    q: Optional[str] = Query(None, description="Free-text search over title and summary."),
    source: str = Query("all", description="economy | calendar | all."),
    order: str = Query("recent", description="recent | oldest | title."),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    if when not in _WHENS:
        raise HTTPException(400, f"when must be one of {sorted(_WHENS)}")
    if source not in _SOURCES:
        raise HTTPException(400, f"source must be one of {sorted(_SOURCES)}")
    if order not in _ORDERS:
        raise HTTPException(400, f"order must be one of {sorted(_ORDERS)}")
    sources = {"economy", "calendar"} if source == "all" else {source}
    # `days` was never declared, so FastAPI dropped it silently and the caller
    # got the entire 7,300-event corpus back believing it was windowed
    # (28 July 2026). For a forward-looking query the window runs forwards;
    # otherwise backwards. An explicit from/to always wins on its own side.
    if days is not None:
        if when == "upcoming":
            if to is None:
                to = date.today() + timedelta(days=days)
        elif from_ is None:
            from_ = date.today() - timedelta(days=days)
    codes = _resolve_scope(body, family)
    items = _fetch(db, codes=codes, since=from_, until=to, when=when, q=q, sources=sources)
    keyf, rev = _sort_key(order)
    items.sort(key=keyf, reverse=rev)
    total = len(items)
    window = items[(page - 1) * limit: (page - 1) * limit + limit]
    names = _body_names(db)
    return build_envelope(
        [_to_item(it, names, with_body=False) for it in window], total, page, limit,
        published_from=from_, published_to=to,
    )


@router.get("/bodies", response_model=dict, tags=["v2-events"],
            summary="Pick-list: bodies and policy families with event counts",
            description=(
                "**What it does**\nThe discovery endpoint for the `body` and `family` filters: every body "
                "that has events (with its count and families) and every Brubru policy family (with its "
                "bodies and total event count).\n\n**When to use it**\nTo build a body/family picker, or "
                "to see what `family=` expands to.\n\n**Input**\nNo parameters.\n\n**Try it**\n```\n"
                "GET /api/v2/events/bodies\n```\n\n**You get back**\n`{bodies: [...], families: [...]}`.\n\n"
                "**Data freshness**\nLive."))
async def bodies_facet(request: Request, db: Session = Depends(get_db),
                       user: User = Depends(api_user_with_rate_limit)):
    items = _fetch(db, codes=None, since=None, until=None, when="all", q=None, sources={"economy", "calendar"})
    names = _body_names(db)
    by_body: dict = {}
    for it in items:
        by_body[it["body_code"]] = by_body.get(it["body_code"], 0) + 1
    bodies = [EventBody(code=c, name=names.get(c), families=families_for_body(c), event_count=n)
              for c, n in sorted(by_body.items(), key=lambda kv: -kv[1])]
    fams = []
    for slug, f in FAMILIES.items():
        member = set(f["bodies"])
        fams.append(EventFamily(slug=slug, label=f["label"], bodies=f["bodies"],
                                event_count=sum(n for c, n in by_body.items() if c in member)))
    fams.sort(key=lambda x: -x.event_count)
    return {"bodies": [b.model_dump() for b in bodies], "families": [f.model_dump() for f in fams]}


@router.get("/{event_id}", response_model=EventItem, tags=["v2-events"],
            summary="One event (full body)",
            description=(
                "**What it does**\nReturns one event in full, including `body_txt` / `body_html` where "
                "the source provides them.\n\n**When to use it**\nAfter finding an event id on "
                "`/api/v2/events/all`.\n\n**Input**\n`event_id` — the prefixed aggregator id (e.g. "
                "`e12345` or `c<uuid>`).\n\n**Try it**\n```\nGET /api/v2/events/e12345\n```\n\n"
                "**You get back**\nA single event with the full 5-datapoint contract.\n\n"
                "**Data freshness**\nLive."))
async def get_event(request: Request,
                    event_id: str = PathParam(..., description="Prefixed aggregator id: 'e<n>' or 'c<uuid>'."),
                    db: Session = Depends(get_db),
                    user: User = Depends(api_user_with_rate_limit)):
    names = _body_names(db)
    if event_id.startswith("e") and event_id[1:].isdigit():
        r = db.execute(text(
            "SELECT id, body_code, title, summary, public_url, body_txt, body_html, document_date, creation_date "
            "FROM economy_items WHERE id = :id AND item_type = 'event'"), {"id": int(event_id[1:])}).fetchone()
        if r:
            it = {"id": event_id, "body_code": r.body_code, "source": "economy", "title": r.title,
                  "summary": r.summary, "event_type": None, "venue": None, "public_url": r.public_url,
                  "document_date": r.document_date, "creation_date": r.creation_date,
                  "body_txt": r.body_txt, "body_html": r.body_html}
            return _to_item(it, names, with_body=True)
    elif event_id.startswith("c"):
        r = db.execute(text(
            "SELECT id, institution::text AS institution, title, description, source_url, agenda_url, "
            "start_date, start_time, first_seen, event_type::text AS event_type, venue "
            "FROM eu_calendar_events WHERE id = :id"), {"id": event_id[1:]}).fetchone()
        if r:
            body = CAL_INSTITUTION_TO_BODY.get(r.institution, (r.institution or "").lower())
            it = {"id": event_id, "body_code": body, "source": "calendar", "title": r.title,
                  "summary": r.description, "event_type": r.event_type, "venue": r.venue,
                  "public_url": r.source_url or r.agenda_url, "document_date": _cal_dt(r.start_date, r.start_time),
                  "creation_date": r.first_seen, "body_txt": r.description,
                  "body_html": (f"<p>{r.description}</p>" if r.description else None)}
            return _to_item(it, names, with_body=True)
    raise HTTPException(404, f"No event with id {event_id}")
