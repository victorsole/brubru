"""
Run migration to add background_preference column to users table
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from sqlalchemy import text
from backend.core.database import SessionLocal

def run_migration():
    """Add background_preference column to users table"""
    db = SessionLocal()

    try:
        print("🔧 Running migration: Add background_preference column")

        # Add column if it doesn't exist
        db.execute(text("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS background_preference VARCHAR(100) DEFAULT 'default';
        """))

        db.commit()

        print("✅ Migration completed successfully!")
        print("   Added background_preference column to users table")

        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Migration failed: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
