"""EBA — European Banking Authority — /api/v2/eu-financial-institutions/eba/{news,publications,events}."""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter(prefix="/eba")

_BODY = "European Banking Authority"
_ACRO = "the EBA"
_TAG = "v2-eu-fin-eba"

register_resource(
    router, body_code="eba", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="EBA press releases, speeches and interviews (server-rendered listings) plus the detail pages.",
    extra="Press releases, speeches and interviews from the European Banking Authority.",
)
register_resource(
    router, body_code="eba", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the EBA publications listing (server-rendered); document bodies are extracted from the source PDFs.",
    extra="Guidelines, technical standards, reports, consultation papers and factsheets.",
)
register_resource(
    router, body_code="eba", item_type="event", slug="events", noun="events",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the EBA events listing (server-rendered).",
    extra="Board of Supervisors meetings, research workshops, hearings and conferences, with their dates.",
)
