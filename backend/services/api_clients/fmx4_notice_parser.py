"""
FMX4 Notice Parser

Fetches and parses the Formex document notice for an EU act, returning
all (language, format, manifestation_uri) tuples.

Notice URL pattern (from Publications Office spec, 12 Nov 2025):
    https://eur-lex.europa.eu/legal-content/EN/TXT/XML/?uri=CELEX:{CELEX}

The notice is plain Formex XML (not Cloudflare-protected). For each
language expression, it lists every manifestation URL — FMX4 XML, XHTML,
PDF, PDF/A-1a, DOCX — under <EXPRESSION_MANIFESTED_BY_MANIFESTATION>
blocks.

Manifestation format is inferred from the URL suffix:
    .fmx4    -> FMX4 (canonical structured XML)
    .xhtml   -> XHTML
    .pdfa1a  -> PDF/A-1a
    .pdf     -> PDF
    .docx    -> DOCX

Used by:
    - api/v1/cellar_discover.py (languages endpoint enrichment)
    - services/catalan_translate.py (XML source resolver — replaces
      LEG_2025-11 dump dependency for newer acts)
    - services/ai/context_builder.py (chat language preference fetch)
"""

from __future__ import annotations

import logging
import re
import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


NOTICE_URL_TEMPLATE = "https://eur-lex.europa.eu/legal-content/EN/TXT/XML/?uri=CELEX:{celex}"

# Pinned Formex schema version (Phase 0 of docs/applications/euvoc.md).
# Notices we parse are produced against this XSD; bumping the version is a
# co-ordinated action across the parser + downstream consumers (Catalan
# pipeline, v1 manifestations endpoint).
FORMEX_SCHEMA_VERSION = "formex-06.02.3-20250123.xd"
FORMEX_SCHEMA_URL = (
    "http://publications.europa.eu/resource/distribution/formex/xsd/schema_formex/"
    + FORMEX_SCHEMA_VERSION
)

# Real-browser UA — the notice URL itself is not WAF-protected, but some
# variants are; defensive headers improve reliability.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
    ),
    "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en",
}

_FORMAT_FROM_SUFFIX = {
    "fmx4": "fmx4",
    "xhtml": "xhtml",
    "xhtml5": "xhtml5",
    "pdfa1a": "pdfa1a",
    "pdfa2a": "pdfa2a",
    "pdf": "pdf",
    "docx": "docx",
    "doc": "doc",
    "html": "html",
    "epub": "epub",
    "print": "print",  # legacy print-ready manifestation, observed in the wild
    "wordperfect": "wordperfect",
    "tiff": "tiff",
}

_URL_FORMAT_RE = re.compile(r"\.([A-Z]{3})\.([A-Za-z0-9]+)(?:\?|$)")

# Corrigenda CELEX pattern (e.g. 32016R0427R(01), 32024L1203R(03))
# Verified empirically May 2026: corrigendum CELEX numbers do NOT have a
# standalone document notice via the EUR-Lex "legal-content/EN/TXT/XML"
# endpoint NOR via Cellar /resource/celex/{...}. Both return 404. Callers
# should resolve to the BASE CELEX (strip the trailing "R(NN)") and fetch
# the parent notice if they need the underlying act's manifestations.
_CORRIGENDUM_SUFFIX_RE = re.compile(r"R\(\d+\)$")


@dataclass
class Manifestation:
    """One downloadable representation of an act in one language and format."""

    language: str
    format: str
    url: str
    identifier: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class NoticeMetadata:
    """Top-level metadata extracted from the Formex notice."""

    celex: Optional[str] = None
    cellar_uri: Optional[str] = None
    eli: Optional[str] = None
    oj_reference: Optional[str] = None
    languages_available: List[str] = field(default_factory=list)
    titles: Dict[str, str] = field(default_factory=dict)
    manifestations: List[Manifestation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "celex": self.celex,
            "cellar_uri": self.cellar_uri,
            "eli": self.eli,
            "oj_reference": self.oj_reference,
            "languages_available": self.languages_available,
            "titles": self.titles,
            "manifestations": [m.to_dict() for m in self.manifestations],
            "manifestation_count": len(self.manifestations),
        }

    def manifestations_by_format(self, fmt: str) -> List[Manifestation]:
        return [m for m in self.manifestations if m.format == fmt]

    def manifestation(self, language: str, fmt: str) -> Optional[Manifestation]:
        lang = language.upper()
        fmt_l = fmt.lower()
        for m in self.manifestations:
            if m.language == lang and m.format == fmt_l:
                return m
        return None


def _infer_format_from_url(url: str) -> Optional[str]:
    """Infer the manifestation format from the URL suffix."""
    match = _URL_FORMAT_RE.search(url)
    if not match:
        # Cellar-style URLs (e.g. /resource/celex/{CELEX}.{LANG}.xhtml)
        bits = url.rsplit(".", 1)
        if len(bits) == 2:
            return _FORMAT_FROM_SUFFIX.get(bits[-1].lower())
        return None
    suffix = match.group(2).lower()
    return _FORMAT_FROM_SUFFIX.get(suffix, suffix)


def _findtext(elem: ET.Element, path: str) -> Optional[str]:
    found = elem.find(path)
    return found.text if found is not None and found.text else None


def parse_notice_xml(xml_bytes: bytes) -> NoticeMetadata:
    """
    Parse a Formex notice payload (bytes) into NoticeMetadata.

    Robust to namespace differences and handles the embedded-notice
    pattern where each <EXPRESSION> sits inside a <WORK_HAS_EXPRESSION>.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as e:
        raise ValueError(f"Notice is not valid XML: {e}") from e

    meta = NoticeMetadata()

    # Top-level WORK -> SAMEAS to find canonical IDs
    for sameas in root.findall(".//WORK/SAMEAS/URI"):
        type_text = _findtext(sameas, "TYPE")
        value_text = _findtext(sameas, "VALUE")
        if not value_text:
            continue
        if type_text == "celex":
            # Corrigendum CELEX numbers (e.g. 32016R0427R(01)) come back
            # URL-encoded in the notice — decode them so callers see the
            # canonical literal form.
            meta.celex = urllib.parse.unquote(value_text.rsplit("/", 1)[-1])
        elif type_text == "eli":
            meta.eli = value_text
        elif type_text == "oj":
            meta.oj_reference = value_text.rsplit("/", 1)[-1]

    # Cellar URI is the WORK itself (first <WORK><URI><VALUE>)
    cellar_uri = root.find("./WORK/URI/VALUE")
    if cellar_uri is not None and cellar_uri.text:
        meta.cellar_uri = cellar_uri.text

    # If the top SAMEAS path didn't match (some notices wrap differently)
    # walk down and pick from any URI block with TYPE=celex
    if not meta.celex:
        for uri in root.findall(".//URI"):
            type_text = _findtext(uri, "TYPE")
            if type_text == "celex":
                value_text = _findtext(uri, "VALUE")
                if value_text:
                    meta.celex = urllib.parse.unquote(value_text.rsplit("/", 1)[-1])
                    break

    # Walk EXPRESSION blocks scoped to the ROOT work and its consolidations.
    # The Formex notice frequently embeds sub-notices for related acts
    # (e.g. GDPR's notice embeds the repealed Data Protection Directive
    # 01995L0046). Without scoping, manifestation harvesting leaks URLs from
    # those unrelated acts. We accept embedded notices whose ID_CELEX equals
    # the root or is a consolidation of it (pattern: "0" + root_tail + "-DATE").
    root_celex = meta.celex
    root_tail = root_celex[1:] if root_celex else None

    def _belongs_to_root(embedded: ET.Element) -> bool:
        if root_celex is None:
            return True  # can't filter — keep everything
        id_celex_node = embedded.find("./WORK/ID_CELEX/VALUE")
        if id_celex_node is None or not id_celex_node.text:
            return True  # default-include when no embedded CELEX label
        em_celex = id_celex_node.text.strip()
        if em_celex == root_celex:
            return True
        # Consolidation pattern: starts with "0", contains the root's
        # year+typeletter+serial substring, and has a date suffix.
        if root_tail and em_celex.startswith("0") and root_tail in em_celex:
            return True
        return False

    expressions: List[ET.Element] = []
    for embedded in root.findall(".//EMBEDDED_NOTICE"):
        if not _belongs_to_root(embedded):
            continue
        expressions.extend(embedded.findall("./EXPRESSION"))
    # Some notices have EXPRESSIONS at the top level (not wrapped in
    # EMBEDDED_NOTICE) — include them.
    for direct in root.findall("./WORK/EXPRESSION"):
        expressions.append(direct)

    # If we found nothing (unusual notice shape), fall back to global walk.
    if not expressions:
        expressions = root.findall(".//EXPRESSION")

    seen: set = set()  # de-dup manifestations across embedded notices
    languages_seen: set = set()

    for expr in expressions:
        # Language
        lang_uri = expr.find("./EXPRESSION_USES_LANGUAGE/URI")
        lang_code: Optional[str] = None
        if lang_uri is not None:
            lang_code = _findtext(lang_uri, "IDENTIFIER")
        if not lang_code:
            # Fallback to OP-CODE
            op_code = expr.find("./EXPRESSION_USES_LANGUAGE/OP-CODE")
            lang_code = op_code.text if op_code is not None and op_code.text else None
        if not lang_code:
            continue
        lang_code = lang_code.upper()
        languages_seen.add(lang_code)

        # Title
        title_node = expr.find("./EXPRESSION_TITLE/VALUE")
        if title_node is not None and title_node.text and lang_code not in meta.titles:
            meta.titles[lang_code] = title_node.text.strip()

        # Manifestations
        for manif in expr.findall("./EXPRESSION_MANIFESTED_BY_MANIFESTATION"):
            uri = manif.find("./SAMEAS/URI")
            if uri is None:
                continue
            url = _findtext(uri, "VALUE")
            if not url:
                continue
            identifier = _findtext(uri, "IDENTIFIER")
            fmt = _infer_format_from_url(url)
            if fmt is None:
                continue
            key = (lang_code, fmt, url)
            if key in seen:
                continue
            seen.add(key)
            meta.manifestations.append(
                Manifestation(language=lang_code, format=fmt, url=url, identifier=identifier)
            )

    meta.languages_available = sorted(languages_seen)
    return meta


async def fetch_notice(celex: str, timeout: int = 30, max_retries: int = 3) -> NoticeMetadata:
    """
    Fetch and parse the Formex document notice for a CELEX.

    EUR-Lex's notice endpoint is async — it can return HTTP 202 with an
    empty body while the response is still being built. We retry with
    exponential backoff (1s → 2s → 4s) up to ``max_retries`` times before
    giving up.

    Args:
        celex: CELEX number (e.g. "32016R0679").
        timeout: HTTP timeout in seconds for each individual request.
        max_retries: number of retries when EUR-Lex returns 202 + empty body.

    Returns:
        NoticeMetadata with all manifestations populated.

    Raises:
        ValueError if CELEX is empty or notice is not retrievable after retries.
    """
    import asyncio

    if not celex:
        raise ValueError("CELEX is required")

    # Corrigendum CELEX numbers don't have standalone notices. Fail fast
    # with a clear hint to fetch the base CELEX instead.
    if _CORRIGENDUM_SUFFIX_RE.search(celex):
        base = _CORRIGENDUM_SUFFIX_RE.sub("", celex)
        raise ValueError(
            f"CELEX {celex!r} is a corrigendum; no standalone notice exists. "
            f"Fetch the base CELEX {base!r} instead."
        )

    # URL-encode the CELEX (defensive — base CELEX numbers are already URL-safe).
    encoded_celex = urllib.parse.quote(celex, safe="")
    url = NOTICE_URL_TEMPLATE.format(celex=encoded_celex)

    backoff = 1.0
    last_status: Optional[int] = None
    async with httpx.AsyncClient(timeout=timeout, headers=_HEADERS, follow_redirects=True) as client:
        for attempt in range(max_retries + 1):
            resp = await client.get(url)
            last_status = resp.status_code

            # 202 Accepted = EUR-Lex is still building the response. Retry.
            if resp.status_code == 202 or (resp.status_code == 200 and not resp.content):
                if attempt < max_retries:
                    logger.info(
                        "EUR-Lex notice %s returned %s (attempt %d/%d) — retrying in %.1fs",
                        celex, resp.status_code, attempt + 1, max_retries + 1, backoff,
                    )
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue
                raise ValueError(
                    f"Notice for {celex} returned HTTP {resp.status_code} + empty body "
                    f"after {max_retries + 1} attempts. EUR-Lex is rebuilding — try again shortly."
                )

            resp.raise_for_status()

            # Defensive — if EUR-Lex returns an HTML challenge, fail loudly.
            first_byte = resp.content[:200].lower()
            if b"<html" in first_byte and b"<notice" not in first_byte:
                raise ValueError(
                    f"Notice for {celex} returned HTML (likely WAF-redirected). "
                    f"Check CELEX validity or try Cellar fallback."
                )
            return parse_notice_xml(resp.content)

    # Defensive: should be unreachable given the for-loop logic above.
    raise ValueError(f"Notice for {celex} unreachable (last status {last_status})")


def fmx4_url_for(meta: NoticeMetadata, language: str = "ENG") -> Optional[str]:
    """Convenience: return the FMX4 manifestation URL for a language, if any."""
    m = meta.manifestation(language, "fmx4")
    return m.url if m else None


def xhtml_url_for(meta: NoticeMetadata, language: str = "ENG") -> Optional[str]:
    m = meta.manifestation(language, "xhtml")
    return m.url if m else None


def pdf_url_for(meta: NoticeMetadata, language: str = "ENG") -> Optional[str]:
    """Prefer PDF/A-1a when available, fall back to plain PDF."""
    m = meta.manifestation(language, "pdfa1a") or meta.manifestation(language, "pdf")
    return m.url if m else None
