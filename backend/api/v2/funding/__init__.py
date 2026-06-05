"""
"Funding & Tenders" domain — /api/v2/funding/*.

EU funding opportunities and public procurement as a top-level domain, sibling
to the institution folders. Sources mirrored verbatim from v1:
    /funding-opportunities   EU funding opportunities
    /ft-calls-for-proposals  Funding & Tenders portal — calls for proposals (grants)
    /ft-calls-for-tenders    Funding & Tenders portal — calls for tenders
    /ft-funded-projects      Funding & Tenders portal — funded projects
    /tenders                 TED — Tenders Electronic Daily (EU public procurement)

Same contract as the rest of v2 (auth + scope + 60 req/min + per-call euro debit,
PaginatedResponse envelope, canonical error shapes, 5-section Markdown
descriptions). LIVE endpoints delegate to the v1 handlers. Scope: read:commission
(mirrors v1 — these are Commission-administered funding + EU procurement).
"""

from fastapi import APIRouter

from . import funding_opportunities as _funding_opportunities
from . import funding_tenders as _funding_tenders
from . import ted_tenders as _ted_tenders

router = APIRouter(prefix="/funding")
router.include_router(_funding_opportunities.funding_router)
router.include_router(_funding_tenders.calls_router)
router.include_router(_funding_tenders.tenders_router)
router.include_router(_funding_tenders.projects_router)
router.include_router(_ted_tenders.tenders_router)
