"""
Canon & deep-dive reports source — /api/v2/proprietary/canon/*.

Backend: Brubru's hand-built HTML deep-dive reports — the EU Canon
(article-by-article explainers of binding EU laws, /eucanon/) and the law
deep-dives (/biotech-act, /critical-medicines-act, ...). Each report is
published in up to six languages (en/es/ca/fr/it/nl) on SiteGround.

NATIVE — metadata is read from a committed manifest
(knowledge_base/canon_reports.json) so it travels with the backend deploy on
Railway (the HTML itself lives on SiteGround; the binding-laws CSV is
gitignored). Regenerate the manifest with `scripts/build_canon_manifest.py`
after a new report ships.

Scope: read:knowledge (Brubru knowledge layer).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/canon", tags=["v2-proprietary-canon"])

# knowledge_base/canon_reports.json — committed snapshot (see module docstring).
_MANIFEST_PATH = Path(__file__).resolve().parents[3] / "knowledge_base" / "canon_reports.json"

_REPORT_TYPES = {"canon", "deep_dive"}
_LANGS = {"en", "es", "ca", "fr", "it", "nl"}


class _DataPoints(BaseModel):
    """The 5 mandatory Brubru v1 datapoints — present even when null."""
    public_url: Optional[str] = Field(None, description="Citizen-facing canonical report URL (the English/index page).")
    body_txt: Optional[str] = Field(None, description="Plain-text body — null on lists; populated on detail when include_body=true.")
    body_html: Optional[str] = Field(None, description="HTML body — null on lists; populated on detail when include_body=true.")
    document_date: Optional[date] = Field(None, description="The underlying act's publication date (canon only); null for deep-dives.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru generated this report (null — reports are not per-row timestamped).")


class CanonReport(_DataPoints):
    """One Brubru deep-dive report (EU Canon entry or law deep-dive)."""
    slug: str = Field(..., description="Stable report slug (e.g. '2024-1689_aiact', 'biotech-act').")
    report_type: str = Field(..., description="'canon' (EU Canon, /eucanon/) or 'deep_dive' (law deep-dive).")
    title: str = Field(..., description="Report title (English).")
    summary: Optional[str] = Field(None, description="One-paragraph summary (the page meta description).")
    celex: Optional[str] = Field(None, description="CELEX of the act the report explains (canon entries; null for thematic deep-dives).")
    doc_type: Optional[str] = Field(None, description="Document type of the underlying act (e.g. Regulation).")
    legal_family: Optional[str] = Field(None, description="Brubru legal-family cluster tag (drives cross-linking).")
    languages: list[str] = Field(default_factory=list, description="Languages this report is published in (en/es/ca/fr/it/nl).")
    lang_urls: Dict[str, str] = Field(default_factory=dict, description="Per-language public URL map.")
    eurlex_url: Optional[str] = Field(None, description="EUR-Lex landing page for the underlying act (canon entries).")


# --------------------------------------------------------------------------- #
# Manifest load (cached) + helpers                                            #
# --------------------------------------------------------------------------- #

_MANIFEST_CACHE: Optional[list[dict]] = None


def _load_manifest() -> list[dict]:
    global _MANIFEST_CACHE
    if _MANIFEST_CACHE is None:
        try:
            payload = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
            _MANIFEST_CACHE = payload.get("reports", [])
        except (OSError, json.JSONDecodeError) as exc:
            logger.error("canon manifest load failed (%s): %s", _MANIFEST_PATH, exc)
            _MANIFEST_CACHE = []
    return _MANIFEST_CACHE


def _to_report(entry: dict) -> CanonReport:
    pd = entry.get("publication_date")
    doc_date = None
    if pd:
        try:
            doc_date = date.fromisoformat(pd)
        except ValueError:
            doc_date = None
    return CanonReport(
        slug=entry["slug"],
        report_type=entry["report_type"],
        title=entry.get("title") or entry["slug"],
        summary=entry.get("summary"),
        celex=entry.get("celex"),
        doc_type=entry.get("doc_type"),
        legal_family=entry.get("legal_family"),
        languages=entry.get("languages", []),
        lang_urls=entry.get("lang_urls", {}),
        eurlex_url=entry.get("eurlex_url"),
        public_url=entry.get("public_url"),
        document_date=doc_date,
        # body_txt / body_html / creation_date stay null (contract: present, null).
    )


def _load_bodies(db: Session, slugs: list[str], lang: str) -> Dict[str, tuple[Optional[str], Optional[str]]]:
    """Batch-load (body_html, body_txt) for the given canon slugs in `lang`
    from the proprietary_report_bodies cache (migration 087). Falls back to the
    English body when the requested language isn't cached for a slug. Bodies are
    served from the DB because Railway cannot fetch SiteGround (datacenter IP
    block) and frontend/public isn't in the backend build context.
    """
    if not slugs:
        return {}
    want = lang if lang in _LANGS else "en"
    rows = db.execute(
        text("""
            SELECT ref, lang, body_html, body_txt
            FROM public.proprietary_report_bodies
            WHERE source = 'canon' AND ref = ANY(:slugs) AND lang IN (:want, 'en')
        """),
        {"slugs": slugs, "want": want},
    ).fetchall()
    # Prefer the requested language; fall back to English.
    out: Dict[str, tuple[Optional[str], Optional[str]]] = {}
    en_only: Dict[str, tuple[Optional[str], Optional[str]]] = {}
    for ref, lg, html, txt in rows:
        if lg == want:
            out[ref] = (html, txt)
        elif lg == "en":
            en_only[ref] = (html, txt)
    for ref, val in en_only.items():
        out.setdefault(ref, val)
    return out


# --------------------------------------------------------------------------- #
# Endpoints                                                                   #
# --------------------------------------------------------------------------- #

@router.get(
    "",
    response_model=PaginatedResponse[CanonReport],
    summary="List every Brubru deep-dive report — the EU Canon + law deep-dives",
    description="""**What it does**
Returns Brubru's catalogue of hand-built HTML deep-dive reports: the **EU Canon** (article-by-article explainers of binding EU laws, e.g. the AI Act, CRR, MiCA) and the **law deep-dives** (thematic explainers, e.g. the Biotech Act, Critical Medicines Act, EU Inc.). With no filters this enumerates the **entire** catalogue, each entry carrying its public URL and the languages it is published in.

**When to use it**
Discover which laws Brubru has a published deep-dive for, link to the citizen-facing report, or pick a `slug` to fetch the full body via `/canon/{slug}`. Filter to one report type or one legal family to build a topic index.

**Input**
- `report_type` — `canon` (EU Canon) or `deep_dive` (law deep-dives). Omit for both.
- `q` — substring over title, summary, slug, CELEX.
- `legal_family` — cluster tag (e.g. `anti_subsidy_trade_remedies`, `eu_pharmaceutical`).
- `language` — keep only reports published in this language (en/es/ca/fr/it/nl).
- `limit` (1-100, default 50), `page` (1-indexed).

**Try it**
```
GET /api/v2/proprietary/canon
GET /api/v2/proprietary/canon?report_type=canon&legal_family=eu_pharmaceutical
GET /api/v2/proprietary/canon?q=AI%20Act
```

**You get back**
A `PaginatedResponse[CanonReport]`. Each item: `slug`, `report_type`, `title`, `summary`, `celex`, `doc_type`, `legal_family`, `languages[]`, `lang_urls{}`, `eurlex_url`, plus the 5 datapoints — including the **fully populated `body_html` + `body_txt`** (the rendered report and its plain-text rendering, in the `language` edition or English). `public_url` is the language page; `document_date` is the act's publication date for canon entries.

**Data freshness**
Brubru-curated. New reports ship via the `/canon` skill; the manifest is regenerated by `scripts/build_canon_manifest.py` and bodies re-seeded by `scripts/seed_proprietary_bodies.py`.""",
)
async def list_canon(
    request: Request,
    report_type: Optional[str] = Query(None, description="canon | deep_dive (omit for both)"),
    q: Optional[str] = Query(None, description="Substring over title, summary, slug, CELEX"),
    legal_family: Optional[str] = Query(None, description="Legal-family cluster tag (e.g. eu_pharmaceutical)"),
    language: Optional[str] = Query(None, description="Keep only reports published in this language (en/es/ca/fr/it/nl); also the body edition returned"),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CanonReport]:
    reports = _load_manifest()

    if report_type:
        rt = report_type.strip().lower()
        if rt not in _REPORT_TYPES:
            raise HTTPException(
                status_code=400,
                detail={"error": f"Unknown report_type {report_type!r}", "reason_code": "invalid_parameter",
                        "valid_values": sorted(_REPORT_TYPES)},
            )
        reports = [r for r in reports if r.get("report_type") == rt]
    if legal_family:
        lf = legal_family.strip().lower()
        reports = [r for r in reports if (r.get("legal_family") or "").lower() == lf]
    if language:
        lang = language.strip().lower()
        reports = [r for r in reports if lang in (r.get("languages") or [])]
    if q:
        ql = q.strip().lower()
        reports = [
            r for r in reports
            if ql in (r.get("title") or "").lower()
            or ql in (r.get("summary") or "").lower()
            or ql in (r.get("slug") or "").lower()
            or ql in (r.get("celex") or "").lower()
        ]

    total = len(reports)
    start = (page - 1) * limit
    page_items = [_to_report(r) for r in reports[start:start + limit]]

    # Populate body_html + body_txt from the DB cache for this page.
    body_lang = (language or "en").strip().lower()
    bodies = _load_bodies(db, [it.slug for it in page_items], body_lang)
    for it in page_items:
        html, txt = bodies.get(it.slug, (None, None))
        it.body_html, it.body_txt = html, txt

    return build_envelope(
        page_items, total=total, page=page, limit=limit,
        op_core_title="Brubru deep-dive reports — EU Canon + law deep-dives",
        op_core_type="Brubru deep-dive report catalogue",
        op_core_identifier=str(request.url),
        op_core_referenced_by=["https://brubru.beresol.eu/eucanon/", "/api/v2/proprietary/guides"],
    )


@router.get(
    "/{slug}",
    response_model=CanonReport,
    summary="One Brubru deep-dive report by slug — optional inlined body",
    description="""**What it does**
Returns one Brubru deep-dive report (EU Canon entry or law deep-dive) by its slug, optionally with the full rendered HTML body inlined in the requested language.

**When to use it**
After locating a report via the list endpoint, fetch its metadata — and, with `include_body=true`, the full rendered article-by-article explainer — for display or downstream processing.

**Input**
- `slug` (path) — the report slug, e.g. `2024-1689_aiact`, `2013-575_crr`, `biotech-act`.
- `lang` (optional, default `en`) — which language edition to return for `body_html` / `body_txt` (falls back to English if that edition isn't published).
- `include_body` (optional, default `true`) — set `false` to omit the body and return metadata only (lighter response).

**Try it**
```
GET /api/v2/proprietary/canon/2024-1689_aiact
GET /api/v2/proprietary/canon/2024-1689_aiact?lang=ca
GET /api/v2/proprietary/canon/2024-1689_aiact?include_body=false
```

**You get back**
A single `CanonReport`: `slug`, `report_type`, `title`, `summary`, `celex`, `doc_type`, `legal_family`, `languages[]`, `lang_urls{}`, `eurlex_url`, plus the 5 datapoints with **`body_html` + `body_txt` populated by default** (the rendered report + its plain-text rendering, served from the DB body cache). HTTP 404 (`reason_code: not_found`) for an unknown slug.

**Data freshness**
Brubru-curated. Bodies are seeded by `scripts/seed_proprietary_bodies.py` and re-seeded when a report changes.""",
)
async def get_canon(
    slug: str = PathParam(..., description="Report slug (e.g. '2024-1689_aiact', 'biotech-act')"),
    lang: str = Query("en", description="Body language edition to return (en/es/ca/fr/it/nl); falls back to English."),
    include_body: bool = Query(True, description="Default true — set false to omit body_html/body_txt for a lighter response."),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> CanonReport:
    entry = next((r for r in _load_manifest() if r.get("slug") == slug), None)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "Report not found", "reason_code": "not_found", "resource": "canon-report", "slug": slug},
        )
    report = _to_report(entry)

    if include_body:
        bodies = _load_bodies(db, [slug], lang.strip().lower())
        report.body_html, report.body_txt = bodies.get(slug, (None, None))

    return report
