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
# FTS recipients (economy_items-backed), grouped under "Funded Projects".
from . import eu_funding_recipients as _eu_funding_recipients
from . import agency_procurement as _agency_procurement
from . import funding_all as _funding_all
from . import startups as _startups
# Per-fund cohesion / structural-fund finance endpoints (DB-backed,
# eu_cohesion_finances, Socrata 9qee-iv7c). Built one fund at a time — ERDF live.
from . import cohesion_finances as _cohesion_finances
# Per-fund achievement / outcome indicators (DB-backed, eu_cohesion_outcomes,
# Socrata xi3a-zddk). Built one fund at a time — ESF+ live.
from . import cohesion_outcomes as _cohesion_outcomes

router = APIRouter(prefix="/funding")
router.include_router(_funding_opportunities.funding_router)
router.include_router(_funding_tenders.calls_router)
router.include_router(_funding_tenders.tenders_router)
router.include_router(_funding_tenders.projects_router)
router.include_router(_ted_tenders.tenders_router)
router.include_router(_eu_funding_recipients.router)
router.include_router(_agency_procurement.router)
router.include_router(_funding_all.router)
router.include_router(_startups.router)
router.include_router(_cohesion_finances.router)
router.include_router(_cohesion_outcomes.router)
