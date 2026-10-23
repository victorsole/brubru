"""Plain-text fields hold characters, not HTML entities (16 Oct 2026).

The content audit read "(S&amp;D)" in 1,362 parliamentary questions, "Mjölby &amp; Motala"
and "&amp;quot;" in 194 TED tender titles, "LOC&amp;PAS" in Commission documents and
implementing acts, "&#039;" in an RSB title: text taken from XML or HTML without decoding.
This decodes the PLAIN-TEXT columns listed below (never a body_html column, where an entity
is correct markup). A doubly escaped "&amp;quot;" is decoded twice.

    python3.12 scripts/decode_text_entities.py            # dry run
    python3.12 scripts/decode_text_entities.py --apply
"""
from __future__ import annotations

import argparse
import html
import os
import re
import sys

from sqlalchemy import create_engine, text

# (table, primary key, plain-text columns, column to stamp as changed or None)
TARGETS = (
    ("parliamentary_questions", "id", ("subject", "text_question", "text_answer"), "last_updated"),
    ("tenders", "id", ("title", "description", "official_name", "summary"), "updated_at"),
    ("secondary_acts", "id", ("title", "description", "text_body"), "last_updated"),
    ("commission_documents", "id", ("title", "text_body"), "last_updated"),
    ("rsb_opinions", "id", ("title", "summary", "full_text"), "last_updated"),
)
_ENTITY = re.compile(r"&(?:amp|lt|gt|quot|apos|nbsp|#\d{2,6}|#x[0-9a-fA-F]{2,5});")


def decode(value: str | None) -> str | None:
    """Entities to characters, twice at most ("&amp;quot;" -> '"')."""
    if not value or not _ENTITY.search(value):
        return value
    out = html.unescape(value)
    if _ENTITY.search(out):
        out = html.unescape(out)
    return out.replace("\xa0", " ")


def _existing(engine, table: str, cols) -> list[str]:
    with engine.connect() as c:
        have = {r[0] for r in c.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = :t"), {"t": table})}
    return [col for col in cols if col in have], have


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    total = 0
    for table, pk, cols, stamp in TARGETS:
        cols, have = _existing(engine, table, cols)
        if not cols:
            continue
        where = " OR ".join(f"{c} ~ '&(amp|lt|gt|quot|apos|nbsp|#[0-9]+|#x[0-9a-fA-F]+);'" for c in cols)
        with engine.connect() as c:
            rows = list(c.execute(text(f"SELECT {pk}::text AS pk, {', '.join(cols)} FROM {table} WHERE {where}")))
        changes, per = [], dict.fromkeys(cols, 0)
        for r in rows:
            new = {col: decode(getattr(r, col)) for col in cols}
            changed = [col for col in cols if new[col] != getattr(r, col)]
            if changed:
                changes.append((r.pk, new))
                for col in changed:
                    per[col] += 1
        print(f"[INFO] {table}: {len(changes)} row(s) {per}")
        if args.apply and changes:
            sets = ", ".join(f"{col} = :{col}" for col in cols)
            if stamp and stamp in have:
                sets += f", {stamp} = now()"
            with engine.begin() as c:
                for pkv, new in changes:
                    c.execute(text(f"UPDATE {table} SET {sets} WHERE {pk}::text = :pk"), {"pk": pkv, **new})
        total += len(changes)
    print(("[DONE] decoded " if args.apply else "[DRY RUN] would decode ") + f"{total} row(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
