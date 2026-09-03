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
sys.path.insert(0, os.path.join(_REPO_ROOT, "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_REPO_ROOT, "backend", ".env"))

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402


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
HAVING count(*) >= :min_docs
ORDER BY count(*) DESC
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="perform the writes (default is dry-run)")
    ap.add_argument("--dry-run", action="store_true", default=True)
    ap.add_argument("--min-docs", type=int, default=1,
                    help="only create a carriage for procedures with at least this many documents")
    ap.add_argument("--limit", type=int, default=0, help="cap the number created (0 = no cap)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        rows = db.execute(text(SELECT_GAP), {"min_docs": args.min_docs}).mappings().all()
        print(f"procedures with eMeeting documents and no carriage (>= {args.min_docs} docs): {len(rows)}")
        total_docs = sum(r["doc_count"] for r in rows)
        print(f"documents they carry: {total_docs}")

        skipped_untitled = [r for r in rows if not r["best_title"]]
        usable = [r for r in rows if r["best_title"]]
        print(f"  usable (eMeeting supplied a title): {len(usable)}")
        print(f"  SKIPPED, no title in eMeeting:      {len(skipped_untitled)}"
              f"  -- a carriage with no title is worse than no carriage")

        if args.limit:
            usable = usable[: args.limit]

        print("\ntop of the list:")
        for r in usable[:12]:
            print(f"   {r['procedure_ref']:22} {r['doc_count']:4} docs  {r['committee'] or '-':6} "
                  f"{r['newest_meeting']}  {(r['best_title'] or '')[:56]}")

        if not args.apply:
            print("\n[DRY-RUN] nothing written. Re-run with --apply to create these carriages.")
            return 0

        created = 0
        for r in usable:
            db.execute(text("""
                INSERT INTO legislative_carriages
                    (id, file_id, title, current_status, immc_tags,
                     oeil_procedure_ref, lead_committee, source, created_at, updated_at)
                VALUES
                    (:id, :file_id, :title, 'tabled', '{}'::jsonb,
                     :ref, :committee, 'oeil_direct', now(), now())
                ON CONFLICT DO NOTHING
            """), {
                "id": str(uuid.uuid4()),
                "file_id": r["procedure_ref"],
                "title": r["best_title"][:500],
                "ref": r["procedure_ref"],
                "committee": r["committee"],
            })
            created += 1
        db.commit()

        # Verify by query, not by the counter. Silence is not success.
        remaining = db.execute(text("""
            SELECT count(DISTINCT d.procedure_ref)
            FROM ep_emeeting_documents d
            LEFT JOIN legislative_carriages c ON c.oeil_procedure_ref = d.procedure_ref
            WHERE d.procedure_ref IS NOT NULL AND c.id IS NULL
        """)).scalar()
        print(f"[OK] created {created} carriages. Procedures still without one: {remaining}")
        print("     Next: run enrich_carriages.py / update_carriage_statuses_from_oeil.py "
              "to fill status and rapporteur from OEIL.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
