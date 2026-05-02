"""
DET / AKN4EU 4.2 renderer.

Phase 6 of docs/applications/euvoc.md.

Naming note: the canonical plan calls this layer "DET" (Drafting Editing
Templates). After Victor's 2 May 2026 input, we standardise on
**AKN4EU 4.2** (Akoma Ntoso 4 EU) as the spec backbone — the canonical
public legal-drafting schema the EU institutions are migrating toward.
DET specs proper are still pending from the Publications Office; until
they land, AKN4EU output covers the practical use case (Commission /
EP / Council drafters can open the XML in their tooling).

Reference artefacts (vendored under docs/ontologies/akn4eu/):
  - docs/AKN4EU_4-2_PART_1_guideline.pdf            (3.4 MB)
  - docs/AKN4EU_4-2_PART_2_document-types.pdf       (3.8 MB)
  - docs/AKN4EU_4-2_PART_3_correspondence_with_CoV_4-2.pdf (0.4 MB)
  - schema/publication-AKN4EU-4.2-2024-10-29/...    (16 sample instances)

Public API:
    render(document, *, format="akn4eu_xml") -> bytes
    SUPPORTED_TYPES = {"position_paper", "amendment", "briefing_note", "ep_question"}
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional
from xml.sax.saxutils import escape as _xml_escape

logger = logging.getLogger(__name__)

# Brubru document types currently supported by the renderer.
SUPPORTED_TYPES = {
    "position_paper": {
        "akn_name": "doc",
        "long_title_default": "Position paper",
        "doc_type_label": "POSITION PAPER",
    },
    "amendment": {
        "akn_name": "amendmentList",
        "long_title_default": "Amendments",
        "doc_type_label": "AMENDMENTS",
    },
    "briefing_note": {
        "akn_name": "doc",
        "long_title_default": "Briefing note",
        "doc_type_label": "BRIEFING NOTE",
    },
    "ep_question": {
        "akn_name": "doc",
        "long_title_default": "Parliamentary question",
        "doc_type_label": "PARLIAMENTARY QUESTION",
    },
}

AKN_NAMESPACE = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"
AKN4EU_VERSION = "4.2.0.0"
AKN4EU_DOCUMENTATION_URL = (
    "https://op.europa.eu/en/web/eu-vocabularies/dataset/-/resource?"
    "uri=http://publications.europa.eu/resource/dataset/akn4eu"
)


class UnsupportedDocumentTypeError(ValueError):
    """Raised when render() is given a doc type Brubru doesn't ship."""


def render(document: Dict[str, Any], *, format: str = "akn4eu_xml") -> bytes:
    """
    Convert a Brubru-internal document into AKN4EU 4.2 XML (or DET later).

    Args:
        document: A dict carrying:
            - "type": one of SUPPORTED_TYPES keys (required)
            - "title": string (required)
            - "language": ISO-639 lowercase (default "en")
            - "author": string or dict (Brubru / partner; optional)
            - "date": ISO date string (default today)
            - "celex_target": optional CELEX of the act this document acts on
            - "body_paragraphs": list of plain-text paragraphs OR
            - "amendments": list of {article, current, proposed, justification}
                (only for type=amendment)
            - "immc_tags": optional dict carrying inter-institutional handoff
              metadata (Phase 5) — surfaced as TLCEvent references
        format: Currently only "akn4eu_xml" is implemented. "det_docx" returns
            NotImplementedError until DET XSDs land.

    Returns:
        UTF-8 encoded bytes of the rendered document.
    """
    if format == "det_docx":
        raise NotImplementedError(
            "DET DOCX rendering is gated on Publications Office DET XSDs. "
            "Use format='akn4eu_xml' for now (AKN4EU 4.2-compliant XML "
            "the EP and Council toolchains accept)."
        )
    if format != "akn4eu_xml":
        raise ValueError(f"unsupported render format: {format}")

    doc_type = document.get("type")
    if doc_type not in SUPPORTED_TYPES:
        raise UnsupportedDocumentTypeError(
            f"document type '{doc_type}' not in {sorted(SUPPORTED_TYPES)}"
        )
    return _render_akn4eu(document).encode("utf-8")


def _render_akn4eu(document: Dict[str, Any]) -> str:
    spec = SUPPORTED_TYPES[document["type"]]
    title = document.get("title") or spec["long_title_default"]
    language = (document.get("language") or "en").lower()
    today_iso = (document.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    celex_target = document.get("celex_target") or ""
    author_label = document.get("author") or "Brubru / Beresol"

    # FRBR identification stubs — exhaustive concrete URIs aren't
    # available at draft-time; preserve the AKN4EU 4.2 shape so the
    # downstream EP/COM toolchain can fill them in.
    frbr_work = (
        '<FRBRWork>'
        '<FRBRthis value=""/>'
        '<FRBRuri value=""/>'
        f'<FRBRdate date="{today_iso}" name=""/>'
        '<FRBRauthor href=""/>'
        '<FRBRcountry value="EU"/>'
        '<FRBRnumber value=""/>'
        '<FRBRprescriptive value="true"/>'
        '</FRBRWork>'
    )
    frbr_expression = (
        '<FRBRExpression>'
        '<FRBRthis value=""/>'
        '<FRBRuri value=""/>'
        f'<FRBRdate date="{today_iso}" name=""/>'
        '<FRBRauthor href=""/>'
        f'<FRBRlanguage language="{language}"/>'
        '</FRBRExpression>'
    )
    frbr_manifestation = (
        '<FRBRManifestation>'
        '<FRBRthis value=""/>'
        '<FRBRuri value=""/>'
        f'<FRBRdate date="{today_iso}" name=""/>'
        '<FRBRauthor href=""/>'
        '<preservation xmlns:akn4eu="http://imfc.europa.eu/akn4eu">'
        f'<akn4eu:akn4euVersion value="{AKN4EU_VERSION}"/>'
        f'<akn4eu:akn4euDocumentation href="{AKN4EU_DOCUMENTATION_URL}"/>'
        f'<akn4eu:brubruRenderer value="brubru.det_renderer"/>'
        '</preservation>'
        '</FRBRManifestation>'
    )

    # References: language + the resource-type concept the doc maps to.
    references = (
        '<references source="~BRUBRU">'
        f'<TLCReference name="language" href="http://publications.europa.eu/resource/authority/language/{language.upper()}" showAs="{language}"/>'
        f'<TLCOrganization xml:id="BRUBRU" href="https://brubru.beresol.eu/.well-known/publisher" showAs="{_xml_escape(str(author_label))}"/>'
    )
    if celex_target:
        references += (
            f'<TLCReference xml:id="targetAct" name="actsOn" '
            f'href="http://publications.europa.eu/resource/celex/{_xml_escape(celex_target)}" '
            f'showAs="CELEX:{_xml_escape(celex_target)}"/>'
        )
    # Phase 5 — IMMC handoff events surfaced as TLCEvent refs.
    immc = document.get("immc_tags") or {}
    for i, ev in enumerate((immc.get("events") or [])[:10]):
        ev_uri = ev.get("event") or f"#brubru-event-{i}"
        ev_label = ev.get("type") or ev.get("date") or "event"
        references += (
            f'<TLCEvent xml:id="ev{i}" '
            f'href="{_xml_escape(str(ev_uri))}" '
            f'showAs="{_xml_escape(str(ev_label))[:80]}"/>'
        )
    references += "</references>"

    # Body — different shape per doc type.
    if document["type"] == "amendment":
        body = _render_amendment_body(document)
    else:
        body = _render_prose_body(document)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<akomaNtoso xmlns="{AKN_NAMESPACE}">\n'
        f'<{spec["akn_name"]} name="{document["type"]}">\n'
        '<meta>\n'
        '<identification source="~BRUBRU">\n'
        f'{frbr_work}\n'
        f'{frbr_expression}\n'
        f'{frbr_manifestation}\n'
        '</identification>\n'
        f'{references}\n'
        '</meta>\n'
        '<preface>\n'
        '<longTitle>\n'
        f'<p><docType refersTo="~BRUBRU">{_xml_escape(spec["doc_type_label"])}</docType> '
        f'— <docTitle>{_xml_escape(title)}</docTitle> '
        f'<date date="{today_iso}">{today_iso}</date></p>\n'
        '</longTitle>\n'
        '</preface>\n'
        f'{body}\n'
        f'</{spec["akn_name"]}>\n'
        '</akomaNtoso>\n'
    )


def _render_prose_body(document: Dict[str, Any]) -> str:
    paragraphs: Iterable[str] = document.get("body_paragraphs") or []
    parts = ['<mainBody>']
    for i, para in enumerate(paragraphs):
        if not isinstance(para, str) or not para.strip():
            continue
        parts.append(
            f'<paragraph xml:id="para_{i+1}"><content><p>{_xml_escape(para)}</p></content></paragraph>'
        )
    if len(parts) == 1:
        # No paragraphs supplied — render a placeholder so the doc parses.
        parts.append('<paragraph xml:id="para_1"><content><p>(empty body)</p></content></paragraph>')
    parts.append('</mainBody>')
    return "\n".join(parts)


def _render_amendment_body(document: Dict[str, Any]) -> str:
    amendments: Iterable[Dict[str, Any]] = document.get("amendments") or []
    parts = ['<amendmentBody>']
    for i, am in enumerate(amendments):
        article = am.get("article") or "—"
        current = am.get("current") or ""
        proposed = am.get("proposed") or ""
        justification = am.get("justification") or ""
        parts.append(
            f'<amendmentJustification xml:id="am_{i+1}_just">'
            f'<p>{_xml_escape(justification)}</p>'
            '</amendmentJustification>'
        )
        parts.append(
            f'<amendmentContent xml:id="am_{i+1}_content">'
            f'<p>Article: {_xml_escape(article)}</p>'
            f'<mod><quotedText>{_xml_escape(current)}</quotedText> '
            f'<quotedText>{_xml_escape(proposed)}</quotedText></mod>'
            '</amendmentContent>'
        )
    if len(parts) == 1:
        parts.append('<p>(no amendments supplied)</p>')
    parts.append('</amendmentBody>')
    return "\n".join(parts)
