"""
/api/v1/vocabularies/* — public surface over the local NAL cache.

Phase 1 of docs/applications/euvoc.md. Exposes 4 of the 12 hot NALs as
paginated, language-aware lookups. Reads from `eu_authority_labels` (filled
nightly by scripts/sync_eu_authority_labels.py).

Endpoints:
    GET /api/v1/vocabularies/corporate-bodies
    GET /api/v1/vocabularies/procedures
    GET /api/v1/vocabularies/directories
    GET /api/v1/vocabularies/modification-types
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vocabularies", tags=["v1-vocabularies"])

# Map endpoint slug -> source dataset URI in the cache.
_DATASET_URIS = {
    "corporate-bodies": "http://publications.europa.eu/resource/dataset/corporate-body",
    "procedures": "http://publications.europa.eu/resource/dataset/procedure",
    "directories": "http://publications.europa.eu/resource/dataset/dir-eu-legal-act",
    "modification-types": "http://publications.europa.eu/resource/dataset/modification-type",
}

_BRUBRU_LANGS = {"en", "fr", "es", "ca", "it", "nl"}


class VocabularyConcept(BaseModel):
    uri: str
    pref_label: str
    alt_labels: list[str] = Field(default_factory=list)
    lang: str
    source_dataset_uri: str
    # 5 mandatory Brubru v1 datapoints.
    public_url: Optional[str] = Field(
        None,
        description="The concept's authoritative URI on op.europa.eu — resolves to a real SKOS RDF page (alias of `uri`).",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Plain-text composition: preferred label + alt labels + language + source NAL.",
    )
    body_html: Optional[str] = Field(
        None,
        description="HTML composition of the same fields.",
    )
    document_date: Optional[date] = Field(
        None,
        description="Vocabulary concepts are not document-dated (NALs are versioned, not dated per-concept). Null by design.",
    )
    creation_date: Optional[datetime] = Field(
        None,
        description="When Brubru last refreshed this concept from the Cellar SPARQL endpoint (alias of fetched_at).",
    )


def _row_to_concept(r) -> dict:
    """Compose body + public_url for one authority-label row."""
    import html as _html
    pref = r.pref_label or "(no label)"
    alts = list(r.alt_labels or [])
    lines = [pref]
    parts_html = [f"<h2>{_html.escape(pref)}</h2>"]
    for k, v in [
        ("URI", r.uri),
        ("Alt labels", ", ".join(alts) if alts else None),
        ("Language", r.lang),
        ("Source NAL", r.source_dataset_uri),
    ]:
        if not v:
            continue
        lines.append(f"{k}: {v}")
        parts_html.append(f"<p><strong>{_html.escape(k)}:</strong> {_html.escape(str(v))}</p>")
    last_fetched = getattr(r, "fetched_at", None)
    return {
        "uri": r.uri,
        "pref_label": pref,
        "alt_labels": alts,
        "lang": r.lang,
        "source_dataset_uri": r.source_dataset_uri,
        "public_url": r.uri,
        "body_txt": "\n".join(lines),
        "body_html": "<article>" + "".join(parts_html) + "</article>",
        "document_date": None,
        "creation_date": last_fetched,
    }


def _list_concepts(
    db: Session,
    dataset_uri: str,
    *,
    lang: str,
    q: Optional[str],
    limit: int,
    offset: int,
) -> tuple[list[dict], int]:
    """Return (rows, total) for the requested NAL slice."""
    where = "source_dataset_uri = :ds AND lang = :lang"
    params = {"ds": dataset_uri, "lang": lang}
    if q:
        # Match pref_label substring OR alt_labels exact (acronym-friendly).
        where += " AND (LOWER(pref_label) LIKE :ql OR :q = ANY(alt_labels))"
        params["q"] = q
        params["ql"] = f"%{q.lower()}%"

    total_row = db.execute(
        text(f"SELECT COUNT(*) AS n FROM eu_authority_labels WHERE {where}"),
        params,
    ).first()
    total = int(total_row.n) if total_row else 0

    rows = db.execute(
        text(
            f"""
            SELECT uri, pref_label, alt_labels, lang, source_dataset_uri, fetched_at
            FROM eu_authority_labels
            WHERE {where}
            ORDER BY pref_label
            LIMIT :lim OFFSET :off
            """
        ),
        {**params, "lim": limit, "off": offset},
    ).all()

    return [_row_to_concept(r) for r in rows], total


def _build_endpoint(slug: str, summary: str, description: str):
    dataset_uri = _DATASET_URIS[slug]

    @router.get(
        f"/{slug}",
        response_model=PaginatedResponse[VocabularyConcept],
        summary=summary,
        description=description,
    )
    async def _handler(
        request: Request,
        q: Optional[str] = Query(None, description="Search term (matches pref_label substring + alt_labels)"),
        lang: str = Query("en", description="Brubru language code (en|fr|es|ca|it|nl)"),
        limit: int = Query(50, ge=1, le=200),
        page: int = Query(1, ge=1),
        user: User = Depends(api_user_with_rate_limit),
        db: Session = Depends(get_db),
    ) -> PaginatedResponse[VocabularyConcept]:
        lang = lang.lower()
        if lang not in _BRUBRU_LANGS:
            lang = "en"
        offset = (page - 1) * limit
        rows, total = _list_concepts(db, dataset_uri, lang=lang, q=q, limit=limit, offset=offset)
        items = [VocabularyConcept(**r) for r in rows]
        return build_envelope(items=items, total=total, page=page, limit=limit, coverage_complete=True)

    _handler.__name__ = f"list_{slug.replace('-', '_')}"
    return _handler


# Register the 4 endpoints.
list_corporate_bodies = _build_endpoint(
    "corporate-bodies",
    "EU corporate bodies — institutions, agencies, DGs, joint undertakings",
    """**What it does**
Lookups against the EU's `corporate-body` authority list. Every EU institution, agency, DG, executive agency, and joint undertaking has a canonical URI and labels in 24 EU languages on `publications.europa.eu`. Brubru caches the 6 languages we support (en, fr, es, ca, it, nl).

~1,958 concepts total. Each `public_url` resolves directly to the concept's SKOS RDF page on the EU Publications Office Cellar.

**When to use it**
- Resolve a short acronym (`EP`, `JUST`, `EMA`) to its canonical name + multilingual labels.
- Display EU body names in the user's language (CA/IT/NL/FR/ES/EN).
- Validate that a corporate-body code is real before storing it.

**Input**
- `q` — substring match on `pref_label` + exact match on `alt_labels` (acronyms).
- `lang` — Brubru language (`en` default; `en|fr|es|ca|it|nl`).
- `limit` (1–200, default 50), `page` (default 1).

**Try it**
```
GET /api/v1/vocabularies/corporate-bodies?q=Parliament&lang=en&limit=5
GET /api/v1/vocabularies/corporate-bodies?q=EMA&lang=ca
```

**You get back**
A paginated envelope of `VocabularyConcept` rows. Each carries the canonical `uri` (== `public_url`, resolves on op.europa.eu), `pref_label`, `alt_labels[]`, `lang`, and the 5 mandatory v1 datapoints (body composition, creation_date).""",
)
list_procedures = _build_endpoint(
    "procedures",
    "Inter-institutional procedure types — COD / CNS / APP / CONS, etc.",
    """**What it does**
Authoritative labels for EU inter-institutional procedure types — the codes OEIL uses to tag every legislative file: COD (ordinary legislative), CNS (consultation), APP (consent), CONS (Council recommendation), INI (own-initiative), RSP (resolution), etc.

~17 concepts. Each `public_url` resolves to the procedure-type concept page on op.europa.eu.

**When to use it**
- Translate a 3-letter code in an OEIL reference (`2024/0123(COD)`) to the full procedure name.
- Show procedure-type labels in the user's language.
- Validate a procedure-type code.

**Input**
- `q` — substring on `pref_label` / acronym match on `alt_labels`.
- `lang` — Brubru language (default `en`).
- `limit`, `page`.

**Try it**
```
GET /api/v1/vocabularies/procedures?lang=en
GET /api/v1/vocabularies/procedures?q=consultation&lang=fr
```

**You get back**
Paginated `VocabularyConcept` envelope with all 5 mandatory v1 datapoints per row.""",
)
list_directories = _build_endpoint(
    "directories",
    "Directory of EU legal acts — subject classification",
    """**What it does**
Subject classification of EU legislation maintained by the Publications Office. Each EU act in EUR-Lex is tagged with one or more directory codes (e.g. "13.30.99 — Environment / Air pollution"). This endpoint returns the classification tree.

~475 concepts. Each `public_url` resolves to the directory-code concept page on op.europa.eu.

**When to use it**
- Build a subject-tag navigator across the acquis.
- Translate a directory code to its localised label.
- Group laws by policy domain (consumer protection, agriculture, etc.).

**Input**
- `q` — substring search on `pref_label`.
- `lang` — Brubru language (default `en`).
- `limit`, `page`.

**Try it**
```
GET /api/v1/vocabularies/directories?q=environment&lang=en
```

**You get back**
Paginated `VocabularyConcept` envelope with all 5 mandatory v1 datapoints.""",
)
list_modification_types = _build_endpoint(
    "modification-types",
    "Legal-act modification types — amends / repeals / corrects / consolidates",
    """**What it does**
Labels for the relationships between EU legal acts: `amends`, `repeals`, `corrects`, `consolidates`, `replaces`, `derogates`. Used to walk the legal-act graph (e.g. "what acts amend Regulation 2016/679?").

~6 concepts. Each `public_url` resolves to the modification-type concept page on op.europa.eu.

**When to use it**
- Render relationship labels on a legal-act timeline.
- Filter cross-references by modification type.
- Multilingual UI for legal-text relations.

**Input**
- `q` — substring match.
- `lang` — Brubru language (default `en`).
- `limit`, `page`.

**Try it**
```
GET /api/v1/vocabularies/modification-types?lang=en
```

**You get back**
Paginated `VocabularyConcept` envelope with all 5 mandatory v1 datapoints per row.""",
)
