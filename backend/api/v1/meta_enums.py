"""
/api/v1/meta/enums — valid values for every filter partners can pass.

Partners call once, cache forever (refresh on schema bump via `generated_at`).
Eliminates the "what values work?" support-ticket class entirely.
"""

from datetime import datetime
from typing import Any, Dict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.database import get_db
from models.eu_law import EULaw
from models.user import User

from ._deps import api_user_with_rate_limit

router = APIRouter(prefix="/meta", tags=["v1-meta"])


# Static lists — stable, don't change between requests.
EP_COMMITTEES = [
    "AFCO", "AFET", "AGRI", "BUDG", "CONT", "CULT", "DEVE", "ECON", "EMPL",
    "ENVI", "FEMM", "IMCO", "INTA", "ITRE", "JURI", "LIBE", "PECH", "PETI",
    "REGI", "SANT", "SEDE", "TRAN", "DROI", "TAXE", "ANIT", "SANI",
]

PROCEDURE_STATUSES = [
    "announced", "proposed", "in_committee", "awaiting_first_reading",
    "first_reading_done", "awaiting_council", "awaiting_second_reading",
    "in_trilogue", "adopted", "published", "withdrawn", "rejected", "blocked",
]

STAKEHOLDER_USER_TYPES = [
    "BUSINESS_ASSOCIATION", "COMPANY", "NGO", "CITIZEN", "PUBLIC_AUTHORITY",
    "ACADEMIC_RESEARCH", "CONSUMER_ORGANISATION", "TRADE_UNION",
    "ENVIRONMENTAL_ORGANISATION", "OTHER",
]

DETAIL_LEVELS = ["Minimal", "Summary", "Full"]

HTTP_METHODS_BY_DATASET = {
    "laws": ["GET"],
    "procedures": ["GET"],
    "commissioners": ["GET"],
    "consultations": ["GET"],
    "legal-text": ["GET", "POST"],
    "publications": ["GET"],
    "knowledge-guides": ["GET"],
    "eprs": ["GET"],
    "committees": ["GET"],
    "calendar": ["GET"],
    "meps": ["GET"],
    "predictions": ["GET"],
}

EPRS_PUBLICATION_TYPES = [
    "BRIEFING", "STUDY", "IN_DEPTH_ANALYSIS", "AT_A_GLANCE",
    "EU_LEGISLATION_IN_PROGRESS", "INITIAL_APPRAISAL", "EX_POST_EVALUATION",
    "HISTORICAL_ARCHIVES", "OTHER",
]

CALENDAR_INSTITUTIONS = [
    "EP", "COUNCIL", "EUROPEAN_COUNCIL", "COMMISSION", "ECJ", "ECB",
    "ESMA", "EMA", "EBA", "EIOPA", "COR", "EESC",
]


@router.get("/enums", summary="All valid enum values for v1 filters")
async def meta_enums(
    user: User = Depends(api_user_with_rate_limit),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    # Live values from DB (fast: distinct on indexed columns; policy_area is small cardinality)
    policy_areas = [
        row[0] for row in db.execute(
            select(EULaw.policy_area).where(EULaw.policy_area.isnot(None)).distinct().order_by(EULaw.policy_area)
        ).all()
    ]
    doc_types = [
        row[0] for row in db.execute(
            select(func.coalesce(EULaw.doc_type_normalized, EULaw.doc_type))
            .where(func.coalesce(EULaw.doc_type_normalized, EULaw.doc_type).isnot(None))
            .distinct()
        ).all() if row[0]
    ]

    return {
        "datasets": list(HTTP_METHODS_BY_DATASET.keys()),
        "methods_by_dataset": HTTP_METHODS_BY_DATASET,
        "doc_types": sorted(set(doc_types)),
        "policy_areas": policy_areas,
        "ep_committees": EP_COMMITTEES,
        "procedure_statuses": PROCEDURE_STATUSES,
        "stakeholder_user_types": STAKEHOLDER_USER_TYPES,
        "detail_levels": DETAIL_LEVELS,
        "eprs_publication_types": EPRS_PUBLICATION_TYPES,
        "calendar_institutions": CALENDAR_INSTITUTIONS,
        "languages": ["en", "fr", "de", "es", "it", "nl", "pt", "pl", "hu", "ro"],
        "countries_iso3_sample": [
            "BEL", "FRA", "DEU", "ESP", "ITA", "NLD", "POL", "ROU", "SWE", "GBR", "USA",
        ],
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
