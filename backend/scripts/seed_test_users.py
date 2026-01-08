"""
Seed Test Users

Creates 13 test users for Brubru training and testing.
Users have different subscription tiers (Blue/Yellow) and policy specialisations.

Usage:
    python3.12 -m backend.scripts.seed_test_users
"""

import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, '/Users/victorsole/Documents/GitHub/brubru')

from passlib.context import CryptContext
from backend.core.database import SessionLocal
from backend.models.user import User

# Password hashing - must match backend/api/auth.py
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def get_password_hash(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)


# Test users data from docs/users.md
TEST_USERS = [
    {
        "full_name": "Charlotte Berends",
        "email": "cjsberends@gmail.com",
        "password": "test123",
        "subscription_tier": "blue",
        "policy_interests": ["Trade"]
    },
    {
        "full_name": "Marga Payola",
        "email": "margapayola@gmail.com",
        "password": "test123",
        "subscription_tier": "blue",
        "policy_interests": ["General"]
    },
    {
        "full_name": "Daniel Roldán",
        "email": "danielroldan1989@gmail.com",
        "password": "test123",
        "subscription_tier": "blue",
        "policy_interests": ["General"]
    },
    {
        "full_name": "Aleix Sarri",
        "email": "aleixsarri@gmail.com",
        "password": "test123",
        "subscription_tier": "blue",
        "policy_interests": ["Economics", "Finance"]
    },
    {
        "full_name": "Nick Ligthart",
        "email": "nsligthart@gmail.com",
        "password": "test123",
        "subscription_tier": "blue",
        "policy_interests": ["Economics", "Finance"]
    },
    {
        "full_name": "Robin Loos",
        "email": "sustainability@beuc.eu",
        "password": "test123",
        "subscription_tier": "yellow",
        "policy_interests": ["Transport", "Consumer Protection"]
    },
    {
        "full_name": "Joan González",
        "email": "j.gonzalez@bepassociation.eu",
        "password": "test123",
        "subscription_tier": "yellow",
        "policy_interests": ["Batteries"]
    },
    {
        "full_name": "Sergi Duarte",
        "email": "sergi@hellobo.eu",
        "password": "test123",
        "subscription_tier": "yellow",
        "policy_interests": ["Agriculture"]
    },
    {
        "full_name": "Meritxell Vicheto",
        "email": "meritxell@hellobo.eu",
        "password": "test23",  # Different password
        "subscription_tier": "yellow",
        "policy_interests": ["Agriculture"]
    },
    {
        "full_name": "Bo",
        "email": "contact@hellobo.eu",
        "password": "test123",
        "subscription_tier": "yellow",
        "policy_interests": ["Agriculture"]
    },
    {
        "full_name": "Marc Desmond",
        "email": "marc.desmond10@gmail.com",
        "password": "test123",
        "subscription_tier": "yellow",
        "policy_interests": ["Sports supplements"]
    },
    {
        "full_name": "Andrés López",
        "email": "andres.lopez1@alumni.esade.edu",
        "password": "test123",
        "subscription_tier": "yellow",
        "policy_interests": ["Economics", "Finance"]
    },
    {
        "full_name": "Jaume Bernis",
        "email": "jaumebernis@taseuro.com",
        "password": "test123",
        "subscription_tier": "yellow",
        "policy_interests": ["Transport"]
    },
]


def main():
    """Seed test users into database"""
    logger.info("=" * 80)
    logger.info("Seeding Test Users")
    logger.info("=" * 80)

    db = SessionLocal()
    created_count = 0
    skipped_count = 0

    try:
        for user_data in TEST_USERS:
            # Check if user already exists
            existing_user = db.query(User).filter(User.email == user_data["email"]).first()

            if existing_user:
                logger.info(f"  SKIP: {user_data['email']} (already exists)")
                skipped_count += 1
                continue

            # Create new user
            hashed_password = get_password_hash(user_data["password"])
            new_user = User(
                email=user_data["email"],
                full_name=user_data["full_name"],
                password_hash=hashed_password,
                subscription_tier=user_data["subscription_tier"],
                policy_interests=user_data["policy_interests"],
                is_active=True,
                is_verified=True,  # Pre-verified for testing
            )

            db.add(new_user)
            logger.info(f"  CREATE: {user_data['full_name']} ({user_data['email']}) - {user_data['subscription_tier'].upper()}")
            created_count += 1

        db.commit()

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("SEED COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Created: {created_count} users")
        logger.info(f"Skipped: {skipped_count} users (already existed)")
        logger.info(f"Total test users: {len(TEST_USERS)}")

        # Breakdown by tier
        blue_count = sum(1 for u in TEST_USERS if u["subscription_tier"] == "blue")
        yellow_count = sum(1 for u in TEST_USERS if u["subscription_tier"] == "yellow")
        logger.info(f"\nBy tier:")
        logger.info(f"  Blue: {blue_count} users")
        logger.info(f"  Yellow: {yellow_count} users")

        logger.info("\nTest users can now log in with their email and password.")
        logger.info("=" * 80)

    except Exception as e:
        db.rollback()
        logger.error(f"Error seeding users: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
