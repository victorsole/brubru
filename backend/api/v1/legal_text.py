"""
/api/v1/legal-text — Legal-Text Intelligence endpoints on the Data Provider API.

Wraps the recital-article linker, definition extractor, cross-reference resolver,
and law alias resolver that power Brubru's internal chatbot and Amendator.

Customers get the same primitives Brubru uses internally.
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from ._body import DEFAULT_HAS_BODY_THRESHOLD, body_threshold_param
from ._deps import api_user_with_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/legal-text", tags=["v1-legal-text"])


class RecitalArticleMapResponse(BaseModel):
    celex: str
    map: dict = Field(..., description="Article -> [{recital_number, score, snippet}, ...] (top-3)")
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL of the parent law (EUR-Lex CELEX URL).")
    body_txt: Optional[str] = Field(None, description="Null — call /api/v1/laws/{celex}/text for the parent law's body.")
    body_html: Optional[str] = Field(None, description="Null — same.")
    document_date: Optional[date] = Field(None, description="Null on this derived endpoint — fetch /api/v1/laws/{celex} for the parent's date.")
    creation_date: Optional[datetime] = Field(None, description="When the recital-article map was last computed.")


class DefinedTermsResponse(BaseModel):
    celex: str
    terms: dict = Field(..., description="Term -> {term, definition, article, point}")
    # Body fields composed from the concatenated definitions, useful as a
    # standalone glossary view of the law. body_html is a semantic <dl> with
    # one <dt>/<dd> pair per term; body_txt is a plain-text rendering.
    has_body: bool = False
    body_html: Optional[str] = None
    body_txt: Optional[str] = None
    # The 5 mandatory Brubru v1 datapoints
    public_url: Optional[str] = Field(None, description="Canonical citizen URL of the parent law (EUR-Lex CELEX URL).")
    document_date: Optional[date] = Field(None, description="Null on this derived endpoint — fetch /api/v1/laws/{celex} for the parent's date.")
    creation_date: Optional[datetime] = Field(None, description="When the defined-terms cache was last computed.")


def _compose_definitions_body(terms: dict, threshold: int = DEFAULT_HAS_BODY_THRESHOLD):
    """Compose body_html / body_text / has_body from the defined-terms dict.

    Builds:
      body_html — <dl><dt>{term}</dt><dd>{definition}</dd>…</dl>, optionally
                  grouped by article when articles vary.
      body_text — "term — definition" lines, blank-line separated.
    Honest empties: returns (None, None, False) when terms is empty.
    """
    from html import escape

    if not terms or not isinstance(terms, dict):
        return None, None, False

    # Iterate in insertion order (typically article order from the parser).
    dt_dd = []
    text_lines = []
    for key, entry in terms.items():
        if not isinstance(entry, dict):
            continue
        term = (entry.get("term") or key or "").strip()
        defn = (entry.get("definition") or "").strip()
        article = (entry.get("article") or "").strip()
        if not term or not defn:
            continue
        anchor = f" <small>({escape(article)})</small>" if article else ""
        dt_dd.append(f"<dt>{escape(term)}{anchor}</dt><dd>{escape(defn)}</dd>")
        text_lines.append(f"{term}{f' ({article})' if article else ''} — {defn}")

    if not dt_dd:
        return None, None, False

    body_html = f"<article><h2>Defined terms</h2><dl>{''.join(dt_dd)}</dl></article>"
    body_text = "\n\n".join(text_lines)
    has_body = len(body_text) >= threshold
    return body_html, body_text, has_body


class ResolveRefsRequest(BaseModel):
    text: str = Field(
        ...,
        description="Plain text containing inline EU citations (CELEX, Reg/Dir refs, COM numbers, ECLI, etc.).",
        examples=["Article 6 of Regulation (EU) 2016/679 and Directive 2002/58/EC apply here."],
    )
    annotate_html: bool = False


class ResolveAliasesRequest(BaseModel):
    text: str = Field(
        ...,
        description="Plain text. Detects GDPR/DSA/AI Act/etc. by name.",
        examples=["The GDPR and the AI Act both regulate automated decision-making."],
    )


@router.get(
    "/{celex}/recital-article-map",
    response_model=RecitalArticleMapResponse,
    summary="Recital-to-article semantic mapping — which recitals explain each article",
    description="""**What it does**
For a given EU law, returns a mapping of each article to its top-3 most semantically related recitals, computed via TF-IDF cosine similarity over the act's preamble + body. The mapping lets you jump from "article 22" to the 3 recitals that explain its drafter's intent — saving you from skimming hundreds of recitals every time.

**When to use it**
When interpreting a specific article and you need its explanatory recitals automatically. Particularly useful for compliance teams reading GDPR / DSA / AI Act, where the preamble is hundreds of recitals long and only a handful are relevant to each operative article.

**Input**
- `celex` (path) — legal identifier of the act.
- `force_recompute` (query, default false) — set true (local dev only) to bypass the cache and recompute.

**Try it**
```
GET /api/v1/legal-text/32025R2149/recital-article-map
```

**You get back**
A `RecitalArticleMapResponse` with `celex`, `map` (dict: article_number → list of [recital_number, similarity_score] tuples), `public_url` (EUR-Lex), and `creation_date`.

**Production cache state (2 May 2026):** 5 implementing acts cached (`32025D2208`, `32025R2149`, `32025R2158`, `32025R2226`). Backfill for flagship laws (DSA, GDPR, AI Act, DORA) is queued — the TF-IDF computation requires Formex XML which is not deployed on Railway for size reasons. 404 with `reason_code=not_found` means the cache hasn't been computed yet for this CELEX.

**Data freshness**
Cached at computation time; deterministic for a given act (the underlying text doesn't change after adoption). New entries land when an act is added to the cache.""",
)
def recital_article_map(
    celex: str,
    force_recompute: bool = Query(False),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> RecitalArticleMapResponse:
    # Defensive: catch ALL exceptions, including the lazy import itself, so
    # any failure surfaces as a clean 503 instead of an unhandled 500.
    try:
        from services.parsers.recital_article_store import get_or_compute_map
        mapping = get_or_compute_map(db, celex, force_recompute=force_recompute)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"recital-article-map computation failed for {celex}: {exc}")
        raise HTTPException(
            status_code=503,
            detail={
                "error": f"Unable to compute recital-article map for CELEX {celex}",
                "reason_code": "computation_unavailable",
                "source": "brubru-recital-linker",
                "exception": type(exc).__name__,
                "exception_message": str(exc)[:200],
            },
        )
    if mapping is None:
        # Either the law isn't in eu_laws or the LEG XML isn't available on
        # this deployment (Railway doesn't ship the LEG corpus by design).
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": f"CELEX {celex} not available — recital map requires Formex XML which is not deployed to production",
                "reason_code": "not_found",
                "resource": "law",
                "id": celex,
                "hint": "Use /api/v1/laws/{celex}/text to get the full text via the EUR-Lex Cellar fallback",
            },
        )
    return RecitalArticleMapResponse(
        celex=celex,
        map=mapping,
        public_url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
        creation_date=datetime.utcnow(),
    )


@router.get(
    "/{celex}/defined-terms",
    response_model=DefinedTermsResponse,
    summary="Legal definitions from one EU act — terms the law itself defines authoritatively",
    description="""**What it does**
Extracts the formal definitions article (typically Article 3 or Article 4) from an EU law — the terms the law defines authoritatively for its own scope. Returns each defined term + its authoritative definition text, parsed from the Formex XML.

**When to use it**
When you need to know exactly how a law defines terms like "very large online platform" (DSA), "AI system" (AI Act), "personal data" (GDPR) — without reading the full text. Critical for compliance analysis where the definitions determine the scope of obligations.

**Input**
- `celex` (path) — legal identifier of the act.
- `force_recompute` (query, default false) — set true locally to bypass the cache.
- `body_threshold` (default 500) — minimum body chars for `has_body=true`.

**Try it**
```
GET /api/v1/legal-text/32022R2065/defined-terms
```
Returns 23 DSA definitions (~7.9 KB) including "online platform", "recipient of the service", "illegal content".

**You get back**
A `DefinedTermsResponse` with `celex`, `terms` (dict: term → definition text), `has_body`, `body_html`, `body_txt`, plus the 5 envelope-level datapoints.

**Production cache state (2 May 2026):** DSA (`32022R2065`) fully cached. GDPR, AI Act, DORA compute on first request but the underlying Formex XML isn't deployed to Railway — backfill queued.

**Data freshness**
Cached deterministically (the underlying definitions don't change after adoption). New entries land when an act is added to the cache.""",
)
def defined_terms(
    celex: str,
    force_recompute: bool = Query(False),
    body_threshold: int = Depends(body_threshold_param),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> DefinedTermsResponse:
    from services.parsers.definition_store import get_or_compute_map as _get_defs

    mapping = _get_defs(db, celex, force_recompute=force_recompute)
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "detail": f"CELEX {celex} not available", "resource": "law", "id": celex},
        )
    body_html, body_text, has_body = _compose_definitions_body(mapping, threshold=body_threshold)
    return DefinedTermsResponse(
        celex=celex, terms=mapping,
        has_body=has_body, body_html=body_html, body_txt=body_text,
        public_url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}",
        creation_date=datetime.utcnow(),
    )


@router.post(
    "/resolve-references",
    summary="Resolve inline EU legal citations in free text — extract every embedded reference",
    description="""**What it does**
Scans a block of free text and extracts every embedded EU legal citation (e.g. "Article 7 of Regulation (EU) 2024/1234"), returning a structured list with the matched legal identifier and canonical EUR-Lex URL. Pass `annotate_html=true` to receive the original text with each citation wrapped in an `<a href=...>` link instead of a separate refs list.

**When to use it**
Auto-link EU citations in opinion pieces, briefings, AI-generated answers, or when converting Word documents into HTML. Idempotent — does NOT modify any server-side data (POST is used only because the request body carries free text that can exceed URL length limits).

**Input**
JSON body: `{ "text": "<free text>", "annotate_html": false }`. `text` is the input to scan; `annotate_html` switches return shape.

**Try it**
```
POST /api/v1/legal-text/resolve-references
{ "text": "Article 5 of Regulation (EU) 2022/2065 prohibits..." }
```

**You get back**
With `annotate_html=false` (default): `{ refs: [{ alias, celex, url, public_url, ... }], plus envelope datapoints }`. With `annotate_html=true`: `{ html: "<text with inserted <a> links>" }`.

**Data freshness**
Live pass-through (pure regex extraction + URL composition; no upstream HTTP call needed).""",
)
def resolve_references(
    payload: ResolveRefsRequest,
    user: User = Depends(api_user_with_rate_limit),
):
    from services.parsers.cross_reference_resolver import (
        resolve_references_json,
        annotate_html,
    )

    if payload.annotate_html:
        return {"html": annotate_html(payload.text)}
    refs = resolve_references_json(payload.text)
    # Augment each ref with public_url (its EUR-Lex URL is already in r["url"])
    # and the 5 mandatory v1 datapoints at envelope level.
    for r in refs:
        r["public_url"] = r.get("url")
        r["body_txt"] = None
        r["body_html"] = None
        r["document_date"] = None
        r["creation_date"] = datetime.utcnow().isoformat()
    return {
        "refs": refs,
        # Envelope-level v1 datapoints
        "public_url": None,
        "body_txt": payload.text,           # the resolver's input IS the body
        "body_html": None,
        "document_date": None,
        "creation_date": datetime.utcnow().isoformat(),
    }


@router.post(
    "/resolve-aliases",
    summary="Resolve human names of EU laws (GDPR, DSA, AI Act, CBAM, ...) to their legal identifiers",
    description="""**What it does**
Scans free text for known human names of EU laws — GDPR, DSA, AI Act, CBAM, DORA, Solvency II, CRR, MiFID II, and 680+ more aliases — and returns each match with its legal identifier, canonical title, and the character offset where it was matched.

**When to use it**
When your users type "GDPR" but you need `32016R0679` to feed into other Brubru endpoints. Or to extract every law referenced in a policy paper, opinion piece, or chat message. Pairs with `/api/v1/legal-text/resolve-references` (which catches the verbose "Regulation (EU) 2016/679" form) to cover both human-friendly and formal citation styles.

**Input**
JSON body: `{ "text": "<free text>" }`.

**Try it**
```
POST /api/v1/legal-text/resolve-aliases
{ "text": "Comparing GDPR and the AI Act on automated decisions" }
```

**You get back**
`{ aliases: [{ alias, celex, title, offset, public_url, ... }], plus envelope datapoints }`.

**Data freshness**
Live pass-through (pure regex matching against a curated alias dictionary of 680+ EU-law nicknames; no upstream HTTP call). The alias dictionary is updated when new flagship laws are adopted (e.g. AI Act in 2024).""",
)
def resolve_aliases(
    payload: ResolveAliasesRequest,
    user: User = Depends(api_user_with_rate_limit),
):
    from datetime import datetime as _dt
    from services.parsers.law_alias_resolver import find_alias_matches

    matches = find_alias_matches(payload.text)
    aliases = []
    for m in matches:
        eurlex = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{m.celex}" if m.celex else None
        aliases.append({
            "raw": m.raw,
            "alias": m.alias,
            "celex": m.celex,
            "full_title": m.full_title,
            "start": m.start,
            "end": m.end,
            # The 5 mandatory Brubru v1 datapoints (per-alias, parent = the resolved CELEX)
            "public_url": eurlex,
            "body_txt": None,           # use /api/v1/laws/{celex}/text for body
            "body_html": None,
            "document_date": None,      # not encoded in alias resolution; call /laws/{celex} for the date
            "creation_date": _dt.utcnow().isoformat(),
        })
    return {
        "aliases": aliases,
        # Envelope-level v1 datapoints (this is a stateless resolver — no parent doc)
        "public_url": None,
        "body_txt": payload.text,       # the resolver's input IS the body
        "body_html": None,
        "document_date": None,
        "creation_date": _dt.utcnow().isoformat(),
    }
