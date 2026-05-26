"""
Knowledge guides source — /api/v2/proprietary/guides/*.

Backend: Brubru's curated EU-policy knowledge guides (the same markdown
explainers the chatbot uses to ground answers). LIVE — delegates to the v1
handlers in api.v1.knowledge_guides so there is exactly one implementation
during the v1+v2 coexistence period.

Scope: read:knowledge (Brubru knowledge layer), same as the v1 surface.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, Request

from models.user import User

from api.v1 import knowledge_guides as _v1
from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse
from api.v1.knowledge_guides import KnowledgeGuideItem

router = APIRouter(prefix="/guides", tags=["v2-proprietary-guides"])


@router.get(
    "",
    response_model=PaginatedResponse[KnowledgeGuideItem],
    summary="List Brubru's curated EU-policy knowledge guides — the chatbot's grounding layer",
    description="""**What it does**
Returns Brubru's curated knowledge-base guides — the same markdown explainers the chatbot uses to ground its answers. Each guide is a 100-300-line domain explainer for one policy area (AI Act, CBAM, MFF 2028-2034, ...) with a QUICK FACTS block at the top, a body, and keyword triggers. With no `q` this enumerates the **entire** corpus (~290 guides), page by page.

**When to use it**
Ground your own LLM in Brubru's EU-policy knowledge: pull the guides for a topic with `q=<topic>`, embed them as context, and your assistant gets the same grounding the Brubru chatbot uses. Pass `detail_level=Full` for the complete markdown body (vs a 500-char preview at `Summary`).

**Input**
- `q` — keyword query (`GDPR`, `AI Act`, `CBAM`, `housing crisis`). Omit to list everything.
- `detail_level` — `Summary` (default, 500-char preview) or `Full` (complete markdown).
- `limit` (1-100, default 50), `page` (1-indexed).

**Try it**
```
GET /api/v2/proprietary/guides?limit=100
GET /api/v2/proprietary/guides?q=AI%20Act&detail_level=Full
```

**You get back**
A `PaginatedResponse[KnowledgeGuideItem]`. Each item carries `id`, `title`, `quick_facts`, `triggers[]`, `content` (Full or preview), `content_preview`, `full_content_chars`. The 5 envelope datapoints sit on the envelope (per-item body lives in `content`).

**Data freshness**
Brubru-curated (not synced from external sources). Refreshed by `/morning` Phase 3D, `/audit-queries` gap-fills, and ad-hoc edits.""",
)
async def list_guides(
    request: Request,
    q: Optional[str] = Query(None, description="Keyword query (e.g. 'GDPR', 'AI Act', 'CBAM'). Omit to list every guide."),
    detail_level: str = Query("Summary", description="Summary returns a 500-char preview; Full returns the full markdown body"),
    limit: int = Query(50, ge=1, le=100, description="Items per page (default 50, max 100)"),
    page: int = Query(1, ge=1),
    user: User = Depends(api_user_with_rate_limit),
) -> PaginatedResponse[KnowledgeGuideItem]:
    return await _v1.list_knowledge_guides(request, q=q, detail_level=detail_level, limit=limit, page=page, user=user)


@router.get(
    "/{guide_id}",
    response_model=KnowledgeGuideItem,
    summary="Look up one knowledge guide by its slug — full markdown body",
    description="""**What it does**
Returns the full markdown content of one Brubru knowledge guide by its filename slug. Always returns the complete body — no truncation. Same content the chatbot injects into Claude/Mistral context for grounded answers.

**When to use it**
After locating a guide via the list endpoint (or when you already know the slug), fetch the full markdown for embedding in your own UI or feeding to a downstream LLM as context.

**Input**
- `guide_id` (path) — the guide's filename slug without `.md`, e.g. `ai_act_regulation`, `cbam_downstream_goods_extension`, `mff_2028_2034`.

**Try it**
```
GET /api/v2/proprietary/guides/ai_act_regulation
```

**You get back**
A single `KnowledgeGuideItem`: `id`, `title`, `quick_facts`, `triggers[]`, full `content` markdown, `full_content_chars`. HTTP 404 (`reason_code: not_found`) if no guide with that slug exists.

**Data freshness**
Brubru-curated. Updated by `/morning` Phase 3D + ad-hoc edits when major legislative developments warrant a refresh.""",
)
async def get_guide(
    guide_id: str,
    user: User = Depends(api_user_with_rate_limit),
) -> KnowledgeGuideItem:
    return await _v1.get_knowledge_guide(guide_id, user=user)
