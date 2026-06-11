"""European Commission database — Register of Commission Expert Groups.
/api/v2/commission/expert-groups.

Backed by economy_items (body_code 'commission', item_type 'expert_group').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="expert_group",
    slug="expert-groups", noun="expert groups",
    body_name="the Register of Commission Expert Groups", acronym="the EC",
    tag="v2-commission",
    source="the Register of Commission Expert Groups (all groups and sub-groups).",
    extra="The expert groups and sub-groups that advise the Commission in preparing legislation and "
          "policy: the group code, name, lead Directorate-General and type (formal, informal, "
          "sub-group). ~2,047 entries. Filter with q (e.g. a topic such as 'AI' or a DG name).",
)
