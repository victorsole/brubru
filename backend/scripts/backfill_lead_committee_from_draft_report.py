"""Fill a NULL `legislative_carriages.lead_committee` from the committee that
tabled the procedure's DRAFT REPORT.

Why this is evidence and not a guess
------------------------------------
Under the EP's own rules the committee responsible for a file is the one that
tables the draft REPORT; committees that table a draft OPINION or an OPINION are
opinion-giving. `ep_emeeting_documents` records both kinds with `doc_kind`, from
the Parliament's own committee agendas, so the lead is derivable rather than
inferred. A file with no draft report yet is left NULL -- honest, not filled.

Measured 7 September 2026: 1,576 of 3,265 carriages (48.3%) have no lead
committee at all, and 16 of those already have a tabled draft report in our own
store, so they are derivable today.

Known limitation, stated rather than hidden
-------------------------------------------
`lead_committee` is a single 4-letter code. It cannot express a **Rule 58 joint
committee**. The European Biotech Act (2025/0406(COD)) is led jointly by SANT and
ITRE under Rule 58 (joint code CJ53, verified against OEIL); this script writes
ITRE, because ITRE is the committee that actually tabled the draft report. That
is accurate but incomplete, and the schema is what makes it so.

Run:
    python3.12 scripts/backfill_lead_committee_from_draft_report.py            # dry run, the two named files
    python3.12 scripts/backfill_lead_committee_from_draft_report.py --apply
    python3.12 scripts/backfill_lead_committee_from_draft_report.py --all-derivable [--apply]
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

DEFAULT_REFS = ["2026/0074(COD)", "2025/0406(COD)"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write; default is a dry run")
    ap.add_argument("--all-derivable", action="store_true",
                    help="every NULL-lead carriage with a tabled draft report, not just the named ones")
    ap.add_argument("--ref", action="append", default=None,
                    help="repeatable; a specific procedure ref (action=append, never nargs)")
    args = ap.parse_args()

    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://")
    engine = create_engine(url)

    where = "c.lead_committee IS NULL"
    params: dict = {}
    if not args.all_derivable:
        params["refs"] = args.ref or DEFAULT_REFS
        where += " AND c.oeil_procedure_ref = ANY(:refs)"

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                f"""
                SELECT c.id, c.oeil_procedure_ref AS ref,
                       coalesce(c.short_title, c.title) AS title,
                       (SELECT array_agg(DISTINCT d.committee_code)
                          FROM ep_emeeting_documents d
                         WHERE d.procedure_ref = c.oeil_procedure_ref
                           AND d.doc_kind = 'draft_report') AS report_committees,
                       (SELECT array_agg(DISTINCT d.committee_code)
                          FROM ep_emeeting_documents d
                         WHERE d.procedure_ref = c.oeil_procedure_ref
                           AND d.doc_kind IN ('draft_opinion', 'opinion')) AS opinion_committees
                  FROM legislative_carriages c
                 WHERE {where}
                 ORDER BY c.oeil_procedure_ref
                """
            ),
            params,
        ).mappings().all()

    plan, skipped = [], []
    for r in rows:
        leads = [x for x in (r["report_committees"] or []) if x]
        if len(leads) == 1:
            plan.append((r, leads[0]))
        elif len(leads) > 1:
            skipped.append((r, f"AMBIGUOUS: {len(leads)} committees tabled a draft report {leads}"))
        else:
            skipped.append((r, "no draft report tabled yet -- left NULL, honestly"))

    print(f"{'APPLY' if args.apply else 'DRY RUN'} -- {len(rows)} candidate row(s)\n")
    for r, lead in plan:
        print(f"  SET  {r['ref']:<18} lead_committee = {lead}")
        print(f"       evidence: {lead} tabled the draft report; "
              f"opinion-giving: {sorted(set(r['opinion_committees'] or [])) or 'none'}")
        print(f"       {str(r['title'])[:70]}")
    for r, why in skipped:
        print(f"  SKIP {r['ref']:<18} {why}")

    if not args.apply:
        print("\nDry run only. Re-run with --apply.")
        return 0

    written = 0
    with engine.begin() as conn:
        for r, lead in plan:
            # Idempotent and racy-safe: only fill a row that is STILL null.
            written += conn.execute(
                text("UPDATE legislative_carriages SET lead_committee = :c "
                     "WHERE id = :i AND lead_committee IS NULL"),
                {"c": lead, "i": r["id"]},
            ).rowcount
    print(f"\n[OK] set lead_committee on {written} row(s); {len(skipped)} left NULL on purpose")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
