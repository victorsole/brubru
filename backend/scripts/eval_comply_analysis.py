"""Score the EU Law Comply gap analyser against a labelled gold set.

Why this exists
---------------
Until now the analyser's accuracy was an anecdote: one run, one finding read
closely, "looks right". Worse, three runs of the SAME cluster against the SAME
document produced compliance scores of 13.51%, 16.22% and 16.67% -- so the
run-to-run noise was wider than most improvements would be, and no change
could be shown to help or hurt.

This harness reports two things:

  ACCURACY  how often the verdict matches a human label, exactly and on the
            decision that actually matters (does this need action or not)
  STABILITY how often repeated runs of the SAME case agree with each other

Stability is the headline number for a compliance product. A tool that is 70%
accurate and always says the same thing is auditable. One that is 70% accurate
and disagrees with itself is not, whatever its average.

The unit under test is GapAnalyzer._analyze_requirement -- the actual decision
-- rather than a whole run, so cases are addressable and repeats are cheap.

Usage (from backend/):
  python3.12 -m scripts.eval_comply_analysis --runs 3
  python3.12 -m scripts.eval_comply_analysis --runs 1 --case 4248
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import logging

logging.disable(logging.INFO)

# Bare imports, matching what the service package uses internally. Mixing
# `backend.models.x` with the package's own `models.x` registers every table
# twice against the same MetaData and raises "Table 'users' is already
# defined". Run from backend/: python3.12 -m scripts.eval_comply_analysis
from core.database import SessionLocal
from models.eu_law import LawRequirement
from services.compliance.gap_analyzer import GapAnalyzer, GapAnalysisUnavailable

GOLD = Path(__file__).parent.parent / "data" / "eval" / "comply_gold_set.json"
DOC = Path(__file__).parent.parent / "data" / "eval" / "nordvik_textiles_policy.txt"

# "Needs action" is the decision a user actually takes off the back of a
# verdict. Confusing met with not_applicable is untidy; confusing gap with met
# is the one that costs somebody a fine.
NEEDS_ACTION = {"gap", "partial"}


def _bar(pct: float, width: int = 24) -> str:
    filled = int(round(pct / 100 * width))
    return "#" * filled + "." * (width - filled)


async def run_case(analyzer, requirement, chunks, runs):
    out = []
    for _ in range(runs):
        try:
            finding = await analyzer._analyze_requirement(requirement, chunks, analysis_id=None)
            out.append((finding.status, float(finding.confidence_score or 0)))
        except GapAnalysisUnavailable as exc:
            out.append(("__unavailable__", 0.0))
        except Exception as exc:  # noqa: BLE001
            out.append((f"__error:{type(exc).__name__}__", 0.0))
    return out


async def main_async(args):
    gold = json.loads(GOLD.read_text())
    cases = gold["cases"]
    if args.case:
        cases = [c for c in cases if c["requirement_id"] == args.case]
        if not cases:
            print(f"no gold case for requirement {args.case}")
            return 1

    db = SessionLocal()
    analyzer = GapAnalyzer(db)
    text = DOC.read_text()
    chunks = analyzer.doc_processor._chunk_text(text)
    analyzer._build_index(chunks)

    ids = [c["requirement_id"] for c in cases]
    reqs = {r.id: r for r in db.query(LawRequirement).filter(LawRequirement.id.in_(ids)).all()}
    missing = [i for i in ids if i not in reqs]
    if missing:
        print(f"[WARN] gold cases reference requirements not in the DB: {missing}")

    print(f"EU Law Comply gap-analyser evaluation")
    print(f"  gold set {gold['version']}  |  {len(cases)} cases  |  {args.runs} run(s) each")
    print(f"  document: {DOC.name}  ({len(chunks)} chunks)")
    print(f"  concurrency={analyzer.concurrency} retries={analyzer.max_attempts}\n")

    t0 = time.time()
    sem = asyncio.Semaphore(analyzer.concurrency)

    async def one(case):
        async with sem:
            r = reqs.get(case["requirement_id"])
            if r is None:
                return case, []
            return case, await run_case(analyzer, r, chunks, args.runs)

    results = await asyncio.gather(*(one(c) for c in cases))
    elapsed = time.time() - t0

    rows = []
    confusion = Counter()
    by_difficulty = defaultdict(lambda: {"exact": 0, "action": 0, "n": 0})
    unstable = 0
    unavailable = 0

    inconclusive = []
    for case, observations in results:
        if not observations:
            continue
        raw = [s for s, _ in observations]
        # Provider failures are NOT verdicts. Scoring them as one inflated
        # needs-action accuracy to 95%, because "__unavailable__" happens not to
        # be in NEEDS_ACTION and so silently "agreed" with every
        # not_applicable case. A harness that rewards an outage is worse than
        # no harness. Drop them, and drop any case left with no real verdict
        # from the denominators entirely.
        statuses = [s for s in raw if not s.startswith("__")]
        n_failed = len(raw) - len(statuses)
        if n_failed:
            unavailable += 1
        if not statuses:
            inconclusive.append((case["requirement_id"], case["article"]))
            continue
        modal, modal_n = Counter(statuses).most_common(1)[0]
        stable = len(set(statuses)) == 1
        if not stable:
            unstable += 1
        expected = case["expected"]
        exact = modal == expected
        action = (modal in NEEDS_ACTION) == (expected in NEEDS_ACTION)
        confusion[(expected, modal)] += 1
        d = by_difficulty[case["difficulty"]]
        d["n"] += 1
        d["exact"] += int(exact)
        d["action"] += int(action)
        rows.append({
            "id": case["requirement_id"], "article": case["article"],
            "expected": expected, "observed": statuses, "modal": modal,
            "stable": stable, "exact": exact, "action": action,
            "difficulty": case["difficulty"],
            "agreement": modal_n / len(statuses),
            "valid_runs": len(statuses),
            "failed_runs": n_failed,
        })

    n = len(rows)
    exact = sum(r["exact"] for r in rows)
    action = sum(r["action"] for r in rows)
    stable_n = sum(r["stable"] for r in rows)
    mean_agree = statistics.mean(r["agreement"] for r in rows) if rows else 0

    print("PER CASE")
    print(f"  {'req':>5}  {'expected':<15} {'modal':<15} {'runs':<22} {'':3} {'':3}")
    for r in sorted(rows, key=lambda x: (x["exact"], x["stable"])):
        marks = ("OK " if r["exact"] else ("~  " if r["action"] else "X  "))
        st = "" if r["stable"] else "  <- unstable"
        print(f"  {r['id']:>5}  {r['expected']:<15} {r['modal']:<15} "
              f"{','.join(s[:4] for s in r['observed']):<22} {marks}{st}")

    # Baseline: the gold set is gap-heavy because the document describes a real
    # company with real gaps. Without this line a 50% score reads as "coin
    # flip" when it is actually no better than a constant answer.
    scored_expected = [r["expected"] for r in rows]
    label_counts = Counter(scored_expected)
    majority_label, majority_n = label_counts.most_common(1)[0]
    base_exact = 100 * majority_n / n
    base_action = 100 * sum(1 for e in scored_expected
                            if (majority_label in NEEDS_ACTION) == (e in NEEDS_ACTION)) / n

    print(f"\nACCURACY  (n={n})")
    print(f"  exact status match      {exact}/{n}  {100*exact/n:5.1f}%  {_bar(100*exact/n)}")
    print(f"  needs-action match      {action}/{n}  {100*action/n:5.1f}%  {_bar(100*action/n)}")
    for diff, d in sorted(by_difficulty.items()):
        print(f"    {diff:<9} exact {d['exact']}/{d['n']}   action {d['action']}/{d['n']}")
    print(f"  --- baseline: always answer '{majority_label}' ---")
    print(f"  exact {base_exact:5.1f}%   needs-action {base_action:5.1f}%")
    lift = 100*exact/n - base_exact
    print(f"  lift over baseline      {lift:+5.1f} pp exact")

    if args.runs > 1:
        print(f"\nSTABILITY  (repeat runs of the same case)")
        print(f"  fully stable cases      {stable_n}/{n}  {100*stable_n/n:5.1f}%  {_bar(100*stable_n/n)}")
        print(f"  mean intra-case agreement        {100*mean_agree:5.1f}%")
        if unstable:
            print(f"  {unstable} case(s) gave different verdicts on identical input")

    print(f"\nCONFUSION  (expected -> modal, where they differ)")
    wrong = {k: v for k, v in confusion.items() if k[0] != k[1]}
    if not wrong:
        print("  none")
    for (exp, got), c in sorted(wrong.items(), key=lambda kv: -kv[1]):
        sev = "SEVERE" if (exp in NEEDS_ACTION) != (got in NEEDS_ACTION) else "minor"
        print(f"  {exp:<15} -> {got:<15} x{c}   {sev}")

    if unavailable:
        print(f"\n[WARN] {unavailable} case(s) had at least one provider failure; those runs are excluded from scoring")
    if inconclusive:
        print(f"[WARN] {len(inconclusive)} case(s) produced NO usable verdict and are excluded from all "
              f"denominators: {[i for i, _ in inconclusive]}")
        print(f"       Results below are over {n} of {len(cases)} gold cases. Re-run when providers are "
              f"less throttled before comparing against another version.")
    print(f"\nelapsed {elapsed:.0f}s for {n * args.runs} model calls")

    if args.json_out:
        Path(args.json_out).write_text(json.dumps({
            "gold_version": gold["version"], "runs": args.runs, "n": n,
            "exact_pct": 100*exact/n, "action_pct": 100*action/n,
            "stable_pct": 100*stable_n/n, "mean_agreement": mean_agree,
            "cases": rows,
        }, indent=2))
        print(f"wrote {args.json_out}")

    db.close()
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3,
                    help="repeats per case; >1 measures stability")
    ap.add_argument("--case", type=int, help="evaluate a single requirement id")
    ap.add_argument("--json-out", help="write machine-readable results here")
    args = ap.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    sys.exit(main())
