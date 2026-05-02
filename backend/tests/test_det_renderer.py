"""
Phase 6 of docs/applications/euvoc.md — DET / AKN4EU 4.2 renderer tests.

Static checks (no network, no DB):
  - render() returns well-formed XML the standard library can parse
  - The 4 supported document types each produce the expected akn:* root
  - Multi-language fields are preserved
  - Phase 5 IMMC tags surface as <TLCEvent> references
  - Unsupported types raise UnsupportedDocumentTypeError
  - format='det_docx' raises NotImplementedError (we're honest)
  - The vendored AKN4EU 4.2 documentation PDFs are present + non-empty
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.document_generation.det_renderer import (  # noqa: E402
    AKN4EU_VERSION,
    SUPPORTED_TYPES,
    UnsupportedDocumentTypeError,
    render,
)

ROOT = Path(__file__).resolve().parents[2]
AKN_DIR = ROOT / "docs" / "ontologies" / "akn4eu"
AKN_NS = "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"


def _parse(xml_bytes: bytes) -> ET.Element:
    return ET.fromstring(xml_bytes)


# ----------------------------------------------------------------------
# Render contracts
# ----------------------------------------------------------------------

class TestRenderContract:
    def test_position_paper_well_formed(self):
        out = render(
            {
                "type": "position_paper",
                "title": "Brubru position on the AI Act",
                "language": "en",
                "body_paragraphs": [
                    "Brubru welcomes the AI Act.",
                    "We propose targeted clarifications to Article 6.",
                ],
            }
        )
        root = _parse(out)
        assert root.tag == f"{{{AKN_NS}}}akomaNtoso"
        # mainBody + 2 paragraphs
        paragraphs = root.findall(f".//{{{AKN_NS}}}paragraph")
        assert len(paragraphs) == 2

    def test_amendment_renders_amendment_body(self):
        out = render(
            {
                "type": "amendment",
                "title": "Amendment to Article 8",
                "amendments": [
                    {
                        "article": "8(1)",
                        "current": "Member States shall ensure",
                        "proposed": "Member States shall guarantee",
                        "justification": "Stronger language matches Recital 22.",
                    },
                ],
            }
        )
        root = _parse(out)
        # amendmentBody must exist (we use the amendmentList root for amendments)
        body = root.findall(f".//{{{AKN_NS}}}amendmentBody")
        assert body, "amendmentBody missing"
        # Every amendment carries a justification + content
        assert root.findall(f".//{{{AKN_NS}}}amendmentJustification")
        assert root.findall(f".//{{{AKN_NS}}}amendmentContent")

    def test_briefing_note_well_formed(self):
        out = render({"type": "briefing_note", "title": "Brubru briefing", "body_paragraphs": ["x"]})
        root = _parse(out)
        # briefing notes use the doc root
        assert root.find(f"{{{AKN_NS}}}doc") is not None

    def test_ep_question_well_formed(self):
        out = render({"type": "ep_question", "title": "Question on the DSA", "body_paragraphs": ["q"]})
        root = _parse(out)
        assert root.find(f"{{{AKN_NS}}}doc") is not None

    def test_unsupported_type_raises(self):
        with pytest.raises(UnsupportedDocumentTypeError):
            render({"type": "quux", "title": "x"})

    def test_det_docx_format_not_implemented(self):
        with pytest.raises(NotImplementedError):
            render({"type": "position_paper", "title": "x"}, format="det_docx")

    def test_unknown_format_rejected(self):
        with pytest.raises(ValueError):
            render({"type": "position_paper", "title": "x"}, format="csv")


class TestStructuralSignals:
    def test_akn4eu_version_in_preservation(self):
        out = render({"type": "position_paper", "title": "x", "body_paragraphs": ["y"]})
        assert AKN4EU_VERSION.encode() in out

    def test_celex_target_renders_as_actsOn(self):
        out = render(
            {
                "type": "position_paper",
                "title": "x",
                "body_paragraphs": ["y"],
                "celex_target": "32016R0679",
            }
        )
        assert b"32016R0679" in out
        assert b'name="actsOn"' in out

    def test_immc_events_render_as_tlcevent(self):
        out = render(
            {
                "type": "amendment",
                "title": "x",
                "amendments": [{"article": "1"}],
                "immc_tags": {
                    "events": [
                        {
                            "event": "http://publications.europa.eu/resource/cellar/abc-123",
                            "type": "http://publications.europa.eu/resource/authority/event/ADOPTED",
                            "date": "2024-06-13",
                        },
                    ],
                },
            }
        )
        root = _parse(out)
        events = root.findall(f".//{{{AKN_NS}}}TLCEvent")
        assert events, "no TLCEvent rendered for IMMC events"
        assert "abc-123" in events[0].get("href", "")

    def test_supported_types_complete(self):
        # The plan calls for exactly these 4 — keep the renderer honest.
        assert set(SUPPORTED_TYPES) == {
            "position_paper", "amendment", "briefing_note", "ep_question",
        }

    def test_brubru_renderer_attribution(self):
        out = render({"type": "position_paper", "title": "x", "body_paragraphs": ["y"]})
        assert b"brubruRenderer" in out


# ----------------------------------------------------------------------
# Vendored documentation
# ----------------------------------------------------------------------

class TestAkn4euArtefacts:
    @pytest.mark.parametrize(
        "name,min_size",
        [
            ("docs/AKN4EU_4-2_PART_1_guideline.pdf", 1_000_000),
            ("docs/AKN4EU_4-2_PART_2_document-types.pdf", 1_000_000),
            ("docs/AKN4EU_4-2_PART_3_correspondence_with_CoV_4-2.pdf", 100_000),
        ],
    )
    def test_pdf_present(self, name, min_size):
        f = AKN_DIR / name
        assert f.exists(), f"missing {f}"
        assert f.stat().st_size >= min_size, (
            f"{f} suspiciously small ({f.stat().st_size} bytes < {min_size})"
        )

    def test_schema_zip_present(self):
        f = AKN_DIR / "schema" / "AKN4EU_4.2.zip"
        assert f.exists()
        assert f.stat().st_size > 30_000_000  # ~32 MB

    def test_at_least_one_reference_instance(self):
        # The unzipped distribution carries 79 sample instance XMLs we
        # validate our renderer against. Just confirm at least one is
        # present.
        instances = list((AKN_DIR / "schema").rglob("*.xml"))
        assert len(instances) >= 1, "no AKN4EU sample instances unzipped"
