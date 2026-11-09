"""Let an `INSERT ... ON CONFLICT DO UPDATE` skip a record that would change nothing.

Without a WHERE on DO UPDATE, PostgreSQL writes a new version of every conflicting row, changed
or not: a new tuple in every index, every BEFORE UPDATE trigger run (a touch trigger rebuilds the
row with its text bodies, a tsvector trigger re-indexes up to 200,000 characters), and the write
log grows with all of it. A touch trigger that keeps `updated_at` for an unchanged row cannot stop
the rewrite itself.

Two scheduled feeds did exactly that on every run (O236 RegDel acts, 6 Nov 2026: 150 KB of WAL per
act for one real change in 6,638; O237 agency items, 9 Nov: half the database's write log).

`only_if_changed(set_clause, table)` builds that WHERE from the SET list it guards, so the two
cannot drift: the row is written only when some target column differs from what its SET
expression would store (the same CASE guards and COALESCEs), compared null-safely. Columns that
always differ by design (`last_updated = NOW()`, `fetched_at = now()`) are left out with `skip`;
whoever needs "this was read" records it somewhere cheaper. A skipped record returns no row from
RETURNING, so the caller can count it as unchanged.
"""
from __future__ import annotations

import re
from typing import Iterable


def only_if_changed(set_clause: str, table: str, skip: Iterable[str] = ("last_updated",)) -> str:
    """The `WHERE (cols) IS DISTINCT FROM (set expressions)` for this SET list on `table`."""
    body, depth, quoted, items, cur = set_clause, 0, False, [], []
    i = 0
    while i < len(body):
        ch = body[i]
        if not quoted and body.startswith("--", i):      # a comment runs to the end of its line
            i = body.find("\n", i)
            i = len(body) if i < 0 else i
            continue
        if ch == "'":
            quoted = not quoted                          # '' inside a literal toggles twice
        elif not quoted and ch == "(":
            depth += 1
        elif not quoted and ch == ")":
            depth -= 1
        elif not quoted and depth == 0 and ch == ",":
            items.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    items.append("".join(cur))
    if depth or quoted:
        raise ValueError("unbalanced SET clause")
    skip = set(skip)
    cols, exprs = [], []
    for item in items:
        col, expr = item.split("=", 1)
        col = col.strip()
        if not re.fullmatch(r"[a-z_]+", col):
            raise ValueError(f"not a column: {col!r}")
        if col in skip:
            continue
        cols.append(f"{table}.{col}")
        exprs.append(expr.strip())
    if not cols:
        raise ValueError("nothing left to compare")
    return f"""
            WHERE ({", ".join(cols)})
                  IS DISTINCT FROM
                  ({", ".join(exprs)})"""
