"""
Scope catalogue + path-to-scope mapping for the Brubru Data Provider API.

Scope enforcement is added via path-pattern middleware (see
backend/api/v1/_scope_middleware.py) rather than per-route dependencies, because
the v1 surface already exposes 40+ routers and we don't want to touch every
one. New routers get covered automatically if their prefix is added to
PATH_TO_SCOPE below — otherwise they default to requiring `read:misc`, which is
NOT in any user-mintable scope set, so any new route falls into a "deny-by-default
unless catalogued" stance.

Wildcard:
    A key whose scopes list contains "*" is permitted on every authenticated
    endpoint (back-compat with admin-issued keys and the GovClipping key).

Free paths:
    PING / WHOAMI / META_ENUMS / OPENAPI / DOCS need a valid key but no scope.
    They are how a caller proves auth works and inspects response envelopes
    without committing to a scope set.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Scope:
    name: str
    label: str           # human-friendly UI label
    description: str     # tooltip / docs body
    default_on_self_serve: bool = True  # pre-checked in the mint UI


SCOPE_CATALOGUE: Tuple[Scope, ...] = (
    Scope(
        name="read:laws",
        label="EU laws and legal text",
        description="Laws, full Formex text, legal-text intelligence (recital-article map, defined terms, alias resolution).",
    ),
    Scope(
        name="read:procedures",
        label="Legislative procedures and predictions",
        description="OEIL procedure files, predictions, citation verification.",
    ),
    Scope(
        name="read:calendar",
        label="EU institutional calendar",
        description="Plenary, Council, Commission and EP committee calendar events; webstreams; meetings.",
    ),
    Scope(
        name="read:ep",
        label="European Parliament",
        description="MEPs, committees, amendments, reports, opinions, votes, press releases, parliamentary questions, texts adopted and submitted, resolutions.",
    ),
    Scope(
        name="read:commission",
        label="European Commission",
        description="Commissioners, consultations, infringements, funding opportunities, F&T calls and projects, TED tenders, DG-specialised datasets (TBT, GI, sanctions, ...).",
    ),
    Scope(
        name="read:council",
        label="Council of the EU",
        description="Council documents, configurations, meetings, voting results, public register, OJ agendas, preparatory bodies, press releases, research papers, treaties.",
    ),
    Scope(
        name="read:european_council",
        label="European Council",
        description="European Council conclusions, summit meetings, the Euro Summit, the Strategic Agenda 2024-2029, members, and institutional reference.",
    ),
    Scope(
        name="read:eurogroup",
        label="Eurogroup",
        description="Eurogroup meetings, document register, work programme, members, and institutional reference.",
    ),
    Scope(
        name="read:knowledge",
        label="Brubru knowledge layer",
        description="Brubru's curated knowledge guides and EPRS / JRC research publications.",
    ),
    Scope(
        name="read:publications",
        label="EU publications and vocabularies",
        description="Cross-institutional press releases and EU controlled vocabularies (NALs, ontologies).",
    ),
    Scope(
        name="read:economy",
        label="Economy & finance institutions",
        description="ECB, ECB Banking Supervision, the EU financial-supervision authorities (EBA/ESMA/EIOPA/ESRB/SRB/EIB/AMLA/EPPO) and the ESM: their news, publications, events and legal acts.",
    ),
    Scope(
        name="read:social",
        label="EU social media directory & posts",
        description="Mapped social accounts of EU institutions, agencies, MEPs, Commissioners and EU-affairs journalists, plus recent posts (Bluesky/Mastodon/YouTube/X).",
    ),
)

SCOPE_NAMES: Tuple[str, ...] = tuple(s.name for s in SCOPE_CATALOGUE)
WILDCARD = "*"


def all_self_serve_scopes() -> List[str]:
    """The scope set pre-checked in the mint UI (every read:* scope)."""
    return [s.name for s in SCOPE_CATALOGUE if s.default_on_self_serve]


def is_known_scope(name: str) -> bool:
    return name == WILDCARD or name in SCOPE_NAMES


# ---------------------------------------------------------------------------
# Free paths (auth required but no scope check)
# ---------------------------------------------------------------------------

# Matched against the full path including the /api/v1 prefix.
FREE_PATH_PATTERNS: Tuple[re.Pattern[str], ...] = (
    re.compile(r"^/api/v1/ping/?$"),
    re.compile(r"^/api/v1/whoami/?$"),
    re.compile(r"^/api/v1/meta/enums/?$"),
    re.compile(r"^/api/v1/openapi\.json/?$"),
    re.compile(r"^/api/v1/docs/?$"),
)


def is_free_path(path: str) -> bool:
    """True for endpoints that need a valid key but no scope and no billing."""
    return any(p.match(path) for p in FREE_PATH_PATTERNS)


# ---------------------------------------------------------------------------
# Path → scope mapping
# ---------------------------------------------------------------------------
# First match wins. Order matters: put more specific patterns above broader ones.
# Add entries here whenever a new v1 router prefix is introduced.

PATH_TO_SCOPE: Tuple[Tuple[re.Pattern[str], str], ...] = (
    # --- API v2: institution-based "Legislative data" domain --------------
    # Source-rooted scope mapping. Same scope vocabulary as v1.
    (re.compile(r"^/api/v2/legislative/eur-lex(/|$)"),          "read:laws"),
    (re.compile(r"^/api/v2/legislative/oeil(/|$)"),             "read:procedures"),
    (re.compile(r"^/api/v2/legislative/legislative-train(/|$)"), "read:procedures"),
    (re.compile(r"^/api/v2/legislative/eurovoc(/|$)"),          "read:publications"),
    (re.compile(r"^/api/v2/legislative/delegated-acts(/|$)"),   "read:commission"),
    (re.compile(r"^/api/v2/legislative/implementing-acts(/|$)"), "read:commission"),

    # --- API v2: institution-based "European Parliament" domain -----------
    # Same scope mapping as the v1 EP surface (read:ep, with the two v1
    # exceptions preserved: webstreams -> read:calendar, eprs -> read:knowledge).
    (re.compile(r"^/api/v2/parliament/meps(/|$)"),                    "read:ep"),
    (re.compile(r"^/api/v2/parliament/committees(/|$)"),             "read:ep"),
    (re.compile(r"^/api/v2/parliament/amendments(/|$)"),             "read:ep"),
    (re.compile(r"^/api/v2/parliament/ep-documents(/|$)"),           "read:ep"),
    (re.compile(r"^/api/v2/parliament/reports(/|$)"),                "read:ep"),
    (re.compile(r"^/api/v2/parliament/opinions(/|$)"),               "read:ep"),
    (re.compile(r"^/api/v2/parliament/votes(/|$)"),                  "read:ep"),
    (re.compile(r"^/api/v2/parliament/parliamentary-questions(/|$)"), "read:ep"),
    (re.compile(r"^/api/v2/parliament/texts-adopted(/|$)"),          "read:ep"),
    (re.compile(r"^/api/v2/parliament/texts-submitted(/|$)"),        "read:ep"),
    (re.compile(r"^/api/v2/parliament/resolutions(/|$)"),            "read:ep"),
    (re.compile(r"^/api/v2/parliament/webstreams(/|$)"),             "read:calendar"),
    (re.compile(r"^/api/v2/parliament/eprs(/|$)"),                   "read:knowledge"),
    (re.compile(r"^/api/v2/parliament/emeeting(/|$)"),               "read:ep"),
    (re.compile(r"^/api/v2/parliament/emeeting-documents(/|$)"),      "read:ep"),
    (re.compile(r"^/api/v2/parliament/committee-transcripts(/|$)"),   "read:ep"),
    (re.compile(r"^/api/v2/parliament/committee-agendas(/|$)"),       "read:ep"),

    # --- API v2: institution-based "European Commission" domain -----------
    # Same scope mapping as the v1 Commission surface (read:commission, with
    # the v1 exception preserved: meetings -> read:calendar).
    (re.compile(r"^/api/v2/commission/commissioners(/|$)"),                  "read:commission"),
    (re.compile(r"^/api/v2/commission/commission-register-documents(/|$)"),  "read:commission"),
    (re.compile(r"^/api/v2/commission/rsb-opinions(/|$)"),                   "read:commission"),
    (re.compile(r"^/api/v2/commission/infringements(/|$)"),                  "read:commission"),
    (re.compile(r"^/api/v2/commission/consultations(/|$)"),                  "read:commission"),
    (re.compile(r"^/api/v2/commission/tris-notifications(/|$)"),             "read:commission"),
    (re.compile(r"^/api/v2/commission/meetings(/|$)"),                       "read:calendar"),

    # --- API v2: institution-based "Council of the EU" domain -------------
    (re.compile(r"^/api/v2/council/council-documents(/|$)"),                 "read:council"),
    (re.compile(r"^/api/v2/council/council-configurations(/|$)"),            "read:council"),
    (re.compile(r"^/api/v2/council/council-meetings(/|$)"),                  "read:council"),
    (re.compile(r"^/api/v2/council/council-voting-results(/|$)"),            "read:council"),
    (re.compile(r"^/api/v2/council/council-register(/|$)"),                  "read:council"),
    (re.compile(r"^/api/v2/council/council-oj-agendas(/|$)"),                "read:council"),
    (re.compile(r"^/api/v2/council/council-preparatory-bodies(/|$)"),        "read:council"),
    (re.compile(r"^/api/v2/council/council-press-releases(/|$)"),            "read:council"),
    (re.compile(r"^/api/v2/council/council-research-papers(/|$)"),           "read:council"),
    (re.compile(r"^/api/v2/council/council-treaties-agreements(/|$)"),       "read:council"),

    # --- API v2: institution-based "European Council" domain --------------
    (re.compile(r"^/api/v2/european-council/euco-conclusions(/|$)"),         "read:european_council"),
    (re.compile(r"^/api/v2/european-council/euco-meetings(/|$)"),            "read:european_council"),
    (re.compile(r"^/api/v2/european-council/euco-euro-summit(/|$)"),         "read:european_council"),
    (re.compile(r"^/api/v2/european-council/euco-strategic-agenda(/|$)"),    "read:european_council"),
    (re.compile(r"^/api/v2/european-council/euco-members(/|$)"),             "read:european_council"),
    (re.compile(r"^/api/v2/european-council/euco-about(/|$)"),               "read:european_council"),

    # --- API v2: institution-based "Eurogroup" domain ---------------------
    (re.compile(r"^/api/v2/eurogroup/eurogroup-meetings(/|$)"),              "read:eurogroup"),
    (re.compile(r"^/api/v2/eurogroup/eurogroup-documents(/|$)"),             "read:eurogroup"),
    (re.compile(r"^/api/v2/eurogroup/eurogroup-work-programme(/|$)"),        "read:eurogroup"),
    (re.compile(r"^/api/v2/eurogroup/eurogroup-members(/|$)"),               "read:eurogroup"),
    (re.compile(r"^/api/v2/eurogroup/eurogroup-about(/|$)"),                 "read:eurogroup"),

    # --- API v2: "General Publications" domain (Publications Office) -------
    (re.compile(r"^/api/v2/general-publications(/|$)"),         "read:publications"),

    # --- API v2: "Who is Who" domain (EU interinstitutional directory) -----
    (re.compile(r"^/api/v2/who-is-who/departments(/|$)"),       "read:publications"),
    (re.compile(r"^/api/v2/who-is-who/officials(/|$)"),         "read:publications"),

    # --- API v2: "Open Data" domain (data.europa.eu / Publications Office) -
    (re.compile(r"^/api/v2/open-data/datasets(/|$)"),            "read:publications"),
    (re.compile(r"^/api/v2/open-data/high-value-datasets(/|$)"), "read:publications"),
    (re.compile(r"^/api/v2/open-data/catalogues(/|$)"),          "read:publications"),

    # --- API v2: "Funding & Tenders" domain (Commission-administered) ------
    (re.compile(r"^/api/v2/funding/funding-opportunities(/|$)"),  "read:commission"),
    (re.compile(r"^/api/v2/funding/ft-calls-for-proposals(/|$)"), "read:commission"),
    (re.compile(r"^/api/v2/funding/ft-calls-for-tenders(/|$)"),   "read:commission"),
    (re.compile(r"^/api/v2/funding/ft-funded-projects(/|$)"),     "read:commission"),
    (re.compile(r"^/api/v2/funding/tenders(/|$)"),                "read:commission"),

    # --- API v2: "Brubru Proprietary Databases" domain --------------------
    (re.compile(r"^/api/v2/proprietary/guides(/|$)"),           "read:knowledge"),
    (re.compile(r"^/api/v2/proprietary/catalan(/|$)"),          "read:laws"),
    (re.compile(r"^/api/v2/proprietary/canon(/|$)"),            "read:knowledge"),
    (re.compile(r"^/api/v2/proprietary/brussels-lobbies(/|$)"), "read:knowledge"),

    # Economy & Finance institutions (3 folders, one scope).
    (re.compile(r"^/api/v2/ecb(/|$)"),                          "read:economy"),
    (re.compile(r"^/api/v2/eu-financial-institutions(/|$)"),    "read:economy"),
    (re.compile(r"^/api/v2/esm(/|$)"),                          "read:economy"),
    # cross-body aggregators + input-first extract (else default to unreachable read:misc)
    (re.compile(r"^/api/v2/extract(/|$)"),                      "read:economy"),
    (re.compile(r"^/api/v2/events(/|$)"),                       "read:economy"),
    (re.compile(r"^/api/v2/news(/|$)"),                         "read:economy"),
    (re.compile(r"^/api/v2/programmes(/|$)"),                   "read:economy"),
    (re.compile(r"^/api/v2/consultations(/|$)"),               "read:economy"),
    (re.compile(r"^/api/v2/social(/|$)"),                       "read:social"),

    # read:laws
    (re.compile(r"^/api/v1/laws(/|$)"),                         "read:laws"),
    (re.compile(r"^/api/v1/legal-text(/|$)"),                   "read:laws"),
    (re.compile(r"^/api/v1/catalan-translations(/|$)"),         "read:laws"),
    (re.compile(r"^/api/v1/identify(/|$)"),                     "read:laws"),
    (re.compile(r"^/api/v1/discover/cellar(/|$)"),              "read:laws"),
    (re.compile(r"^/api/v1/discover/ecli(/|$)"),                "read:laws"),

    # read:procedures
    (re.compile(r"^/api/v1/procedures(/|$)"),                   "read:procedures"),
    (re.compile(r"^/api/v1/predictions(/|$)"),                  "read:procedures"),
    (re.compile(r"^/api/v1/citations(/|$)"),                    "read:procedures"),
    (re.compile(r"^/api/v1/verify-citation(/|$)"),              "read:procedures"),
    (re.compile(r"^/api/v1/discover/eurio(/|$)"),               "read:procedures"),

    # read:calendar
    (re.compile(r"^/api/v1/calendar(/|$)"),                     "read:calendar"),
    (re.compile(r"^/api/v1/webstreams(/|$)"),                   "read:calendar"),
    (re.compile(r"^/api/v1/meetings(/|$)"),                     "read:calendar"),

    # read:ep
    (re.compile(r"^/api/v1/meps(/|$)"),                         "read:ep"),
    (re.compile(r"^/api/v1/committees(/|$)"),                   "read:ep"),
    (re.compile(r"^/api/v1/committee-transcripts(/|$)"),        "read:ep"),
    (re.compile(r"^/api/v1/committee-agendas(/|$)"),            "read:ep"),
    (re.compile(r"^/api/v1/emeeting(/|$)"),                     "read:ep"),
    (re.compile(r"^/api/v1/emeeting-documents(/|$)"),           "read:ep"),
    (re.compile(r"^/api/v1/amendments(/|$)"),                   "read:ep"),
    (re.compile(r"^/api/v1/ep-documents(/|$)"),                 "read:ep"),
    (re.compile(r"^/api/v1/reports(/|$)"),                      "read:ep"),
    (re.compile(r"^/api/v1/opinions(/|$)"),                     "read:ep"),
    (re.compile(r"^/api/v1/votes(/|$)"),                        "read:ep"),
    (re.compile(r"^/api/v1/press-releases(/|$)"),               "read:ep"),
    (re.compile(r"^/api/v1/parliamentary-questions(/|$)"),      "read:ep"),
    (re.compile(r"^/api/v1/texts-adopted(/|$)"),                "read:ep"),
    (re.compile(r"^/api/v1/texts-submitted(/|$)"),              "read:ep"),
    (re.compile(r"^/api/v1/resolutions(/|$)"),                  "read:ep"),

    # read:commission
    (re.compile(r"^/api/v1/commissioners(/|$)"),                "read:commission"),
    (re.compile(r"^/api/v1/commission-register-documents(/|$)"), "read:commission"),
    (re.compile(r"^/api/v1/consultations(/|$)"),                "read:commission"),
    (re.compile(r"^/api/v1/infringements(/|$)"),                "read:commission"),
    (re.compile(r"^/api/v1/funding-opportunities(/|$)"),        "read:commission"),
    (re.compile(r"^/api/v1/ft-calls-for-proposals(/|$)"),       "read:commission"),
    (re.compile(r"^/api/v1/ft-calls-for-tenders(/|$)"),         "read:commission"),
    (re.compile(r"^/api/v1/ft-funded-projects(/|$)"),           "read:commission"),
    (re.compile(r"^/api/v1/tenders(/|$)"),                      "read:commission"),
    (re.compile(r"^/api/v1/officials(/|$)"),                    "read:commission"),
    (re.compile(r"^/api/v1/delegated-acts(/|$)"),               "read:commission"),
    (re.compile(r"^/api/v1/implementing-acts(/|$)"),            "read:commission"),
    (re.compile(r"^/api/v1/rsb-opinions(/|$)"),                 "read:commission"),
    (re.compile(r"^/api/v1/tris-notifications(/|$)"),           "read:commission"),
    (re.compile(r"^/api/v1/specialised(/|$)"),                  "read:commission"),

    # read:council
    (re.compile(r"^/api/v1/general-publications(/|$)"),         "read:publications"),
    (re.compile(r"^/api/v1/who-is-who/departments(/|$)"),       "read:publications"),
    (re.compile(r"^/api/v1/who-is-who/officials(/|$)"),         "read:publications"),
    (re.compile(r"^/api/v1/open-data/datasets(/|$)"),           "read:publications"),
    (re.compile(r"^/api/v1/open-data/high-value-datasets(/|$)"), "read:publications"),
    (re.compile(r"^/api/v1/open-data/catalogues(/|$)"),         "read:publications"),
    (re.compile(r"^/api/v1/council-documents(/|$)"),            "read:council"),
    (re.compile(r"^/api/v1/council-configurations(/|$)"),       "read:council"),
    (re.compile(r"^/api/v1/council-meetings(/|$)"),             "read:council"),
    (re.compile(r"^/api/v1/council-voting-results(/|$)"),       "read:council"),
    (re.compile(r"^/api/v1/council-register(/|$)"),             "read:council"),
    (re.compile(r"^/api/v1/council-oj-agendas(/|$)"),           "read:council"),
    (re.compile(r"^/api/v1/council-preparatory-bodies(/|$)"),   "read:council"),
    (re.compile(r"^/api/v1/council-press-releases(/|$)"),       "read:council"),
    (re.compile(r"^/api/v1/council-research-papers(/|$)"),      "read:council"),
    (re.compile(r"^/api/v1/council-treaties-agreements(/|$)"),  "read:council"),
    # European Council (v1)
    (re.compile(r"^/api/v1/euco-conclusions(/|$)"),             "read:european_council"),
    (re.compile(r"^/api/v1/euco-meetings(/|$)"),                "read:european_council"),
    (re.compile(r"^/api/v1/euco-euro-summit(/|$)"),             "read:european_council"),
    (re.compile(r"^/api/v1/euco-strategic-agenda(/|$)"),        "read:european_council"),
    (re.compile(r"^/api/v1/euco-members(/|$)"),                 "read:european_council"),
    (re.compile(r"^/api/v1/euco-about(/|$)"),                   "read:european_council"),
    # Eurogroup (v1)
    (re.compile(r"^/api/v1/eurogroup-meetings(/|$)"),           "read:eurogroup"),
    (re.compile(r"^/api/v1/eurogroup-documents(/|$)"),          "read:eurogroup"),
    (re.compile(r"^/api/v1/eurogroup-work-programme(/|$)"),     "read:eurogroup"),
    (re.compile(r"^/api/v1/eurogroup-members(/|$)"),            "read:eurogroup"),
    (re.compile(r"^/api/v1/eurogroup-about(/|$)"),              "read:eurogroup"),

    # read:knowledge
    (re.compile(r"^/api/v1/knowledge-guides(/|$)"),             "read:knowledge"),
    (re.compile(r"^/api/v1/eprs(/|$)"),                         "read:knowledge"),
    (re.compile(r"^/api/v1/research-publications(/|$)"),        "read:knowledge"),

    # read:publications
    (re.compile(r"^/api/v1/publications(/|$)"),                 "read:publications"),
    (re.compile(r"^/api/v1/vocabularies(/|$)"),                 "read:publications"),
)


def resolve_required_scope(path: str) -> Optional[str]:
    """Return the scope required to access `path`, or None for free paths.

    Free paths (ping/whoami/enums/openapi/docs) return None.
    Paths matching a PATH_TO_SCOPE entry return the entry's scope.
    Unmatched paths under /api/v1/* fall back to "read:misc" — a scope no user
    can hold — so they deny-by-default and surface as a config gap, not a leak.
    """
    if is_free_path(path):
        return None
    for pattern, scope in PATH_TO_SCOPE:
        if pattern.match(path):
            return scope
    if path.startswith(("/api/v1/", "/api/v2/")):
        return "read:misc"  # uncatalogued paid path; deny-by-default
    return None  # non-API paths are outside this module's concern


# ---------------------------------------------------------------------------
# Validation helpers (used by the mint endpoint)
# ---------------------------------------------------------------------------

def validate_scope_list(scopes: Iterable[str], *, allow_wildcard: bool = False) -> List[str]:
    """Normalise a user-supplied scope list.

    - Strips whitespace, deduplicates while preserving order.
    - Rejects unknown scopes with ValueError.
    - By default rejects "*" — only the admin path may mint wildcard keys.
    """
    out: List[str] = []
    seen: set[str] = set()
    for raw in scopes:
        s = (raw or "").strip()
        if not s or s in seen:
            continue
        if s == WILDCARD and not allow_wildcard:
            raise ValueError("wildcard scope is reserved for admin-minted keys")
        if not is_known_scope(s):
            raise ValueError(f"unknown scope: {s!r}")
        out.append(s)
        seen.add(s)
    if not out:
        raise ValueError("at least one scope is required")
    return out
