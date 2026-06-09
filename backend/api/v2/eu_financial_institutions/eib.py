"""EIB — European Investment Bank (with EIF embedded) —
/api/v2/eu-financial-institutions/eib/{news,publications,events}."""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter(prefix="/eib")

_BODY = "European Investment Bank"
_ACRO = "the EIB"
_TAG = "v2-eu-fin-eib"

register_resource(
    router, body_code="eib", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the EIB Group press feed (which also covers the European Investment Fund) plus the detail pages.",
    extra="Press releases from the EIB and the European Investment Fund (EIF), part of the EIB Group.",
)
register_resource(
    router, body_code="eib", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the EIB publications and research catalogue.",
    extra="Reports, studies, annual reports and economics research from the EIB Group.",
)
register_resource(
    router, body_code="eib", item_type="event", slug="events", noun="events",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the EIB events listing.",
    extra="Board meetings, conferences and other EIB Group events, with their dates.",
)
