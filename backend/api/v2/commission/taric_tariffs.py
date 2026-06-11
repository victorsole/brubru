"""European Commission database — TARIC / Combined Nomenclature goods codes.
/api/v2/commission/taric-tariffs.

Backed by economy_items (body_code 'commission', item_type 'tariff_code').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="tariff_code",
    slug="taric-tariffs", noun="customs goods-classification codes",
    body_name="the Combined Nomenclature (CN), the EU customs tariff", acronym="the EC",
    tag="v2-commission",
    source="The EU Combined Nomenclature annual table (Eurostat / EU Vocabularies, SKOS), "
           "chapters down to 8-digit CN subheadings.",
    extra="The classification of goods used across the EU for customs duties and external-trade "
          "statistics: the CN code, its classification level (chapter, heading, HS subheading, CN "
          "subheading), the English description and the full descriptive definition. Each result links "
          "to the live TARIC measures lookup, where the applicable duty rates for that code are shown. "
          "Filter with q (e.g. a product such as 'footwear' or 'lithium', or a code such as '8703').",
)
