"""SRB — Single Resolution Board —
/api/v2/eu-financial-institutions/srb/{news,publications,events}."""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter(prefix="/srb")

_BODY = "Single Resolution Board"
_ACRO = "the SRB"
_TAG = "v2-eu-fin-srb"

register_resource(
    router, body_code="srb", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the SRB news archive (rendered from the SRB site) plus the detail pages.",
    extra="Press releases, statements, speeches and interviews from the Single Resolution Board.",
)
register_resource(
    router, body_code="srb", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the SRB public register of documents; bodies are extracted from the source PDFs.",
    extra="Decisions, reports, guidance, budgets and other documents from the public register.",
)
register_resource(
    router, body_code="srb", item_type="event", slug="events", noun="events",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the SRB events listing.",
    extra="Conferences, technical meetings and public engagements, with their dates.",
)
