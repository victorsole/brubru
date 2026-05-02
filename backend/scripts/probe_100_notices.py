#!/usr/bin/env python3
"""
Probe 100 random EU acts to validate the FMX4 notice parser.

Pulls a real, deduplicated sample of CELEX numbers from Cellar SPARQL
(no hardcoded list, no guesses), fetches each notice, parses it, and
reports: languages, manifestation counts, format diversity, error rates,
and any structural anomalies.

Run:
    PYTHONPATH=backend python3.12 -m backend.scripts.probe_100_notices
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.api_clients.cellar_sparql_client import CellarSPARQLClient  # noqa: E402
from services.api_clients.fmx4_notice_parser import (  # noqa: E402
    fetch_notice,
    NoticeMetadata,
)

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("probe-100")
log.setLevel(logging.INFO)

SAMPLE_SIZE = 100
CONCURRENCY = 8


async def gather_sample_celex_numbers(target: int = SAMPLE_SIZE) -> List[str]:
    """Pull a real sample of CELEX numbers from Cellar SPARQL.

    Strategy: pick ~10x candidates across diverse sectors and years, then
    randomly down-sample to `target`. This avoids the head-of-list bias
    you'd get from a single ORDER BY DESC(?date) query.
    """
    end = date.today()
    pools: Dict[str, List[Dict[str, Any]]] = {}
    async with CellarSPARQLClient() as client:
        # Five overlapping windows so we get variety in age + structure
        windows = [
            (end - timedelta(days=30), end, ["3"], 200),     # very recent legislation
            (end - timedelta(days=180), end - timedelta(days=30), ["3"], 200),
            (date(2024, 1, 1), date(2024, 6, 30), ["3"], 200),
            (date(2020, 1, 1), date(2020, 12, 31), ["3"], 200),
            (date(2016, 1, 1), date(2016, 12, 31), ["3"], 200),
        ]
        for window_id, (a, b, sectors, lim) in enumerate(windows):
            rows = await client.discover_by_date_range(
                date_from=a, date_to=b, sectors=sectors, limit=lim
            )
            pools[f"window_{window_id}"] = rows
            log.info(f"  window {window_id}: {a.isoformat()} -> {b.isoformat()}: {len(rows)} candidates")

    # Flatten + dedupe by CELEX
    seen = set()
    unique_rows: List[Dict[str, Any]] = []
    for rows in pools.values():
        for r in rows:
            celex = r.get("celex")
            if celex and celex not in seen:
                seen.add(celex)
                unique_rows.append(r)

    log.info(f"Total unique CELEX candidates: {len(unique_rows)}")
    if len(unique_rows) < target:
        log.warning(f"Only {len(unique_rows)} unique candidates — using all")
        return [r["celex"] for r in unique_rows]

    random.seed(42)  # reproducible
    sampled = random.sample(unique_rows, target)
    return [r["celex"] for r in sampled]


async def fetch_one(celex: str, sem: asyncio.Semaphore) -> Dict[str, Any]:
    """Parse one notice and return a result dict for aggregation."""
    async with sem:
        try:
            # Corrigenda are skipped at the parser level (verified May 2026:
            # no standalone notice exists). Mark them as a separate skip class
            # so they don't drag down the parser's true success rate.
            if "R(" in celex and celex.endswith(")"):
                return {"celex": celex, "ok": False, "skipped": True, "reason": "corrigendum_no_notice"}
            meta = await fetch_notice(celex, timeout=30)
            return {
                "celex": celex,
                "ok": True,
                "parsed_celex": meta.celex,
                "celex_match": meta.celex == celex,
                "cellar_uri": meta.cellar_uri,
                "eli": meta.eli,
                "oj_reference": meta.oj_reference,
                "languages_count": len(meta.languages_available),
                "languages": meta.languages_available,
                "manifestation_count": len(meta.manifestations),
                "formats": sorted({m.format for m in meta.manifestations}),
                "titles_count": len(meta.titles),
                "has_eng_title": "ENG" in meta.titles,
                "has_fra_title": "FRA" in meta.titles,
                "has_spa_title": "SPA" in meta.titles,
                "has_eng_fmx4": meta.manifestation("ENG", "fmx4") is not None,
                "has_eng_xhtml": meta.manifestation("ENG", "xhtml") is not None,
                "has_eng_pdf": (
                    meta.manifestation("ENG", "pdfa1a") is not None
                    or meta.manifestation("ENG", "pdf") is not None
                ),
                # Pull a sample manifestation URL for the consolidated/repealed leak check
                "eng_xhtml_url": (
                    meta.manifestation("ENG", "xhtml").url
                    if meta.manifestation("ENG", "xhtml") is not None
                    else None
                ),
            }
        except Exception as e:
            return {
                "celex": celex,
                "ok": False,
                "error": str(e)[:200],
            }


async def main() -> int:
    log.info("Step 1 — gathering CELEX sample from Cellar SPARQL")
    celex_sample = await gather_sample_celex_numbers(SAMPLE_SIZE)
    log.info(f"  sampled: {len(celex_sample)} CELEX numbers")
    log.info(f"  first 5: {celex_sample[:5]}")

    log.info(f"Step 2 — fetching notices (concurrency={CONCURRENCY})")
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(fetch_one(c, sem) for c in celex_sample))

    # Aggregate
    ok = [r for r in results if r["ok"]]
    skipped = [r for r in results if not r["ok"] and r.get("skipped")]
    failed = [r for r in results if not r["ok"] and not r.get("skipped")]

    log.info("=" * 70)
    log.info(
        f"SUCCESS: {len(ok)}/{len(results)}  |  "
        f"SKIPPED (corrigenda): {len(skipped)}  |  "
        f"FAIL: {len(failed)}"
    )
    if len(ok) + len(skipped) > 0:
        rate = len(ok) / (len(ok) + len(failed)) if (len(ok) + len(failed)) else 0.0
        log.info(f"Parser success rate (excluding corrigenda): {rate:.1%}")

    if ok:
        # CELEX match
        celex_mismatches = [r for r in ok if not r["celex_match"]]
        log.info(f"CELEX parsed-vs-asked mismatch: {len(celex_mismatches)}")
        if celex_mismatches[:5]:
            for r in celex_mismatches[:5]:
                log.info(f"  asked={r['celex']}  parsed={r['parsed_celex']}")

        # Language coverage distribution
        lang_counts = Counter(r["languages_count"] for r in ok)
        log.info(f"Language-count distribution: {dict(sorted(lang_counts.items()))}")

        # Manifestation count distribution (bucketed)
        manif_buckets: Counter = Counter()
        for r in ok:
            n = r["manifestation_count"]
            if n == 0:
                manif_buckets["0"] += 1
            elif n < 24:
                manif_buckets["1-23"] += 1
            elif n <= 50:
                manif_buckets["24-50"] += 1
            elif n <= 100:
                manif_buckets["51-100"] += 1
            else:
                manif_buckets["100+"] += 1
        log.info(f"Manifestation count buckets: {dict(manif_buckets)}")

        # Format coverage
        all_formats: Counter = Counter()
        for r in ok:
            for f in r["formats"]:
                all_formats[f] += 1
        log.info(f"Format coverage (notices containing each format):")
        for fmt, n in all_formats.most_common():
            log.info(f"  {fmt:10s}  {n:4d} / {len(ok)}")

        # Title coverage
        with_eng = sum(1 for r in ok if r["has_eng_title"])
        with_spa = sum(1 for r in ok if r["has_spa_title"])
        log.info(f"English title present: {with_eng}/{len(ok)}")
        log.info(f"Spanish title present: {with_spa}/{len(ok)}")

        # FMX4 / XHTML availability for ENG
        eng_fmx = sum(1 for r in ok if r["has_eng_fmx4"])
        eng_xhtml = sum(1 for r in ok if r["has_eng_xhtml"])
        eng_pdf = sum(1 for r in ok if r["has_eng_pdf"])
        log.info(f"ENG FMX4 available:  {eng_fmx}/{len(ok)}")
        log.info(f"ENG XHTML available: {eng_xhtml}/{len(ok)}")
        log.info(f"ENG PDF available:   {eng_pdf}/{len(ok)}")

        # Embedded-notice leak check: is the ENG XHTML URL's CELEX in path
        # different from the asked CELEX? (Indicates we're harvesting from
        # an embedded sub-notice — the bug we found on GDPR.)
        leaks = []
        for r in ok:
            url = r.get("eng_xhtml_url") or ""
            celex = r["celex"]
            # If the URL is /resource/celex/{X}.ENG.xhtml and X != celex AND
            # X != one of the consolidated forms (e.g. starts with "0" + celex tail),
            # flag it.
            if "/resource/celex/" in url:
                in_url = url.split("/resource/celex/")[-1].split(".")[0]
                if in_url != celex:
                    # Allow consolidated form pattern: leading "0" + same year-tail
                    if not in_url.startswith("0"):
                        leaks.append((celex, in_url, url))
        log.info(f"Suspect embedded-notice URL leaks (ENG XHTML): {len(leaks)}")
        for c, in_url, url in leaks[:8]:
            log.info(f"  asked={c}  url-celex={in_url}  url={url}")

    if failed:
        log.info("---- failures (first 10) ----")
        for r in failed[:10]:
            log.info(f"  {r['celex']}: {r['error']}")

    # Persist for inspection
    out = ROOT / "audit" / "fmx4_notice_probe_100.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str))
    log.info(f"Full results -> {out.relative_to(ROOT)}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
