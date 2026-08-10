"""
Tender Templates API — exposes the JSON funding templates that drive
Tender Docs section structure + AI co-writer prompts.

Endpoints under /api/tender-templates:
- GET /                        list all available templates (programme filter)
- GET /{template_id}           full template detail including section structure
- GET /programmes              list distinct programmes with counts

Templates live at backend/knowledge_base/funding_templates/*.json. They are
shipped in git; not user-editable. Loading, locale fallback and caching all live
in services/funding_template_loader.py.

Shipped 16 Jun 2026 with Tender Docs v1. Locale support added 10 Aug 2026.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status, Depends, Query

from api.auth_optional import require_blue_tier_dev
from models.user import User
from services.funding_template_loader import (
    SUPPORTED_LANGS,
    load_all,
    load_template,
    normalise_lang,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tender-templates", tags=["Tender Docs"])

_LANG_DESC = (
    "Render the template in one of Brubru's six languages "
    f"({', '.join(SUPPORTED_LANGS)}). Falls back to English key by key, so a "
    "partially translated template returns translated headings with English "
    "prompts rather than failing."
)


@router.get(
    "/",
    summary="List available Tender Templates",
    description=(
        "**What it does**\nReturns every funding template Brubru ships, "
        "optionally filtered by programme.\n\n"
        "**When to use it**\nIn the 'Start a Tender Doc' wizard, after the user "
        "picks a programme.\n\n"
        "**Input**\n`programme` to filter, `lang` to pick a language.\n\n"
        "**Try it**\n`GET /api/tender-templates/?programme=EIC&lang=fr`\n\n"
        "**You get back**\nA list of summaries: id, name, programme, "
        "sub_instrument, stage, scaffold_version, deadline, plus the languages "
        "each template is available in. Detail is at /{id}."
    ),
)
async def list_templates(
    programme: Optional[str] = None,
    lang: Optional[str] = Query(None, description=_LANG_DESC),
):
    all_templates = load_all(lang)
    if programme:
        all_templates = [
            t for t in all_templates
            if (t.get("programme") or "").lower() == programme.lower()
        ]
    summaries = []
    for t in all_templates:
        # Pick a representative deadline from the template if present
        deadline = (
            t.get("deadline_2026_cet")
            or (t.get("cut_offs_2026_cet") or [None])[0]
            or t.get("deadline_2027_indicative_cet")
            or t.get("deadline_2027_cet")
        )
        summaries.append({
            "id": t["id"],
            "name": t["name"],
            "programme": t.get("programme"),
            "sub_instrument": t.get("sub_instrument"),
            "stage": t.get("stage"),
            "scaffold_version": t.get("scaffold_version"),
            "kb_guide": t.get("kb_guide"),
            "topic_id_default": t.get("topic_id_default"),
            "deadline": deadline,
            "official_template_url": t.get("official_template_url"),
            "note": t.get("note"),
            "lang": t.get("lang"),
            "available_locales": t.get("available_locales", ["en"]),
            "is_translated": t.get("is_translated", False),
        })
    return {"templates": summaries, "count": len(summaries), "lang": normalise_lang(lang)}


@router.get(
    "/programmes",
    summary="List distinct programmes with template counts",
)
async def list_programmes():
    counts: dict[str, int] = {}
    for t in load_all():
        prog = t.get("programme") or "Unknown"
        counts[prog] = counts.get(prog, 0) + 1
    return {
        "programmes": [
            {"programme": p, "template_count": n} for p, n in sorted(counts.items())
        ]
    }


@router.get(
    "/{template_id}",
    summary="Get a Tender Template by id",
    description=(
        "**What it does**\nReturns one funding template in full: every section, "
        "sub-section, page budget, evaluation criterion, official reference "
        "document and AI prompt seed.\n\n"
        "**When to use it**\nWhen the wizard or the editor opens a template.\n\n"
        "**Input**\nThe template id from `GET /api/tender-templates/`, plus an "
        "optional `lang`.\n\n"
        "**Try it**\n`GET /api/tender-templates/eic-accelerator-stage-2?lang=es`\n\n"
        "**You get back**\nThe full template document, plus `lang`, "
        "`available_locales` and `is_translated` so the interface can say which "
        "language the user is actually reading. Professional subscription "
        "required: the section structure and prompt seeds are the substance of "
        "Tender Docs, unlike the catalogue listing which stays open."
    ),
)
async def get_template(
    template_id: str,
    lang: Optional[str] = Query(None, description=_LANG_DESC),
    current_user: User = Depends(require_blue_tier_dev),
):
    document = load_template(template_id, lang)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Funding template '{template_id}' not found",
        )
    return document
