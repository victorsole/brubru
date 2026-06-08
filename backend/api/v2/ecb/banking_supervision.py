"""ECB Banking Supervision (SSM) — /api/v2/ecb/banking-supervision/{news,publications,events}."""
from __future__ import annotations

from fastapi import APIRouter

from ._common import register_resource

router = APIRouter(prefix="/banking-supervision")

_BODY = "ECB Banking Supervision"
_ACRO = "the SSM"
_TAG = "v2-ecb-banking-supervision"

register_resource(
    router, body_code="ecb_ssm", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="SSM press & speeches RSS feeds plus the server-rendered detail pages.",
    extra="Press releases, speeches, interviews, blog posts and supervisory newsletters.",
)
register_resource(
    router, body_code="ecb_ssm", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the SSM publications listing (headless-rendered) with PDF/HTML detail.",
    extra="SREP outcomes, supervisory reports, thematic reviews and good-practice guides.",
)
register_resource(
    router, body_code="ecb_ssm", item_type="event", slug="events", noun="events",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the SSM conferences programme (headless-rendered).",
    extra="Supervision conferences, fora and research events, with their dates.",
)
