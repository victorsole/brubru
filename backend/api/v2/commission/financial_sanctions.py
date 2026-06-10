"""European Commission database — EU Consolidated Financial Sanctions List.
/api/v2/commission/financial-sanctions (DG FISMA / FPI).

Backed by economy_items (body_code 'commission', item_type 'financial_sanction')
via the shared register_resource helper, same contract as the rest of v2.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="financial_sanction",
    slug="financial-sanctions", noun="financial sanctions",
    body_name="the EU Consolidated Financial Sanctions List", acronym="the EU",
    tag="v2-commission",
    source="the EU Consolidated Financial Sanctions List (DG FISMA / FPI), the public FSD full-list export.",
    extra="Every person, entity and group subject to EU financial sanctions — name and aliases, "
          "subject type, sanctions programme, the legal act, citizenship, date/place of birth, "
          "identification documents and EU reference number. Filter with q (e.g. a name, country or programme).",
)
