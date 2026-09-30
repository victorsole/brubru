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
    source="EFCA's procurement table (every procedure since 2015) and each procedure's own page.",
    extra="EFCA procurement, the whole table from 2015 (open and negotiated procedures). Each item "
          "carries `tender_reference`, `status` (EFCA's own Open/Closed, open only while the deadline "
          "is ahead) and `deadline`; `document_date` is the publication date of the linked Funding & "
          "Tenders notice, null where there is none. Calls for interest are at /efca-calls. Filter with q.",
    procurement=True,
)
register_resource(
    router, body_code="efca", item_type="eoi_call", slug="efca-calls",
    noun="EFCA calls for expression of interest", body_name="the European Fisheries Control Agency",
    acronym="EFCA", tag="v2-funding",
    source="EFCA's calls-for-expression-of-interest table and each call's own page.",
    extra="EFCA calls for expression of interest (experts, service providers). Each item carries "
          "`tender_reference`, `status` (open while the deadline is ahead) and `deadline`; "
          "`document_date` is the publication date of the linked Funding & Tenders notice. Filter with q.",
    procurement=True,
)

# --- Cedefop -------------------------------------------------------------- #
register_resource(
    router, body_code="cedefop", item_type="tender", slug="cedefop-tenders",
    noun="Cedefop calls for tender", body_name="Cedefop", acronym="Cedefop", tag="v2-funding",
    source="every page of the Cedefop public-procurement listing and each procedure's own page.",
    extra="Cedefop's own public procurement, the whole archive (published from 2006; calls for tenders and "
          "calls for proposals). Each item carries `tender_reference`, `status` "
          "(open | closed; open only while the deadline is ahead) and `deadline` (the extended "
          "closing date when Cedefop extended it); `document_date` is the Official Publication "
          "Date. The detail body holds the description, the key dates, the TED and Funding & "
          "Tenders links and the list of the procedure's files; `/{item_id}/documents` serves "
          "those files with their extracted text. Filter with q.",
    procurement=True, documents=True,
)
register_resource(
    router, body_code="cedefop", item_type="eoi_call", slug="cedefop-calls",
    noun="Cedefop calls for expression of interest", body_name="Cedefop", acronym="Cedefop",
    tag="v2-funding",
    source="every page of the Cedefop public-procurement listing (expression-of-interest procedures).",
    extra="Cedefop calls for expression of interest (e.g. lists of remunerated experts), the whole "
          "archive. Each item carries `tender_reference`, `status` and `deadline`; "
          "`document_date` is the Official Publication Date. The detail body lists the call's "
          "files; `/{item_id}/documents` serves them with their extracted text. Filter with q.",
    procurement=True, documents=True,
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
    source="the EU Funding & Tenders portal (EFSA's notices, by its buyer id) and EFSA's archive of "
           "procedures below EUR 140k.",
    extra="EFSA procurement, the whole archive from 2015: every EFSA notice on the Funding & Tenders "
          "portal (calls for tender, prior information and ex-ante notices), plus EFSA's closed "
          "procedures below EUR 140k that only its own site keeps; the kind stated in the body. Each "
          "item carries `tender_reference` (the portal notice id, or EFSA's NP reference), `status` "
          "(as on the portal; a prior notice is closed once its call is out) and `deadline`; "
          "`document_date` is the publication date (null for the archive procedures). Filter with q.",
    procurement=True,
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
    source="every page of the ECDC procurement-and-grants listing and each procedure's own page.",
    extra="ECDC procurement (epidemiological studies, surveillance IT, modelling, training), the "
          "whole archive from 2015: ex-ante publicity notices, calls for tender and calls for "
          "proposal, the kind stated in the body. Each item carries `tender_reference`, `status` "
          "(open while the deadline is ahead, else closed; ECDC publishes no status) and "
          "`deadline`; `document_date` is the page's publication date. The detail body holds "
          "the description and, for calls for tender, the Funding & Tenders link. Filter with q.",
    procurement=True,
)

# --- ECHA — European Chemicals Agency ------------------------------------- #
register_resource(
    router, body_code="echa", item_type="tender", slug="echa-tenders",
    noun="ECHA calls for tender",
    body_name="the European Chemicals Agency", acronym="ECHA", tag="v2-funding",
    source="ECHA's current and closed business-opportunity pages and each procedure's own page.",
    extra="ECHA procurement (IUCLID and REACH-IT IT services, scientific data, translation, "
          "chemicals studies), the whole archive from 2009: open, restricted and negotiated "
          "procedures, market consultations, auctions and contract advertisements, the "
          "procedure type stated in the body. Each item carries `tender_reference`, `status` "
          "(open only while on ECHA's current page with the deadline ahead) and `deadline`; "
          "`document_date` is the publication date of the linked Funding & Tenders notice, "
          "null where there is none (ECHA publishes no date itself). Calls for interest are "
          "at /echa-calls. Filter with q.",
    procurement=True,
)
register_resource(
    router, body_code="echa", item_type="eoi_call", slug="echa-calls",
    noun="ECHA calls for expression of interest",
    body_name="the European Chemicals Agency", acronym="ECHA", tag="v2-funding",
    source="ECHA's current and closed business-opportunity pages (calls for interest).",
    extra="ECHA calls for expression of interest (e.g. lists of external experts), the whole "
          "archive. Each item carries `tender_reference`, `status` and `deadline`; "
          "`document_date` is the linked Funding & Tenders notice's publication date, null "
          "where there is none. Filter with q.",
    procurement=True,
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
    source="the EU Funding & Tenders portal (EEA's notices, by its buyer id) and EEA's own "
           "procurement-and-grants pages (its calls for interest).",
    extra="EEA procurement, the whole archive from 2015: every EEA notice on the Funding & "
          "Tenders portal (calls for tender and ex-ante notices), plus EEA's own calls for "
          "expression of interest (remunerated experts, Topic Centres), the kind stated in the "
          "body. Each item carries `tender_reference` (the portal notice id; none for EEA's own "
          "calls), `status` (open, forthcoming or closed, as on the portal) and `deadline`; "
          "`document_date` is the publication date. Filter with q.",
    procurement=True,
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
