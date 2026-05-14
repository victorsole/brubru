#!/usr/bin/env python3
"""
Endpoint Documentation Audit

Walks every router decorator in backend/api/v1/*.py and checks each endpoint's
summary + description against the canonical 6-section format:

  1. **What it does**      — plain-English (no CELEX/ECLI/EURIO jargon as primary name)
  2. **When to use it**    — concrete use case
  3. **Input**             — parameters with examples
  4. **Try it**            — live example URL
  5. **You get back**      — response shape + 5 mandatory datapoints
  6. **Data freshness**    — sync cadence (resolved from backend/config/sync_cadence.json)

Outputs a table to stdout; exits 1 if any endpoint has missing sections.

Usage:
    python3.12 backend/scripts/audit_endpoint_docs.py
    python3.12 backend/scripts/audit_endpoint_docs.py --json
    python3.12 backend/scripts/audit_endpoint_docs.py --file backend/api/v1/cellar_discover.py
    python3.12 backend/scripts/audit_endpoint_docs.py --fail-on-missing
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
V1_DIR = REPO_ROOT / "backend" / "api" / "v1"
CADENCE_FILE = REPO_ROOT / "backend" / "config" / "sync_cadence.json"

REQUIRED_SECTIONS = [
    "What it does",
    "When to use it",
    "Input",
    "Try it",
    "You get back",
    "Data freshness",
]

# Tokens that should NOT appear in `summary=` (they belong inside the description
# body where users can read context; using them as the primary name confuses
# non-EU-specialist readers).
JARGON_TOKENS = [
    "CELEX",
    "ECLI",
    "EURIO",
    "CORDIS",
    "OEIL",
    "FMX4",
    "SPARQL",
    "Akoma Ntoso",
]

# Decorator method names that register routes.
ROUTER_METHODS = {"get", "post", "put", "delete", "patch"}


def _get_keyword(call: ast.Call, name: str) -> Optional[str]:
    """Extract a string keyword argument from a Call AST node."""
    for kw in call.keywords:
        if kw.arg != name:
            continue
        return _const_to_str(kw.value)
    return None


def _const_to_str(node: ast.AST) -> Optional[str]:
    """Best-effort resolve an AST node to a string literal."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                out.append(v.value)
            else:
                return None
        return "".join(out)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _const_to_str(node.left)
        right = _const_to_str(node.right)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.Call):
        # Sometimes wrapped as f"...".format(...) — give up cleanly
        return None
    return None


def _decorator_route(deco: ast.AST) -> Optional[tuple[str, str]]:
    """If `deco` is a router-method call like @router.get("/x", ...), return
    (METHOD, PATH). Otherwise None."""
    if not isinstance(deco, ast.Call):
        return None
    func = deco.func
    # Common shapes: router.get(...), _router.get(...), my_router.get(...)
    if not isinstance(func, ast.Attribute):
        return None
    method = func.attr
    if method not in ROUTER_METHODS:
        return None
    # Router instance must look like an attribute access on a Name (e.g. `router`)
    target = func.value
    if not isinstance(target, (ast.Name, ast.Attribute)):
        return None
    if not deco.args:
        return None
    path = _const_to_str(deco.args[0])
    if path is None:
        return None
    return method.upper(), path


def _check_sections(description: str) -> tuple[set[str], set[str]]:
    """Return (present_sections, missing_sections) checked against REQUIRED_SECTIONS."""
    present = set()
    for section in REQUIRED_SECTIONS:
        # Match **Section** or **Section ...** (allowing some trailing words like
        # "**Where to find ECLIs to test**" is a free-form heading and doesn't count).
        pattern = rf"\*\*{re.escape(section)}\*\*"
        if re.search(pattern, description, re.IGNORECASE):
            present.add(section)
    missing = set(REQUIRED_SECTIONS) - present
    return present, missing


def _check_summary_jargon(summary: str) -> list[str]:
    """Return list of jargon tokens found in summary."""
    if not summary:
        return []
    return [t for t in JARGON_TOKENS if re.search(rf"\b{re.escape(t)}\b", summary)]


def audit_file(path: Path) -> list[dict]:
    """Audit a single Python file. Returns a list of endpoint records."""
    try:
        source = path.read_text(encoding="utf-8")
    except Exception as e:
        return [{"file": str(path.relative_to(REPO_ROOT)), "error": str(e)}]

    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return [{"file": str(path.relative_to(REPO_ROOT)), "error": f"SyntaxError: {e}"}]

    records = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            route = _decorator_route(deco)
            if route is None:
                continue
            method, route_path = route
            summary = _get_keyword(deco, "summary") or ""
            description = _get_keyword(deco, "description") or ""
            present, missing = _check_sections(description)
            jargon = _check_summary_jargon(summary)
            records.append({
                "file": str(path.relative_to(REPO_ROOT)),
                "function": node.name,
                "method": method,
                "path": route_path,
                "summary": summary,
                "summary_jargon": jargon,
                "description_chars": len(description),
                "sections_present": sorted(present),
                "sections_missing": sorted(missing),
                "has_summary": bool(summary),
                "has_description": bool(description),
                "complete": (not missing and bool(summary) and not jargon),
            })
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", help="Audit a single file instead of all of api/v1/")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text table")
    parser.add_argument("--fail-on-missing", action="store_true", help="Exit 1 if any endpoint is incomplete")
    parser.add_argument("--only-missing", action="store_true", help="Show only incomplete endpoints")
    args = parser.parse_args()

    if args.file:
        files = [Path(args.file).resolve()]
    else:
        files = sorted(p for p in V1_DIR.glob("*.py") if not p.name.startswith("_") and p.name != "__init__.py")

    all_records = []
    for f in files:
        all_records.extend(audit_file(f))

    # Aggregate
    total = len(all_records)
    complete = sum(1 for r in all_records if r.get("complete"))
    no_summary = sum(1 for r in all_records if not r.get("has_summary"))
    no_description = sum(1 for r in all_records if not r.get("has_description"))
    jargon_hits = sum(1 for r in all_records if r.get("summary_jargon"))

    if args.json:
        print(json.dumps({
            "total": total,
            "complete": complete,
            "incomplete": total - complete,
            "no_summary": no_summary,
            "no_description": no_description,
            "summary_jargon": jargon_hits,
            "records": all_records,
        }, indent=2, ensure_ascii=False))
    else:
        # Text table
        print(f"\n{'='*100}")
        print(f"ENDPOINT DOCUMENTATION AUDIT — {total} endpoints across {len(files)} files")
        print(f"{'='*100}")
        print(f"  Complete (all 6 sections + clean summary): {complete} / {total} ({100*complete/total if total else 0:.0f}%)")
        print(f"  Missing summary=:                          {no_summary}")
        print(f"  Missing description=:                      {no_description}")
        print(f"  Jargon in summary= (CELEX/ECLI/etc):       {jargon_hits}")
        print(f"{'='*100}\n")

        print(f"  {'METHOD':<6} {'PATH':<60} {'STATUS':<8} MISSING SECTIONS / FLAGS")
        print(f"  {'-'*6} {'-'*60} {'-'*8} {'-'*40}")
        rows = all_records if not args.only_missing else [r for r in all_records if not r.get("complete")]
        for r in sorted(rows, key=lambda x: (x.get("file", ""), x.get("path", ""))):
            if "error" in r:
                print(f"  ERROR  {r['file']:<60}          {r['error']}")
                continue
            status = "OK" if r["complete"] else "MISS"
            flags = []
            if not r["has_summary"]:
                flags.append("no-summary")
            if not r["has_description"]:
                flags.append("no-description")
            if r["summary_jargon"]:
                flags.append(f"jargon:{','.join(r['summary_jargon'])}")
            if r["sections_missing"]:
                flags.append(f"missing:{','.join(s.replace(' ', '_') for s in r['sections_missing'])}")
            method = r["method"]
            path = r["path"][:60]
            print(f"  {method:<6} {path:<60} {status:<8} {' | '.join(flags) if flags else '(clean)'}")

    if args.fail_on_missing and total - complete > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
