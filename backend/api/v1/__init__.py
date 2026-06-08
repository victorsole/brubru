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
from . import committee_agendas as _committee_agendas
from . import committees as _committees
from . import consultations as _consultations
from . import council_documents as _council_documents
from . import council_register as _council_register
from . import european_council as _european_council
from . import eurogroup as _eurogroup
from . import ep_emeeting as _ep_emeeting
from . import open_data as _open_data
from . import who_is_who as _who_is_who
from . import general_publications as _general_publications
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
from . import transcripts as _transcripts
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
from . import specialised_a2m as _specialised_a2m
from . import specialised_cohesion as _specialised_cohesion
from . import specialised_comitology as _specialised_comitology
from . import specialised_competition as _specialised_competition
from . import specialised_fta as _specialised_fta
from . import specialised_gi as _specialised_gi
from . import specialised_jrc as _specialised_jrc
from . import specialised_sanctions as _specialised_sanctions
from . import specialised_trade_defence as _specialised_trade_defence
from . import specialised_transparency_register as _specialised_tr

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
router.include_router(_committee_agendas.router)
router.include_router(_transcripts.router)
router.include_router(_calendar.router)
router.include_router(_meps.router)
router.include_router(_predictions.router)
router.include_router(_resolutions.router)
router.include_router(_texts_adopted.texts_adopted_router)
router.include_router(_texts_adopted.texts_submitted_router)
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
router.include_router(_european_council.conclusions_router)
router.include_router(_european_council.meetings_router)
router.include_router(_european_council.euro_summit_router)
router.include_router(_european_council.strategic_agenda_router)
router.include_router(_european_council.members_router)
router.include_router(_european_council.about_router)
router.include_router(_eurogroup.meetings_router)
router.include_router(_eurogroup.documents_router)
router.include_router(_eurogroup.work_programme_router)
router.include_router(_eurogroup.members_router)
router.include_router(_eurogroup.about_router)
router.include_router(_ep_emeeting.router)
router.include_router(_ep_emeeting.documents_router)
router.include_router(_open_data.datasets_router)
router.include_router(_open_data.hvd_router)
router.include_router(_open_data.catalogues_router)
router.include_router(_who_is_who.departments_router)
router.include_router(_who_is_who.officials_router)
router.include_router(_general_publications.router)
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
router.include_router(_specialised_a2m.router)
router.include_router(_specialised_cohesion.router)
router.include_router(_specialised_comitology.router)
router.include_router(_specialised_competition.router)
router.include_router(_specialised_fta.router)
router.include_router(_specialised_gi.router)
router.include_router(_specialised_jrc.router)
router.include_router(_specialised_sanctions.router)
router.include_router(_specialised_trade_defence.router)
router.include_router(_specialised_tr.router)
# Raw filtered v1 spec only (/api/v1/openapi.json). The v1 Scalar viewer and the
# /api/docs→v1 alias have been retired; v2 is now the only public API reference.
router.include_router(_docs.router)
