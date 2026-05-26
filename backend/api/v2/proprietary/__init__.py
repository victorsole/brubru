"""
"Brubru Proprietary Databases" domain — /api/v2/proprietary/*.

Brubru's own data products (not mirrored EU institutional sources). One
sub-router per source:
    /guides    Curated EU-policy knowledge guides (the chatbot's grounding)
    /catalan   The EU acquis translated into Catalan (Softcatalà NMT / Sonnet)
    /canon     Brubru deep-dive HTML reports: EU Canon + law deep-dives

Same 1:1 mapping the "Legislative data" domain follows (Postman collection
"Brubru Proprietary Databases" -> sub-folders -> URL segments).

Structure contract — IDENTICAL to v1 (what Jordi reviewed): shared
api_user_with_rate_limit dependency (auth + scope + 60 req/min + per-call euro
debit), the canonical PaginatedResponse envelope, the canonical error shapes,
and the 5-section Markdown description contract.

guides + catalan DELEGATE to the existing v1 handlers (single source of truth
during v1+v2 coexistence). canon is implemented natively here off a committed
manifest (the HTML lives on SiteGround; metadata snapshots into
knowledge_base/canon_reports.json so it travels with the backend deploy).
"""

from fastapi import APIRouter

from . import guides as _guides
from . import catalan as _catalan
from . import canon as _canon

router = APIRouter(prefix="/proprietary")
router.include_router(_guides.router)
router.include_router(_catalan.router)
router.include_router(_canon.router)
