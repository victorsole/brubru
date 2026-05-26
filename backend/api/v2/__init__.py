"""
Brubru Data Provider API v2 — institution-based surface at /api/v2/*.

v2 reorganises the public API around EU institutions and data sources, as
reviewed with Jordi. The first domain is "Legislative data"
(/api/v2/legislative/*) with one sub-router per source: EUR-Lex, Legislative
Observatory (OEIL), Legislative Train, EuroVoc.

Design contract — IDENTICAL to v1 (the structure Jordi assessed and approved):
- same auth/scope/billing dependency  (api.v1._deps.api_user_with_rate_limit)
- same response envelope               (api.v1._envelope.PaginatedResponse)
- same canonical error shapes          (api.v1._errors — broadened to /api/v2/*)
- same documentation contract          (plain-English summary= +
  5-section Markdown description=: What it does / When to use it / Input /
  Try it / You get back / Data freshness)

LIVE endpoints delegate to the v1 handler functions so there is exactly one
implementation during the v1+v2 coexistence period; cross-links in the
response body are rewritten to the v2 path. PROPOSED endpoints are
implemented natively here. When v1 is retired, the shared logic moves to a
service layer and v1 becomes a thin alias of v2.
"""

from fastapi import APIRouter

from .legislative import router as _legislative_router
from .proprietary import router as _proprietary_router

router = APIRouter(prefix="/api/v2")
router.include_router(_legislative_router)
router.include_router(_proprietary_router)
