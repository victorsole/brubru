"""Each answered question's answering Member, read from the answer itself (16 Oct 2026).

/api/v2/parliament/parliamentary-questions served answering_commissioner "European
Commission" on 5,833 answers (null on 275 more) whose text names the Member: "Answer given
by Executive Vice-President Séjourné on behalf of the European Commission". The answers job
wrote the institution there. This writes the named Member, and clears an institution name
where the answer names nobody (the institution stays in answering_institution).

    python3.12 scripts/backfill_question_answering_member.py            # dry run
    python3.12 scripts/backfill_question_answering_member.py --apply
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, text  # noqa: E402

from scripts.backfill_parl_question_answers import answering_member_from_text  # noqa: E402

INSTITUTIONS = ("European Commission", "Council of the EU", "European Central Bank")
ROWS = text("""SELECT id::text, answering_commissioner, left(text_answer, 1500) AS head
               FROM parliamentary_questions WHERE text_answer IS NOT NULL""")
STORE = text("""UPDATE parliamentary_questions SET answering_commissioner = :m, last_updated = now()
                WHERE id = CAST(:id AS uuid)""")


def wanted(current: str | None, head: str | None) -> str | None:
    named = answering_member_from_text(head)
    if named:
        return named
    return None if current in INSTITUTIONS else current


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    engine = create_engine(os.environ["DATABASE_URL"].replace("postgres://", "postgresql://", 1))
    with engine.connect() as c:
        rows = list(c.execute(ROWS))
    plan = [(r.id, r.answering_commissioner, wanted(r.answering_commissioner, r.head)) for r in rows]
    plan = [p for p in plan if p[1] != p[2]]
    print(f"[INFO] {len(rows)} answered; {len(plan)} to change")
    print("[INFO] from:", dict(collections.Counter(p[1] for p in plan).most_common(4)))
    print("[INFO] to (top):", dict(collections.Counter(p[2] for p in plan).most_common(6)))
    if not args.apply:
        print("[DRY RUN] nothing written")
        return 0
    with engine.begin() as c:
        for qid, _, m in plan:
            c.execute(STORE, {"id": qid, "m": m})
    print(f"[DONE] {len(plan)} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
