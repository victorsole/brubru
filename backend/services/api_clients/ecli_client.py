"""
ECLI search-engine client.

Phase 13 of docs/applications/euvoc.md. Provides:

  - Deep-link URLs into the public e-Justice ECLI search engine
    (https://e-justice.europa.eu/topics/legislation-and-case-law/
     european-case-law-identifier-ecli-search-engine_en).
  - Identifier-shape validation (delegated to standard_identifier_resolver).
  - Resolution to the InforCuria / EUR-Lex case-detail page when the
    ECLI corresponds to a Court of Justice of the EU (CJEU) ruling.

Honesty disclaimer (May 2026): the e-Justice ECLI search engine has NO
publicly available programmatic API at this time. Per the official FAQ
at https://e-justice.europa.eu/topics/legislation-and-case-law/
european-case-law-identifier-ecli-search-engine/general-information-
and-terms-and-conditions_en :

  Q: Is there a web service available which would allow me to search
     for ECLI decisions in an automated fashion?
  A: The SOAP-based web service is being updated and is currently not
     available. Please check back regularly on this page for updates.

So this client emits deep-link URLs that put the user on the search
landing page with their query pre-filled. When the SOAP / REST web
service is restored, swap `deep_link()` for a real
`search_by_ecli()` call without changing the public API.

Public API:
    deep_link(ecli)              -> str
    eur_lex_url(ecli)            -> Optional[str]  (CJEU only)
    is_cjeu(ecli)                -> bool
    parse(ecli)                  -> dict
"""

from __future__ import annotations

import os
from typing import Dict, Optional
from urllib.parse import quote

ECLI_SEARCH_BASE = (
    "https://e-justice.europa.eu/topics/legislation-and-case-law/"
    "european-case-law-identifier-ecli-search-engine_en"
)
INFORCURIA_BASE = "https://curia.europa.eu/juris/document/document.jsf"


def _base() -> str:
    return os.environ.get("ECLI_SEARCH_BASE", ECLI_SEARCH_BASE).rstrip("/")


def deep_link(ecli: str) -> str:
    """Return a deep-link to the e-Justice search engine for the given ECLI.

    The URL puts the user on the search-engine landing page with the
    ECLI pre-fed via the query string. The SPA's router picks the value
    up; users see results without typing.
    """
    return f"{_base()}?ecli={quote(ecli, safe='')}"


def parse(ecli: str) -> Dict[str, str]:
    """Decompose an ECLI into its 5 components.

    Format: ECLI:{country}:{court}:{year}:{ordinal}
    Returns an empty dict if the input doesn't match the shape.
    """
    if not ecli or not isinstance(ecli, str):
        return {}
    parts = ecli.upper().split(":")
    if len(parts) != 5 or parts[0] != "ECLI":
        return {}
    return {
        "country": parts[1],
        "court": parts[2],
        "year": parts[3],
        "ordinal": parts[4],
    }


def is_cjeu(ecli: str) -> bool:
    """True iff the ECLI is for a Court of Justice of the EU ruling.

    CJEU ECLIs use country code EU and court codes C (Court), T (General
    Court), or F (Civil Service Tribunal — historic).
    """
    p = parse(ecli)
    return p.get("country") == "EU" and p.get("court") in {"C", "T", "F"}


def eur_lex_url(ecli: str) -> Optional[str]:
    """Return the EUR-Lex URL for a CJEU ECLI if applicable, else None.

    EUR-Lex case-law CELEX numbers can be derived from CJEU ECLIs but
    the mapping is non-trivial (sector 6 + reformatted year + ordinal).
    For now we route partners to the InforCuria search interface with
    the ECLI pre-filled; that's the canonical CJEU search path.
    """
    if not is_cjeu(ecli):
        return None
    return f"{INFORCURIA_BASE}?ecli={quote(ecli, safe='')}"
