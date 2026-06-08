"""EIOPA — European Insurance and Occupational Pensions Authority —
/api/v2/eu-financial-institutions/eiopa/{news,publications,events}."""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter(prefix="/eiopa")

_BODY = "European Insurance and Occupational Pensions Authority"
_ACRO = "EIOPA"
_TAG = "v2-eu-fin-eiopa"
_SRC = "EIOPA's server-rendered EU ECL listings (with ISO-dated cards), paginated, plus the detail pages."

register_resource(
    router, body_code="eiopa", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG, source=_SRC,
    extra="News articles, interviews, feature articles and speeches/presentations.",
)
register_resource(
    router, body_code="eiopa", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG, source=_SRC,
    extra="Reports, technical standards, studies and consultations from the EIOPA document library.",
)
register_resource(
    router, body_code="eiopa", item_type="event", slug="events", noun="events",
    body_name=_BODY, acronym=_ACRO, tag=_TAG, source=_SRC,
    extra="Public workshops, debates and conferences, with their dates.",
)
