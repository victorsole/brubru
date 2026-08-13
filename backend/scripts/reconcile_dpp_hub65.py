"""Reconcile the DPP hub (cluster 65) with EU Law Comply's conventions.

Hub 65, "EU Digital Product Passport regime (ESPR + product laws)", was seeded
by the canon-building session across 13 acts (210 requirements). It is published
and live. A validator pass (scripts/validate_compliance_packages --cluster 65)
found 124 errors, all from two things the seed scripts did differently:

1. Criticality vocabulary. 123 rows used high / medium / low, which EU Law
   Comply does not recognise (it sorts them last and the badge CSS misses them).
   Fixed corpus-wide, cluster-relatively, by scripts/normalise_requirement_criticality.py
   -- since hub 65 already has 'critical', high -> important and medium/low ->
   recommended. That script is the authority; this one does not repeat it. Run
   it first.

2. Rows that are not company duties were scored as duties. This marks them
   interpretive (context, shown in the preview, never scored), which is the
   same treatment given to recitals and penalty ceilings elsewhere. Nothing is
   deleted or moved -- the canon session's rule is that these rows stay -- only
   the flag changes.

     * The Standards Decision (32026D1736) is an OPTIONAL conformity route:
       build to EN 18216-18223 and you get a presumption of conformity under
       ESPR Article 41(2). It imposes no obligation of its own, so scoring a
       company as a gap for not taking the route is wrong. Flagged by the canon
       session's handover as the review item.
     * Six WFD-textiles (32025L1892) rows bind Member States, producer
       responsibility organisations or online platforms, not the company.
     * One row is a recital.

The cross-act duplicate the validator now reports as a warning (the same
supply-chain obligation in the Toys and Detergents Regulations) is legitimate
aggregation and is left as is.

Idempotent: matches rows by id, and the interpretive flag is set with a reason.
Applied to production directly (already live); this script makes it reproducible.

  python3.12 -m scripts.reconcile_dpp_hub65 --dry-run
  python3.12 -m scripts.reconcile_dpp_hub65 --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import logging  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal, engine  # noqa: E402

engine.echo = False

CLUSTER_ID = 65

# Rows to mark interpretive, grouped by why. Matched by (id, celex) so a stray id
# reused elsewhere can never be caught.
GROUPS = {
    "route (optional conformity, not a duty)": {
        "celex": "32026D1736",
        "ids": [4548, 4549, 4550, 4551],
    },
    "binds an authority or third party, not the company": {
        "celex": "32025L1892",
        "ids": [4603, 4611, 4612, 4613, 4619, 4621],
    },
    "recital": {
        "celex": "32026R0296",
        "ids": [4566],
    },
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    plan = []
    try:
        for reason, spec in GROUPS.items():
            rows = db.execute(text("""
                SELECT r.id, r.article FROM law_requirements r
                  JOIN eu_laws l ON l.id = r.law_id
                 WHERE r.cluster_id = :c AND r.id = ANY(:ids) AND l.celex = :celex
                   AND COALESCE(r.extra_metadata->>'interpretive','') <> 'true'"""),
                {"c": CLUSTER_ID, "ids": spec["ids"], "celex": spec["celex"]}).fetchall()
            for rid, article in rows:
                plan.append(f"CONTEXT [{spec['celex']} {article}] -> {reason}")
            if apply and rows:
                db.execute(text("""
                    UPDATE law_requirements
                       SET extra_metadata = COALESCE(extra_metadata,'{}'::jsonb)
                           || jsonb_build_object('interpretive','true','interpretive_reason',:why)
                     WHERE cluster_id = :c AND id = ANY(:ids)"""),
                    {"why": reason, "c": CLUSTER_ID, "ids": [r[0] for r in rows]})

        print("=== PLAN ===")
        for p in plan:
            print("  -", p)
        if not plan:
            print("  (nothing to do; already reconciled)")

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Run scripts.normalise_requirement_criticality "
                  "first, then re-run this with --apply")
            return 0

        db.commit()
        b = db.execute(text("""
            SELECT count(*) FILTER (WHERE COALESCE(extra_metadata->>'interpretive','')<>'true'),
                   count(*) FROM law_requirements WHERE cluster_id = :c"""),
            {"c": CLUSTER_ID}).fetchone()
        print(f"\n[OK] committed. Hub {CLUSTER_ID}: {b[0]} binding / {b[1]} total.")
        return 0
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
