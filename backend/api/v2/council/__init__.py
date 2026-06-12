"""
"Council of the EU" domain — /api/v2/council/*.

The Council of the EU as a top-level institutional domain, sibling to
"Legislative data", "European Parliament", "European Commission" and
"Proprietary Databases". One sub-router per source, copy-pasted verbatim from
v1 (multi-institution endpoints are excluded):
    /council-documents       Council documents (list + detail) — press releases,
                             conclusions, meeting agendas, summits
    /council-configurations  the 10 Council configurations (+ Eurogroup)

Same contract as the rest of v2 (auth + scope + 60 req/min + per-call euro
debit, PaginatedResponse envelope, canonical error shapes, 5-section Markdown
descriptions). LIVE endpoints delegate to the v1 handlers so there is exactly
one implementation during the v1+v2 coexistence period.
"""

from fastapi import APIRouter

from . import council_documents as _council_documents
from . import council_register as _council_register
from . import sanctions_regimes as _sanctions_regimes

router = APIRouter(prefix="/council")
router.include_router(_council_documents.router)
router.include_router(_council_documents.configurations_router)
router.include_router(_council_register.meetings_router)
router.include_router(_council_register.votes_router)
router.include_router(_council_register.register_router)
router.include_router(_council_register.oj_router)
router.include_router(_council_register.prep_router)
router.include_router(_council_register.press_router)
router.include_router(_council_register.research_router)
router.include_router(_council_register.treaties_router)
router.include_router(_sanctions_regimes.router)
