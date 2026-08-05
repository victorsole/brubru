"""One-shot ingestion + repair for Directive (EU) 2022/2464 (CSRD).

Special case: eu_laws already carries the row (id=10087 at time of writing) but
under the WRONG CELEX letter — stored as `32022R2464` with `celex_type='R'`
while the act is a Directive (32022L2464, celex_type='L'). Same CELEX-collision
pattern the pharma canon batch surfaced. Patch the row, then link as primary.

Idempotent: safe to re-run.

Run AFTER `create_law_clusters.py --package csrd_corporate_sustainability_reporting`.
"""
import sys
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "backend"))

from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from core.database import SessionLocal
from sqlalchemy import text

CORRECT_CELEX = "32022L2464"
WRONG_CELEX = "32022R2464"
TITLE = (
    "Directive (EU) 2022/2464 of the European Parliament and of the Council of "
    "14 December 2022 amending Regulation (EU) No 537/2014, Directive 2004/109/EC, "
    "Directive 2006/43/EC and Directive 2013/34/EU, as regards corporate "
    "sustainability reporting (Text with EEA relevance)"
)
CLUSTER_NAME = "CSRD - Corporate Sustainability Reporting Directive"

db = SessionLocal()
try:
    # 1) Locate the row by any CELEX variant or title
    row = db.execute(text("""
        SELECT id, celex, celex_type FROM eu_laws
        WHERE celex IN (:correct, :wrong) OR title LIKE '%2022/2464%'
        LIMIT 1
    """), {"correct": CORRECT_CELEX, "wrong": WRONG_CELEX}).fetchone()
    if not row:
        print(f"[ABORT] no eu_laws row found for CSRD (searched CELEXes and title 2022/2464)")
        sys.exit(1)
    law_id = row.id
    print(f"[found] eu_laws.id={law_id} current celex={row.celex} type={row.celex_type}")

    # 2) Patch canonical metadata
    db.execute(text("""
        UPDATE eu_laws SET
            celex = :celex,
            celex_type = 'L',
            celex_year = 2022,
            celex_number = 2464,
            title = :title,
            doc_type = 'Directive',
            doc_type_normalized = 'Directive (EU)',
            date = :date,
            oj_reference = :oj,
            policy_area = 'Financial Services',
            is_primary_legislation = TRUE
        WHERE id = :id
    """), {
        "celex": CORRECT_CELEX,
        "title": TITLE,
        "date": date(2022, 12, 14),
        "oj": "OJ L 322, 16.12.2022, p. 15",
        "id": law_id,
    })
    db.commit()
    print(f"[patched] eu_laws.id={law_id} celex now {CORRECT_CELEX} (was {row.celex}), type=L")

    # 3) Find the CSRD cluster
    cluster = db.execute(text("SELECT id, primary_law_id FROM law_clusters WHERE name = :n"),
                         {"n": CLUSTER_NAME}).fetchone()
    if not cluster:
        print(f"[ABORT] cluster '{CLUSTER_NAME}' not found — run create_law_clusters.py first")
        sys.exit(1)
    cluster_id = cluster.id
    print(f"[cluster] id={cluster_id} primary_law_id={cluster.primary_law_id}")

    # 4) Clean noise from cluster_laws (delete all rows NOT the primary CSRD)
    deleted = db.execute(text("""
        DELETE FROM cluster_laws
        WHERE cluster_id = :cid AND law_id != :lid
    """), {"cid": cluster_id, "lid": law_id}).rowcount
    print(f"[cleanup] removed {deleted} noise-matched cluster_laws rows")

    # 5) Ensure the primary row exists (in case create_law_clusters missed it after the CELEX rename)
    existing = db.execute(text("""
        SELECT relationship_type FROM cluster_laws
        WHERE cluster_id = :cid AND law_id = :lid
    """), {"cid": cluster_id, "lid": law_id}).fetchone()
    if not existing:
        db.execute(text("""
            INSERT INTO cluster_laws (cluster_id, law_id, relationship_type)
            VALUES (:cid, :lid, 'primary')
        """), {"cid": cluster_id, "lid": law_id})
        print(f"[cluster_laws] inserted primary row")
    elif existing.relationship_type != "primary":
        db.execute(text("""
            UPDATE cluster_laws SET relationship_type = 'primary'
            WHERE cluster_id = :cid AND law_id = :lid
        """), {"cid": cluster_id, "lid": law_id})
        print(f"[cluster_laws] upgraded existing row to primary")
    else:
        print(f"[cluster_laws] primary row already in place")

    # 6) Set cluster.primary_law_id
    db.execute(text("UPDATE law_clusters SET primary_law_id = :lid WHERE id = :cid"),
               {"lid": law_id, "cid": cluster_id})
    db.commit()
    print(f"[cluster] set primary_law_id = {law_id}")

    # 7) Verify
    v = db.execute(text("""
        SELECT lc.id, lc.name, lc.primary_law_id, COUNT(cl.law_id) AS n_laws
        FROM law_clusters lc
        LEFT JOIN cluster_laws cl ON cl.cluster_id = lc.id
        WHERE lc.id = :cid
        GROUP BY lc.id, lc.name, lc.primary_law_id
    """), {"cid": cluster_id}).fetchone()
    print(f"[verify] cluster {v.id} '{v.name}' primary={v.primary_law_id} n_laws={v.n_laws}")

finally:
    db.close()
