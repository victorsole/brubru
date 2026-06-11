"""European Commission database — comitology committees register.
/api/v2/commission/comitology.

Backed by economy_items (body_code 'commission', item_type 'comitology_committee').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="comitology_committee",
    slug="comitology", noun="comitology committees",
    body_name="the Comitology register", acronym="the EC",
    tag="v2-commission",
    source="the EU Comitology register (the full list of comitology committees).",
    extra="The Member-State committees that assist the Commission when it adopts implementing acts: "
          "the committee code, title, lead Directorate-General and whether it is active or abolished. "
          "~628 committees. Filter with q (e.g. a topic such as 'food' or a DG such as 'SANTE').",
)
