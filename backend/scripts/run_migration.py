"""
Run database migration to add AI enrichment columns
"""
import sys
from pathlib import Path
from sqlalchemy import text

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.database import engine

def run_migration():
    """Apply the AI enrichment migration"""
    migration_file = Path(__file__).parent.parent / "migrations" / "add_ai_enrichment_to_legislative_carriages.sql"
    
    print(f"📝 Reading migration file: {migration_file}")
    with open(migration_file, 'r') as f:
        sql = f.read()
    
    print("🔄 Applying migration...")
    with engine.connect() as conn:
        conn.execute(text(sql))
        conn.commit()
    
    print("✅ Migration applied successfully!")
    print("   - Added ai_summary column")
    print("   - Added ai_entities column") 
    print("   - Added ai_policy_classifications column")
    print("   - Added enriched_at column")

if __name__ == "__main__":
    run_migration()
