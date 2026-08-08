"""Collapse the law_requirements.criticality vocabulary to the three documented values.

Problem
-------
The API documents and the frontend render exactly three criticality values:
'critical', 'important', 'recommended' (see compliance_report.tsx getCriticalityColor and
the ?criticality= filter on GET /eu-law-comply/clusters/{id}/requirements). Successive
seeding rounds introduced four more: 'high', 'medium', 'informational' and 'low'. Every
requirement carrying one of those falls through to the frontend's default branch and is
labelled "Recommended" -- so 232 requirements, including 134 'high' ones, are shown to
users with a severity that is simply wrong.

Mapping is cluster-relative, because 'high' means different things in different seeds
--------------------------------------------------------------------------------------
Some clusters were seeded with a critical/important/informational vocabulary; some with
high/medium/low; some (the newer canon ones) with critical/high/medium. So 'high' is the
TOP tier in a cluster that has no 'critical', but the SECOND tier in a cluster that does.
Collapsing with one global map would either promote second-tier obligations to critical or
demote genuine top-tier ones. The rule applied here:

  cluster already uses 'critical'   ->  high -> important,  medium -> recommended,
                                        low -> recommended, informational -> recommended
  cluster has no 'critical'         ->  high -> critical,   medium -> important,
                                        low -> recommended, informational -> recommended

Requirements with cluster_id IS NULL are treated as their own group (no 'critical' present
is evaluated over the null-cluster set).

Usage:
  python3.12 -m backend.scripts.normalise_requirement_criticality --dry-run
  python3.12 -m backend.scripts.normalise_requirement_criticality --apply
"""
import argparse
import sys
from collections import defaultdict
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from backend.core.database import SessionLocal

CANONICAL = {"critical", "important", "recommended"}

MAP_WITH_CRITICAL = {
    "high": "important",
    "medium": "recommended",
    "low": "recommended",
    "informational": "recommended",
}
MAP_WITHOUT_CRITICAL = {
    "high": "critical",
    "medium": "important",
    "low": "recommended",
    "informational": "recommended",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                "SELECT id, cluster_id, criticality FROM law_requirements "
                "WHERE criticality IS NOT NULL"
            )
        ).fetchall()

        by_cluster = defaultdict(list)
        for rid, cid, crit in rows:
            by_cluster[cid].append((rid, (crit or "").strip().lower()))

        changes = []          # (id, old, new)
        per_cluster_summary = []
        for cid, items in sorted(by_cluster.items(), key=lambda kv: (kv[0] is None, kv[0])):
            vocab = {c for _, c in items}
            has_critical = "critical" in vocab
            mapping = MAP_WITH_CRITICAL if has_critical else MAP_WITHOUT_CRITICAL
            offvocab = vocab - CANONICAL
            if not offvocab:
                continue
            n = 0
            for rid, crit in items:
                if crit in mapping:
                    changes.append((rid, crit, mapping[crit]))
                    n += 1
            per_cluster_summary.append(
                (cid, sorted(vocab), has_critical, sorted(offvocab), n)
            )

        print(f"{len(rows)} requirements scanned, {len(changes)} to remap\n")
        print(f"{'cluster':>8}  {'has_critical':>12}  {'off-vocab':<34} {'remapped':>8}  vocabulary")
        for cid, vocab, hc, off, n in per_cluster_summary:
            print(
                f"{str(cid):>8}  {str(hc):>12}  {', '.join(off):<34} {n:>8}  {', '.join(vocab)}"
            )

        tally = defaultdict(int)
        for _, old, new in changes:
            tally[(old, new)] += 1
        print("\nremap tally:")
        for (old, new), n in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"  {old:<14} -> {new:<12} {n:>5}")

        if apply and changes:
            for rid, _old, new in changes:
                db.execute(
                    text("UPDATE law_requirements SET criticality = :c WHERE id = :i"),
                    {"c": new, "i": rid},
                )
            db.commit()
            left = db.execute(
                text(
                    "SELECT criticality, count(*) FROM law_requirements "
                    "GROUP BY 1 ORDER BY 2 DESC"
                )
            ).fetchall()
            print("\n[OK] committed. Vocabulary now:")
            for c, n in left:
                flag = "" if c in CANONICAL else "   <-- STILL OFF-VOCAB"
                print(f"  {c:<14} {n:>5}{flag}")
        elif not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
