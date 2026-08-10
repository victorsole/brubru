"""Move requirements off corrigendum rows and onto the act they correct.

The defect
----------
`eu_laws` holds 1,256 rows whose title begins "Corrigendum to ...". A corrigendum
is a typographical correction published in the OJ, not a source of obligations,
but 40 of them are attached to compliance clusters and 78 requirements hang off
them across 9 clusters. Because the findings table and the cluster preview both
read `law_title` and `law_celex` from the joined `eu_laws` row, a user checking
their GDPR position was told the obligation came from "Corrigendum to Regulation
(EU) 2016/679" rather than from the GDPR.

Worse, the real act is often attached to the same cluster in parallel with zero
requirements against it, so the cluster advertises "GDPR" in its law list and
delivers nothing under that name. Cluster 21, "SaaS & B2B Startup Compliance",
showed exactly that: GDPR with 0 requirements next to a corrigendum with 9.

The requirements themselves are sound -- "Certification shall be issued to a
controller or processor for a maximum period of three years" is GDPR Article
42(7), correctly extracted. Only their parent row is wrong.

What this does
--------------
For every corrigendum carrying requirements, find the act it corrects by
stripping the "Corrigendum to " prefix and matching the remaining title against
a non-corrigendum row. Where exactly one such act exists, re-point the
requirements onto it and swap the cluster_laws link. Where no match exists in
eu_laws, the requirements are LEFT ALONE and reported: inventing a parent would
be worse than an ugly title.

Deliberately not done here: deleting the corrigendum rows. They are legitimate
corpus entries and other features cite them. Only their role as a requirement
parent is removed.

Usage:
  python3.12 -m scripts.repoint_corrigendum_requirements --dry-run
  python3.12 -m scripts.repoint_corrigendum_requirements --apply
"""
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

from core.database import SessionLocal  # noqa: E402

FIND = text("""
    SELECT DISTINCT l.id, l.title,
           regexp_replace(l.title, '^Corrigendum to\\s+', '') AS real_title
      FROM law_requirements r JOIN eu_laws l ON l.id = r.law_id
     WHERE l.title ILIKE 'Corrigendum to%'
     ORDER BY l.id
""")

# Match on a generous prefix of the corrected title. Requiring the whole title
# fails on the trailing "(OJ L ...)" that corrigenda append; a short prefix
# would collide across amending acts of the same regulation.
MATCH = text("""
    SELECT id, celex, title FROM eu_laws
     WHERE title NOT ILIKE 'Corrigendum to%'
       AND title ILIKE :prefix || '%'
     ORDER BY length(title)
""")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    db = SessionLocal()
    moved = skipped = 0
    try:
        for corr_id, corr_title, real_title in db.execute(FIND).fetchall():
            n = db.execute(
                text("SELECT count(*) FROM law_requirements WHERE law_id=:l"),
                {"l": corr_id}).scalar()
            if not n:
                continue

            prefix = real_title[:60]
            cands = db.execute(MATCH, {"prefix": prefix}).fetchall()
            if not cands:
                print(f"  SKIP  [{n:>2} reqs] {corr_title[:66]}")
                print(f"        no non-corrigendum row matches {prefix[:52]!r}")
                skipped += n
                continue

            real_id, real_celex, real_law_title = cands[0]

            # Which clusters are affected, so the link swap is exact.
            clusters = [r[0] for r in db.execute(
                text("""SELECT DISTINCT cluster_id FROM law_requirements
                         WHERE law_id=:l AND cluster_id IS NOT NULL"""),
                {"l": corr_id}).fetchall()]

            print(f"  MOVE  [{n:>2} reqs] {corr_title[:60]}")
            print(f"        -> {real_celex} {real_law_title[:56]}")
            print(f"        clusters {clusters}")

            if apply:
                db.execute(text("UPDATE law_requirements SET law_id=:new WHERE law_id=:old"),
                           {"new": real_id, "old": corr_id})
                for cid in clusters:
                    # Attach the real act if the cluster does not already list it.
                    exists = db.execute(
                        text("SELECT 1 FROM cluster_laws WHERE cluster_id=:c AND law_id=:l"),
                        {"c": cid, "l": real_id}).scalar()
                    if not exists:
                        db.execute(
                            text("INSERT INTO cluster_laws (cluster_id, law_id) VALUES (:c,:l)"),
                            {"c": cid, "l": real_id})
                    # Drop the corrigendum's link; it no longer carries anything.
                    db.execute(
                        text("DELETE FROM cluster_laws WHERE cluster_id=:c AND law_id=:l"),
                        {"c": cid, "l": corr_id})
            moved += n

        print(f"\n  {moved} requirements re-pointed, {skipped} left on a corrigendum")

        if not apply:
            db.rollback()
            print("\n[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        db.commit()
        left = db.execute(text("""
            SELECT count(*) FROM law_requirements r JOIN eu_laws l ON l.id=r.law_id
             WHERE l.title ILIKE 'Corrigendum to%'""")).scalar()
        attached = db.execute(text("""
            SELECT count(DISTINCT cl.law_id) FROM cluster_laws cl
              JOIN eu_laws l ON l.id=cl.law_id
             WHERE l.title ILIKE 'Corrigendum to%'""")).scalar()
        print(f"\n[OK] committed. {left} requirements still on a corrigendum; "
              f"{attached} corrigenda still linked to a cluster")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"[ERROR] {type(exc).__name__}: {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
