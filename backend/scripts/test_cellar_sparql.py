#!/usr/bin/env python3
"""
Smoke test for cellar_sparql_client.py

Run from repo root:
    python3 -m backend.scripts.test_cellar_sparql

Tests:
  1. Endpoint health
  2. discover_by_date_range over the last 30 days
  3. get_celex_metadata for GDPR (32016R0679)
  4. get_eli for GDPR
  5. get_related_acts for GDPR
  6. get_available_languages for GDPR
  7. get_force_status for a known repealed act (31995L0046 = old Data Protection Directive)
  8. count_by_year for sector 3 in 2024
"""

import asyncio
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

# Allow running as a script
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("cellar-test")


async def main() -> int:
    failures = 0
    async with CellarSPARQLClient(timeout=120) as client:
        # 1. Health
        log.info("[1/8] Endpoint health check")
        ok = await client.is_healthy()
        log.info(f"      health: {ok}")
        if not ok:
            failures += 1

        # 2. Date range
        log.info("[2/8] discover_by_date_range last 30 days")
        end = date.today()
        start = end - timedelta(days=30)
        results = await client.discover_by_date_range(
            date_from=start, date_to=end, sectors=["3"], limit=10
        )
        log.info(f"      found {len(results)} acts. First 3:")
        for r in results[:3]:
            log.info(f"        - {r.get('celex')} ({r.get('date')}) {r.get('title','')[:80]}")
        if len(results) == 0:
            log.warning("      WARN: 0 results — this is suspicious; check filter")

        # 3. GDPR metadata
        log.info("[3/8] get_celex_metadata(32016R0679 = GDPR)")
        meta = await client.get_celex_metadata("32016R0679")
        if meta:
            log.info(f"      title: {(meta.get('title') or '')[:120]}")
            log.info(f"      date:  {meta.get('date')}")
            log.info(f"      type:  {meta.get('type')}")
            log.info(f"      eli:   {meta.get('eli')}")
        else:
            log.error("      FAIL: no metadata for GDPR")
            failures += 1

        # 4. ELI
        log.info("[4/8] get_eli(32016R0679)")
        eli = await client.get_eli("32016R0679")
        log.info(f"      eli: {eli}")
        if not eli:
            log.warning("      WARN: ELI not returned (older acts may lack ELI)")

        # 5. Related acts
        log.info("[5/8] get_related_acts(32016R0679)")
        rel = await client.get_related_acts("32016R0679")
        log.info(f"      {len(rel)} related acts")
        for r in rel[:5]:
            log.info(f"        - {r.get('relation','').split('#')[-1]}: {r.get('relatedCelex')}")

        # 6. Languages
        log.info("[6/8] get_available_languages(32016R0679)")
        langs = await client.get_available_languages("32016R0679")
        log.info(f"      {len(langs)} languages: {sorted(langs)[:12]}...")
        if len(langs) < 20:
            log.warning("      WARN: GDPR should be available in ~24 languages")

        # 7. Force status
        log.info("[7/8] get_force_status(31995L0046 = old Data Protection Directive, repealed)")
        fs = await client.get_force_status("31995L0046")
        log.info(f"      in_force={fs['in_force']} end_validity={fs['date_end_validity']}")

        # 8. Count
        log.info("[8/8] count_by_year(2024, sector=3)")
        n = await client.count_by_year(2024, sector="3")
        log.info(f"      sector-3 acts dated 2024: {n}")

        log.info(f"Cache stats: {client.get_cache_stats()}")

    log.info(f"DONE — failures: {failures}")
    return failures


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
