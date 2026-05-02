"""
Phase 9 of docs/applications/euvoc.md — OJEEP-style validator tests.

Static (no I/O): a synthetic minimal OJ-shaped HTML passes; a broken
fixture fails with the expected check keys.

Filesystem (no network): when the Catalan corpus is on disk, the
validator runs cleanly across every CELEX-shaped subdirectory.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Pull the validator module directly via importlib since scripts/ isn't a package.
import importlib.util

ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = ROOT / "backend" / "scripts" / "validate_catalan_against_ojeep.py"
spec = importlib.util.spec_from_file_location("ojeep_validator", SCRIPT_PATH)
mod = importlib.util.module_from_spec(spec)
# Register in sys.modules BEFORE exec so @dataclass can resolve __module__.
sys.modules["ojeep_validator"] = mod
spec.loader.exec_module(mod)  # type: ignore[union-attr]


# ----------------------------------------------------------------------
# Static structural checks
# ----------------------------------------------------------------------

_GOOD_HTML = """
<!DOCTYPE html>
<html lang="ca">
<head>
  <title>Reglament test</title>
  <meta name="description" content="x">
</head>
<body>
  <div class="disclaimer-banner">disclaimer</div>
  <div class="doc-header"><h1>title</h1></div>
  <div class="preamble-init">EL CONSELL</div>
  <p class="visa">vist el tractat</p>
  <p class="recital">considerant</p>
  <div class="preamble-final">HA ADOPTAT</div>
  <div class="article">
    <div class="article-title">Article 1</div>
    <p class="article-text">x</p>
  </div>
  <div class="final-block">final</div>
  <div class="footer">brubru</div>
</body>
</html>
"""

_BROKEN_HTML = """
<html><head><title>x</title></head><body>nothing OJ-shaped</body></html>
"""


class TestStructuralValidator:
    def test_good_html_passes(self):
        res = mod._validate_html(_GOOD_HTML, celex="32099X9999", path="x")
        assert res.ok, f"unexpected fails: {res.fails}"
        assert res.passes >= 11  # core checks all hit

    def test_broken_html_fails(self):
        res = mod._validate_html(_BROKEN_HTML, celex="brk", path="b")
        assert not res.ok
        # Required checks that should fail: doc_header, articles_present, article_title_present.
        keys = " ".join(res.fails)
        assert "doc_header" in keys
        assert "articles_present" in keys
        assert "article_title_present" in keys

    def test_emit_xml_round_trip(self):
        xml = mod.emit_xml_for_act(_GOOD_HTML, "32099X9999")
        assert xml.startswith("<?xml")
        assert "<celex>32099X9999</celex>" in xml
        assert "<recital n=\"1\">" in xml
        assert "<article n=\"1\">" in xml

    def test_xml_well_formed(self):
        import xml.etree.ElementTree as ET

        xml = mod.emit_xml_for_act(_GOOD_HTML, "32099X9999")
        root = ET.fromstring(xml)
        assert root.tag.endswith("ojeepAct")


# ----------------------------------------------------------------------
# CELEX shape filter
# ----------------------------------------------------------------------

class TestCELEXFilter:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("32016R0679", True),
            ("32024R1689", True),
            ("32019D1194", True),
            ("eu-andorra", False),
            ("README", False),
            ("32016R0679-softcatala", True),  # variant suffix tolerated (split('-')[0])
        ],
    )
    def test_celex_pattern(self, name, expected):
        celex_candidate = name.split("-", 1)[0]
        assert bool(mod._CELEX_RE.match(celex_candidate)) == expected


# ----------------------------------------------------------------------
# Filesystem (skipped if corpus missing)
# ----------------------------------------------------------------------

class TestLiveCorpus:
    def test_validator_cli_against_real_corpus(self):
        catalan_dir = ROOT / "frontend" / "public" / "legislacio-ue-catala"
        if not catalan_dir.exists():
            pytest.skip("Catalan corpus not present")
        # Spot-check: at least one CELEX-named subdirectory has an index.html.
        celex_dirs = [
            p for p in catalan_dir.iterdir()
            if p.is_dir() and mod._CELEX_RE.match(p.name.split("-", 1)[0])
        ]
        if not celex_dirs:
            pytest.skip("No CELEX-shaped Catalan acts on disk")

        cmd = ["python3.12", str(SCRIPT_PATH)]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=120)
        # Validator exits 0 if all CELEX-shaped acts pass.
        assert result.returncode == 0, (
            f"validator exit={result.returncode}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
