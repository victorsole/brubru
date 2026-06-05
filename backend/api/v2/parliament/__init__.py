"""
"European Parliament" domain — /api/v2/parliament/*.

The European Parliament as a top-level institutional domain, sibling to
"Legislative data" and "Proprietary Databases". One sub-router per source
(mirroring the v1 EP surface), copy-pasted verbatim from v1:
    /meps                     Members of the European Parliament
    /amendments               EP committee amendments
    /votes                    EP roll-call votes (+ per-MEP records)
    /ep-documents             Unified EP committee output
    /reports                  EP committee reports / draft recommendations
    /opinions                 Associated-committee opinions
    /committees/{code}/...     Committee work-items + minutes
    /texts-adopted            EP plenary adopted texts
    /texts-submitted          EP plenary tabled (not-yet-adopted) texts
    /resolutions              EP non-legislative resolutions
    /eprs                     EPRS think-tank publications
    /webstreams               EP committee webstreams + transcripts
    /parliamentary-questions  EP questions to Commission / Council / ECB

Same contract as the rest of v2 (auth + scope + 60 req/min + per-call euro
debit, PaginatedResponse envelope, canonical error shapes, 5-section Markdown
descriptions). LIVE endpoints delegate to the v1 handlers so there is exactly
one implementation during the v1+v2 coexistence period.
"""

from fastapi import APIRouter

from . import meps as _meps
from . import ep_entities as _ep_entities
from . import committees as _committees
from . import texts_adopted as _texts_adopted
from . import resolutions as _resolutions
from . import eprs as _eprs
from . import webstreams as _webstreams
from . import parliamentary_questions as _parliamentary_questions
from . import ep_emeeting as _ep_emeeting

router = APIRouter(prefix="/parliament")
router.include_router(_meps.router)
router.include_router(_ep_entities.amendments_router)
router.include_router(_ep_entities.votes_router)
router.include_router(_ep_entities.ep_documents_router)
router.include_router(_ep_entities.reports_router)
router.include_router(_ep_entities.opinions_router)
router.include_router(_committees.router)
router.include_router(_texts_adopted.texts_adopted_router)
router.include_router(_texts_adopted.texts_submitted_router)
router.include_router(_resolutions.router)
router.include_router(_eprs.router)
router.include_router(_webstreams.router)
router.include_router(_parliamentary_questions.parl_q_router)
router.include_router(_ep_emeeting.router)
router.include_router(_ep_emeeting.documents_router)
