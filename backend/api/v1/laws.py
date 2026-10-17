"""
/api/v1/laws — EU legislation from the eu_laws corpus (28,500+ laws).

Wraps the TSVECTOR-backed eu_laws table with canonical filters:
    celex, doc_type, policy_area, q (full-text), published_from, published_to.
"""

import logging
import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from api.v1._date_bounds import UpperBoundDatetime
from pydantic import BaseModel, Field
from sqlalchemy import and_, any_, case, func, literal, or_, text
from sqlalchemy.orm import Session, defer

from core.database import get_db
from models.eu_law import EULaw
from models.user import User
from services.celex_types import SECTORS, celex_info, type_codes_for

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope
from api.v1._pagination import stable
from ._row_dates import row_updated
from ._change_window import validate_window

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/laws", tags=["v1-laws"])


class EuroVocTerm(BaseModel):
    id: str = Field(..., description="EuroVoc concept id, the last segment of `uri` (e.g. `3030`).")
    uri: str = Field(..., description="The concept on the EuroVoc thesaurus, e.g. http://eurovoc.europa.eu/3030.")
    label: Optional[str] = Field(None, description="English preferred label, e.g. `artificial intelligence`.")
    domain: Optional[str] = Field(None, description="The EuroVoc domain the concept sits in, e.g. `64 PRODUCTION, TECHNOLOGY AND RESEARCH`.")


class LawItem(BaseModel):
    id: Optional[int] = Field(
        None,
        description=(
            "Brubru's own permanent row id. Use this to recognise a law across syncs: it "
            "never changes, whereas `celex` can be corrected. GovClipping reported on "
            "25 Sep 2026 that a corrected CELEX reads to them as a brand new record, "
            "because this id was not exposed."
        ),
    )
    self: Optional[str] = Field(
        None,
        alias="self",
        description=(
            "The URL of this item on this API. Follow it rather than building a URL: "
            "it is escaped, and it keys on whatever this collection's item route takes. "
            "STABLE for the life of the record, because it is built from `id` when the "
            "row has no CELEX and from `celex` otherwise, and `id` never changes. A "
            "corrected CELEX changes this URL; `id` is the key to store."
        ),
    )
    celex: Optional[str] = None
    title: Optional[str] = None
    doc_type: Optional[str] = None
    adopted_on: Optional[date] = Field(None, description="Adoption / publication date")
    oj_reference: Optional[str] = Field(None, description=(
        "The Official Journal citation, as the acts cite each other (read from the Publications Office's Cellar): "
        "`OJ L 119, 4.5.2016, p. 1` for an act published in an issue (until 30 September 2023), "
        "`OJ L, 2025/40, 22.1.2025` for an act published act by act (since 1 October 2023), "
        "`OJ 56, 4.4.1964, p. 850` before 1968, when the Journal had no L and C series."))
    # What the CELEX itself states, read from the string (the EUR-Lex tables "CELEX numbers" and "Types of documents").
    sector: Optional[str] = Field(None, description="CELEX sector, the first character: `3` (legal acts) for every law here, the only sector this corpus holds.")
    sector_name: Optional[str] = Field(None, description="The sector's name in EUR-Lex, e.g. `Legal acts`.")
    year: Optional[int] = Field(None, description="The year in the CELEX (e.g. 2024 for `32024R1689`): the year the act's number belongs to.")
    number: Optional[int] = Field(None, description="The number in the CELEX (e.g. 1689 for `32024R1689`): for most acts the act's own number; for some types (opinions and agreements filed by date, e.g. `32016A0817(01)`) a date.")
    document_type_code: Optional[str] = Field(None, description="The CELEX descriptor letter(s), e.g. `R`, `L`, `D`, `PC`.")
    document_type: Optional[str] = Field(None, description="What the descriptor means in EUR-Lex's own table, e.g. `Regulation`, `Directive`, `CFSP act (common position, joint action, common strategy)`. `doc_type` above is Brubru's normalised family; this is the Publications Office's label.")
    corrected_act: Optional[str] = Field(None, description="For a corrigendum (`R(01)` suffix): the CELEX of the act it corrects. Null for every other document.")
    # Brubru's curated names (migration 301).
    alias: Optional[str] = Field(None, description="The law's common name, e.g. `General Data Protection Regulation`, from Brubru's curated list (17 laws on 16 Oct 2026), never derived. To find a law by name, `q` also matches these names and titles.")
    acronym: Optional[str] = Field(None, description="The acronym of the alias, e.g. `GDPR`, from the same curated list.")
    # The Publications Office's metadata for the law (migrations 301 and 302).
    authors: list[str] = Field(default_factory=list, description="The bodies that created the act, as Publications Office corporate-body codes: `COM` Commission, `CONSIL` Council, `EP` European Parliament, or a Commission department such as `SANTE`.")
    in_force: Optional[bool] = Field(None, description="The Publications Office's in-force flag, refreshed daily from Cellar. `false` means not in force on the last check: either not yet (see `entry_into_force`) or no longer. Null when the Publications Office carries no flag (corrigenda among others): unknown, not false.")
    eli: Optional[str] = Field(None, description="The act's European Legislation Identifier (ELI) URI as the metadata states it on the work, e.g. `http://data.europa.eu/eli/reg/2024/1689/oj`. Null when it states none.")
    entry_into_force: list[date] = Field(default_factory=list, description="The dates the metadata types as entry into force (or leaves untyped), e.g. the AI Act: 2024-08-01.")
    application_dates: list[date] = Field(default_factory=list, description="The dates from which the act, or part of it, applies, e.g. the AI Act: 2025-02-02, 2025-08-02, 2026-08-02, 2027-08-02. Served as the Publications Office states them, its own errors included (the DSA's 2022-02-17 should read 2024-02-17).")
    effect_dates: list[date] = Field(default_factory=list, description="The dates of effect the metadata states (often a retroactive date).")
    procedures: list[str] = Field(default_factory=list, description="The interinstitutional procedure numbers the act came from, as `YYYY/NNNN` (the Legislative Observatory reference without its type, e.g. `2021/0106`, or `2011/0901A`): the export's links, Cellar's and Brubru's Legislative Observatory data together.")
    policy_area: Optional[str] = Field(
        None,
        description=(
            "The act's EuroVoc domain (e.g. `10 EUROPEAN UNION`): the domain most of its "
            "`eurovoc` descriptors belong to, ties going to the lowest domain number. "
            "`72 GEOGRAPHY` is chosen only when it is the act's sole domain. Null "
            "while the Publications Office has not indexed the act yet."
        ),
    )
    eurovoc: list[EuroVocTerm] = Field(
        default_factory=list,
        description=(
            "The EuroVoc descriptors the Publications Office assigned to the act, read from "
            "Cellar. Empty while the act is not indexed yet (new acts lag a few weeks)."
        ),
    )
    legal_basis: list = Field(default_factory=list)
    eurlex_url: Optional[str] = None
    text_url: Optional[str] = Field(None, description="Brubru endpoint for the full body (XML or plain text). Call this URL to retrieve the actual law content.")
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of eurlex_url).")
    body_txt: Optional[str] = Field(None, description="Plain text of the act, stored from Cellar. Pass include_body=false to omit it.")
    body_html: Optional[str] = Field(None, description="XHTML of the act, stored from Cellar. Pass include_body=false to omit it.")
    document_date: Optional[date] = Field(None, description="Adoption / publication date (alias of adopted_on).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this CELEX (eu_laws.created_at).")
    updated_date: Optional[datetime] = Field(None, description="When this record last changed, for incremental sync. Null when the source table keeps no change signal.")


def _policy_area_filter(value: str):
    """Match the EuroVoc domain by number (`52`), full label (`52 ENVIRONMENT`) or name
    (`environment`, `agri-foodstuffs`), case-insensitively."""
    v = value.strip()
    if v.isdigit():
        return EULaw.eurovoc_domain.like(f"{v.zfill(2)} %")
    name = re.sub(r"^\d+\s+", "", v).replace("_", " ")
    return func.regexp_replace(EULaw.eurovoc_domain, r"^\d+ ", "").ilike(name)


def _bad_filter(name: str, value, expected: str):
    return HTTPException(status_code=422, detail={
        "error": f"Invalid {name}={value!r}: expected {expected}.", "reason_code": "invalid_filter"})


def metadata_filters(sector=None, year=None, number=None, document_type=None, alias=None, author=None,
                     in_force=None, procedure=None, corrects=None) -> list:
    """SQL filters for the CELEX parts and the export metadata (16 Oct 2026). One builder for v1 and v2, so the two
    routes cannot filter differently. CELEX parts are matched on the CELEX string itself, the way they are served."""
    fs = []
    if sector:
        s = sector.strip().upper()
        if s not in SECTORS:
            raise _bad_filter("sector", sector, "one of " + ", ".join(SECTORS))
        fs.append(EULaw.celex.like(f"{s}%"))
    if year is not None:
        fs.append(func.substr(EULaw.celex, 2, 4) == f"{year:04d}")
    if number is not None:
        fs.append(EULaw.celex.op("~")(rf"^[0-9CE][0-9]{{4}}[A-Z]{{1,3}}0*{number}([^0-9]|$)"))
    if document_type:
        pairs = type_codes_for(document_type)
        if not pairs:
            raise _bad_filter("document_type", document_type, "a CELEX descriptor (R, L, D, E...) or its EUR-Lex label (regulation, directive...)")
        fs.append(or_(*[EULaw.celex.op("~")(rf"^{s or '[0-9CE]'}[0-9]{{4}}{t}[0-9]") for s, t in pairs]))
    if alias:
        v = alias.strip().lower()
        fs.append(or_(func.lower(EULaw.alias) == v, func.lower(EULaw.acronym) == v))
    if author:
        fs.append(literal(author.strip().upper()) == any_(EULaw.authors))  # the model's generic ARRAY has no .contains()
    if in_force is not None:
        fs.append(EULaw.in_force.is_(in_force))
    if procedure:
        m = re.fullmatch(r"\s*(\d{4})\s*/\s*0*(\d{1,4})([A-Za-z]?)\s*(?:\([A-Za-z]{3}\))?\s*", procedure)
        if not m:
            raise _bad_filter("procedure", procedure, "YYYY/NNNN, e.g. 2021/0106, 2021/0106(COD) or 2011/0901A")
        fs.append(literal(f"{m[1]}/{int(m[2]):04d}{m[3].upper()}") == any_(EULaw.procedures))
    if corrects:
        c = corrects.strip().upper()
        if not re.fullmatch(r"[0-9CE][0-9]{4}[A-Z]{1,3}[0-9]{4,6}(\([0-9]{2}\))?", c):  # also keeps LIKE wildcards out
            raise _bad_filter("corrects", corrects, "a CELEX such as 32006R1907")
        fs.append(EULaw.celex.like(f"{c}R(%"))
    return fs


def _eurlex_url(celex: Optional[str]) -> Optional[str]:
    if not celex:
        return None
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def _law_item(r, include_body: bool = True) -> "LawItem":
    """One row as a LawItem. Shared so the row-id path and the CELEX path cannot drift.

    The body used to be null here, with the list telling callers to fetch
    /laws/{celex}/text instead. That route reads the act live from Cellar, so a
    100-row page would have meant 100 live fetches; the text is now stored
    (migration 269) and served straight from the row.

    include_body=false stays available because a caller paging the whole corpus for
    metadata should not have to carry roughly 41 KB of XHTML per row to get it.
    """
    return LawItem(
        id=r.id,
        celex=r.celex,
        title=r.title,
        doc_type=r.doc_type_normalized or r.doc_type,
        adopted_on=r.date,
        oj_reference=r.oj_reference,
        **celex_info(r.celex),
        alias=getattr(r, "alias", None),
        acronym=getattr(r, "acronym", None),
        authors=list(getattr(r, "authors", None) or []),
        in_force=getattr(r, "in_force", None),
        eli=getattr(r, "eli", None),
        entry_into_force=list(getattr(r, "entry_into_force", None) or []),
        application_dates=list(getattr(r, "application_dates", None) or []),
        effect_dates=list(getattr(r, "effect_dates", None) or []),
        procedures=list(getattr(r, "procedures", None) or []),
        # EuroVoc as the Publications Office indexed it (migration 276), never Brubru's
        # classifier, which put the decision electing the European Ombudsman under "Energy".
        policy_area=getattr(r, "eurovoc_domain", None),
        eurovoc=list(getattr(r, "eurovoc", None) or []),
        legal_basis=list(r.legal_basis or []),
        eurlex_url=_eurlex_url(r.celex),
        text_url=f"/api/v1/laws/{r.celex}/text" if r.celex else None,
        public_url=_eurlex_url(r.celex),
        body_txt=getattr(r, "body_txt", None) if include_body else None,
        body_html=getattr(r, "body_html", None) if include_body else None,
        document_date=r.date,
        creation_date=r.created_at,
        updated_date=row_updated(r),
    )


@router.get(
    "",
    response_model=PaginatedResponse[LawItem],
    summary="Search adopted EU legislation — 27,103 distinct laws across 30,246 OJ publications with full text",
    description="""**What it does**
Full-text search over Brubru's mirror of adopted EU legislation — the LEG_2026-10 bulk export from the Publications Office, covering 27,103 distinct laws across 30,246 Official Journal publications with full text. Each row carries the EU's legal identifier, the document type (regulation / directive / decision / recommendation / opinion / communication / agreement), the title + subject matter, the policy area, the publication date, the CELEX number, and a link to the EUR-Lex canonical URL.

**When to use it**
The single highest-traffic Brubru endpoint — used to find specific acts (e.g. "the AI Act"), enumerate laws by topic (e.g. all environment regulations from 2024), or build a partner integration that needs the live adopted-legislation corpus. Pair with `/api/v1/laws/{celex}/text` for the full legal text body. For procedures still in negotiation, use `/api/v1/procedures` instead.

**Input**
- `q` — full-text search on title + subject matter (PostgreSQL TSVECTOR).
- `celex` — exact match on the legal identifier (the CELEX number).
- `doc_type` — `regulation` / `directive` / `decision` / `recommendation` / `opinion` / etc. See `/api/v1/document-types` for the live distinct list.
- `policy_area` — EuroVoc domain, by number (`52`), label (`52 ENVIRONMENT`) or name (`environment`).
- `include_body` — default true; false pages the corpus for metadata only.
- `published_from`, `published_to` — date filter on `published_date`.
- `updated_from`, `updated_to` — when the law's record last changed (incremental sync).
- `created_from`, `created_to` — when Brubru first stored the law (`creation_date`); a bare date as `created_to` covers the whole day.
- `sector`, `year`, `number`, `document_type`: the parts of the CELEX. Every law here is a legal act, CELEX sector `3`. `sector=3&year=2024&document_type=R` lists 2024 regulations; `document_type` takes the descriptor (`R`, `L`, `D`, `H`...) or its EUR-Lex label (`regulation`). A corrigendum carries its act's descriptor, so `document_type=R` lists the corrections of regulations too (`corrected_act` names their act).
- `alias`: a name or acronym from Brubru's curated list (`GDPR`, `Digital Services Act`), exact and case-insensitive; the list is short, so search by name with `q`.
- `author`: creating body (`COM`, `CONSIL`, `EP`, `SANTE`...). `in_force`: `true` or `false` (false: not yet or no longer in force). `procedure`: `2021/0106` (a type such as `(COD)` and a trailing letter are accepted). `corrects`: a CELEX, returns its corrigenda.
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/laws?q=AI%20Act&limit=10
GET /api/v1/laws?doc_type=regulation&policy_area=environment&published_from=2024-01-01
GET /api/v1/laws?sector=3&year=2024&document_type=R&in_force=true&include_body=false
GET /api/v1/laws?alias=GDPR
GET /api/v1/laws?corrects=32016R0679
```

**You get back**
A `PaginatedResponse[LawItem]` envelope. Each item carries `id`, `celex`, `title`, `doc_type`, `adopted_on`, `oj_reference` (the Official Journal citation as the acts cite it: `OJ L 119, 4.5.2016, p. 1`, or `OJ L, 2025/40, 22.1.2025` since 1 October 2023); what the CELEX states: `sector`, `sector_name`, `year`, `number`, `document_type_code`, `document_type` (EUR-Lex's label), `corrected_act` (for a corrigendum); Brubru's curated `alias` and `acronym`; the Publications Office's metadata: `authors[]`, `in_force`, `eli`, `entry_into_force[]`, `application_dates[]`, `effect_dates[]`, `procedures[]`; then `policy_area` (the EuroVoc domain), `eurovoc[]` (the act's EuroVoc descriptors, as the Publications Office indexed it), `legal_basis[]`, `eurlex_url`, `text_url`, `body_txt` and `body_html` (the act's text, stored from Cellar; `include_body=false` omits them), plus the 5 envelope-level datapoints.

`doc_type` is Brubru's normalised family (from the document's own heading); `document_type` is the official label of the CELEX descriptor. They agree on nearly every law; where a CELEX letter and a heading differ (an act headed "Decision" filed under another descriptor), filter on the one you mean.

The metadata comes from the LEG_2026-10 export (11 Oct 2026) for the laws it holds and from Cellar for the others (16 Oct 2026); procedures also from Brubru's Legislative Observatory data. `in_force` is refreshed daily from Cellar and is null where the Publications Office carries no flag. Dates are split by the type the Publications Office gives them and served as it states them; its placeholder dates are left out. Acts the daily Official Journal sync adds later (every sector-3 act of the OJ L series with an English text; a corrigendum of another language version only is not in this English corpus) carry the CELEX parts and this metadata from the day they are added; a field the Publications Office publishes later is filled then (any empty field within a week of the act's addition, the authors and ELI within 30 days), without moving `updated_date`, and `in_force` is checked daily.

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from EUR-Lex RSS feeds + Cellar SPARQL sector-3 (secondary acts). New regulations + directives published in the Official Journal L-series appear in our mirror within the same day they hit EUR-Lex.""",
)
async def list_laws(
    request: Request,
    q: Optional[str] = Query(None, description="Full-text search (title + subject matter)"),
    celex: Optional[str] = Query(None, description="Exact CELEX filter"),
    doc_type: Optional[str] = Query(None, description="Document type (Regulation, Directive, Decision, ...)"),
    policy_area: Optional[str] = Query(None, description="EuroVoc domain: number (52), label (52 ENVIRONMENT) or name (environment)"),
    published_from: Optional[date] = Query(None, description="Lower bound — laws with adoption date >= value (YYYY-MM-DD)"),
    published_to: Optional[date] = Query(None, description="Upper bound — laws with adoption date <= value (YYYY-MM-DD). Preferred name."),
    published_end: Optional[date] = Query(None, description="Alias of published_to for GovClipping compatibility. If both are sent with different values, returns 422."),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync lower bound — rows with updated_at >= value. Returns rows ordered by updated_at desc when set."),
    updated_to: Optional[UpperBoundDatetime] = Query(None, description="Incremental sync upper bound — rows with updated_at <= value."),
    updated_end: Optional[UpperBoundDatetime] = Query(None, description="Alias of updated_to (GovClipping-compatible). 422 if both differ."),
    created_from: Optional[datetime] = Query(None, description="First stored by Brubru on or after (ISO date or datetime; UTC when no zone). Matches `creation_date`."),
    created_to: Optional[UpperBoundDatetime] = Query(None, description="First stored by Brubru on or before; a bare date covers the whole day."),
    include_orphans: bool = Query(False, description="Include rows that have no CELEX (orphaned annexes / recitals from Formex parsing). Default false — they have no useful identifier and produce all-null rows."),
    include_body: bool = Query(
        True,
        description="Include body_txt and body_html. Pass false to page the corpus "
                    "for metadata without carrying ~41 KB of XHTML per row.",
    ),
    sector: Optional[str] = Query(None, description="CELEX sector: `3`, legal acts, the only sector this corpus holds (another sector returns no law)."),
    year: Optional[int] = Query(None, ge=1900, le=2100, description="The year in the CELEX (e.g. 2024)"),
    number: Optional[int] = Query(None, ge=1, description="The number in the CELEX (e.g. 1689 for the AI Act)"),
    document_type: Optional[str] = Query(None, description="CELEX descriptor (R, L, D, E...) or its EUR-Lex label (regulation, directive, ...)"),
    alias: Optional[str] = Query(None, description="Common name or acronym, exact and case-insensitive (GDPR, Digital Services Act)"),
    author: Optional[str] = Query(None, description="Creating body, Publications Office code: COM, CONSIL, EP, or a department such as SANTE"),
    in_force: Optional[bool] = Query(None, description="true: in force per the metadata; false: not in force. Laws whose metadata carries no flag match neither."),
    procedure: Optional[str] = Query(None, description="Interinstitutional procedure number, YYYY/NNNN (2021/0106 or 2021/0106(COD))"),
    corrects: Optional[str] = Query(None, description="A CELEX: returns the corrigenda of that act"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LawItem]:
    # published_end is an alias of published_to (GovClipping-compatible).
    # If both are passed with different values, reject with 422.
    if published_end and published_to and published_end != published_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Conflicting upper-bound parameters: published_to={published_to} and published_end={published_end}. They are aliases of the same bound; pass only one, or pass matching values.",
                "reason_code": "conflicting_params",
            },
        )
    if published_end and not published_to:
        published_to = published_end

    if published_from and published_to and published_from > published_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Invalid date range: published_from={published_from} is after published_to={published_to}.",
                "reason_code": "invalid_date_range",
            },
        )

    if updated_end and updated_to and updated_end != updated_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Conflicting upper-bound parameters: updated_to={updated_to} and updated_end={updated_end}.",
                "reason_code": "conflicting_params",
            },
        )
    if updated_end and not updated_to:
        updated_to = updated_end
    if updated_from and updated_to and updated_from > updated_to:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Invalid date range: updated_from={updated_from} is after updated_to={updated_to}.",
                "reason_code": "invalid_date_range",
            },
        )

    # created_ was silently ignored until 7 Oct 2026: the list returned all 19,136 laws.
    created = validate_window(created_from, created_to)

    query = db.query(EULaw)

    filters = []
    # Default: hide rows that have no CELEX. These are mostly orphaned annexes
    # / recitals from older Formex parses where the parser failed to bind the
    # part to its parent. Surfacing them produces all-null /laws rows that
    # confuse partners. Pass include_orphans=true to opt back in.
    if not include_orphans:
        filters.append(and_(EULaw.celex.isnot(None), EULaw.celex != ""))
    if celex:
        filters.append(EULaw.celex == celex.upper())
    if doc_type:
        filters.append(func.lower(EULaw.doc_type_normalized) == doc_type.lower())
    if policy_area:
        filters.append(_policy_area_filter(policy_area))
    if published_from:
        filters.append(EULaw.date >= published_from)
    if published_to:
        filters.append(EULaw.date <= published_to)
    if updated_from:
        filters.append(EULaw.updated_at >= updated_from)
    if updated_to:
        filters.append(EULaw.updated_at <= updated_to)
    if created["created_from"]:
        filters.append(EULaw.created_at >= created["created_from"])
    if created["created_to"]:
        filters.append(EULaw.created_at <= created["created_to"])
    filters += metadata_filters(sector, year, number, document_type, alias, author, in_force, procedure, corrects)

    ts_query = None
    alias_celexes: list[str] = []
    if q:
        # Full-text match OR title ILIKE, plus any law-nickname alias (GDPR,
        # AI Act, DSA, ...) resolved to its CELEX, so common-name searches recall
        # the flagship act even when its title uses the formal long form.
        ts_query = func.plainto_tsquery("english", q)
        try:
            from services.parsers.law_alias_resolver import find_alias_matches
            alias_celexes = [m.celex for m in find_alias_matches(q) if getattr(m, "celex", None)]
        except Exception:
            alias_celexes = []
        text_match = or_(
            EULaw.search_vector.op("@@")(ts_query),
            EULaw.title.ilike(f"%{q}%"),
        )
        if alias_celexes:
            filters.append(or_(text_match, EULaw.celex.in_(alias_celexes)))
        else:
            filters.append(text_match)

    if filters:
        query = query.filter(and_(*filters))

    total = query.count()
    # Ordering: for a text search, rank by RELEVANCE (alias-matched flagship acts
    # first, then full-text rank), not by date — otherwise recent minor acts that
    # loosely match bury the flagship law. For incremental sync, newest-updated
    # first. Otherwise, most-recent adoption date.
    if q is not None and ts_query is not None:
        order_cols = []
        if alias_celexes:
            order_cols.append(case((EULaw.celex.in_(alias_celexes), 0), else_=1))
        # Prefer the canonical act over annexes / joint declarations that share
        # its CELEX: the canonical row's title starts with its own doc-type word
        # (e.g. "Regulation ..."), the same heuristic get_law_detail uses.
        order_cols.append(
            case(
                (func.lower(EULaw.title).like(
                    func.lower(func.coalesce(EULaw.doc_type_normalized, "zzzznomatch")).concat("%")
                ), 0),
                else_=1,
            )
        )
        order_cols.append(func.ts_rank(EULaw.search_vector, ts_query).desc())
        order_cols.append(EULaw.date.desc().nullslast())
        query = query.order_by(*order_cols)
    elif updated_from or updated_to:
        query = query.order_by(EULaw.updated_at.desc().nullslast())
    elif created_from or created_to:
        query = query.order_by(EULaw.created_at.desc().nullslast())
    else:
        query = query.order_by(EULaw.date.desc().nullslast())
    if not include_body:
        # The bodies are 103 KB of a 107 KB row: without this, include_body=false blanked them
        # only after the database had sent them (17 Oct 2026, Supabase egress over quota; a
        # metadata walk of the corpus moved 3.4 GB). raiseload: a later read fails loudly
        # instead of fetching each row's text again behind the caller's back.
        query = query.options(defer(EULaw.body_html, raiseload=True), defer(EULaw.body_txt, raiseload=True))
    rows = (
        stable(query).offset((page - 1) * limit)
        .limit(limit)
        .all()
    )

    # One builder for list and item alike: this list kept its own copy of the
    # LawItem construction, which is exactly how the two drift apart.
    data = [_law_item(r, include_body=include_body) for r in rows]

    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        published_from=published_from,
        published_to=published_to,
        updated_from=updated_from,
        updated_to=updated_to,
        # Phase 3 — OP Core Metadata enrichment.
        op_core_title="EU legislation listing",
        op_core_type="EU legislation",
        op_core_identifier=str(request.url),
        op_core_referenced_by=[
            "https://brubru.beresol.eu/api/v1/discover/cellar/recent",
            "https://brubru.beresol.eu/api/v1/discover/cellar/celex/{celex}/relationships",
            "https://brubru.beresol.eu/api/v1/vocabularies/modification-types",
        ],
    )


@router.get(
    "/{celex}",
    response_model=LawItem,
    summary="Look up one adopted EU law by its legal identifier",
    description="""**What it does**
Returns one adopted EU law identified by its CELEX (the EU's stable legal identifier, e.g. `32024R1689` for the AI Act): its metadata and its stored text (`body_txt`, `body_html`), the same item the list returns.

**When to use it**
To read one law by its identifier. The item carries the stored text when Brubru has fetched it from Cellar (null while the act waits in the fetch queue); `/api/v1/laws/{celex}/text` reads the text live from Cellar instead.

**Input**
- `celex` (path) — the EU legal identifier. Case-insensitive; we uppercase internally. Format: 5 digits + 1-2 letters + 4 digits (e.g. `32024R1689`, `52026PC0321`).

**Try it**
```
GET /api/v1/laws/32024R1689
GET /api/v1/laws/32016R0679
```

**You get back**
A `LawItem` with `celex`, `title`, `doc_type` (normalised), `adopted_on`, `oj_reference`, what the CELEX states (`sector`, `year`, `number`, `document_type`, `corrected_act`...), `alias` and `acronym`, the Publications Office's metadata (`authors[]`, `in_force`, `eli`, `entry_into_force[]`, `application_dates[]`, `effect_dates[]`, `procedures[]`), `policy_area`, `legal_basis[]`, `eurlex_url`, `text_url` (relative URL to the text endpoint), `body_txt` and `body_html`, plus the 5 envelope-level datapoints. The fields are the list's; see it for their meaning. HTTP 404 with `reason_code: not_found` if the CELEX isn't in our mirror.

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from EUR-Lex RSS feeds + Cellar SPARQL sector-3.""",
)
async def get_law_detail(
    celex: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> LawItem:
    # CELEX can collide across LEG corpus dumps (e.g. an annex or related
    # joint-declaration re-uses the parent's CELEX). Prefer the row whose
    # title starts with the doc_type word ("Regulation"/"Directive"/...) which
    # is the canonical originator, then fall back to lowest id (earliest
    # ingestion = canonical entry in 99% of cases).
    # A bare integer is the ROW ID, not a CELEX. 11,436 rows carry no CELEX at all
    # (drafts, association-council acts, EEA declarations, annex fragments), so the
    # `self` the list prints for them is /laws/{id} -- and this route used to read that
    # as a CELEX and 404. The id is also the identifier we tell clients to key on,
    # because a corrected CELEX otherwise reads as a brand new record. Safe to overload:
    # no CELEX in the corpus is all digits, and a test asserts that stays true.
    key = (celex or "").strip()
    if key.isdigit():
        row = db.query(EULaw).filter(EULaw.id == int(key)).first()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Law id {key} not found")
        return _law_item(row)

    upper_celex = key.upper()
    candidates = (
        db.query(EULaw)
        .filter(EULaw.celex == upper_celex)
        .order_by(EULaw.id.asc())
        .all()
    )
    r = None
    if candidates:
        # Prefer titles that start with the normalised doc_type
        for cand in candidates:
            dt = (cand.doc_type_normalized or cand.doc_type or "").strip()
            if dt and (cand.title or "").lower().startswith(dt.lower()):
                r = cand
                break
        if r is None:
            r = candidates[0]
    if not r:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"CELEX {celex} not found",
                "reason_code": "not_found",
                "resource": "law",
                "id": celex,
            },
        )
    return _law_item(r)


class LawTextResponse(BaseModel):
    celex: str
    title: Optional[str] = None
    doc_type: Optional[str] = None
    adopted_on: Optional[date] = None
    format: str = Field(..., description="xml | plain")
    content: str
    content_length: int
    eurlex_url: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL (alias of eurlex_url).")
    body_txt: Optional[str] = Field(None, description="Plain-text body — populated when format=plain (mirrors `content`).")
    body_html: Optional[str] = Field(None, description="HTML/XHTML body — populated when format=xml (mirrors `content`).")
    document_date: Optional[date] = Field(None, description="Adoption / publication date (alias of adopted_on).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this CELEX.")
    updated_date: Optional[datetime] = Field(None, description="When this record last changed, for incremental sync. Null when the source table keeps no change signal.")


@router.get(
    "/{celex}/text",
    response_model=LawTextResponse,
    summary="Full text of one adopted EU law — plain text or raw XML",
    description="""**What it does**
Returns the full legal text of an adopted EU law identified by its CELEX. Tries the local Formex V4 XML cache first (the 30,246 publications with text of the LEG_2026-10 bulk export); falls back to live fetch from Cellar (`publications.europa.eu/resource/celex/{celex}` with `Accept: application/xhtml+xml`). Returns the body as either whitespace-normalised plain text (default) or raw markup.

**When to use it**
When you need the actual legal text — for citation, full-text analysis, or feeding into a downstream LLM context. The local Formex cache is fast (~50ms); Cellar fallback is slower (~2-3s) but always works for any post-1952 CELEX. For pre-parsed structured access (recital ↔ article mapping, definition extraction), use the `/api/v1/legal-text/*` endpoints instead.

**Input**
- `celex` (path) — EU legal identifier (case-insensitive).
- `format` — `plain` (default, whitespace-normalised) or `xml` (raw Formex markup).

**Try it**
```
GET /api/v1/laws/32024R1689/text
GET /api/v1/laws/32016R0679/text?format=xml
```

**You get back**
A `LawTextResponse` with `celex`, `title`, `doc_type`, `adopted_on`, `format`, `content` (the actual text), `content_length`, `eurlex_url`, plus the 5 envelope-level datapoints (`body_txt` mirrors `content` when format=plain, `body_html` when format=xml).

**Data freshness**
Live pass-through (the local Formex cache is regenerated quarterly from the LEG_YYYY-MM bulk export). For acts NOT in the local cache, the live Cellar fetch always reflects the latest published text — but the Publications Office is the slow-changing authoritative source: once an act is published in the OJ, its text doesn't change (only consolidations get new CELEX numbers).""",
)
async def get_law_text(
    celex: str,
    format: str = Query("plain", pattern="^(plain|xml)$"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> LawTextResponse:
    from pathlib import Path
    import re

    row = db.query(EULaw).filter(EULaw.celex == celex.upper()).first()
    if not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"CELEX {celex} not found", "reason_code": "not_found", "resource": "law", "id": celex},
        )

    xml_path = row.xml_path or ""
    raw = ""
    # Prefer local LEG corpus if deployed
    if xml_path:
        repo_root = Path(__file__).resolve().parents[3]
        full_path = repo_root / xml_path
        if full_path.exists():
            raw = full_path.read_text(encoding="utf-8", errors="ignore")

    # Fallback to EUR-Lex Cellar API (works on prod where LEG XML isn't shipped)
    if not raw:
        import httpx
        cellar_url = f"https://publications.europa.eu/resource/celex/{row.celex}"
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as hc:
                resp = await hc.get(cellar_url, headers={"Accept": "application/xhtml+xml, text/html", "Accept-Language": "eng"})
                if resp.status_code == 200 and resp.text:
                    raw = resp.text
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Cellar fetch failed for {row.celex}: {exc}")

    if not raw:
        raise HTTPException(
            status_code=404,
            detail={"error": f"Text unavailable for CELEX {celex}", "reason_code": "text_unavailable", "resource": "law", "id": celex},
        )
    if format == "plain":
        text = re.sub(r"<[^>]+>", " ", raw)
        text = re.sub(r"\s+", " ", text).strip()
    else:
        text = raw

    return LawTextResponse(
        celex=row.celex,
        title=row.title,
        doc_type=row.doc_type_normalized or row.doc_type,
        adopted_on=row.date,
        format=format,
        content=text,
        content_length=len(text),
        eurlex_url=_eurlex_url(row.celex),
        public_url=_eurlex_url(row.celex),
        body_txt=text if format == "plain" else None,
        body_html=text if format == "xml" else None,
        document_date=row.date,
        creation_date=row.created_at,
        updated_date=row_updated(row),
    )
