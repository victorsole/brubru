"""
Run database migration for Legislative Train tables

Creates all tables for the Legislative Train Schedule feature:
- legislative_trains (EC Priorities)
- legislative_packages (Package hierarchy - NEW January 2025)
- legislative_carriages (Individual files)
- carriage_status_history (Status transitions)
- user_carriage_tracks (User subscriptions)

Run with: python -m backend.scripts.run_legislative_train_migration
"""
import sys
from pathlib import Path
from sqlalchemy import text

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import engine


def run_migration():
    """Apply the Legislative Train tables migration"""
    migration_file = Path(__file__).parent.parent / "migrations" / "009_add_legislative_train_tables.sql"

    print(f"📝 Reading migration file: {migration_file}")

    if not migration_file.exists():
        print(f"❌ Migration file not found: {migration_file}")
        sys.exit(1)

    with open(migration_file, 'r') as f:
        sql = f.read()

    print("🔄 Applying Legislative Train migration...")
    print("   Tables: legislative_trains, legislative_packages, legislative_carriages,")
    print("           carriage_status_history, user_carriage_tracks")
    print()

    with engine.connect() as conn:
        # Execute the migration
        conn.execute(text(sql))
        conn.commit()

    print("✅ Migration applied successfully!")
    print()
    print("Tables created/updated:")
    print("   ✓ legislative_trains - EC Priority trains")
    print("   ✓ legislative_packages - Package hierarchy (NEW)")
    print("   ✓ legislative_carriages - Individual legislative files")
    print("   ✓ carriage_status_history - Status change history")
    print("   ✓ user_carriage_tracks - User subscriptions")
    print()
    print("Enums created:")
    print("   ✓ carriage_status_enum")
    print("   ✓ text_type_enum")
    print()
    print("Indexes and triggers created for optimal query performance.")


if __name__ == "__main__":
    run_migration()
