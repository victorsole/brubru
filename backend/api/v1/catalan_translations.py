"""
/api/v1/catalan-translations — open data: the EU acquis in Catalan.

OPEN-SOURCE / FREE TIER
========================
Unlike the rest of /api/v1/*, this surface is NOT gated by X-API-Key.
The underlying corpus is published under the MIT licence (see the
landing page footer at https://brubru.beresol.eu/legislacio-ue-catala/);
gating it would be at odds with that licence. Free public endpoints
share the global rate-limit middleware; no per-key tier is enforced.

The /api/v1/catalan-translations namespace exposes the binding-law
subset of the corpus only — sector-3 acts whose CELEX matches
``^3[0-9]{4}[RLD][0-9]{4}$`` (Regulations, Directives, Decisions). The
257 OJ C/L-series fragments imported under the broader sweep are
filtered out at SQL level until the audit pipeline reclassifies them.

Endpoints
---------
- GET  /api/v1/catalan-translations            List + filter (paginated)
- GET  /api/v1/catalan-translations/stats      Aggregate counts
- GET  /api/v1/catalan-translations/{celex}    Single record (?body=html opt-in)

Created: 7 May 2026 — Dia d'Europa launch.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, or_, text
from sqlalchemy.orm import Session

from core.database import get_db
from models.catalan_translation import CatalanTranslation

from ._body import body_from_html, body_threshold_param
from ._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalan-translations", tags=["v1-catalan-translations"])

# Binding-law CELEX (sector 3, forms R/L/D). Matches the filter we put on
# batch_catalan_translate.py --binding-only. Excludes OJ C/L-series notice
# fragments imported beyond the canonical 8,710 set.
BINDING_CELEX_SQL = r"^3\d{4}[RLD]\d{4}$"

LANDING_BASE = "https://brubru.beresol.eu/legislacio-ue-catala/"
EURLEX_BASE = "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:"

# Local on-disk path to rendered Catalan HTML — used as a fallback for dev
# environments where the files live alongside the backend. In production
# (Railway) the files live on SiteGround, fetched via HTTP from ca_url
# (https://brubru.beresol.eu/legislacio-ue-catala/{celex}/).
DISK_TRANSLATIONS_DIR = (
    Path(__file__).resolve().parents[3] / "data" / "legislacio-ue-catala"
)

# In-memory cache for fetched HTML bodies — partner-facing public endpoint
# so we don't refetch the same 50-500 KB body twice in a row. 6h TTL aligns
# with how often we re-render the upstream HTML.
_HTML_CACHE: Dict[str, Tuple[float, str]] = {}
_HTML_CACHE_TTL_S = 6 * 60 * 60
_HTML_CACHE_MAX = 200  # rough cap on resident bodies


def _fetch_ca_body_html(celex: str, ca_url: str) -> Optional[str]:
    """Fetch the rendered Catalan HTML body for a CELEX.

    Resolution order:
      1. In-memory cache (6h TTL).
      2. Local disk (dev — DISK_TRANSLATIONS_DIR).
      3. HTTP from `ca_url` on SiteGround (production).

    Returns None if no copy is available — the caller leaves body_html=None
    and the partner falls back to ca_url client-side. We never 500 on a
    fetch miss.
    """
    now = time.time()
    cached = _HTML_CACHE.get(celex)
    if cached and (now - cached[0]) < _HTML_CACHE_TTL_S:
        return cached[1]

    # Local disk first (fastest in dev)
    disk_path = DISK_TRANSLATIONS_DIR / celex / "index.html"
    if disk_path.is_file():
        try:
            html = disk_path.read_text(encoding="utf-8", errors="replace")
            _cache_body(celex, html)
            return html
        except OSError as exc:
            logger.warning("disk read failed for %s: %s", celex, exc)

    # HTTP fetch from SiteGround (production). Use urllib over httpx because
    # httpx had silent failures on Railway egress; urllib + explicit logging
    # surfaces the failure mode (DNS / TLS / rate-limit / 403) instead of
    # swallowing it.
    import urllib.request
    import urllib.error

    try:
        req = urllib.request.Request(
            ca_url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)",
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "ca,en;q=0.9",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            status = resp.status
            content = resp.read()
            if status == 200 and len(content) > 500:
                html = content.decode("utf-8", errors="replace")
                _cache_body(celex, html)
                logger.info("ca_url fetch ok for %s: %d bytes", celex, len(content))
                return html
            logger.warning(
                "ca_url fetch for %s: HTTP %s, %d bytes (too short or non-200)",
                celex, status, len(content),
            )
    except urllib.error.HTTPError as exc:
        logger.warning("ca_url HTTPError for %s [%s]: %s — %s", celex, ca_url, exc.code, exc.reason)
    except urllib.error.URLError as exc:
        logger.warning("ca_url URLError for %s [%s]: %s", celex, ca_url, exc.reason)
    except Exception as exc:
        logger.warning("ca_url fetch failed for %s [%s]: %s", celex, ca_url, exc)

    return None


def _cache_body(celex: str, html: str) -> None:
    """Add to the LRU-ish cache; evict oldest when over cap."""
    if len(_HTML_CACHE) >= _HTML_CACHE_MAX:
        # Evict the oldest entry (cheap, this is bounded by _HTML_CACHE_MAX)
        oldest = min(_HTML_CACHE.items(), key=lambda kv: kv[1][0])[0]
        _HTML_CACHE.pop(oldest, None)
    _HTML_CACHE[celex] = (time.time(), html)


# Doc-type shorthand mapping — partners often expect CELEX-form letters
# (R = Regulation, L = Directive, D = Decision). The DB stores the long
# form. Normalise the query input so both work.
_DOC_TYPE_SHORTHAND = {
    "R": "regulation",
    "L": "directive",
    "D": "decision",
    "REG": "regulation",
    "DIR": "directive",
    "DEC": "decision",
}


def _normalise_doc_type(value: str) -> str:
    """Accept R/L/D shorthand alongside long form."""
    if not value:
        return value
    upper = value.strip().upper()
    return _DOC_TYPE_SHORTHAND.get(upper, value.strip().lower())


def _slugify(s: str) -> str:
    """ASCII-only kebab-case for category slug-matching."""
    if not s:
        return ""
    # Replace accented chars; keep alphanumerics; collapse to dashes
    norm = (
        s.lower()
        .replace("à", "a").replace("á", "a").replace("ä", "a").replace("â", "a")
        .replace("è", "e").replace("é", "e").replace("ë", "e").replace("ê", "e")
        .replace("ì", "i").replace("í", "i").replace("ï", "i").replace("î", "i")
        .replace("ò", "o").replace("ó", "o").replace("ö", "o").replace("ô", "o")
        .replace("ù", "u").replace("ú", "u").replace("ü", "u").replace("û", "u")
        .replace("ñ", "n").replace("ç", "c").replace("·", "")
    )
    norm = re.sub(r"[^a-z0-9]+", "-", norm).strip("-")
    return norm


def _filter_by_category(qry, column_name: str, value: str):
    """Filter on category / category_en supporting exact, ILIKE, and slug forms.

    Matches if any of:
      - exact match (case-sensitive)
      - case-insensitive substring (ILIKE %value%)
      - slugified DB column equals slugified user input — built in SQL via
        regexp_replace + lower, so e.g. ``core-economic-and-market-policies``
        matches ``Core Economic and Market Policies``.

    Uses ``regexp_replace`` on the DB column (Postgres). Index-less because
    the table is small (≤8,710 rows); for larger corpora we'd add a stored
    slug column with an index.
    """
    column = getattr(CatalanTranslation, column_name)
    user_slug = _slugify(value)
    # SQL slug expression: unaccent + lowercase + collapse non-alphanumerics
    # to "-" (matches what _slugify() produces in Python). The `unaccent`
    # extension was installed on the DB to fold accented chars (Catalan
    # categories like "Polítiques econòmiques i de mercat" → "politiques-...").
    db_slug = func.regexp_replace(
        func.unaccent(func.lower(column)),
        r"[^a-z0-9]+",
        "-",
        "g",
    )
    qry = qry.filter(or_(
        column == value,
        func.lower(column).contains(value.lower()),
        func.trim(db_slug, "-") == user_slug,
    ))
    return qry


# --------------------------------------------------------------------------- #
# Pydantic schemas                                                            #
# --------------------------------------------------------------------------- #

class CatalanTranslationItem(BaseModel):
    """One translated EU legal act in Catalan."""

    model_config = ConfigDict(from_attributes=True)

    celex: str = Field(..., description="CELEX identifier (sector 3, form R/L/D).")
    oj_reference: Optional[str] = Field(None, description="Official Journal reference (L-series).")
    doc_type: Optional[str] = Field(None, description="regulation | directive | decision | delegated | implementing | treaty")
    short_name: Optional[str] = Field(None, description="Common short name where known (GDPR, AI Act, MiFID II...).")
    title_ca: Optional[str] = Field(None, description="Title in Catalan.")
    title_en: Optional[str] = Field(None, description="Title in English (source).")
    category: Optional[str] = Field(None, description="Brubru top-level category (Catalan).")
    category_en: Optional[str] = Field(None, description="Brubru top-level category (English).")
    subcategory: Optional[str] = Field(None, description="More granular tag where assigned.")
    articles_count: Optional[int] = None
    recitals_count: Optional[int] = None
    html_size_bytes: Optional[int] = None
    engine: Optional[str] = Field(None, description="Translation engine: softcatala (NMT) or sonnet (Claude).")
    source_format: Optional[str] = Field(None, description="Source XML format — currently 'formex' (Formex V4).")
    ca_url: str = Field(..., description="Canonical Catalan HTML rendering on brubru.beresol.eu.")
    source_eurlex_url: str = Field(..., description="EUR-Lex landing page for the original act (multilingual).")
    translated_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class CatalanTranslationDetail(CatalanTranslationItem):
    """Single-record response — extends the list item with optional body inlining.

    Body fields follow the v1 contract used across the rest of the API:
      - has_body: bool — true iff a body is available upstream (>=
        body_threshold chars). Computed from html_size_bytes so partners
        can branch before requesting the body.
      - body_html / body_text — populated only when ?body=html is requested
        on this endpoint. body_html is the raw upstream HTML; body_text is
        the stripped plain-text rendering.
    """

    has_body: bool = Field(
        False,
        description="True if a Catalan-rendered body is available for this act (html_size_bytes >= body_threshold).",
    )
    body_html: Optional[str] = Field(
        None,
        description="Rendered Catalan HTML body. Populated only when `?body=html` is requested. May be null if the upstream file is unreachable — fall back to ca_url.",
    )
    body_txt: Optional[str] = Field(
        None,
        description="Plain-text rendering of body_html (HTML stripped). Populated only when `?body=html` is requested.",
    )


class CategoryCount(BaseModel):
    category: Optional[str]
    category_en: Optional[str]
    count: int


class DocTypeCount(BaseModel):
    doc_type: Optional[str]
    count: int


class EngineCount(BaseModel):
    engine: Optional[str]
    count: int


class CatalanStats(BaseModel):
    """Aggregate counts over the binding-law subset."""

    total: int = Field(..., description="Total binding-law translations available.")
    target: int = Field(8710, description="Canonical EU binding-law count we converge to.")
    coverage_pct: float = Field(..., description="100 * total / target, capped at 100.")
    by_doc_type: list[DocTypeCount]
    by_category: list[CategoryCount]
    by_engine: list[EngineCount]
    last_translated_at: Optional[datetime] = None
    licence: str = Field("MIT", description="Translations are MIT-licensed; redistribution permitted with attribution.")


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

def _ca_url(celex: str) -> str:
    return f"{LANDING_BASE}{celex}/"


def _eurlex_url(celex: str) -> str:
    return f"{EURLEX_BASE}{celex}"


def _row_to_item(row: CatalanTranslation) -> CatalanTranslationItem:
    return CatalanTranslationItem(
        celex=row.celex,
        oj_reference=row.oj_reference,
        doc_type=row.doc_type,
        short_name=row.short_name,
        title_ca=row.title_ca,
        title_en=row.title_en,
        category=row.category,
        category_en=row.category_en,
        subcategory=row.subcategory,
        articles_count=row.articles_count,
        recitals_count=row.recitals_count,
        html_size_bytes=row.html_size_bytes,
        engine=row.engine,
        source_format=row.source_format,
        ca_url=_ca_url(row.celex),
        source_eurlex_url=_eurlex_url(row.celex),
        translated_at=row.translated_at,
        updated_at=row.updated_at,
    )


def _binding_law_filter(query):
    """Apply the binding-law CELEX filter at SQL level.

    Hides the 257 OJ C/L-series notice fragments imported beyond the
    canonical 8,710 set — we don't promote those to the paid v1 surface
    until the audit pipeline reclassifies them.
    """
    return query.filter(
        and_(
            CatalanTranslation.file_type == "main",
            CatalanTranslation.celex.op("~")(BINDING_CELEX_SQL),
        )
    )


# --------------------------------------------------------------------------- #
# Endpoints                                                                   #
# --------------------------------------------------------------------------- #

@router.get(
    "",
    response_model=PaginatedResponse[CatalanTranslationItem],
    summary="List EU binding laws translated into Catalan / Llista lleis vinculants UE traduïdes al català",
    description=(
        "## English\n\n"
        "**What it does.** Returns a paginated catalogue of binding EU legal acts (Regulations, Directives, Decisions) translated into Catalan by Brubru using the Softcatalà NMT engine.\n\n"
        "**When to use it.** When you want to browse, search, or sync the Catalan translation corpus — e.g. populate a search index, build a per-category dashboard, or pull updates incrementally via `updated_from`.\n\n"
        "**Input.**\n"
        "- `q` — substring search across `title_ca`, `title_en`, `short_name`, `celex` (e.g. `q=GDPR`).\n"
        "- `celex` — exact CELEX filter (e.g. `32016R0679`).\n"
        "- `doc_type` — accepts long form (`regulation`/`directive`/`decision`/`delegated`/`implementing`) **or** CELEX shorthand (`R`/`L`/`D`).\n"
        "- `category`, `category_en` — exact name OR slug (e.g. `category_en=core-economic-and-market-policies`). Use `/stats` to discover names.\n"
        "- `engine` — `softcatala` (default for 8,257 rows) or `sonnet` (Claude-translated, currently 1 row).\n"
        "- `updated_from` / `updated_to` — incremental sync against `updated_at`.\n"
        "- `limit` 1–200 (default 50); `page` 1+.\n\n"
        "**Try it.** `GET /api/v1/catalan-translations?q=GDPR&limit=3` (no API key required).\n\n"
        "**You get back.** Per row: `celex`, `doc_type`, `short_name`, `title_ca`, `title_en`, `category`/`category_en`, `articles_count`, `recitals_count`, `html_size_bytes`, `engine`, `ca_url` (canonical render on `brubru.beresol.eu`), `source_eurlex_url`, timestamps.\n\n"
        "**Open data.** No API key required. MIT-licensed. Subject to the standard global rate limit.\n\n"
        "---\n\n"
        "## Català\n\n"
        "**Què fa.** Retorna un catàleg paginat dels actes legals vinculants de la UE (Reglaments, Directives, Decisions) traduïts al català per Brubru amb el motor de traducció automàtica de Softcatalà.\n\n"
        "**Quan fer-ho servir.** Per consultar, cercar o sincronitzar el corpus de traduccions — per exemple, omplir un índex de cerca, fer un panell per categoria o baixar les novetats amb `updated_from`.\n\n"
        "**Entrada.**\n"
        "- `q` — cerca de subcadena a `title_ca`, `title_en`, `short_name`, `celex` (ex.: `q=GDPR`).\n"
        "- `celex` — filtre CELEX exacte (ex.: `32016R0679`).\n"
        "- `doc_type` — accepta forma llarga (`regulation`/`directive`/`decision`/`delegated`/`implementing`) **o** abreviatura CELEX (`R`/`L`/`D`).\n"
        "- `category`, `category_en` — nom exacte o slug. Mira `/stats` per veure els noms disponibles.\n"
        "- `engine` — `softcatala` (per defecte, 8.257 files) o `sonnet` (Claude, 1 fila).\n"
        "- `updated_from` / `updated_to` — sincronització incremental sobre `updated_at`.\n"
        "- `limit` 1–200 (per defecte 50); `page` 1+.\n\n"
        "**Prova-ho.** `GET /api/v1/catalan-translations?q=GDPR&limit=3` (sense clau API).\n\n"
        "**Què obtens.** Per fila: `celex`, `doc_type`, `short_name`, `title_ca`, `title_en`, `category`/`category_en`, `articles_count`, `recitals_count`, `html_size_bytes`, `engine`, `ca_url` (rendització canònica a `brubru.beresol.eu`), `source_eurlex_url`, marques de temps.\n\n"
        "**Dades obertes.** No cal clau API. Llicència MIT. Subjecte al límit de freqüència global estàndard.\n\n"
        "---\n\n"
        "**Data freshness.** Brubru-generated content (not synced from external sources). New translations are added by the `/catalan` skill in a separate conversation; the corpus grows by tens of acts per week. Daily sync of disk-to-DB via `backend/scripts/sync_catalan_disk_to_db.py`.\n\n"
        "**Actualització de dades.** Contingut generat per Brubru (no se sincronitza des de fonts externes). Es generen noves traduccions amb l'skill `/catalan` en una conversa separada; el corpus creix per desenes d'actes a la setmana. Sincronització diària de disc a BD mitjançant `backend/scripts/sync_catalan_disk_to_db.py`."
    ),
)
async def list_catalan_translations(
    request: Request,
    q: Optional[str] = Query(None, description="Substring search across title_ca, title_en, short_name, celex."),
    celex: Optional[str] = Query(None, description="Exact CELEX filter."),
    doc_type: Optional[str] = Query(None, description="regulation | directive | decision | delegated | implementing | treaty."),
    category: Optional[str] = Query(None, description="Brubru category (Catalan name) — see /stats for the full list."),
    category_en: Optional[str] = Query(None, description="Brubru category (English name)."),
    engine: Optional[str] = Query(None, description="softcatala | sonnet"),
    updated_from: Optional[datetime] = Query(None, description="Incremental sync — rows with updated_at >= value."),
    updated_to: Optional[datetime] = Query(None, description="Incremental sync upper bound — rows with updated_at <= value."),
    limit: int = Query(50, ge=1, le=200, description="Items per page (default 50, max 200)."),
    page: int = Query(1, ge=1),
    db: Session = Depends(get_db),
) -> PaginatedResponse[CatalanTranslationItem]:
    qry = _binding_law_filter(db.query(CatalanTranslation))

    if q:
        term = f"%{q}%"
        qry = qry.filter(
            or_(
                CatalanTranslation.title_ca.ilike(term),
                CatalanTranslation.title_en.ilike(term),
                CatalanTranslation.short_name.ilike(term),
                CatalanTranslation.celex.ilike(term),
            )
        )
    if celex:
        qry = qry.filter(CatalanTranslation.celex == celex)
    if doc_type:
        # Accept R/L/D shorthand alongside long form (regulation/directive/decision)
        qry = qry.filter(CatalanTranslation.doc_type == _normalise_doc_type(doc_type))
    if category:
        qry = _filter_by_category(qry, "category", category)
    if category_en:
        qry = _filter_by_category(qry, "category_en", category_en)
    if engine:
        qry = qry.filter(CatalanTranslation.engine == engine.lower())
    if updated_from:
        qry = qry.filter(CatalanTranslation.updated_at >= updated_from)
    if updated_to:
        qry = qry.filter(CatalanTranslation.updated_at <= updated_to)

    total = qry.count()
    rows = (
        qry.order_by(CatalanTranslation.celex.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    items = [_row_to_item(r) for r in rows]

    return build_envelope(
        items=items,
        total=total,
        page=page,
        limit=limit,
        updated_from=updated_from,
        updated_to=updated_to,
        op_core_title="EU binding-law corpus translated into Catalan (Brubru, MIT)",
        op_core_type="EU legislation translation catalogue",
        op_core_identifier=str(request.url),
        op_core_language="ca",
        op_core_referenced_by=[
            "https://brubru.beresol.eu/legislacio-ue-catala/",
            "/api/v1/laws",
        ],
    )


@router.get(
    "/stats",
    response_model=CatalanStats,
    summary="Catalan translations — aggregate counts / Estadístiques de les traduccions catalanes",
    description=(
        "## English\n\n"
        "**What it does.** Returns aggregate counts of Catalan-translated EU acts grouped by `doc_type`, `category` (Catalan + English names), and `engine`, plus the canonical 8,710 target and current coverage percentage.\n\n"
        "**When to use it.** Build a coverage dashboard, verify ingestion before pulling pages, or discover the canonical category names to use as filters on the list endpoint.\n\n"
        "**Input.** No parameters.\n\n"
        "**Try it.** `GET /api/v1/catalan-translations/stats` (no API key required).\n\n"
        "**You get back.**\n"
        "- `total` — current count of binding-law translations\n"
        "- `target` — canonical 8,710 EU binding-law set\n"
        "- `coverage_pct` — `100 * total / target`, capped at 100\n"
        "- `by_doc_type[]` — `{doc_type, count}` for `regulation` / `directive` / `decision` / `delegated` / `implementing`\n"
        "- `by_category[]` — `{category, category_en, count}` (use these names for the `category` / `category_en` filters)\n"
        "- `by_engine[]` — `{engine, count}` (`softcatala` vs `sonnet`)\n"
        "- `last_translated_at` — timestamp of the most recent ingestion\n"
        "- `licence` — always `MIT`\n\n"
        "---\n\n"
        "## Català\n\n"
        "**Què fa.** Retorna comptadors agregats de les traduccions catalanes d'actes de la UE agrupats per `doc_type`, `category` (català + anglès) i `engine`, més l'objectiu canònic de 8.710 actes i el percentatge de cobertura actual.\n\n"
        "**Quan fer-ho servir.** Per construir un panell de cobertura, verificar la ingesta abans de descarregar pàgines, o descobrir els noms canònics de categoria que pots utilitzar com a filtres al llistat.\n\n"
        "**Entrada.** Cap paràmetre.\n\n"
        "**Prova-ho.** `GET /api/v1/catalan-translations/stats` (sense clau API).\n\n"
        "**Què obtens.**\n"
        "- `total` — comptador actual de traduccions de dret vinculant\n"
        "- `target` — conjunt canònic de 8.710 actes vinculants de la UE\n"
        "- `coverage_pct` — `100 * total / target`, limitat a 100\n"
        "- `by_doc_type[]` — `{doc_type, count}` per `regulation` / `directive` / `decision` / `delegated` / `implementing`\n"
        "- `by_category[]` — `{category, category_en, count}` (fes servir aquests noms als filtres `category` / `category_en`)\n"
        "- `by_engine[]` — `{engine, count}` (`softcatala` vs `sonnet`)\n"
        "- `last_translated_at` — marca de temps de la ingesta més recent\n"
        "- `licence` — sempre `MIT`\n\n"
        "---\n\n"
        "**Data freshness.** Live aggregate query over the `catalan_translations` table on each request. The underlying table grows as new translations are added via the `/catalan` skill (Brubru-curated, not synced from external sources).\n\n"
        "**Actualització de dades.** Consulta agregada en directe a la taula `catalan_translations` a cada petició. La taula creix amb les noves traduccions generades amb l'skill `/catalan` (contingut Brubru, no se sincronitza des de fonts externes)."
    ),
)
async def catalan_translations_stats(db: Session = Depends(get_db)) -> CatalanStats:
    base = _binding_law_filter(db.query(CatalanTranslation))
    total = base.count()

    by_doc = (
        _binding_law_filter(db.query(CatalanTranslation.doc_type, func.count().label("n")))
        .group_by(CatalanTranslation.doc_type)
        .order_by(func.count().desc())
        .all()
    )
    by_cat = (
        _binding_law_filter(
            db.query(
                CatalanTranslation.category,
                CatalanTranslation.category_en,
                func.count().label("n"),
            )
        )
        .group_by(CatalanTranslation.category, CatalanTranslation.category_en)
        .order_by(func.count().desc())
        .all()
    )
    by_eng = (
        _binding_law_filter(db.query(CatalanTranslation.engine, func.count().label("n")))
        .group_by(CatalanTranslation.engine)
        .order_by(func.count().desc())
        .all()
    )
    last_translated = base.with_entities(func.max(CatalanTranslation.translated_at)).scalar()

    target = 8710
    coverage = min(100.0, round(100.0 * total / target, 2)) if target else 0.0

    return CatalanStats(
        total=total,
        target=target,
        coverage_pct=coverage,
        by_doc_type=[DocTypeCount(doc_type=d[0], count=d[1]) for d in by_doc],
        by_category=[
            CategoryCount(category=c[0], category_en=c[1], count=c[2]) for c in by_cat
        ],
        by_engine=[EngineCount(engine=e[0], count=e[1]) for e in by_eng],
        last_translated_at=last_translated,
        licence="MIT",
    )


@router.get(
    "/{celex}",
    response_model=CatalanTranslationDetail,
    response_model_exclude_none=False,
    summary="Look up one Catalan translation by its EU legal identifier / Una traducció catalana per identificador legal",
    description=(
        "## English\n\n"
        "**What it does.** Returns one Catalan-translated EU act by its CELEX number.\n\n"
        "**When to use it.** When you have a CELEX and want the Catalan translation's metadata, optionally with the full rendered body inlined.\n\n"
        "**Input.**\n"
        "- `celex` (path) — CELEX number (sector 3, forms R/L/D), e.g. `32016R0679` (GDPR), `32024R1689` (AI Act).\n"
        "- `body=html` (optional query param) — inlines the rendered Catalan HTML body (typically 50-500 KB) into `body_html` + a stripped plain-text version into `body_text`.\n"
        "- `body_threshold` (optional, default 500) — minimum char length for `has_body=true`.\n\n"
        "**Try it.**\n"
        "- `GET /api/v1/catalan-translations/32016R0679` — metadata only\n"
        "- `GET /api/v1/catalan-translations/32016R0679?body=html` — metadata + inlined body\n\n"
        "**You get back.** All the list fields plus:\n"
        "- `has_body` — bool, true iff a Catalan render is available (`html_size_bytes >= body_threshold`)\n"
        "- `body_html` — full rendered HTML (only when `?body=html`)\n"
        "- `body_text` — HTML stripped to plain text (only when `?body=html`)\n\n"
        "**404** when the CELEX is outside the binding-law corpus, or when no Catalan translation exists yet.\n\n"
        "---\n\n"
        "## Català\n\n"
        "**Què fa.** Retorna un acte legal de la UE traduït al català pel seu CELEX.\n\n"
        "**Quan fer-ho servir.** Quan tens un CELEX i vols les metadades de la traducció catalana, opcionalment amb el cos sencer en línia.\n\n"
        "**Entrada.**\n"
        "- `celex` (ruta) — CELEX (sector 3, formes R/L/D), p. ex. `32016R0679` (RGPD), `32024R1689` (Llei d'IA).\n"
        "- `body=html` (paràmetre opcional) — incorpora l'HTML català renderitzat (50-500 KB típicament) a `body_html` + una versió en text pla a `body_text`.\n"
        "- `body_threshold` (opcional, per defecte 500) — longitud mínima de caràcters perquè `has_body=true`.\n\n"
        "**Prova-ho.**\n"
        "- `GET /api/v1/catalan-translations/32016R0679` — només metadades\n"
        "- `GET /api/v1/catalan-translations/32016R0679?body=html` — metadades + cos en línia\n\n"
        "**Què obtens.** Tots els camps de la llista més:\n"
        "- `has_body` — booleà, cert si hi ha una rendització catalana disponible (`html_size_bytes >= body_threshold`)\n"
        "- `body_html` — HTML renderitzat sencer (només amb `?body=html`)\n"
        "- `body_text` — HTML convertit a text pla (només amb `?body=html`)\n\n"
        "**404** quan el CELEX queda fora del corpus de dret vinculant o no existeix encara cap traducció catalana.\n\n"
        "---\n\n"
        "**Data freshness.** Brubru-curated content (not synced from external sources). Translations are generated by the `/catalan` skill using the Softcatalà NMT engine (default) or Claude Sonnet (high-quality opt-in). New translations land in the DB via daily disk-to-DB sync.\n\n"
        "**Actualització de dades.** Contingut Brubru (no se sincronitza des de fonts externes). Les traduccions es generen amb l'skill `/catalan` mitjançant el motor NMT de Softcatalà (per defecte) o Claude Sonnet (opció premium). Les noves traduccions arriben a la BD amb la sincronització diària disc-a-BD."
    ),
)
async def get_catalan_translation(
    celex: str,
    body: Optional[str] = Query(
        None,
        description="Set to `html` to inline the rendered Catalan HTML body. / Posa `html` per incorporar el cos HTML renderitzat al català.",
    ),
    body_threshold: int = Depends(body_threshold_param),
    db: Session = Depends(get_db),
) -> CatalanTranslationDetail:
    if not re.match(BINDING_CELEX_SQL.replace(r"\d", r"[0-9]"), celex):
        raise HTTPException(
            status_code=404,
            detail=f"CELEX {celex} is outside the binding-law corpus (sector 3, forms R/L/D).",
        )

    row = (
        db.query(CatalanTranslation)
        .filter(
            CatalanTranslation.celex == celex,
            CatalanTranslation.file_type == "main",
        )
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"No Catalan translation for CELEX {celex}.")

    base = _row_to_item(row).model_dump()
    # Compute has_body from html_size_bytes (always available without
    # fetching the body) — partners can branch on this before deciding
    # whether to request ?body=html.
    has_body = bool(row.html_size_bytes and row.html_size_bytes >= body_threshold)

    detail = CatalanTranslationDetail(
        **base,
        has_body=has_body,
        body_html=None,
        body_txt=None,
    )

    if body and body.lower() == "html":
        html = _fetch_ca_body_html(celex, base["ca_url"])
        if html:
            # Use the shared body_from_html helper for consistency with the
            # rest of the v1 surface — same threshold semantics, same plain-
            # text strip rules.
            body_html, body_text, has = body_from_html(html, threshold=body_threshold)
            detail.body_html = body_html
            detail.body_text = body_text
            detail.has_body = has

    return detail
