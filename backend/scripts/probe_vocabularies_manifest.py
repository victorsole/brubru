#!/usr/bin/env python3
"""
Probe every dataset URI in data/eu_vocabularies/manifest.yaml.

For each entry that has a `uri` and is targeting the Cellar SPARQL endpoint,
ask the live endpoint how many skos:Concept rows belong to the dataset and
write the count back into the manifest as `live_concept_count`.

Run from repo root:
    python3.12 backend/scripts/probe_vocabularies_manifest.py

Optional flags:
    --dry-run   Print counts but do not modify the manifest.
    --section   Restrict probing to a specific top-level section
                (e.g. nal_hot_twelve, nal_long_tail, ontologies).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import yaml  # PyYAML

from services.api_clients.base_sparql_client import BaseSPARQLClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("probe-manifest")

MANIFEST_PATH = ROOT / "data" / "eu_vocabularies" / "manifest.yaml"
SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
CONCURRENCY = 4

# Sections in the manifest that contain probable dataset URIs.
SECTIONS_WITH_URIS = (
    "nal_hot_twelve",
    "already_integrated",
    "ontologies",
    "schemas",
    "phase_5_to_9",
    "parked",
    "nal_long_tail",
)


# Datasets that don't follow the `.../resource/authority/{name}/...` concept-IRI
# convention. Probed via a custom IRI prefix instead. Empty list means "use
# the default authority/{name}/ pattern".
_CONCEPT_IRI_OVERRIDES = {
    # EuroVoc has its own namespace (verified live, May 2026: 7,523 concepts).
    "eurovoc": "http://eurovoc.europa.eu/",
}

# Entries that are NOT SKOS concept lists (schemas, ontologies, application
# profiles, restricted-internal lists). The probe still fires but we tag the
# result so the manifest carries a meaningful "n/a" reason instead of "0".
_NOT_SKOS_KEYS = {
    # Application profiles / schemas — no SKOS concepts under /resource/authority/.
    "immc", "det", "ojeep", "op-core-metadata", "dcat-ap",
    # Commission-internal NALs — not exposed in the public graph.
    "com-internal-consultation-type", "com-internal-event", "com-internal-procedure",
}


def _count_query_for(entry: Dict[str, Any]) -> Optional[str]:
    """Return the SPARQL count query for one manifest entry, or None if the
    entry has no probable URI."""
    key = entry.get("key", "")
    dataset_uri = entry.get("uri")
    if not dataset_uri or not dataset_uri.startswith("http://publications.europa.eu/resource/dataset/"):
        return None
    iri_prefix = _CONCEPT_IRI_OVERRIDES.get(key)
    if iri_prefix is None:
        name = dataset_uri.rstrip("/").rsplit("/", 1)[-1]
        iri_prefix = f"http://publications.europa.eu/resource/authority/{name}/"
    return f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT (COUNT(DISTINCT ?c) AS ?n) WHERE {{
            ?c a skos:Concept .
            FILTER(STRSTARTS(STR(?c), "{iri_prefix}"))
        }}
    """


async def probe_one(
    client: BaseSPARQLClient,
    entry: Dict[str, Any],
    sem: asyncio.Semaphore,
) -> Tuple[str, Optional[int], Optional[str]]:
    """Probe a single entry. Returns (key, count|None, error|None)."""
    key = entry.get("key", "?")
    query = _count_query_for(entry)
    if query is None:
        return (key, None, "skipped (no dataset URI)")

    async with sem:
        try:
            results = await client.select(query)
            if results and results[0].get("n"):
                count = int(results[0]["n"])
                return (key, count, None)
            return (key, 0, None)
        except Exception as e:
            return (key, None, f"{type(e).__name__}: {str(e)[:160]}")


async def main(dry_run: bool, section_filter: Optional[str]) -> int:
    raw = MANIFEST_PATH.read_text()
    manifest = yaml.safe_load(raw)

    # Collect entries to probe
    entries: List[Tuple[str, int, Dict[str, Any]]] = []
    for section in SECTIONS_WITH_URIS:
        if section_filter and section != section_filter:
            continue
        items = manifest.get(section) or []
        if not isinstance(items, list):
            continue
        for idx, item in enumerate(items):
            entries.append((section, idx, item))

    log.info(f"Probing {len(entries)} manifest entries against {SPARQL_ENDPOINT}")

    sem = asyncio.Semaphore(CONCURRENCY)
    client = BaseSPARQLClient(SPARQL_ENDPOINT, timeout=120)
    try:
        results = await asyncio.gather(
            *(probe_one(client, item, sem) for _, _, item in entries)
        )
    finally:
        await client.close()

    # Apply results back into manifest
    ok = 0
    empty = 0
    failed = 0
    skipped = 0
    for (section, idx, item), (key, count, err) in zip(entries, results):
        if err == "skipped (no dataset URI)":
            skipped += 1
            continue
        if err:
            failed += 1
            log.warning(f"  {key:42s}  ERROR  {err}")
            manifest[section][idx]["live_concept_count"] = None
            manifest[section][idx]["live_probe_error"] = err
            continue
        if count == 0:
            empty += 1
            if key in _NOT_SKOS_KEYS:
                log.info(f"  {key:42s}  N/A    (not a SKOS list — application profile / restricted)")
                manifest[section][idx]["live_concept_count"] = None
                manifest[section][idx]["live_probe_status"] = "not_skos_or_restricted"
            else:
                log.warning(f"  {key:42s}  EMPTY  (live_concept_count=0 — review)")
                manifest[section][idx]["live_concept_count"] = 0
                manifest[section][idx]["live_probe_status"] = "empty"
        else:
            ok += 1
            log.info(f"  {key:42s}  {count:>8d}")
            manifest[section][idx]["live_concept_count"] = count
            manifest[section][idx].pop("live_probe_status", None)
        manifest[section][idx].pop("live_probe_error", None)

    manifest["last_probed"] = datetime.now(timezone.utc).isoformat()

    log.info("=" * 70)
    log.info(
        f"OK: {ok}  |  EMPTY: {empty}  |  FAILED: {failed}  |  SKIPPED: {skipped}"
    )

    if dry_run:
        log.info("--dry-run: manifest NOT written")
        return 0 if failed == 0 else 1

    MANIFEST_PATH.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=120)
    )
    log.info(f"Manifest updated -> {MANIFEST_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Probe vocabulary manifest URIs")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--section", default=None, help=f"Limit to one section: {SECTIONS_WITH_URIS}")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.dry_run, args.section)))
