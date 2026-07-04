"""
EuroVoc & vocabularies source — /api/v2/legislative/eurovoc/*.

Backend: the Publications Office EuroVoc thesaurus (Cellar SPARQL) +
EU Vocabularies authority tables (NALs). Covers subject classification:
concept search, acts-by-concept, and authority-table lookups.

LIVE endpoints delegate to api.v1.cellar_discover (EuroVoc) and
api.v1.vocabularies (authority NALs). All paths sit under the read:publications
scope (vocabulary/classification data — a deliberate v2 consolidation; in v1
the Cellar EuroVoc routes lived under the /discover/cellar read:laws prefix).
PROPOSED: /directories/legal-acts is served today via /authority/directories.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text as _sql
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from api.v1 import cellar_discover as _v1_cellar
from api.v1 import vocabularies as _v1_vocab
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from api.v1.cellar_discover import CellarRecentItem, EuroVocConcept
from api.v1.vocabularies import VocabularyConcept

router = APIRouter(prefix="/eurovoc", tags=["v2-legislative-eurovoc"])


@router.get(
    "/concepts/search",
    response_model=PaginatedResponse[EuroVocConcept],
    summary="Search the EU subject thesaurus (EuroVoc) — find concept IDs to enumerate acts by topic",
    description="""**What it does**
Free-text search against the EuroVoc thesaurus — the EU's official multilingual subject vocabulary. Returns matching concepts with `concept_uri`, human-readable `label`, and a ShowVoc deep-link.

**When to use it**
Discover the `concept_id` to feed `/eurovoc/concepts/{concept_id}/acts` (the id is the trailing digits of `concept_uri`, e.g. `http://eurovoc.europa.eu/3030` -> `3030`). Or translate a plain-English topic into the EU's canonical subject tag.

**Input**
- `q` — search term (min 2 chars; multilingual).
- `language` — ISO-2 (default `en`).
- `limit` (1-100, default 20).

**Try it**
```
GET /api/v2/legislative/eurovoc/concepts/search?q=artificial%20intelligence
```

**You get back**
A `PaginatedResponse[EuroVocConcept]`. The trailing digits of each `concept_uri` are the IDs for the `/acts` route.

**Data freshness**
Live SPARQL pass-through.""",
)
async def search_concepts(
    request: Request,
    q: str = Query(..., min_length=2, description="Free-text search term", example="artificial intelligence"),
    language: str = Query("en", description="ISO-2 language code for labels"),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[EuroVocConcept]:
    return await _v1_cellar.search_eurovoc(request, q=q, language=language, limit=limit, user=user)


@router.get(
    "/concepts/{concept_id}/acts",
    response_model=PaginatedResponse[CellarRecentItem],
    summary="EU acts tagged with one EuroVoc concept (e.g. AI, data protection, climate)",
    description="""**What it does**
Returns every EU legal act in the Cellar metadata graph tagged with the given EuroVoc subject concept (driven by `cdm:work_is_about_concept_eurovoc`). Optional date floor + language.

**When to use it**
To enumerate "every EU act about X" where X is a curated EuroVoc subject — more precise than free-text search because EuroVoc is the EU's authoritative subject thesaurus.

**How to obtain a concept_id**
Call `/eurovoc/concepts/search?q=<topic>`; the trailing digits of each `concept_uri` are the IDs. Both `3030` and `http://eurovoc.europa.eu/3030` are accepted. Examples: `3030` AI, `5181` data protection, `5482` climate change, `754` renewable energy.

**Input**
- `concept_id` (path) — digits or full EuroVoc URI.
- `published_from` (optional) — lower bound on document date.
- `language` (default ENG) — ISO-3 for the title.
- `limit` (1-200, default 50).

**Try it**
```
GET /api/v2/legislative/eurovoc/concepts/3030/acts?limit=5
```

**You get back**
A `PaginatedResponse[CellarRecentItem]`; each row's `public_url` deep-links to EUR-Lex.

**Data freshness**
Live SPARQL pass-through.""",
)
async def acts_by_concept(
    request: Request,
    concept_id: str = Path(..., description="EuroVoc concept ID (digits, e.g. 3030) or full URI"),
    published_from: Optional[date] = Query(None, description="Lower bound on document date"),
    language: str = Query("ENG", description="ISO-3 language code for titles"),
    limit: int = Query(50, ge=1, le=200),
    include_body: bool = Query(False, description="Inline each act's full body (Cellar XHTML). Caps the page to 10. Default false."),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CellarRecentItem]:
    if include_body and limit > 10:
        limit = 10
    resp = await _v1_cellar.acts_by_eurovoc(
        request, concept_id=concept_id, published_from=published_from, language=language, limit=limit, user=user
    )
    if include_body:
        from api.v2.legislative.eur_lex import _fill_bodies
        await _fill_bodies(resp.data)
    return resp


# Authority NAL dispatcher — maps a table slug to the v1 vocabularies handler.
_AUTHORITY_TABLES = {
    "corporate-bodies": _v1_vocab.list_corporate_bodies,
    "procedures": _v1_vocab.list_procedures,
    "directories": _v1_vocab.list_directories,
    "modification-types": _v1_vocab.list_modification_types,
}


@router.get(
    "/authority/{table}",
    response_model=PaginatedResponse[VocabularyConcept],
    summary="EU authority tables (NALs) — corporate bodies, procedure types, directories, modification types",
    description="""**What it does**
Language-aware lookups against the EU's Named Authority Lists (NALs). One endpoint, four tables selected by the `table` path segment:
- `corporate-bodies` — EU institutions, agencies, DGs, joint undertakings (~1,958 concepts).
- `procedures` — inter-institutional procedure types (COD / CNS / APP / CONS / INI ...).
- `directories` — the subject-matter directory tree of EU legal acts (~475 concepts). This also serves the "directory of legal acts" subject classification.
- `modification-types` — amends / repeals / corrects / consolidates / replaces.

**When to use it**
Resolve an acronym (`EP`, `EMA`) to its canonical multilingual name, translate a 3-letter procedure code, build a subject navigator, or render relationship labels — all in the user's language (en/fr/es/ca/it/nl).

**Input**
- `table` (path) — one of `corporate-bodies` / `procedures` / `directories` / `modification-types`.
- `q` — substring on `pref_label` + exact match on `alt_labels` (acronym-friendly).
- `lang` — Brubru language (default `en`).
- `limit` (1-200, default 50), `page`.

**Try it**
```
GET /api/v2/legislative/eurovoc/authority/corporate-bodies?q=Parliament&lang=en
GET /api/v2/legislative/eurovoc/authority/directories?q=environment
```

**You get back**
A `PaginatedResponse[VocabularyConcept]`; each carries the canonical `uri` (== `public_url`), `pref_label`, `alt_labels[]`, `lang`, plus the 5 envelope datapoints. HTTP 404 (`reason_code: not_found`) for an unknown table.

**Data freshness**
Refreshed nightly from the Cellar SPARQL endpoint into the local authority-label cache.""",
)
async def authority_table(
    request: Request,
    table: str = Path(..., description="corporate-bodies | procedures | directories | modification-types"),
    q: Optional[str] = Query(None, description="Search term (matches pref_label substring + alt_labels)"),
    lang: str = Query("en", description="Brubru language code (en|fr|es|ca|it|nl)"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[VocabularyConcept]:
    handler = _AUTHORITY_TABLES.get(table)
    if handler is None:
        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Unknown authority table {table!r}",
                "reason_code": "not_found",
                "valid_tables": sorted(_AUTHORITY_TABLES),
            },
        )
    return await handler(request, q=q, lang=lang, limit=limit, page=page, user=user, db=db)


@router.get(
    "/directories/legal-acts",
    response_model=PaginatedResponse[VocabularyConcept],
    summary="Directory of EU legal acts — the 20-chapter subject classification tree",
    description="""**What it does**
Returns the Publications Office subject classification of EU legislation — the directory codes (e.g. "13.30.99 Environment / Air pollution") every EUR-Lex act is tagged with. A convenience alias of `/authority/directories`.

**When to use it**
To build a subject-tag navigator across the acquis or translate a directory code into its localised label.

**Input**
- `q` — substring search on the chapter label.
- `lang` — Brubru language (default `en`).
- `limit` (1-200, default 50), `page`.

**Try it**
```
GET /api/v2/legislative/eurovoc/directories/legal-acts?q=environment
```

**You get back**
A `PaginatedResponse[VocabularyConcept]`; each carries the directory-code `uri` (== `public_url`), `pref_label`, `alt_labels[]`, `lang`, plus the 5 envelope datapoints.

**Data freshness**
Refreshed nightly from the Cellar SPARQL endpoint into the local authority-label cache.""",
)
async def directories_legal_acts(
    request: Request,
    q: Optional[str] = Query(None, description="Substring search on the chapter label"),
    lang: str = Query("en", description="Brubru language code (en|fr|es|ca|it|nl)"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[VocabularyConcept]:
    return await _v1_vocab.list_directories(request, q=q, lang=lang, limit=limit, page=page, user=user, db=db)


# ===========================================================================
# EuroVoc TAXONOMY tree — the full walkable thesaurus.
# Served from the local eurovoc_concepts table (migration 199): 21 domains ->
# 127 microthesauri -> 7,502 descriptors, with the skos:broader hierarchy and
# multilingual labels (en/es/fr/it/nl; ca reserved for the Catalan taxonomy).
# This differs from /search (which only *finds* concepts): these routes *walk*
# the tree top-down for building a subject navigator or a translated taxonomy.
# ===========================================================================

class EuroVocTaxonomyConcept(BaseModel):
    uri: str
    notation: Optional[str] = None
    concept_type: str = Field(..., description="domain | microthesaurus | descriptor")
    labels: dict = Field(default_factory=dict, description="prefLabel per language {en,es,fr,it,nl[,ca]}")
    alt_labels: Optional[dict] = None
    domain_uri: Optional[str] = None
    microthesaurus_uri: Optional[str] = None
    broader_uri: Optional[str] = None
    # 5 mandatory Brubru datapoints
    public_url: Optional[str] = Field(None, description="The concept's EuroVoc URI (stable key; links to EUR-Lex tagging).")
    body_txt: Optional[str] = Field(None, description="Preferred label in the requested language.")
    body_html: Optional[str] = Field(None, description="HTML composition of the label.")
    document_date: Optional[str] = None
    creation_date: Optional[str] = None


def _tx_item(r, lang: str) -> EuroVocTaxonomyConcept:
    labels = r["labels"] or {}
    pref = labels.get(lang) or labels.get("en") or ""
    return EuroVocTaxonomyConcept(
        uri=r["concept_uri"], notation=r["notation"], concept_type=r["concept_type"],
        labels=labels, alt_labels=r["alt_labels"], domain_uri=r["domain_uri"],
        microthesaurus_uri=r["microthesaurus_uri"], broader_uri=r["broader_uri"],
        public_url=r["concept_uri"], body_txt=pref, body_html=f"<p>{pref}</p>",
    )


def _tx_page(db: Session, where: str, params: dict, page: int, limit: int, lang: str):
    off = (page - 1) * limit
    total = db.execute(_sql(f"SELECT count(*) FROM eurovoc_concepts WHERE {where}"), params).scalar() or 0
    rows = db.execute(_sql(
        "SELECT concept_uri, notation, concept_type, labels, alt_labels, domain_uri, "
        "microthesaurus_uri, broader_uri FROM eurovoc_concepts WHERE " + where +
        " ORDER BY notation LIMIT :lim OFFSET :off"),
        {**params, "lim": limit, "off": off}).mappings().all()
    items = [_tx_item(r, lang) for r in rows]
    return build_envelope(items, total, page, limit, op_core_title="EuroVoc taxonomy", op_core_type="Thesaurus")


_TX_DESC = """**What it does**
Walks the EuroVoc thesaurus tree top-down: {level}. Labels in en/es/fr/it/nl (ca once the Catalan taxonomy is loaded).

**When to use it**
Build a subject navigator over the acquis, or export the taxonomy to translate/re-use as an official classification.

**Input**
{inp}`lang` (en|es|fr|it|nl|ca, default en) selects which label to surface in `body_txt`; `labels` always carries every language. Pagination via `page`/`limit`.

**Try it**
`GET /api/v2/legislative/eurovoc/taxonomy/{ex}`

**You get back**
A `PaginatedResponse[EuroVocTaxonomyConcept]`: each concept's stable `uri` (== `public_url`), `notation`, `concept_type`, the multilingual `labels`, and its `domain_uri`/`microthesaurus_uri`/`broader_uri` for walking the hierarchy."""


@router.get("/taxonomy/domains", response_model=PaginatedResponse[EuroVocTaxonomyConcept],
            summary="EuroVoc top level — the 21 subject domains (Politics, Law, Environment, ...)",
            description=_TX_DESC.format(level="the 21 top domains", inp="", ex="domains"))
async def taxonomy_domains(
    request: Request,
    lang: str = Query("en", description="Label language (en|es|fr|it|nl|ca)"),
    limit: int = Query(50, ge=1, le=200), page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[EuroVocTaxonomyConcept]:
    return _tx_page(db, "concept_type='domain'", {}, page, limit, lang)


@router.get("/taxonomy/microthesauri", response_model=PaginatedResponse[EuroVocTaxonomyConcept],
            summary="EuroVoc mid level — the 127 microthesauri (optionally within one domain)",
            description=_TX_DESC.format(level="the 127 microthesauri, optionally filtered to one domain",
                                        inp="`domain` — a domain notation like `28` to list only that domain's microthesauri. ",
                                        ex="microthesauri?domain=28"))
async def taxonomy_microthesauri(
    request: Request,
    domain: Optional[str] = Query(None, description="Domain notation (e.g. 28) to filter"),
    lang: str = Query("en"), limit: int = Query(200, ge=1, le=200), page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[EuroVocTaxonomyConcept]:
    where, params = "concept_type='microthesaurus'", {}
    if domain:
        where += " AND domain_uri = (SELECT concept_uri FROM eurovoc_concepts WHERE concept_type='domain' AND notation=:d)"
        params["d"] = domain
    return _tx_page(db, where, params, page, limit, lang)


@router.get("/taxonomy/descriptors", response_model=PaginatedResponse[EuroVocTaxonomyConcept],
            summary="EuroVoc descriptors — the ~7,500 subject terms (by microthesaurus or free-text)",
            description=_TX_DESC.format(level="the descriptors, filtered by microthesaurus and/or a label search",
                                        inp="`microthesaurus` — a microthesaurus notation (e.g. 2826); `q` — substring match on the label in `lang`. ",
                                        ex="descriptors?microthesaurus=2826"))
async def taxonomy_descriptors(
    request: Request,
    microthesaurus: Optional[str] = Query(None, description="Microthesaurus notation (e.g. 2826)"),
    q: Optional[str] = Query(None, description="Label substring search (in `lang`)"),
    lang: str = Query("en"), limit: int = Query(50, ge=1, le=200), page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[EuroVocTaxonomyConcept]:
    where, params = "concept_type='descriptor'", {}
    if microthesaurus:
        where += " AND microthesaurus_uri = (SELECT concept_uri FROM eurovoc_concepts WHERE concept_type='microthesaurus' AND notation=:m)"
        params["m"] = microthesaurus
    if q:
        where += " AND labels->>:lg ILIKE :q"
        params["lg"] = lang if lang in ("en", "es", "fr", "it", "nl", "ca") else "en"
        params["q"] = f"%{q}%"
    return _tx_page(db, where, params, page, limit, lang)


@router.get("/taxonomy/concept/{notation}", response_model=PaginatedResponse[EuroVocTaxonomyConcept],
            summary="One EuroVoc concept by notation, with its full hierarchy path",
            description="""**What it does**
Returns one EuroVoc concept (domain, microthesaurus or descriptor) by its `notation`, plus its ancestors (domain > microthesaurus > broader-terms) so you have the full path in one call.

**When to use it**
Resolve a EuroVoc code to its multilingual labels and place in the tree.

**Input**
`notation` — the EuroVoc code (descriptor id like `1764`, microthesaurus `2826`, or domain `28`). `lang` selects `body_txt`.

**Try it**
`GET /api/v2/legislative/eurovoc/taxonomy/concept/1764`

**You get back**
A `PaginatedResponse[EuroVocTaxonomyConcept]` whose `data` is the concept followed by its ancestors, root-last.""")
async def taxonomy_concept(
    request: Request,
    notation: str = Path(..., description="EuroVoc notation (e.g. 1764, 2826, 28)"),
    lang: str = Query("en"),
    user: User = Depends(api_user_with_rate_limit), db: Session = Depends(get_db),
) -> PaginatedResponse[EuroVocTaxonomyConcept]:
    row = db.execute(_sql(
        "SELECT concept_uri, notation, concept_type, labels, alt_labels, domain_uri, "
        "microthesaurus_uri, broader_uri FROM eurovoc_concepts WHERE notation=:n LIMIT 1"),
        {"n": notation}).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail={"reason_code": "not_found", "notation": notation})
    chain = [row]
    # walk broader-terms, then microthesaurus, then domain
    seen = {row["concept_uri"]}
    cur_uri = row["broader_uri"]
    for uri in (row["broader_uri"], row["microthesaurus_uri"], row["domain_uri"]):
        while uri and uri not in seen:
            anc = db.execute(_sql(
                "SELECT concept_uri, notation, concept_type, labels, alt_labels, domain_uri, "
                "microthesaurus_uri, broader_uri FROM eurovoc_concepts WHERE concept_uri=:u LIMIT 1"),
                {"u": uri}).mappings().first()
            if not anc:
                break
            chain.append(anc); seen.add(uri)
            uri = anc["broader_uri"] if anc["concept_type"] == "descriptor" else None
    items = [_tx_item(r, lang) for r in chain]
    return build_envelope(items, len(items), 1, len(items) or 1,
                          op_core_title="EuroVoc concept path", op_core_type="Thesaurus")
