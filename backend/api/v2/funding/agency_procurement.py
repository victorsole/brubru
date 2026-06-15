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

# --- EUAA — EU Agency for Asylum ------------------------------------------ #
register_resource(
    router, body_code="euaa", item_type="eoi_call", slug="euaa-calls",
    noun="EUAA calls for expression of interest",
    body_name="the European Union Agency for Asylum", acronym="EUAA", tag="v2-funding",
    source="the EUAA procurement page.",
    extra="EUAA calls for expression of interest (CEIs) such as the list of external remunerated "
          "experts in asylum-related fields, with reference and closing date. Headline open tenders "
          "are mirrored on the F&T Portal. Filter with q.",
)

# --- EUDA — EU Drugs Agency (formerly EMCDDA) ----------------------------- #
register_resource(
    router, body_code="euda", item_type="tender", slug="euda-tenders",
    noun="EUDA calls for tender",
    body_name="the European Union Drugs Agency", acronym="EUDA", tag="v2-funding",
    source="the EUDA procurement page (mirrors TED notices).",
    extra="EUDA open procedures — drug-policy development and evaluation, monitoring infrastructure, "
          "REITOX network support — each with its TED notice, reference and closing date. Filter "
          "with q.",
)

# --- ENISA — EU Agency for Cybersecurity ---------------------------------- #
register_resource(
    router, body_code="enisa", item_type="tender", slug="enisa-tenders",
    noun="ENISA calls for tender",
    body_name="the European Union Agency for Cybersecurity", acronym="ENISA", tag="v2-funding",
    source="the ENISA public-procurement page (mixed open + negotiated + CEI table).",
    extra="ENISA cybersecurity tenders — threat landscapes, exercises, certification, training — "
          "each with reference and deadline. EOIs are split into the calls endpoint. Filter with q.",
)
register_resource(
    router, body_code="enisa", item_type="eoi_call", slug="enisa-calls",
    noun="ENISA calls for expression of interest",
    body_name="the European Union Agency for Cybersecurity", acronym="ENISA", tag="v2-funding",
    source="the ENISA public-procurement page (CEI rows).",
    extra="ENISA calls for expression of interest (e.g. external-expert lists). Filter with q.",
)

# --- ERA — EU Agency for Railways ----------------------------------------- #
register_resource(
    router, body_code="era", item_type="tender", slug="era-tenders",
    noun="ERA calls for tender",
    body_name="the European Union Agency for Railways", acronym="ERA", tag="v2-funding",
    source="the ERA procurement listing (open status, listing-item cards).",
    extra="ERA's own procurement — railway-engineering studies, ERTMS support, IT, translation — "
          "each with reference (URL slug) and status. Filter with q.",
)

# --- ECDC — European Centre for Disease Prevention and Control ------------ #
register_resource(
    router, body_code="ecdc", item_type="tender", slug="ecdc-tenders",
    noun="ECDC calls for tender",
    body_name="the European Centre for Disease Prevention and Control", acronym="ECDC",
    tag="v2-funding",
    source="the ECDC procurement-and-grants listing (paginated ct-procurement cards).",
    extra="ECDC procurement — epidemiological studies, surveillance IT, modelling, training — each "
          "with reference and closing date. The agency mixes ex-ante publicity notices with open "
          "calls; the listing covers both. Filter with q.",
)

# --- ECHA — European Chemicals Agency ------------------------------------- #
register_resource(
    router, body_code="echa", item_type="tender", slug="echa-tenders",
    noun="ECHA calls for tender",
    body_name="the European Chemicals Agency", acronym="ECHA", tag="v2-funding",
    source="the ECHA Business Opportunities page (Playwright-rendered, WAF-protected).",
    extra="ECHA procurement — IUCLID and REACH-IT IT services, scientific data, translation, "
          "chemicals studies. Each call with reference and deadline. CEIs are split into the "
          "calls endpoint. Filter with q.",
)
register_resource(
    router, body_code="echa", item_type="eoi_call", slug="echa-calls",
    noun="ECHA calls for expression of interest",
    body_name="the European Chemicals Agency", acronym="ECHA", tag="v2-funding",
    source="the ECHA Business Opportunities page (CEI rows).",
    extra="ECHA calls for expression of interest (e.g. external-expert lists). Filter with q.",
)

# --- EIGE — European Institute for Gender Equality ------------------------ #
register_resource(
    router, body_code="eige", item_type="tender", slug="eige-tenders",
    noun="EIGE calls for tender",
    body_name="the European Institute for Gender Equality", acronym="EIGE", tag="v2-funding",
    source="the EIGE procurement page.",
    extra="EIGE's own procurement — gender-equality research, indicators, communications. The "
          "listing is often empty between procurement waves; the endpoint returns [] cleanly when "
          "EIGE has no ongoing procedures. Filter with q.",
)

# --- FRA — EU Agency for Fundamental Rights ------------------------------- #
register_resource(
    router, body_code="fra", item_type="tender", slug="fra-tenders",
    noun="FRA calls for tender",
    body_name="the European Union Agency for Fundamental Rights", acronym="FRA",
    tag="v2-funding",
    source="the FRA Ongoing Procedures page (Playwright-rendered, Anubis-protected).",
    extra="FRA procurement — fundamental-rights research, multi-country surveys, FRANET country "
          "correspondent contracts. Headline FRANET appointments run on a multi-year cycle. "
          "Listing returns [] cleanly when no procedures are open. Filter with q.",
)

# --- EEA — European Environment Agency (F&T-only) ------------------------- #
register_resource(
    router, body_code="eea", item_type="tender", slug="eea-tenders",
    noun="EEA calls for tender",
    body_name="the European Environment Agency", acronym="EEA", tag="v2-funding",
    source="the EEA procurement-and-grants page (informational; opportunities live on the F&T Portal).",
    extra="EEA publishes its open calls on the EU F&T Portal rather than on its own site. This "
          "endpoint returns an empty list and is wired so the agency is discoverable; EEA "
          "opportunities surface via the F&T Portal ingest (ft-calls-for-tenders / -proposals).",
)

# --- EU-OSHA — European Agency for Safety and Health at Work -------------- #
register_resource(
    router, body_code="eu_osha", item_type="tender", slug="eu-osha-tenders",
    noun="EU-OSHA calls for tender",
    body_name="the European Agency for Safety and Health at Work", acronym="EU-OSHA",
    tag="v2-funding",
    source="the EU-OSHA procurement archive (calls_archive/<year>, Drupal views-row).",
    extra="EU-OSHA procurement — ESENER survey field-work, sectoral occupational-safety studies, "
          "Healthy Workplaces campaign communications, IT, translation. Each call with reference "
          "and deadline. Filter with q.",
)
register_resource(
    router, body_code="eu_osha", item_type="eoi_call", slug="eu-osha-calls",
    noun="EU-OSHA calls for expression of interest",
    body_name="the European Agency for Safety and Health at Work", acronym="EU-OSHA",
    tag="v2-funding",
    source="the EU-OSHA calls-for-expression-of-interest listing.",
    extra="EU-OSHA calls for expression of interest (occupational-safety expert pools). Filter with q.",
)

# --- EIB — European Investment Bank --------------------------------------- #
register_resource(
    router, body_code="eib", item_type="tender", slug="eib-tenders",
    noun="EIB calls for tender",
    body_name="the European Investment Bank", acronym="EIB", tag="v2-funding",
    source="the TED public API v3 (buyer-name=European Investment Bank).",
    extra="EIB corporate procurement — financial advisory, IT, premises, "
          "consultancy — pulled from TED rather than EIB's own site (EIB "
          "publishes nothing on its site; everything is in TED). Open "
          "calls by default; each notice carries reference, procedure type "
          "and submission deadline. The first multilateral development bank "
          "wired into the Tenderator. Filter with q.",
)

# --- Eurofound — Foundation for Living and Working Conditions ------------- #
register_resource(
    router, body_code="eurofound", item_type="tender", slug="eurofound-tenders",
    noun="Eurofound calls for tender",
    body_name="the European Foundation for the Improvement of Living and Working Conditions",
    acronym="Eurofound", tag="v2-funding",
    source="the Eurofound procurement sub-pages (above-/below-€140k, Playwright-rendered).",
    extra="Eurofound procurement — large-scale European Working Conditions Survey (EWCS) field-work, "
          "industrial-relations correspondents network, secondary analyses, IT, translation. Filter "
          "with q.",
)
register_resource(
    router, body_code="eurofound", item_type="eoi_call", slug="eurofound-calls",
    noun="Eurofound calls for expression of interest",
    body_name="the European Foundation for the Improvement of Living and Working Conditions",
    acronym="Eurofound", tag="v2-funding",
    source="the Eurofound expression-of-interest listing (Playwright-rendered).",
    extra="Eurofound calls for expression of interest (correspondent networks, expert pools). Filter with q.",
)
