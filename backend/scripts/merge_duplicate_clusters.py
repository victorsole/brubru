"""Merge the four duplicate cluster pairs and drop machine-extracted orphan requirements.

Duplicates
----------
Canon seeding created a second cluster for four laws that already had a package
cluster, so EU Law Comply offered users two entries for the same law with very
different depth. Which one they clicked decided their compliance score:

    GDPR   1 "GDPR Package (Data Protection)"        49 laws / 401 reqs
        vs 50 "GDPR (Regulation (EU) 2016/679)"       1 law  /  16 reqs
    DSA    2 vs 51      DMA 3 vs 52       NIS2 5 vs 53

The package cluster is kept (lower id, broader framing, and the one the
eucanon map and existing links point at) and the canon cluster's laws and
requirements move into it. Verified before writing:

  * zero article-level overlap between any pair, so the merge is purely
    additive and creates no duplicate obligations;
  * zero compliance_analyses reference any of the four clusters being dropped,
    so no user history is affected.

Orphans
-------
19 requirements carry cluster_id IS NULL and are unreachable by every endpoint.
They are not curated obligations: they are artefacts of an early extractor run
(duplicated rows, text starting mid-sentence, "Article 2This Regulation shall
enter into force", entry-into-force boilerplate) across three laws, one of
which belongs to no cluster at all. Assigning them to a cluster would put
malformed text in front of paying users, so they are deleted. Verified: zero
gap_findings reference them.

Usage:
  python3.12 -m backend.scripts.merge_duplicate_clusters --dry-run
  python3.12 -m backend.scripts.merge_duplicate_clusters --apply
"""
import argparse
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import psycopg2

# (keep, drop) -- keep the package cluster, retire the canon duplicate.
PAIRS = [(1, 50), (2, 51), (3, 52), (5, 53)]


def connect():
    """Transaction-mode pooler. Session mode (5432) caps at 15 clients and is
    routinely saturated by the local server plus prod."""
    url = os.environ.get("DATABASE_URL") or ""
    return psycopg2.connect(url.replace(":5432/", ":6543/"), connect_timeout=25)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    conn = connect()
    cur = conn.cursor()

    # ---- safety gates -----------------------------------------------------
    drops = [d for _, d in PAIRS]
    cur.execute(
        "SELECT count(*) FROM compliance_analyses WHERE cluster_id = ANY(%s)", (drops,)
    )
    n_analyses = cur.fetchone()[0]
    cur.execute(
        """SELECT count(*) FROM law_requirements a JOIN law_requirements b
             ON a.law_id=b.law_id AND a.article=b.article
            WHERE (a.cluster_id, b.cluster_id) IN %s""",
        (tuple(PAIRS),),
    )
    n_overlap = cur.fetchone()[0]
    cur.execute(
        """SELECT count(*) FROM gap_findings f JOIN law_requirements r ON r.id=f.requirement_id
            WHERE r.cluster_id IS NULL"""
    )
    n_orphan_refs = cur.fetchone()[0]

    print(f"[gate] analyses on clusters being dropped : {n_analyses}  (must be 0)")
    print(f"[gate] article-level overlap in the pairs : {n_overlap}  (must be 0)")
    print(f"[gate] findings referencing orphans       : {n_orphan_refs}  (must be 0)")
    if n_analyses or n_overlap or n_orphan_refs:
        print("[ABORT] a safety gate failed; nothing written.")
        return 1

    print("\n=== plan ===")
    moved_reqs = moved_laws = 0
    for keep, drop in PAIRS:
        cur.execute("SELECT name FROM law_clusters WHERE id=%s", (keep,))
        keep_name = (cur.fetchone() or ["?"])[0]
        cur.execute("SELECT name FROM law_clusters WHERE id=%s", (drop,))
        row = cur.fetchone()
        if not row:
            print(f"  {drop} already merged, skipping")
            continue
        cur.execute("SELECT count(*) FROM law_requirements WHERE cluster_id=%s", (drop,))
        r = cur.fetchone()[0]
        cur.execute(
            """SELECT count(*) FROM cluster_laws d
                WHERE d.cluster_id=%s
                  AND NOT EXISTS (SELECT 1 FROM cluster_laws k
                                   WHERE k.cluster_id=%s AND k.law_id=d.law_id)""",
            (drop, keep),
        )
        l = cur.fetchone()[0]
        moved_reqs += r
        moved_laws += l
        print(f"  {drop} -> {keep}  ({r} requirements, {l} new law links)  [{keep_name}]")

    cur.execute("SELECT count(*) FROM law_requirements WHERE cluster_id IS NULL")
    n_orphans = cur.fetchone()[0]
    print(f"  delete {n_orphans} orphan requirements (cluster_id IS NULL)")

    if not apply:
        conn.rollback()
        cur.close()
        conn.close()
        print("\n[DRY-RUN] nothing written. Re-run with --apply")
        return 0

    for keep, drop in PAIRS:
        cur.execute("SELECT 1 FROM law_clusters WHERE id=%s", (drop,))
        if not cur.fetchone():
            continue
        cur.execute(
            "UPDATE law_requirements SET cluster_id=%s WHERE cluster_id=%s", (keep, drop)
        )
        # Move only law links the keeper does not already hold; cluster_laws has
        # a composite PK, so re-pointing a shared law would violate it.
        cur.execute(
            """UPDATE cluster_laws d SET cluster_id=%s
                WHERE d.cluster_id=%s
                  AND NOT EXISTS (SELECT 1 FROM cluster_laws k
                                   WHERE k.cluster_id=%s AND k.law_id=d.law_id)""",
            (keep, drop, keep),
        )
        cur.execute("DELETE FROM cluster_laws WHERE cluster_id=%s", (drop,))
        cur.execute("DELETE FROM law_clusters WHERE id=%s", (drop,))

    cur.execute("DELETE FROM law_requirements WHERE cluster_id IS NULL")
    deleted = cur.rowcount
    conn.commit()

    print(f"\n[OK] merged 4 pairs, deleted {deleted} orphan requirements")
    cur.execute("SELECT count(*) FROM law_clusters")
    print(f"  clusters now: {cur.fetchone()[0]}")
    cur.execute("SELECT count(*) FROM law_requirements WHERE cluster_id IS NULL")
    print(f"  orphan requirements now: {cur.fetchone()[0]}")
    for keep, drop in PAIRS:
        cur.execute(
            "SELECT name,(SELECT count(*) FROM law_requirements WHERE cluster_id=%s),"
            "(SELECT count(*) FROM cluster_laws WHERE cluster_id=%s) FROM law_clusters WHERE id=%s",
            (keep, keep, keep),
        )
        n, r, l = cur.fetchone()
        print(f"  {keep}: {n[:44]:46} {l} laws / {r} reqs")
        cur.execute("SELECT count(*) FROM law_clusters WHERE id=%s", (drop,))
        assert cur.fetchone()[0] == 0, f"cluster {drop} still exists"
    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
