"""ESRB — European Systemic Risk Board —
/api/v2/eu-financial-institutions/esrb/{news,publications,events}."""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter(prefix="/esrb")

_BODY = "European Systemic Risk Board"
_ACRO = "the ESRB"
_TAG = "v2-eu-fin-esrb"

register_resource(
    router, body_code="esrb", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ESRB press RSS feed (press releases + speeches) plus the detail pages.",
    extra="Press releases and speeches from the European Systemic Risk Board.",
)
register_resource(
    router, body_code="esrb", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ESRB macroprudential-policy pages (server-rendered); bodies are extracted from the source PDFs.",
    extra="Recommendations, warnings, opinions, stress tests and responses.",
)
register_resource(
    router, body_code="esrb", item_type="event", slug="events", noun="events",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ESRB schedule page (server-rendered).",
    extra="Conferences, workshops and meetings, with their dates.",
)
