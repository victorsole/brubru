"""
Brubru Data Provider API v1

Public paid REST surface at /api/v1/*.

Gated by X-API-Key header (see api.auth_api_key).
Rate-limited at 60 req/min per key (see api.v1._deps).
All responses use the canonical PaginatedResponse envelope.
All errors use the canonical error shapes in _errors.
"""

from fastapi import APIRouter

from . import calendar as _calendar
from . import commissioners as _commissioners
from . import committees as _committees
from . import consultations as _consultations
from . import docs as _docs
from . import eprs as _eprs
from . import knowledge_guides as _knowledge_guides
from . import laws as _laws
from . import legal_text as _legal_text
from . import meps as _meps
from . import meta as _meta
from . import meta_enums as _meta_enums
from . import predictions as _predictions
from . import procedures as _procedures
from . import publications as _publications

router = APIRouter(prefix="/api/v1")
router.include_router(_meta.router)
router.include_router(_meta_enums.router)
router.include_router(_consultations.router)
router.include_router(_laws.router)
router.include_router(_procedures.router)
router.include_router(_commissioners.router)
router.include_router(_legal_text.router)
router.include_router(_publications.router)
router.include_router(_knowledge_guides.router)
router.include_router(_eprs.router)
router.include_router(_committees.router)
router.include_router(_calendar.router)
router.include_router(_meps.router)
router.include_router(_predictions.router)
router.include_router(_docs.router)

# Pretty docs also served at /api/docs (convenience alias).
docs_alias_router = APIRouter(prefix="/api")
docs_alias_router.include_router(_docs.router)
