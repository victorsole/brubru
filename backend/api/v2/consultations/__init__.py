"""
"Public Consultations" domain — /api/v2/consultations/*.

Every EU public consultation in one place. The Commission's central "Have Your
Say" consultations live at /api/v2/commission/consultations; this folder adds the
decentralised agency consultations (ECHA, EMA, BEREC, EIOPA, EASA, ERA, ...) that
agencies run on their own sites and that never reach Have Your Say, plus an
all-institutions aggregate at /consultations/all.

economy_items-backed (item_type 'consultation'), one register_resource per agency.
Tag v2-consultations → grouped in the "Public Consultations" Postman folder.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource
from . import consultations_all as _consultations_all

router = APIRouter(prefix="/consultations")

# --- EMA — draft documents under public consultation ---------------------- #
register_resource(
    router, body_code="ema", item_type="consultation", slug="ema",
    noun="EMA public consultations", body_name="the European Medicines Agency", acronym="EMA",
    tag="v2-consultations",
    source="the EMA open-consultations page.",
    extra="Draft documents the European Medicines Agency has open for public consultation — herbal "
          "monographs, scientific guidelines, concept papers and assessment reports — each linking "
          "to the document. Filter with q (e.g. a substance or guideline topic).",
)

# --- BEREC — public consultations & calls for inputs ---------------------- #
register_resource(
    router, body_code="berec", item_type="consultation", slug="berec",
    noun="BEREC public consultations", body_name="BEREC", acronym="BEREC", tag="v2-consultations",
    source="the BEREC public consultations & calls for inputs.",
    extra="BEREC's public consultations and calls for inputs on electronic-communications "
          "regulation. Filter with q (e.g. 'roaming' or 'net neutrality').",
)

# --- EIOPA — insurance & pensions supervisory consultations --------------- #
register_resource(
    router, body_code="eiopa", item_type="consultation", slug="eiopa",
    noun="EIOPA public consultations", body_name="EIOPA", acronym="EIOPA", tag="v2-consultations",
    source="the EIOPA consultations & surveys.",
    extra="EIOPA's public consultations and surveys on insurance and occupational-pensions "
          "supervision. Filter with q (e.g. 'Solvency II' or 'IORP').",
)

router.include_router(_consultations_all.router)
