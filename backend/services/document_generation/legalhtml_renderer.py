"""
LegalHTML renderer + validator.

Phase 12 of docs/applications/euvoc.md.

LegalHTML is the Publications Office's HTML extension for representing
EU legal documents (W3ID spec at https://w3id.org/legalhtml/specs/,
2024-01-15). It augments XHTML with:

  - `is="lh-*"` custom-element attributes (lh-title, lh-preamble,
    lh-citations, lh-citation, lh-recitals, lh-recital-list,
    lh-recital, lh-recital-init, lh-number, lh-footnote-ref, ...)
  - RDFa-style attributes (rel, resource, property, about, xmlns:*)
  - Authority-list URI references (corpbody:, place:, role:)
  - <time datetime="..."> for dates
  - ELI ontology predicates (eli:based_on, eli:type_document, eli:relevance)

Local artefacts vendored under docs/ontologies/legalhtml/:
  - LegalHTML-2024-01-15/legalhtml-specs/index.html  (the W3ID spec)
  - LegalHTML-2024-01-15/LegalHTML - Correspondence with CoV 4.docx
  - COV-LegalHTML-converted-docs/  (~30 reference instance documents
    with .xhtml LegalHTML output + .xml Formex source +
    .xml.html alternate rendering + CELEX_*.pdf reference)

Public API:
    render(document, *, lang="en") -> bytes
    validate(html_bytes) -> ValidationResult
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from xml.sax.saxutils import escape as _xml_escape

logger = logging.getLogger(__name__)

LH_NS = "http://data.europa.eu/legalhtml#"
ELI_NS = "http://data.europa.eu/eli/ontology#"
CORPBODY_NS = "http://publications.europa.eu/resource/authority/corporate-body/"
PLACE_NS = "http://publications.europa.eu/resource/authority/place/"
ROLE_NS = "http://publications.europa.eu/resource/authority/role/"
RESOURCE_TYPE_NS = "http://publications.europa.eu/resource/authority/resource-type/"

LEGALHTML_VERSION = "2024-01-15"
SPEC_URL = "https://w3id.org/legalhtml/specs/"

# Map Brubru document.type -> LegalHTML resource-type code.
# (Only the document types this renderer covers — extend as needed.)
_RESOURCE_TYPE_BY_DOCTYPE = {
    "regulation": "REG",
    "directive": "DIR",
    "decision": "DEC",
    "recommendation": "REC",
    "communication": "COMMUNIC",
    "proposal": "PROP_REG",
}


# ----------------------------------------------------------------------
# Render
# ----------------------------------------------------------------------

def render(document: Dict[str, Any], *, lang: str = "en") -> bytes:
    """
    Render a Brubru-internal legal-act document as LegalHTML XHTML.

    Args:
        document: dict with keys:
            - title: full official title (string)
            - effective_title: (optional) the "repealing X" / "on Y" tail
            - act_type: 'regulation' | 'directive' | 'decision' | ...
            - act_date: ISO date string (YYYY-MM-DD)
            - acting_entities: list of {label, corp_body_code} —
              e.g. [{"label": "THE EUROPEAN PARLIAMENT", "corp_body_code": "EP"}]
            - eea_relevance: bool (default False)
            - citations: list of {text, eli_predicate?, href?}
              e.g. [{"text": "Treaty on the Functioning ...", "eli_predicate": "eli:based_on", "href": "..."}]
            - recitals: list of {n: int, text: str}
            - articles: list of {n: int, title: str, text: str}
            - celex: optional CELEX number for the canonical resource
        lang: ISO-639 lowercase

    Returns:
        UTF-8 XHTML bytes.
    """
    title = document.get("title", "Untitled act")
    effective_title = document.get("effective_title")
    act_date = document.get("act_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    act_type = (document.get("act_type") or "").lower()
    res_type_code = _RESOURCE_TYPE_BY_DOCTYPE.get(act_type, "REG")
    eea = bool(document.get("eea_relevance"))
    acting = document.get("acting_entities") or []
    citations = document.get("citations") or []
    recitals = document.get("recitals") or []
    articles = document.get("articles") or []
    celex = document.get("celex") or ""

    parts: List[str] = []
    parts.append('<?xml version="1.0" encoding="UTF-8"?>')
    # Optional ELI base IRI (xmlns:base) — only emit when supplied so we
    # don't ship an empty-URI namespace declaration (invalid XML).
    base_iri = document.get("eli_base") or ""
    base_attr = f'xmlns:base="{_xml_escape(base_iri)}" ' if base_iri else ""
    parts.append(
        f'<html xml:lang="{lang}" xmlns="http://www.w3.org/1999/xhtml" '
        f'{base_attr}'
        f'xmlns:corpbody="{CORPBODY_NS}" '
        f'xmlns:eli="{ELI_NS}" '
        f'xmlns:lh="{LH_NS}" '
        f'xmlns:place="{PLACE_NS}" '
        f'xmlns:r="http://www.w3.org/1999/02/22-rdf-syntax-ns#" '
        f'xmlns:role="{ROLE_NS}">'
    )
    parts.append("<head>")
    parts.append(
        f'<meta about="" property="eli:type_document" '
        f'resource="{RESOURCE_TYPE_NS}{res_type_code}"/>'
    )
    parts.append(f'<title>{_xml_escape(title)}</title>')
    if celex:
        parts.append(
            f'<meta about="" property="eli:id_local" content="{_xml_escape(celex)}"/>'
        )
    parts.append(
        f'<meta name="generator" content="brubru.legalhtml_renderer; '
        f'spec={SPEC_URL}; spec_version={LEGALHTML_VERSION}"/>'
    )
    parts.append("</head>")
    parts.append("<body>")

    # ---------- title block ----------
    parts.append('<header is="lh-title">')
    parts.append(f'<h1>{_xml_escape(title)}</h1>')
    parts.append(
        f'<h1>of <time datetime="{act_date}">{_humanise_date(act_date, lang)}</time></h1>'
    )
    if effective_title:
        parts.append(
            f'<h1 is="lh-effective-title">{_xml_escape(effective_title)}</h1>'
        )
    parts.append("</header>")

    if eea:
        parts.append(
            f'<h1 rel="lh:relevance" resource="corpbody:EEAREA">'
            f'(Text with EEA relevance)</h1>'
        )

    # ---------- preamble ----------
    parts.append('<section is="lh-preamble">')
    if acting:
        ent_html = " AND ".join(
            f'<span rel="lh:actingEntity" resource="corpbody:'
            f'{_xml_escape(e.get("corp_body_code", ""))}">'
            f'{_xml_escape(e.get("label", ""))}</span>'
            for e in acting
        )
        parts.append(f'<div is="lh-preamble-init">{ent_html}</div>')

    if citations:
        parts.append('<div is="lh-citations">')
        for c in citations:
            text = c.get("text", "")
            href = c.get("href")
            pred = c.get("eli_predicate")
            if href and pred:
                parts.append(
                    f'<div is="lh-citation">Having regard to the '
                    f'<a href="{_xml_escape(href)}" property="{_xml_escape(pred)}">'
                    f'{_xml_escape(text)}</a>,</div>'
                )
            else:
                parts.append(f'<div is="lh-citation">{_xml_escape(text)}</div>')
        parts.append("</div>")

    if recitals:
        parts.append('<div is="lh-recitals">')
        parts.append('<div is="lh-recital-init">Whereas:</div>')
        parts.append('<ol is="lh-recital-list">')
        for r in recitals:
            n = r.get("n", "")
            text = r.get("text", "")
            parts.append(
                f'<li><span data-value="{n}" is="lh-number">({n})</span>'
                f'<div is="lh-recital">{_xml_escape(text)}</div></li>'
            )
        parts.append("</ol>")
        parts.append("</div>")

    parts.append("</section>")  # /lh-preamble

    # ---------- body / articles ----------
    if articles:
        parts.append('<section is="lh-body">')
        for a in articles:
            n = a.get("n", "")
            title_a = a.get("title", "")
            text = a.get("text", "")
            parts.append('<article is="lh-article">')
            parts.append(
                f'<h2 is="lh-article-title">Article {_xml_escape(str(n))}'
                + (f' — {_xml_escape(title_a)}' if title_a else "")
                + '</h2>'
            )
            parts.append(f'<div is="lh-article-body">{_xml_escape(text)}</div>')
            parts.append("</article>")
        parts.append("</section>")

    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts).encode("utf-8")


def _humanise_date(iso_date: str, lang: str) -> str:
    """Render YYYY-MM-DD as e.g. '11 February 2015' / '11 de febrer de 2015'."""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d")
    except ValueError:
        return iso_date
    months = {
        "en": ["", "January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"],
        "ca": ["", "gener", "febrer", "març", "abril", "maig", "juny",
               "juliol", "agost", "setembre", "octubre", "novembre", "desembre"],
        "es": ["", "enero", "febrero", "marzo", "abril", "mayo", "junio",
               "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
        "fr": ["", "janvier", "février", "mars", "avril", "mai", "juin",
               "juillet", "août", "septembre", "octobre", "novembre", "décembre"],
        "it": ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
               "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
        "nl": ["", "januari", "februari", "maart", "april", "mei", "juni",
               "juli", "augustus", "september", "oktober", "november", "december"],
    }
    m = months.get(lang, months["en"])[d.month]
    if lang in ("ca", "es", "it"):
        return f"{d.day} de {m} de {d.year}"
    if lang == "fr":
        return f"{d.day} {m} {d.year}"
    if lang == "nl":
        return f"{d.day} {m} {d.year}"
    return f"{d.day} {m} {d.year}"


# ----------------------------------------------------------------------
# Validate
# ----------------------------------------------------------------------

@dataclass
class ValidationResult:
    ok: bool = True
    passes: int = 0
    fails: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    detected_features: Dict[str, int] = field(default_factory=dict)


# Required vs. optional checks — based on the LegalHTML spec + the shape
# of real CoV reference samples (full acts vs. annexes vs. Council notes
# vs. statements of reasons all share namespaces + eli:type_document but
# diverge structurally).
#
# Each check: (key, description, regex_pattern, required, multiplicity_min)
_LH_CHECKS = [
    # Required (universal across all LegalHTML documents — full acts,
    # annexes, Council notes, statements of reasons):
    ("namespace_lh", "xmlns:lh declared", r'xmlns:lh="http://data\.europa\.eu/legalhtml#"', True, 1),
    ("namespace_eli", "xmlns:eli declared", r'xmlns:eli="http://data\.europa\.eu/eli/ontology#"', True, 1),
    # Optional / document-type-dependent (full acts carry the title +
    # preamble + recital structure; annexes / Council notes / STAT_REASON
    # documents legitimately don't have those elements OR the
    # eli:type_document meta tag):
    ("eli_type_document", "eli:type_document meta present (full acts only)", r'property="eli:type_document"', False, 1),
    ("lh_title_header", '<header is="lh-title"> present (full acts only)', r'is="lh-title"', False, 1),
    ("lh_preamble", "<section is=\"lh-preamble\"> present", r'is="lh-preamble"', False, 1),
    ("lh_citations", "lh-citations present", r'is="lh-citations"', False, 1),
    ("lh_citation", "at least one lh-citation", r'is="lh-citation"', False, 1),
    ("lh_recitals", "lh-recitals present", r'is="lh-recitals"', False, 1),
    ("lh_recital_list", "lh-recital-list present", r'is="lh-recital-list"', False, 1),
    ("lh_recital", "at least one lh-recital", r'is="lh-recital"', False, 1),
    ("lh_number", "lh-number present (numbered recital/article)", r'is="lh-number"', False, 1),
    ("rdfa_resource", "RDFa resource= attributes used", r'\bresource="', False, 1),
    ("rdfa_rel", "RDFa rel= attributes used", r'\brel="', False, 1),
    ("time_datetime", "<time datetime=...> used for dates", r'<time\s+datetime="', False, 1),
]


def validate(html_bytes: bytes) -> ValidationResult:
    """Validate an HTML/XHTML document against the LegalHTML structural pattern.

    Returns a ValidationResult with `ok=True` iff every required check
    passes. Warnings are recorded for optional features that are absent
    so callers can see what's missing without failing.
    """
    res = ValidationResult()
    text = html_bytes.decode("utf-8", errors="replace") if isinstance(html_bytes, (bytes, bytearray)) else html_bytes
    for key, desc, pat, required, mn in _LH_CHECKS:
        n = len(re.findall(pat, text, flags=re.IGNORECASE))
        res.detected_features[key] = n
        if n >= mn:
            res.passes += 1
        else:
            msg = f"[{key}] {desc} — found {n}, required >= {mn}"
            if required:
                res.fails.append(msg)
                res.ok = False
            else:
                res.warnings.append(msg)
    return res
