"""
Section-aware AI generation for Tender Docs.

Single endpoint POST /api/generate/tender-section:
   - takes a template_id + section_id (sub-id, e.g. '1.1', '2.4')
   - looks up that section's official prompts from the template JSON
   - assembles a section-aware system prompt (Excellence/Impact/Implementation
     framing; mandatory generative-AI disclosure note when required)
   - runs through MultiProviderService (Cerebras → Gemini → ...)
   - returns markdown sized to the section's page_budget
   - appends a `disclosure` field listing the providers used so the caller
     can update tender_file.extra.ai_disclosure for the export footer

Shipped 16 Jun 2026 with Tender Docs v1.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field

from api.auth_optional import get_current_user_dev as get_current_user
from models.user import User
from services.ai.multi_provider_service import get_multi_provider_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/generate", tags=["Tender Docs"])

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "knowledge_base" / "funding_templates"


# ---------------------------------------------------------------------------
# Pydantic
# ---------------------------------------------------------------------------

class TenderSectionRequest(BaseModel):
    template_id: str = Field(..., description="Template id e.g. 'eic-accelerator-stage-1'")
    section_id: str = Field(..., description="Section or sub-section id e.g. '1.1' or '3.2'")
    funding_mode: Optional[str] = Field(None, description="'grant-only' | 'equity-only' | 'blended'  used for conditional sections")
    topic_id: Optional[str] = None
    topic_variant: Optional[str] = None
    org_context: Optional[Dict[str, Any]] = Field(None, description="Optional org-profile facts (company name, sector, stage, founder count, prior projects)")
    prior_sections: Optional[Dict[str, str]] = Field(None, description="Map of section_id -> markdown the user already drafted, for narrative coherence")
    user_intent: Optional[str] = Field(None, description="Free-text user steering for this section")
    max_words: Optional[int] = Field(None, description="Override the page_budget-derived word target")


class TenderSectionResponse(BaseModel):
    template_id: str
    section_id: str
    markdown: str
    word_count: int
    provider: Optional[str] = None
    model: Optional[str] = None
    disclosure: Dict[str, Any]
    section: Dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_template(template_id: str) -> Dict[str, Any]:
    p = _TEMPLATES_DIR / f"{template_id}.json"
    if not p.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_id}' not found")
    with p.open() as fh:
        return json.load(fh)


def _find_section(template: Dict[str, Any], section_id: str) -> Optional[Dict[str, Any]]:
    """Find the section (or sub-section) inside the template's documents."""
    for doc in template.get("documents", []):
        for section in doc.get("sections", []) or []:
            if section.get("id") == section_id:
                return {**section, "_doc_kind": doc.get("kind"), "_page_limit": doc.get("page_limit"), "_doc_title": doc.get("title")}
            for sub in section.get("sub", []) or []:
                if sub.get("id") == section_id:
                    return {
                        **sub,
                        "_parent_label": section.get("label"),
                        "_criterion": section.get("criterion"),
                        "_page_budget": section.get("page_budget"),
                        "_doc_kind": doc.get("kind"),
                        "_page_limit": doc.get("page_limit"),
                        "_doc_title": doc.get("title"),
                    }
    return None


def _section_word_target(section: Dict[str, Any], override: Optional[int]) -> int:
    """Convert page budget into a word target (~300 words/page typical EU narrative)."""
    if override:
        return max(50, override)
    pb = section.get("_page_budget") or section.get("page_budget") or 1
    try:
        return max(150, int(float(pb) * 300))
    except Exception:
        return 300


def _build_system_prompt(template: Dict[str, Any], section: Dict[str, Any], req: TenderSectionRequest) -> str:
    """Assemble a section-aware system prompt for the AI co-writer."""
    programme = template.get("programme", "EIC")
    name = template.get("name", template.get("id", ""))
    criterion = section.get("_criterion") or section.get("criterion") or "the relevant criterion"

    prompts_block = "\n".join(f"- {p}" for p in section.get("prompts", []) or [])
    conditional = section.get("conditional_prompts") or {}
    cond_block = ""
    if conditional and req.funding_mode and req.funding_mode in conditional:
        cond_block = f"\n\nCONDITIONAL on funding mode '{req.funding_mode}': {conditional[req.funding_mode]}"

    word_target = _section_word_target(section, req.max_words)

    org_block = ""
    if req.org_context:
        org_block = "\n\nOrg-profile facts (use them if relevant, do not fabricate):\n" + "\n".join(
            f"- {k}: {v}" for k, v in req.org_context.items() if v
        )

    prior_block = ""
    if req.prior_sections:
        snippets = []
        for sid, md in req.prior_sections.items():
            if md and md.strip():
                snippets.append(f"### Section {sid} (the user has already written):\n{md.strip()[:1500]}")
        if snippets:
            prior_block = "\n\nNarrative context the user has already written:\n" + "\n\n".join(snippets) + "\n\nKeep your draft consistent with the above."

    user_steer = ""
    if req.user_intent:
        user_steer = f"\n\nUser steering for this section: {req.user_intent.strip()[:1500]}"

    sys = (
        f"You are Brubru, an EU funding application co-writer.\n"
        f"You are drafting section '{section.get('label', section.get('id'))}' of a {programme} {name} application.\n"
        f"The section addresses the {criterion} criterion.\n"
        f"Word target: approximately {word_target} words. Hard cap: {int(word_target * 1.3)} words.\n"
        f"Output: clean markdown ONLY for this section. NO heading at the top (the heading is already in the doc skeleton).\n"
        f"Tone: precise, evaluator-facing, no marketing fluff. Use bullet points where the official template uses them.\n"
        f"Do NOT fabricate data, citations, partner names, financials, TRL evidence, or patents  leave clearly-marked placeholders like `[INSERT TRL 5 validation data here]` instead.\n"
        f"Do NOT invent EU policy references; cite only the official criterion language from the template prompts below.\n"
    )
    if section.get("ai_disclosure_required") or template.get("documents", [{}])[0].get("ai_disclosure_required"):
        sys += "Note: this template requires the applicant to disclose AI assistance. Do NOT add the disclosure to the section body  the export pipeline adds it once at document end.\n"
    sys += (
        f"\nThe official template asks the following for this section. Address each in your draft:\n{prompts_block}"
        f"{cond_block}"
        f"{org_block}"
        f"{prior_block}"
        f"{user_steer}"
    )
    return sys


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post(
    "/tender-section",
    response_model=TenderSectionResponse,
    summary="Draft (or refine) one section of a Tender Doc via the multi-provider AI chain",
    description=(
        "**What it does**\n"
        "Looks up the template's section structure for the given section_id, "
        "assembles a section-aware system prompt (criterion + prompts + "
        "funding-mode conditional + org context + prior-sections context), "
        "runs it through the open-model chain (Cerebras → Gemini → NVIDIA → "
        "Mistral → Groq → Anthropic → OpenAI), and returns markdown.\n\n"
        "**When to use it**\n"
        "Per-section 'Draft with AI' button in the TenderFileEditor.\n\n"
        "**Input**\n"
        "template_id + section_id (required); funding_mode + topic_id + "
        "org_context + prior_sections + user_intent + max_words (all optional).\n\n"
        "**You get back**\n"
        "Markdown sized to the section's page budget, plus the provider that "
        "served it, plus a disclosure block the caller appends to "
        "tender_file.extra.ai_disclosure for the mandatory export-time footer."
    ),
)
async def generate_tender_section(
    payload: TenderSectionRequest,
    current_user: User = Depends(get_current_user),
):
    template = _load_template(payload.template_id)
    section = _find_section(template, payload.section_id)
    if not section:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Section '{payload.section_id}' not found in template '{payload.template_id}'",
        )

    system_prompt = _build_system_prompt(template, section, payload)

    # Empty user message  all the steering is in the system prompt + the
    # conversation primer below. We send a short user kickoff so providers
    # have something to respond to.
    user_kickoff = f"Draft this section now."

    service = get_multi_provider_service()
    try:
        resp = await service.generate(
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": user_kickoff}],
            max_tokens=2400,
            temperature=0.3,
            prefer_claude=False,  # open-chain first; see memory/feedback_chat_must_use_anthropic.md
        )
    except Exception as e:
        logger.exception("tender-section generation failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI provider chain unavailable for tender-section. Try again in a moment.",
        )

    markdown = (resp.message or "").strip()
    word_count = len([w for w in markdown.split() if w])

    disclosure = {
        "providers_used": [resp.provider or "unknown"],
        "model": resp.model if hasattr(resp, "model") else None,
        "template_id": payload.template_id,
        "section_id": payload.section_id,
    }

    return TenderSectionResponse(
        template_id=payload.template_id,
        section_id=payload.section_id,
        markdown=markdown,
        word_count=word_count,
        provider=resp.provider,
        model=getattr(resp, "model", None),
        disclosure=disclosure,
        section={
            "id": section.get("id"),
            "label": section.get("label"),
            "criterion": section.get("_criterion") or section.get("criterion"),
            "page_budget": section.get("_page_budget") or section.get("page_budget"),
            "prompts": section.get("prompts", []),
        },
    )
