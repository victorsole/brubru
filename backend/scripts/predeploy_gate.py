#!/usr/bin/env python3.12
"""
Brubru Pre-Deploy Quality Gate

Runs before every /railway deploy. Sequentially runs:

    1. Knowledge base integrity check (check_knowledge_integrity.py)
       - Blocks on FAIL-class findings (orphan triggers, missing QUICK FACTS)
    2. Quality evaluation (eval_quality.py, 30 golden answers)
       - Blocks if pass rate falls below 85%
    3. Cross-feature link test (cross_link_test.py, 10 canonical-tree probes)
       - Blocks if pass rate falls below 90%
       - Added 25 April 2026 to enforce the canonical-tree mandate

Any failure halts deploy. This is the "pull the cord" principle from
the Quality Framework: no silent defects shipped to users.

Quality Framework: Playbook item F.

Usage:
    python3.12 scripts/predeploy_gate.py                  # Integrity + cross-link only (fast)
    python3.12 scripts/predeploy_gate.py --with-eval      # Add 30-query eval (slow, ~10 min)
    python3.12 scripts/predeploy_gate.py --skip-cross-link # Drop cross-link gate
    python3.12 scripts/predeploy_gate.py --backend URL    # Eval/cross-link backend
    python3.12 scripts/predeploy_gate.py --strict         # WARN findings also block

Exit codes:
    0  -- all gates passed, safe to deploy
    1  -- at least one gate failed, DO NOT deploy
    10 -- integrity gate failed
    20 -- eval gate failed
    30 -- cross-link gate failed
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND_ROOT = HERE.parent

INTEGRITY_SCRIPT = HERE / "check_knowledge_integrity.py"
EVAL_SCRIPT = HERE / "eval_quality.py"
CROSS_LINK_SCRIPT = HERE / "cross_link_test.py"

DEFAULT_BACKEND = "https://brubru-production.up.railway.app"


def run_integrity(strict: bool, total_gates: int) -> int:
    """Run the KB integrity checker. Returns its exit code."""
    print("\n" + "=" * 70)
    print(f"  GATE 1/{total_gates}: Knowledge Base Integrity")
    print("=" * 70)
    args = ["python3.12", str(INTEGRITY_SCRIPT)]
    if strict:
        args.append("--strict")
    result = subprocess.run(args, cwd=BACKEND_ROOT)
    return result.returncode


def run_eval(backend: str, gate_num: int, total_gates: int) -> int:
    """Run the answer-quality eval. Returns its exit code."""
    print("\n" + "=" * 70)
    print(f"  GATE {gate_num}/{total_gates}: Quality Evaluation (30 golden queries)")
    print("=" * 70)
    args = [
        "python3.12", str(EVAL_SCRIPT),
        "--backend", backend,
    ]
    result = subprocess.run(args, cwd=BACKEND_ROOT)
    return result.returncode


def run_cross_link(backend: str, gate_num: int, total_gates: int) -> int:
    """Run the canonical-tree cross-link test. Returns its exit code."""
    print("\n" + "=" * 70)
    print(f"  GATE {gate_num}/{total_gates}: Cross-Feature Link Test (10 probes)")
    print("=" * 70)
    args = [
        "python3.12", str(CROSS_LINK_SCRIPT),
        "--backend", backend,
    ]
    result = subprocess.run(args, cwd=BACKEND_ROOT)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description="Pre-deploy quality gate")
    parser.add_argument(
        "--with-eval",
        action="store_true",
        help="Run the full 30-query eval (slow: ~10 min)",
    )
    parser.add_argument(
        "--backend",
        default=DEFAULT_BACKEND,
        help="Backend URL for the eval gate",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="WARN findings in integrity check also fail the gate",
    )
    parser.add_argument(
        "--skip-cross-link",
        action="store_true",
        help="Skip the canonical-tree cross-link probe gate",
    )
    args = parser.parse_args()

    # Total stages depends on which optional gates are enabled
    total_gates = 1 + (1 if args.with_eval else 0) + (0 if args.skip_cross_link else 1)
    next_gate = 2

    start = time.time()
    print("\n" + "#" * 70)
    print("#  BRUBRU PRE-DEPLOY GATE")
    print("#  Sarasohn principle: defects must not reach the user")
    print("#" * 70)

    # Gate 1: integrity (always runs -- cheap, local)
    integrity_code = run_integrity(strict=args.strict, total_gates=total_gates)
    if integrity_code != 0:
        elapsed = time.time() - start
        print(f"\n[!!] DEPLOY BLOCKED by integrity gate ({elapsed:.0f}s)")
        print("     Fix the FAIL-class findings above, then re-run.")
        sys.exit(10)

    # Gate 2 (optional): full eval -- slow, hits network
    if args.with_eval:
        eval_code = run_eval(backend=args.backend, gate_num=next_gate, total_gates=total_gates)
        next_gate += 1
        if eval_code != 0:
            elapsed = time.time() - start
            print(f"\n[!!] DEPLOY BLOCKED by eval gate ({elapsed:.0f}s)")
            print("     Pass rate below 85%. Investigate failing queries.")
            sys.exit(20)
    else:
        print("\n" + "=" * 70)
        print(f"  GATE _/{total_gates}: Quality Evaluation  [SKIPPED]")
        print("  Re-run with --with-eval to include (adds ~10 min).")
        print("=" * 70)

    # Gate 3: cross-link (canonical-tree mandate, ~3-4 min)
    if not args.skip_cross_link:
        cross_link_code = run_cross_link(
            backend=args.backend, gate_num=next_gate, total_gates=total_gates,
        )
        if cross_link_code != 0:
            elapsed = time.time() - start
            print(f"\n[!!] DEPLOY BLOCKED by cross-link gate ({elapsed:.0f}s)")
            print("     Chat is not naming the right canonical features.")
            print("     Fix in backend/services/ai_service.py _build_system_prompt:")
            print("     CRITICAL -- CROSS-LINK BRUBRU FEATURES section.")
            sys.exit(30)
    else:
        print("\n" + "=" * 70)
        print("  GATE _/_: Cross-Feature Link  [SKIPPED]")
        print("  Re-run without --skip-cross-link to include (~3-4 min).")
        print("=" * 70)

    elapsed = time.time() - start
    print("\n" + "#" * 70)
    print(f"#  [OK] ALL GATES PASSED ({elapsed:.0f}s) -- safe to deploy")
    print("#" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
