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
from . import catalan_translations as _catalan_translations
from . import commission_register as _commission_register
from . import commissioners as _commissioners
from . import committees as _committees
from . import consultations as _consultations
from . import council_documents as _council_documents
from . import docs as _docs
from . import ep_entities as _ep_entities
from . import eprs as _eprs
from . import knowledge_guides as _knowledge_guides
from . import laws as _laws
from . import legal_text as _legal_text
from . import meps as _meps
from . import meta as _meta
from . import meta_enums as _meta_enums
from . import metadata as _metadata
from . import predictions as _predictions
from . import procedures as _procedures
from . import publications as _publications
from . import resolutions as _resolutions
from . import texts_adopted as _texts_adopted
from . import w4_endpoints as _w4
from . import w5_endpoints as _w5
from . import webstreams as _webstreams
from . import citations as _citations
from . import infringements_funding as _infringements_funding
from . import funding_tenders_collections as _ft_collections
from . import cellar_discover as _cellar_discover
from . import vocabularies as _vocabularies
from . import eurio_discover as _eurio_discover
from . import identify as _identify
from . import ecli_search as _ecli_search
from . import specialised_fta as _specialised_fta
from . import specialised_gi as _specialised_gi
from . import specialised_sanctions as _specialised_sanctions
from . import specialised_trade_defence as _specialised_trade_defence

router = APIRouter(prefix="/api/v1")
router.include_router(_meta.router)
router.include_router(_meta_enums.router)
router.include_router(_consultations.router)
router.include_router(_catalan_translations.router)
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
router.include_router(_resolutions.router)
router.include_router(_texts_adopted.texts_adopted_router)
router.include_router(_texts_adopted.texts_submitted_router)
router.include_router(_council_documents.router)
router.include_router(_metadata.router)
router.include_router(_metadata.meta_router)
router.include_router(_ep_entities.amendments_router)
router.include_router(_ep_entities.votes_router)
router.include_router(_ep_entities.ep_documents_router)
router.include_router(_ep_entities.press_releases_router)
router.include_router(_ep_entities.reports_router)
router.include_router(_ep_entities.opinions_router)
router.include_router(_w4.parl_q_router)
router.include_router(_w4.meetings_router)
router.include_router(_w4.rsb_router)
router.include_router(_w4.delegated_router)
router.include_router(_w4.implementing_router)
router.include_router(_w4.tris_router)
router.include_router(_w5.research_router)
router.include_router(_w5.officials_router)
router.include_router(_w5.tenders_router)
router.include_router(_commission_register.router)
router.include_router(_webstreams.router)
router.include_router(_citations.router)
router.include_router(_citations.citations_router)
router.include_router(_infringements_funding.infringements_router)
router.include_router(_infringements_funding.funding_router)
router.include_router(_ft_collections.calls_router)
router.include_router(_ft_collections.tenders_router)
router.include_router(_ft_collections.projects_router)
router.include_router(_cellar_discover.router)
router.include_router(_vocabularies.router)
router.include_router(_eurio_discover.router)
router.include_router(_identify.router)
router.include_router(_ecli_search.router)
router.include_router(_specialised_fta.router)
router.include_router(_specialised_gi.router)
router.include_router(_specialised_sanctions.router)
router.include_router(_specialised_trade_defence.router)
router.include_router(_docs.router)

# Pretty docs also served at /api/docs (convenience alias).
docs_alias_router = APIRouter(prefix="/api")
docs_alias_router.include_router(_docs.router)
