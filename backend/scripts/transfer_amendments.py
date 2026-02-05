"""
Transfer amendments from one user to another.
This fixes the issue where amendments were created under a dev user.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from backend.core.database import SessionLocal
from backend.models.amendment import Amendment
from backend.models.user import User

def transfer_amendments(from_user_email: str, to_user_email: str):
    """Transfer all amendments from one user to another"""
    db = SessionLocal()

    try:
        # Get source user
        from_user = db.query(User).filter(User.email == from_user_email).first()
        if not from_user:
            print(f"❌ Source user not found: {from_user_email}")
            return False

        # Get target user
        to_user = db.query(User).filter(User.email == to_user_email).first()
        if not to_user:
            print(f"❌ Target user not found: {to_user_email}")
            return False

        # Count amendments to transfer
        amendments = db.query(Amendment).filter(Amendment.user_id == from_user.id).all()
        count = len(amendments)

        if count == 0:
            print(f"ℹ️  No amendments found for user {from_user_email}")
            return True

        print(f"📊 Found {count} amendments belonging to {from_user_email}")
        print(f"🔄 Transferring to {to_user_email}...")

        # Transfer amendments
        for amendment in amendments:
            amendment.user_id = to_user.id

        db.commit()

        print(f"✅ Successfully transferred {count} amendments!")
        print(f"   From: {from_user_email} (ID: {from_user.id})")
        print(f"   To:   {to_user_email} (ID: {to_user.id})")

        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

def transfer_from_all_users_to_target(target_email: str):
    """Transfer all amendments from all users to target user"""
    db = SessionLocal()

    try:
        # Get target user
        target_user = db.query(User).filter(User.email == target_email).first()
        if not target_user:
            print(f"❌ Target user not found: {target_email}")
            return False

        # Get all amendments not belonging to target user
        amendments = db.query(Amendment).filter(Amendment.user_id != target_user.id).all()
        count = len(amendments)

        if count == 0:
            print(f"ℹ️  All amendments already belong to {target_email}")
            return True

        print(f"📊 Found {count} amendments from other users")
        print(f"🔄 Transferring all to {target_email}...")

        # Transfer amendments
        for amendment in amendments:
            amendment.user_id = target_user.id

        db.commit()

        print(f"✅ Successfully transferred {count} amendments to {target_email}!")

        return True

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🔧 Amendment Transfer Script")
    print("=" * 50)

    # Transfer all amendments to hello@beresol.eu
    success = transfer_from_all_users_to_target("hello@beresol.eu")

    if success:
        print("\n✅ Transfer complete! Refresh your Dashboard to see the amendments.")
    else:
        print("\n❌ Transfer failed. Please check the error messages above.")

    print("=" * 50)
