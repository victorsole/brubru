"""European Commission database — DG TRADE trade-defence cases (TRON).
/api/v2/commission/trade-defence.

Backed by economy_items (body_code 'commission', item_type 'trade_defence_case').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="trade_defence_case",
    slug="trade-defence", noun="trade-defence cases",
    body_name="the EU trade-defence case database (DG TRADE / TRON)", acronym="DG TRADE",
    tag="v2-commission",
    source="the Commission's TRON investigations database (the full EU trade-defence case set).",
    extra="The EU's trade-defence cases — anti-dumping, anti-subsidy (countervailing) and safeguard "
          "investigations and the measures in force: the product, the proceeding type, the measure "
          "status (measures in force, expired, no measure), the countries concerned and the case "
          "reference (AD###/AS###), each linking to the case detail page. Filter with q (e.g. a product "
          "such as 'steel', a country such as 'China', or a reference such as 'AD734').",
)
