"""
Tender Templates API  exposes the JSON funding templates that drive
Tender Docs section structure + AI co-writer prompts.

Endpoints under /api/tender-templates:
- GET /                        list all available templates (programme filter)
- GET /{template_id}           full template detail including section structure
- GET /programmes              list distinct programmes with counts

Templates live at backend/knowledge_base/funding_templates/*.json. They are
shipped in git; not user-editable. Cached in process for the request lifecycle.

Shipped 16 Jun 2026 with Tender Docs v1.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tender-templates", tags=["Tender Docs"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "knowledge_base" / "funding_templates"
_TEMPLATE_CACHE: Dict[str, Dict[str, Any]] = {}


def _load_all() -> List[Dict[str, Any]]:
    """Load every *.json under funding_templates/ (skip _schema.md)."""
    out: List[Dict[str, Any]] = []
    for p in sorted(_TEMPLATES_DIR.glob("*.json")):
        try:
            if p.stem in _TEMPLATE_CACHE:
                out.append(_TEMPLATE_CACHE[p.stem])
                continue
            with p.open() as fh:
                data = json.load(fh)
            _TEMPLATE_CACHE[p.stem] = data
            out.append(data)
        except Exception as e:
            logger.warning("Failed to load tender template %s: %s", p.name, e)
    return out


@router.get(
    "/",
    summary="List available Tender Templates",
    description=(
        "**What it does**\nReturns every funding template Brubru ships, "
        "optionally filtered by programme.\n\n"
        "**When to use it**\nIn the 'Start a Tender Doc' wizard, after the user "
        "picks a programme.\n\n"
        "**You get back**\nA list of summaries  id, name, programme, "
        "sub_instrument, stage, scaffold_version, deadline. Detail is at /{id}."
    ),
)
async def list_templates(programme: Optional[str] = None):
    all_templates = _load_all()
    if programme:
        all_templates = [t for t in all_templates if (t.get("programme") or "").lower() == programme.lower()]
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
        })
    return {"templates": summaries, "count": len(summaries)}


@router.get(
    "/programmes",
    summary="List distinct programmes with template counts",
)
async def list_programmes():
    all_templates = _load_all()
    counts: Dict[str, int] = {}
    for t in all_templates:
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
)
async def get_template(template_id: str):
    path = _TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Funding template '{template_id}' not found",
        )
    if template_id in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[template_id]
    with path.open() as fh:
        data = json.load(fh)
    _TEMPLATE_CACHE[template_id] = data
    return data
