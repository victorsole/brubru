#!/usr/bin/env python3
"""
Phase 1 nightly sync — pull skos:prefLabel + skos:altLabel for every
concept in the 12 hot NALs (data/eu_vocabularies/manifest.yaml) in the
6 Brubru languages, upsert into eu_authority_labels.

Run from repo root:
    python3.12 backend/scripts/sync_eu_authority_labels.py

Flags:
    --nal KEY     Restrict to one NAL (e.g. corporate-body)
    --lang CODE   Restrict to one language (en|fr|es|ca|it|nl)
    --force       Re-fetch even if a row exists (default: idempotent upsert)
    --dry-run     Print counts but do not write
    --limit N     Cap concepts per NAL (default: all)

Idempotent: re-running yields the same DB state. Safe to schedule
nightly via cron.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

import yaml

from core.database import SessionLocal  # noqa: E402
from services.api_clients.base_sparql_client import BaseSPARQLClient  # noqa: E402
from services.vocabularies.authority_label_cache import AuthorityLabelCache  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("sync-auth-labels")

MANIFEST_PATH = ROOT / "data" / "eu_vocabularies" / "manifest.yaml"
SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"

BRUBRU_LANGS = ("en", "fr", "es", "ca", "it", "nl")


def _label_query(dataset_uri: str, lang: str, limit: Optional[int] = None) -> str:
    """SPARQL to pull concepts + prefLabel + altLabels for one NAL in one lang.

    EU Vocabularies SKOS uses 2-letter ISO-639 lang tags on labels.
    """
    name = dataset_uri.rstrip("/").rsplit("/", 1)[-1]
    iri_prefix = f"http://publications.europa.eu/resource/authority/{name}/"
    if name == "eurovoc":
        iri_prefix = "http://eurovoc.europa.eu/"
    limit_clause = f"LIMIT {limit}" if limit else ""

    return f"""
        PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
        SELECT ?c ?pref (GROUP_CONCAT(DISTINCT ?alt; separator="||") AS ?alts) WHERE {{
            ?c a skos:Concept .
            FILTER(STRSTARTS(STR(?c), "{iri_prefix}"))
            ?c skos:prefLabel ?pref .
            FILTER(LANG(?pref) = "{lang}")
            OPTIONAL {{
                ?c skos:altLabel ?alt .
                FILTER(LANG(?alt) = "{lang}")
            }}
        }}
        GROUP BY ?c ?pref
        {limit_clause}
    """


async def fetch_one_nal_lang(
    client: BaseSPARQLClient,
    dataset_uri: str,
    lang: str,
    limit: Optional[int],
) -> List[Dict[str, Any]]:
    """Fetch all (uri, pref, alts) rows for one NAL in one language."""
    rows = await client.select(_label_query(dataset_uri, lang, limit))
    out: List[Dict[str, Any]] = []
    for r in rows:
        uri = r.get("c")
        pref = r.get("pref")
        if not uri or not pref:
            continue
        alts_concat = r.get("alts") or ""
        alts = [a.strip() for a in alts_concat.split("||") if a.strip()]
        out.append({"uri": uri, "pref": pref, "alts": alts})
    return out


def _hot_twelve(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [e for e in (manifest.get("nal_hot_twelve") or []) if e.get("enabled")]


async def run(
    nal_filter: Optional[str],
    lang_filter: Optional[str],
    force: bool,
    dry_run: bool,
    limit: Optional[int],
) -> int:
    manifest = yaml.safe_load(MANIFEST_PATH.read_text())
    nals = _hot_twelve(manifest)
    if nal_filter:
        nals = [n for n in nals if n["key"] == nal_filter]
    if not nals:
        log.error(f"No NALs to sync (filter: {nal_filter or 'none'})")
        return 1

    langs: Sequence[str] = (lang_filter,) if lang_filter else BRUBRU_LANGS
    log.info(f"Syncing {len(nals)} NALs × {len(langs)} languages (force={force}, dry_run={dry_run})")

    sparql = BaseSPARQLClient(SPARQL_ENDPOINT, timeout=120)
    db = SessionLocal()
    cache = AuthorityLabelCache(db)

    total_rows = 0
    total_upserts = 0
    total_skipped = 0
    failures: List[str] = []

    try:
        for nal in nals:
            ds_uri = nal["uri"]
            ds_key = nal["key"]
            log.info(f"  [{ds_key}]")
            for lang in langs:
                try:
                    rows = await fetch_one_nal_lang(sparql, ds_uri, lang, limit)
                except Exception as e:  # noqa: BLE001
                    failures.append(f"{ds_key}/{lang}: {type(e).__name__}: {e}")
                    log.warning(f"    {lang}: SPARQL failed: {e}")
                    continue

                total_rows += len(rows)
                log.info(f"    {lang}: {len(rows)} concepts")

                if dry_run:
                    continue

                # Upsert
                for row in rows:
                    cache.upsert(
                        uri=row["uri"],
                        lang=lang,
                        pref_label=row["pref"],
                        alt_labels=row["alts"],
                        source_dataset_uri=ds_uri,
                    )
                    total_upserts += 1
                db.commit()

        log.info("=" * 70)
        log.info(
            f"DONE  rows={total_rows}  upserts={total_upserts}  failures={len(failures)}"
        )
        if failures:
            for f in failures[:10]:
                log.warning(f"  FAIL  {f}")
            return 1
        return 0
    finally:
        await sparql.close()
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 1 EU authority-label sync")
    parser.add_argument("--nal", default=None)
    parser.add_argument("--lang", default=None, choices=BRUBRU_LANGS)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.nal, args.lang, args.force, args.dry_run, args.limit)))
