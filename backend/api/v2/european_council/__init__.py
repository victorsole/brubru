"""
"European Council" domain — /api/v2/european-council/*.

The European Council (heads of state or government, Art 15 TEU) as a top-level
institutional domain, sibling to "Council of the EU" and "Eurogroup". One
sub-router per surface, copy-pasted verbatim from v1:
    /euco-conclusions       conclusions register (2004-present)
    /euco-meetings          summit meetings
    /euco-euro-summit       the Euro Summit (euro-area leaders)
    /euco-strategic-agenda  Strategic Agenda 2024-2029
    /euco-members           members of the European Council
    /euco-about             institutional reference

Same contract as the rest of v2 (auth + scope + 60 req/min + per-call euro
debit, PaginatedResponse envelope, canonical error shapes, 5-section Markdown
descriptions). LIVE endpoints delegate to the v1 handlers.
"""

from fastapi import APIRouter

from . import european_council as _ec

router = APIRouter(prefix="/european-council")
router.include_router(_ec.conclusions_router)
router.include_router(_ec.meetings_router)
router.include_router(_ec.euro_summit_router)
router.include_router(_ec.strategic_agenda_router)
router.include_router(_ec.members_router)
router.include_router(_ec.about_router)
