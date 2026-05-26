"""
/api/v1/knowledge-guides — Brubru's 128+ curated EU policy guides.

Each guide is a hand-written explainer on a specific EU law, proposal, or
policy area with a QUICK FACTS summary + keyword triggers. Used internally
by the chatbot for context injection; now exposed so partners can bootstrap
their own assistants.
"""

import re
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, Field

from models.user import User
from ._deps import api_user_with_rate_limit
from ._envelope import PaginatedResponse, build_envelope

# Guides are surfaced publicly via the guides index (no per-guide public page).
GUIDES_PUBLIC_URL = "https://brubru.beresol.eu/guides/"


def _render_md(md: str) -> Optional[str]:
    """Render guide markdown to HTML for body_html. Prefers the `markdown`
    library; falls back to a small dependency-free converter so body_html is
    ALWAYS populated even if the library isn't importable on the host (Railway
    has shown it can be). Returns None only for empty input."""
    if not md:
        return None
    try:
        import markdown as _md
        return _md.markdown(md, extensions=["extra", "sane_lists", "tables"])
    except Exception:  # noqa: BLE001 — lib missing OR an extension failed
        try:
            import markdown as _md
            return _md.markdown(md)  # retry without extensions
        except Exception:  # noqa: BLE001 — lib genuinely unavailable
            return _md_fallback(md)


def _md_fallback(md: str) -> str:
    """Minimal, dependency-free Markdown -> HTML for guide bodies. Handles
    headings, unordered/ordered lists, blockquotes, fenced/indented code,
    bold/italic/inline-code/links, and paragraphs. Not a full CommonMark
    implementation — a reliable floor so body_html is never empty."""
    import html as _h
    import re as _re

    def _inline(t: str) -> str:
        t = _h.escape(t, quote=False)
        t = _re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = _re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = _re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
        t = _re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
        return t

    out: list[str] = []
    lines = md.replace("\r\n", "\n").split("\n")
    i, n = 0, len(lines)
    list_tag: Optional[str] = None

    def _close_list():
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    while i < n:
        line = lines[i]
        if line.strip().startswith("```"):  # fenced code block
            _close_list()
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(_h.escape(lines[i], quote=False))
                i += 1
            i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
            continue
        m = _re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            _close_list()
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{_inline(m.group(2).strip())}</h{lvl}>")
            i += 1
            continue
        if _re.match(r"^\s*[-*+]\s+", line):
            if list_tag != "ul":
                _close_list()
                out.append("<ul>")
                list_tag = "ul"
            out.append(f"<li>{_inline(_re.sub(r'^\s*[-*+]\s+', '', line))}</li>")
            i += 1
            continue
        if _re.match(r"^\s*\d+\.\s+", line):
            if list_tag != "ol":
                _close_list()
                out.append("<ol>")
                list_tag = "ol"
            out.append(f"<li>{_inline(_re.sub(r'^\s*\d+\.\s+', '', line))}</li>")
            i += 1
            continue
        if line.strip().startswith(">"):
            _close_list()
            out.append(f"<blockquote>{_inline(line.strip()[1:].strip())}</blockquote>")
            i += 1
            continue
        if not line.strip():
            _close_list()
            i += 1
            continue
        # paragraph: gather consecutive non-blank, non-block lines
        _close_list()
        para = [line]
        i += 1
        while i < n and lines[i].strip() and not _re.match(r"^(#{1,6}\s|\s*[-*+]\s|\s*\d+\.\s|>|```)", lines[i]):
            para.append(lines[i])
            i += 1
        out.append("<p>" + _inline(" ".join(s.strip() for s in para)) + "</p>")
    _close_list()
    return "\n".join(out)


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
    # `content` carries the full markdown body when detail_level=Full, and is
    # truncated to a 500-char preview at detail_level=Summary. Mirrored as
    # `content_preview` for back-compat with anyone built against the old name.
    content: Optional[str] = None
    content_preview: Optional[str] = None
    full_content_chars: int = 0

    # The 5 mandatory Brubru datapoints (present even when null). For a guide:
    # public_url -> the guides index (no per-guide public page exists);
    # body_txt   -> the markdown content (the guide body IS the payload);
    # body_html  -> null (guides are not rendered to HTML);
    # document_date / creation_date -> null (guides are not dated documents).
    public_url: Optional[str] = Field(None, description="Citizen-facing URL — the guides index (guides have no per-guide public page).")
    body_txt: Optional[str] = Field(None, description="The guide's markdown body (mirrors `content` at the requested detail level).")
    body_html: Optional[str] = Field(None, description="Always null — guides are not rendered to HTML.")
    document_date: Optional[date] = Field(None, description="Always null — guides are not dated documents.")
    creation_date: Optional[datetime] = Field(None, description="Always null — guides are not per-row timestamped.")


def _loader():
    from knowledge_base.knowledge_loader import KnowledgeLoader
    kl = KnowledgeLoader()
    kl.load_all()
    return kl


@router.get(
    "",
    response_model=PaginatedResponse[KnowledgeGuideItem],
    summary="Brubru's curated EU policy guides — what the chatbot uses to ground answers",
    description="""**What it does**
Returns Brubru's curated knowledge-base guides — the same markdown explainers that the chatbot uses to ground answers. Each guide is a 100-300-line domain explainer for one policy area (e.g. AI Act, CBAM downstream extension, MFF 2028-2034, Right to Stay Strategy). Every guide has a QUICK FACTS block at the top (latest news, key dates, actors), a body, and a set of keyword triggers used for retrieval.

**When to use it**
For partners who want to ground their own LLM in Brubru's curated EU-policy knowledge — fetch the guides relevant to a topic with `q=<topic>`, embed them as context, and your LLM gets the same grounding the Brubru chatbot uses. Pass `detail_level=Full` to get the complete markdown body (vs the 500-char preview for `Summary`).

**Input**
- `q` — keyword query (e.g. `GDPR`, `AI Act`, `CBAM`, `housing crisis`).
- `detail_level` — `Summary` (default, 500-char preview) or `Full` (complete markdown body).
- `limit` (default 50, max 100), `page` (1-indexed).

**Try it**
```
GET /api/v1/knowledge-guides?q=AI%20Act&detail_level=Full
GET /api/v1/knowledge-guides?limit=100
```

**You get back**
A `PaginatedResponse[KnowledgeGuideItem]` envelope. Each item carries `id`, `title`, `quick_facts` (the leading QUICK FACTS section parsed out), `triggers` (up to 50 keyword triggers), `content` (Full or 500-char preview based on `detail_level`), `content_preview`, `full_content_chars` (total body length).

**Data freshness**
Brubru-curated content (not synced from external sources). Updated by `/morning` Phase 3D (new guides created from news), `/audit-queries` (gap fills from user query analysis), and ad-hoc edits. Approximately 200+ guides as of May 2026.""",
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
        # Summary level: 500-char preview. Full level: the entire markdown body
        # (no cap — Jordi #1 / #8: API users need raw content, not titles).
        body = content if include_full else content[:500]
        data.append(KnowledgeGuideItem(
            id=gid,
            title=parsed["title"],
            summary=None,
            quick_facts=parsed["quick_facts"],
            triggers=sorted(set(triggers_by_guide.get(gid, [])))[:50],
            content=body,
            content_preview=body,
            full_content_chars=len(content),
            public_url=GUIDES_PUBLIC_URL,
            body_txt=body,
            body_html=_render_md(body),
        ))

    env = build_envelope(data, total=total, page=page, limit=limit, detail_level="Full" if include_full else "Summary")
    return env


@router.get(
    "/{guide_id}",
    response_model=KnowledgeGuideItem,
    summary="Look up one knowledge guide by its filename slug — full markdown body",
    description="""**What it does**
Returns the full markdown content of one Brubru knowledge guide by its filename slug. Always returns the complete body — no truncation. Same content the chatbot injects into Claude/Mistral context for grounded answers.

**When to use it**
After locating a guide via the list endpoint (or because you already know the slug from a previous response), use this to fetch the full markdown — useful for embedding the explainer in your own UI, or for feeding into a downstream LLM as context.

**Input**
- `guide_id` (path) — the guide's filename slug (without `.md` extension), e.g. `ai_act_regulation`, `cbam_downstream_goods_extension`, `mff_2028_2034`.

**Try it**
```
GET /api/v1/knowledge-guides/ai_act_regulation
```

**You get back**
A single `KnowledgeGuideItem` with `id`, `title`, `quick_facts`, `triggers[]`, full `content` markdown, `full_content_chars`. HTTP 404 with `reason_code: not_found` if no guide with that slug exists.

**Data freshness**
Brubru-curated content. Guides are updated by `/morning` Phase 3D + ad-hoc edits when major legislative developments warrant a refresh.""",
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
        content=parsed["content"],
        content_preview=parsed["content"],
        full_content_chars=len(parsed["content"]),
        public_url=GUIDES_PUBLIC_URL,
        body_txt=parsed["content"],
        body_html=_render_md(parsed["content"]),
    )
