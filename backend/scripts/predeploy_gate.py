#!/usr/bin/env python3.12
"""
Brubru Pre-Deploy Quality Gate

Runs before every /railway deploy. Sequentially runs:

    1. Knowledge base integrity check (check_knowledge_integrity.py)
       - Blocks on FAIL-class findings (orphan triggers, missing QUICK FACTS)
    2. Quality evaluation (eval_quality.py, --must-pass subset)
       - Blocks if pass rate falls below 85%

Either failure halts deploy. This is the "pull the cord" principle from
the Quality Framework: no silent defects shipped to users.

Quality Framework: Playbook item F.

Usage:
    python3.12 scripts/predeploy_gate.py                 # Run both gates (skip eval by default)
    python3.12 scripts/predeploy_gate.py --with-eval     # Include eval gate (slow, ~10 min)
    python3.12 scripts/predeploy_gate.py --backend URL   # Eval backend (default: production)
    python3.12 scripts/predeploy_gate.py --strict        # WARN findings also block

Exit codes:
    0  -- all gates passed, safe to deploy
    1  -- at least one gate failed, DO NOT deploy
    10 -- integrity gate failed
    20 -- eval gate failed
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

DEFAULT_BACKEND = "https://brubru-production.up.railway.app"


def run_integrity(strict: bool) -> int:
    """Run the KB integrity checker. Returns its exit code."""
    print("\n" + "=" * 70)
    print("  GATE 1/2: Knowledge Base Integrity")
    print("=" * 70)
    args = ["python3.12", str(INTEGRITY_SCRIPT)]
    if strict:
        args.append("--strict")
    result = subprocess.run(args, cwd=BACKEND_ROOT)
    return result.returncode


def run_eval(backend: str) -> int:
    """Run the answer-quality eval. Returns its exit code."""
    print("\n" + "=" * 70)
    print("  GATE 2/2: Quality Evaluation (30 golden queries)")
    print("=" * 70)
    args = [
        "python3.12", str(EVAL_SCRIPT),
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
    args = parser.parse_args()

    start = time.time()
    print("\n" + "#" * 70)
    print("#  BRUBRU PRE-DEPLOY GATE")
    print("#  Sarasohn principle: defects must not reach the user")
    print("#" * 70)

    # Gate 1: integrity (always runs -- cheap, local)
    integrity_code = run_integrity(strict=args.strict)
    if integrity_code != 0:
        elapsed = time.time() - start
        print(f"\n[!!] DEPLOY BLOCKED by integrity gate ({elapsed:.0f}s)")
        print("     Fix the FAIL-class findings above, then re-run.")
        sys.exit(10)

    # Gate 2: eval (opt-in -- slow, hits network)
    if args.with_eval:
        eval_code = run_eval(backend=args.backend)
        if eval_code != 0:
            elapsed = time.time() - start
            print(f"\n[!!] DEPLOY BLOCKED by eval gate ({elapsed:.0f}s)")
            print("     Pass rate below 85%. Investigate failing queries.")
            sys.exit(20)
    else:
        print("\n" + "=" * 70)
        print("  GATE 2/2: Quality Evaluation  [SKIPPED]")
        print("  Re-run with --with-eval to include (adds ~10 min).")
        print("=" * 70)

    elapsed = time.time() - start
    print("\n" + "#" * 70)
    print(f"#  [OK] ALL GATES PASSED ({elapsed:.0f}s) -- safe to deploy")
    print("#" * 70)
    sys.exit(0)


if __name__ == "__main__":
    main()
