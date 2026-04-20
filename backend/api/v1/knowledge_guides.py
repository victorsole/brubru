"""
/api/v1/knowledge-guides — Brubru's 128+ curated EU policy guides.

Each guide is a hand-written explainer on a specific EU law, proposal, or
policy area with a QUICK FACTS summary + keyword triggers. Used internally
by the chatbot for context injection; now exposed so partners can bootstrap
their own assistants.
"""

import re
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, Field

from models.user import User
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope


def _parse_guide(gid: str, raw: str) -> dict:
    """Parse a markdown guide into title, quick_facts, content."""
    if not isinstance(raw, str):
        raw = str(raw or "")
    # Title: first H1
    m = re.search(r"^#\s+(.+)$", raw, re.MULTILINE)
    title = m.group(1).strip() if m else gid.replace("_", " ").title()
    # Quick facts: under "## QUICK FACTS" up to next H2
    qf = None
    m2 = re.search(r"^##\s+QUICK FACTS\s*\n(.+?)(?=^##\s|\Z)", raw, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if m2:
        qf = m2.group(1).strip()[:2000]
    return {"title": title, "quick_facts": qf, "content": raw}

router = APIRouter(prefix="/knowledge-guides", tags=["v1-knowledge-guides"])


class KnowledgeGuideItem(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    quick_facts: Optional[str] = None
    triggers: list = Field(default_factory=list)
    content_preview: Optional[str] = None
    full_content_chars: int = 0


def _loader():
    from knowledge_base.knowledge_loader import KnowledgeLoader
    kl = KnowledgeLoader()
    kl.load_all()
    return kl


@router.get(
    "",
    response_model=PaginatedResponse[KnowledgeGuideItem],
    summary="Search or list Brubru knowledge guides",
    description=(
        "Curated EU policy explainers. Each guide has a QUICK FACTS block and keyword "
        "triggers the chatbot uses for context matching. Pass ?q= for keyword-based "
        "search, omit q to paginate everything."
    ),
)
async def list_knowledge_guides(
    request: Request,
    q: Optional[str] = Query(None, description="Keyword query (e.g. 'GDPR', 'AI Act', 'CBAM')"),
    detail_level: str = Query("Summary", description="Summary returns preview; Full returns full markdown"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[KnowledgeGuideItem]:
    kl = _loader()

    if q:
        matches = kl.search_guides(q, output_mode="titles_only")
        ids = [m.get("id") for m in matches if m.get("id")]
    else:
        ids = sorted(kl.guides.keys())

    total = len(ids)
    start = (page - 1) * limit
    page_ids = ids[start:start + limit]

    include_full = detail_level.lower() == "full"
    # Build reverse-trigger lookup for speed
    from knowledge_base.knowledge_loader import GUIDE_KEYWORD_TRIGGERS
    triggers_by_guide: dict[str, list[str]] = {}
    for trig, gids in GUIDE_KEYWORD_TRIGGERS.items():
        for gid in gids:
            triggers_by_guide.setdefault(gid, []).append(trig)

    data = []
    for gid in page_ids:
        raw = kl.guides.get(gid, "")
        parsed = _parse_guide(gid, raw)
        content = parsed["content"]
        preview = content[:500] if not include_full else content[:20000]
        data.append(KnowledgeGuideItem(
            id=gid,
            title=parsed["title"],
            summary=None,
            quick_facts=parsed["quick_facts"],
            triggers=sorted(set(triggers_by_guide.get(gid, [])))[:50],
            content_preview=preview,
            full_content_chars=len(content),
        ))

    env = build_envelope(data, total=total, page=page, limit=limit, detail_level="Full" if include_full else "Summary")
    return env


@router.get(
    "/{guide_id}",
    response_model=KnowledgeGuideItem,
    summary="Get a single knowledge guide (full markdown content)",
)
async def get_knowledge_guide(
    guide_id: str,
    user: User = Depends(api_user_with_rate_limit),
) -> KnowledgeGuideItem:
    kl = _loader()
    raw = kl.guides.get(guide_id)
    if not raw:
        raise HTTPException(
            status_code=404,
            detail={"error": "Knowledge guide not found", "reason_code": "not_found", "resource": "knowledge-guide", "id": guide_id},
        )
    parsed = _parse_guide(guide_id, raw)
    from knowledge_base.knowledge_loader import GUIDE_KEYWORD_TRIGGERS
    triggers = sorted({t for t, gids in GUIDE_KEYWORD_TRIGGERS.items() if guide_id in gids})
    return KnowledgeGuideItem(
        id=guide_id,
        title=parsed["title"],
        summary=None,
        quick_facts=parsed["quick_facts"],
        triggers=triggers,
        content_preview=parsed["content"],
        full_content_chars=len(parsed["content"]),
    )
