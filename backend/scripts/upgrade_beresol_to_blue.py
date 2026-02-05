"""
Upgrade Beresol account to Blue tier

This script upgrades hello@beresol.eu to Blue tier with all features.
Run from project root: python backend/scripts/upgrade_beresol_to_blue.py
"""

from pathlib import Path
from dotenv import load_dotenv
import os
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(env_path)


def upgrade_beresol_account():
    """Upgrade hello@beresol.eu to Blue tier"""

    # Create database connection
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("❌ DATABASE_URL not found in environment variables")
        return

    engine = create_engine(DATABASE_URL)

    try:
        with engine.connect() as conn:
            # Check if user exists
            result = conn.execute(
                text("SELECT id, email, subscription_tier FROM users WHERE email = :email"),
                {"email": "hello@beresol.eu"}
            )
            user = result.fetchone()

            if not user:
                print("❌ User hello@beresol.eu not found in database")
                print("Please log in with Google OAuth first to create the account")
                return

            # Upgrade user to Blue tier
            expiry_date = datetime.utcnow() + timedelta(days=365 * 10)  # 10 years

            conn.execute(
                text("""
                    UPDATE users
                    SET
                        subscription_tier = :tier,
                        role = :role,
                        is_active = true,
                        is_verified = true,
                        subscription_expires_at = :expires_at,
                        updated_at = :updated_at
                    WHERE email = :email
                """),
                {
                    "tier": "blue",
                    "role": "admin",
                    "expires_at": expiry_date,
                    "updated_at": datetime.utcnow(),
                    "email": "hello@beresol.eu"
                }
            )
            conn.commit()

            # Verify update
            result = conn.execute(
                text("SELECT email, subscription_tier, role, subscription_expires_at FROM users WHERE email = :email"),
                {"email": "hello@beresol.eu"}
            )
            updated_user = result.fetchone()

            print("✓ Successfully upgraded account!")
            print(f"  Email: {updated_user[0]}")
            print(f"  Tier: {updated_user[1]}")
            print(f"  Role: {updated_user[2]}")
            print(f"  Expires: {updated_user[3]}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        engine.dispose()


if __name__ == "__main__":
    print("Upgrading Beresol account to Blue tier...\n")
    upgrade_beresol_account()
    print("\nDone!")
