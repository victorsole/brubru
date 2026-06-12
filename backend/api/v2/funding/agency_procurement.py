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

# --- Cedefop -------------------------------------------------------------- #
register_resource(
    router, body_code="cedefop", item_type="tender", slug="cedefop-tenders",
    noun="Cedefop calls for tender", body_name="Cedefop", acronym="Cedefop", tag="v2-funding",
    source="the Cedefop public-procurement listing.",
    extra="Cedefop's own public procurement: each call for tender with reference, status and "
          "closing date. Decentralised procurement (sub-threshold not in TED). Filter with q.",
)
register_resource(
    router, body_code="cedefop", item_type="eoi_call", slug="cedefop-calls",
    noun="Cedefop calls for expression of interest", body_name="Cedefop", acronym="Cedefop",
    tag="v2-funding",
    source="the Cedefop public-procurement listing (expression-of-interest entries).",
    extra="Cedefop calls for expression of interest (e.g. lists of remunerated experts), with "
          "reference and closing date. Filter with q.",
)

# --- EMA — European Medicines Agency -------------------------------------- #
register_resource(
    router, body_code="ema", item_type="tender", slug="ema-tenders",
    noun="EMA calls for tender", body_name="the European Medicines Agency", acronym="EMA",
    tag="v2-funding",
    source="the EMA procurement & grants listing.",
    extra="The European Medicines Agency's own open procurement: each call for tender with "
          "reference and deadline. Filter with q (e.g. a reference or topic).",
)

# --- EFSA — European Food Safety Authority -------------------------------- #
register_resource(
    router, body_code="efsa", item_type="tender", slug="efsa-tenders",
    noun="EFSA calls for tender", body_name="the European Food Safety Authority", acronym="EFSA",
    tag="v2-funding",
    source="the EFSA procurement calls listing.",
    extra="The European Food Safety Authority's own calls for tender, each with its publication "
          "and closing dates. Filter with q (e.g. a scientific topic).",
)

# --- Eurojust ------------------------------------------------------------- #
register_resource(
    router, body_code="eurojust", item_type="tender", slug="eurojust-tenders",
    noun="Eurojust calls for tender", body_name="Eurojust", acronym="Eurojust", tag="v2-funding",
    source="the Eurojust procurement pages (ongoing calls for tender + low/middle-value contracts).",
    extra="Eurojust's own procurement, including the low- and middle-value contracts that are "
          "below the EU threshold and never appear in TED. Each with reference, status and closing "
          "date. Filter with q (e.g. a reference or a topic such as 'security').",
)

# --- ETF — European Training Foundation ----------------------------------- #
register_resource(
    router, body_code="etf", item_type="tender", slug="etf-tenders",
    noun="ETF calls for tender", body_name="the European Training Foundation", acronym="ETF",
    tag="v2-funding",
    source="the ETF procurement listing.",
    extra="The European Training Foundation's own procurement (tenders and expression-of-interest "
          "calls), each with its closing date. Filter with q.",
)
