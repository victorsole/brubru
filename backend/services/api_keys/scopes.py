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
        description="Council documents.",
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

    # --- API v2: "Brubru Proprietary Databases" domain --------------------
    (re.compile(r"^/api/v2/proprietary/guides(/|$)"),           "read:knowledge"),
    (re.compile(r"^/api/v2/proprietary/catalan(/|$)"),          "read:laws"),
    (re.compile(r"^/api/v2/proprietary/canon(/|$)"),            "read:knowledge"),

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
    (re.compile(r"^/api/v1/council-documents(/|$)"),            "read:council"),

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
