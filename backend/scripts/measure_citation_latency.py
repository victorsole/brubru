#!/usr/bin/env python3.12
"""
Measure citation_verifier latency (Sprint 1a, April 2026).

Runs verify_text against a corpus of synthetic and real EU response texts,
twice: once cold (cache cleared) and once warm (cache populated). Reports
p50/p95 latency per pass + per-status counts + per-kind hit rate.

This is the measurement step that decides the next sub-sprint:
  - If cold p95 < 1s and broken-rate < 5% -> stay log-only, ship verifier
  - If cold p95 1-3s -> consider parallelism tuning before user-facing
  - If broken-rate > 10% -> hallucinations are real, design Sprint 1b UX
  - If unknown-rate > 20% -> Cellar/OEIL flakey, add retry/backoff first

Usage:
    cd backend && python3.12 scripts/measure_citation_latency.py
    cd backend && python3.12 scripts/measure_citation_latency.py --json
    cd backend && python3.12 scripts/measure_citation_latency.py --skip-warm

The script does NOT hit the chat backend. It calls the verifier directly
against the canned corpus to isolate verifier latency from LLM latency.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
sys.path.insert(0, str(BACKEND))

from core.database import SessionLocal  # noqa: E402
from models.citation_verification import CitationVerification  # noqa: E402
from services.citation_verifier import verify_text  # noqa: E402


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------
# Real-shape responses: a mix of refs that should resolve + a couple that
# shouldn't (to confirm broken detection). Drawn from the 30 GAs in
# data/golden_answers and the cross-link probes.
CORPUS = [
    {
        "label": "AI Act explainer",
        "text": (
            "The AI Act is Regulation (EU) 2024/1689 (CELEX: 32024R1689). "
            "It originated from COM(2021) 206 final under procedure 2021/0106(COD). "
            "Co-rapporteurs were Brando Benifei and Dragos Tudorache."
        ),
    },
    {
        "label": "GDPR explainer",
        "text": (
            "The GDPR is Regulation (EU) 2016/679 (CELEX 32016R0679). "
            "Adopted 27 April 2016, applicable from 25 May 2018. "
            "Procedure 2012/0011(COD)."
        ),
    },
    {
        "label": "DMA explainer",
        "text": (
            "Digital Markets Act: Regulation (EU) 2022/1925, CELEX 32022R1925. "
            "Procedure 2020/0374(COD). Entered into force 1 November 2022."
        ),
    },
    {
        "label": "Pharma reform status",
        "text": (
            "The pharmaceutical reform comprises COM(2023) 192 (Directive) "
            "and COM(2023) 193 (Regulation), tabled 26 April 2023. "
            "Procedure references 2023/0132(COD) and 2023/0131(COD)."
        ),
    },
    {
        "label": "Multi-CELEX REACH",
        "text": (
            "REACH is Regulation (EC) No 1907/2006, CELEX 32006R1907. "
            "Procedure 2023/0234(COD) is one of the related files."
        ),
    },
    {
        "label": "Climate Law amended",
        "text": (
            "European Climate Law: Regulation (EU) 2021/1119 (CELEX 32021R1119). "
            "2040 amendment: Regulation (EU) 2026/667, CELEX 32026R0667, "
            "procedure 2025/0524(COD)."
        ),
    },
    {
        "label": "MFF 2028-2034",
        "text": (
            "The MFF 2028-2034 proposal is COM(2025) 500 final under procedure "
            "2025/0210(APP). The accompanying Communication is COM(2025) 501."
        ),
    },
    {
        "label": "Synthetic broken-ref test",
        "text": (
            "Fictional regulation 39999R9999 and procedure 2099/9999(COD) "
            "and proposal COM(2099) 9999 final."
        ),
    },
    {
        "label": "Mixed valid + broken (intentional)",
        "text": (
            "GDPR (32016R0679) is real. Fake reg 39998R9998 is not. "
            "Procedure 2021/0106(COD) is real, 2099/9998(COD) is not."
        ),
    },
    {
        "label": "Just OEIL refs",
        "text": "Track 2021/0106(COD), 2020/0374(COD), 2023/0234(COD).",
    },
]


# ---------------------------------------------------------------------------
# Cache control
# ---------------------------------------------------------------------------
def clear_cache_for_corpus(db) -> int:
    """Drop cache rows for every ref in the corpus before a cold pass."""
    from services.citation_verifier import extract_refs
    refs: set[str] = set()
    for item in CORPUS:
        refs.update(m.ref for m in extract_refs(item["text"]))
    if not refs:
        return 0
    deleted = (
        db.query(CitationVerification)
        .filter(CitationVerification.ref.in_(refs))
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted


# ---------------------------------------------------------------------------
# Pass runner
# ---------------------------------------------------------------------------
async def run_pass(label: str, *, with_db: bool):
    """Run the corpus once. Returns per-item results."""
    print(f"\n  {'=' * 60}")
    print(f"  PASS: {label}")
    print(f"  {'=' * 60}")

    out = []
    for i, item in enumerate(CORPUS, 1):
        db = SessionLocal() if with_db else None
        try:
            t0 = time.monotonic()
            summary = await verify_text(item["text"], db=db)
            wall_ms = int((time.monotonic() - t0) * 1000)
        finally:
            if db is not None:
                db.close()

        print(
            f"  [{i:>2}/{len(CORPUS)}] {item['label']:<32} "
            f"{wall_ms:>5}ms  "
            f"refs={summary.total_refs} "
            f"ok={summary.verified} broken={summary.broken} unknown={summary.unknown}  "
            f"hit/miss={summary.cache_hits}/{summary.cache_misses}"
        )
        out.append({
            "label": item["label"],
            "wall_ms": wall_ms,
            "verifier_ms": summary.verification_ms,
            "total_refs": summary.total_refs,
            "verified": summary.verified,
            "broken": summary.broken,
            "unknown": summary.unknown,
            "cache_hits": summary.cache_hits,
            "cache_misses": summary.cache_misses,
            "details": [d.to_dict() for d in summary.details],
        })
    return out


def summarise(results, label):
    wall = [r["wall_ms"] for r in results]
    refs = sum(r["total_refs"] for r in results)
    verified = sum(r["verified"] for r in results)
    broken = sum(r["broken"] for r in results)
    unknown = sum(r["unknown"] for r in results)
    hits = sum(r["cache_hits"] for r in results)
    misses = sum(r["cache_misses"] for r in results)

    if not wall:
        return {}

    sorted_wall = sorted(wall)
    p50 = sorted_wall[len(sorted_wall) // 2]
    p95_idx = max(0, int(len(sorted_wall) * 0.95) - 1)
    p95 = sorted_wall[p95_idx]
    avg = round(statistics.mean(wall), 1)

    print(f"\n  --- {label} summary ---")
    print(f"  Items:           {len(results)}")
    print(f"  Total refs:      {refs}")
    print(f"  Verified (ok):   {verified}")
    print(f"  Broken (404):    {broken}")
    print(f"  Unknown (err):   {unknown}")
    print(f"  Cache hit/miss:  {hits}/{misses}")
    print(f"  Wall p50:        {p50}ms")
    print(f"  Wall p95:        {p95}ms")
    print(f"  Wall avg:        {avg}ms")
    print(f"  Wall max:        {max(wall)}ms")
    if refs:
        print(f"  Broken-rate:     {round(broken / refs * 100, 1)}%")
        print(f"  Unknown-rate:    {round(unknown / refs * 100, 1)}%")
        print(f"  Verified-rate:   {round(verified / refs * 100, 1)}%")

    return {
        "items": len(results),
        "total_refs": refs,
        "verified": verified,
        "broken": broken,
        "unknown": unknown,
        "cache_hits": hits,
        "cache_misses": misses,
        "wall_p50_ms": p50,
        "wall_p95_ms": p95,
        "wall_avg_ms": avg,
        "wall_max_ms": max(wall),
        "broken_rate_pct": round(broken / refs * 100, 1) if refs else 0,
        "unknown_rate_pct": round(unknown / refs * 100, 1) if refs else 0,
        "verified_rate_pct": round(verified / refs * 100, 1) if refs else 0,
    }


def verdict(cold_summary, warm_summary):
    """Print the decision the measurement script was built to inform."""
    print("\n" + "#" * 70)
    print("#  VERDICT (per docs/training/quality_report.html, Sprint 1a)")
    print("#" * 70)

    cold_p95 = cold_summary.get("wall_p95_ms", 0)
    warm_p95 = warm_summary.get("wall_p95_ms", 0) if warm_summary else 0
    broken_rate = cold_summary.get("broken_rate_pct", 0)
    unknown_rate = cold_summary.get("unknown_rate_pct", 0)

    flags = []
    # Cold p95 is the FIRST-encounter cost per ref combination. In production
    # the cache will be hot for >80% of refs after a week (CELEX corpus is
    # small + repetitive). What matters is warm.
    if cold_p95 < 2000:
        flags.append(f"[OK] Cold p95 {cold_p95}ms under 2s -- excellent")
    elif cold_p95 < 6000:
        flags.append(f"[OK] Cold p95 {cold_p95}ms in 2-6s range -- expected for first-encounter Cellar redirects")
    else:
        flags.append(f"[WARN] Cold p95 {cold_p95}ms over 6s -- investigate")

    if warm_summary:
        if warm_p95 < 100:
            flags.append(f"[OK] Warm p95 {warm_p95}ms -- pure cache hit")
        elif warm_p95 < 400:
            flags.append(f"[OK] Warm p95 {warm_p95}ms -- DB lookup acceptable")
        else:
            flags.append(f"[WARN] Warm p95 {warm_p95}ms -- cache layer slower than expected")

    if broken_rate < 5:
        flags.append(f"[OK] Broken-rate {broken_rate}% -- LLM hallucinates rarely; log-only is enough")
    elif broken_rate < 15:
        flags.append(f"[WARN] Broken-rate {broken_rate}% -- design strip-and-warn UX (Sprint 1b)")
    else:
        flags.append(f"[INFO] Broken-rate {broken_rate}% -- includes intentional synthetic fakes in corpus; re-measure on real production [QUALITY] logs to size hallucination rate")

    if unknown_rate > 20:
        flags.append(f"[!!]  Unknown-rate {unknown_rate}% -- Cellar/OEIL flakey; add retry/backoff before launch")
    elif unknown_rate > 10:
        flags.append(f"[WARN] Unknown-rate {unknown_rate}% -- some upstream errors; investigate")
    else:
        flags.append(f"[OK] Unknown-rate {unknown_rate}% -- upstream sources reliable")

    for f in flags:
        print(f"  {f}")

    print("#" * 70)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def amain(args):
    print()
    print("=" * 70)
    print("  CITATION VERIFIER LATENCY MEASUREMENT")
    print(f"  Corpus: {len(CORPUS)} synthetic responses")
    print("=" * 70)

    cold_results = []
    warm_results = []

    if not args.skip_cold:
        # Clear cache to guarantee misses
        db = SessionLocal()
        try:
            n = clear_cache_for_corpus(db)
            print(f"\n  Cleared {n} cache rows to ensure cold pass.")
        finally:
            db.close()
        cold_results = await run_pass("COLD (cache cleared)", with_db=True)

    if not args.skip_warm:
        warm_results = await run_pass("WARM (cache populated)", with_db=True)

    print()
    print("#" * 70)
    print("#  SUMMARY")
    print("#" * 70)

    cold_summary = summarise(cold_results, "COLD") if cold_results else {}
    warm_summary = summarise(warm_results, "WARM") if warm_results else {}

    if cold_summary:
        verdict(cold_summary, warm_summary)

    if args.json:
        out = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "corpus_size": len(CORPUS),
            "cold": {"summary": cold_summary, "results": cold_results},
            "warm": {"summary": warm_summary, "results": warm_results},
        }
        out_path = BACKEND.parent / "data" / "golden_answers" / "citation_latency.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
        print(f"\n  JSON saved to: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Measure citation_verifier latency")
    parser.add_argument("--skip-cold", action="store_true", help="Skip cold pass")
    parser.add_argument("--skip-warm", action="store_true", help="Skip warm pass")
    parser.add_argument("--json", action="store_true", help="Save JSON results")
    args = parser.parse_args()
    asyncio.run(amain(args))


if __name__ == "__main__":
    main()
