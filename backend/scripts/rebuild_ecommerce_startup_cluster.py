"""Rebuild cluster 18, "E-commerce & Platform Startup Compliance", and purge empty corrigendum links.

Part 1: cluster 18
------------------
Same fingerprint as cluster 17, which was rebuilt on 10 August 2026. Cluster 18
is startup-focused, so it appears in "For you" by default, and it held 33
requirements from four acts, none of which binds an e-commerce startup:

  32023R1484  Eurostat ICT-usage statistics; duties on national statistical
              offices. The same wrong act that polluted cluster 17.
  32005D0752  a 2005 decision establishing an expert group; duties on the
              group's own members.
  32023R1127  DMA delegated regulation on supervisory fees; binds designated
              gatekeepers only, which by definition a startup is not.
  32023R1201  DMA implementing regulation on procedural rules; governs how the
              Commission conducts inspections.

Meanwhile the Digital Services Act, the one regime that actually binds an online
marketplace or platform, was attached to the cluster with ZERO requirements. The
cluster advertised the DSA in its law list and delivered nothing under it.

The DSA is already curated properly in cluster 2, "Digital Services Act
Package": 16 requirements covering orders, points of contact, terms, reporting,
notice and action, statements of reasons, internal complaints, trusted flaggers,
measures against misuse, interface design, advertising transparency, trader
traceability, and the VLOP tier. Those are copied here rather than rewritten,
which is the established pattern -- law_requirements.cluster_id is single-valued
and the corpus already carries such duplicates.

Two DSA points are marked interpretive so they are not scored: the VLOP systemic
risk duties (Arts 34-35, 37, 39-40) bind platforms above 45 million monthly
users in the Union, and telling a startup it has a "gap" on independent systemic
risk audits is noise. They stay visible because a founder should know the
threshold exists.

The Consumer Rights Directive and the omnibus amendments are the obvious next
addition to this cluster; neither is in eu_laws yet, so this script does not
pretend to cover distance selling or the 14-day withdrawal right.

Part 2: empty corrigendum links
-------------------------------
22 cluster_laws rows point at a "Corrigendum to ..." act that carries no
requirement in that cluster. They inflate the "laws covered" count on the
cluster card and produce nothing when an analysis runs. Detached here.
Requirements that still hang off a corrigendum are NOT touched -- see
repoint_corrigendum_requirements.py, which moves the ones whose corrected act
exists in eu_laws and deliberately leaves the rest alone.

Usage:
  python3.12 -m scripts.rebuild_ecommerce_startup_cluster --dry-run
  python3.12 -m scripts.rebuild_ecommerce_startup_cluster --apply
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

import logging  # noqa: E402

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402

CLUSTER_ID = 18
SOURCE_CLUSTER = 2          # Digital Services Act Package
DSA_CELEX = "32022R2065"

DETACH_CELEX = {
    "32023R1484": "Eurostat ICT-usage statistics; binds national statistical offices",
    "32005D0752": "establishes an expert group; binds the group's members",
    "32023R1127": "DMA supervisory fees; binds designated gatekeepers only",
    "32023R1201": "DMA procedural rules; governs Commission inspections",
}

# VLOP-tier duties: real, but they start at 45 million monthly users.
INTERPRETIVE_ARTICLES = {"Arts 34-35", "Art 37", "Arts 39-40"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    plan = []
    try:
        used = db.execute(text("""
            SELECT count(*) FROM gap_findings g
              JOIN law_requirements r ON r.id = g.requirement_id
             WHERE r.cluster_id = :c"""), {"c": CLUSTER_ID}).scalar()
        if used:
            print(f"[ABORT] {used} gap_findings reference cluster {CLUSTER_ID}'s "
                  "requirements; deleting them would erase analysis history.")
            return 1
        plan.append(f"0 gap_findings depend on cluster {CLUSTER_ID}")

        # --- Part 1a: detach the acts that bind someone else -----------------
        for celex, why in DETACH_CELEX.items():
            lid = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                             {"x": celex}).scalar()
            if not lid:
                continue
            n = db.execute(text("""SELECT count(*) FROM law_requirements
                                    WHERE cluster_id=:c AND law_id=:l"""),
                           {"c": CLUSTER_ID, "l": lid}).scalar()
            plan.append(f"DETACH {celex} ({why}); drop {n} requirements")
            db.execute(text("DELETE FROM law_requirements WHERE cluster_id=:c AND law_id=:l"),
                       {"c": CLUSTER_ID, "l": lid})
            db.execute(text("DELETE FROM cluster_laws WHERE cluster_id=:c AND law_id=:l"),
                       {"c": CLUSTER_ID, "l": lid})

        # --- Part 1b: copy the curated DSA set from cluster 2 ----------------
        dsa_id = db.execute(text("SELECT id FROM eu_laws WHERE celex=:x"),
                            {"x": DSA_CELEX}).scalar()
        if not dsa_id:
            print(f"[ERROR] {DSA_CELEX} not in eu_laws")
            db.rollback()
            return 1

        src = db.execute(text("""
            SELECT article, requirement_text, criticality, applicable_entity,
                   deadline, extra_metadata
              FROM law_requirements
             WHERE cluster_id=:s AND law_id=:l ORDER BY id"""),
            {"s": SOURCE_CLUSTER, "l": dsa_id}).fetchall()
        if not src:
            print(f"[ERROR] cluster {SOURCE_CLUSTER} has no DSA requirements to copy")
            db.rollback()
            return 1

        exists = db.execute(text("SELECT 1 FROM cluster_laws WHERE cluster_id=:c AND law_id=:l"),
                            {"c": CLUSTER_ID, "l": dsa_id}).scalar()
        if not exists:
            db.execute(text("INSERT INTO cluster_laws (cluster_id, law_id) VALUES (:c,:l)"),
                       {"c": CLUSTER_ID, "l": dsa_id})
            plan.append(f"ATTACH {DSA_CELEX}")

        copied = interp = 0
        for article, body, crit, entity, deadline, meta in src:
            dupe = db.execute(text("""SELECT 1 FROM law_requirements
                                       WHERE cluster_id=:c AND law_id=:l AND article=:a"""),
                              {"c": CLUSTER_ID, "l": dsa_id, "a": article}).scalar()
            if dupe:
                continue
            m = dict(meta or {})
            m["copied_from_cluster"] = SOURCE_CLUSTER
            if article in INTERPRETIVE_ARTICLES:
                m["interpretive"] = "true"
                crit = "recommended"
                interp += 1
            db.execute(text("""
                INSERT INTO law_requirements
                    (law_id, cluster_id, article, requirement_text, criticality,
                     applicable_entity, deadline, extra_metadata)
                VALUES (:l,:c,:a,:t,:crit,:entity,:deadline, CAST(:meta AS jsonb))"""),
                {"l": dsa_id, "c": CLUSTER_ID, "a": article, "t": body,
                 "crit": crit, "entity": entity, "deadline": deadline,
                 "meta": json.dumps(m)})
            copied += 1
        plan.append(f"COPY {copied} DSA requirements from cluster {SOURCE_CLUSTER} "
                    f"({interp} marked interpretive: VLOP tier)")

        # --- Part 2: purge empty corrigendum links, all clusters -------------
        empty = db.execute(text("""
            SELECT cl.cluster_id, cl.law_id, l.title
              FROM cluster_laws cl JOIN eu_laws l ON l.id = cl.law_id
             WHERE l.title ILIKE 'Corrigendum to%'
               AND NOT EXISTS (SELECT 1 FROM law_requirements r
                                WHERE r.law_id = cl.law_id
                                  AND r.cluster_id = cl.cluster_id)""")).fetchall()
        for cid, lid, title in empty:
            db.execute(text("DELETE FROM cluster_laws WHERE cluster_id=:c AND law_id=:l"),
                       {"c": cid, "l": lid})
        plan.append(f"DETACH {len(empty)} empty corrigendum links across "
                    f"{len({c for c, _, _ in empty})} clusters")

        print("=== PLAN ===")
        for p in plan:
            print("  -", p)

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        db.commit()
        rows = db.execute(text("""
            SELECT l.celex, count(*) AS n,
                   count(*) FILTER (WHERE COALESCE(r.extra_metadata->>'interpretive','')<>'true') AS binding
              FROM law_requirements r JOIN eu_laws l ON l.id=r.law_id
             WHERE r.cluster_id=:c GROUP BY l.celex ORDER BY n DESC"""),
            {"c": CLUSTER_ID}).fetchall()
        print(f"\n[OK] committed. Cluster {CLUSTER_ID}:")
        for celex, n, binding in rows:
            print(f"  {celex}  {n} requirements ({binding} binding)")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
