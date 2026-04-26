#!/usr/bin/env python3.12
"""
Brubru Cross-Feature Link Test

Probes whether Chat surfaces the right Brubru feature for each query intent.
The 10 queries below come from .claude/skills/test-chatbot/SKILL.md and are
the canonical regression suite for the CRITICAL -- CROSS-LINK BRUBRU FEATURES
system prompt rule (added 25 April 2026).

A pass means: the response names AT LEAST ONE expected feature from the
canonical tree. Wrong feature or generic phrasing ("another part of Brubru")
counts as a fail.

Usage:
    python3.12 scripts/cross_link_test.py
    python3.12 scripts/cross_link_test.py --backend http://localhost:8000
    python3.12 scripts/cross_link_test.py --json

Exit codes:
    0  -- all 10 pass (>= 90% pass rate)
    1  -- one or more failures
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from eval_quality import (  # noqa: E402
    detect_features_named,
    FEATURE_PATTERNS,
)

DEFAULT_BACKEND = "https://brubru-production.up.railway.app"
CHAT_ENDPOINT = "/api/chat/message"
REQUEST_TIMEOUT = 200

# 10 queries from .claude/skills/test-chatbot/SKILL.md "Cross-Feature Link Tests"
CROSS_LINK_TESTS = [
    {
        "id": "CL-01",
        "query": "What's happening on the AI Act this week?",
        "expected": ["My EU Calendar", "Position Analysis", "Predictions"],
    },
    {
        "id": "CL-02",
        "query": "Help me draft an amendment to Article 5 of the AI Act",
        "expected": ["Amendator", "Amendments"],
    },
    {
        "id": "CL-03",
        "query": "Which MEPs are likely to vote against the CSAM regulation?",
        "expected": ["Predictions", "Position Analysis"],
    },
    {
        "id": "CL-04",
        "query": "What compliance obligations does the AI Act create for my company?",
        "expected": ["EU Law Comply", "Documents"],
    },
    {
        "id": "CL-05",
        "query": "Are there any open consultations on digital fairness?",
        "expected": ["EC Public Consultations"],
    },
    {
        "id": "CL-06",
        "query": "Track the trilogues on the Grids Package for me",
        "expected": ["My Files", "Legislative Tracker", "My EU Calendar"],
    },
    {
        "id": "CL-07",
        "query": "Are there Horizon Europe calls on quantum?",
        "expected": ["Tenderator"],
    },
    {
        "id": "CL-08",
        "query": "Can I subscribe to a feed of new EU AI Act delegated acts?",
        "expected": ["API"],
    },
    {
        "id": "CL-09",
        "query": "Draft me a position paper on the EU Migration Pact",
        "expected": ["Documents", "Amendator"],
    },
    {
        "id": "CL-10",
        "query": "Show me what's coming up in EU committees next week",
        "expected": ["My EU Calendar"],
    },
]


def run_one(backend: str, test: dict) -> dict:
    payload = {
        "message": test["query"],
        "user_id": None,
        "chat_id": None,
        "pre_user_id": None,
        "use_context": True,
        "stream": False,
    }
    out = {
        "id": test["id"],
        "query": test["query"],
        "expected": test["expected"],
        "named": [],
        "matched": [],
        "passed": False,
        "response_time_ms": 0.0,
        "error": "",
        "model": "",
    }
    try:
        start = time.time()
        resp = requests.post(
            f"{backend}{CHAT_ENDPOINT}",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=REQUEST_TIMEOUT,
        )
        out["response_time_ms"] = round((time.time() - start) * 1000, 1)
        if resp.status_code != 200:
            out["error"] = f"HTTP {resp.status_code}: {resp.text[:200]}"
            return out
        data = resp.json()
        text = data.get("message", "")
        out["model"] = data.get("model", "unknown")
        out["named"] = detect_features_named(text)
        out["matched"] = [f for f in test["expected"] if f in out["named"]]
        out["passed"] = bool(out["matched"])
        out["response_text"] = text
    except requests.exceptions.Timeout:
        out["error"] = f"Timeout after {REQUEST_TIMEOUT}s"
    except requests.exceptions.ConnectionError:
        out["error"] = f"Connection refused: {backend}"
    except Exception as e:
        out["error"] = str(e)
    return out


def main():
    parser = argparse.ArgumentParser(description="Cross-feature link test")
    parser.add_argument("--backend", default=DEFAULT_BACKEND)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  BRUBRU CROSS-FEATURE LINK TEST")
    print(f"  Backend: {args.backend}")
    print("=" * 70)

    # Quick reachability check
    try:
        h = requests.get(f"{args.backend}/docs", timeout=5)
        if h.status_code != 200:
            print(f"  [WARN] /docs returned {h.status_code}")
    except requests.exceptions.ConnectionError:
        print(f"  [ERROR] Cannot reach {args.backend}")
        sys.exit(2)

    print(f"\n  Running {len(CROSS_LINK_TESTS)} cross-link probes...\n")

    results = []
    for i, test in enumerate(CROSS_LINK_TESTS, 1):
        print(f"  [{i:>2}/10] {test['id']}: {test['query'][:55]}...", end="", flush=True)
        r = run_one(args.backend, test)
        results.append(r)
        if r["error"]:
            print(f" ERR ({r['error'][:35]})")
        elif r["passed"]:
            print(f" PASS ({r['response_time_ms']:.0f}ms) -> {', '.join(r['matched'])}")
        else:
            named = ", ".join(r["named"]) if r["named"] else "<none>"
            print(f" FAIL ({r['response_time_ms']:.0f}ms) named: {named}")

    passed = sum(1 for r in results if r["passed"])
    errors = sum(1 for r in results if r["error"])
    pass_rate = round(passed / len(results) * 100, 1)

    print()
    print("=" * 70)
    print(f"  Pass rate: {pass_rate}%   ({passed}/{len(results)} passed, {errors} errors)")
    print("=" * 70)

    if not all(r["passed"] for r in results):
        print("\n  Failures:")
        for r in results:
            if not r["passed"] and not r["error"]:
                print(f"    {r['id']}: expected {r['expected']}, named {r['named'] or '<none>'}")

    if args.json:
        out_path = HERE.parent.parent / "data" / "golden_answers" / "cross_link_results.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "backend": args.backend,
            "pass_rate": pass_rate,
            "passed": passed,
            "total": len(results),
            "results": results,
        }, indent=2, ensure_ascii=False))
        print(f"\n  JSON saved to: {out_path}")

    # Gate: 90% threshold (1 fail tolerated, 2+ blocks deploy)
    if pass_rate >= 90.0:
        print("\n  [OK] Cross-link gate PASSED")
        sys.exit(0)
    else:
        print(f"\n  [!!] Cross-link gate FAILED (pass rate {pass_rate}% < 90%)")
        print("       Fix in backend/services/ai_service.py _build_system_prompt")
        print("       (CRITICAL -- CROSS-LINK BRUBRU FEATURES section).")
        sys.exit(1)


if __name__ == "__main__":
    main()
