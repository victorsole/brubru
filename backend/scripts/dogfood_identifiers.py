#!/usr/bin/env python3
"""
Identifier-resolution dogfood for /news.

Reads identifiers from stdin or a file (one per line, OR free text from
which they're scanned), passes each through
`services/identifiers/standard_identifier_resolver`, and reports
pass/fail. The /news skill calls this every run on the daily scrape's
identifier soup so we catch:

  - typos in EU sources (e.g. malformed CELEX)
  - parser drift (a new pattern shape we don't handle)

Output (stdout, JSON):
    {
        "scanned_at": "...",
        "input_lines": N,
        "matched": [{"kind": "celex", "value": "32016R0679", "canonical_url": "..."}],
        "unmatched_lines": ["..."],
        "summary": {"celex": 12, "ecli": 3, ...}
    }

Exit code:
    0 - all input lines matched at least one identifier OR input was free text
    1 - one or more lines that *looked* like identifiers (digits/colons) failed to match

Run:
    echo "32016R0679" | python3.12 backend/scripts/dogfood_identifiers.py
    python3.12 backend/scripts/dogfood_identifiers.py --file refs.txt
    python3.12 backend/scripts/dogfood_identifiers.py --strict --file refs.txt

Cadence: every /news run, free piggyback on existing scrape (Step 1.dogfood).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from services.identifiers.standard_identifier_resolver import (  # noqa: E402
    parse_all,
    recognise,
)

# Lines that *look* identifier-shaped but fail to recognise() are
# suspicious. This regex is intentionally loose — the goal is to flag
# things we *should* be able to match.
_LOOKS_LIKE_ID = re.compile(
    r"(?:"
    r"\d[A-Z\d]?\d{4}[A-Z]"          # CELEX-ish
    r"|ECLI:[A-Z]{2}:"                # ECLI-ish
    r"|COM\(\d{4}\)"                  # COM-ish
    r"|\d{4}/\d{4}\(COD\)"             # OEIL-ish
    r"|\bPE\d{3,}"                    # PE-number
    r"|http://publications\.europa\.eu/resource/"
    r")",
    re.IGNORECASE,
)


def _read_input(file: str | None) -> List[str]:
    if file:
        return Path(file).read_text(encoding="utf-8").splitlines()
    return sys.stdin.read().splitlines()


def main() -> int:
    p = argparse.ArgumentParser(description="Run identifier resolver against a list of refs.")
    p.add_argument("--file", default=None, help="Path to file with one ref per line")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if any identifier-shaped line fails to recognise()",
    )
    args = p.parse_args()

    lines = [ln.strip() for ln in _read_input(args.file) if ln.strip()]
    matched = []
    unmatched_suspicious: List[str] = []
    summary: Counter = Counter()

    for ln in lines:
        # Try anchored recognise() first (single ref per line).
        m = recognise(ln)
        if m:
            matched.append({
                "kind": m.kind.value,
                "value": m.value,
                "canonical_url": m.canonical_url,
                "brubru_url": m.brubru_url,
            })
            summary[m.kind.value] += 1
            continue

        # Fall back to parse_all (free text containing one or more refs).
        embedded = parse_all(ln)
        if embedded:
            for em in embedded:
                matched.append({
                    "kind": em.kind.value,
                    "value": em.value,
                    "canonical_url": em.canonical_url,
                    "brubru_url": em.brubru_url,
                })
                summary[em.kind.value] += 1
            continue

        # No match — was the line identifier-shaped? If yes, flag it.
        if _LOOKS_LIKE_ID.search(ln):
            unmatched_suspicious.append(ln)

    result = {
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "input_lines": len(lines),
        "matched_count": len(matched),
        "matched": matched,
        "unmatched_suspicious": unmatched_suspicious,
        "summary": dict(summary),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.strict and unmatched_suspicious:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
