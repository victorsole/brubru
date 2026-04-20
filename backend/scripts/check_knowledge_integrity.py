#!/usr/bin/env python3.12
"""
Brubru Knowledge Base Integrity Checker

Pre-deploy gate that validates the knowledge base is healthy before shipping.
Runs 7 checks across guides and GUIDE_KEYWORD_TRIGGERS, classifies each
finding by severity (FAIL / WARN / INFO), and exits 1 if any FAIL-class
check is violated.

Quality Framework: Playbook item E.
Complements eval_quality.py (answer quality) with KB structural quality.

Usage:
    python3.12 scripts/check_knowledge_integrity.py            # full report
    python3.12 scripts/check_knowledge_integrity.py --json     # machine-readable
    python3.12 scripts/check_knowledge_integrity.py --strict   # WARNs also fail

Exit codes:
    0 -- all FAIL checks pass (WARNs and INFOs do not block)
    1 -- at least one FAIL check violated (or any WARN in --strict mode)

Checks:
    1. Orphan triggers     -- trigger -> non-existent guide id         [FAIL]
    2. Unreachable guides  -- guide exists but no trigger points to it [WARN]
    3. Missing QUICK FACTS -- guide lacks QUICK FACTS block             [FAIL]
    4. Stale guides        -- mtime > 30 days                           [WARN]
    5. Duplicate triggers  -- same keyword maps twice                   [INFO]
    6. Short guides        -- content < 500 chars                       [WARN]
    7. Long guides         -- content > 8000 chars (truncation risk)    [WARN]
"""

import argparse
import json
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# Path setup: be usable from any cwd
HERE = Path(__file__).resolve().parent
BACKEND_ROOT = HERE.parent
PROJECT_ROOT = BACKEND_ROOT.parent
GUIDES_DIR = BACKEND_ROOT / "knowledge_base" / "guides"

sys.path.insert(0, str(BACKEND_ROOT))
from knowledge_base.knowledge_loader import GUIDE_KEYWORD_TRIGGERS  # noqa: E402


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
STALE_AFTER_DAYS = 30
MIN_GUIDE_CHARS = 500
MAX_GUIDE_CHARS = 8000
QUICK_FACTS_RE = re.compile(r"##\s*QUICK\s*FACTS", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Check results
# ---------------------------------------------------------------------------
class Severity:
    FAIL = "FAIL"
    WARN = "WARN"
    INFO = "INFO"


def check_orphan_triggers(guide_ids: set) -> list:
    """1. Orphan triggers -- trigger points to non-existent guide id. FAIL."""
    findings = []
    orphans = defaultdict(list)
    for keyword, targets in GUIDE_KEYWORD_TRIGGERS.items():
        for guide_id in targets:
            if guide_id not in guide_ids:
                orphans[guide_id].append(keyword)
    for guide_id, keywords in sorted(orphans.items()):
        findings.append({
            "severity": Severity.FAIL,
            "check": "orphan_triggers",
            "guide_id": guide_id,
            "detail": f"{len(keywords)} triggers point here but the guide doesn't exist",
            "sample_keywords": keywords[:5],
        })
    return findings


def check_unreachable_guides(guides: dict) -> list:
    """2. Unreachable guides -- guide exists but no trigger points to it. WARN."""
    findings = []
    targeted = set()
    for targets in GUIDE_KEYWORD_TRIGGERS.values():
        targeted.update(targets)
    for guide_id in sorted(guides.keys()):
        if guide_id not in targeted:
            findings.append({
                "severity": Severity.WARN,
                "check": "unreachable_guide",
                "guide_id": guide_id,
                "detail": "No keyword trigger points to this guide",
            })
    return findings


def check_missing_quick_facts(guides: dict) -> list:
    """3. Guides without QUICK FACTS block. FAIL."""
    findings = []
    for guide_id, content in sorted(guides.items()):
        if not QUICK_FACTS_RE.search(content):
            findings.append({
                "severity": Severity.FAIL,
                "check": "missing_quick_facts",
                "guide_id": guide_id,
                "detail": "No '## QUICK FACTS' heading found",
            })
    return findings


def check_stale_guides(guide_mtimes: dict) -> list:
    """4. Guides older than 30 days without update. WARN."""
    findings = []
    cutoff = datetime.now() - timedelta(days=STALE_AFTER_DAYS)
    for guide_id, mtime in sorted(guide_mtimes.items(), key=lambda x: x[1]):
        if mtime < cutoff:
            age_days = (datetime.now() - mtime).days
            findings.append({
                "severity": Severity.WARN,
                "check": "stale_guide",
                "guide_id": guide_id,
                "detail": f"Last modified {age_days} days ago ({mtime.strftime('%Y-%m-%d')})",
                "age_days": age_days,
            })
    return findings


def check_duplicate_triggers() -> list:
    """5. Same keyword → same guide twice (dict can't, but list target duplicates). INFO."""
    findings = []
    for keyword, targets in GUIDE_KEYWORD_TRIGGERS.items():
        counts = Counter(targets)
        for guide_id, n in counts.items():
            if n > 1:
                findings.append({
                    "severity": Severity.INFO,
                    "check": "duplicate_trigger",
                    "keyword": keyword,
                    "guide_id": guide_id,
                    "detail": f"Listed {n} times in the same trigger",
                })
    return findings


def check_short_guides(guides: dict) -> list:
    """6. Guides shorter than 500 chars (suspiciously empty). WARN."""
    findings = []
    for guide_id, content in sorted(guides.items()):
        if len(content) < MIN_GUIDE_CHARS:
            findings.append({
                "severity": Severity.WARN,
                "check": "short_guide",
                "guide_id": guide_id,
                "detail": f"{len(content)} chars (threshold: {MIN_GUIDE_CHARS})",
                "char_count": len(content),
            })
    return findings


def check_long_guides(guides: dict) -> list:
    """7. Guides longer than 8000 chars (context truncation risk). WARN."""
    findings = []
    for guide_id, content in sorted(guides.items()):
        if len(content) > MAX_GUIDE_CHARS:
            findings.append({
                "severity": Severity.WARN,
                "check": "long_guide",
                "guide_id": guide_id,
                "detail": f"{len(content)} chars (threshold: {MAX_GUIDE_CHARS})",
                "char_count": len(content),
            })
    return findings


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------
def load_guides():
    """Return (guides_dict, mtimes_dict) from backend/knowledge_base/guides."""
    if not GUIDES_DIR.exists():
        print(f"[ERROR] Guides dir not found: {GUIDES_DIR}")
        sys.exit(1)

    guides = {}
    mtimes = {}
    for path in GUIDES_DIR.glob("*.md"):
        guide_id = path.stem
        try:
            guides[guide_id] = path.read_text(encoding="utf-8")
            mtimes[guide_id] = datetime.fromtimestamp(path.stat().st_mtime)
        except Exception as e:
            print(f"[WARN] Could not read {path.name}: {e}")
    return guides, mtimes


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
def print_report(findings: list, summary: dict, strict: bool):
    print()
    print("=" * 70)
    print("  BRUBRU KNOWLEDGE BASE INTEGRITY CHECK")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # Summary
    print(f"  Guides:           {summary['total_guides']}")
    print(f"  Trigger keywords: {summary['total_triggers']}")
    print(f"  Targeted guides:  {summary['targeted_guides']}")
    print()
    print(f"  FAIL findings:    {summary['fail_count']}")
    print(f"  WARN findings:    {summary['warn_count']}")
    print(f"  INFO findings:    {summary['info_count']}")
    print()

    if not findings:
        print("  [OK] No findings. Knowledge base is healthy.")
        print()
        return

    # Group findings by check
    by_check = defaultdict(list)
    for f in findings:
        by_check[f["check"]].append(f)

    for check, items in sorted(by_check.items()):
        sev = items[0]["severity"]
        print(f"  [{sev}] {check} ({len(items)} items)")
        print("  " + "-" * 55)
        for item in items[:10]:
            key = item.get("guide_id") or item.get("keyword", "?")
            print(f"       {key:<45} {item['detail']}")
        if len(items) > 10:
            print(f"       ... and {len(items) - 10} more")
        print()

    # Verdict
    gate_failed = summary["fail_count"] > 0 or (strict and summary["warn_count"] > 0)
    if gate_failed:
        print("  [!!] Integrity gate FAILED")
        if summary["fail_count"] > 0:
            print(f"       {summary['fail_count']} FAIL-class findings must be resolved before deploy")
        if strict and summary["warn_count"] > 0:
            print(f"       {summary['warn_count']} WARN findings (strict mode)")
    else:
        if summary["warn_count"] > 0:
            print(f"  [OK] Integrity gate PASSED (but {summary['warn_count']} WARNs -- review when possible)")
        else:
            print("  [OK] Integrity gate PASSED")
    print()


def save_json_report(findings: list, summary: dict, path: Path):
    output = {
        "timestamp": datetime.now().isoformat(),
        "summary": summary,
        "findings": findings,
    }
    with open(path, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    print(f"\n  JSON report saved to: {path}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Brubru knowledge base integrity checker")
    parser.add_argument("--json", action="store_true", help="Save JSON report")
    parser.add_argument("--strict", action="store_true", help="WARN findings also fail the gate")
    parser.add_argument("--output", help="JSON output path (default: audit/kb_integrity.json)")
    args = parser.parse_args()

    guides, mtimes = load_guides()
    guide_ids = set(guides.keys())

    findings = []
    findings.extend(check_orphan_triggers(guide_ids))
    findings.extend(check_unreachable_guides(guides))
    findings.extend(check_missing_quick_facts(guides))
    findings.extend(check_stale_guides(mtimes))
    findings.extend(check_duplicate_triggers())
    findings.extend(check_short_guides(guides))
    findings.extend(check_long_guides(guides))

    targeted = set()
    for targets in GUIDE_KEYWORD_TRIGGERS.values():
        targeted.update(targets)

    summary = {
        "total_guides": len(guides),
        "total_triggers": len(GUIDE_KEYWORD_TRIGGERS),
        "targeted_guides": len(targeted & guide_ids),
        "fail_count": sum(1 for f in findings if f["severity"] == Severity.FAIL),
        "warn_count": sum(1 for f in findings if f["severity"] == Severity.WARN),
        "info_count": sum(1 for f in findings if f["severity"] == Severity.INFO),
    }

    print_report(findings, summary, strict=args.strict)

    if args.json:
        output_path = Path(args.output) if args.output else PROJECT_ROOT / "audit" / "kb_integrity.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_json_report(findings, summary, output_path)

    gate_failed = summary["fail_count"] > 0 or (args.strict and summary["warn_count"] > 0)
    sys.exit(1 if gate_failed else 0)


if __name__ == "__main__":
    main()
