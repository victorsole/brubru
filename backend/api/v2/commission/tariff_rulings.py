"""European Commission database — EBTI binding tariff-classification rulings.
/api/v2/commission/tariff-rulings.

Backed by economy_items (body_code 'commission', item_type 'tariff_ruling').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="tariff_ruling",
    slug="tariff-rulings", noun="binding tariff rulings",
    body_name="EBTI (European Binding Tariff Information)", acronym="the EC",
    tag="v2-commission",
    source="EBTI — the European Binding Tariff Information bulk extract (DDS2), most recent two years.",
    extra="Binding customs-classification rulings issued by Member State customs authorities — the "
          "goods description, assigned CN/TARIC nomenclature code, issuing country, validity dates, "
          "status, classification justification and English keywords. Filter with q (e.g. a product, "
          "keyword or nomenclature code).",
)
