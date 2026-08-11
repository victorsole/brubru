"""
Create Compliance Engine Tables

This script creates all tables needed for the EU Law Comply feature.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import backend modules
backend_dir = Path(__file__).parent.parent
project_root = backend_dir.parent
sys.path.insert(0, str(project_root))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(project_root / ".env")

from sqlalchemy import text
from backend.core.database import engine, Base

# Import existing models so SQLAlchemy knows about their tables
from backend.models.eu_law import EULaw, LawCluster, ClusterLaw, LawRequirement
from backend.models.user import User

# Import compliance models
from backend.models.compliance import (
    ComplianceAnalysis,
    GapFinding,
    ComplianceAction,
    AnalysisExport
)


def check_pgvector():
    """Check if pgvector extension is installed"""
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector')"
        ))
        return result.scalar()


def install_pgvector():
    """Try to install pgvector extension"""
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
            print("✓ pgvector extension installed")
            return True
    except Exception as e:
        print(f"⚠ Warning: Could not install pgvector extension: {e}")
        print("  Requirement embeddings will be created without vector support.")
        return False


def create_trigger_function():
    """Create the compliance score update trigger"""
    trigger_sql = """
    -- Function to auto-update compliance scores
    CREATE OR REPLACE FUNCTION update_compliance_score()
    RETURNS TRIGGER AS $$
    BEGIN
        UPDATE compliance_analyses
        SET
            requirements_met = (
                SELECT COUNT(*) FROM gap_findings
                WHERE analysis_id = NEW.analysis_id AND status = 'met'
            ),
            requirements_partial = (
                SELECT COUNT(*) FROM gap_findings
                WHERE analysis_id = NEW.analysis_id AND status = 'partial'
            ),
            requirements_gap = (
                SELECT COUNT(*) FROM gap_findings
                WHERE analysis_id = NEW.analysis_id AND status = 'gap'
            ),
            total_requirements = (
                SELECT COUNT(*) FROM gap_findings
                WHERE analysis_id = NEW.analysis_id AND status != 'not_applicable'
            ),
            compliance_score = CASE
                WHEN (SELECT COUNT(*) FROM gap_findings
                      WHERE analysis_id = NEW.analysis_id AND status != 'not_applicable') = 0
                THEN NULL
                ELSE (
                    (
                        (SELECT COUNT(*) FROM gap_findings
                         WHERE analysis_id = NEW.analysis_id AND status = 'met') * 100.0 +
                        (SELECT COUNT(*) FROM gap_findings
                         WHERE analysis_id = NEW.analysis_id AND status = 'partial') * 50.0
                    ) /
                    (SELECT COUNT(*) FROM gap_findings
                     WHERE analysis_id = NEW.analysis_id AND status != 'not_applicable')
                )
            END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = NEW.analysis_id;

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql;

    -- Drop trigger if exists
    DROP TRIGGER IF EXISTS update_compliance_score_trigger ON gap_findings;

    -- Create trigger
    CREATE TRIGGER update_compliance_score_trigger
    AFTER INSERT OR UPDATE OR DELETE ON gap_findings
    FOR EACH ROW
    EXECUTE FUNCTION update_compliance_score();
    """

    with engine.connect() as conn:
        conn.execute(text(trigger_sql))
        conn.commit()
        print("✓ Compliance score trigger created")


def create_views():
    """Create helpful views for compliance queries"""
    views_sql = """
    -- View: User's recent compliance analyses with summary
    CREATE OR REPLACE VIEW user_compliance_summary AS
    SELECT
        ca.id,
        ca.user_id,
        ca.analysis_name,
        lc.name as cluster_name,
        lc.policy_area,
        ca.status,
        ca.compliance_score,
        ca.requirements_met,
        ca.requirements_partial,
        ca.requirements_gap,
        ca.total_requirements,
        ca.created_at,
        ca.completed_at,
        CASE
            WHEN ca.compliance_score >= 90 THEN 'excellent'
            WHEN ca.compliance_score >= 70 THEN 'good'
            WHEN ca.compliance_score >= 50 THEN 'needs_improvement'
            ELSE 'critical'
        END as compliance_rating
    FROM compliance_analyses ca
    JOIN law_clusters lc ON ca.cluster_id = lc.id
    ORDER BY ca.created_at DESC;

    -- View: Critical gaps by cluster (for dashboard)
    CREATE OR REPLACE VIEW critical_gaps_summary AS
    SELECT
        lc.id as cluster_id,
        lc.name as cluster_name,
        COUNT(DISTINCT gf.id) as critical_gap_count,
        COUNT(DISTINCT ca.user_id) as affected_users,
        string_agg(DISTINCT lr.article, ', ' ORDER BY lr.article) as affected_articles
    FROM law_clusters lc
    JOIN compliance_analyses ca ON lc.id = ca.cluster_id
    JOIN gap_findings gf ON ca.id = gf.analysis_id
    JOIN law_requirements lr ON gf.requirement_id = lr.id
    WHERE gf.status = 'gap'
      AND lr.criticality = 'critical'
      AND ca.status = 'completed'
    GROUP BY lc.id, lc.name
    ORDER BY critical_gap_count DESC;
    """

    with engine.connect() as conn:
        conn.execute(text(views_sql))
        conn.commit()
        print("✓ Compliance views created")


def create_indexes():
    """Create additional indexes for performance"""
    indexes_sql = """
    -- Vector similarity index (can be enabled after embeddings are generated)
    -- Uncomment when ready to use semantic search:
    -- CREATE INDEX IF NOT EXISTS idx_req_embedding
    --     ON requirement_embeddings USING ivfflat (embedding vector_cosine_ops)
    --     WITH (lists = 100);
    """

    # No indexes to create initially - vector index should be created after embeddings
    # with engine.connect() as conn:
    #     conn.execute(text(indexes_sql))
    #     conn.commit()
    print("✓ Index creation skipped (will be created after embeddings are generated)")


def main():
    print("=" * 70)
    print("Creating Compliance Engine Tables")
    print("=" * 70)

    # Step 1: Check/install pgvector
    print("\n1. Checking pgvector extension...")
    if not check_pgvector():
        install_pgvector()
    else:
        print("✓ pgvector extension already installed")

    # Step 2: Create tables
    print("\n2. Creating tables...")
    try:
        Base.metadata.create_all(
            bind=engine,
            tables=[
                ComplianceAnalysis.__table__,
                GapFinding.__table__,
                ComplianceAction.__table__,
                AnalysisExport.__table__
            ]
        )
        print("✓ Tables created successfully")
    except Exception as e:
        print(f"✗ Error creating tables: {e}")
        return 1

    # Step 3: Create trigger function
    print("\n3. Creating trigger function...")
    try:
        create_trigger_function()
    except Exception as e:
        print(f"✗ Error creating trigger: {e}")
        return 1

    # Step 4: Create views
    print("\n4. Creating views...")
    try:
        create_views()
    except Exception as e:
        print(f"✗ Error creating views: {e}")
        return 1

    # Step 5: Create indexes
    print("\n5. Creating additional indexes...")
    try:
        create_indexes()
    except Exception as e:
        print(f"✗ Error creating indexes: {e}")
        return 1

    print("\n" + "=" * 70)
    print("✓ Compliance engine tables created successfully!")
    print("=" * 70)

    # Print summary
    print("\nTables created:")
    print("  • compliance_analyses - Compliance check sessions")
    print("  • gap_findings - Individual gap analysis results")
    print("  • compliance_actions - Action items for gaps")
    print("  • analysis_exports - Exported compliance reports")
    print("\nNote: The law_requirements table already exists (defined in eu_law.py)")
    print("\nViews created:")
    print("  • user_compliance_summary - User analysis summaries")
    print("  • critical_gaps_summary - Critical gaps by cluster")
    print("\nTriggers created:")
    print("  • update_compliance_score_trigger - Auto-update compliance scores")

    return 0


if __name__ == "__main__":
    sys.exit(main())
