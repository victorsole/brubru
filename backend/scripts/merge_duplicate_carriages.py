"""Merge legislative_carriages rows that share an OEIL procedure reference.

Why this exists (found by /news, 4 September 2026)
--------------------------------------------------
Three procedures exist TWICE in `legislative_carriages`, because different ingest
paths (LEGISLATIVE_TRAIN, EURLEX, OEIL_DIRECT) each created their own row for the
same procedure and nothing enforces uniqueness on `oeil_procedure_ref`:

    2026/0013(COD)  Digital Networks Act        2 user tracks + 0
    2026/0068(COD)  Industrial Accelerator Act  6 user tracks + 5
    2026/0074(COD)  EU Inc. 28th regime         1 user track  + 3

Users are tracking BOTH copies. A user on copy A never sees documents or events
attached to copy B, and Position Analysis generates two snapshots for the same
file that disagree with each other (one 'full/high', one 'partial/medium').

The winner is the row with the most user tracks, then the richest content, then
the earliest first_seen -- keeping the row people already point at.

Run:
    python3.12 scripts/merge_duplicate_carriages.py            # dry run
    python3.12 scripts/merge_duplicate_carriages.py --apply
"""
import argparse
import os
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(os.path.join(_REPO_ROOT, "backend", ".env"))

# Tables that carry a carriage_id and must be repointed at the winner.
CHILD_TABLES = [
    ("user_carriage_tracks", "carriage_id"),
    ("file_position_snapshots", "carriage_id"),
]


def _child_tables(conn):
    """Only touch tables that actually exist and actually have the column."""
    live = []
    for tbl, col in CHILD_TABLES:
        ok = conn.execute(
            text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ),
            {"t": tbl, "c": col},
        ).first()
        if ok:
            live.append((tbl, col))
        else:
            print(f"  [skip] {tbl}.{col} does not exist")
    return live


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write; default is a dry run")
    args = ap.parse_args()

    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://")
    engine = create_engine(url)

    with engine.connect() as conn:
        children = _child_tables(conn)
        refs = [
            r[0]
            for r in conn.execute(
                text(
                    "SELECT oeil_procedure_ref FROM legislative_carriages "
                    "WHERE oeil_procedure_ref IS NOT NULL "
                    "GROUP BY 1 HAVING count(*) > 1 ORDER BY 1"
                )
            )
        ]
        if not refs:
            print("[OK] no duplicate procedure references. Nothing to do.")
            return 0

        plan = []
        for ref in refs:
            rows = conn.execute(
                text(
                    """SELECT c.id, c.source, c.first_seen,
                              coalesce(c.short_title, c.title) AS title,
                              length(coalesce(c.oeil_text_body, '')
                                     || coalesce(c.description, '')) AS content_len,
                              (SELECT count(*) FROM user_carriage_tracks t
                                WHERE t.carriage_id = c.id) AS tracks
                         FROM legislative_carriages c
                        WHERE c.oeil_procedure_ref = :r"""
                ),
                {"r": ref},
            ).mappings().all()
            # Most user tracks wins, then richest content, then oldest row.
            ordered = sorted(
                rows,
                key=lambda r: (-r["tracks"], -r["content_len"], r["first_seen"]),
            )
            plan.append((ref, ordered[0], ordered[1:]))

        print(f"{'APPLY' if args.apply else 'DRY RUN'} -- {len(plan)} duplicate reference(s)\n")
        for ref, win, losers in plan:
            print(f"{ref}")
            print(f"  KEEP  {win['id']}  {win['source']:<18} tracks={win['tracks']}  {str(win['title'])[:46]}")
            for l in losers:
                print(f"  MERGE {l['id']}  {l['source']:<18} tracks={l['tracks']}  {str(l['title'])[:46]}")
            print()

    if not args.apply:
        print("Dry run only. Re-run with --apply to merge.")
        return 0

    moved = {t: 0 for t, _ in children}
    deleted = 0
    with engine.begin() as conn:
        for ref, win, losers in plan:
            for l in losers:
                for tbl, col in children:
                    if tbl == "user_carriage_tracks":
                        # A user may already track BOTH copies; repointing would
                        # violate the (user_id, carriage_id) uniqueness, so drop
                        # the redundant row instead of moving it.
                        conn.execute(
                            text(
                                f"DELETE FROM {tbl} l USING {tbl} k "
                                f"WHERE l.{col} = :loser AND k.{col} = :win "
                                f"AND l.user_id = k.user_id"
                            ),
                            {"loser": l["id"], "win": win["id"]},
                        )
                    n = conn.execute(
                        text(f"UPDATE {tbl} SET {col} = :win WHERE {col} = :loser"),
                        {"win": win["id"], "loser": l["id"]},
                    ).rowcount
                    moved[tbl] += n
                # Track count decides the SURVIVOR, but the survivor may carry
                # the raw "Proposal for a REGULATION OF THE EUROPEAN PARLIAMENT..."
                # title while the loser carries the plain-language name users
                # recognise. Keep the better name on the row that survives.
                def _plain(t):
                    return t and not t.lower().startswith(("proposal for", "establishing a framework"))
                if _plain(l["title"]) and not _plain(win["title"]):
                    conn.execute(
                        text("UPDATE legislative_carriages SET short_title = :t WHERE id = :i"),
                        {"t": l["title"], "i": win["id"]},
                    )
                    print(f"  [title] {ref}: kept plain-language name {l['title'][:40]!r}")
                deleted += conn.execute(
                    text("DELETE FROM legislative_carriages WHERE id = :i"),
                    {"i": l["id"]},
                ).rowcount
    for tbl, n in moved.items():
        print(f"[OK] repointed {n} row(s) in {tbl}")
    print(f"[OK] deleted {deleted} duplicate carriage row(s)")
    print("[INFO] Add a UNIQUE index on legislative_carriages(oeil_procedure_ref) "
          "in a migration so this cannot recur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
