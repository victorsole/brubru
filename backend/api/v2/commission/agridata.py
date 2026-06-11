"""European Commission database — DG AGRI Agri-food data portal catalogue.
/api/v2/commission/agridata.

Backed by economy_items (body_code 'commission', item_type 'agri_data_series').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="agri_data_series",
    slug="agridata", noun="agri-food data series",
    body_name="the DG AGRI Agri-food data portal", acronym="DG AGRI",
    tag="v2-commission",
    source="the DG AGRI Agri-food data portal REST API (the full series catalogue, ~19 sectors).",
    extra="A catalogue of the EU agricultural market-data series — prices, production, trade and "
          "CMEF/PMEF indicators across beef, pigmeat, poultry, dairy, cereals, rice, oilseeds, sugar, "
          "olive oil, wine, fruit & vegetables, fertiliser, organic and TAXUD customs data. Each result "
          "gives the series title, sector, the filter parameters it accepts and a ready-to-run link to "
          "the live agri-food API that returns the actual figures. Filter with q (e.g. a sector or "
          "'prices', 'production', 'trade').",
)
