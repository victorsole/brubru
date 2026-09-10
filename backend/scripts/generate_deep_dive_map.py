#!/usr/bin/env python3.12
"""Regenerate the Python deep-dive map from its TypeScript source of truth.

WHY A GENERATOR AND NOT A PARSE-AT-IMPORT
-----------------------------------------
The obvious fix for the drift found on 10 September 2026 -- the TS map declared
12 deep-dives while `services/comparator/deep_dives.py` held 8 -- is to parse the
TS file at import and delete the copy. That was written, and then thrown away.

`backend/railway.json` sets the Docker build context to `backend/`, and the
Dockerfile does `COPY . /app`. **`frontend/` is not in the production image.**
Parsing at import would have raised on boot and taken the backend down. The image
layout is a fact to check, not to assume.

So the Python list stays a committed artefact -- it must, to ship -- and drift is
prevented by a test instead: tests/test_deep_dive_map_sync.py fails when the two
disagree, and points here.

USAGE
    python3.12 -m backend.scripts.generate_deep_dive_map --check   # exit 1 on drift
    python3.12 -m backend.scripts.generate_deep_dive_map --write   # rewrite the block
"""
import argparse
import pathlib
import re
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
TS_MAP = _REPO_ROOT / "frontend" / "src" / "utils" / "deep_dive_map.ts"
PY_MAP = _REPO_ROOT / "backend" / "services" / "comparator" / "deep_dives.py"

_BEGIN = "# --- BEGIN GENERATED (scripts/generate_deep_dive_map.py) ---"
_END = "# --- END GENERATED ---"

# COM(2026) 321 -> 52026PC0321. Checked against all eight hand-written entries
# this replaced: 8/8 identical, including the two-document pharma package.
_COM_RE = re.compile(r"COM\((\d{4})\)\s*(\d{1,4})")


def celex_from_com(com_reference: str) -> list[str]:
    return [f"5{y}PC{int(n):04d}" for y, n in _COM_RE.findall(com_reference or "")]


def parse_ts() -> list[dict]:
    text = TS_MAP.read_text(encoding="utf-8")
    out: list[dict] = []
    for block in re.split(r"\n\s*\{", text):
        base = re.search(r"basePath:\s*'([^']+)'", block)
        if not base:
            continue

        def field(name: str):
            m = re.search(name + r":\s*'([^']*)'", block)
            return m.group(1) if m else None

        com = field("comReference") or ""
        out.append({
            "short_title": field("shortTitle") or "",
            "title": field("title") or "",
            "com_reference": com or None,
            "procedure_ref": field("procedureRef") or None,
            "base_path": base.group(1),
            "celex_candidates": celex_from_com(com),
        })
    if not out:
        raise SystemExit(f"[ERROR] parsed 0 deep-dives from {TS_MAP}; the format changed")
    return out


def render(entries: list[dict]) -> str:
    lines = [_BEGIN,
             f"# {len(entries)} deep-dives, generated from frontend/src/utils/deep_dive_map.ts.",
             "# Do NOT edit by hand: run scripts/generate_deep_dive_map.py --write.",
             "DEEP_DIVES: List[DeepDive] = ["]
    for e in entries:
        lines.append("    {")
        for key in ("short_title", "title", "com_reference", "procedure_ref", "base_path"):
            lines.append(f"        {key!r}: {e[key]!r},")
        lines.append(f"        'celex_candidates': {e['celex_candidates']!r},")
        lines.append("    },")
    lines.append("]")
    lines.append(_END)
    return "\n".join(lines)


def current_block() -> str | None:
    text = PY_MAP.read_text(encoding="utf-8")
    if _BEGIN not in text or _END not in text:
        return None
    return text[text.index(_BEGIN): text.index(_END) + len(_END)]


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    args = ap.parse_args()

    wanted = render(parse_ts())
    have = current_block()

    if args.check:
        if have == wanted:
            print(f"[OK] deep-dive map in sync ({wanted.count('base_path')} entries)")
            return 0
        print("[DRIFT] the Python map no longer matches the TS source of truth.")
        print("        run: python3.12 -m backend.scripts.generate_deep_dive_map --write")
        return 1

    text = PY_MAP.read_text(encoding="utf-8")
    if have is None:
        raise SystemExit(f"[ERROR] no generated block found in {PY_MAP}; add the markers first")
    PY_MAP.write_text(text.replace(have, wanted), encoding="utf-8")
    print(f"[OK] wrote {wanted.count('base_path')} entries into {PY_MAP}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
