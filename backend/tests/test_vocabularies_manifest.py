"""
Phase 0 of docs/applications/euvoc.md — manifest sanity tests.

Two test suites:
  1. Static structural checks on data/eu_vocabularies/manifest.yaml
     (no network — runs in unit-test mode).
  2. Optional live-probe assertion that every "enabled" entry with a
     dataset URI has live_concept_count > 0. Marked with @pytest.mark.live
     so CI can opt out.

Migration round-trip is covered separately (see test_migration_048_eu_vocabularies.py).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = ROOT / "data" / "eu_vocabularies" / "manifest.yaml"

# Sections that contain manifest entries (top-level YAML keys).
ENTRY_SECTIONS = (
    "nal_hot_twelve",
    "already_integrated",
    "ontologies",
    "schemas",
    "phase_5_to_9",
    "parked",
    "nal_long_tail",
)


@pytest.fixture(scope="module")
def manifest() -> Dict[str, Any]:
    return yaml.safe_load(MANIFEST_PATH.read_text())


def _all_entries(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for section in ENTRY_SECTIONS:
        for item in manifest.get(section) or []:
            if isinstance(item, dict):
                item["_section"] = section
                out.append(item)
    return out


# ----------------------------------------------------------------------
# Structural checks (offline)
# ----------------------------------------------------------------------

def test_manifest_exists():
    assert MANIFEST_PATH.exists(), f"manifest missing at {MANIFEST_PATH}"


def test_manifest_has_required_top_level_keys(manifest):
    for k in ("version", "created", "nal_hot_twelve", "already_integrated"):
        assert k in manifest, f"manifest is missing top-level key '{k}'"


def test_hot_twelve_count(manifest):
    """Phase 1 promises exactly 12 hot NALs in the nightly sync."""
    hot = manifest.get("nal_hot_twelve") or []
    assert len(hot) == 12, f"nal_hot_twelve must have 12 entries, found {len(hot)}"


def test_every_entry_has_a_key(manifest):
    for entry in _all_entries(manifest):
        assert entry.get("key"), f"entry missing 'key' in section {entry['_section']}: {entry}"


def test_keys_unique_within_section(manifest):
    for section in ENTRY_SECTIONS:
        items = manifest.get(section) or []
        keys = [i.get("key") for i in items if isinstance(i, dict)]
        assert len(keys) == len(set(keys)), (
            f"duplicate keys in section '{section}': "
            f"{[k for k in keys if keys.count(k) > 1]}"
        )


def test_dataset_uris_use_canonical_namespace(manifest):
    """Every entry that has a `uri` field must point at the Publications
    Office /resource/dataset/ namespace (DCAT-AP-style entries are exempt
    because they declare a `namespace` instead)."""
    bad = []
    for entry in _all_entries(manifest):
        uri = entry.get("uri")
        if not uri:
            continue
        if not (
            uri.startswith("http://publications.europa.eu/resource/dataset/")
            or uri.startswith("http://data.europa.eu/")
        ):
            bad.append((entry["_section"], entry["key"], uri))
    assert not bad, f"non-canonical URIs: {bad}"


def test_hot_twelve_all_enabled(manifest):
    """The hot twelve are by definition enabled for the Phase 1 nightly sync."""
    for entry in manifest["nal_hot_twelve"]:
        assert entry.get("enabled") is True, f"{entry['key']} must have enabled: true"


def test_hot_twelve_languages_cover_six_brubru_langs(manifest):
    expected = {"en", "fr", "es", "ca", "it", "nl"}
    for entry in manifest["nal_hot_twelve"]:
        langs = set(entry.get("languages") or [])
        missing = expected - langs
        assert not missing, f"{entry['key']} missing languages: {missing}"


def test_no_entry_carries_only_concept_count_zero_without_status(manifest):
    """If a probe returned 0, the manifest must explain why
    (live_probe_status: empty | not_skos_or_restricted)."""
    for entry in _all_entries(manifest):
        if entry.get("live_concept_count") == 0:
            assert entry.get("live_probe_status"), (
                f"entry {entry['key']} has live_concept_count=0 but no live_probe_status"
            )


def test_eurovoc_count_in_expected_range(manifest):
    """EuroVoc should report between 7,000 and 8,500 concepts (4.23 has 7,523)."""
    eurovoc = next(
        (e for e in manifest.get("already_integrated") or [] if e.get("key") == "eurovoc"),
        None,
    )
    assert eurovoc is not None, "EuroVoc entry missing"
    n = eurovoc.get("live_concept_count")
    assert n is not None, "EuroVoc has not been live-probed yet (run probe_vocabularies_manifest.py)"
    assert 7000 <= n <= 8500, f"EuroVoc count out of expected range: {n}"


# ----------------------------------------------------------------------
# Live probe (network)
# ----------------------------------------------------------------------

@pytest.mark.live
def test_hot_twelve_all_have_positive_live_count(manifest):
    """Each hot NAL must have a positive live count after probe_vocabularies_manifest.py."""
    for entry in manifest["nal_hot_twelve"]:
        n = entry.get("live_concept_count")
        assert n is not None, (
            f"{entry['key']} not yet probed — run "
            f"`python3.12 backend/scripts/probe_vocabularies_manifest.py`"
        )
        assert n > 0, f"{entry['key']} has live_concept_count={n} (expected > 0)"


@pytest.mark.live
def test_long_tail_uses_status_for_zero_counts(manifest):
    """Long-tail NALs that probe at 0 must have a status field."""
    for entry in manifest.get("nal_long_tail") or []:
        if entry.get("live_concept_count") == 0:
            assert entry.get("live_probe_status") in {"empty", "not_skos_or_restricted"}, (
                f"{entry['key']} probed 0 with no live_probe_status"
            )
