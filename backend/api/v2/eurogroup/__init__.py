"""
"Eurogroup" domain — /api/v2/eurogroup/*.

The Eurogroup (informal body of euro-area finance ministers) as a top-level
institutional domain, sibling to "Council of the EU" and "European Council".
One sub-router per surface, copy-pasted verbatim from v1:
    /eurogroup-meetings        meetings (agenda + Main results)
    /eurogroup-documents       document register (agendas, summing-up letters)
    /eurogroup-work-programme   the Eurogroup work programme
    /eurogroup-members         members of the Eurogroup
    /eurogroup-about           institutional reference

Same contract as the rest of v2 (auth + scope + 60 req/min + per-call euro
debit, PaginatedResponse envelope, canonical error shapes, 5-section Markdown
descriptions). LIVE endpoints delegate to the v1 handlers.
"""

from fastapi import APIRouter

from . import eurogroup as _eg

router = APIRouter(prefix="/eurogroup")
router.include_router(_eg.meetings_router)
router.include_router(_eg.documents_router)
router.include_router(_eg.work_programme_router)
router.include_router(_eg.members_router)
router.include_router(_eg.about_router)
