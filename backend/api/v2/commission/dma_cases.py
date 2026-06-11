"""European Commission database — Digital Markets Act cases.
/api/v2/commission/dma-cases.

Backed by economy_items (body_code 'commission', item_type 'dma_case').
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

register_resource(
    router, body_code="commission", item_type="dma_case",
    slug="dma-cases", noun="Digital Markets Act cases",
    body_name="the Digital Markets Act case register (DG COMP)", acronym="DG COMP",
    tag="v2-commission",
    source="the Digital Markets Act cases portal (the full DMA case set).",
    extra="The Commission's Digital Markets Act cases — gatekeeper designations, specification and "
          "non-compliance proceedings against the designated gatekeepers (Alphabet, Amazon, Apple, "
          "Booking, ByteDance, Meta, Microsoft): the case number, title, type and core platform "
          "service concerned, linking to the case page. Filter with q (e.g. 'Apple' or 'app stores').",
)
