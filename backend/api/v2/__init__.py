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
from .parliament import router as _parliament_router
from .commission import router as _commission_router
from .council import router as _council_router
from .european_council import router as _european_council_router
from .eurogroup import router as _eurogroup_router
from .funding import router as _funding_router
from .open_data import router as _open_data_router
from .who_is_who import router as _who_is_who_router
from .general_publications import router as _general_publications_router
from .proprietary import router as _proprietary_router
from .ecb import router as _ecb_router
from .eu_financial_institutions import router as _eu_fin_router
from .esm import router as _esm_router
from .berec import router as _berec_router
from .acer import router as _acer_router
from .eit import router as _eit_router
from .enisa import router as _enisa_router
from .eu_lisa import router as _eu_lisa_router
from .euipo import router as _euipo_router
from .cpvo import router as _cpvo_router
from .geographical_indications import router as _geographical_indications_router
from .ema import router as _ema_router
from .ecdc import router as _ecdc_router
from .efsa import router as _efsa_router
from .eea import router as _eea_router
from .echa import router as _echa_router
from .euda import router as _euda_router
from .eige import router as _eige_router
from .cedefop import router as _cedefop_router
from .euaa import router as _euaa_router
from .fra import router as _fra_router
from .eu_osha import router as _eu_osha_router
from . import docs as _docs

router = APIRouter(prefix="/api/v2")
router.include_router(_legislative_router)
router.include_router(_parliament_router)
router.include_router(_commission_router)
router.include_router(_council_router)
router.include_router(_european_council_router)
router.include_router(_eurogroup_router)
router.include_router(_funding_router)
router.include_router(_open_data_router)
router.include_router(_who_is_who_router)
router.include_router(_general_publications_router)
router.include_router(_proprietary_router)
# Economy & Finance — folder #1 (ECB + SSM), folder #2 (the EU financial
# institutions) and folder #3 (ESM, intergovernmental, its own folder).
router.include_router(_ecb_router)
router.include_router(_eu_fin_router)
router.include_router(_esm_router)
# Single-market / digital EU agencies (api_market.md), each its own folder.
router.include_router(_berec_router)
router.include_router(_acer_router)
router.include_router(_eit_router)
router.include_router(_enisa_router)
router.include_router(_eu_lisa_router)
router.include_router(_euipo_router)
router.include_router(_cpvo_router)
# Geographical Indications — thematic domain (eAmbrosia EU + third-country, EUIPO GIView).
router.include_router(_geographical_indications_router)
# Health agencies (api_health.md), each its own folder.
router.include_router(_ema_router)
router.include_router(_ecdc_router)
router.include_router(_efsa_router)
router.include_router(_eea_router)
router.include_router(_echa_router)
router.include_router(_euda_router)
router.include_router(_eige_router)
router.include_router(_cedefop_router)
router.include_router(_euaa_router)
router.include_router(_fra_router)
router.include_router(_eu_osha_router)
# Scalar docs + filtered OpenAPI spec → /api/v2/docs and /api/v2/openapi.json
router.include_router(_docs.router)

# Canonical public docs alias: /api/docs and /api/openapi.json serve the v2
# Scalar viewer and v2 spec. This is the ONLY API reference Brubru links publicly.
docs_alias_router = APIRouter(prefix="/api")
docs_alias_router.include_router(_docs.router)
