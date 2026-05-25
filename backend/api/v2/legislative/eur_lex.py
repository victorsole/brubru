"""
EUR-Lex / Publications Office source — /api/v2/legislative/eur-lex/*.

Backend: the Publications Office Cellar (publications.europa.eu) + Brubru's
eu_laws mirror. Covers adopted EU legislation across the proposal's eight
groupings: identifiers & resolution, documents, search & summaries,
relationships & lifecycle, the Official Journal, citations, and vocabularies.

Structure contract: every endpoint uses the shared api_user_with_rate_limit
dependency (auth + scope + 60 req/min + per-call euro debit), returns the
canonical PaginatedResponse / typed model, and ships the plain-English
summary + 5-section Markdown description — identical to the v1 surface Jordi
reviewed.

LIVE endpoints delegate to the v1 handler functions (single source of truth
during v1+v2 coexistence); body cross-links are rewritten to the v2 path.
PROPOSED endpoints (resolve, xref, views, consolidated, summaries, lifecycle,
OJ) are implemented natively and land across the next checkpoints.
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.eu_law import EULaw
from models.legislative_train import LegislativeCarriage
from models.user import User

from api.v1 import laws as _v1_laws
from api.v1 import identify as _v1_identify
from api.v1 import legal_text as _v1_legal_text
from api.v1 import citations as _v1_citations
from api.v1 import cellar_discover as _v1_cellar
from api.v1._body import body_threshold_param
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from api.v1.laws import LawItem, LawTextResponse
from api.v1.identify import IdentifyResult
from api.v1.legal_text import (
    DefinedTermsResponse,
    RecitalArticleMapResponse,
    ResolveAliasesRequest,
    ResolveRefsRequest,
)
from api.v1.citations import VerifyCitationResponse
from api.v1.cellar_discover import CellarMetadata, CellarRecentItem, CellarRelation
from services.api_clients.cellar_sparql_client import CellarSPARQLClient
from services.identifiers.standard_identifier_resolver import recognise
from services.parsers.law_alias_resolver import find_alias_matches

router = APIRouter(prefix="/eur-lex", tags=["v2-legislative-eur-lex"])

_V2_BASE = "/api/v2/legislative/eur-lex"

# CELEX shape: 5 digits + 1-2 type letters + 4 digits (+ optional consolidation suffix).
_CELEX_RE = re.compile(r"^[0-9]{5}[A-Z]{1,2}[0-9]{4}(\([0-9]+\))?$", re.IGNORECASE)


def _eurlex(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"


def _law_created_at(db: Session, celex: str):
    """eu_laws.created_at for a CELEX (the 5th mandatory datapoint), or None."""
    try:
        return db.query(EULaw.created_at).filter(EULaw.celex == celex).scalar()
    except Exception:
        return None


class _DataPoints(BaseModel):
    """The 5 mandatory Brubru v1 datapoints, mixed into every native v2 model
    so the response contract matches v1 (fields present, even when null)."""
    public_url: Optional[str] = Field(None, description="Citizen-facing canonical EU URL.")
    body_txt: Optional[str] = Field(None, description="Plain-text body (null when the resource has no inline body).")
    body_html: Optional[str] = Field(None, description="HTML body (null when the resource has no inline body).")
    document_date: Optional[date] = Field(None, description="The resource's document date, when applicable.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru generated/ingested this (server time).")


# ---------------------------------------------------------------------------
# law_xref cache (best-effort — endpoints work even if the table is absent)
# ---------------------------------------------------------------------------

_XREF_COLS = (
    "eli", "oj_reference", "procedure_ref", "resource_type", "in_force",
    "document_date", "eurovoc", "legal_basis", "authors", "relation_counts",
    "relation_total", "computed_at",
)


def _read_law_xref(db: Session, celex: str) -> Optional[dict]:
    try:
        row = db.execute(
            text(f"SELECT {', '.join(_XREF_COLS)} FROM public.law_xref WHERE celex = :c"),
            {"c": celex},
        ).mappings().first()
        return dict(row) if row else None
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _write_law_xref(db: Session, celex: str, data: dict) -> None:
    try:
        db.execute(
            text(
                """
                INSERT INTO public.law_xref
                    (celex, eli, oj_reference, procedure_ref, resource_type, in_force,
                     document_date, eurovoc, legal_basis, authors, relation_counts,
                     relation_total, computed_at)
                VALUES
                    (:celex, :eli, :oj, :proc, :rtype, :inforce, :ddate,
                     CAST(:eurovoc AS jsonb), CAST(:lb AS jsonb), CAST(:authors AS jsonb),
                     CAST(:rc AS jsonb), :rtotal, NOW())
                ON CONFLICT (celex) DO UPDATE SET
                    eli = EXCLUDED.eli, oj_reference = EXCLUDED.oj_reference,
                    procedure_ref = EXCLUDED.procedure_ref, resource_type = EXCLUDED.resource_type,
                    in_force = EXCLUDED.in_force, document_date = EXCLUDED.document_date,
                    eurovoc = EXCLUDED.eurovoc, legal_basis = EXCLUDED.legal_basis,
                    authors = EXCLUDED.authors, relation_counts = EXCLUDED.relation_counts,
                    relation_total = EXCLUDED.relation_total, computed_at = NOW()
                """
            ),
            {
                "celex": celex,
                "eli": data.get("eli"),
                "oj": data.get("oj_reference"),
                "proc": data.get("procedure_ref"),
                "rtype": data.get("resource_type"),
                "inforce": data.get("in_force"),
                "ddate": data.get("document_date"),
                "eurovoc": json.dumps(data.get("eurovoc") or []),
                "lb": json.dumps(data.get("legal_basis") or []),
                "authors": json.dumps(data.get("authors") or []),
                "rc": json.dumps(data.get("relation_counts") or {}),
                "rtotal": data.get("relation_total") or 0,
            },
        )
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


def _nativise_law_links(item: LawItem) -> LawItem:
    """Point a LawItem's cross-links at the v2 surface instead of v1."""
    if item.celex:
        item.text_url = f"{_V2_BASE}/laws/{item.celex}/text"
    return item


# ---------------------------------------------------------------------------
# Identifiers & resolution (PROPOSED — the crown jewels, native v2)
# Registered BEFORE /laws/{celex} so the literal /laws/resolve wins routing.
# ---------------------------------------------------------------------------

class ResolveResult(_DataPoints):
    input: str
    recognised_kind: Optional[str] = Field(None, description="Identifier type recognised from the input (celex, eli, ecli, oj, alias, oeil_ref, ...).")
    resolved_via: str = Field(..., description="How the CELEX was reached: celex | eli | alias | oeil | unresolved.")
    celex: Optional[str] = None
    eli: Optional[str] = None
    title: Optional[str] = None
    in_force: Optional[bool] = None
    canonical_url: Optional[str] = Field(None, description="Official EU URL for the resource.")
    brubru_url: Optional[str] = Field(None, description="The Brubru v2 endpoint for this law, when resolved to a CELEX.")


@router.get(
    "/laws/resolve",
    response_model=ResolveResult,
    summary="Resolve any identifier to the canonical CELEX + ELI",
    description="""**What it does**
Accepts any EU identifier — a CELEX, an ELI URI, an ECLI, a COM/OJ reference, an OEIL procedure reference, or a law nickname (GDPR, DSA, AI Act) — and normalises it to the canonical CELEX + ELI, with the recognised type and the matching Brubru endpoint. The productised join key: one identifier in, every other name out.

**When to use it**
When you hold one identifier and need the others, or before calling any CELEX-keyed endpoint with an input of unknown shape. Pairs with `/laws/{celex}/xref` for the full relationship graph.

**Input**
- `id` — the identifier or nickname (e.g. `GDPR`, `32016R0679`, `2021/0106(COD)`).

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/resolve?id=GDPR
GET /api/v2/legislative/eur-lex/laws/resolve?id=2021/0106(COD)
```

**You get back**
A `ResolveResult` with `input`, `recognised_kind`, `resolved_via` (celex/eli/alias/oeil), `celex`, `eli`, `title`, `in_force`, `canonical_url`, `brubru_url`. HTTP 422 (`reason_code: unresolved_identifier`) when nothing matches.

**Data freshness**
Live: pattern recognition + alias dictionary + one Cellar lookup for the ELI (cached to law_xref).""",
)
async def resolve_identifier(
    request: Request,
    id: str = Query(..., min_length=1, description="Any EU identifier or law nickname", example="GDPR"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ResolveResult:
    raw = id.strip()
    kind: Optional[str] = None
    canonical: Optional[str] = None
    brubru: Optional[str] = None
    celex: Optional[str] = None
    eli: Optional[str] = None
    via = "unresolved"

    match = recognise(raw)
    if match is not None:
        kind = match.kind.value
        canonical = match.canonical_url
        brubru = match.brubru_url

    # 1. Direct CELEX shape wins.
    if _CELEX_RE.match(raw):
        celex = raw.upper()
        via = "celex"
        kind = kind or "celex"
    # 2. ELI -> CELEX reverse lookup.
    elif kind and kind.lower() == "eli":
        eli = match.value if match else None
        try:
            async with CellarSPARQLClient() as client:
                celex = await client.get_celex_from_eli(eli or raw)
            if celex:
                via = "eli"
        except Exception:
            pass

    # 3. Law nickname (GDPR, AI Act, ...).
    if celex is None:
        try:
            aliases = find_alias_matches(raw)
            if aliases and aliases[0].celex:
                celex = aliases[0].celex
                via = "alias"
                kind = kind or "alias"
        except Exception:
            pass

    # 4. OEIL procedure reference -> carriage CELEX.
    if celex is None:
        try:
            car = (
                db.query(LegislativeCarriage)
                .filter(LegislativeCarriage.oeil_procedure_ref == raw)
                .first()
            )
            if car and car.celex_numbers:
                nums = list(car.celex_numbers or [])
                if nums:
                    celex = nums[0]
                    via = "oeil"
                    kind = kind or "oeil_ref"
        except Exception:
            pass

    title: Optional[str] = None
    in_force: Optional[bool] = None
    if celex:
        celex = celex.upper()
        cached = _read_law_xref(db, celex)
        if cached and cached.get("eli"):
            eli = eli or cached.get("eli")
            in_force = cached.get("in_force")
        else:
            try:
                async with CellarSPARQLClient() as client:
                    meta = await client.get_celex_metadata(celex, language="ENG")
                if meta:
                    eli = eli or meta.get("eli")
                    title = meta.get("title")
                    in_force = meta.get("in_force")
            except Exception:
                pass
        canonical = canonical or _eurlex(celex)
        brubru = f"{_V2_BASE}/laws/{celex}"

    if celex is None and match is None:
        raise HTTPException(
            status_code=422,
            detail={
                "error": f"Could not resolve {raw!r} to any EU identifier or law",
                "reason_code": "unresolved_identifier",
            },
        )

    return ResolveResult(
        input=raw,
        recognised_kind=kind,
        resolved_via=via,
        celex=celex,
        eli=eli,
        title=title,
        in_force=in_force,
        canonical_url=canonical,
        brubru_url=brubru,
        public_url=canonical or (_eurlex(celex) if celex else None),
        creation_date=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# LEGISSUM summaries (PROPOSED, native). Registered BEFORE /laws/{celex} so the
# literal /laws/summaries wins routing.
# ---------------------------------------------------------------------------

class SummaryItem(_DataPoints):
    summary_id: Optional[str] = None
    celex: Optional[str] = None
    title: Optional[str] = None
    lsu_url: Optional[str] = Field(None, description="EUR-Lex Legislative Summary (LSU) view URL.")


def _lsu_url(celex: str) -> str:
    return f"https://eur-lex.europa.eu/legal-content/EN/LSU/?uri=CELEX:{celex}"


@router.get(
    "/laws/summaries",
    response_model=PaginatedResponse[SummaryItem],
    summary="Browse / search the LEGISSUM plain-language summaries of EU legislation",
    description="""**What it does**
Searches the LEGISSUM corpus — the Publications Office's plain-language "Summaries of EU legislation" that explain a directive or regulation in accessible prose. Returns matching summaries with the underlying CELEX and the EUR-Lex LSU view URL.

**When to use it**
When you want the human-readable summary of a law rather than its legal text — ideal for grounding a chatbot answer or briefing a non-lawyer.

**Input**
- `q` — free-text search over summary titles (optional).
- `limit` (1-200, default 50).

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/summaries?q=data%20protection
```

**You get back**
A `PaginatedResponse[SummaryItem]` (`summary_id`, `celex`, `title`, `lsu_url`). `coverage_complete=false`: LEGISSUM is a sparse subgraph in Cellar, so results are best-effort pending a dedicated LEGISSUM sync.

**Data freshness**
Live SPARQL pass-through against the Cellar LEGISSUM graph.""",
)
async def list_summaries(
    request: Request,
    q: Optional[str] = Query(None, description="Free-text search over summary titles"),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[SummaryItem]:
    rows = []
    try:
        async with CellarSPARQLClient() as client:
            rows = await client.search_legissum(keyword=q, limit=limit)
    except Exception:
        rows = []
    items = []
    for r in rows:
        celex = r.get("celex")
        items.append(
            SummaryItem(
                summary_id=celex or r.get("work"),
                celex=celex,
                title=r.get("title"),
                lsu_url=_lsu_url(celex) if celex else None,
                public_url=_lsu_url(celex) if celex else r.get("work"),
                creation_date=datetime.utcnow(),
            )
        )
    return build_envelope(
        items=items,
        total=len(items),
        page=1,
        limit=limit,
        coverage_complete=False,
        op_core_title="LEGISSUM summaries of EU legislation",
        op_core_type="EU legislation summary",
        op_core_identifier=str(request.url),
    )


@router.get(
    "/laws/summaries/{summary_id}",
    response_model=SummaryItem,
    summary="One LEGISSUM summary by its identifier",
    description="""**What it does**
Returns one plain-language summary record. If the id is a CELEX, builds the EUR-Lex LSU view URL and resolves the title from Cellar; otherwise treats the id as a LEGISSUM reference.

**When to use it**
After `/laws/summaries` (or when you already hold a CELEX) to get the direct LSU link + title.

**Input**
- `summary_id` (path) — a CELEX (e.g. `32016R0679`) or a LEGISSUM reference.

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/summaries/32016R0679
```

**You get back**
A `SummaryItem` with `summary_id`, `celex`, `title`, `lsu_url`, `public_url`.

**Data freshness**
Live: URL construction + an optional Cellar title lookup for CELEX ids.""",
)
async def get_summary(
    summary_id: str,
    user: User = Depends(api_user_with_rate_limit),
) -> SummaryItem:
    sid = summary_id.strip()
    is_celex = bool(_CELEX_RE.match(sid))
    if is_celex:
        url = _lsu_url(sid.upper())
        title = None
        try:
            async with CellarSPARQLClient() as client:
                meta = await client.get_celex_metadata(sid.upper(), language="ENG")
            if meta:
                title = meta.get("title")
        except Exception:
            pass
        return SummaryItem(summary_id=sid.upper(), celex=sid.upper(), title=title, lsu_url=url, public_url=url, creation_date=datetime.utcnow())
    url = f"https://eur-lex.europa.eu/legal-content/EN/LSU/?uri=LEGISSUM:{sid}"
    return SummaryItem(summary_id=sid, celex=None, title=None, lsu_url=url, public_url=url, creation_date=datetime.utcnow())


# ---------------------------------------------------------------------------
# Documents & search (LIVE — delegate to v1)
# ---------------------------------------------------------------------------

@router.get(
    "/laws",
    response_model=PaginatedResponse[LawItem],
    summary="Search adopted EU legislation — 8,710 distinct laws across 28,513 OJ publications",
    description="""**What it does**
Full-text search over Brubru's mirror of adopted EU legislation (the LEG_2025-11 Publications Office bulk export — 8,710 distinct laws across 28,513 Official Journal publications). Each row carries the CELEX legal identifier, document type, title + subject matter, policy area, publication date, and the EUR-Lex canonical URL.

**When to use it**
To find specific acts ("the AI Act"), enumerate laws by topic, or feed a partner integration the live adopted-legislation corpus. Pair with `/api/v2/legislative/eur-lex/laws/{celex}/text` for the full body. For procedures still in negotiation, use the Legislative Observatory source at `/api/v2/legislative/oeil/procedures`.

**Input**
- `q` — full-text search on title + subject matter (PostgreSQL TSVECTOR).
- `celex` — exact match on the legal identifier.
- `doc_type` — `regulation` / `directive` / `decision` / `recommendation` / `opinion` / ...
- `policy_area` — single policy tag.
- `published_from`, `published_to` — adoption-date bounds (YYYY-MM-DD).
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v2/legislative/eur-lex/laws?q=AI%20Act&limit=10
GET /api/v2/legislative/eur-lex/laws?doc_type=regulation&policy_area=environment&published_from=2024-01-01
```

**You get back**
A `PaginatedResponse[LawItem]` envelope. Each item carries `celex`, `title`, `doc_type`, `adopted_on`, `oj_reference`, `policy_area`, `legal_basis[]`, `eurlex_url`, `text_url`, plus the 5 envelope-level datapoints.

**Data freshness**
Synced every 6 hours (00:00 / 06:00 / 12:00 / 18:00 UTC, hot tier) from EUR-Lex RSS feeds + Cellar SPARQL sector-3.""",
)
async def list_laws(
    request: Request,
    q: Optional[str] = Query(None, description="Full-text search (title + subject matter)"),
    celex: Optional[str] = Query(None, description="Exact CELEX filter"),
    doc_type: Optional[str] = Query(None, description="Document type (regulation, directive, decision, ...)"),
    policy_area: Optional[str] = Query(None, description="Policy area slug"),
    published_from: Optional[date] = Query(None, description="Adoption date >= value (YYYY-MM-DD)"),
    published_to: Optional[date] = Query(None, description="Adoption date <= value (YYYY-MM-DD). Preferred name."),
    published_end: Optional[date] = Query(None, description="Alias of published_to (GovClipping-compatible). 422 if it conflicts."),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync lower bound (updated_at >= value)."),
    updated_to: Optional[datetime] = Query(None, description="Incremental sync upper bound (updated_at <= value)."),
    updated_end: Optional[datetime] = Query(None, description="Alias of updated_to (GovClipping-compatible)."),
    include_orphans: bool = Query(False, description="Include rows with no CELEX (orphaned annexes). Default false."),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LawItem]:
    resp = await _v1_laws.list_laws(
        request,
        q=q,
        celex=celex,
        doc_type=doc_type,
        policy_area=policy_area,
        published_from=published_from,
        published_to=published_to,
        published_end=published_end,
        updated_from=updated_from,
        updated_to=updated_to,
        updated_end=updated_end,
        include_orphans=include_orphans,
        limit=limit,
        page=page,
        user=user,
        db=db,
    )
    for it in resp.data:
        _nativise_law_links(it)
    return resp


@router.get(
    "/laws/{celex}",
    response_model=LawItem,
    summary="Look up one adopted EU law by its legal identifier — metadata only (no body)",
    description="""**What it does**
Returns the bibliographic metadata for one adopted EU law identified by its CELEX (the EU's stable legal identifier — e.g. `32024R1689` for the AI Act): title, document type, adoption date, OJ reference, policy area, legal-basis array, EUR-Lex URL, and a relative URL to the text endpoint.

**When to use it**
When you only need bibliographic fields and not the full body — faster than `/{celex}/text` because it doesn't fetch the body. Pair with `/api/v2/legislative/eur-lex/laws/{celex}/text` for the actual legal text.

**Input**
- `celex` (path) — the EU legal identifier. Case-insensitive; uppercased internally. Format: 5 digits + 1-2 letters + 4 digits (e.g. `32024R1689`, `52026PC0321`).

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32024R1689
GET /api/v2/legislative/eur-lex/laws/32016R0679
```

**You get back**
A `LawItem` with `celex`, `title`, `doc_type`, `adopted_on`, `oj_reference`, `policy_area`, `legal_basis[]`, `eurlex_url`, `text_url`, plus the 5 envelope-level datapoints. HTTP 404 with `reason_code: not_found` if the CELEX isn't in our mirror.

**Data freshness**
Synced every 6 hours (hot tier) from EUR-Lex RSS feeds + Cellar SPARQL sector-3.""",
)
async def get_law_detail(
    celex: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> LawItem:
    item = await _v1_laws.get_law_detail(celex, user=user, db=db)
    return _nativise_law_links(item)


@router.get(
    "/laws/{celex}/text",
    response_model=LawTextResponse,
    summary="Full text of one adopted EU law — plain text or raw XML",
    description="""**What it does**
Returns the full legal text of an adopted EU law identified by its CELEX. Tries the local Formex V4 XML cache first (28,513 files from the LEG_2025-11 bulk export); falls back to a live Cellar fetch (`publications.europa.eu/resource/celex/{celex}`). Returns the body as whitespace-normalised plain text (default) or raw markup.

**When to use it**
When you need the actual legal text — for citation, full-text analysis, or feeding a downstream LLM context. For pre-parsed structured access (recital -> article mapping, definition extraction) use the legal-text endpoints under this same source.

**Input**
- `celex` (path) — EU legal identifier (case-insensitive).
- `format` — `plain` (default) or `xml` (raw Formex markup).

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32024R1689/text
GET /api/v2/legislative/eur-lex/laws/32016R0679/text?format=xml
```

**You get back**
A `LawTextResponse` with `celex`, `title`, `doc_type`, `adopted_on`, `format`, `content`, `content_length`, `eurlex_url`, plus the 5 envelope-level datapoints (`body_txt` mirrors `content` when format=plain, `body_html` when format=xml).

**Data freshness**
Live pass-through; the local Formex cache is regenerated quarterly from the LEG_YYYY-MM bulk export. Once an act is published in the OJ its text doesn't change (only consolidations get new CELEX numbers).""",
)
async def get_law_text(
    celex: str,
    format: str = Query("plain", pattern="^(plain|xml)$"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> LawTextResponse:
    return await _v1_laws.get_law_text(celex, format=format, user=user, db=db)


# ---------------------------------------------------------------------------
# Legal-text intelligence on one act (LIVE — delegate to v1 legal-text)
# ---------------------------------------------------------------------------

@router.get(
    "/laws/{celex}/recital-article-map",
    response_model=RecitalArticleMapResponse,
    summary="Recital-to-article semantic mapping — which recitals explain each article",
    description="""**What it does**
For a given EU law, returns a mapping of each article to its top-3 most semantically related recitals, computed via TF-IDF cosine similarity over the act's preamble + body. Jump from "article 22" to the recitals that explain the drafter's intent.

**When to use it**
When interpreting a specific article and you need its explanatory recitals automatically — especially for GDPR / DSA / AI Act, where the preamble runs to hundreds of recitals.

**Input**
- `celex` (path) — legal identifier.
- `force_recompute` (query, default false) — local dev only; bypass the cache.

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32025R2149/recital-article-map
```

**You get back**
A `RecitalArticleMapResponse` with `celex`, `map` (article -> [recital, score] list), `public_url`, `creation_date`. HTTP 404 (`reason_code: not_found`) when the cache hasn't been computed for this CELEX (Formex XML is not deployed to production — use `/laws/{celex}/text`).

**Data freshness**
Cached deterministically; the underlying text doesn't change after adoption.""",
)
def recital_article_map(
    celex: str,
    force_recompute: bool = Query(False),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> RecitalArticleMapResponse:
    return _v1_legal_text.recital_article_map(celex, force_recompute=force_recompute, user=user, db=db)


@router.get(
    "/laws/{celex}/defined-terms",
    response_model=DefinedTermsResponse,
    summary="Legal definitions from one EU act — terms the law itself defines authoritatively",
    description="""**What it does**
Extracts the formal definitions article (typically Article 3 or 4) from an EU law — the terms the law defines authoritatively for its own scope — with each term + its definition text parsed from the Formex XML.

**When to use it**
When you need to know exactly how a law defines terms like "very large online platform" (DSA), "AI system" (AI Act), "personal data" (GDPR) without reading the full text. Critical for compliance scope analysis.

**Input**
- `celex` (path) — legal identifier.
- `force_recompute` (query, default false) — local dev only.
- `body_threshold` (default 500) — minimum body chars for `has_body=true`.

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32022R2065/defined-terms
```

**You get back**
A `DefinedTermsResponse` with `celex`, `terms` (term -> definition), `has_body`, `body_html`, `body_txt`, plus the 5 envelope-level datapoints.

**Data freshness**
Cached deterministically (definitions don't change after adoption).""",
)
def defined_terms(
    celex: str,
    force_recompute: bool = Query(False),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> DefinedTermsResponse:
    return _v1_legal_text.defined_terms(
        celex, force_recompute=force_recompute, body_threshold=body_threshold, user=user, db=db
    )


@router.post(
    "/resolve-references",
    summary="Resolve inline EU legal citations in free text — extract every embedded reference",
    description="""**What it does**
Scans a block of free text and extracts every embedded EU legal citation (e.g. "Article 7 of Regulation (EU) 2024/1234"), returning a structured list with the matched legal identifier and canonical EUR-Lex URL. Pass `annotate_html=true` to receive the original text with each citation wrapped in an `<a href=...>` link.

**When to use it**
Auto-link EU citations in briefings, opinion pieces, AI-generated answers, or Word-to-HTML conversion. Idempotent; POST is used only because the request body carries free text.

**Input**
JSON body: `{ "text": "<free text>", "annotate_html": false }`.

**Try it**
```
POST /api/v2/legislative/eur-lex/resolve-references
{ "text": "Article 5 of Regulation (EU) 2022/2065 prohibits..." }
```

**You get back**
With `annotate_html=false`: `{ refs: [{ alias, celex, url, public_url, ... }], + envelope datapoints }`. With `annotate_html=true`: `{ html: "<text with inserted links>" }`.

**Data freshness**
Live pass-through (regex extraction + URL composition; no upstream call).""",
)
def resolve_references(
    payload: ResolveRefsRequest,
    user: User = Depends(api_user_with_rate_limit),
):
    return _v1_legal_text.resolve_references(payload, user=user)


@router.post(
    "/resolve-aliases",
    summary="Resolve human names of EU laws (GDPR, DSA, AI Act, CBAM, ...) to their legal identifiers",
    description="""**What it does**
Scans free text for known human names of EU laws — GDPR, DSA, AI Act, CBAM, DORA, Solvency II, CRR, MiFID II, and 680+ more aliases — and returns each match with its legal identifier, canonical title, and the character offset where it was matched.

**When to use it**
When your users type "GDPR" but you need `32016R0679` to feed into other endpoints. Pairs with `/resolve-references` (which catches the formal "Regulation (EU) 2016/679" form).

**Input**
JSON body: `{ "text": "<free text>" }`.

**Try it**
```
POST /api/v2/legislative/eur-lex/resolve-aliases
{ "text": "Comparing GDPR and the AI Act on automated decisions" }
```

**You get back**
`{ aliases: [{ alias, celex, full_title, start, end, public_url, ... }], + envelope datapoints }`.

**Data freshness**
Live pass-through (regex match against a curated 680+ alias dictionary).""",
)
def resolve_aliases(
    payload: ResolveAliasesRequest,
    user: User = Depends(api_user_with_rate_limit),
):
    return _v1_legal_text.resolve_aliases(payload, user=user)


# ---------------------------------------------------------------------------
# Identifiers & citation verification (LIVE — delegate to v1)
# ---------------------------------------------------------------------------

@router.get(
    "/identify",
    response_model=IdentifyResult,
    summary="Recognise any single EU identifier — legal IDs, case-law IDs, DOIs, ISBNs, OJ refs",
    description="""**What it does**
Hand it any EU standard identifier (CELEX, ECLI, ELI, ISBN, ISSN, DOI, OJ reference, catalogue number, authority URI, EuroVoc URI) and get back its recognised type, the canonical EU URL, the matching Brubru endpoint, and a ShowVoc deep-link.

**When to use it**
When you have an identifier of unknown type and want one call that says "this is an X, here's where to find it".

**Input**
- `q` — the identifier string.

**Try it**
```
GET /api/v2/legislative/eur-lex/identify?q=32016R0679
GET /api/v2/legislative/eur-lex/identify?q=ECLI:EU:C:2014:317
```

**You get back**
An `IdentifyResult` with `kind`, `value`, `canonical_url`, `brubru_url`, `showvoc_url`, `parts`. HTTP 422 (`reason_code: unknown_identifier`) if no type matches.

**Data freshness**
Live pass-through (pure pattern recognition; no upstream call).""",
)
async def identify_one(
    request: Request,
    q: str = Query(..., min_length=1, description="Identifier string", example="32016R0679"),
    user: User = Depends(api_user_with_rate_limit),
) -> IdentifyResult:
    return await _v1_identify.identify_one(request, q=q, user=user)


@router.get(
    "/identify/scan",
    response_model=PaginatedResponse[IdentifyResult],
    summary="Scan free text and extract every embedded EU identifier — list of recognised matches",
    description="""**What it does**
Scans any free-text string and returns every embedded EU standard identifier it recognises — CELEX, ECLI, ELI, ISBN, ISSN, DOI, OJ refs, catalogue numbers — each as a fully-resolved match.

**When to use it**
When you have a chunk of free text (an article, an email, a chat message) and want every identifier in it extracted + resolved in one call.

**Input**
- `text` — the free-text string to scan (min 2 chars).

**Try it**
```
GET /api/v2/legislative/eur-lex/identify/scan?text=See%20Regulation%20(EU)%202016/679%20and%20Directive%202002/58/EC.
```

**You get back**
A `PaginatedResponse[IdentifyResult]` — each item is one match (same shape as `/identify`).

**Data freshness**
Live pass-through (pure pattern recognition).""",
)
async def identify_scan(
    request: Request,
    text: str = Query(..., min_length=2, description="Free text to scan", example="See Regulation (EU) 2016/679 and Directive 2002/58/EC."),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[IdentifyResult]:
    return await _v1_identify.identify_scan(request, text=text, user=user)


@router.get(
    "/verify-citation/{ref:path}",
    response_model=VerifyCitationResponse,
    summary="Verify any EU legal reference — confirm it exists + return its full body and dates",
    description="""**What it does**
Given any EU legal reference, tells you whether it points at a real document on EUR-Lex / OEIL, and returns the canonical URLs plus the document's body and dates. Accepts CELEX (`32024R1689`), COM number (`COM(2021) 206`, auto-converted to CELEX), or OEIL procedure (`2021/0106(COD)`).

**When to use it**
Ground your own AI's citations, validate a regulatory feed, or detect hallucinated legal-identifier numbers before showing them to users.

**Input**
- `ref` (path) — the reference (URL-encoded if it contains spaces or parentheses).

**Try it**
```
GET /api/v2/legislative/eur-lex/verify-citation/32016R0679
```

**You get back**
A `VerifyCitationResponse` with `data` (`VerifyCitationItem`): `ref`, `kind`, `status` (ok/broken/unknown), `public_url`, `resolved_url`, `http_status`, `body_txt`, `body_html`, `creation_date`, `document_date`.

**Data freshness**
Cached 30 days on success, 24h on broken refs, 1h on transient errors; body fetched from Cellar XHTML on first call.""",
)
async def verify_citation(
    request: Request,
    ref: str = Path(..., description="The reference to verify (URL-encoded if it contains spaces or parentheses)"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> VerifyCitationResponse:
    return await _v1_citations.verify_citation(request, ref=ref, user=user, db=db)


# ---------------------------------------------------------------------------
# Cellar live discovery, relationships & manifestations (LIVE — delegate)
# ---------------------------------------------------------------------------

@router.get(
    "/recent",
    response_model=PaginatedResponse[CellarRecentItem],
    summary="Recently published EU acts (live from the Publications Office Cellar)",
    description="""**What it does**
Live discovery of EU acts published in a date range, queried directly against the Publications Office Cellar SPARQL endpoint — covers the full corpus (incl. case law + proposals not in the local `eu_laws` mirror). Metadata-only by default; pass `include_body=true` for a concurrent body fetch (limit capped at 10).

**When to use it**
Daily polling of newly-published acts, sector-scoped discovery, or "what landed on EUR-Lex since date X".

**Input**
- `published_from` (required), `published_to` (defaults today).
- `sectors` — comma-separated CELEX sector codes (e.g. `3,5`).
- `language` — ISO-3 (default ENG).
- `limit` (1-200, default 50; forced <=10 with include_body), `page`, `include_body`.

**Try it**
```
GET /api/v2/legislative/eur-lex/recent?published_from=2026-05-01&sectors=3&limit=20
```

**You get back**
Paginated `CellarRecentItem` rows; each `public_url` deep-links to EUR-Lex.

**Data freshness**
Live SPARQL pass-through; Cellar publishes throughout the day.""",
)
async def recent(
    request: Request,
    published_from: date = Query(..., description="Lower bound (YYYY-MM-DD)", example="2026-05-01"),
    published_to: Optional[date] = Query(None, description="Upper bound (YYYY-MM-DD); defaults to today"),
    sectors: Optional[str] = Query(None, description="Comma-separated CELEX sector codes (e.g. '3,5')"),
    language: str = Query("ENG", description="ISO-3 language code (uppercase) for titles"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    include_body: bool = Query(False, description="If true, fetch each row's Cellar XHTML body (limit capped at 10)."),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CellarRecentItem]:
    return await _v1_cellar.recent_cellar_acts(
        request,
        published_from=published_from,
        published_to=published_to,
        sectors=sectors,
        language=language,
        limit=limit,
        page=page,
        include_body=include_body,
        user=user,
    )


@router.get(
    "/laws/{celex}/cellar",
    response_model=CellarMetadata,
    summary="Live Publications Office metadata for one act — title, ELI, in-force, languages, EuroVoc",
    description="""**What it does**
Live fetch of full metadata for any EU act by CELEX from the Publications Office Cellar SPARQL graph — title, ELI URI, resource type, in-force status, validity dates, available languages, and EuroVoc subject concepts. Wider coverage than the `eu_laws`-backed `/laws/{celex}` (spans the full corpus incl. case law).

**When to use it**
When `/laws/{celex}` returns 404 (the act is outside Brubru's local mirror) or you need the live in-force flag + language list. Higher latency than the local cache (~2-3s vs ~50ms).

**Input**
- `celex` (path) — legal identifier.
- `language` (query, default ENG) — ISO-3 for the returned title.

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32016R0679/cellar
```

**You get back**
A `CellarMetadata` object with `celex`, `work_uri`, `title`, `document_date`, `eli`, `resource_type_label`, `in_force`, validity dates, `available_languages[]`, `eurovoc_concepts[]`, plus envelope datapoints.

**Data freshness**
Live pass-through (no cache; hits Cellar SPARQL on every request).""",
)
async def cellar_metadata(
    request: Request,
    celex: str = Path(..., description="CELEX number, e.g. 32016R0679"),
    language: str = Query("ENG", description="ISO-3 language code (uppercase) for titles"),
    user: User = Depends(api_user_with_rate_limit),
) -> CellarMetadata:
    return await _v1_cellar.cellar_celex_metadata(request, celex=celex, language=language, user=user)


@router.get(
    "/laws/{celex}/relationships",
    response_model=PaginatedResponse[CellarRelation],
    summary="Acts that amend, repeal, or are amended by an act — the legal-relationship graph",
    description="""**What it does**
Returns the directed legal-relationship graph around one CELEX: outgoing edges (this act amends / repeals / is based on …) and incoming edges (other acts that amend / repeal / cite this one). The envelope also carries the parent act's body so you don't need a second round-trip.

**When to use it**
Render an amendment tree, find every act that cites or supersedes a law, or drive an "is this still in force, or amended by X?" check.

**Input**
- `celex` (path).

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32025R2158/relationships
```

**You get back**
A paginated envelope of `CellarRelation` edges (`relation`, `related_celex`, `direction`) + the parent act's body in the envelope-level fields.

**Data freshness**
Live SPARQL pass-through.""",
)
async def relationships(
    request: Request,
    celex: str = Path(...),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CellarRelation]:
    return await _v1_cellar.cellar_celex_relationships(request, celex=celex, user=user)


@router.get(
    "/laws/{celex}/languages",
    summary="Every language version + download format of an EU act — direct download URLs",
    description="""**What it does**
Returns every `(language, format, URL)` tuple for one EU act from the Cellar metadata graph — up to 24 EU languages x multiple formats (FMX4 structured XML, XHTML, PDF/A, DOCX).

**When to use it**
When you need a specific-language or specific-format version of an act for a downstream parser or translation memory.

**Input**
- `celex` (path).

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32016R0679/languages
```

**You get back**
A JSON object with `languages[]`, `manifestations[]` (each `language`, `format`, `url`), plus envelope datapoints.

**Data freshness**
Live SPARQL pass-through.""",
)
async def languages(
    request: Request,
    celex: str = Path(...),
    user: User = Depends(api_user_with_rate_limit),
) -> dict:
    return await _v1_cellar.cellar_celex_languages(request, celex=celex, user=user)


# ---------------------------------------------------------------------------
# Cross-reference graph (PROPOSED — the crown jewel, native v2 + law_xref cache)
# ---------------------------------------------------------------------------

class XrefResult(BaseModel):
    celex: str
    eli: Optional[str] = None
    oj_reference: Optional[str] = None
    procedure_ref: Optional[str] = Field(None, description="The OEIL procedure that produced this act (reverse-looked-up from legislative carriages).")
    resource_type: Optional[str] = None
    in_force: Optional[bool] = None
    document_date: Optional[date] = None
    eurovoc: list = Field(default_factory=list, description="EuroVoc subject concepts attached to the work.")
    legal_basis: list = Field(default_factory=list)
    authors: list = Field(default_factory=list)
    relation_counts: dict = Field(default_factory=dict, description="Edge counts keyed by '{relation}:{direction}' (e.g. 'amendment:incoming').")
    relation_total: int = 0
    eurlex_url: Optional[str] = None
    cached: bool = Field(False, description="True when served from the law_xref cache; false when freshly computed.")
    computed_at: Optional[datetime] = None
    # The 5 mandatory Brubru v1 datapoints.
    public_url: Optional[str] = Field(None, description="Citizen-facing EUR-Lex URL (alias of eurlex_url).")
    body_txt: Optional[str] = Field(None, description="Null — call /laws/{celex}/text for the body.")
    body_html: Optional[str] = Field(None, description="Null — call /laws/{celex}/text for the body.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first ingested this CELEX (eu_laws.created_at).")


@router.get(
    "/laws/{celex}/xref",
    response_model=XrefResult,
    summary="All the other names and links for one EU law",
    description="""**What it does**
Given one EU law's CELEX, returns every identifier and relationship the Publications Office holds for it: its ELI permalink, its Official Journal reference, the legislative procedure that produced it, its EuroVoc topics, its legal basis, whether it's still in force, and counts of the acts it repeals / amends / is cited by. The productised join key — the same data that backfills Brubru's law_xref table.

**When to use it**
When you have one identifier and need the others, or to join a law across EUR-Lex, OEIL and your own records. The backbone for citation, deduplication, and "show me the full context of this act". For the full edge list (not counts), call `/laws/{celex}/relationships`.

**Input**
- `celex` (path) — the real CELEX (call `/laws/resolve` first if you hold a different identifier).
- `refresh` (query, default false) — bypass the cache and recompute.

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32016R0679/xref
```

**You get back**
An `XrefResult` with `celex`, `eli`, `oj_reference`, `procedure_ref`, `resource_type`, `in_force`, `document_date`, `eurovoc[]`, `legal_basis[]`, `relation_counts{}`, `relation_total`, `eurlex_url`, `cached`, `computed_at`. HTTP 404 (`reason_code: not_found`) if the CELEX is in neither Cellar nor the local mirror.

**Data freshness**
Cache-first: served from law_xref when present, else aggregated live from Cellar (metadata + relationships + EuroVoc) and written through to the cache.""",
)
async def law_xref(
    request: Request,
    celex: str = Path(..., description="CELEX number, e.g. 32016R0679"),
    refresh: bool = Query(False, description="Bypass the cache and recompute."),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> XrefResult:
    celex = celex.upper()

    if not refresh:
        cached = _read_law_xref(db, celex)
        if cached:
            return XrefResult(
                celex=celex,
                cached=True,
                eurlex_url=_eurlex(celex),
                public_url=_eurlex(celex),
                creation_date=_law_created_at(db, celex),
                **cached,
            )

    meta: dict = {}
    rels: list = []
    eurovoc: list = []
    type_label: Optional[str] = None
    try:
        async with CellarSPARQLClient() as client:
            meta = await client.get_celex_metadata(celex, language="ENG") or {}
            if meta:
                rels = await client.get_related_acts(celex)
                eurovoc = await client.get_eurovoc_concepts(celex)
                if meta.get("resourceTypeUri"):
                    type_label = await client.resolve_resource_type(meta["resourceTypeUri"])
    except Exception:
        pass

    row = db.query(EULaw).filter(EULaw.celex == celex).first()
    if not meta and not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"CELEX {celex} not found", "reason_code": "not_found", "resource": "law", "id": celex},
        )

    # Reverse-lookup the procedure that produced this act (best-effort).
    procedure_ref: Optional[str] = None
    try:
        car = (
            db.query(LegislativeCarriage)
            .filter(LegislativeCarriage.celex_numbers.contains([celex]))
            .first()
        )
        if car:
            procedure_ref = car.oeil_procedure_ref
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    # Bucket relationship edges by '{relation}:{direction}'.
    counts: dict = {}
    for r in rels:
        rel = (r.get("relation") or "").rstrip("/").split("/")[-1].split("#")[-1] or "related"
        direction = r.get("direction", "outgoing")
        counts[f"{rel}:{direction}"] = counts.get(f"{rel}:{direction}", 0) + 1

    doc_date: Optional[date] = None
    if meta.get("date"):
        try:
            doc_date = date.fromisoformat(meta["date"].split("T")[0])
        except (ValueError, AttributeError):
            doc_date = None
    if doc_date is None and row:
        doc_date = row.date

    result = {
        "eli": meta.get("eli"),
        "oj_reference": row.oj_reference if row else None,
        "procedure_ref": procedure_ref,
        "resource_type": type_label or (row.doc_type_normalized if row else None),
        "in_force": meta.get("in_force"),
        "document_date": doc_date,
        "eurovoc": eurovoc,
        "legal_basis": list(row.legal_basis or []) if row else [],
        "authors": [],
        "relation_counts": counts,
        "relation_total": len(rels),
    }
    _write_law_xref(db, celex, result)

    return XrefResult(
        celex=celex,
        cached=False,
        eurlex_url=_eurlex(celex),
        public_url=_eurlex(celex),
        computed_at=datetime.utcnow(),
        creation_date=row.created_at if row else None,
        **result,
    )


# ---------------------------------------------------------------------------
# Permanent links, lifecycle, consolidated (PROPOSED — native v2)
# ---------------------------------------------------------------------------

class ViewsResult(_DataPoints):
    celex: str
    eli: Optional[str] = None
    views: dict = Field(..., description="EUR-Lex permanent-link views keyed by code (txt, all, his, nim, lsu, pdf).")
    xml_notice: str
    cellar_resource: str


@router.get(
    "/laws/{celex}/views",
    response_model=ViewsResult,
    summary="Deterministic permanent-link set for one act — TXT / ALL / HIS / NIM / LSU + XML notice",
    description="""**What it does**
Builds the full set of EUR-Lex permanent-link views for one CELEX — TXT (text), ALL (all formats), HIS (procedure history), NIM (national transposition), LSU (legislative summary), PDF — plus the Cellar XML notice and resource URIs. Pure construction; no upstream fetch.

**When to use it**
When you want every canonical link for an act in one call, to render a "view this law on EUR-Lex" link set without composing URLs yourself.

**Input**
- `celex` (path) — legal identifier.

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32016R0679/views
```

**You get back**
A `ViewsResult` with `celex`, `eli` (from cache when present), `views{}` (the link set), `xml_notice`, `cellar_resource`, `public_url`.

**Data freshness**
Live: deterministic URL construction (ELI is read from the law_xref cache when available).""",
)
async def law_views(
    celex: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> ViewsResult:
    celex = celex.upper()
    base = "https://eur-lex.europa.eu/legal-content/EN"
    views = {
        "txt": f"{base}/TXT/?uri=CELEX:{celex}",
        "all": f"{base}/ALL/?uri=CELEX:{celex}",
        "his": f"{base}/HIS/?uri=CELEX:{celex}",
        "nim": f"{base}/NIM/?uri=CELEX:{celex}",
        "lsu": f"{base}/LSU/?uri=CELEX:{celex}",
        "pdf": f"{base}/PDF/?uri=CELEX:{celex}",
    }
    cached = _read_law_xref(db, celex)
    eli = cached.get("eli") if cached else None
    return ViewsResult(
        celex=celex,
        eli=eli,
        views=views,
        xml_notice=f"https://publications.europa.eu/resource/celex/{celex}?language=eng",
        cellar_resource=f"http://publications.europa.eu/resource/celex/{celex}",
        public_url=views["txt"],
        creation_date=datetime.utcnow(),
    )


class LifecycleResult(_DataPoints):
    celex: str
    in_force: Optional[bool] = None
    date_in_force: Optional[str] = None
    date_end_validity: Optional[str] = None
    repealed_or_expired: Optional[bool] = Field(None, description="True when an end-of-validity date is set.")


@router.get(
    "/laws/{celex}/lifecycle",
    response_model=LifecycleResult,
    summary="In-force status + entry-into-force / end-of-validity dates for one act",
    description="""**What it does**
Returns the temporal lifecycle of one act from the Cellar legal-status graph: whether it is in force, its entry-into-force date, its end-of-validity date (when set), the document date, and a derived repealed/expired flag.

**When to use it**
For an "is this law still in force?" check, or to drive a compliance timeline.

**Input**
- `celex` (path) — legal identifier.

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32016R0679/lifecycle
```

**You get back**
A `LifecycleResult` with `celex`, `in_force`, `date_in_force`, `date_end_validity`, `document_date`, `repealed_or_expired`, `public_url`. HTTP 404 if the CELEX is in neither Cellar nor the local mirror.

**Data freshness**
Live SPARQL pass-through against the Cellar legal-status graph.""",
)
async def law_lifecycle(
    celex: str,
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> LifecycleResult:
    celex = celex.upper()
    status: dict = {}
    try:
        async with CellarSPARQLClient() as client:
            status = await client.get_force_status(celex) or {}
    except Exception:
        status = {}
    row = db.query(EULaw).filter(EULaw.celex == celex).first()
    if not status and not row:
        raise HTTPException(
            status_code=404,
            detail={"error": f"CELEX {celex} not found", "reason_code": "not_found", "resource": "law", "id": celex},
        )
    end_validity = status.get("date_end_validity")
    return LifecycleResult(
        celex=celex,
        in_force=status.get("in_force"),
        date_in_force=status.get("date_in_force"),
        date_end_validity=end_validity,
        document_date=row.date if row else None,
        repealed_or_expired=bool(end_validity) if end_validity is not None else None,
        public_url=_eurlex(celex),
        creation_date=row.created_at if row else None,
    )


class ConsolidatedResult(_DataPoints):
    base_celex: str
    count: int
    latest: Optional[dict] = None
    versions: list = Field(default_factory=list, description="All consolidated versions, newest first: {celex, date, uri}.")


@router.get(
    "/laws/{celex}/consolidated",
    response_model=ConsolidatedResult,
    summary="Consolidated versions of one act — every dated consolidation, newest first",
    description="""**What it does**
Returns every consolidated version of a base act (each consolidation folds in subsequent amendments and gets its own CELEX), newest first, with the latest highlighted.

**When to use it**
When you need the current consolidated text rather than the original as-adopted version — the consolidated CELEX is what you then feed to `/laws/{celex}/text`.

**Input**
- `celex` (path) — the base act's legal identifier.

**Try it**
```
GET /api/v2/legislative/eur-lex/laws/32016R0679/consolidated
```

**You get back**
A `ConsolidatedResult` with `base_celex`, `count`, `latest` ({celex, date, uri}), `versions[]`, `public_url`. Empty `versions` when the act has no consolidations.

**Data freshness**
Live SPARQL pass-through against the Cellar consolidation graph.""",
)
async def law_consolidated(
    celex: str,
    user: User = Depends(api_user_with_rate_limit),
) -> ConsolidatedResult:
    celex = celex.upper()
    versions = []
    try:
        async with CellarSPARQLClient() as client:
            rows = await client.get_consolidated_versions(celex)
        for r in rows:
            versions.append({
                "celex": r.get("consolidatedCelex"),
                "date": r.get("date"),
                "uri": r.get("consolidated"),
            })
    except Exception:
        versions = []
    return ConsolidatedResult(
        base_celex=celex,
        count=len(versions),
        latest=versions[0] if versions else None,
        versions=versions,
        public_url=_eurlex(celex),
        creation_date=datetime.utcnow(),
    )


# ---------------------------------------------------------------------------
# Official Journal (PROPOSED — native v2)
# ---------------------------------------------------------------------------

@router.get(
    "/oj/daily",
    response_model=PaginatedResponse[CellarRecentItem],
    summary="Acts published in the Official Journal on a given date",
    description="""**What it does**
Lists the EU acts whose document date falls on a given day — the daily Official Journal view. Backed by the Cellar SPARQL date-range discovery constrained to a single date. `series=L` narrows to legislation (CELEX sector 3); `series=C` returns the rest.

**When to use it**
Daily monitoring of what was published in the OJ on a specific date.

**Input**
- `date` — the publication date (YYYY-MM-DD).
- `series` — `L` (legislation, default) or `C` (information & notices).
- `limit` (1-200, default 50), `page`.

**Try it**
```
GET /api/v2/legislative/eur-lex/oj/daily?date=2026-05-01&series=L
```

**You get back**
A `PaginatedResponse[CellarRecentItem]`; each row's `public_url` deep-links to EUR-Lex. Note: the OJ numbering switched to an act-by-act scheme on 1 Oct 2023; this endpoint keys on document date, which is stable across that change.

**Data freshness**
Live SPARQL pass-through.""",
)
async def oj_daily(
    request: Request,
    date: date = Query(..., description="Publication date (YYYY-MM-DD)", example="2026-05-01"),  # noqa: A002
    series: str = Query("L", pattern="^[LC]$", description="OJ series: L (legislation) or C (information)"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CellarRecentItem]:
    sectors = "3" if series == "L" else None
    return await _v1_cellar.recent_cellar_acts(
        request,
        published_from=date,
        published_to=date,
        sectors=sectors,
        language="ENG",
        limit=limit,
        page=page,
        include_body=False,
        user=user,
    )


@router.get(
    "/oj/{series}/{year}/{number}",
    response_model=PaginatedResponse[LawItem],
    summary="Look up acts by an Official Journal reference (series / year / number)",
    description="""**What it does**
Resolves an Official Journal reference to the act(s) carrying it, from Brubru's `eu_laws` mirror. Handles both the pre-2023 issue-based form (`L 187/41`) and the post-1-Oct-2023 act-by-act form (`L 2024/1689`).

**When to use it**
When you hold an OJ citation (from a footnote or a press release) and need the act's CELEX + metadata.

**Input**
- `series` (path) — `L` or `C`.
- `year` (path) — 4-digit year.
- `number` (path) — the issue number (pre-2023) or act number (post-2023).

**Try it**
```
GET /api/v2/legislative/eur-lex/oj/L/2024/1689
GET /api/v2/legislative/eur-lex/oj/L/2016/119
```

**You get back**
A `PaginatedResponse[LawItem]` of acts whose `oj_reference` matches. Empty when no local row carries that reference.

**Data freshness**
Synced every 6 hours (hot tier) from EUR-Lex + Cellar.""",
)
async def oj_by_reference(
    request: Request,
    series: str,
    year: int,
    number: str,
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[LawItem]:
    series = series.upper()
    # Post-2023 act-by-act ("L 2024/1689") OR pre-2023 issue-based ("L 187/41").
    post_2023 = f"{series} {year}/{number}%"
    pre_2023 = f"{series} {number}/%"
    q = db.query(EULaw).filter(
        EULaw.celex.isnot(None),
        (EULaw.oj_reference.ilike(post_2023)) | (
            (EULaw.oj_reference.ilike(pre_2023)) & (EULaw.celex_year == year)
        ),
    )
    total = q.count()
    rows = q.order_by(EULaw.date.desc().nullslast()).offset((page - 1) * limit).limit(limit).all()
    data = [
        LawItem(
            celex=r.celex,
            title=r.title,
            doc_type=r.doc_type_normalized or r.doc_type,
            adopted_on=r.date,
            oj_reference=r.oj_reference,
            policy_area=r.policy_area,
            legal_basis=list(r.legal_basis or []),
            eurlex_url=_eurlex(r.celex),
            text_url=f"{_V2_BASE}/laws/{r.celex}/text" if r.celex else None,
            public_url=_eurlex(r.celex),
            document_date=r.date,
            creation_date=r.created_at,
        )
        for r in rows
    ]
    return build_envelope(
        data,
        total=total,
        page=page,
        limit=limit,
        coverage_complete=True,
        op_core_title=f"Official Journal {series} {year}/{number}",
        op_core_type="EU legislation",
        op_core_identifier=str(request.url),
    )


@router.get(
    "/xref",
    response_model=PaginatedResponse[XrefResult],
    summary="Browse the whole cross-reference index — every law whose links have been computed",
    description="""**What it does**
Lists the complete cross-reference index — every CELEX whose ELI / OJ ref / procedure / EuroVoc / relationship graph has been computed and cached in `law_xref`. The browse-all sibling of `/laws/{celex}/xref`: where the single-act endpoint resolves one law, this one shows everything the index holds.

**When to use it**
To enumerate the cross-reference corpus, sync it into your own store, or sample what Brubru has joined across EUR-Lex / OEIL / EuroVoc. Each `/laws/{celex}/xref` call adds to this index, and a backfill populates it in bulk.

**Input**
- `q` — optional CELEX prefix filter (e.g. `32024`).
- `limit` (1-200, default 50), `page`.

**Try it**
```
GET /api/v2/legislative/eur-lex/xref?limit=50
GET /api/v2/legislative/eur-lex/xref?q=32024
```

**You get back**
A `PaginatedResponse[XrefResult]`, newest-computed first — each item is the same shape as the single-act `/xref` (celex, eli, oj_reference, procedure_ref, eurovoc[], relation_counts{}, ...).

**Data freshness**
Reads the `law_xref` cache, which grows as `/laws/{celex}/xref` is called and via bulk backfill.""",
)
async def list_xref(
    request: Request,
    q: Optional[str] = Query(None, description="Filter by CELEX prefix (e.g. 32024)"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[XrefResult]:
    where = ""
    params: dict = {}
    if q:
        where = "WHERE celex ILIKE :q"
        params["q"] = f"{q.upper()}%"
    total = 0
    rows = []
    try:
        total = int(
            db.execute(text(f"SELECT COUNT(*) FROM public.law_xref {where}"), params).scalar() or 0
        )
        rows = db.execute(
            text(
                f"SELECT celex, {', '.join(_XREF_COLS)} FROM public.law_xref {where} "
                "ORDER BY computed_at DESC NULLS LAST LIMIT :lim OFFSET :off"
            ),
            {**params, "lim": limit, "off": (page - 1) * limit},
        ).mappings().all()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        rows = []
    items = [
        XrefResult(
            celex=r["celex"],
            cached=True,
            eurlex_url=_eurlex(r["celex"]),
            public_url=_eurlex(r["celex"]),
            **{k: r[k] for k in _XREF_COLS},
        )
        for r in rows
    ]
    return build_envelope(
        items=items,
        total=total,
        page=page,
        limit=limit,
        op_core_title="EU law cross-reference index",
        op_core_type="EU legislation",
        op_core_identifier=str(request.url),
    )
