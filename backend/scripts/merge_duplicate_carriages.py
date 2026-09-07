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

# Child tables are DISCOVERED from the catalogue, never hardcoded.
#
# Why (found by the /news audit, 7 September 2026). This script used to carry a
# hardcoded two-entry list -- user_carriage_tracks and file_position_snapshots.
# The schema has ELEVEN foreign keys pointing at legislative_carriages, and the
# nine that were missing are not harmless:
#
#   amendments.carriage_id            ON DELETE SET NULL  -> 28 user amendments on
#                                     the EU Inc. duplicate would have been silently
#                                     ORPHANED from their file. No error, no crash.
#   procedure_snapshots.carriage_id   ON DELETE CASCADE   -> 288 daily snapshots
#                                     silently destroyed.
#   committee_work_items....          ON DELETE NO ACTION -> the DELETE would simply
#                                     fail, which is the only reason the damage above
#                                     had not already happened.
#
# A hardcoded list of child tables goes stale the moment someone adds a foreign
# key. Reading pg_constraint cannot.
#
# Two tables are UNIQUE on the carriage column, so their rows cannot be repointed
# -- they would collide with the winner's own row. Their loser rows are deleted
# instead; both are derived series that the winner already carries for the same
# period and that regenerate on the next run.
DELETE_INSTEAD_OF_REPOINT = {
    "file_position_snapshots",   # UNIQUE (carriage_id)
    "procedure_snapshots",       # UNIQUE (carriage_id, snapshot_date)
}

# For those tables, the rest of the unique key beyond the carriage column. A
# loser row is MOVED when the winner has no row on the same key, and only
# DELETED when it genuinely collides.
UNIQUE_KEY_EXTRA = {
    "file_position_snapshots": [],                # UNIQUE is the carriage alone
    "procedure_snapshots": ["snapshot_date"],
}


def _child_tables(conn):
    """Every table with a FK to legislative_carriages, read from the catalogue."""
    rows = conn.execute(
        text(
            """
            SELECT src.relname AS tbl, att.attname AS col,
                   CASE con.confdeltype WHEN 'c' THEN 'CASCADE' WHEN 'n' THEN 'SET NULL'
                        WHEN 'r' THEN 'RESTRICT' WHEN 'd' THEN 'SET DEFAULT'
                        ELSE 'NO ACTION' END AS on_delete
              FROM pg_constraint con
              JOIN pg_class src ON src.oid = con.conrelid
              JOIN pg_class tgt ON tgt.oid = con.confrelid
              JOIN unnest(con.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
              JOIN pg_attribute att ON att.attrelid = src.oid AND att.attnum = k.attnum
             WHERE con.contype = 'f' AND tgt.relname = 'legislative_carriages'
             ORDER BY src.relname
            """
        )
    ).mappings().all()
    live = [(r["tbl"], r["col"], r["on_delete"]) for r in rows]
    print(f"  [schema] {len(live)} table(s) reference legislative_carriages:")
    for tbl, col, rule in live:
        how = "DELETE loser rows" if tbl in DELETE_INSTEAD_OF_REPOINT else "repoint"
        print(f"           {tbl}.{col}  (ON DELETE {rule})  -> {how}")
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

    moved = {t: 0 for t, _, _ in children}
    collided: dict = {}
    deleted = 0
    with engine.begin() as conn:
        for ref, win, losers in plan:
            for l in losers:
                for tbl, col, _rule in children:
                    if tbl in DELETE_INSTEAD_OF_REPOINT:
                        # UNIQUE on the carriage column, so a blanket repoint would
                        # collide with the winner's own row -- but a blanket DELETE
                        # is wrong too. Caught by the audit on 7 September 2026:
                        # 2026/0068(COD)'s loser held the ONLY file_position_snapshot
                        # and an unconditional delete destroyed it.
                        # Correct order: repoint every loser row the winner does NOT
                        # already cover, then delete only what genuinely collides.
                        keycols = UNIQUE_KEY_EXTRA.get(tbl, [])
                        match = " AND ".join([f"k.{c} = l.{c}" for c in keycols]) or "TRUE"
                        n_moved = conn.execute(
                            text(
                                f"UPDATE {tbl} l SET {col} = :win "
                                f" WHERE l.{col} = :loser "
                                f"   AND NOT EXISTS (SELECT 1 FROM {tbl} k "
                                f"                    WHERE k.{col} = :win AND {match})"
                            ),
                            {"win": win["id"], "loser": l["id"]},
                        ).rowcount
                        n_del = conn.execute(
                            text(f"DELETE FROM {tbl} WHERE {col} = :loser"),
                            {"loser": l["id"]},
                        ).rowcount
                        moved[tbl] += n_moved
                        collided[tbl] = collided.get(tbl, 0) + n_del
                        continue
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
                # Field-level merge. The winner is chosen on user tracks, which
                # says nothing about which row carries the richer metadata. On
                # 2026/0013(COD) the winner had NO celex while the loser held
                # 52026PC0016 -- the identifier that powers the EUR-Lex link and
                # the Amendator example. Deleting the loser without merging would
                # have thrown it away silently.
                conn.execute(
                    text(
                        """
                        UPDATE legislative_carriages w SET
                          celex_numbers = (SELECT array(SELECT DISTINCT unnest(
                                             coalesce(w.celex_numbers,'{}') ||
                                             coalesce(l.celex_numbers,'{}')) ORDER BY 1)),
                          policy_areas  = (SELECT array(SELECT DISTINCT unnest(
                                             coalesce(w.policy_areas,'{}') ||
                                             coalesce(l.policy_areas,'{}')) ORDER BY 1)),
                          lead_committee = coalesce(w.lead_committee, l.lead_committee)
                        FROM legislative_carriages l
                        WHERE w.id = :win AND l.id = :loser
                        """
                    ),
                    {"win": win["id"], "loser": l["id"]},
                )
                deleted += conn.execute(
                    text("DELETE FROM legislative_carriages WHERE id = :i"),
                    {"i": l["id"]},
                ).rowcount
    for tbl, n in moved.items():
        # Two tables have their loser rows DELETED, not moved (UNIQUE on the
        # carriage column). Saying "repointed" for those misreports what happened.
        print(f"[OK] repointed {n} row(s) in {tbl}"
              + (f" (+{collided[tbl]} deleted as genuine duplicates)" if collided.get(tbl) else ""))
    print(f"[OK] deleted {deleted} duplicate carriage row(s)")
    print("[INFO] Add a UNIQUE index on legislative_carriages(oeil_procedure_ref) "
          "in a migration so this cannot recur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
