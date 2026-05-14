#!/usr/bin/env python3
"""
Auto-retrofit `**Data freshness**` section into endpoint descriptions.

For every endpoint whose description= already ends with a `**You get back**`
section, append a `**Data freshness**` section pulling the cadence label from
backend/config/sync_cadence.json.

This is the safe automated pass. Endpoints with non-canonical description shapes
(no `**You get back**` block, or completely missing description=) are left alone
and surface in audit_endpoint_docs.py as TODO for manual retrofit.

Usage:
    python3.12 backend/scripts/retrofit_data_freshness.py --dry-run
    python3.12 backend/scripts/retrofit_data_freshness.py --apply
"""

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
V1_DIR = REPO_ROOT / "backend" / "api" / "v1"
CADENCE_FILE = REPO_ROOT / "backend" / "config" / "sync_cadence.json"


def load_cadence() -> dict:
    return json.loads(CADENCE_FILE.read_text(encoding="utf-8"))


def _router_prefix_from_call(call: ast.Call) -> str | None:
    """If a Call is APIRouter(prefix="..."), return the prefix string."""
    func = call.func
    name = None
    if isinstance(func, ast.Name):
        name = func.id
    elif isinstance(func, ast.Attribute):
        name = func.attr
    if name != "APIRouter":
        return None
    for kw in call.keywords:
        if kw.arg == "prefix" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _find_router_prefixes(tree: ast.AST) -> dict[str, str]:
    """Find every `<name> = APIRouter(prefix='...')` and return {name: prefix}."""
    prefixes: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if not isinstance(node.value, ast.Call):
                continue
            prefix = _router_prefix_from_call(node.value)
            if prefix is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    prefixes[target.id] = prefix
    return prefixes


def _resolve_cadence_for_path(full_path: str, cadence: dict) -> tuple[str, str] | None:
    """Find the longest path_prefix in sync_cadence.json that matches full_path.

    Returns (tier, freshness_label) or None.
    """
    candidates = []
    for entry in cadence["endpoints"]:
        prefix = entry["path_prefix"]
        if full_path == prefix or full_path.startswith(prefix.rstrip("/") + "/") or full_path.startswith(prefix + "/"):
            candidates.append((len(prefix), entry))
    if not candidates:
        return None
    # Longest-prefix wins
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0][1]
    tier = best["tier"]
    source = best.get("source", "upstream source")
    label_tpl = cadence["tiers"][tier]["freshness_label"]
    label = label_tpl.format(source=source)
    notes = best.get("notes", "")
    if notes:
        label = f"{label} {notes}"
    return tier, label


# Regex matches `description="""..."""` or `description='''...'''`
# Captures the triple-quoted body so we can append safely.
DESC_PATTERN = re.compile(
    r'(description\s*=\s*)(?P<quote>"""|\'\'\')(?P<body>.*?)(?P=quote)',
    flags=re.DOTALL,
)


def _path_for_decorator(deco: ast.Call) -> tuple[str, str] | None:
    """Return (router_var_name, route_path) for a router.<method>(...) call."""
    func = deco.func
    if not isinstance(func, ast.Attribute):
        return None
    if func.attr not in {"get", "post", "put", "delete", "patch"}:
        return None
    if not isinstance(func.value, ast.Name):
        return None
    if not deco.args:
        return None
    arg = deco.args[0]
    if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
        return None
    return func.value.id, arg.value


def retrofit_file(path: Path, cadence: dict, apply: bool) -> dict:
    """Retrofit Data freshness into one file. Returns a report dict."""
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return {"file": str(path.relative_to(REPO_ROOT)), "error": f"SyntaxError: {e}"}

    prefixes = _find_router_prefixes(tree)

    # Walk routes and collect (function_name, full_path, freshness_label) tuples.
    target_routes: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for deco in node.decorator_list:
            if not isinstance(deco, ast.Call):
                continue
            info = _path_for_decorator(deco)
            if info is None:
                continue
            router_var, route_path = info
            prefix = prefixes.get(router_var, "")
            full_path = f"/api/v1{prefix}{route_path}" if not prefix.startswith("/api/v1") else f"{prefix}{route_path}"
            # Some prefixes already include /api/v1 (from main.py mount). Normalise.
            if not full_path.startswith("/api/v1"):
                full_path = "/api/v1" + full_path
            full_path = re.sub(r"/+", "/", full_path)

            resolved = _resolve_cadence_for_path(full_path, cadence)
            if resolved is None:
                continue
            tier, freshness_label = resolved
            target_routes.append({
                "function": node.name,
                "full_path": full_path,
                "tier": tier,
                "freshness_label": freshness_label,
                "decorator_lineno": deco.lineno,
            })

    # Now walk the source line-by-line, find each route's decorator block, and
    # if its description= triple-quoted body has `**You get back**` but not
    # `**Data freshness**`, append the freshness section.
    changes: list[dict] = []
    new_source = source
    offset_delta = 0  # cumulative inserted-chars offset as we patch

    # For each target route, locate its description=""" block and patch it.
    # We do this by re-parsing each time (slow but safe).
    for target in target_routes:
        # Re-parse the current new_source (so we work with up-to-date line numbers)
        try:
            cur_tree = ast.parse(new_source)
        except SyntaxError:
            changes.append({"function": target["function"], "status": "skipped", "reason": "re-parse failed"})
            continue

        # Find the matching decorator Call (same function name + path)
        found_call = None
        for node in ast.walk(cur_tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name != target["function"]:
                continue
            for deco in node.decorator_list:
                if not isinstance(deco, ast.Call):
                    continue
                info = _path_for_decorator(deco)
                if info is None:
                    continue
                _, route_path = info
                if target["full_path"].endswith(route_path) or route_path == "" and target["full_path"].endswith("/"):
                    found_call = deco
                    break
            if found_call:
                break
        if not found_call:
            changes.append({"function": target["function"], "status": "skipped", "reason": "decorator not found"})
            continue

        # Find description= keyword in the call
        desc_kw = None
        for kw in found_call.keywords:
            if kw.arg == "description":
                desc_kw = kw
                break
        if desc_kw is None:
            changes.append({"function": target["function"], "status": "skipped", "reason": "no description="})
            continue

        # Only handle triple-quoted Constant strings (the canonical multi-line form).
        if not isinstance(desc_kw.value, ast.Constant) or not isinstance(desc_kw.value.value, str):
            changes.append({"function": target["function"], "status": "skipped", "reason": "non-literal description"})
            continue

        body = desc_kw.value.value
        # Check shape
        if "**Data freshness**" in body:
            changes.append({"function": target["function"], "status": "skipped", "reason": "already has Data freshness"})
            continue
        if "**You get back**" not in body:
            changes.append({"function": target["function"], "status": "skipped", "reason": "no canonical You get back section"})
            continue

        # Locate the literal in new_source by line + col offsets.
        # ast Constant nodes carry .lineno + .col_offset (1-indexed line, 0-indexed col).
        # The string literal token starts at (lineno, col_offset).
        lines = new_source.splitlines(keepends=True)
        if desc_kw.value.lineno - 1 >= len(lines):
            changes.append({"function": target["function"], "status": "skipped", "reason": "line OOB"})
            continue

        # Find the triple-quote in the line at col_offset.
        line_idx = desc_kw.value.lineno - 1
        line = lines[line_idx]
        col = desc_kw.value.col_offset

        # Determine which triple-quote style is used
        if line[col:col+3] == '"""':
            quote = '"""'
        elif line[col:col+3] == "'''":
            quote = "'''"
        else:
            changes.append({"function": target["function"], "status": "skipped", "reason": "not triple-quoted"})
            continue

        # Find the START byte offset in new_source
        # Sum of (lengths of lines 0..line_idx-1) + col_offset
        start_byte = sum(len(l) for l in lines[:line_idx]) + col

        # Find the matching closing triple-quote after start_byte+3
        end_byte = new_source.find(quote, start_byte + 3)
        if end_byte == -1:
            changes.append({"function": target["function"], "status": "skipped", "reason": "no closing triple-quote"})
            continue

        # Build the insertion: append a blank line + Data freshness section before the closing triple-quote.
        # Ensure we end the previous content cleanly.
        insertion = f"\n\n**Data freshness**\n{target['freshness_label']}"

        # Insert just before the closing quote (handling trailing whitespace)
        # Find the last non-whitespace char before end_byte to know if we need a newline.
        prefix_text = new_source[start_byte + 3:end_byte]
        if not prefix_text.endswith("\n"):
            patch = prefix_text + insertion + "\n"
        else:
            patch = prefix_text.rstrip() + insertion + "\n"

        new_chunk = quote + patch + quote
        old_chunk = new_source[start_byte:end_byte + 3]
        new_source = new_source[:start_byte] + new_chunk + new_source[end_byte + 3:]

        changes.append({
            "function": target["function"],
            "full_path": target["full_path"],
            "tier": target["tier"],
            "status": "patched",
            "delta_chars": len(new_chunk) - len(old_chunk),
        })

    if apply and new_source != source:
        path.write_text(new_source, encoding="utf-8")

    return {
        "file": str(path.relative_to(REPO_ROOT)),
        "total_routes": len(target_routes),
        "patched": sum(1 for c in changes if c["status"] == "patched"),
        "skipped": sum(1 for c in changes if c["status"] == "skipped"),
        "changes": changes,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write changes (default: dry-run)")
    parser.add_argument("--file", help="Retrofit a single file")
    args = parser.parse_args()

    cadence = load_cadence()

    if args.file:
        files = [Path(args.file).resolve()]
    else:
        files = sorted(p for p in V1_DIR.glob("*.py") if not p.name.startswith("_") and p.name != "__init__.py")

    total_patched = 0
    total_skipped = 0
    print(f"\nRetrofit Data freshness ({'APPLY' if args.apply else 'DRY-RUN'})")
    print("=" * 70)
    for f in files:
        report = retrofit_file(f, cadence, apply=args.apply)
        if "error" in report:
            print(f"  [ERR ] {report['file']} — {report['error']}")
            continue
        if report["patched"] == 0:
            continue
        print(f"  [{'PATCH' if args.apply else 'DRY'}] {report['file']} — patched={report['patched']} skipped={report['skipped']}")
        for c in report["changes"]:
            if c["status"] == "patched":
                print(f"          + {c['full_path']} ({c['tier']})")
        total_patched += report["patched"]
        total_skipped += report["skipped"]

    print("=" * 70)
    print(f"  Total patched: {total_patched}")
    print(f"  Total skipped: {total_skipped}")
    print(f"  Mode: {'APPLIED' if args.apply else 'DRY-RUN — no files written. Re-run with --apply.'}")


if __name__ == "__main__":
    main()
