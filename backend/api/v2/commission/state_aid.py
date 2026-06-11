"""European Commission database — State aid cases.
/api/v2/commission/state-aid.

Backed by economy_items (body_code 'commission', item_type 'state_aid_case').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="state_aid_case",
    slug="state-aid", noun="State aid cases",
    body_name="the State aid case register (DG COMP)", acronym="DG COMP",
    tag="v2-commission",
    source="the EU competition case database, State aid cases (the full set, by member state).",
    extra="The Commission's State aid cases (SA.*): the case number, title, case type, member State, "
          "lead Directorate-General, economic sector, aid category and last decision date, linking to "
          "the case page. Covers all member states. Filter with q (e.g. a company, a sector such as "
          "'aviation', a member State or a case number such as 'SA.100000').",
)
