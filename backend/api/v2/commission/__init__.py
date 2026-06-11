"""
"European Commission" domain — /api/v2/commission/*.

The European Commission as a top-level institutional domain, sibling to
"Legislative data", "European Parliament" and "Proprietary Databases". One
sub-router per source (the core Commission surface, copy-pasted verbatim from
v1; multi-institution endpoints are excluded):
    /commissioners                  College of Commissioners (+ profile + agenda)
    /commission-register-documents  Transparency Register: College agendas, COM/SWD, IAs
    /meetings                       Transparency Initiative meetings with lobbyists
    /rsb-opinions                   Regulatory Scrutiny Board opinions
    /infringements                  Commission infringement decisions vs Member States
    /consultations                  Have Your Say consultations + calls for evidence
    /tris-notifications             National technical-regulation notifications (TRIS)

Same contract as the rest of v2 (auth + scope + 60 req/min + per-call euro
debit, PaginatedResponse envelope, canonical error shapes, 5-section Markdown
descriptions). LIVE endpoints delegate to the v1 handlers so there is exactly
one implementation during the v1+v2 coexistence period. Note: Commission
delegated/implementing acts live under "Legislative data -> Legislative
Documents"; the Funding & Tenders and Specialised EC Databases clusters are
their own domains.
"""

from fastapi import APIRouter

from . import commissioners as _commissioners
from . import commission_register as _commission_register
from . import meetings as _meetings
from . import rsb_opinions as _rsb_opinions
from . import infringements as _infringements
from . import consultations as _consultations
from . import tris_notifications as _tris_notifications
# EC database folders (economy_items-backed; one per database).
from . import financial_sanctions as _financial_sanctions
from . import research_projects as _research_projects
from . import tariff_rulings as _tariff_rulings
from . import taric_tariffs as _taric_tariffs
from . import agridata as _agridata
from . import cap_beneficiaries as _cap_beneficiaries
from . import trade_defence as _trade_defence
from . import comitology as _comitology
from . import expert_groups as _expert_groups
from . import dma_cases as _dma_cases
from . import state_aid as _state_aid
from . import rasff as _rasff

router = APIRouter(prefix="/commission")
router.include_router(_commissioners.router)
router.include_router(_commission_register.router)
router.include_router(_meetings.router)
router.include_router(_rsb_opinions.router)
router.include_router(_infringements.router)
router.include_router(_consultations.router)
router.include_router(_tris_notifications.router)
router.include_router(_financial_sanctions.router)
router.include_router(_research_projects.router)
router.include_router(_tariff_rulings.router)
router.include_router(_taric_tariffs.router)
router.include_router(_agridata.router)
router.include_router(_cap_beneficiaries.router)
router.include_router(_trade_defence.router)
router.include_router(_comitology.router)
router.include_router(_expert_groups.router)
router.include_router(_dma_cases.router)
router.include_router(_state_aid.router)
router.include_router(_rasff.router)
