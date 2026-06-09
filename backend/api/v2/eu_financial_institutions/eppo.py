"""EPPO — European Public Prosecutor's Office —
/api/v2/eu-financial-institutions/eppo/{news,publications}."""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter(prefix="/eppo")

_BODY = "European Public Prosecutor's Office"
_ACRO = "the EPPO"
_TAG = "v2-eu-fin-eppo"

register_resource(
    router, body_code="eppo", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the EPPO news listing plus the detail pages.",
    extra="Press releases on investigations, seizures and prosecutions from the European Public Prosecutor's Office.",
)
register_resource(
    router, body_code="eppo", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the EPPO documents register; bodies are extracted from the source PDFs.",
    extra="Decisions, appointments, declarations of interest and other EPPO documents.",
)
