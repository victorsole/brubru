"""
Packaging & Packaging Waste Regulation (PPWR) — /api/v2/proprietary/packaging-waste-regulation.

A single-call, marketing-ready brief on Regulation (EU) 2025/40 (PPWR), the EU's
first Regulation covering the whole packaging life-cycle. It repeals Directive
94/62/EC and **applies from 12 August 2026** (note: the act ENTERED INTO FORCE on
11 February 2025 — "12 August 2026" is the general date of APPLICATION, not entry
into force; do not conflate them).

Returns the regulation with the 5-datapoint contract, a curated phased-obligation
TIMELINE (the dates that actually bite: PFAS ban, recyclability grades, recycled
content, reuse targets, DRS), the delegated/implementing acts still moving (from
legislative_carriages), and the official Commission resources (guidance, FAQ,
facts, LEGISSUM) + Brubru deep-links.

Curated seed (verified against the PPWR knowledge guide + canon page, 11 Aug 2026);
in-force status / ELI are re-confirmed live from Cellar with a short budget and a
graceful fallback to the seed. Same pattern as textile_circularity.py.
Scope: read:knowledge. Policy family: climate-energy-environment.
"""
from __future__ import annotations

import asyncio
import html as _html
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/packaging-waste-regulation", tags=["v2-proprietary-ppwr"])

_LANGS = {"ca", "es", "en"}
_BRUBRU = "https://brubru.beresol.eu"
_CELEX = "32025R0040"

# --------------------------------------------------------------------------- #
# Curated seed — Regulation (EU) 2025/40 (PPWR).                               #
# Verified against knowledge_base/guides/ppwr_packaging_waste_regulation.md +  #
# frontend/public/eucanon/2025-40_ppwr/ on 11 Aug 2026.                        #
# --------------------------------------------------------------------------- #

_TITLES = {
    "en": "Packaging and Packaging Waste Regulation (PPWR)",
    "es": "Reglamento de envases y residuos de envases (PPWR)",
    "ca": "Reglament d'envasos i residus d'envasos (PPWR)",
}

# Phased-obligation timeline. Each entry: date + plain label (en/es/ca) + article.
# The dates that actually bite — the point of the endpoint for a compliance/marketing view.
_TIMELINE: List[Dict[str, Any]] = [
    {"date": "2025-02-11", "article": "Art. 71",
     "en": "Entry into force", "es": "Entrada en vigor", "ca": "Entrada en vigor"},
    {"date": "2025-07-12", "article": "Art. 40",
     "en": "Member States designate the competent authority", "es": "Los Estados miembros designan la autoridad competente", "ca": "Els Estats membres designen l'autoritat competent"},
    {"date": "2025-12-31", "article": "Art. 34",
     "en": "Max 40 lightweight plastic carrier bags per person per year", "es": "Máximo 40 bolsas de plástico ligeras por persona y año", "ca": "Màxim 40 bosses de plàstic lleugeres per persona i any"},
    {"date": "2026-02-12", "article": "Art. 44",
     "en": "First EPR implementing act; national producer registers set up", "es": "Primer acto de ejecución de RAP; registros nacionales de productores", "ca": "Primer acte d'execució de RAP; registres nacionals de productors"},
    {"date": "2026-08-12", "article": "Art. 3, 5, 12, 68",
     "en": "GENERAL DATE OF APPLICATION: PFAS ban on food-contact packaging; Directive 94/62/EC repealed; harmonised-label implementing acts due", "es": "FECHA GENERAL DE APLICACIÓN: prohibición de PFAS en envases alimentarios; derogación de la Directiva 94/62/CE; actos de ejecución de etiquetado armonizado", "ca": "DATA GENERAL D'APLICACIÓ: prohibició de PFAS en envasos alimentaris; derogació de la Directiva 94/62/CE; actes d'execució d'etiquetatge harmonitzat"},
    {"date": "2027-02-12", "article": "Art. 11, 25",
     "en": "Minimum-rotation delegated act; restricted-format guidelines", "es": "Acto delegado de rotaciones mínimas; directrices de formatos restringidos", "ca": "Acte delegat de rotacions mínimes; directrius de formats restringits"},
    {"date": "2027-06-30", "article": "Art. 30",
     "en": "Reuse-target calculation methodology adopted", "es": "Metodología de cálculo de objetivos de reutilización", "ca": "Metodologia de càlcul d'objectius de reutilització"},
    {"date": "2028-02-12", "article": "Art. 24",
     "en": "Sales packaging: empty space minimised", "es": "Envases de venta: espacio vacío minimizado", "ca": "Envasos de venda: espai buit minimitzat"},
    {"date": "2028-08-12", "article": "Art. 12, 13",
     "en": "Harmonised packaging labels + waste-receptacle labels", "es": "Etiquetas armonizadas de envases + etiquetas de contenedores", "ca": "Etiquetes harmonitzades d'envasos + etiquetes de contenidors"},
    {"date": "2029-01-01", "article": "Art. 48, 50",
     "en": "Deposit-return systems: 90% collection of plastic/metal beverage containers", "es": "Sistemas de depósito: 90% de recogida de envases de bebidas de plástico/metal", "ca": "Sistemes de dipòsit: 90% de recollida d'envasos de begudes de plàstic/metall"},
    {"date": "2030-01-01", "article": "Art. 6, 7, 24, 25, 29",
     "en": "Recyclability Grade C minimum; recycled-content targets; 50% empty-space cap; reuse targets (40% transport, 10% beverages); restricted-format ban", "es": "Grado C de reciclabilidad mínimo; contenido reciclado; tope 50% espacio vacío; objetivos de reutilización; prohibición de formatos restringidos", "ca": "Grau C de reciclabilitat mínim; contingut reciclat; límit 50% espai buit; objectius de reutilització; prohibició de formats restringits"},
    {"date": "2038-01-01", "article": "Art. 6",
     "en": "Grade C packaging banned — only Grade A or B may be placed on the market", "es": "Envases de grado C prohibidos: solo grado A o B", "ca": "Envasos de grau C prohibits: només grau A o B"},
]

# Official Commission / EUR-Lex resources (all verified live 11 Aug 2026).
_RESOURCES: List[Dict[str, str]] = [
    {"kind": "regulation", "publisher": "EUR-Lex", "title": "Regulation (EU) 2025/40 — full text (ELI)",
     "url": "https://eur-lex.europa.eu/eli/reg/2025/40/oj/eng"},
    {"kind": "summary", "publisher": "EUR-Lex", "title": "Summary of the PPWR (LEGISSUM)",
     "url": "https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=LEGISSUM:4806724"},
    {"kind": "official_page", "publisher": "DG ENV", "title": "PPWR — European Commission topic page",
     "url": "https://environment.ec.europa.eu/topics/waste-and-recycling/packaging-waste/packaging-packaging-waste-regulation_en"},
    {"kind": "facts", "publisher": "DG ENV", "title": "Facts about the new EU packaging rules",
     "url": "https://environment.ec.europa.eu/topics/waste-and-recycling/packaging-waste/facts-about-new-eu-rules-packaging-and-packaging-waste_en"},
    {"kind": "guidance", "publisher": "DG ENV", "title": "Guidance document on the PPWR",
     "url": "https://environment.ec.europa.eu/publications/guidance-document-packaging-and-packaging-waste-regulation-ppwr_en"},
    {"kind": "faq", "publisher": "DG ENV", "title": "FAQ on the PPWR",
     "url": "https://environment.ec.europa.eu/publications/faq-packaging-and-packaging-waste-regulation-ppwr_en"},
    {"kind": "implementation", "publisher": "DG ENV", "title": "PPWR implementation — Green Forum",
     "url": "https://green-forum.ec.europa.eu/packaging-and-packaging-waste-regulation-implementation_en"},
    {"kind": "delegated_decision", "publisher": "DG ENV", "title": "Delegated decision: pallet-wrappings and straps exemption",
     "url": "https://environment.ec.europa.eu/publications/commission-delegated-decision-exempting-certain-economic-operators-use-pallet-wrappings-and-straps_en"},
    {"kind": "news", "publisher": "DG ENV", "title": "Plastics — latest Commission news",
     "url": "https://environment.ec.europa.eu/topics/plastics/news_en"},
]

_REGULATION: Dict[str, Any] = {
    "celex": _CELEX,
    "eli": "http://data.europa.eu/eli/reg/2025/40/oj",
    "titles": _TITLES,
    "role": "The EU's first Regulation covering the whole packaging life-cycle — design, recycled content, reuse, labelling and waste management. Directly applicable; repeals Directive 94/62/EC.",
    "procedure_ref": "2022/0396(COD)",
    "document_date": "2024-12-19",           # signature
    "entry_into_force": "2025-02-11",
    "applies_from": "2026-08-12",
    "repeals": "Directive 94/62/EC (from 12 August 2026)",
    "structure": "13 chapters, 71 articles, 189 recitals, Annexes I-XIII",
    "deep_link": f"{_BRUBRU}/eucanon/2025-40_ppwr/",
    "guide_slugs": ["ppwr_packaging_waste_regulation", "eu_packaging_packaging_waste_2025_40"],
    "eurlex_url": f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{_CELEX}",
}

# Delegated / implementing acts still moving (resolved live from legislative_carriages).
_DELEGATED_REFS = ["2026/2631(DEA)"]  # pallet-wrappings & straps exemption (PPWR Art. 65)

# The regulation's own body = Brubru's PPWR knowledge guide (the article-by-article
# explainer, ~39 KB). Read the committed markdown file directly (ships in the Docker
# image; cheaper than KnowledgeLoader.load_all which loads every guide) and cache it.
# body_txt = the markdown; body_html = rendered (markdown lib, safe <pre> fallback).
_GUIDE_MD_PATH = Path(__file__).resolve().parents[3] / "knowledge_base" / "guides" / "ppwr_packaging_waste_regulation.md"
_BODY_CACHE: Optional[Tuple[Optional[str], Optional[str]]] = None


def _guide_body() -> Tuple[Optional[str], Optional[str]]:
    """(body_txt, body_html) from the committed PPWR guide. Cached. Own content
    (Brubru's PPWR explainer) — no fabrication."""
    global _BODY_CACHE
    if _BODY_CACHE is not None:
        return _BODY_CACHE
    txt: Optional[str] = None
    html: Optional[str] = None
    try:
        txt = _GUIDE_MD_PATH.read_text(encoding="utf-8")
        try:
            import markdown as _markdown

            html = _markdown.markdown(txt, extensions=["tables", "fenced_code", "sane_lists"])
        except Exception:  # noqa: BLE001 — markdown lib absent: safe, valid <pre> fallback
            html = f'<div class="brubru-guide"><pre>{_html.escape(txt)}</pre></div>'
    except Exception as exc:  # noqa: BLE001
        logger.warning("ppwr: guide body read failed (%s): %s", _GUIDE_MD_PATH, exc)
    _BODY_CACHE = (txt, html)
    return _BODY_CACHE


# --------------------------------------------------------------------------- #
# Response models                                                             #
# --------------------------------------------------------------------------- #

class _DataPoints(BaseModel):
    public_url: Optional[str] = Field(None, description="Citizen/machine deep-link (== deep_link).")
    body_txt: Optional[str] = Field(None, description="Plain-text body — null (see deep-link).")
    body_html: Optional[str] = Field(None, description="HTML body — null.")
    document_date: Optional[date] = Field(None, description="Signature/publication date of the act.")
    creation_date: Optional[datetime] = Field(None, description="When Brubru resolved this row.")


class TimelineEntry(BaseModel):
    date: date
    label: str = Field(..., description="Plain-language milestone in the requested lang.")
    article: Optional[str] = Field(None, description="The PPWR article the milestone comes from.")


class Resource(BaseModel):
    kind: str
    title: str
    url: str
    publisher: Optional[str] = None


class NewsRef(BaseModel):
    """A recent packaging/plastics news item, with its (already-backfilled) body."""
    title: str
    url: Optional[str] = None
    published: Optional[date] = None
    summary: Optional[str] = None
    body_txt: Optional[str] = Field(None, description="Full article body (backfilled in economy_items).")


class PpwrItem(_DataPoints):
    celex: Optional[str] = Field(None, description="CELEX (the regulation; null for pending delegated acts).")
    procedure_ref: Optional[str] = Field(None, description="OEIL procedure ref (delegated acts).")
    kind: str = Field(..., description="regulation | delegated_act.")
    eli: Optional[str] = Field(None, description="ELI permalink (null for acts not yet adopted).")
    title: str = Field(..., description="Plain-language title in the requested lang.")
    titles: Dict[str, str] = Field(default_factory=dict, description="Titles in ca/es/en.")
    role: str = Field(..., description="What this act is / why it matters.")
    status: str = Field(..., description="in_force | applies_soon | pending.")
    in_force: Optional[bool] = Field(None, description="Live in-force flag (Cellar).")
    entry_into_force: Optional[date] = Field(None, description="Entry-into-force date.")
    applies_from: Optional[date] = Field(None, description="General date of application (distinct from entry into force!).")
    days_until_application: Optional[int] = Field(None, description="Days from today to applies_from (negative if already applying).")
    structure: Optional[str] = Field(None, description="Structural summary (regulation only).")
    procedure_ref_reg: Optional[str] = Field(None, description="The regulation's own COD procedure ref.")
    repeals: Optional[str] = Field(None, description="What the act repeals.")
    timeline: List[TimelineEntry] = Field(default_factory=list, description="Phased-obligation dates (regulation only).")
    official_resources: List[Resource] = Field(default_factory=list, description="Official Commission / EUR-Lex resources (regulation only).")
    related_news: List[NewsRef] = Field(default_factory=list, description="Recent packaging & circular-economy news from Brubru's news corpus, with backfilled bodies (regulation only). Keyword-matched, so relevance is approximate.")
    latest_step: Optional[str] = Field(None, description="Latest legislative step (delegated acts).")
    deep_link: str = Field(..., description="Brubru deep-link (canon page or OEIL).")


# --------------------------------------------------------------------------- #
# Live resolution (best-effort, bounded, graceful)                            #
# --------------------------------------------------------------------------- #

_CELLAR_CACHE: Dict[str, Any] = {}
_CELLAR_EXPIRES: Optional[datetime] = None
_CELLAR_TTL = 12 * 3600
_CELLAR_BUDGET = 6
_CELLAR_LOCK = asyncio.Lock()


async def _resolve_cellar() -> Dict[str, Any]:
    """Confirm ELI + in-force for the PPWR CELEX from Cellar; cached; best-effort."""
    global _CELLAR_CACHE, _CELLAR_EXPIRES
    now = datetime.now(timezone.utc)
    if _CELLAR_EXPIRES and now < _CELLAR_EXPIRES and _CELLAR_CACHE:
        return _CELLAR_CACHE
    async with _CELLAR_LOCK:
        now = datetime.now(timezone.utc)
        if _CELLAR_EXPIRES and now < _CELLAR_EXPIRES and _CELLAR_CACHE:
            return _CELLAR_CACHE
        resolved: Dict[str, Any] = {}
        try:
            from services.api_clients.cellar_sparql_client import CellarSPARQLClient

            async def one() -> None:
                async with CellarSPARQLClient() as client:
                    meta = await client.get_celex_metadata(_CELEX, language="ENG")
                    if meta:
                        resolved.update({
                            "eli": meta.get("eli"),
                            "in_force": meta.get("in_force"),
                            "entry_into_force": meta.get("dateInForce"),
                            "document_date": meta.get("date"),
                        })
            await asyncio.wait_for(one(), timeout=_CELLAR_BUDGET)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ppwr: Cellar resolve unavailable (%s) — serving curated seed", exc)
        if resolved:
            _CELLAR_CACHE = resolved
            _CELLAR_EXPIRES = datetime.now(timezone.utc) + timedelta(seconds=_CELLAR_TTL)
        return _CELLAR_CACHE if _CELLAR_CACHE else resolved


def _as_date(value: Any) -> Optional[date]:
    if value is None or isinstance(value, date):
        return value.date() if isinstance(value, datetime) else value
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _related_news(db: Session, limit: int = 10) -> List[NewsRef]:
    """Recent packaging & circular-economy news from economy_items (bodies already
    backfilled there). Newest first. Best-effort — empty on any error.

    Precision-first: matches packaging/circular-economy terms in TITLE/SUMMARY
    (accelerated by the pg_trgm GIN indexes, migration 214). We deliberately do NOT
    match the body here: an article is *about* packaging if it's in the headline;
    a passing body mention ("e-commerce packaging") is noise. (The general
    /news/all uses the tsvector index for body-inclusive word search — different goal.)
    Keyword-matched, so relevance is approximate."""
    try:
        rows = db.execute(
            text("""
                SELECT title, public_url, document_date, summary, body_txt
                FROM public.economy_items
                WHERE item_type IN ('news','press_release')
                  AND (title ILIKE '%packaging%' OR summary ILIKE '%packaging%'
                       OR title ILIKE '%PPWR%'
                       OR title ILIKE '%recycl%' OR summary ILIKE '%recycl%'
                       OR title ILIKE '%circular econom%' OR summary ILIKE '%circular econom%')
                ORDER BY document_date DESC NULLS LAST
                LIMIT :lim
            """),
            {"lim": max(1, min(int(limit or 10), 25))},
        ).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ppwr: related-news lookup failed: %s", exc)
        return []
    out: List[NewsRef] = []
    for title, url, doc_date, summary, body_txt in rows:
        out.append(NewsRef(
            title=title or "(untitled)",
            url=url,
            published=_as_date(doc_date),
            summary=(summary or None),
            body_txt=(body_txt or None),
        ))
    return out


def _resolve_carriages(db: Session, refs: List[str]) -> Dict[str, Dict[str, Any]]:
    if not refs:
        return {}
    try:
        rows = db.execute(
            text("SELECT oeil_procedure_ref, current_status, title, url FROM public.legislative_carriages "
                 "WHERE oeil_procedure_ref = ANY(:refs)"),
            {"refs": refs},
        ).fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ppwr: carriage lookup failed: %s", exc)
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for ref, status, title, url in rows:
        raw = (str(status) if status is not None else "").split(".")[-1].lower()
        out[ref] = {"latest_step": raw.replace("_", " ").title() if raw else None, "title": title, "url": url}
    return out


# --------------------------------------------------------------------------- #
# Endpoint                                                                     #
# --------------------------------------------------------------------------- #

@router.get(
    "",
    response_model=PaginatedResponse[PpwrItem],
    summary="The EU Packaging Regulation (PPWR) in one call — applies from 12 August 2026",
    description="""**What it does**
Returns everything you need on the **Packaging and Packaging Waste Regulation (Regulation (EU) 2025/40, PPWR)** in a single call: the act itself (CELEX + ELI + status), a **phased-obligation timeline** (the dates that actually bite — PFAS ban, recyclability grades, recycled content, reuse targets, deposit-return systems), the delegated acts still moving, and the official Commission resources (guidance, FAQ, facts, LEGISSUM) plus Brubru's deep-dive.

**Heads-up on dates:** the PPWR **entered into force on 11 February 2025** and **applies from 12 August 2026** — these are different. The endpoint returns both, plus `days_until_application`.

**When to use it**
For a compliance team, packaging producer, retailer or comms team tracking what the PPWR requires and when. One call gives the whole roadmap; feed it into a dashboard or a briefing.

**Input**
- `lang` — `ca` | `es` | `en` (default `en`). Selects the title and timeline labels.
- `upcoming_only` — `true` returns only timeline milestones on/after today (default `false`).
- `include_delegated` — include the delegated/implementing acts still moving (default `true`).
- `include_news` — attach recent packaging & circular-economy news, with full article bodies (default `true`; keyword-matched, relevance approximate).
- `include_body` — include the full guide body in `body_txt` + `body_html` (~80 KB; default `true`). Set `false` for a light response (timeline + resources + news only).

**Try it**
```
GET /api/v2/proprietary/packaging-waste-regulation
GET /api/v2/proprietary/packaging-waste-regulation?lang=es&upcoming_only=true
```

**You get back**
A `PaginatedResponse[PpwrItem]`. The first item is the **regulation** — `celex`, `eli`, `title` (+ `titles{}`), `status`, `in_force`, `entry_into_force`, `applies_from`, `days_until_application`, `structure`, `repeals`, the `timeline[]`, `official_resources[]` and `related_news[]` (recent packaging/plastics news with full bodies), the Brubru `deep_link`, and the **full guide body in `body_txt` + `body_html`**. Further items are the delegated acts (with `procedure_ref` + live `latest_step`).

**Data freshness**
Curated corpus, verified against the PPWR knowledge guide + canon page; ELI/in-force re-confirmed live from Cellar; delegated-act status from `legislative_carriages`.""",
)
async def packaging_waste_regulation(
    request: Request,
    lang: str = Query("en", description="ca | es | en (default en)"),
    upcoming_only: bool = Query(False, description="Only timeline milestones on/after today"),
    include_delegated: bool = Query(True, description="Include delegated/implementing acts still moving"),
    include_news: bool = Query(True, description="Attach recent packaging & circular-economy news (with backfilled bodies)"),
    include_body: bool = Query(True, description="Include the full guide body (body_txt + body_html, ~80 KB). Set false for a light response."),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[PpwrItem]:
    lang_n = (lang or "en").strip().lower()
    if lang_n not in _LANGS:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Unknown lang {lang!r}", "reason_code": "invalid_parameter", "valid_values": sorted(_LANGS)},
        )

    cellar = await _resolve_cellar()
    today = date.today()

    # --- the regulation item ---
    seed = _REGULATION
    titles = seed["titles"]
    eli = cellar.get("eli") or seed["eli"]
    in_force = cellar.get("in_force")
    if in_force is None:
        in_force = True
    entry = _as_date(cellar.get("entry_into_force") or seed["entry_into_force"])
    applies = _as_date(seed["applies_from"])
    days_until = (applies - today).days if applies else None

    tl = _TIMELINE
    if upcoming_only:
        tl = [t for t in tl if (_as_date(t["date"]) or today) >= today]
    timeline = [TimelineEntry(date=t["date"], label=t.get(lang_n) or t["en"], article=t.get("article")) for t in tl]

    reg = PpwrItem(
        celex=seed["celex"],
        kind="regulation",
        eli=eli,
        title=titles.get(lang_n) or titles["en"],
        titles=titles,
        role=seed["role"],
        status="in_force" if (applies and applies <= today) else "applies_soon",
        in_force=in_force,
        entry_into_force=entry,
        applies_from=applies,
        days_until_application=days_until,
        structure=seed["structure"],
        procedure_ref_reg=seed["procedure_ref"],
        repeals=seed["repeals"],
        timeline=timeline,
        official_resources=[Resource(**r) for r in _RESOURCES],
        deep_link=seed["deep_link"],
        public_url=seed["deep_link"],
        document_date=_as_date(cellar.get("document_date") or seed["document_date"]),
        creation_date=datetime.now(timezone.utc),
    )
    # Backfill the 5-datapoint body from Brubru's own PPWR guide (cached).
    if include_body:
        reg.body_txt, reg.body_html = _guide_body()
    # Attach recent packaging/plastics news (bodies already backfilled in economy_items).
    if include_news:
        reg.related_news = _related_news(db, limit=10)
    items: List[PpwrItem] = [reg]

    # --- delegated acts (live from carriages) ---
    if include_delegated:
        carriages = _resolve_carriages(db, _DELEGATED_REFS)
        for ref in _DELEGATED_REFS:
            c = carriages.get(ref, {})
            deep = c.get("url") or seed["deep_link"]
            items.append(PpwrItem(
                procedure_ref=ref,
                kind="delegated_act",
                title=c.get("title") or "PPWR delegated act (pallet-wrappings and straps exemption)",
                titles={},
                role="Delegated act under the PPWR (Art. 65) — resolves live from the OEIL procedure file.",
                status="pending",
                deep_link=deep,
                latest_step=c.get("latest_step"),
                public_url=deep,
                creation_date=datetime.now(timezone.utc),
            ))

    total = len(items)
    return build_envelope(
        items, total=total, page=1, limit=max(total, 1),
        op_core_title="Packaging & Packaging Waste Regulation (PPWR) — applies from 12 Aug 2026",
        op_core_type="Curated EU regulation brief",
        op_core_identifier=str(request.url),
        op_core_language=lang_n,
        op_core_referenced_by=[
            "https://brubru.beresol.eu/eucanon/2025-40_ppwr/",
            "/api/v2/proprietary/textile-circularity",
            "/api/v2/proprietary/canon",
        ],
    )
