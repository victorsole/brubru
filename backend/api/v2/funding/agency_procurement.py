"""Decentralised EU agency procurement under the Funding & Tenders folder.

Every EU body runs its own tenders, grants and calls for expression of interest
on its own site — data that never reaches TED (below threshold) or the central
F&T Portal. Each is surfaced here as /api/v2/funding/{agency}-{tenders|grants|calls},
all grouped in the "Funding & Tenders" folder (tag v2-funding), backed by
economy_items (body_code = the agency, item_type = tender|grant|eoi_call).

One register_resource per agency-resource; add agencies incrementally.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..economy_endpoints import register_resource

router = APIRouter()

# --- EFCA — European Fisheries Control Agency ----------------------------- #
register_resource(
    router, body_code="efca", item_type="tender", slug="efca-tenders",
    noun="EFCA calls for tender", body_name="the European Fisheries Control Agency",
    acronym="EFCA", tag="v2-funding",
    source="the EFCA public-procurement pages (open calls for tender + negotiated procedures).",
    extra="The European Fisheries Control Agency's own public procurement: each call for tender "
          "with its reference number, status and deadline, linking to the tender page. Decentralised "
          "procurement that does not appear in TED below threshold. Filter with q (e.g. a reference "
          "or a topic such as 'vessel').",
)
register_resource(
    router, body_code="efca", item_type="eoi_call", slug="efca-calls",
    noun="EFCA calls for expression of interest", body_name="the European Fisheries Control Agency",
    acronym="EFCA", tag="v2-funding",
    source="the EFCA calls for expression of interest.",
    extra="EFCA calls for expression of interest (experts, service providers), with reference and "
          "deadline. Filter with q.",
)
