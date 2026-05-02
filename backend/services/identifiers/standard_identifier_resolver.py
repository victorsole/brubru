"""
Standard-identifier resolver.

Phase 13 of docs/applications/euvoc.md. Recognises every identifier
type the EU Publications Office uses (per OP Standards v4.0.0 §2) and
routes each to the right Brubru retrieval path.

Identifier types covered:
    - URI/IRI       (any http://publications.europa.eu/resource/...)
    - CELEX         (e.g. 32016R0679, 52026PC0028, 31995L0046)
    - ECLI          (ECLI:EU:C:2023:123 — European Case Law Identifier)
    - ELI URI       (http://publications.europa.eu/resource/eli/...)
    - ISBN          (978-92-78-41349-1)
    - ISSN          (1234-5678)
    - DOI           (10.2775/123456)
    - OJ ref        (JOL_2014_001_R_0001_01 / L_202401689)
    - Catalogue     (OA-AS-16-001-EN-N)
    - Authority URI (http://publications.europa.eu/resource/authority/...)
    - EuroVoc URI   (http://eurovoc.europa.eu/{id})

Public API:
    recognise(text)  -> Optional[IdentifierMatch]
    parse_all(text)  -> list[IdentifierMatch]   # find every identifier in a string
    canonical_url(match)   -> str               # canonical Brubru/EU URL
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class IdentifierKind(str, Enum):
    URI = "uri"
    AUTHORITY_URI = "authority_uri"
    EUROVOC_URI = "eurovoc_uri"
    ELI_URI = "eli_uri"
    CELEX = "celex"
    ECLI = "ecli"
    ISBN = "isbn"
    ISSN = "issn"
    DOI = "doi"
    OJ_REF = "oj_ref"
    CATALOGUE_NUMBER = "catalogue_number"


@dataclass
class IdentifierMatch:
    kind: IdentifierKind
    value: str
    canonical_url: Optional[str] = None
    brubru_url: Optional[str] = None  # the Brubru endpoint that serves this identifier
    parts: Optional[dict] = None      # parsed components (e.g. CELEX sector / year / serial)


# ----------------------------------------------------------------------
# Patterns (anchored variants for `recognise`, unanchored for `parse_all`)
# ----------------------------------------------------------------------

# CELEX: sector(1 digit) + year(4) + type-letter(1-2 alpha) + serial(1-5 digits) + optional R(NN)
# Examples: 32016R0679, 52026PC0028, 31995L0046, 32016R0679R(01)
_CELEX_INNER = r"\d[A-Z\d]?\d{4}[A-Z]{1,2}\d{1,5}(?:R\(\d+\))?"
_CELEX_RE = re.compile(rf"^{_CELEX_INNER}$")
_CELEX_SCAN = re.compile(rf"\b{_CELEX_INNER}\b")

# ECLI: ECLI:{country 2-letter}:{court}:{year 4}:{ordinal}
_ECLI_INNER = r"ECLI:[A-Z]{2}:[A-Z0-9]+:\d{4}:[A-Z0-9.]+"
_ECLI_RE = re.compile(rf"^{_ECLI_INNER}$", re.IGNORECASE)
_ECLI_SCAN = re.compile(rf"\b{_ECLI_INNER}\b", re.IGNORECASE)

# ISBN: 13-digit (modern) or 10-digit (legacy), with optional hyphens
_ISBN13_INNER = r"(?:97[89][- ]?)?(?:\d[- ]?){9}\d"
_ISBN_RE = re.compile(rf"^(?:ISBN[\s:-]+)?{_ISBN13_INNER}$", re.IGNORECASE)

# ISSN: 4 digits + hyphen + 4 digits / X
_ISSN_INNER = r"\d{4}-\d{3}[\dX]"
_ISSN_RE = re.compile(rf"^(?:ISSN[\s:-]+)?{_ISSN_INNER}$", re.IGNORECASE)
_ISSN_SCAN = re.compile(rf"(?:ISSN[\s:-]+)?\b{_ISSN_INNER}\b", re.IGNORECASE)

# DOI: 10.NNNN/anything (per RFC 3986-ish, no whitespace)
_DOI_INNER = r"10\.\d{4,9}/[^\s]+"
_DOI_RE = re.compile(rf"^(?:doi:)?{_DOI_INNER}$", re.IGNORECASE)
_DOI_SCAN = re.compile(rf"(?:doi:\s*)?\b{_DOI_INNER}\b", re.IGNORECASE)

# Catalogue number (OP scheme): {3 letters}-{2 letters}-{2 digits}-{3 digits}-{LANG}-{N}
_CATALOGUE_INNER = r"[A-Z]{2,3}-[A-Z]{2}-\d{2}-\d{3}-[A-Z]{2,3}-[A-Z]"
_CATALOGUE_RE = re.compile(rf"^{_CATALOGUE_INNER}$")
_CATALOGUE_SCAN = re.compile(rf"\b{_CATALOGUE_INNER}\b")

# OJ reference (e.g. JOL_2014_001_R_0001_01 / L_202401689)
_OJ_INNER = r"(?:JO[LC]_\d{4}_\d{3,4}_[A-Z]_\d{4}(?:_\d{2})?|L_\d{6,9}|C_\d{6,9}(?:_\d{2})?)"
_OJ_RE = re.compile(rf"^{_OJ_INNER}$")
_OJ_SCAN = re.compile(rf"\b{_OJ_INNER}\b")

# URIs
_AUTHORITY_URI_RE = re.compile(r"^http://publications\.europa\.eu/resource/authority/[A-Za-z0-9_\-]+/[A-Za-z0-9_\-:.]+$")
_EUROVOC_URI_RE = re.compile(r"^http://eurovoc\.europa\.eu/[A-Za-z0-9_\-]+$")
_ELI_URI_RE = re.compile(r"^https?://(?:publications\.europa\.eu|data\.europa\.eu)/(?:resource/)?eli/[A-Za-z0-9/_\-]+$")
_GENERIC_HTTP_RE = re.compile(r"^https?://[^\s]+$")


# ----------------------------------------------------------------------
# recognise (single, anchored)
# ----------------------------------------------------------------------

def recognise(text: str) -> Optional[IdentifierMatch]:
    """Match a single string against every known identifier shape.

    Returns the most specific match. URI matches take precedence over
    bare-string matches when applicable.
    """
    if not text or not isinstance(text, str):
        return None
    t = text.strip()

    # URI variants first — most specific.
    if _AUTHORITY_URI_RE.match(t):
        return IdentifierMatch(
            kind=IdentifierKind.AUTHORITY_URI,
            value=t,
            canonical_url=t,
            brubru_url=_brubru_url_for_authority(t),
        )
    if _EUROVOC_URI_RE.match(t):
        concept_id = t.rsplit("/", 1)[-1]
        return IdentifierMatch(
            kind=IdentifierKind.EUROVOC_URI,
            value=t,
            canonical_url=t,
            brubru_url=f"https://brubru.beresol.eu/api/v1/discover/cellar/eurovoc/{concept_id}/acts",
        )
    if _ELI_URI_RE.match(t):
        return IdentifierMatch(
            kind=IdentifierKind.ELI_URI,
            value=t,
            canonical_url=t,
            brubru_url=None,  # No direct Brubru route — partner uses ELI as cross-ref
        )

    # CELEX (sector 1-9)
    if _CELEX_RE.match(t):
        return IdentifierMatch(
            kind=IdentifierKind.CELEX,
            value=t,
            canonical_url=f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{t}",
            brubru_url=f"https://brubru.beresol.eu/api/v1/laws?celex={t}",
            parts=_parse_celex_parts(t),
        )

    # ECLI
    if _ECLI_RE.match(t):
        return IdentifierMatch(
            kind=IdentifierKind.ECLI,
            value=t.upper(),
            canonical_url=f"https://e-justice.europa.eu/ecli/{t}",
            brubru_url=None,
            parts=_parse_ecli_parts(t),
        )

    # ISBN / ISSN — order matters (ISSN is shorter)
    if _ISSN_RE.match(t):
        cleaned = re.sub(r"[ISSN\s:]", "", t, flags=re.IGNORECASE)
        return IdentifierMatch(kind=IdentifierKind.ISSN, value=cleaned)
    if _ISBN_RE.match(t):
        cleaned = re.sub(r"[\s-]", "", re.sub(r"^ISBN[:\s-]?", "", t, flags=re.IGNORECASE))
        return IdentifierMatch(
            kind=IdentifierKind.ISBN,
            value=cleaned,
            canonical_url=f"https://op.europa.eu/en/publication-search?facet.identifier={cleaned}",
        )

    # DOI
    if _DOI_RE.match(t):
        cleaned = re.sub(r"^doi:\s*", "", t, flags=re.IGNORECASE)
        return IdentifierMatch(
            kind=IdentifierKind.DOI,
            value=cleaned,
            canonical_url=f"https://doi.org/{cleaned}",
        )

    # OJ reference
    if _OJ_RE.match(t):
        return IdentifierMatch(
            kind=IdentifierKind.OJ_REF,
            value=t,
            canonical_url=f"http://publications.europa.eu/resource/oj/{t}",
        )

    # Catalogue number
    if _CATALOGUE_RE.match(t):
        return IdentifierMatch(
            kind=IdentifierKind.CATALOGUE_NUMBER,
            value=t,
            canonical_url=f"https://op.europa.eu/en/publication-detail?facet.catNumber={t}",
        )

    # Generic URI as the catch-all
    if _GENERIC_HTTP_RE.match(t):
        return IdentifierMatch(kind=IdentifierKind.URI, value=t, canonical_url=t)

    return None


# ----------------------------------------------------------------------
# parse_all — find every identifier embedded in a longer string
# ----------------------------------------------------------------------

def parse_all(text: str) -> List[IdentifierMatch]:
    """Scan a longer string for every embedded identifier.

    Used for chat / context enrichment when the user pastes a paragraph
    that contains a CELEX, an ECLI, and an ISSN.
    """
    out: List[IdentifierMatch] = []
    seen: set = set()
    if not text:
        return out

    # ECLI before CELEX (ECLI contains alpha that could shadow some CELEX shapes).
    for m in _ECLI_SCAN.finditer(text):
        match = recognise(m.group(0))
        if match and match.value not in seen:
            seen.add(match.value)
            out.append(match)
    for m in _CELEX_SCAN.finditer(text):
        match = recognise(m.group(0))
        if match and match.value not in seen:
            seen.add(match.value)
            out.append(match)
    for m in _CATALOGUE_SCAN.finditer(text):
        match = recognise(m.group(0))
        if match and match.value not in seen:
            seen.add(match.value)
            out.append(match)
    for m in _OJ_SCAN.finditer(text):
        match = recognise(m.group(0))
        if match and match.value not in seen:
            seen.add(match.value)
            out.append(match)
    for m in _DOI_SCAN.finditer(text):
        match = recognise(m.group(0))
        if match and match.value not in seen:
            seen.add(match.value)
            out.append(match)
    for m in _ISSN_SCAN.finditer(text):
        match = recognise(m.group(0))
        if match and match.value not in seen:
            seen.add(match.value)
            out.append(match)

    return out


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _parse_celex_parts(celex: str) -> dict:
    m = re.match(r"^(\d[A-Z\d]?)(\d{4})([A-Z]{1,2})(\d{1,5})(R\(\d+\))?$", celex)
    if not m:
        return {"raw": celex}
    sector, year, type_letter, serial, corrigendum = m.groups()
    return {
        "sector": sector,
        "year": year,
        "type_letter": type_letter,
        "serial": serial,
        "corrigendum": corrigendum or None,
    }


def _parse_ecli_parts(ecli: str) -> dict:
    parts = ecli.upper().split(":")
    if len(parts) < 5:
        return {"raw": ecli}
    _, country, court, year, ordinal = parts[0], parts[1], parts[2], parts[3], parts[4]
    return {"country": country, "court": court, "year": year, "ordinal": ordinal}


def _brubru_url_for_authority(uri: str) -> Optional[str]:
    """Map an authority URI to the right Brubru v1 vocabulary endpoint
    where one exists; otherwise return None."""
    # http://publications.europa.eu/resource/authority/{name}/{code}
    parts = uri.split("/resource/authority/", 1)
    if len(parts) != 2:
        return None
    name = parts[1].split("/", 1)[0]
    slug_by_name = {
        "corporate-body": "corporate-bodies",
        "procedure": "procedures",
        "dir-eu-legal-act": "directories",
        "modification-type": "modification-types",
    }
    slug = slug_by_name.get(name)
    if not slug:
        return None
    return f"https://brubru.beresol.eu/api/v1/vocabularies/{slug}"
