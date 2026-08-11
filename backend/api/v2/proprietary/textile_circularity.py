"""
Textile-circularity corpus — /api/v2/proprietary/textile-circularity.

Bespoke, curated, live-resolved view of the EU law that governs the textile /
waste / ecodesign product lifecycle. Built for the LIFE DPP-TEX project
(Terraqui + Blue Room Innovation) so a digital-product-passport platform can
always show the norm *in force*, not a copy that ages.

Design (see docs/instructions.md "FOR THE API SESSION — Terraqui / LIFE DPP-TEX"):

  * The corpus is a HAND-CURATED shortlist (not the whole DB): the acts that
    actually define textile circularity, plus the delegated acts / proposals
    still moving. The seed lives in `_CORPUS` below so it travels with the
    backend deploy.

  * Titles / ELI / status are RESOLVED LIVE from the Publications Office Cellar
    SPARQL graph (`CellarSPARQLClient`) with a server-side TTL cache, because
    Cellar is authoritative for in-force status and an act's status changes
    without anything in this repository changing. Cellar is also WAF-free.
    The curated seed is the FLOOR — if Cellar is unreachable the endpoint still
    returns the full contract from the seed (graceful degradation).

    NOTE (corrected 11 Aug 2026): this docstring used to justify the live
    resolution by claiming `eu_laws` was missing several corpus acts. That is
    no longer true — 32025L1892, 32026R1778 and the rest of the DPP regime were
    ingested on 11 Aug (see scripts/_ingest_dpp_regime_oneshot.py), and
    `eu_laws` still has no recurring ingest but does now hold these acts. The
    live-Cellar design stands on freshness, not on absence.

  * The still-moving delegated acts / proposals live in `legislative_carriages`
    (NOT `eu_laws`) and are resolved by their OEIL procedure reference so
    `latest_step` reflects the live procedure status.

Each act carries the 5-datapoint contract the spec defines:
  1. CELEX + ELI permalink        -> `celex`, `eli`
  2. Plain-language title CA/ES/EN -> `title` (in `lang`) + `titles{}`
  3. In-force status + key dates   -> `status`, `in_force`, `entry_into_force`,
                                      `transposition{}`, `key_dates[]`
  4. Latest legislative step       -> `latest_step` (from legislative_carriages)
  5. Brubru deep-link              -> `deep_link` (== public_url; canon page or guide)

Scope: read:knowledge (Brubru knowledge layer). Policy family:
climate-energy-environment (+ trade-industry-market for CBAM).
"""

from __future__ import annotations

import asyncio
import logging
from html import escape as html_escape
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User

from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/textile-circularity", tags=["v2-proprietary-textile-circularity"])

_LANGS = {"ca", "es", "en"}
_STATUSES = {"in_force", "pending", "all"}
_BRUBRU = "https://brubru.beresol.eu"

# --------------------------------------------------------------------------- #
# Seed corpus — hand-curated, verified against Cellar + the textile EPR guide  #
# (knowledge_base/guides/textile_epr_waste_framework_directive_2025_1892.md)   #
# on 6 Aug 2026. Titles/ELI/status are re-confirmed live from Cellar at        #
# request time; the values here are the fallback floor.                        #
# --------------------------------------------------------------------------- #

# In-force base acts (CELEX-identified).
_BASE_ACTS: List[Dict[str, Any]] = [
    {
        "celex": "32025L1892",
        "kind": "directive",
        "eli": "http://data.europa.eu/eli/dir/2025/1892/oj",
        "role": "Core act: the EU's first harmonised extended producer responsibility (EPR) regime for textiles, inserted into the Waste Framework Directive.",
        "titles": {
            "en": "Textile EPR / Waste Framework Directive amendment",
            "es": "Responsabilidad ampliada del productor textil (modificación de la Directiva marco de residuos)",
            "ca": "Responsabilitat ampliada del productor tèxtil (modificació de la Directiva marc de residus)",
        },
        "document_date": "2025-09-10",
        "entry_into_force": "2025-10-16",
        "transposition": {"ES": "2027-06-17", "BG": "2027-06-17"},
        "key_dates": [
            {"date": "2025-10-16", "en": "Entry into force", "es": "Entrada en vigor", "ca": "Entrada en vigor"},
            {"date": "2027-06-17", "en": "Transposition deadline (Art. 2(1))", "es": "Plazo de transposición (art. 2(1))", "ca": "Termini de transposició (art. 2(1))"},
            {"date": "2028-04-17", "en": "Textile EPR schemes must be operational (Art. 22a(14))", "es": "Los sistemas de RAP textil deben estar operativos (art. 22a(14))", "ca": "Els sistemes de RAP tèxtil han d'estar operatius (art. 22a(14))"},
            {"date": "2029-04-17", "en": "Micro-enterprises come into scope (Art. 41)", "es": "Las microempresas entran en el ámbito (art. 41)", "ca": "Les microempreses entren en l'àmbit (art. 41)"},
            {"date": "2030-12-31", "en": "Binding food-waste reduction targets must be met (Art. 9a(4))", "es": "Deben cumplirse los objetivos vinculantes de residuos alimentarios (art. 9a(4))", "ca": "S'han de complir els objectius vinculants de residus alimentaris (art. 9a(4))"},
        ],
        "deep_link": f"{_BRUBRU}/eucanon/2025-1892_wfd_textiles/",
        "guide_slug": "textile_epr_waste_framework_directive_2025_1892",
    },
    {
        "celex": "32008L0098",
        "kind": "directive",
        "eli": "http://data.europa.eu/eli/dir/2008/98/oj",
        "role": "Parent act that 2025/1892 amends: the Waste Framework Directive (the general EU waste-management and EPR baseline).",
        "titles": {
            "en": "Waste Framework Directive",
            "es": "Directiva marco de residuos",
            "ca": "Directiva marc de residus",
        },
        "document_date": "2008-11-19",
        "entry_into_force": None,
        "transposition": None,  # transposed long ago; not re-asserting a historical per-MS date
        "key_dates": [],
        "deep_link": f"{_BRUBRU}/eucanon/2025-1892_wfd_textiles/",
        "guide_slug": "textile_epr_waste_framework_directive_2025_1892",
    },
    {
        "celex": "32024R1781",
        "kind": "regulation",
        "eli": "http://data.europa.eu/eli/reg/2024/1781/oj",
        "role": "Ecodesign for Sustainable Products Regulation (ESPR): the Art. 25 destruction-of-unsold ban and the textile ecodesign / Digital Product Passport delegated acts.",
        "titles": {
            "en": "Ecodesign for Sustainable Products Regulation (ESPR)",
            "es": "Reglamento de diseño ecológico para productos sostenibles (ESPR)",
            "ca": "Reglament de disseny ecològic per a productes sostenibles (ESPR)",
        },
        "document_date": "2024-06-13",
        "entry_into_force": None,
        "transposition": None,
        "key_dates": [],
        "deep_link": f"{_BRUBRU}/api/v2/proprietary/guides/ecodesign_digital_product_passport",
        "guide_slug": "ecodesign_digital_product_passport",
    },
    {
        "celex": "32025R0040",
        "kind": "regulation",
        "eli": "http://data.europa.eu/eli/reg/2025/40/oj",
        "role": "Packaging and Packaging Waste Regulation (PPWR): the packaging side of the circular product.",
        "titles": {
            "en": "Packaging and Packaging Waste Regulation (PPWR)",
            "es": "Reglamento de envases y residuos de envases (PPWR)",
            "ca": "Reglament d'envasos i residus d'envasos (PPWR)",
        },
        "document_date": "2024-12-19",
        "entry_into_force": None,
        "transposition": None,
        "key_dates": [],
        "deep_link": f"{_BRUBRU}/eucanon/2025-40_ppwr/",
        "guide_slug": "eu_packaging_packaging_waste_2025_40",
    },
    {
        "celex": "32024R1157",
        "kind": "regulation",
        "eli": "http://data.europa.eu/eli/reg/2024/1157/oj",
        "role": "Waste Shipments Regulation: export controls over sorted textiles leaving the EU.",
        "titles": {
            "en": "Waste Shipments Regulation",
            "es": "Reglamento de traslados de residuos",
            "ca": "Reglament de trasllats de residus",
        },
        "document_date": "2024-04-11",
        "entry_into_force": None,
        "transposition": None,
        "key_dates": [],
        "deep_link": f"{_BRUBRU}/api/v2/proprietary/guides/eu_waste_shipment_regulation_diwass",
        "guide_slug": "eu_waste_shipment_regulation_diwass",
    },
    {
        "celex": "32024R1252",
        "kind": "regulation",
        "eli": "http://data.europa.eu/eli/reg/2024/1252/oj",
        "role": "Critical Raw Materials Act: the recovered-fibre / secondary-raw-material angle of textile recycling.",
        "titles": {
            "en": "Critical Raw Materials Act",
            "es": "Reglamento de materias primas fundamentales",
            "ca": "Reglament de matèries primeres fonamentals",
        },
        "document_date": "2024-04-11",
        "entry_into_force": None,
        "transposition": None,
        "key_dates": [],
        "deep_link": f"{_BRUBRU}/api/v2/proprietary/guides/eu_critical_raw_materials_act",
        "guide_slug": "eu_critical_raw_materials_act",
    },
    {
        "celex": "32023R0956",
        "kind": "regulation",
        "eli": "http://data.europa.eu/eli/reg/2023/956/oj",
        "role": "Carbon Border Adjustment Mechanism (CBAM): the downstream carbon-cost extension Terraqui tracks.",
        "titles": {
            "en": "Carbon Border Adjustment Mechanism (CBAM)",
            "es": "Mecanismo de ajuste en frontera por carbono (CBAM)",
            "ca": "Mecanisme d'ajust en frontera per carboni (CBAM)",
        },
        "document_date": "2023-05-10",
        "entry_into_force": None,
        "transposition": None,
        "key_dates": [],
        "deep_link": f"{_BRUBRU}/eucanon/2023-956_cbam/",
        "guide_slug": "cbam_carbon_border_adjustment_mechanism",
    },
]

# Still-moving delegated acts / proposals (procedure-identified, in
# legislative_carriages). `title` is resolved LIVE from the carriage (OEIL is
# the identity source of truth); curated CA/ES aliases are plain-language
# fallbacks. NOTE: 2026/2537(DEA) resolves in the DB to an ESPR ecodesign
# delegated act ("local space heaters"), NOT "Right to Repair Annex II" as an
# earlier draft of the spec labelled it — the live carriage title wins.
_DELEGATED_ACTS: List[Dict[str, Any]] = [
    {
        "procedure_ref": "2026/2615(DEA)",
        "kind": "delegated_act",
        "role": "ESPR delegated act: derogations from the destruction-of-unsold-consumer-products prohibition.",
        "titles": {
            "en": "Derogations from the prohibition of destruction of unsold consumer products",
            "es": "Excepciones a la prohibición de destrucción de productos de consumo no vendidos",
            "ca": "Excepcions a la prohibició de destrucció de productes de consum no venuts",
        },
        "parent_celex": "32024R1781",
    },
    {
        "procedure_ref": "2026/0099(COD)",
        "kind": "proposal",
        "role": "Waste Shipments proposal: export of mixed municipal waste for recovery to third countries.",
        "titles": {
            "en": "Shipments of waste: export of mixed municipal waste for recovery",
            "es": "Traslados de residuos: exportación de residuos municipales mixtos para valorización",
            "ca": "Trasllats de residus: exportació de residus municipals mixtos per a valorització",
        },
        "parent_celex": "32024R1157",
    },
    {
        "procedure_ref": "2026/2631(DEA)",
        "kind": "delegated_act",
        "role": "PPWR delegated act: exemption for operators using pallet wrappings and strapping bands.",
        "titles": {
            "en": "Exempting certain operators that use pallet wrappings and strapping bands",
            "es": "Exención de operadores que utilizan envoltorios de palés y flejes",
            "ca": "Exempció d'operadors que utilitzen embalatges de palet i cintes de subjecció",
        },
        "parent_celex": "32025R0040",
    },
    {
        "procedure_ref": "2026/2537(DEA)",
        "kind": "delegated_act",
        "role": "ESPR ecodesign delegated act (resolves live from the OEIL procedure file).",
        "titles": {
            "en": "Ecodesign requirements (ESPR delegated act)",
            "es": "Requisitos de diseño ecológico (acto delegado ESPR)",
            "ca": "Requisits de disseny ecològic (acte delegat ESPR)",
        },
        "parent_celex": "32024R1781",
    },
]

# Parent CELEX -> curated deep-link for delegated acts that don't have their own
# Brubru page (fall back to the parent act's canon page / guide).
_PARENT_DEEP_LINK = {a["celex"]: a["deep_link"] for a in _BASE_ACTS}


# --------------------------------------------------------------------------- #
# Response models                                                             #
# --------------------------------------------------------------------------- #

class _DataPoints(BaseModel):
    """The 5 mandatory Brubru v1 datapoints — present even when null."""
    public_url: Optional[str] = Field(None, description="Citizen/machine deep-link for this act (== deep_link).")
    body_txt: Optional[str] = Field(None, description="Plain-text body — null here (see the deep-link for the full explainer).")
    body_html: Optional[str] = Field(None, description="HTML body — null here.")
    document_date: Optional[date] = Field(None, description="Publication/signature date of the underlying act (null for pending procedures).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru resolved this row (server time).")


class Transposition(BaseModel):
    member_state: str = Field(..., description="Member State ISO code (ES, BG, ...).")
    deadline: Optional[date] = Field(None, description="Transposition deadline for this Member State.")


class TextileAct(_DataPoints):
    """One act in the textile-circularity corpus with the 5-datapoint contract."""
    celex: Optional[str] = Field(None, description="CELEX number (null for delegated acts / proposals identified by procedure ref).")
    procedure_ref: Optional[str] = Field(None, description="OEIL procedure reference for pending delegated acts / proposals (e.g. '2026/2615(DEA)').")
    kind: str = Field(..., description="directive | regulation | delegated_act | proposal.")
    eli: Optional[str] = Field(None, description="Datapoint 1 — ELI permalink (the stable link). Null for acts not yet adopted.")
    title: str = Field(..., description="Datapoint 2 — plain-language title in the requested `lang`.")
    titles: Dict[str, str] = Field(default_factory=dict, description="Plain-language titles in ca/es/en.")
    role: str = Field(..., description="Why this act is in the textile-circularity corpus.")
    status: str = Field(..., description="Datapoint 3 — 'in_force' or 'pending'.")
    in_force: Optional[bool] = Field(None, description="Live in-force flag resolved from Cellar (null if unresolved).")
    entry_into_force: Optional[date] = Field(None, description="Entry-into-force date (from Cellar or curated).")
    transposition: List[Transposition] = Field(default_factory=list, description="Per-Member-State transposition deadlines (directives only).")
    key_dates: List[Dict[str, Any]] = Field(default_factory=list, description="Datapoint 3 — key operational dates ({date, label}) in the requested `lang`.")
    latest_step: Optional[str] = Field(None, description="Datapoint 4 — latest legislative step (from legislative_carriages; pending acts only).")
    deep_link: str = Field(..., description="Datapoint 5 — Brubru deep-link (canon page or knowledge guide).")


# --------------------------------------------------------------------------- #
# Cellar live-resolution (best-effort, cached, graceful)                      #
# --------------------------------------------------------------------------- #

# celex -> {"eli", "in_force", "entry_into_force", "document_date", "title_en", "title_es"}
_CELLAR_CACHE: Dict[str, Dict[str, Any]] = {}
_CELLAR_CACHE_EXPIRES: Optional[datetime] = None
_CELLAR_TTL_SECONDS = 12 * 3600
# Hard wall on the live Cellar resolution so a slow/again SPARQL endpoint can
# never hang a worker: past this budget we serve the curated seed floor and let
# the next request try again. (The Cellar client's own timeout is 120s — far too
# long to sit in a paid partner's request path.)
_CELLAR_BUDGET_SECONDS = 8
_CELLAR_LOCK = asyncio.Lock()


async def _resolve_cellar(celexes: List[str]) -> Dict[str, Dict[str, Any]]:
    """Resolve ELI / in-force / entry-into-force / titles for the given CELEX
    numbers live from Cellar, cached for _CELLAR_TTL_SECONDS. Best-effort: any
    failure (Cellar down, httpx missing, timeout) returns whatever is cached
    (possibly empty) so the caller falls back to the curated seed."""
    global _CELLAR_CACHE, _CELLAR_CACHE_EXPIRES

    now = datetime.now(timezone.utc)
    if _CELLAR_CACHE_EXPIRES and now < _CELLAR_CACHE_EXPIRES and _CELLAR_CACHE:
        return _CELLAR_CACHE

    async with _CELLAR_LOCK:
        # Re-check after acquiring the lock (another request may have filled it).
        now = datetime.now(timezone.utc)
        if _CELLAR_CACHE_EXPIRES and now < _CELLAR_CACHE_EXPIRES and _CELLAR_CACHE:
            return _CELLAR_CACHE

        resolved: Dict[str, Dict[str, Any]] = {}
        try:
            # Lazy import so a missing/broken Cellar stack never breaks the
            # endpoint import (graceful degradation to the seed floor).
            from services.api_clients.cellar_sparql_client import CellarSPARQLClient

            async with CellarSPARQLClient() as client:
                async def one(celex: str) -> None:
                    try:
                        meta_en = await client.get_celex_metadata(celex, language="ENG")
                        meta_es = await client.get_celex_metadata(celex, language="SPA")
                        if not meta_en and not meta_es:
                            return
                        meta = meta_en or meta_es or {}
                        resolved[celex] = {
                            "eli": meta.get("eli"),
                            "in_force": meta.get("in_force"),
                            "entry_into_force": meta.get("dateInForce"),
                            "document_date": meta.get("date"),
                            "title_en": (meta_en or {}).get("title"),
                            "title_es": (meta_es or {}).get("title"),
                        }
                    except Exception as exc:  # per-CELEX failure is non-fatal
                        logger.warning("textile-circularity: Cellar resolve failed for %s: %s", celex, exc)

                await asyncio.wait_for(
                    asyncio.gather(*(one(c) for c in celexes)),
                    timeout=_CELLAR_BUDGET_SECONDS,
                )
        except asyncio.TimeoutError:
            logger.warning(
                "textile-circularity: Cellar resolution exceeded %ss budget — serving curated seed "
                "(partial=%d)", _CELLAR_BUDGET_SECONDS, len(resolved),
            )
        except Exception as exc:
            logger.warning("textile-circularity: Cellar enrichment unavailable (%s) — serving curated seed", exc)

        if resolved:
            _CELLAR_CACHE = resolved
            # Full result -> long TTL; partial (timeout/some failures) -> short
            # TTL so the next request self-heals instead of serving seed for 12h.
            complete = len(resolved) == len(celexes)
            ttl = _CELLAR_TTL_SECONDS if complete else 900
            _CELLAR_CACHE_EXPIRES = datetime.now(timezone.utc) + timedelta(seconds=ttl)
        return _CELLAR_CACHE if _CELLAR_CACHE else resolved


def _resolve_carriages(db: Session, refs: List[str]) -> Dict[str, Dict[str, Any]]:
    """latest_step + live title + OEIL url for the given procedure refs, from
    legislative_carriages. Small indexed query (matches the canon.py pattern)."""
    if not refs:
        return {}
    try:
        rows = db.execute(
            text("""
                SELECT oeil_procedure_ref, current_status, title, url
                FROM public.legislative_carriages
                WHERE oeil_procedure_ref = ANY(:refs)
            """),
            {"refs": refs},
        ).fetchall()
    except Exception as exc:
        logger.warning("textile-circularity: carriage lookup failed: %s", exc)
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    for ref, status, title, url in rows:
        # current_status is a Postgres enum -> str; humanise for latest_step.
        raw = (str(status) if status is not None else "").split(".")[-1].lower()
        step = raw.replace("_", " ").strip().title() if raw else None
        out[ref] = {"latest_step": step, "title": title, "url": url}
    return out


def _as_date(value: Any) -> Optional[date]:
    """Coerce a value to a date, tolerating None and malformed upstream
    strings (a bad Cellar date must never 500 the endpoint)."""
    if value is None or isinstance(value, date):
        return value if not isinstance(value, datetime) else value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def _localise_key_dates(key_dates: List[Dict[str, Any]], lang: str) -> List[Dict[str, Any]]:
    out = []
    for kd in key_dates:
        out.append({"date": kd.get("date"), "label": kd.get(lang) or kd.get("en")})
    return out


def _build_base_act(seed: Dict[str, Any], lang: str, cellar: Dict[str, Any]) -> TextileAct:
    titles = seed["titles"]
    title = titles.get(lang) or titles.get("en")
    # Prefer the live Cellar title in en/es when present; keep curated CA (not
    # an official EU language, so Cellar has no Catalan title).
    live_titles = dict(titles)
    if cellar.get("title_en"):
        live_titles["en"] = cellar["title_en"]
    if cellar.get("title_es"):
        live_titles["es"] = cellar["title_es"]

    eli = cellar.get("eli") or seed.get("eli")
    in_force = cellar.get("in_force")
    if in_force is None:
        in_force = True  # every base act in this corpus is adopted + in force
    entry = _as_date(cellar.get("entry_into_force") or seed.get("entry_into_force"))
    doc_date = _as_date(cellar.get("document_date") or seed.get("document_date"))

    transposition: List[Transposition] = []
    if seed.get("transposition"):
        for ms, deadline in seed["transposition"].items():
            transposition.append(Transposition(member_state=ms, deadline=_as_date(deadline)))

    _body_txt, _body_html = _compose_body(
        title=title, celex=seed["celex"], procedure_ref=None, eli=eli,
        role=seed["role"], status="in_force", in_force=in_force, entry=entry,
        transposition=transposition,
        key_dates=_localise_key_dates(seed.get("key_dates", []), lang),
        latest_step=None, deep_link=seed["deep_link"],
    )
    return TextileAct(
        celex=seed["celex"],
        procedure_ref=None,
        kind=seed["kind"],
        eli=eli,
        title=title,
        titles=live_titles,
        role=seed["role"],
        status="in_force",
        in_force=in_force,
        entry_into_force=entry,
        transposition=transposition,
        key_dates=_localise_key_dates(seed.get("key_dates", []), lang),
        latest_step=None,
        deep_link=seed["deep_link"],
        # 5 Brubru datapoints
        public_url=seed["deep_link"],
        body_txt=_body_txt,
        body_html=_body_html,
        document_date=doc_date,
        creation_date=datetime.now(timezone.utc),
    )


def _compose_body(*, title: str, celex: Optional[str], procedure_ref: Optional[str],
                  eli: Optional[str], role: str, status: str, in_force: bool,
                  entry: Optional[date], transposition: List["Transposition"],
                  key_dates: List[Any], latest_step: Optional[str],
                  deep_link: str) -> tuple:
    """Compose body_txt + body_html for one act.

    The v2 item contract requires a rendered body on every item, structured data
    included: the body is what chat and RAG ingest, so an act returned with a null
    body is invisible to everything downstream of the API.
    """
    lines = [title, ""]
    if celex:
        lines.append(f"CELEX: {celex}")
    if procedure_ref:
        lines.append(f"Procedure: {procedure_ref}")
    if eli:
        lines.append(f"ELI: {eli}")
    lines.append(f"Role in textile circularity: {role}")
    lines.append(f"Status: {status}" + (" (in force)" if in_force else ""))
    if entry:
        lines.append(f"Entry into force: {entry}")
    if latest_step:
        lines.append(f"Latest procedural step: {latest_step}")
    for t in transposition or []:
        if getattr(t, "deadline", None):
            lines.append(f"Transposition, {t.member_state}: {t.deadline}")
    for kd in key_dates or []:
        label = getattr(kd, "label", None) or (kd.get("label") if isinstance(kd, dict) else None)
        when = getattr(kd, "date", None) or (kd.get("date") if isinstance(kd, dict) else None)
        if label and when:
            lines.append(f"Key date, {label}: {when}")
    lines += ["", f"Brubru explainer: {deep_link}"]
    txt = "\n".join(lines)

    rows_html = "".join(
        f"<tr><th align='left'>{html_escape(str(k))}</th><td>{html_escape(str(v))}</td></tr>"
        for k, v in (
            ("CELEX", celex), ("Procedure", procedure_ref), ("ELI", eli),
            ("Role", role), ("Status", status),
            ("Entry into force", entry), ("Latest step", latest_step),
        ) if v
    )
    htm = (f"<h2>{html_escape(title)}</h2>"
           f"<table>{rows_html}</table>"
           f"<p><a href='{html_escape(deep_link)}'>Brubru explainer</a></p>")
    return txt, htm


def _build_delegated_act(seed: Dict[str, Any], lang: str, carriage: Dict[str, Any]) -> TextileAct:
    titles = dict(seed["titles"])
    # OEIL/carriage is the identity source of truth for the EN title.
    if carriage.get("title"):
        titles["en"] = carriage["title"]
    title = titles.get(lang) or titles.get("en")
    deep_link = carriage.get("url") or _PARENT_DEEP_LINK.get(seed.get("parent_celex")) or f"{_BRUBRU}/api"

    _body_txt, _body_html = _compose_body(
        title=title, celex=None, procedure_ref=seed["procedure_ref"], eli=None,
        role=seed["role"], status="pending", in_force=False, entry=None,
        transposition=[], key_dates=[], latest_step=carriage.get("latest_step"),
        deep_link=deep_link,
    )
    return TextileAct(
        celex=None,
        procedure_ref=seed["procedure_ref"],
        kind=seed["kind"],
        eli=None,  # not adopted yet -> no ELI
        title=title,
        titles=titles,
        role=seed["role"],
        status="pending",
        in_force=False,
        entry_into_force=None,
        transposition=[],
        key_dates=[],
        latest_step=carriage.get("latest_step"),
        deep_link=deep_link,
        public_url=deep_link,
        body_txt=_body_txt,
        body_html=_body_html,
        document_date=None,
        creation_date=datetime.now(timezone.utc),
    )


# --------------------------------------------------------------------------- #
# Endpoint                                                                     #
# --------------------------------------------------------------------------- #

@router.get(
    "",
    response_model=PaginatedResponse[TextileAct],
    summary="Live status of EU textile-circularity law",
    description="""**What it does**
Returns the curated corpus of EU law that governs the textile / waste / ecodesign product lifecycle — the acts a digital product passport must track so it always shows the norm **in force**, not a copy that ages. Each act carries a stable ELI permalink, a plain-language title (Catalan / Spanish / English), its in-force status and key operational dates, the latest legislative step for acts still moving, and a Brubru deep-link. Titles, ELI and in-force status are resolved **live** from the EU Publications Office (Cellar), so this never returns the blanks a stale local mirror would.

**When to use it**
Feed a digital-product-passport platform (or any compliance surface) the live regulatory backbone for textiles: the Textile EPR / Waste Framework Directive, the ESPR, the PPWR, the Waste Shipments Regulation, the Critical Raw Materials Act and CBAM, plus the delegated acts and proposals still moving through the institutions.

**Input**
- `lang` — `ca` | `es` | `en` (default `ca`). Selects the title and key-date labels.
- `status` — `in_force` | `pending` | `all` (default `all`). `pending` returns the delegated acts / proposals still in procedure.
- `member_state` — `ES` | `BG` | ... . Restricts to acts that carry a transposition deadline for that Member State (directives) and echoes that date.
- `include_delegated` — `true` (default) | `false`. Set `false` to drop the not-yet-adopted delegated acts / proposals.

**Try it**
```
GET /api/v2/proprietary/textile-circularity?lang=ca
GET /api/v2/proprietary/textile-circularity?status=pending
GET /api/v2/proprietary/textile-circularity?member_state=ES
GET /api/v2/proprietary/textile-circularity?lang=es&include_delegated=false
```

**You get back**
A `PaginatedResponse[TextileAct]`. Each item: `celex` (or `procedure_ref` for pending acts), `kind`, `eli`, `title` (+ `titles{}` in ca/es/en), `role`, `status`, `in_force`, `entry_into_force`, `transposition[]` (per Member State), `key_dates[]`, `latest_step` (pending acts), `deep_link`, plus the 5 Brubru datapoints (`public_url` == the deep-link; `document_date`; `creation_date`). In-force acts carry a non-null `eli`; delegated acts / proposals carry a `procedure_ref` and a live `latest_step` instead.

**Data freshness**
Curated corpus, live-resolved. ELI / in-force / titles come from Cellar SPARQL (12h server-side cache); `latest_step` comes from `legislative_carriages`; transposition dates and key operational dates are Brubru-curated from the primary act. If Cellar is briefly unreachable the endpoint degrades to the curated values.""",
)
async def list_textile_circularity(
    request: Request,
    lang: str = Query("ca", description="ca | es | en (default ca)"),
    status: str = Query("all", description="in_force | pending | all (default all)"),
    member_state: Optional[str] = Query(None, description="ES | BG | ... — restrict to acts with a transposition deadline for that Member State"),
    include_delegated: bool = Query(True, description="Include not-yet-adopted delegated acts / proposals (default true)"),
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TextileAct]:
    lang_n = (lang or "ca").strip().lower()
    if lang_n not in _LANGS:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Unknown lang {lang!r}", "reason_code": "invalid_parameter", "valid_values": sorted(_LANGS)},
        )
    status_n = (status or "all").strip().lower()
    if status_n not in _STATUSES:
        raise HTTPException(
            status_code=400,
            detail={"error": f"Unknown status {status!r}", "reason_code": "invalid_parameter", "valid_values": sorted(_STATUSES)},
        )
    ms_n = member_state.strip().upper() if member_state else None

    items: List[TextileAct] = []

    # In-force base acts (unless the caller asked only for pending).
    if status_n in ("in_force", "all"):
        cellar = await _resolve_cellar([a["celex"] for a in _BASE_ACTS])
        for seed in _BASE_ACTS:
            act = _build_base_act(seed, lang_n, cellar.get(seed["celex"], {}))
            items.append(act)

    # Pending delegated acts / proposals.
    if include_delegated and status_n in ("pending", "all"):
        carriages = _resolve_carriages(db, [a["procedure_ref"] for a in _DELEGATED_ACTS])
        for seed in _DELEGATED_ACTS:
            act = _build_delegated_act(seed, lang_n, carriages.get(seed["procedure_ref"], {}))
            items.append(act)

    # member_state filter: keep only acts carrying a transposition deadline for
    # that Member State, and narrow the transposition list to that state.
    if ms_n:
        filtered: List[TextileAct] = []
        for act in items:
            match = [t for t in act.transposition if t.member_state == ms_n]
            if match:
                act.transposition = match
                filtered.append(act)
        items = filtered

    total = len(items)
    limit = max(total, 1)
    return build_envelope(
        items, total=total, page=1, limit=limit,
        op_core_title="EU textile-circularity corpus — live-resolved",
        op_core_type="Curated EU legislation corpus",
        op_core_identifier=str(request.url),
        op_core_language=lang_n,
        op_core_referenced_by=[
            "https://brubru.beresol.eu/eucanon/2025-1892_wfd_textiles/",
            "/api/v2/proprietary/canon",
            "/api/v2/proprietary/guides",
        ],
    )
