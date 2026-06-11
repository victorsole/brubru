"""European Parliament database — MEP declarations of financial interests.
/api/v2/parliament/mep-declarations.

Backed by economy_items (body_code 'parliament', item_type 'mep_declaration').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="parliament", item_type="mep_declaration",
    slug="mep-declarations", noun="MEP declarations of financial interests",
    body_name="the European Parliament", acronym="the EP",
    tag="v2-parliament",
    source="the EP Open Data Portal (current Members) plus the per-MEP declarations pages.",
    extra="One entry per current Member of the European Parliament with a direct link to that MEP's "
          "declaration of financial (private) interests for the current term, plus the MEP's name and "
          "country. Filter with q (e.g. an MEP name or a country code such as 'DEU').",
)
