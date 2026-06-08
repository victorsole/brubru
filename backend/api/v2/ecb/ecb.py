"""ECB proper — /api/v2/ecb/{news,publications,events,legal-acts}."""
from __future__ import annotations

from fastapi import APIRouter

from ._common import register_resource

router = APIRouter()

_BODY = "European Central Bank"
_ACRO = "the ECB"
_TAG = "v2-ecb"

register_resource(
    router, body_code="ecb", item_type="news", slug="news", noun="news items",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="ECB press & blog RSS feeds plus the server-rendered detail pages.",
    extra="Covers press releases, speeches, interviews and The ECB Blog.",
)
register_resource(
    router, body_code="ecb", item_type="publication", slug="publications", noun="publications",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="ECB publication RSS feeds (working papers, statistical releases) with PDF/HTML detail.",
    extra="Working papers and statistical releases; bodies are extracted from the source PDFs.",
)
register_resource(
    router, body_code="ecb", item_type="event", slug="events", noun="events",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the ECB conferences programme (headless-rendered, since the list is loaded client-side).",
    extra="Conferences, seminars and fora, with their dates.",
)
register_resource(
    router, body_code="ecb", item_type="legal", slug="legal-acts", noun="legal acts",
    body_name=_BODY, acronym=_ACRO, tag=_TAG,
    source="the EU Publications Office (Cellar SPARQL), with ECB as author. CELEX is taken verbatim, never derived.",
    extra="ECB regulations, decisions, guidelines and opinions, each linking to its EUR-Lex record.",
)
