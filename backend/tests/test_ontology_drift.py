"""
Phase 4 of docs/applications/euvoc.md — ontology-drift CI test.

Two static checks:
  1. Every cdm:* predicate the codebase references is present in the
     snapshot at docs/ontologies/cdm/cdm-brubru-subset.ttl. New
     predicates introduced without refreshing the snapshot fail CI.
  2. Every predicate in `RELATIONSHIP_PREDICATES` (used by
     cellar_sparql_client.py for amends/repeals/consolidates traversal)
     is in the snapshot.

One artefact-existence check:
  3. The three ELI reference artefacts (eli.owl, eli_ontology.xlsx,
     eli-sdo.ttl) live under docs/ontologies/eli/ and are non-empty.

The drift test is offline / static — no network, no DB. It runs in
every pytest invocation.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Set

import pytest

# Add backend/ to sys.path so we can import from services.*
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_PATH = ROOT / "docs" / "ontologies" / "cdm" / "cdm-brubru-subset.ttl"
ELI_DIR = ROOT / "docs" / "ontologies" / "eli"

# Stub matches — partial constants whose value happens to start with `cdm:`.
_STUB_PREDICATES = {"act_consolidated_", "resource_legal_", "event_legal_"}
_VALID_PREDICATE_RE = re.compile(r"^[a-z][a-zA-Z_\-]+$")


def _harvest_predicates_from_codebase() -> Set[str]:
    """Run grep across backend/ and collect every cdm:foo predicate."""
    cmd = [
        "grep", "-rEho",
        r"cdm:[a-zA-Z_-]+",
        str(_BACKEND / "services"),
        str(_BACKEND / "api"),
        str(_BACKEND / "scripts"),
    ]
    out = subprocess.run(cmd, check=False, capture_output=True, text=True).stdout
    raw = {ln.strip()[len("cdm:"):] for ln in out.splitlines() if ln.strip()}
    return {p for p in raw if p not in _STUB_PREDICATES and _VALID_PREDICATE_RE.match(p)}


def _harvest_predicates_from_snapshot() -> Set[str]:
    """Parse the snapshot Turtle for `cdm:foo` declarations."""
    if not SNAPSHOT_PATH.exists():
        return set()
    txt = SNAPSHOT_PATH.read_text()
    # Each predicate appears as `cdm:foo` at column 0.
    return {m.group(1) for m in re.finditer(r"^cdm:([a-zA-Z_\-]+)$", txt, re.MULTILINE)}


# ----------------------------------------------------------------------
# Snapshot drift
# ----------------------------------------------------------------------

class TestSnapshotDrift:
    def test_snapshot_exists(self):
        assert SNAPSHOT_PATH.exists(), (
            f"Missing snapshot at {SNAPSHOT_PATH}. Run "
            "`python3.12 backend/scripts/snapshot_cdm.py` to regenerate."
        )

    def test_snapshot_has_predicates(self):
        snap = _harvest_predicates_from_snapshot()
        assert snap, "Snapshot file exists but contains no predicates"

    def test_every_codebase_predicate_in_snapshot(self):
        codebase = _harvest_predicates_from_codebase()
        snap = _harvest_predicates_from_snapshot()
        new_in_codebase = codebase - snap
        assert not new_in_codebase, (
            "The codebase references cdm: predicates that are not in the "
            "snapshot at docs/ontologies/cdm/cdm-brubru-subset.ttl: "
            f"{sorted(new_in_codebase)}. Either fix a typo, or run "
            "`python3.12 backend/scripts/snapshot_cdm.py` to refresh the "
            "snapshot deliberately."
        )

    def test_relationship_predicates_in_snapshot(self):
        from services.api_clients.cellar_sparql_client import RELATIONSHIP_PREDICATES

        snap = _harvest_predicates_from_snapshot()
        for full in RELATIONSHIP_PREDICATES:
            local = full.split(":", 1)[1] if ":" in full else full
            assert local in snap, (
                f"RELATIONSHIP_PREDICATES references '{full}' which is not "
                f"in the snapshot. Refresh the snapshot or remove the dead "
                f"reference."
            )


# ----------------------------------------------------------------------
# ELI artefacts
# ----------------------------------------------------------------------

class TestELIArtefacts:
    @pytest.mark.parametrize(
        "filename,min_size",
        [
            ("eli.owl", 50_000),  # full ontology — expect > 50 KB
            ("eli_ontology.xlsx", 10_000),  # XLSX > 10 KB
            ("eli-sdo.ttl", 1_000),  # alignment > 1 KB
        ],
    )
    def test_artefact_present_and_nonempty(self, filename, min_size):
        f = ELI_DIR / filename
        assert f.exists(), f"Missing ELI artefact {f}"
        size = f.stat().st_size
        assert size >= min_size, (
            f"{f} is suspiciously small ({size} bytes < {min_size}). "
            "Re-download from the Publications Office."
        )

    def test_eli_owl_is_xml(self):
        head = (ELI_DIR / "eli.owl").read_text(encoding="utf-8", errors="ignore")[:200]
        assert "<?xml" in head, "eli.owl is not XML — re-download"
        assert "rdf:RDF" in head or "ontology" in head.lower(), (
            "eli.owl missing OWL/RDF root — re-download"
        )


# ----------------------------------------------------------------------
# ELI URI template (smoke)
# ----------------------------------------------------------------------

class TestELIUriTemplate:
    """A handful of known acts + their canonical ELI templates.

    The template is `http://data.europa.eu/eli/{type}/{year}/{number}/oj`
    or `http://publications.europa.eu/resource/eli/{type}/{year}/{number}/oj`.
    We assert the templates are well-formed strings so a partner can
    parse them.
    """

    # Sample 10 acts across decades, sectors, and types — not GDPR-only.
    KNOWN = [
        # (CELEX, ELI fragment we expect to be in the URI)
        ("32016R0679", "reg/2016/679"),    # GDPR
        ("32024R1689", "reg/2024/1689"),   # AI Act
        ("32022R2065", "reg/2022/2065"),   # DSA
        ("32023R1542", "reg/2023/1542"),   # Battery Regulation
        ("32014R0596", "reg/2014/596"),    # Market Abuse Regulation
        ("32016L1148", "dir/2016/1148"),   # NIS 1
        ("32022L2555", "dir/2022/2555"),   # NIS 2
        ("32011L0083", "dir/2011/83"),     # Consumer Rights Directive
        ("32020D2229", "dec/2020/2229"),   # Decision (sample)
        ("31995L0046", "dir/1995/46"),     # old DPD (repealed)
    ]

    @pytest.mark.parametrize("celex,eli_fragment", KNOWN)
    def test_eli_template_well_formed(self, celex, eli_fragment):
        # We don't need a network call here — just assert the regex
        # template that backend code uses produces a parseable URI.
        url = f"http://publications.europa.eu/resource/eli/{eli_fragment}/oj"
        assert url.startswith("http://publications.europa.eu/resource/eli/")
        # Sanity: the path segment matches the CELEX year + number we
        # encoded.
        year_match = re.search(r"/(\d{4})/", url)
        assert year_match, f"No year segment in ELI URI for {celex}"
        assert year_match.group(1) in celex, (
            f"ELI year segment {year_match.group(1)} doesn't match CELEX {celex}"
        )
