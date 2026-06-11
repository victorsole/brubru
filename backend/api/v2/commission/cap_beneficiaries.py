"""European Commission database — CAP beneficiaries national-portal directory.
/api/v2/commission/cap-beneficiaries.

Backed by economy_items (body_code 'commission', item_type 'cap_beneficiary_portal').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="cap_beneficiary_portal",
    slug="cap-beneficiaries", noun="CAP beneficiary portals",
    body_name="the CAP beneficiaries directory (DG AGRI)", acronym="DG AGRI",
    tag="v2-commission",
    source="the DG AGRI index of national CAP-beneficiary transparency portals (one per Member State).",
    extra="Under EU transparency rules the names of Common Agricultural Policy beneficiaries (EAGF "
          "direct payments and EAFRD rural-development support) are published by each Member State on "
          "its own national portal, not in a single EU dataset. This directory gives one entry per "
          "Member State with a direct link to the national portal where the actual beneficiary records "
          "can be searched. Filter with q (e.g. a country such as 'Spain' or 'Ireland').",
)
