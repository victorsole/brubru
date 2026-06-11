"""European Commission database — RASFF food & feed safety notifications.
/api/v2/commission/rasff.

Backed by economy_items (body_code 'commission', item_type 'rasff_notification').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="rasff_notification",
    slug="rasff", noun="RASFF food and feed safety notifications",
    body_name="RASFF (Rapid Alert System for Food and Feed)", acronym="DG SANTE",
    tag="v2-commission",
    source="the RASFF Window consolidated notification search (the full notification set).",
    extra="Cross-border food, feed and food-contact-material safety notifications between EU/EEA "
          "members: the reference, subject, notifying country, product category and type, "
          "classification (alert, border rejection, information), risk decision and origin countries. "
          "~31,000 notifications. Filter with q (e.g. a product such as 'fish', a hazard such as "
          "'salmonella' or 'mercury', or a country).",
)
