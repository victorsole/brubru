"""ESMA — European Securities and Markets Authority — /api/v2/eu-financial-institutions/esma/{news,publications}.

ESMA's site is a Drupal 10 mid-migration: the news + consultations listings are
server-rendered and dated, but the "key dates" agenda is a custom FullCalendar
widget with no clean data source, so ESMA exposes news + publications only.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter(prefix="/esma")

_BODY = "European Securities and Markets Authority"
_ACRO = "ESMA"
_TAG = "v2-eu-fin-esma"

register_resource(
    router, body_code="esma", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ESMA news listing (server-rendered, paginated) plus the detail pages.",
    extra="Press releases, consultations, Q&As and reports from ESMA's news stream.",
)
register_resource(
    router, body_code="esma", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ESMA consultations/library listing (server-rendered); bodies are extracted from the source PDFs.",
    extra="Consultation papers, reply forms and related library documents.",
)
