"""European Parliament database — accredited parliamentary assistants register.
/api/v2/parliament/mep-assistants.

Backed by economy_items (body_code 'parliament', item_type 'mep_assistant_register').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="parliament", item_type="mep_assistant_register",
    slug="mep-assistants", noun="MEP assistant registers",
    body_name="the European Parliament", acronym="the EP",
    tag="v2-parliament",
    source="every current MEP's assistants page (accredited and local parliamentary assistants).",
    extra="One entry per current Member of the European Parliament listing their accredited "
          "parliamentary assistants and local assistants, with the MEP's name and country, linking to "
          "the assistants page. Filter with q (e.g. an MEP name, an assistant name or a country code).",
)
