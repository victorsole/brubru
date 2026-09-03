"""
Create legislative_carriages rows for EP committee procedures that have eMeeting
documents but no carriage, so those documents stop being unreachable in MEUB.

The gap (eMeeting audit, 3 September 2026)
-------------------------------------------
Every MEUB surface that shows committee documents -- Position Analysis, the
tracked-file detail card, Amendments, Votes, Transcripts -- reaches them through
`services/linking/emeeting_links.py`, which takes a list of OEIL procedure refs
from the CALLER. The caller gets those refs from the user's tracked files, and a
tracked file is a `legislative_carriages` row. So a procedure with no carriage
cannot be tracked, and its committee documents cannot be reached by anybody.

Measured on 3 September 2026:

    eMeeting procedures                        830
    with no legislative_carriages row      463  (55.8%)
    documents stranded behind that gap   3,565  (21.8% of 16,349)

It is not a long tail. The worst single file is 2025/0555(COD), the European
Competitiveness Fund, with 119 documents. Also absent: energy taxation (54),
the European Social Fund (44), passenger rights 2023/0437(COD) (41, including
the trilogue agreed text signed on 2 September 2026), foreign investment
screening (40), trainees' working conditions (34).

Where the title comes from
--------------------------
From eMeeting itself -- `item_title`, which is the European Parliament's own
committee agenda text. That is primary EP data, not a guess. OEIL remains the
source of truth for rapporteur identity and status, and this script does NOT
invent either: rows are created with status TABLED and no rapporteur, marked
`source=OEIL_DIRECT`, for the existing enrichment scripts (`enrich_carriages.py`,
`bulk_enrich_oeil.py`, `update_carriage_statuses_from_oeil.py`) to fill in.

Note for whoever runs the enrichment next: `OEILScraper.get_procedure_full()`
currently returns the page LABELS ("Procedure File: 2023/0437(COD)" as the title,
"Stage reached in procedure" as the status) because oeil.europarl.europa.eu
serves a JS-rendered SPA and the parser reads the unrendered HTML. The endpoint
itself is fine (HTTP 200). That wants the browser fetcher, and it is a separate
defect from this one.

Usage:
    python3.12 scripts/backfill_carriages_from_emeeting.py --dry-run          # default
    python3.12 scripts/backfill_carriages_from_emeeting.py --min-docs 5 --apply
"""

import argparse
import os
import pathlib
import sys
import uuid

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv(os.path.join(_REPO_ROOT, "backend", ".env"))

SELECT_GAP = """
SELECT d.procedure_ref,
       count(*)                                             AS doc_count,
       max(d.meeting_date)                                  AS newest_meeting,
       (array_agg(d.committee_code ORDER BY d.meeting_date DESC))[1] AS committee,
       (array_agg(NULLIF(btrim(coalesce(d.item_title, d.title, '')), '')
                  ORDER BY length(coalesce(d.item_title, d.title, '')) DESC)
        FILTER (WHERE btrim(coalesce(d.item_title, d.title, '')) <> ''))[1] AS best_title
FROM ep_emeeting_documents d
LEFT JOIN legislative_carriages c ON c.oeil_procedure_ref = d.procedure_ref
WHERE d.procedure_ref IS NOT NULL AND c.id IS NULL
GROUP BY d.procedure_ref
HAVING count(*) >= %(min_docs)s
ORDER BY count(*) DESC
"""

# Column names and enum CASE both come from the live schema, not from memory.
# The first --apply died on `created_at` (this table has first_seen /
# last_updated) and on lower-case enum values (they are TABLED / OEIL_DIRECT).
# A dry-run that returns before the INSERT cannot catch either, so the dry-run
# below actually runs the statement and rolls it back.
INSERT_SQL = """
INSERT INTO legislative_carriages
    (id, file_id, title, current_status, immc_tags,
     oeil_procedure_ref, lead_committee, source, first_seen, last_updated)
VALUES
    (%(id)s, %(file_id)s, %(title)s, 'TABLED', '{}'::jsonb,
     %(ref)s, %(committee)s, 'OEIL_DIRECT', now(), now())
ON CONFLICT DO NOTHING
"""


def params_for(r):
    return {"id": str(uuid.uuid4()), "file_id": r["procedure_ref"],
            "title": r["best_title"][:2000], "ref": r["procedure_ref"],
            "committee": r["committee"]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform the writes (default is dry-run)")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--min-docs", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("[ERROR] DATABASE_URL not set; aborting rather than guessing.")
        return 2

    conn = psycopg2.connect(url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(SELECT_GAP, {"min_docs": args.min_docs})
    rows = cur.fetchall()

    print(f"procedures with eMeeting documents and no carriage (>= {args.min_docs} docs): {len(rows)}")
    print(f"documents they carry: {sum(r['doc_count'] for r in rows)}")
    usable = [r for r in rows if r["best_title"]]
    skipped = [r for r in rows if not r["best_title"]]
    print(f"  usable (eMeeting supplied a title): {len(usable)}")
    print(f"  SKIPPED, no title in eMeeting:      {len(skipped)}  -- a carriage with no title is worse than none")
    if args.limit:
        usable = usable[: args.limit]

    for r in usable[:10]:
        print(f"   {r['procedure_ref']:22} {r['doc_count']:4} docs  {(r['committee'] or '-'):6} "
              f"{r['newest_meeting']}  {(r['best_title'] or '')[:52]}")

    if usable:
        try:
            cur.execute(INSERT_SQL, params_for(usable[0]))
            conn.rollback()
            print("  [OK] INSERT validated against the live schema, then rolled back")
        except Exception as exc:                                  # noqa: BLE001
            conn.rollback()
            print(f"  [ABORT] INSERT does not match the schema: {type(exc).__name__}: {str(exc)[:170]}")
            return 2

    if not args.apply:
        print("\n[DRY-RUN] nothing written. Re-run with --apply to create these carriages.")
        return 0

    created = 0
    for r in usable:
        cur.execute(INSERT_SQL, params_for(r))
        created += cur.rowcount
    conn.commit()

    cur.execute("""SELECT count(DISTINCT d.procedure_ref) AS n
                   FROM ep_emeeting_documents d
                   LEFT JOIN legislative_carriages c ON c.oeil_procedure_ref = d.procedure_ref
                   WHERE d.procedure_ref IS NOT NULL AND c.id IS NULL""")
    remaining = cur.fetchone()["n"]
    cur.execute("SELECT count(*) AS n FROM legislative_carriages")
    total = cur.fetchone()["n"]
    print(f"[OK] created {created} carriages (table now {total}). Procedures still without one: {remaining}")
    print("     Next: enrich_carriages.py / update_carriage_statuses_from_oeil.py for status and rapporteur.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
