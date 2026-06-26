"""
"Public Consultations" domain — /api/v2/consultations/*.

Every EU public consultation from every body in one folder. The comprehensive feed
(/all) is a query-time UNION of the EC "Have Your Say" register (public_consultations
— the rich source: status, closing date, responsible DG, policy areas, feedback
counts) and the agency consultations in economy_items, with an on-demand picker:
pick a body, a Brubru policy family, an institution, or everything.

Endpoints: directory (root), /all (the aggregate, body/family/institution/status
filters), /bodies (pick-list), /{id} (detail). The per-agency convenience endpoints
(/ema, /berec, /eiopa, /amla, /echa) stay for direct access. Tag v2-consultations
→ grouped in the "Public Consultations" Postman folder.
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

# --- AMLA — anti-money-laundering consultations --------------------------- #
register_resource(
    router, body_code="amla", item_type="consultation", slug="amla",
    noun="AMLA public consultations", body_name="AMLA", acronym="AMLA", tag="v2-consultations",
    source="the AMLA public consultations.",
    extra="The Anti-Money Laundering Authority's public consultations (draft guidelines and RTS). "
          "Filter with q.",
)

# --- ECHA — chemicals consultations (by type) ---------------------------- #
register_resource(
    router, body_code="echa", item_type="consultation", slug="echa",
    noun="ECHA public consultations", body_name="the European Chemicals Agency", acronym="ECHA",
    tag="v2-consultations",
    source="the ECHA current-consultations overview, grouped by type.",
    extra="ECHA's open public consultations by type -- applications for authorisation, restriction "
          "proposals, harmonised classification & labelling (CLH), testing proposals, calls for "
          "comments & evidence, candidates for substitution -- each with the count of open "
          "consultations, the closing date and a link to the full sub-list. Filter with q.",
)


# Directory at the folder root (the parent router carries the /consultations prefix,
# so "" resolves to /consultations without the empty-prefix include error).
from fastapi import Depends, Request  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from core.database import get_db  # noqa: E402
from models.user import User  # noqa: E402
from api.v1._deps import api_user_with_rate_limit  # noqa: E402


@router.get("", response_model=_consultations_all.ConsultationsDirectory, tags=["v2-consultations"],
            summary="Consultations folder directory — every EU public consultation, aggregated",
            description=(
                "**What it does**\nOne-call overview of every EU public consultation: open vs closed, "
                "bodies and policy families covered, split by institution.\n\n**When to use it**\nBefore "
                "querying the feed.\n\n**Input**\nNo parameters.\n\n**Try it**\n```\nGET /api/v2/consultations\n```\n\n"
                "**You get back**\nA summary. Then `/api/v2/consultations/all`, `/api/v2/consultations/bodies`, "
                "or `/api/v2/consultations/{id}`.\n\n**Data freshness**\nLive union of the Have Your Say "
                "register + agency consultations."))
async def _consultations_directory(request: Request, db: Session = Depends(get_db),
                                   user: User = Depends(api_user_with_rate_limit)):
    return _consultations_all.build_directory(db)


router.include_router(_consultations_all.router)
