"""European Commission database — CORDIS EU research projects.
/api/v2/commission/research-projects.

Backed by economy_items (body_code 'commission', item_type 'research_project').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="research_project",
    slug="research-projects", noun="research projects",
    body_name="CORDIS (the EU research-projects service)", acronym="the EC",
    tag="v2-commission",
    source="CORDIS — the EU research-projects bulk dataset for Horizon Europe (2021-2027).",
    extra="EU-funded research projects under Horizon Europe — acronym, title, objective, EC "
          "contribution, total cost, funding scheme, topic, call, status, start/end dates, grant DOI "
          "and keywords, each linking to its CORDIS project page. Filter with q (e.g. an acronym, "
          "topic or keyword).",
)
