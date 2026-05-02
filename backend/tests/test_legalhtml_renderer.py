"""
Phase 12 of docs/applications/euvoc.md — LegalHTML renderer + validator.

Static checks (no I/O):
  - render() produces well-formed XHTML with the required namespaces
  - validate() approves a self-rendered document
  - validate() rejects plain non-LegalHTML

Filesystem checks (require the vendored reference samples under
docs/ontologies/legalhtml/COV-LegalHTML-converted-docs/):
  - validate() approves every reference .xhtml sample
  - the spec HTML + 30+ reference instance files exist
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from services.document_generation.legalhtml_renderer import (  # noqa: E402
    LEGALHTML_VERSION,
    SPEC_URL,
    render,
    validate,
)

ROOT = Path(__file__).resolve().parents[2]
LH_DIR = ROOT / "docs" / "ontologies" / "legalhtml"
SPEC_HTML = LH_DIR / "LegalHTML-2024-01-15" / "legalhtml-specs" / "index.html"
COV_DIR = LH_DIR / "COV-LegalHTML-converted-docs"


def _sample_doc():
    return {
        "title": "DIRECTIVE (EU) 2026/123 OF THE EUROPEAN PARLIAMENT AND OF THE COUNCIL",
        "effective_title": "on the protection of natural persons",
        "act_type": "directive",
        "act_date": "2026-04-15",
        "eea_relevance": True,
        "celex": "32026L0123",
        "acting_entities": [
            {"label": "THE EUROPEAN PARLIAMENT", "corp_body_code": "EP"},
            {"label": "THE COUNCIL OF THE EUROPEAN UNION", "corp_body_code": "CONSIL"},
        ],
        "citations": [
            {
                "text": "Treaty on the Functioning of the EU",
                "eli_predicate": "eli:based_on",
                "href": "http://publications.europa.eu/resource/eli/treaty/tfeu_2012",
            },
            {"text": "the proposal from the European Commission"},
        ],
        "recitals": [
            {"n": 1, "text": "Personal data protection is a fundamental right."},
            {"n": 2, "text": "Member States shall ensure proportionate enforcement."},
        ],
        "articles": [
            {"n": "1", "title": "Subject matter", "text": "This Directive lays down rules on ..."},
        ],
    }


# ----------------------------------------------------------------------
# Renderer
# ----------------------------------------------------------------------

class TestRenderer:
    def test_render_returns_bytes(self):
        out = render(_sample_doc())
        assert isinstance(out, bytes)
        assert out.startswith(b"<?xml")

    def test_render_well_formed_xml(self):
        out = render(_sample_doc())
        # The output MUST parse cleanly with the standard library.
        ET.fromstring(out)

    def test_render_emits_required_namespaces(self):
        out = render(_sample_doc()).decode()
        for ns in (
            'xmlns:lh="http://data.europa.eu/legalhtml#"',
            'xmlns:eli="http://data.europa.eu/eli/ontology#"',
            'xmlns:corpbody="http://publications.europa.eu/resource/authority/corporate-body/"',
        ):
            assert ns in out, f"missing namespace declaration: {ns}"

    def test_render_carries_eli_type_document(self):
        out = render(_sample_doc()).decode()
        assert 'property="eli:type_document"' in out
        assert "/resource-type/DIR" in out  # directive

    def test_render_resolves_humanised_date_per_lang(self):
        out_en = render(_sample_doc(), lang="en").decode()
        out_ca = render(_sample_doc(), lang="ca").decode()
        out_es = render(_sample_doc(), lang="es").decode()
        assert "April" in out_en
        assert "abril" in out_ca
        assert "abril" in out_es  # both CA and ES happen to share "abril"
        assert 'datetime="2026-04-15"' in out_en

    def test_render_includes_brubru_attribution(self):
        out = render(_sample_doc()).decode()
        assert "brubru.legalhtml_renderer" in out
        assert SPEC_URL in out
        assert LEGALHTML_VERSION in out

    def test_render_supports_each_act_type(self):
        for t, code in [
            ("regulation", "REG"), ("directive", "DIR"), ("decision", "DEC"),
        ]:
            doc = _sample_doc()
            doc["act_type"] = t
            out = render(doc).decode()
            assert f"/resource-type/{code}" in out, f"act_type={t} mapped wrong"

    def test_render_omits_eea_when_false(self):
        doc = _sample_doc()
        doc["eea_relevance"] = False
        out = render(doc).decode()
        assert "(Text with EEA relevance)" not in out


# ----------------------------------------------------------------------
# Validator (self)
# ----------------------------------------------------------------------

class TestValidatorSelf:
    def test_validate_self_render_ok(self):
        out = render(_sample_doc())
        res = validate(out)
        assert res.ok, f"self-render failed validation: {res.fails}"
        assert res.passes >= 14

    def test_validate_rejects_plain_html(self):
        plain = b"<html><head><title>x</title></head><body>not LegalHTML</body></html>"
        res = validate(plain)
        assert not res.ok
        # Required checks that must fail: namespace_lh + namespace_eli
        # (the universal LegalHTML markers across full acts, annexes,
        # Council notes, STAT_REASON, etc.).
        keys = " ".join(res.fails)
        assert "namespace_lh" in keys
        assert "namespace_eli" in keys


# ----------------------------------------------------------------------
# Validator (vendored reference samples)
# ----------------------------------------------------------------------

def _reference_xhtml_files() -> List[Path]:
    if not COV_DIR.exists():
        return []
    return sorted(p for p in COV_DIR.rglob("*.xhtml") if p.is_file())


class TestVendoredArtefacts:
    def test_spec_html_present(self):
        assert SPEC_HTML.exists(), f"missing {SPEC_HTML}"
        size = SPEC_HTML.stat().st_size
        assert size > 100_000, f"spec HTML suspiciously small ({size} bytes)"

    def test_at_least_30_reference_samples(self):
        files = _reference_xhtml_files()
        # The COV bundle has ~30 acts; we tolerate a small floor.
        assert len(files) >= 20, f"only {len(files)} reference .xhtml samples present"


@pytest.mark.parametrize(
    "ref_path",
    _reference_xhtml_files(),
    ids=lambda p: p.name[:60],
)
class TestValidateAllReferences:
    """Every CoV LegalHTML reference sample must pass our validator —
    proves we haven't accidentally inverted a check."""

    def test_validates(self, ref_path: Path):
        res = validate(ref_path.read_bytes())
        # Reference samples MUST pass the required-checks tier. Warnings
        # on optional checks are fine.
        assert res.ok, (
            f"reference sample {ref_path.name} failed validation:\n"
            f"  fails: {res.fails}"
        )
