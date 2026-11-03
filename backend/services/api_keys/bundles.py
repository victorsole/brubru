"""API bundles: named groups of routes, so that a user can get what they want from over a thousand of them
(Victor, 3 Nov 2026). The one definition: the console, the docs, the key limit and the bundle audit all read it.

A route can sit in several bundles: an agency's news is both Agencies and News. Every /api/v2 route belongs to at
least one, and tests/test_api_bundles.py fails on a new route that does not, so nothing is left out of an audit.
These are not the subscription plan bundles in pricing.md: an API bundle changes what a key opens, not its price.

Each pattern is matched against both a route's template (/api/v2/news/{item_id}) and a called path (/api/v2/news/7).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Tuple

V2 = r"^/api/v2/"
END = r"(?:/|$)"
# The lists an EU body publishes sit one or two levels down: /ema/news, /eu-financial-institutions/eba/news.
UNDER_A_BODY = r"[a-z0-9-]+/(?:[a-z0-9-]+/)?"

# Every folder of one EU agency, joint undertaking, financial institution, court or advisory body. Written out, so that
# a new folder is a decision (the guard test asks for it) and not silently filed as an agency.
AGENCY_FOLDERS = (
    "acer", "berec", "cbe", "cdt", "cedefop", "cepol", "cert-eu", "chips", "cinea", "cjeu", "clean-aviation",
    "clean-hydrogen", "cor", "cpvo", "eacea", "eas", "easa", "eca", "ecb", "eccc", "ecdc", "echa", "eda", "edctp3",
    "edpb", "edps", "eea", "eeas", "eesc", "efca", "efsa", "eige", "eismea", "eit", "ela", "ema", "emsa", "enisa",
    "epso", "era", "ercea", "esdc", "esm", "etf", "eu-financial-institutions", "eu-lisa", "eu-osha", "euaa", "euda",
    "euipo", "euiss", "euratom", "eurofound", "eurohpc", "eurojust", "europes-rail", "europol", "euspa", "f4e", "fra",
    "frontex", "hadea", "ihi", "ombudsman", "rea", "satcen", "sesar", "sns",
)

# Routes that are not data and so sit in no bundle: the spec and its page, the lists of prices and bundles, and the
# tool that fetches any page live.
NOT_IN_A_BUNDLE = ("/api/v2/docs", "/api/v2/openapi.json", "/api/v2/pricing", "/api/v2/bundles", "/api/v2/extract")


@dataclass(frozen=True)
class ApiBundle:
    id: str
    label: str
    description: str
    patterns: Tuple[re.Pattern, ...]


def _bundle(bundle_id: str, label: str, description: str, *patterns: str) -> ApiBundle:
    return ApiBundle(bundle_id, label, description, tuple(re.compile(V2 + p) for p in patterns))


API_BUNDLES: Tuple[ApiBundle, ...] = (
    _bundle(
        "official-journal", "Official Journal",
        "What the EU publishes each day: the acts of the Official Journal, by date or by reference.",
        rf"legislative/eur-lex/(?:oj|recent){END}",
    ),
    _bundle(
        "legislation", "Laws and the legislative process",
        "EU laws and the files behind them: procedures, amendments, votes, adopted texts, Council documents, "
        "delegated and implementing acts, court rulings.",
        r"legislative/(?!eur-lex/oj(?:/|$)|eur-lex/recent(?:/|$))",
        r"parliament/(?:amendments|plenary-|texts-|reports|resolution|opinions|ep-documents|votes|parliamentary-questions)",
        r"commission/(?:commission-register-documents|comitology|rsb-opinions|tris-notifications)",
        r"council/(?:council-documents|council-register|council-voting-results|council-treaties-agreements|council-configurations|council-preparatory-bodies)",
        r"predictions/", rf"advisory-opinions{END}", rf"{UNDER_A_BODY}(?:case-law|legal-acts|legal-framework){END}",
        r"european-council/", r"eurogroup/(?:eurogroup-documents|eurogroup-about|eurogroup-work-programme)",
    ),
    _bundle(
        "funding-procurement", "Funding and procurement",
        "Every call, tender and award, EU programmes and budgets, and who can partner.",
        rf"funding{END}", rf"programmes{END}", rf"{UNDER_A_BODY}(?:calls|tenders){END}", r"proprietary/tender-docs",
        r"commission/(?:cap-beneficiaries|research-projects)", r"eu-financial-institutions/eib",
    ),
    _bundle(
        "news-events", "News and events",
        "News, press releases and events from every EU institution and body, and what is on the calendar.",
        rf"(?:news|events|calendar|social){END}", rf"{UNDER_A_BODY}(?:news|events|press-releases){END}",
        r"commission/meetings", r"parliament/(?:committee-agendas|webstreams|emeeting)",
        r"council/(?:council-meetings|council-press-releases|council-oj-agendas)",
        r"european-council/euco-meetings", r"eurogroup/eurogroup-meetings",
    ),
    _bundle(
        "agencies-bodies", "Agencies and bodies",
        "Everything from the EU's agencies, financial institutions, courts and advisory bodies, folder by folder.",
        rf"(?:{'|'.join(AGENCY_FOLDERS)}){END}",
    ),
    _bundle(
        "people", "People and organisations",
        "Officials, MEPs and their assistants, Commissioners, expert groups, lobbyists and the organisations on the "
        "Transparency Register.",
        rf"who-is-who{END}", r"parliament/(?:meps|mep-assistants|mep-declarations|committees)",
        r"commission/(?:commissioners|expert-groups)", rf"transparency-register{END}", r"proprietary/brussels-lobbies",
        r"european-council/euco-members", r"eurogroup/eurogroup-members", r"social/accounts",
    ),
    _bundle(
        "consultations", "Public consultations",
        "Public consultations of the Commission and the agencies, and the feedback they receive.",
        rf"consultations{END}", rf"{UNDER_A_BODY}consultations{END}",
    ),
    _bundle(
        "enforcement-markets", "Enforcement and markets",
        "Infringements, competition, state aid, digital markets cases, sanctions, trade defence, tariffs, food alerts, "
        "product passports and geographical indications.",
        r"commission/(?:infringements|competition-cases|state-aid|dma-cases|financial-sanctions|trade-defence|taric-tariffs|tariff-rulings|access2markets|agridata|rasff)",
        r"council/sanctions-regimes", rf"geographical-indications{END}", rf"dpp{END}",
        r"proprietary/(?:textile-circularity|packaging-waste-regulation)",
    ),
    _bundle(
        "research-data", "Research and data",
        "Studies, publications and topic pages, Parliament's research service, open data and statistics, and Brubru's "
        "own guides and translations.",
        r"parliament/(?:eprs|supporting-analyses|committee-transcripts)", r"council/council-research-papers",
        rf"open-data{END}", rf"general-publications{END}", rf"{UNDER_A_BODY}(?:publications|topics|datasets){END}",
        r"proprietary/(?:canon|catalan|guides)", rf"(?:interoperable|eugovtech){END}",
    ),
)

_BY_ID = {b.id: b for b in API_BUNDLES}


def bundle_ids() -> List[str]:
    return [b.id for b in API_BUNDLES]


def get_bundle(bundle_id: str) -> ApiBundle | None:
    return _BY_ID.get(bundle_id)


def bundles_of(path: str) -> List[str]:
    """The bundles a route or a called path belongs to."""
    return [b.id for b in API_BUNDLES if any(p.search(path) for p in b.patterns)]


def path_in_bundles(path: str, wanted: Iterable[str]) -> bool:
    """True when the path sits in one of these bundles. An id that no longer exists opens nothing."""
    return any(p.search(path) for bundle_id in wanted if bundle_id in _BY_ID for p in _BY_ID[bundle_id].patterns)
