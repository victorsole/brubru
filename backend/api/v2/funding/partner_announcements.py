"""GET /api/v2/funding/partner-announcements — organisations looking for partners on the F&T Portal.

Phase 1 C2 of the funding standard (proposal 23 Oct 2026, §3.3, item type `partner_announcement`). On
21 Oct Beresol's partner search for a DG CNECT tender found nothing from Brubru about organisations
that publish their interest on the F&T Portal's Partner Search, most of which hold no EU project yet.
ft_partner_search_announcements + ft_partner_search_orgs (migration 316, scripts/sync_ft_partner_search.py)
hold every organisation announcement in the portal's search index since 2018 (329,855 from 16,084
organisations on 27 Oct 2026): never a person's profile or announcement, nor a profile that may be a
person's own registration (services/funding/organisations.py).

`status` is the topic's status as Brubru holds it (ft_calls_for_proposals: open, forthcoming,
closed), not the index's own field, which keeps the status the topic had when the announcement was
indexed (2019 announcements still say Forthcoming).
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.v1._change_window import SYNC_ORDERS, SYNC_PARAMS_DOC, UpperBoundDatetime, sql_order, sql_window, validate_window
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from core.database import get_db
from models.user import User
from services.funding.countries import eu_code
from services.funding.programme_codes import named_codes, topic_prefixes
from services.scrapers.ft_partner_search import compose_body

router = APIRouter()

_ORDERS = {"recent", "oldest"}
_ORDER_SQL = {
    "recent": "s.requested_date DESC NULLS LAST, s.announcement_id DESC",
    "oldest": "s.requested_date ASC NULLS LAST, s.announcement_id ASC",
}
_EXPERTISE = {"offer", "request"}
_TOPIC_STATUSES = {"open", "forthcoming", "closed"}
# The expression the table's full-text index is built on (migration 316).
_TSV = "to_tsvector('english', coalesce(s.topic_title, '') || ' ' || coalesce(s.summary, ''))"
# The topic as Brubru holds it (topic_id is unique in the calls table).
_JOINS = ("LEFT JOIN ft_partner_search_orgs o ON o.pic = s.pic "
          "LEFT JOIN ft_calls_for_proposals t ON t.topic_id = s.topic_id AND t.is_test = false")
_COLS = ("s.announcement_id, s.pic, s.organisation_name, s.country, s.organisation_type, s.expertise, s.topic_id, "
         "s.topic_ids, s.topic_title, s.summary, s.summary_cut, s.requested_date, s.public_url, s.first_seen, "
         "s.last_updated, o.city, o.projects, t.status AS topic_status, t.deadline AS topic_deadline")
_FROM = f"FROM ft_partner_search_announcements s {_JOINS} WHERE true"


class AnnouncingOrganisation(BaseModel):
    pic: str = Field(..., description="Participant Identification Code.")
    name: Optional[str] = None
    country: Optional[str] = Field(None, description="EU style code (EL Greece, UK United Kingdom).")
    city: Optional[str] = None
    organisation_type: Optional[str] = Field(None, description="As the portal states it: Small or medium-size enterprise, "
                                             "Research Organisation, Higher or secondary education establishment ...")
    projects: Optional[int] = Field(None, description="Its EU projects, as the portal counts them (0: none yet); none when "
                                    "Brubru does not hold its profile yet (the index can list a new announcement first).")
    role: str = Field("partner", description="Always partner: the organisation that published the announcement.")
    partner: str = Field(..., description="This organisation on /api/v2/funding/partners.")


class PartnerAnnouncementItem(BaseModel):
    id: str = Field(..., description="The announcement's id on the portal.")
    item_type: str = "partner_announcement"
    title: Optional[str] = Field(None, description="The topic's title.")
    summary: Optional[str] = Field(None, description="What the organisation wrote: its first 500 characters, as the "
                                   "portal's search shows them, without e-mail addresses, ORCIDs, LinkedIn links or "
                                   "telephone numbers.")
    status: Optional[str] = Field(None, description="The topic's status as Brubru holds it: open | forthcoming | closed; "
                                  "none when Brubru does not hold the topic.")
    announcement_id: str
    expertise: Optional[str] = Field(None, description="offer (it offers its expertise) | request (it seeks expertise).")
    topic_id: Optional[str] = Field(None, description="The call topic, e.g. HORIZON-CL5-2024-D4-02-05.")
    topic_ids: List[str] = Field(default_factory=list)
    topic_title: Optional[str] = None
    topic_deadline: Optional[datetime] = Field(None, description="The topic's deadline, when Brubru holds the topic.")
    summary_cut: bool = Field(False, description="True when the text stops at the portal's 500 characters.")
    pic: str
    organisation_name: Optional[str] = None
    country: Optional[str] = None
    organisation_type: Optional[str] = None
    organisations: List[AnnouncingOrganisation] = Field(default_factory=list, description="The organisation, role partner.")
    public_url: str = Field(..., description="The organisation's Partner Search profile on the F&T Portal.")
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = Field(None, description="The announcement's date.")
    creation_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None


def _body(r) -> tuple:
    """The announcement as text and HTML, composed from its columns (none is stored: migration 317)."""
    return compose_body({"organisation_name": r.organisation_name, "pic": r.pic, "country": r.country,
                         "organisation_type": r.organisation_type, "expertise": r.expertise, "topic_id": r.topic_id,
                         "topic_title": r.topic_title, "summary": r.summary, "summary_cut": r.summary_cut,
                         "requested_date": r.requested_date})


def _item(r, base: str, with_body: bool) -> PartnerAnnouncementItem:
    body = _body(r) if with_body else (None, None)
    org = AnnouncingOrganisation(pic=r.pic, name=r.organisation_name, country=r.country, city=r.city,
                                 organisation_type=r.organisation_type, projects=r.projects,
                                 partner=f"{base}/api/v2/funding/partners/pic:{r.pic}")
    return PartnerAnnouncementItem(
        id=r.announcement_id, title=r.topic_title, summary=r.summary, status=r.topic_status,
        announcement_id=r.announcement_id, expertise=r.expertise, topic_id=r.topic_id, topic_ids=list(r.topic_ids or []),
        topic_title=r.topic_title, topic_deadline=r.topic_deadline, summary_cut=bool(r.summary_cut), pic=r.pic,
        organisation_name=r.organisation_name, country=r.country, organisation_type=r.organisation_type,
        organisations=[org], public_url=r.public_url,
        body_txt=body[0], body_html=body[1],
        document_date=r.requested_date, creation_date=r.first_seen, updated_date=r.last_updated,
    )


_DESC = f"""**What it does**
Organisations looking for partners: every announcement an organisation published on the F&T Portal's Partner Search (since 2018), with the call topic it is for, whether it **offers** its expertise or **requests** expertise, and what it wrote. On 27 Oct 2026 Brubru held 329,855 announcements from 16,084 organisations; of the 9,996 whose portal profile carries the Partner Search flag, 5,196 had no EU project as the portal counts them, so they appear nowhere else in Brubru's funding data. Organisations only: the portal's person profiles and persons' announcements are never read, and since the portal lists some people with their own registration as organisations and says nowhere which, a self-registered profile (not validated by the Commission) typed Other, SME or private for-profit whose name carries no legal form, organisation word or digit is left out with its announcements (on 27 Oct 2026 this left out 2,635 profiles, 1,544 of the 11,540 with the flag, and took Brubru from 358,431 announcements to 329,855; a validated profile is always kept).

**When to use it**
"Who is looking for partners on this topic", "which SMEs in Spain offer expertise for hydrogen calls", "who seeks a partner for an open Horizon Europe topic". For an organisation's whole record (its projects, EU payments, contract awards and announcements), follow its `partner` link to `/api/v2/funding/partners`.

**Input**
- `q` — words in the topic's title and the announcement's text (full text: every word in any form; `"quoted phrase"`, `OR`, `-word`).
- `topic` — a topic code or its start (`HORIZON-CL5-2026`); `programme` — part of the topic code (`LIFE`, `ERASMUS`, `EDF`, `DIGITAL`) or a programme's name (`Horizon Europe`, `Connecting Europe`).
- `status` — the topic's status as Brubru holds it: open | forthcoming | closed (announcements for topics Brubru does not hold are then left out).
- `expertise` — offer | request. `organisation_type` — part of the portal's type (`Small or medium`, `Research`, `Higher or secondary education`, `Public`, `Non-governmental`).
- `pic`, `organisation` (part of its name), `country` (ISO-2; EL and GR, UK and GB are the same); `without_eu_projects=true` — only organisations with no EU project yet.
- `requested_from`, `requested_to` (`since`, `until`, `from`, `to` are aliases). {SYNC_PARAMS_DOC.replace(chr(10), ' ')}
- `order` — recent (default) | oldest | updated_asc | updated_desc | created_asc | created_desc. `page`, `limit` (default 50, max 200), `include_body` (default true).

**Try it**
```
GET /api/v2/funding/partner-announcements?topic=HORIZON-CL5&expertise=request
GET /api/v2/funding/partner-announcements?q=hydrogen%20storage&country=ES&status=open
GET /api/v2/funding/partner-announcements?programme=LIFE&without_eu_projects=true
```

**You get back**
A paginated envelope. Each item: `id` (the announcement's id), `title` (the topic's title), `summary` (what the organisation wrote: its first 500 characters, as the portal's search shows them, `summary_cut` true when it stops there; e-mail addresses, ORCIDs, LinkedIn links and telephone numbers removed), `status` and `topic_deadline` (the topic as Brubru holds it), `expertise`, `topic_id`, `organisations` (the organisation: PIC, name, country, city, type, its EU projects as the portal counts them, and its `partner` link; where the announcement gives no name, country or type, as 544 from 2018-2022 do, its profile's), `public_url` (its Partner Search profile on the portal; the full text and the contact form need an EU Login), `body_txt` / `body_html` (on the list unless `include_body=false`, and on the item route), `document_date` (the announcement's date), `creation_date`, `updated_date`.

**Data freshness**
The portal's search index, read every day: the announcements of the last 14 days, and a seventh of the older ones in turn, so every announcement is read again each week (one no longer there is deleted)."""


@router.get("/partner-announcements", response_model=PaginatedResponse[PartnerAnnouncementItem], tags=["v2-funding"],
            summary="Partner announcements — organisations looking for partners on the F&T Portal",
            description=_DESC)
async def list_partner_announcements(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    q: Optional[str] = Query(None, description="Words in the topic's title and the announcement's text (full text)."),
    topic: Optional[str] = Query(None, description="A topic code or its start, e.g. HORIZON-CL5-2026."),
    programme: Optional[str] = Query(None, description="Part of the topic code, e.g. LIFE, ERASMUS, EDF."),
    status: Optional[str] = Query(None, description="The topic's status as Brubru holds it: open | forthcoming | closed."),
    expertise: Optional[str] = Query(None, description="offer | request."),
    organisation_type: Optional[str] = Query(None, description="Part of the portal's type, e.g. Small or medium, Research."),
    pic: Optional[str] = Query(None, description="The organisation's PIC."),
    organisation: Optional[str] = Query(None, description="Part of the organisation's name."),
    country: Optional[str] = Query(None, min_length=2, max_length=2, description="The organisation's country, ISO-2."),
    without_eu_projects: bool = Query(False, description="Only organisations with no EU project yet (as the portal counts them)."),
    requested_from: Optional[date] = Query(None, description="Announced on or after (YYYY-MM-DD)."),
    requested_to: Optional[date] = Query(None, description="Announced on or before (YYYY-MM-DD)."),
    since: Optional[date] = Query(None, include_in_schema=False),
    until: Optional[date] = Query(None, include_in_schema=False),
    from_: Optional[date] = Query(None, alias="from", include_in_schema=False),
    to: Optional[date] = Query(None, include_in_schema=False),
    created_from: Optional[datetime] = Query(None, description="First recorded by Brubru on or after (ISO date or datetime, UTC)."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First recorded by Brubru on or before; a bare date covers the whole day."),
    updated_from: Optional[datetime] = Query(None, description="Last changed on or after. The incremental-sync filter."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Last changed on or before; a bare date covers the whole day."),
    order: str = Query("recent", description="recent | oldest | updated_asc | updated_desc | created_asc | created_desc."),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    include_body: bool = Query(True, description="Return body_txt / body_html on every item of the list (default true)."),
):
    if order not in _ORDERS and order not in SYNC_ORDERS:
        raise HTTPException(status_code=400, detail=f"order must be one of {sorted(_ORDERS) + list(SYNC_ORDERS)}")
    for value, allowed, label in ((expertise, _EXPERTISE, "expertise"), (status, _TOPIC_STATUSES, "status")):
        if value is not None and value not in allowed:
            raise HTTPException(status_code=400, detail=f"{label} must be one of {sorted(allowed)}")
    window = validate_window(created_from, created_to, updated_from, updated_to)
    where: list = []
    params: dict = {"limit": limit, "offset": (page - 1) * limit}
    if q:
        where.append(f"{_TSV} @@ websearch_to_tsquery('english', :q)"); params["q"] = q
    if topic:
        where.append("s.topic_id ILIKE :topic"); params["topic"] = f"{topic.strip()}%"
    if programme:
        params["programme"] = f"%{programme.strip()}%"
        named = named_codes(programme)
        if named:
            # "Horizon Europe" -> HORIZON-..., "Connecting Europe" -> CEF-...: the topic carries the code.
            params["prog_topics"] = topic_prefixes(named)
            where.append("(s.topic_id ILIKE :programme OR s.topic_id ILIKE ANY(CAST(:prog_topics AS text[])))")
        else:
            where.append("s.topic_id ILIKE :programme")
    if status:
        where.append("s.topic_id IN (SELECT topic_id FROM ft_calls_for_proposals WHERE status = :status AND is_test = false)")
        params["status"] = status
    if expertise:
        where.append("s.expertise = :expertise"); params["expertise"] = expertise
    if organisation_type:
        where.append("s.organisation_type ILIKE :otype"); params["otype"] = f"%{organisation_type.strip()}%"
    if pic:
        where.append("s.pic = :pic"); params["pic"] = pic.strip()
    if organisation:
        where.append("s.organisation_name ILIKE :org"); params["org"] = f"%{organisation.strip()}%"
    if country:
        where.append("s.country = :cc"); params["cc"] = eu_code(country)
    if without_eu_projects:
        where.append("s.pic IN (SELECT pic FROM ft_partner_search_orgs WHERE projects = 0)")
    start, end = requested_from or since or from_, requested_to or until or to
    if start:
        where.append("s.requested_date >= :start"); params["start"] = start
    if end:
        where.append("s.requested_date <= :end"); params["end"] = end
    sql_window(where, params, window, "s.first_seen", "s.last_updated")
    # The page is chosen on the announcements alone; the organisation and the topic join its rows only.
    clause = "FROM ft_partner_search_announcements s WHERE true" + "".join(f" AND {w}" for w in where)
    total = db.execute(text(f"SELECT count(*) {clause}"), params).scalar() or 0
    order_sql = sql_order(order, "s.first_seen", "s.last_updated", "s.announcement_id") or _ORDER_SQL[order]
    rows = db.execute(text(
        f"""WITH page AS (SELECT s.announcement_id {clause} ORDER BY {order_sql} LIMIT :limit OFFSET :offset)
            SELECT {_COLS} FROM page JOIN ft_partner_search_announcements s USING (announcement_id) {_JOINS}
             ORDER BY {order_sql}"""), params).fetchall()
    base = str(request.base_url).rstrip("/")
    items = [_item(r, base, include_body) for r in rows]
    return build_envelope(items, total, page, limit, updated_from=window["updated_from"], updated_to=window["updated_to"])


@router.get("/partner-announcements/{announcement_id}", response_model=PartnerAnnouncementItem, tags=["v2-funding"],
            summary="One partner announcement — an organisation's offer or request for a topic",
            description="""**What it does**
One announcement from `/api/v2/funding/partner-announcements` in full: the organisation, the topic, what it wrote, and the announcement as text.

**When to use it**
After the list, to read one announcement's whole record.

**Input**
`announcement_id` — the announcement's id on the portal (each item's `id`; its `self` is this route).

**Try it**
```
GET /api/v2/funding/partner-announcements/197771
```

**You get back**
One item with the list's fields, `body_txt` and `body_html` included, or 404 when Brubru does not hold that announcement (it holds the organisations' announcements in the portal's search index; a person's are never read).

**Data freshness**
As the list: read every day, every announcement again each week.""")
async def get_partner_announcement(
    request: Request,
    announcement_id: str = PathParam(..., description="The announcement's id, e.g. 197771."),
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
):
    r = db.execute(text(f"SELECT {_COLS} {_FROM} AND s.announcement_id = :a"), {"a": announcement_id.strip()}).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail=f"No partner announcement with id {announcement_id}")
    return _item(r, str(request.base_url).rstrip("/"), True)
