"""Council of the EU database — EU sanctions (restrictive measures) regimes.
/api/v2/council/sanctions-regimes.

Backed by economy_items (body_code 'council', item_type 'sanctions_regime').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="council", item_type="sanctions_regime",
    slug="sanctions-regimes", noun="EU sanctions regimes",
    body_name="the Council of the EU", acronym="the Council",
    tag="v2-council",
    source="the EU Sanctions Map — every EU restrictive-measures regime the Council has "
           "decided, with its legal basis, the measures imposed, the target country or theme "
           "and explanatory notes.",
    extra="One entry per sanctions regime: the official specification, target country/theme, "
          "the measure types imposed (asset freeze, arms embargo, travel ban, sector bans, etc.), "
          "explanatory notes, and the underlying Council Decisions and Regulations with their "
          "EUR-Lex links. Filter with q (e.g. a country such as Russia or Belarus, or a measure type).",
)
