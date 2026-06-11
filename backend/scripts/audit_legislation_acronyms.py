#!/usr/bin/env python3.12
"""
Audit knowledge_base/institutions/legislation_acronyms.json for the data-quality
defects that poison the chat linkifier (_linkify_legislation).

Background: the file was bulk auto-ingested from Formex XML, and the ingestion
mis-keyed popular names / acronyms onto IMPLEMENTING and DELEGATED instruments
that merely reference the base act -- e.g. "Digital Services Act" -> 32023R1201
(an implementing reg) instead of the real DSA 32022R2065 (the 11 June 2026
production bug). See memory/feedback_linkify_override_celex.md.

This script flags four defect classes. It is read-only (no writes). Run after
any edit to the acronyms DB, and in CI, to keep the linkifier honest.

  python3.12 scripts/audit_legislation_acronyms.py [--harmful-only]

Exit code is non-zero if any name->CELEX conflict exists (the hard defect that
caused the prod bug); the softer classes are reported but do not fail the run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

DB_PATH = (
    Path(__file__).resolve().parent.parent
    / "knowledge_base" / "institutions" / "legislation_acronyms.json"
)

# Keys that are inert in the linkifier (mirrors _linkify_legislation STEP 2
# skips): <=2 chars, pure digits, Roman numerals, denylist. A wrong CELEX on one
# of these cannot mislead a user because the bare key never appears in answers.
_DENYLIST = {
    "ETF", "COVID-19", "COVID", "ACT", "NEW", "API", "ART", "EOV", "SET", "END",
    "KEY", "ONE", "TWO", "AID", "AIR", "GAS", "NET", "USE", "WAR",
}
_NON_BASE_MARKERS = ("Implementing ", "Delegated ")


def is_inert(key: str) -> bool:
    if len(key) <= 2 or key.isdigit():
        return True
    if re.fullmatch(r"[IVXLCDM]+", key):
        return True
    return key.upper() in _DENYLIST


def parse_celex(celex: str):
    m = re.fullmatch(r"(\d)(\d{4})([A-Z]{1,2})(\d{3,4})", celex or "")
    return (m.group(2), int(m.group(4))) if m else None  # (year, number)


def title_actnum(full_title: str):
    """Primary act (year, number) named in the title, robust to both numbering
    conventions: 'No 231/2014' (number/year) and '2018/1240' (year/number)."""
    m = re.search(r"\((?:EU|EC|EEC|Euratom|CFSP)\)\s*(?:No\s*)?(\d{1,4})/(\d{1,4})", full_title or "")
    if not m:
        return None
    a, b = int(m.group(1)), int(m.group(2))
    if 1950 <= a <= 2099:
        return (str(a), b)
    if 1950 <= b <= 2099:
        return (str(b), a)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harmful-only", action="store_true",
                    help="only report non-inert keys (those that can actually mislink)")
    args = ap.parse_args()

    db = json.loads(DB_PATH.read_text(encoding="utf-8"))["acronyms"]

    # Class 1 (HARD): same normalised name -> multiple CELEX. This is what caused
    # the prod bug. Must be empty.
    names = defaultdict(set)
    for key, info in db.items():
        celex = info.get("celex")
        if not celex:
            continue
        names[key.strip().lower()].add(celex)
        full = (info.get("full_name") or "").strip().lower()
        if full:
            names[full].add(celex)
    conflicts = {k: sorted(s) for k, s in names.items() if len(s) > 1}

    # Classes 2-4 (SOFT): per-entry defects.
    malformed, mismatch, non_base = [], [], []
    for key, info in db.items():
        if args.harmful_only and is_inert(key):
            continue
        celex = info.get("celex")
        ft = info.get("full_title") or ""
        pc = parse_celex(celex)
        if not pc:
            malformed.append((key, celex))
            continue
        tn = title_actnum(ft)
        if tn and (tn[0] != pc[0] or tn[1] != pc[1]):
            mismatch.append((key, celex, ft[:70]))
        if any(mk in ft for mk in _NON_BASE_MARKERS):
            non_base.append((key, celex, ft[:70]))

    print(f"DB: {DB_PATH}")
    print(f"entries: {len(db)}\n")

    print(f"[Class 1 HARD] name->CELEX conflicts: {len(conflicts)}")
    for k, s in sorted(conflicts.items()):
        print(f"    {k!r} -> {s}")

    scope = "non-inert" if args.harmful_only else "all"
    print(f"\n[Class 2] malformed/empty CELEX ({scope}): {len(malformed)}")
    for x in malformed[:50]:
        print("   ", x)

    print(f"\n[Class 3] title<->CELEX contradiction ({scope}): {len(mismatch)}")
    for x in mismatch[:80]:
        print("   ", x)

    print(f"\n[Class 4] keyed onto implementing/delegated act ({scope}): {len(non_base)}")
    print("    (these are NEUTRALISED in the linkifier by _is_linkify_safe_act;")
    print("     listed for data-hygiene follow-up, not a safety risk)")
    for x in non_base[:120]:
        print("   ", x)

    if conflicts:
        print("\nFAIL: name->CELEX conflict present (linkifier poison). Fix before shipping.")
        return 1
    print("\nOK: no name->CELEX conflicts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
