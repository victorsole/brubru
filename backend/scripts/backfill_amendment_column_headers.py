"""Amendments without their table's column headings, typed by what they do (16 Oct 2026).

/api/v2/parliament/amendments served 63,730 proposed texts beginning "Amendment" and 59,798
original texts beginning "Text proposed by the Commission": the parser kept the headings
when they share a row with the text. A new provision's original column held the heading
alone, so 10,279 additions read 'modification', and 4,464 "Amendment / deleted" read
'modification' too. This rewrites the stored texts as the fixed parser reads them, types
each amendment with the parser's own rule, and clears a political group that is not one
(a committee code, "LIBE").

    python3.12 scripts/backfill_amendment_column_headers.py            # dry run
    python3.12 scripts/backfill_amendment_column_headers.py --apply
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from services.parsers.ep_amendment_parser import GROUP_ALIASES, EPAmendmentParser, strip_column_header  # noqa: E402

GROUPS = set(GROUP_ALIASES.values())
ROWS = text("""SELECT id::text, original_text, proposed_text, amendment_type, political_group, on_behalf_of_group
               FROM mep_amendments""")
STORE = text("""UPDATE mep_amendments SET original_text = :o, proposed_text = :p, amendment_type = :t,
                       political_group = :g, on_behalf_of_group = :b, updated_at = now()
                WHERE id = CAST(:id AS uuid)""")


def corrected(row) -> dict | None:
    """The row as the fixed parser would store it, or None when nothing changes."""
    o, p = strip_column_header(row["original_text"]), strip_column_header(row["proposed_text"])
    t = EPAmendmentParser()._classify_amendment_type(o, p)
    g = row["political_group"] if row["political_group"] in GROUPS else None
    b = bool(row["on_behalf_of_group"]) and g is not None
    new = {"o": o, "p": p, "t": t, "g": g, "b": b}
    old = {"o": (row["original_text"] or "").strip(), "p": (row["proposed_text"] or "").strip(),
           "t": row["amendment_type"], "g": row["political_group"], "b": bool(row["on_behalf_of_group"])}
    return None if new == old else new


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    with engine.connect() as c:
        rows = [dict(r._mapping) for r in c.execute(ROWS)]
    plan = [(r, corrected(r)) for r in rows]
    plan = [(r, n) for r, n in plan if n]
    types = collections.Counter((r["amendment_type"], n["t"]) for r, n in plan if r["amendment_type"] != n["t"])
    groups = collections.Counter(r["political_group"] for r, n in plan if r["political_group"] != n["g"])
    print(f"[INFO] {len(rows)} amendments; {len(plan)} to rewrite")
    print(f"[INFO] type changes: {dict(types)}")
    print(f"[INFO] group cleared: {dict(groups)}")
    if not args.apply:
        print("[DRY RUN] nothing written")
        return 0
    with engine.begin() as c:
        for i, (r, n) in enumerate(plan, 1):
            c.execute(STORE, {"id": r["id"], **n})
            if i % 5000 == 0:
                print(f"   ...{i}", flush=True)
    print(f"[DONE] rewrote {len(plan)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
