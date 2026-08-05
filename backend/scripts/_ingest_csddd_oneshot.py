"""One-shot ingestion + repair for Directive (EU) 2024/1760 (CSDDD).

Same eu_laws CELEX-collision pattern as CSRD: existing row has celex=32024R1760
(wrong letter, should be L). Patch, then link as primary of cluster 60.

Idempotent.

Run AFTER `create_law_clusters.py --package csddd_corporate_sustainability_due_diligence`.
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

CORRECT_CELEX = "32024L1760"
WRONG_CELEX = "32024R1760"
TITLE = (
    "Directive (EU) 2024/1760 of the European Parliament and of the Council of "
    "13 June 2024 on corporate sustainability due diligence and amending "
    "Directive (EU) 2019/1937 and Regulation (EU) 2023/2859 (Text with EEA relevance)"
)
CLUSTER_NAME = "CSDDD - Corporate Sustainability Due Diligence Directive"

db = SessionLocal()
try:
    row = db.execute(text("""
        SELECT id, celex, celex_type FROM eu_laws
        WHERE celex IN (:correct, :wrong) OR title LIKE '%2024/1760%' AND title LIKE '%corporate sustainability due diligence%'
        LIMIT 1
    """), {"correct": CORRECT_CELEX, "wrong": WRONG_CELEX}).fetchone()
    if not row:
        print(f"[ABORT] no eu_laws row found for CSDDD")
        sys.exit(1)
    law_id = row.id
    print(f"[found] eu_laws.id={law_id} current celex={row.celex} type={row.celex_type}")

    db.execute(text("""
        UPDATE eu_laws SET
            celex = :celex,
            celex_type = 'L',
            celex_year = 2024,
            celex_number = 1760,
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
        "date": date(2024, 6, 13),
        "oj": "OJ L, 2024/1760, 5.7.2024",
        "id": law_id,
    })
    db.commit()
    print(f"[patched] eu_laws.id={law_id} celex now {CORRECT_CELEX} (was {row.celex}), type=L")

    cluster = db.execute(text("SELECT id, primary_law_id FROM law_clusters WHERE name = :n"),
                         {"n": CLUSTER_NAME}).fetchone()
    if not cluster:
        print(f"[ABORT] cluster '{CLUSTER_NAME}' not found")
        sys.exit(1)
    cluster_id = cluster.id
    print(f"[cluster] id={cluster_id} primary_law_id={cluster.primary_law_id}")

    deleted = db.execute(text("""
        DELETE FROM cluster_laws
        WHERE cluster_id = :cid AND law_id != :lid
    """), {"cid": cluster_id, "lid": law_id}).rowcount
    print(f"[cleanup] removed {deleted} noise cluster_laws rows")

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
        print(f"[cluster_laws] upgraded row to primary")
    else:
        print(f"[cluster_laws] primary row already in place")

    db.execute(text("UPDATE law_clusters SET primary_law_id = :lid WHERE id = :cid"),
               {"lid": law_id, "cid": cluster_id})
    db.commit()
    print(f"[cluster] set primary_law_id = {law_id}")

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
