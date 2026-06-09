"""AMLA — Anti-Money Laundering Authority —
/api/v2/eu-financial-institutions/amla/{news,publications,events}."""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter(prefix="/amla")

_BODY = "Anti-Money Laundering Authority"
_ACRO = "AMLA"
_TAG = "v2-eu-fin-amla"

register_resource(
    router, body_code="amla", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the AMLA news RSS feed plus the detail pages.",
    extra="News articles and press releases from the Anti-Money Laundering Authority.",
)
register_resource(
    router, body_code="amla", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the AMLA document library; bodies are extracted from the source PDFs.",
    extra="Guidelines, technical standards, consultation papers and other AMLA documents.",
)
register_resource(
    router, body_code="amla", item_type="event", slug="events", noun="events",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the AMLA public hearings and speaking engagements listings.",
    extra="Public hearings and speaking engagements, with their dates.",
)
