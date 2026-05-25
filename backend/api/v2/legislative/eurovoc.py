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
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from api.v1 import cellar_discover as _v1_cellar
from api.v1 import vocabularies as _v1_vocab
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
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
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[CellarRecentItem]:
    return await _v1_cellar.acts_by_eurovoc(
        request, concept_id=concept_id, published_from=published_from, language=language, limit=limit, user=user
    )


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
