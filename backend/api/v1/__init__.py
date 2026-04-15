"""
Brubru Data Provider API v1

Public paid REST surface at /api/v1/*.

Gated by X-API-Key header (see api.auth_api_key).
Rate-limited at 60 req/min per key (see api.v1._deps).
All responses use the canonical PaginatedResponse envelope.
All errors use the canonical error shapes in _errors.
"""

from fastapi import APIRouter

from . import commissioners as _commissioners
from . import consultations as _consultations
from . import docs as _docs
from . import laws as _laws
from . import legal_text as _legal_text
from . import meta as _meta
from . import procedures as _procedures

router = APIRouter(prefix="/api/v1")
router.include_router(_meta.router)
router.include_router(_consultations.router)
router.include_router(_laws.router)
router.include_router(_procedures.router)
router.include_router(_commissioners.router)
router.include_router(_legal_text.router)
router.include_router(_docs.router)

# Pretty docs also served at /api/docs (convenience alias).
docs_alias_router = APIRouter(prefix="/api")
docs_alias_router.include_router(_docs.router)
