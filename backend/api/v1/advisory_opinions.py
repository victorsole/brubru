"""
/api/v1/opinions — the opinions of the EU's two advisory committees.

The European Economic and Social Committee and the European Committee of the Regions: the
bodies the Treaties require the Commission, Parliament and Council to consult before adopting
much of EU law. Brubru has held both corpora since migrations 064 and 065 and filled their
full text on 25 September 2026, but no route read either table, so 4,518 opinions averaging
over 20,000 characters were served to nobody. This is that route.

One collection per committee, because each has its own primary key and its own
committee-specific fields, plus `/advisory-opinions/all` for callers who want both in one page.

Named "advisory-opinions", not "opinions": `/api/v1/opinions` already serves the PARLIAMENT's
committee opinions on legislative files, an unrelated thing. An `/advisory-opinions/all` that excluded
those would have been the plainest kind of inconsistency, promising everything and serving two
kinds out of three.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session, defer

from api.v1._pagination import stable
from core.database import get_db
from models.opinion import EuCorOpinion, EuEescOpinion
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

router = APIRouter(prefix="/advisory-opinions", tags=["v1-advisory-opinions"])

_BODIES = {"eesc": EuEescOpinion, "cor": EuCorOpinion}
_BODY_NAME = {"eesc": "European Economic and Social Committee",
              "cor": "European Committee of the Regions"}


class OpinionItem(BaseModel):
    id: int = Field(..., description="The opinion's own primary key WITHIN its committee. "
                                     "Not unique across committees: pair it with `body_code`, "
                                     "or just follow `self`.")
    body_code: Literal["eesc", "cor"] = Field(..., description="Which committee adopted it.")
    body_name: str
    celex: Optional[str] = Field(None, description="CELEX of the opinion, when it has one.")
    title: Optional[str] = None
    public_url: Optional[str] = Field(None, description="The committee's own page when we have "
                                                        "one, otherwise the EUR-Lex record.")
    body_txt: Optional[str] = Field(None, description="The whole opinion as text. Null on the "
                                                      "list unless `include_body=true`.")
    body_html: Optional[str] = Field(None, description="The whole opinion as HTML. Same rule.")
    document_date: Optional[date] = Field(None, description="The date the committee states. "
                                                            "Null when it states none; never "
                                                            "filled with the date Brubru "
                                                            "captured the opinion.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested it.")
    adopted_date: Optional[date] = None
    rapporteur: Optional[str] = None
    session_label: Optional[str] = None
    own_initiative: Optional[bool] = Field(None, description="True when the committee wrote it "
                                                             "on its own initiative rather than "
                                                             "on referral.")
    related_celex: Optional[str] = Field(None, description="The act the opinion is about.")
    self: Optional[str] = None


def _public_url(row) -> Optional[str]:
    own = getattr(row, "eesc_url", None) or getattr(row, "cor_url", None)
    return own or row.eurlex_url


def _to_item(row, body_code: str, base_url: str = "", with_body: bool = False) -> OpinionItem:
    return OpinionItem(
        id=row.id,
        body_code=body_code,
        body_name=_BODY_NAME[body_code],
        celex=row.celex,
        title=row.title,
        public_url=_public_url(row),
        body_txt=row.body_text if with_body else None,
        body_html=row.body_html if with_body else None,
        document_date=row.document_date,
        creation_date=row.created_at,
        adopted_date=row.adopted_date,
        rapporteur=row.rapporteur,
        session_label=row.session_label,
        own_initiative=row.own_initiative,
        related_celex=row.related_celex,
        self=f"{base_url.rstrip('/')}/{body_code}/{row.id}" if base_url else None,
    )


def _filtered(db: Session, model, q, published_from, published_to, has_body, related_celex,
              with_body: bool = False):
    # Leave the bodies in the database unless the caller asked for them. These opinions average
    # over 20,000 characters, so loading them to throw away is megabytes per page: page 47 of
    # the union pulled thousands of full opinions out of Postgres to serve a list of titles.
    query = db.query(model)
    if not with_body:
        query = query.options(defer(model.body_text), defer(model.body_html))
    if q:
        query = query.filter(model.title.ilike(f"%{q}%"))
    if published_from:
        query = query.filter(model.document_date >= published_from)
    if published_to:
        query = query.filter(model.document_date <= published_to)
    if related_celex:
        query = query.filter(model.related_celex == related_celex)
    if has_body is True:
        query = query.filter(model.body_text.isnot(None))
    elif has_body is False:
        query = query.filter(model.body_text.is_(None))
    return query


_INPUT_DOC = """
**Input**
- `q` — substring search over the title.
- `from` / `to` (YYYY-MM-DD) — bound on `document_date`.
- `related_celex` — only opinions about that act.
- `has_body` — true for opinions whose full text we hold, false for those we do not.
- `include_body` — return `body_txt` and `body_html` in the list. Off by default: these
  opinions average over 20,000 characters, so a page of 100 with bodies is several megabytes.
- `limit` (default 25, max 100), `page` (1-indexed).
"""

_FRESHNESS_DOC = """
**How this differs from `/eesc/opinions` and `/cor/opinions`**
Those read the committees' own websites through Brubru's economy store and hold 97 EESC and
78 CoR items, useful for what the committees are publishing right now. This reads the
Publications Office register: 3,617 EESC and 1,091 CoR opinions with the adopted text. For
the full record, or for any opinion older than the websites keep, use this one.

**Data freshness**
Ingested from CellarIngested from Cellar and refreshed daily; the full text is fetched separately, so a very
recent opinion can appear with `has_body=false` for a day. `document_date` is the date the
committee states and is null when it states none.
"""


@router.get(
    "/all",
    response_model=PaginatedResponse[OpinionItem],
    summary="Opinions of both EU advisory committees",
    description=f"""**What it does**
Returns the opinions of the European Economic and Social Committee and the European Committee
of the Regions in one feed, newest first, with the whole text on request.

**When to use it**
When you want both committees in one call: "what have the advisory committees said about this
act", or a daily sweep of new opinions. Use `/advisory-opinions/eesc` or `/advisory-opinions/cor` for one.
{_INPUT_DOC}- `body` — `eesc`, `cor`, or omit for both.

**Try it**
```
GET /api/v1/advisory-opinions/all?limit=5
GET /api/v1/advisory-opinions/all?body=cor&from=2026-01-01
GET /api/v1/advisory-opinions/all?related_celex=52021PC0206&include_body=true
```

**You get back**
A paginated envelope. Each item carries the five datapoints, `body_code` and `body_name`
saying which committee adopted it, the rapporteur and session, `own_initiative`, and `self`
— the URL for that one opinion. `id` is the opinion's key WITHIN its committee and is not
unique across the two, so pair it with `body_code` or just follow `self`.
{_FRESHNESS_DOC}""")
async def list_all_opinions(
    request: Request,
    body: Optional[Literal["eesc", "cor"]] = Query(None, description="Restrict to one committee."),
    q: Optional[str] = Query(None),
    from_: Optional[date] = Query(None, alias="from"),
    to: Optional[date] = Query(None),
    related_celex: Optional[str] = Query(None),
    has_body: Optional[bool] = Query(None),
    include_body: bool = Query(False),
    limit: int = Query(25, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[OpinionItem]:
    codes = [body] if body else ["eesc", "cor"]
    base = str(request.url).split("/all")[0]

    # A SQL union, not a Python merge. Merging meant fetching page*limit rows from EACH table
    # and sorting them here: correct, but page 47 took 9.3 seconds, and GovClipping page deep.
    # The database slices 100 rows instead. The ORDER BY ends on (body_code, id), which is a
    # TOTAL order, so no row is served twice or skipped -- the same rule as stable().
    body_cols = ("body_text, body_html" if include_body else "NULL::text, NULL::text")
    selects, params = [], {"limit": limit, "offset": (page - 1) * limit}
    for code in codes:
        table = f"eu_{code}_opinions"
        own_url = "eesc_url" if code == "eesc" else "cor_url"
        where = ["TRUE"]
        if q:
            where.append(f"title ILIKE :q_{code}"); params[f"q_{code}"] = f"%{q}%"
        if from_:
            where.append(f"document_date >= :from_{code}"); params[f"from_{code}"] = from_
        if to:
            where.append(f"document_date <= :to_{code}"); params[f"to_{code}"] = to
        if related_celex:
            where.append(f"related_celex = :celex_{code}"); params[f"celex_{code}"] = related_celex
        if has_body is True:
            where.append("body_text IS NOT NULL")
        elif has_body is False:
            where.append("body_text IS NULL")
        selects.append(
            f"SELECT '{code}' AS body_code, id, celex, title, "
            f"       coalesce({own_url}, eurlex_url) AS public_url, {body_cols}, "
            f"       document_date, created_at, adopted_date, rapporteur, session_label, "
            f"       own_initiative, related_celex "
            f"FROM {table} WHERE {' AND '.join(where)}")

    union = " UNION ALL ".join(selects)
    total = db.execute(sa_text(f"SELECT count(*) FROM ({union}) u"), params).scalar() or 0
    rows = db.execute(sa_text(
        f"SELECT * FROM ({union}) u "
        "ORDER BY document_date DESC NULLS LAST, body_code, id DESC "
        "LIMIT :limit OFFSET :offset"), params).mappings().all()

    items = [OpinionItem(
        id=r["id"], body_code=r["body_code"], body_name=_BODY_NAME[r["body_code"]],
        celex=r["celex"], title=r["title"], public_url=r["public_url"],
        body_txt=r["body_text"] if include_body else None,
        body_html=r["body_html"] if include_body else None,
        document_date=r["document_date"], creation_date=r["created_at"],
        adopted_date=r["adopted_date"], rapporteur=r["rapporteur"],
        session_label=r["session_label"], own_initiative=r["own_initiative"],
        related_celex=r["related_celex"],
        self=f"{base.rstrip('/')}/{r['body_code']}/{r['id']}") for r in rows]

    return build_envelope(
        items, total=total, page=page, limit=limit,
        op_core_title="EU advisory committee opinions", op_core_type="EU opinion",
        op_core_identifier=str(request.url))


def _make_list_route(code: str):
    model = _BODIES[code]
    name = _BODY_NAME[code]

    @router.get(
        f"/{code}",
        response_model=PaginatedResponse[OpinionItem],
        summary=f"Opinions of the {name}",
        description=f"""**What it does**
Returns the opinions of the {name}, newest first, with the whole text on request.

**When to use it**
When you want this committee only. `/advisory-opinions/all` returns both committees in one feed.
{_INPUT_DOC}
**Try it**
```
GET /api/v1/advisory-opinions/{code}?limit=5
GET /api/v1/advisory-opinions/{code}?q=artificial+intelligence&include_body=true
```

**You get back**
A paginated envelope of opinions, each with the five datapoints, the rapporteur and session,
`own_initiative`, `related_celex` (the act it is about) and `self`.
{_FRESHNESS_DOC}""")
    async def _list(
        request: Request,
        q: Optional[str] = Query(None),
        from_: Optional[date] = Query(None, alias="from"),
        to: Optional[date] = Query(None),
        related_celex: Optional[str] = Query(None),
        has_body: Optional[bool] = Query(None),
        include_body: bool = Query(False),
        limit: int = Query(25, ge=1, le=100),
        page: int = Query(1, ge=1),
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> PaginatedResponse[OpinionItem]:
        query = _filtered(db, model, q, from_, to, has_body, related_celex, include_body)
        total = query.count()
        rows = (stable(query.order_by(model.document_date.desc().nullslast()))
                .offset((page - 1) * limit).limit(limit).all())
        base = str(request.url).split(f"/{code}")[0]
        return build_envelope(
            [_to_item(row, code, base, include_body) for row in rows],
            total=total, page=page, limit=limit,
            op_core_title=f"{name} opinions", op_core_type="EU opinion",
            op_core_identifier=str(request.url))

    @router.get(
        f"/{code}/{{item_id}}",
        response_model=OpinionItem,
        summary=f"One {name} opinion by id",
        description=f"""**What it does**
Returns one {name} opinion, always with its whole text.

**When to use it**
After a list call, to read the opinion itself. `include_body` is not needed here: the item
route always carries `body_txt` and `body_html`.

**Input**
- `item_id` — the `id` from a list call (this committee's own key).

**Try it**
```
GET /api/v1/advisory-opinions/{code}/1
```

**You get back**
One opinion with the five datapoints filled. 404 with `reason_code: not_found` if there is no
such opinion.
{_FRESHNESS_DOC}""")
    async def _item(
        item_id: int,
        request: Request,
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> OpinionItem:
        row = db.query(model).filter(model.id == item_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail={
                "reason_code": "not_found",
                "message": f"No {code.upper()} opinion with id {item_id}"})
        base = str(request.url).split(f"/{code}/")[0]
        return _to_item(row, code, base, with_body=True)

    return _list, _item


for _code in ("eesc", "cor"):
    _make_list_route(_code)
