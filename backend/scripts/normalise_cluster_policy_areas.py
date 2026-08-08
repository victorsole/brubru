"""Bring law_clusters.policy_area back onto the canonical Brubru policy taxonomy,
and demote recital-anchored requirements so they stop being scored as obligations.

Part 1 -- policy_area drift
---------------------------
`policy_area` is not decorative. It drives two things:
  * the policy-area filter dropdown on the EU Law Comply landing page, and
  * the SOFT register of GET /eu-law-comply/clusters/for-me, which matches
    `LawCluster.policy_area IN user.policy_interests`.

User policy interests are picked from knowledge_base/policy_taxonomy.json (34 areas).
Successive canon seeding rounds invented 10 more granular values that appear nowhere in
that taxonomy, so 26 clusters / 420 requirements could never surface in "For you", and the
dropdown offered four near-identical finance areas. Observed symptom: a consumer-affairs
profile was recommended China BEV, India/Indonesia stainless steel and Morocco aluminium
duties.

Part 2 -- recitals are not obligations
--------------------------------------
306 requirements across 18 clusters are anchored to a recital ("Recital 9", "Recital (16)").
Recitals are non-binding interpretive aids: they explain why an act was adopted, they do not
impose duties. Scoring a company as having a "gap" against Recital 16 is wrong on the law and
is the single most credibility-damaging thing in the corpus for a paying compliance client.
They are demoted to 'recommended' and tagged interpretive=true so a later scoring change can
exclude them cleanly. They are NOT deleted: a recital is genuinely useful context.

Companion code change (do not run this without it)
--------------------------------------------------
api/eu_law_comply.py::resolve_clusters_by_topic maps Tender Docs template targets onto
policy_area strings. Those strings are the PRE-normalisation values, so this script would
silently empty the Tender Docs comply panel. The mapping is updated in the same commit.

Usage:
  python3.12 -m backend.scripts.normalise_cluster_policy_areas --dry-run
  python3.12 -m backend.scripts.normalise_cluster_policy_areas --apply
"""
import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

from sqlalchemy import text

from backend.core.database import SessionLocal

TAXONOMY_PATH = project_root / "backend" / "knowledge_base" / "policy_taxonomy.json"

# Off-taxonomy value -> canonical taxonomy area.
# Each choice follows the Commission's own portfolio split, so a user who declared the
# canonical interest would expect the cluster to appear under it.
POLICY_AREA_MAP = {
    "Competition and State Aid": "Competition",
    "Cybersecurity and Digital Infrastructure": "Digital Policy and Digital Economy",
    "Data Protection and Privacy": "Justice and Fundamental Rights",
    "Digital Policy and Platform Regulation": "Digital Policy and Digital Economy",
    "Digital Policy and Telecommunications": "Communication Networks, Content and Technology",
    "Financial Services": "Economic and Financial Affairs",
    "Financial Services and Insurance": "Economic and Financial Affairs",
    "Financial Services and Markets": "Economic and Financial Affairs",
    "Public Health": "Health",
    "Public Health and Pharmaceuticals": "Health",
}


def canonical_areas():
    areas = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("name", "label", "title", "area", "policy_area") and isinstance(v, str):
                    areas.add(v)
                walk(v)
        elif isinstance(o, list):
            for i in o:
                walk(i)

    walk(json.load(open(TAXONOMY_PATH))["categories"])
    return areas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    canon = canonical_areas()
    print(f"[INFO] canonical taxonomy: {len(canon)} areas")

    # Guard: every target of the map must itself be canonical, else we swap one
    # off-taxonomy value for another.
    bad = {v for v in POLICY_AREA_MAP.values() if v not in canon}
    if bad:
        print(f"[ERROR] map targets not in taxonomy: {sorted(bad)}")
        return 1
    print("[OK]   every map target is canonical")

    db = SessionLocal()
    try:
        # ---------------- Part 1: policy areas -----------------------------
        rows = db.execute(
            text(
                "SELECT policy_area, count(*) FROM law_clusters "
                "WHERE policy_area IS NOT NULL GROUP BY 1 ORDER BY 1"
            )
        ).fetchall()

        print("\n=== policy_area audit ===")
        to_fix, already_ok, unmapped = [], [], []
        for pa, n in rows:
            if pa in canon:
                already_ok.append((pa, n))
            elif pa in POLICY_AREA_MAP:
                to_fix.append((pa, POLICY_AREA_MAP[pa], n))
            else:
                unmapped.append((pa, n))
        for pa, n in already_ok:
            print(f"  OK       {pa}  ({n})")
        for pa, new, n in to_fix:
            print(f"  REMAP    {pa}  ({n})  ->  {new}")
        for pa, n in unmapped:
            print(f"  UNMAPPED {pa}  ({n})   <-- add to POLICY_AREA_MAP")

        if unmapped:
            print("\n[ERROR] unmapped off-taxonomy values present. Aborting.")
            return 1

        # ---------------- Part 2: recitals ---------------------------------
        recitals = db.execute(
            text(
                "SELECT count(*), count(DISTINCT cluster_id) FROM law_requirements "
                "WHERE article ILIKE 'recital%'"
            )
        ).fetchone()
        already_demoted = db.execute(
            text(
                "SELECT count(*) FROM law_requirements "
                "WHERE article ILIKE 'recital%' AND criticality = 'recommended' "
                "AND extra_metadata->>'interpretive' = 'true'"
            )
        ).scalar()
        print(
            f"\n=== recital audit ===\n  {recitals[0]} recital-anchored requirements "
            f"across {recitals[1]} clusters ({already_demoted} already demoted)"
        )

        if apply:
            for pa, new, _ in to_fix:
                db.execute(
                    text("UPDATE law_clusters SET policy_area = :new WHERE policy_area = :old"),
                    {"new": new, "old": pa},
                )
            db.execute(
                text(
                    """
                    UPDATE law_requirements
                       SET criticality = 'recommended',
                           extra_metadata = COALESCE(extra_metadata, '{}'::jsonb)
                                            || jsonb_build_object(
                                                 'interpretive', true,
                                                 'interpretive_reason',
                                                 'Anchored to a recital. Recitals explain the '
                                                 'purpose of an act and are not binding '
                                                 'obligations; kept as context, excluded from '
                                                 'obligation scoring.')
                     WHERE article ILIKE 'recital%'
                    """
                )
            )
            db.commit()

            print("\n[OK] committed.")
            after = db.execute(
                text(
                    "SELECT policy_area, count(*) FROM law_clusters "
                    "WHERE policy_area IS NOT NULL GROUP BY 1 ORDER BY 1"
                )
            ).fetchall()
            offs = [pa for pa, _ in after if pa not in canon]
            print(f"  distinct policy areas: {len(rows)} -> {len(after)}")
            print(f"  off-taxonomy remaining: {offs if offs else 'none'}")
            n_int = db.execute(
                text(
                    "SELECT count(*) FROM law_requirements "
                    "WHERE extra_metadata->>'interpretive' = 'true'"
                )
            ).scalar()
            print(f"  requirements tagged interpretive: {n_int}")
            vocab = db.execute(
                text("SELECT criticality, count(*) FROM law_requirements GROUP BY 1 ORDER BY 2 DESC")
            ).fetchall()
            print(f"  criticality vocabulary: {dict(vocab)}")
        else:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
