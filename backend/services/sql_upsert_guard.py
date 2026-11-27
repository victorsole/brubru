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

Comparing is a READ, and a long text is read whole to be compared (27 Nov 2026, O245): the
guard on the agency items read every stored article back from the long-text store on every run,
about 40% of the database's disk reads, to find that nothing had changed. A column whose SET
expression already says when it changes (a "longer text wins" CASE) is given that test in
`changed_when` instead of being compared by value: the test can be written so the stored text
is never opened (its size is in the row; `octet_length` reads it without fetching the text).
"""
from __future__ import annotations

import re
from typing import Iterable, Mapping, Optional


def only_if_changed(set_clause: str, table: str, skip: Iterable[str] = ("last_updated",),
                    changed_when: Optional[Mapping[str, str]] = None) -> str:
    """The `WHERE (cols) IS DISTINCT FROM (set expressions)` for this SET list on `table`.

    `changed_when` maps a column to a boolean SQL test that is true exactly when its SET
    expression would store a different value. Such a column is left out of the value
    comparison and its test is OR-ed in, so its stored value is never read to be compared.
    Every column named there must be in the SET list.
    """
    changed_when = dict(changed_when or {})
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
    cols, exprs, tests = [], [], []
    for item in items:
        col, expr = item.split("=", 1)
        col = col.strip()
        if not re.fullmatch(r"[a-z_]+", col):
            raise ValueError(f"not a column: {col!r}")
        if col in skip:
            continue
        if col in changed_when:
            tests.append(f"({changed_when.pop(col).strip()})")
            continue
        cols.append(f"{table}.{col}")
        exprs.append(expr.strip())
    if changed_when:
        raise ValueError(f"changed_when names columns the SET list does not set: {sorted(changed_when)}")
    if not cols:
        raise ValueError("nothing left to compare")
    compared = f"""({", ".join(cols)})
                  IS DISTINCT FROM
                  ({", ".join(exprs)})"""
    if not tests:
        return f"""
            WHERE {compared}"""
    return f"""
            WHERE ({compared}
               OR """ + """
               OR """.join(tests) + ")"
