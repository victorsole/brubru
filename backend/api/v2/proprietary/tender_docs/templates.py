"""
Tender Docs templates: /api/v2/proprietary/tender-docs/templates/*.

Backend: Brubru's funding-application template library. Each template is a
JSON file under `backend/knowledge_base/funding_templates/` shipping the
section structure, comply targets, reference-doc bundle, and (for grant
programmes) the model + annotated grant-agreement URLs that Tenderator's
Tender Docs editor renders.

19 templates as of 17 June 2026 across 8 programmes / 17 sub-instruments:
EIC (Accelerator Stage 1+2, Pathfinder Open + Challenges, Transition,
STEP Scale-up, AIC Stage 1+2, Pre-Accelerator 2027), Erasmus+ (LSI),
Digital Europe (DEP), CERV, LIFE (SAP), Creative Europe (Culture + Media),
CEF (Transport + Energy + Digital), ESF+ (Agency Procurement).

Native implementation: reads the committed JSON manifest directly. The
list endpoint returns a `Summary` projection (no body) by default; the
detail endpoint returns the full body with all sections + reference_docs.

Scope: read:knowledge (Brubru knowledge layer).
"""

from __future__ import annotations

import html as _html
import json as _json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from models.user import User
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/templates", tags=["v2-proprietary-tender-docs"])

_TEMPLATES_DIR = Path(__file__).resolve().parents[4] / "knowledge_base" / "funding_templates"
_TEMPLATE_CACHE: Dict[str, Dict[str, Any]] = {}

_BRUBRU_TEMPLATE_URL = "https://brubru.beresol.eu/tenderator?template={tid}"


class _DataPoints(BaseModel):
    """The 5 mandatory Brubru v1 datapoints: present even when null."""
    public_url: Optional[str] = Field(None, description="Citizen-facing canonical URL: the EU funding portal page for this template when known, else the Brubru Tenderator surface.")
    body_txt: Optional[str] = Field(None, description="Plain-text body composed from sections + reference docs: null on list (Summary), populated on detail.")
    body_html: Optional[str] = Field(None, description="HTML body: null on list, populated on detail.")
    document_date: Optional[date] = Field(None, description="Next call deadline if known (deadline_2026_cet / first cut-off / deadline_2027_indicative_cet); null for evergreen calls.")
    creation_date: Optional[datetime] = Field(None, description="When this API response was generated.")


class TenderTemplateItem(_DataPoints):
    """One Brubru funding template (list / detail shape)."""
    id: str = Field(..., description="Stable template slug (filename without .json), e.g. 'eic-accelerator-stage-2', 'esf-plus-agency-procurement'.")
    name: str = Field(..., description="Human-readable template name.")
    programme: Optional[str] = Field(None, description="EU funding programme (Horizon Europe / EIC, Erasmus+, Digital Europe, CERV, LIFE, Creative Europe, CEF, ESF+).")
    sub_instrument: Optional[str] = Field(None, description="Sub-instrument inside the programme (e.g. 'accelerator', 'pathfinder', 'media', 'agency-procurement').")
    stage: Optional[str] = Field(None, description="Application stage (e.g. 'stage-1', 'stage-2', 'full-proposal').")
    scaffold_version: Optional[str] = Field(None, description="Brubru-internal version tag for the section scaffold.")
    kb_guide: Optional[str] = Field(None, description="Slug of the related Brubru knowledge guide.")
    topic_id_default: Optional[str] = Field(None, description="Default F&T Portal topic id this template is anchored to.")
    deadline: Optional[str] = Field(None, description="Representative next deadline (CET).")
    official_template_url: Optional[str] = Field(None, description="EU's authoritative template page: the Funding & Tenders Portal source.")
    note: Optional[str] = Field(None, description="Free-text note (e.g. caveats, placeholder status).")
    # Detail-only enrichment (null on list)
    documents: Optional[List[Dict[str, Any]]] = Field(None, description="Section structure + AI prompt seeds per document: detail only.")
    comply_targets: Optional[List[str]] = Field(None, description="Template's comply_target labels (drives the comply-clusters cross-fetch): detail only.")
    hand_offs: Optional[Dict[str, Any]] = Field(None, description="Hand-off CTAs for the next stage (chat / comply) once this template is completed: detail only.")
    model_grant_agreement_url: Optional[str] = Field(None, description="EU's Model Grant Agreement page: detail only.")
    annotated_grant_agreement_url: Optional[str] = Field(None, description="EU's Annotated Model Grant Agreement page: detail only.")
    reference_docs: Optional[List[Dict[str, Any]]] = Field(None, description="Curated reference-doc bundle: list of {label, url, ...} entries (Model/Annotated Grant Agreement, unit-cost guidance, programme regulations, ...). Detail only.")


class ProgrammeFacet(BaseModel):
    programme: str = Field(..., description="Programme name as stored in the template files.")
    template_count: int = Field(..., description="Number of templates under this programme.")


# --------------------------------------------------------------------------- #
# Manifest loader (cached)                                                    #
# --------------------------------------------------------------------------- #


def _load_one(template_id: str) -> Optional[Dict[str, Any]]:
    if template_id in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[template_id]
    p = _TEMPLATES_DIR / f"{template_id}.json"
    if not p.exists():
        return None
    try:
        with p.open() as fh:
            data = _json.load(fh)
        _TEMPLATE_CACHE[template_id] = data
        return data
    except Exception as e:
        logger.warning("Failed to load tender template %s: %s", p.name, e)
        return None


def _load_all() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for p in sorted(_TEMPLATES_DIR.glob("*.json")):
        data = _load_one(p.stem)
        if data is not None:
            out.append(data)
    return out


def _representative_deadline(t: Dict[str, Any]) -> Optional[str]:
    return (
        t.get("deadline_2026_cet")
        or (t.get("cut_offs_2026_cet") or [None])[0]
        or t.get("deadline_2027_indicative_cet")
        or t.get("deadline_2027_cet")
    )


def _parse_deadline_date(s: Optional[str]) -> Optional[date]:
    """Best-effort ISO date extraction from a deadline string."""
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _compose_body(t: Dict[str, Any]) -> tuple[str, str]:
    """Compose plain-text + HTML bodies from the full template payload."""
    lines: List[str] = [t.get("name") or t["id"]]
    if t.get("programme"):
        lines.append(f"Programme: {t['programme']}")
    if t.get("sub_instrument"):
        lines.append(f"Sub-instrument: {t['sub_instrument']}")
    if t.get("stage"):
        lines.append(f"Stage: {t['stage']}")
    if t.get("topic_id_default"):
        lines.append(f"Default topic: {t['topic_id_default']}")
    dl = _representative_deadline(t)
    if dl:
        lines.append(f"Next deadline (CET): {dl}")
    if t.get("official_template_url"):
        lines.append(f"Official template: {t['official_template_url']}")

    documents = t.get("documents") or []
    if documents:
        lines.append("")
        lines.append(f"Documents ({len(documents)}):")
        for d in documents:
            kind = d.get("kind") or d.get("doc_kind") or "document"
            title = d.get("title") or kind
            sections = d.get("sections") or []
            lines.append(f"- {title} ({kind}, {len(sections)} sections)")
            for s in sections:
                heading = s.get("heading") or s.get("title") or ""
                if heading:
                    lines.append(f"    * {heading}")

    targets = t.get("comply_targets") or []
    if targets:
        lines.append("")
        lines.append(f"Comply targets: {', '.join(targets)}")

    refs = t.get("reference_docs") or []
    # Defensive: tolerate either shape (list of {label,url} today; legacy dict keyed by category)
    if isinstance(refs, dict):
        refs = [r for category_items in refs.values() for r in (category_items or [])]
    if refs:
        lines.append("")
        lines.append(f"Reference docs ({len(refs)}):")
        for r in refs:
            label = r.get("label") or r.get("title") or r.get("name") or ""
            url = r.get("url") or ""
            if label and url:
                lines.append(f"  - {label}: {url}")
            elif label:
                lines.append(f"  - {label}")

    if t.get("model_grant_agreement_url"):
        lines.append("")
        lines.append(f"Model Grant Agreement: {t['model_grant_agreement_url']}")
    if t.get("annotated_grant_agreement_url"):
        lines.append(f"Annotated MGA: {t['annotated_grant_agreement_url']}")

    body_txt = "\n".join(str(x) for x in lines)
    body_html = "<ul>" + "".join(
        f"<li>{_html.escape(str(x))}</li>" for x in lines if x
    ) + "</ul>"
    return body_txt, body_html


def _to_summary(t: Dict[str, Any]) -> TenderTemplateItem:
    """List-projection: no body, no detail-only fields."""
    return TenderTemplateItem(
        id=t["id"],
        name=t.get("name") or t["id"],
        programme=t.get("programme"),
        sub_instrument=t.get("sub_instrument"),
        stage=t.get("stage"),
        scaffold_version=t.get("scaffold_version"),
        kb_guide=t.get("kb_guide"),
        topic_id_default=t.get("topic_id_default"),
        deadline=_representative_deadline(t),
        official_template_url=t.get("official_template_url"),
        note=t.get("note"),
        public_url=t.get("official_template_url") or _BRUBRU_TEMPLATE_URL.format(tid=t["id"]),
        body_txt=None,
        body_html=None,
        document_date=_parse_deadline_date(_representative_deadline(t)),
        creation_date=datetime.utcnow(),
    )


def _to_full(t: Dict[str, Any]) -> TenderTemplateItem:
    """Detail projection: composed body + every detail-only field."""
    body_txt, body_html = _compose_body(t)
    return TenderTemplateItem(
        id=t["id"],
        name=t.get("name") or t["id"],
        programme=t.get("programme"),
        sub_instrument=t.get("sub_instrument"),
        stage=t.get("stage"),
        scaffold_version=t.get("scaffold_version"),
        kb_guide=t.get("kb_guide"),
        topic_id_default=t.get("topic_id_default"),
        deadline=_representative_deadline(t),
        official_template_url=t.get("official_template_url"),
        note=t.get("note"),
        documents=t.get("documents") or [],
        comply_targets=t.get("comply_targets") or [],
        hand_offs=t.get("hand_offs") or {},
        model_grant_agreement_url=t.get("model_grant_agreement_url"),
        annotated_grant_agreement_url=t.get("annotated_grant_agreement_url"),
        reference_docs=(
            t.get("reference_docs")
            if isinstance(t.get("reference_docs"), list)
            else (
                [r for items in (t.get("reference_docs") or {}).values() for r in (items or [])]
                if isinstance(t.get("reference_docs"), dict)
                else []
            )
        ),
        public_url=t.get("official_template_url") or _BRUBRU_TEMPLATE_URL.format(tid=t["id"]),
        body_txt=body_txt,
        body_html=body_html,
        document_date=_parse_deadline_date(_representative_deadline(t)),
        creation_date=datetime.utcnow(),
    )


# --------------------------------------------------------------------------- #
# Endpoints                                                                   #
# --------------------------------------------------------------------------- #


@router.get(
    "",
    response_model=PaginatedResponse[TenderTemplateItem],
    summary="List Brubru's funding-application templates: section structure, comply targets, reference-doc bundles",
    description="""**What it does**
Returns Brubru's library of funding-application templates for EU grant programmes: each one ships the section structure, AI co-writer prompt seeds, comply targets, and (for grant programmes) the model + annotated Grant Agreement URLs that the Tenderator product renders. List projection only: `documents`, `reference_docs`, and the rest of the detail-only payload sit on `/{template_id}`.

19 templates (17 June 2026) across 8 programmes / 17 sub-instruments: EIC (8 templates: Accelerator Stage 1+2, Pathfinder Open + Challenges, Transition, STEP Scale-up, AIC Stage 1+2, Pre-Accelerator 2027), Erasmus+, Digital Europe, CERV, LIFE, Creative Europe (Culture + Media), CEF (Transport + Energy + Digital), ESF+ (Agency Procurement).

**When to use it**
Building a Tenderator-like UX in your own product, or enumerating Brubru's grant-template coverage before deciding which templates to deep-fetch. Filter by `programme` to scope (e.g. `programme=Horizon%20Europe`).

**Input**
- `programme`: programme name as stored on the templates (e.g. `Horizon Europe`, `Erasmus+`, `Digital Europe`, `CERV`, `LIFE`, `Creative Europe`, `Connecting Europe Facility`, `ESF+`).
- `sub_instrument`: narrow to a sub-instrument (e.g. `accelerator`, `agency-procurement`).
- `limit` (1-100, default 50), `page` (1-indexed).

**Try it**
```
GET /api/v2/proprietary/tender-docs/templates
GET /api/v2/proprietary/tender-docs/templates?programme=ESF%2B
```

**You get back**
A `PaginatedResponse[TenderTemplateItem]`. Per item: `id`, `name`, `programme`, `sub_instrument`, `stage`, `scaffold_version`, `kb_guide`, `topic_id_default`, `deadline`, `official_template_url`, plus the 5 datapoints (`public_url` = official_template_url when known, `document_date` = the next deadline; `body_txt`/`body_html` null on list: fetch `/{template_id}` for the composed body).

**Data freshness**
Brubru-curated. Templates are committed JSON files; refreshed when EU programmes publish new calls or revise existing ones (see `kb_guide` for the related knowledge guide).""",
)
async def list_templates(
    request: Request,
    programme: Optional[str] = Query(None, description="Programme name filter (case-insensitive)."),
    sub_instrument: Optional[str] = Query(None, description="Sub-instrument filter (case-insensitive)."),
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[TenderTemplateItem]:
    all_templates = _load_all()
    if programme:
        prog_lc = programme.lower()
        all_templates = [t for t in all_templates if (t.get("programme") or "").lower() == prog_lc]
    if sub_instrument:
        sub_lc = sub_instrument.lower()
        all_templates = [t for t in all_templates if (t.get("sub_instrument") or "").lower() == sub_lc]

    total = len(all_templates)
    start = (page - 1) * limit
    page_slice = all_templates[start : start + limit]
    items = [_to_summary(t) for t in page_slice]

    return build_envelope(
        items, total, page, limit,
        op_core_title="Brubru funding-application templates",
        op_core_type="Tender Docs template",
        op_core_identifier=str(request.url),
        creation_date=datetime.utcnow(),
    )


@router.get(
    "/programmes",
    response_model=PaginatedResponse[ProgrammeFacet],
    summary="List distinct programmes with template counts",
    description="""**What it does**
Returns the distinct EU funding programmes Brubru ships templates for, with a count of templates per programme: the facet used by the Tenderator "Start a Tender Doc" wizard.

**When to use it**
To populate a programme picker before calling the list endpoint with `programme=<name>`.

**Input**
- `limit` (1-100, default 50), `page` (1-indexed).

**Try it**
```
GET /api/v2/proprietary/tender-docs/templates/programmes
```

**You get back**
A `PaginatedResponse[ProgrammeFacet]`. Each item: `programme`, `template_count`. Sorted alphabetically by programme.

**Data freshness**
Same as the list endpoint.""",
)
async def list_programmes(
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[ProgrammeFacet]:
    counts: Dict[str, int] = {}
    for t in _load_all():
        prog = t.get("programme") or "Unknown"
        counts[prog] = counts.get(prog, 0) + 1

    all_facets = [ProgrammeFacet(programme=p, template_count=n) for p, n in sorted(counts.items())]
    total = len(all_facets)
    start = (page - 1) * limit
    items = all_facets[start : start + limit]

    return build_envelope(
        items, total, page, limit,
        op_core_title="Tender Docs programmes",
        op_core_type="Programme facet",
        op_core_identifier=str(request.url),
        creation_date=datetime.utcnow(),
    )


@router.get(
    "/{template_id}",
    response_model=TenderTemplateItem,
    summary="Get one funding template by id: full section structure + reference_docs + grant-agreement URLs",
    description="""**What it does**
Returns one funding template in full: every section, every AI co-writer prompt seed, the complete `reference_docs` bundle (guidance / model_documents / unit_costs / annotated MGA / ...), and the canonical Grant Agreement URLs. Composes `body_txt` / `body_html` from those sections so a downstream LLM can ingest the template as a single grounded context.

The richest reference-doc bundle today is `eic-accelerator-stage-2` (13 reference entries across 7 categories).

**When to use it**
To preview a template before generating an application, to embed the section scaffold in your own UI, or to feed an LLM the full template as context for a custom drafter. Pair with `/comply-clusters?template_id=<id>` to surface the EU Law Comply clusters relevant to this template.

**Input**
- `template_id` (path): the template slug, e.g. `eic-accelerator-stage-2`, `cef-transport`, `esf-plus-agency-procurement`.

**Try it**
```
GET /api/v2/proprietary/tender-docs/templates/eic-accelerator-stage-2
```

**You get back**
A single `TenderTemplateItem` with every detail-only field populated: `documents` (full section trees), `comply_targets`, `hand_offs`, `model_grant_agreement_url`, `annotated_grant_agreement_url`, `reference_docs`, plus the 5 datapoints (`body_txt`/`body_html` composed from sections + references). HTTP 404 (`reason_code: not_found`) if the slug is unknown.

**Data freshness**
Brubru-curated. Committed JSON; refreshed when the underlying EU programme publishes a new revision.""",
)
async def get_template(
    template_id: str,
    user: User = Depends(api_user_with_rate_limit),
) -> TenderTemplateItem:
    data = _load_one(template_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Funding template '{template_id}' not found",
        )
    return _to_full(data)
