#!/usr/bin/env python3.12
"""
Audit GUIDE_KEYWORD_TRIGGERS for the failure modes that hide in a 13,000-line
dict literal.

Run after ANY bulk trigger change:

    cd backend && python3.12 scripts/audit_guide_triggers.py

Checks
------
1. DUPLICATE KEYS. Python keeps the LAST occurrence in a dict literal, so an
   entry added near the top of the file is silently discarded. This is not
   theoretical: on 6 August 2026 a block of new triggers for CSRD, CSDDD and
   PPWR was inserted at the top, parsed cleanly, raised the trigger count, and
   changed nothing at all, because every key already existed further down. The
   audit found 396 duplicated keys shadowing 449 entries. If you are adding
   overrides, put them at the END of the dict.

2. ORPHAN TARGETS. A trigger pointing at a guide stem that has no .md file can
   never fire.

3. ZERO-TRIGGER GUIDES. A guide no trigger points at is unreachable by keyword.
   CSRD and CSDDD were in this state while live as public canon pages.

Exit code is 1 when orphans or zero-trigger guides exist, 0 otherwise.
Duplicates are reported but do not fail the run, since 396 of them predate this
script and clearing them is its own piece of work.
"""

import collections
import glob
import os
import re
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)

LOADER = os.path.join(HERE, "knowledge_base", "knowledge_loader.py")
GUIDES = os.path.join(HERE, "knowledge_base", "guides", "*.md")


def main() -> int:
    src = open(LOADER, encoding="utf-8").read()
    start = src.index("GUIDE_KEYWORD_TRIGGERS: Dict[str, List[str]] = {")
    end = src.index("\n}\n", start)
    body = src[start:end]

    literal_keys = re.findall(r"^\s*'((?:[^'\\]|\\.)*)'\s*:\s*\[", body, re.M)
    counts = collections.Counter(literal_keys)
    dupes = {k: n for k, n in counts.items() if n > 1}

    from knowledge_base.knowledge_loader import GUIDE_KEYWORD_TRIGGERS as G

    stems = {os.path.basename(p)[:-3] for p in glob.glob(GUIDES)}
    targets = {t for v in G.values() for t in v}
    orphans = sorted(targets - stems)
    untriggered = sorted(stems - targets)

    print(f"literal entries   : {len(literal_keys)}")
    print(f"effective keys    : {len(G)}")
    print(f"guides on disk    : {len(stems)}")
    print()
    print(f"[{'WARN' if dupes else 'OK'}] duplicate keys: {len(dupes)} "
          f"(shadowing {sum(n - 1 for n in dupes.values())} entries)")
    if dupes:
        worst = sorted(dupes.items(), key=lambda kv: -kv[1])[:10]
        print(f"       worst: {worst}")
        print("       NOTE: an entry added ABOVE a duplicate is dead. Append "
              "overrides at the END of the dict.")
    print(f"[{'FAIL' if orphans else 'OK'}] orphan targets: {len(orphans)} {orphans[:8]}")
    print(f"[{'FAIL' if untriggered else 'OK'}] zero-trigger guides: "
          f"{len(untriggered)} {untriggered[:8]}")

    return 1 if (orphans or untriggered) else 0


if __name__ == "__main__":
    raise SystemExit(main())
