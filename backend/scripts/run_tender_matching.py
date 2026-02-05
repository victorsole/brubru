"""
Run Tender Matching

Triggers the tender matching algorithm for active user profiles.
This creates TenderMatch records linking tenders to users based on their preferences.

Usage:
    python -m backend.scripts.run_tender_matching
    python -m backend.scripts.run_tender_matching --email hello@beresol.eu
    python -m backend.scripts.run_tender_matching --profile-id 1
"""

import sys
import asyncio
import logging
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.core.database import SessionLocal
from backend.models.tender import TenderProfile
from backend.models import User
from backend.services.tenders.matcher import TenderMatcher

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_matching_for_user(email: Optional[str] = None, profile_id: Optional[int] = None):
    """
    Run tender matching for a specific user or profile.

    Args:
        email: User email address
        profile_id: Specific profile ID
    """
    db = SessionLocal()

    try:
        print("=" * 60)
        print("TENDER MATCHING")
        print("=" * 60)

        # Find the profile
        if profile_id:
            profile = db.query(TenderProfile).filter(
                TenderProfile.id == profile_id
            ).first()
            if not profile:
                logger.error(f"Profile {profile_id} not found")
                return
        elif email:
            user = db.query(User).filter(User.email == email).first()
            if not user:
                logger.error(f"User with email {email} not found")
                return

            profile = db.query(TenderProfile).filter(
                TenderProfile.user_id == user.id
            ).first()
            if not profile:
                logger.error(f"No tender profile found for user {email}")
                return
        else:
            logger.error("Must provide either email or profile_id")
            return

        logger.info(f"Found profile: {profile.company_name} (ID: {profile.id})")
        logger.info(f"  User ID: {profile.user_id}")
        logger.info(f"  Active: {profile.is_active}")

        if profile.cpv_categories:
            logger.info(f"  CPV Categories: {profile.cpv_categories}")
        if profile.cpv_codes:
            logger.info(f"  CPV Codes: {profile.cpv_codes}")
        if profile.countries_of_interest:
            logger.info(f"  Countries: {profile.countries_of_interest}")
        if profile.keywords:
            logger.info(f"  Keywords: {profile.keywords}")

        print("-" * 60)

        # Run the matcher
        logger.info("Running tender matching algorithm...")
        matcher = TenderMatcher(db, score_threshold=50.0)

        # Match for this specific profile
        matches_created = await matcher.match_all_users(profile_ids=[profile.id])

        print("=" * 60)
        print("MATCHING COMPLETE")
        print("=" * 60)
        logger.info(f"New matches created: {matches_created}")

        # Get match statistics
        stats = matcher.get_match_statistics(user_id=str(profile.user_id))
        logger.info(f"Total matches: {stats['total_matches']}")
        logger.info(f"Average score: {stats['average_score']:.1f}")
        if stats.get('high_score_count'):
            logger.info(f"High score matches (≥70): {stats['high_score_count']}")

        print("=" * 60)

        # Show top matches
        from backend.models.tender import TenderMatch
        top_matches = db.query(TenderMatch).filter(
            TenderMatch.profile_id == profile.id
        ).order_by(TenderMatch.match_score.desc()).limit(5).all()

        if top_matches:
            print("\nTop 5 Matches:")
            print("-" * 60)
            for i, match in enumerate(top_matches, 1):
                print(f"\n{i}. {match.tender.title[:70]}")
                print(f"   Score: {match.match_score:.1f}%")
                print(f"   Country: {match.tender.buyer_country}")
                if match.tender.estimated_value:
                    print(f"   Value: €{match.tender.estimated_value:,.0f}")
                if match.tender.submission_deadline:
                    from datetime import datetime, timezone
                    days_left = (match.tender.submission_deadline - datetime.now(timezone.utc)).days
                    print(f"   Deadline: {days_left} days")
                if match.match_details:
                    print(f"   Details: {match.match_details}")

        print("=" * 60)

    except Exception as e:
        logger.error(f"Matching failed: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise

    finally:
        db.close()


async def run_matching_all():
    """Run matching for all active profiles."""
    db = SessionLocal()

    try:
        print("=" * 60)
        print("TENDER MATCHING - ALL PROFILES")
        print("=" * 60)

        matcher = TenderMatcher(db, score_threshold=50.0)
        matches_created = await matcher.match_all_users()

        print("=" * 60)
        print("MATCHING COMPLETE")
        print("=" * 60)
        logger.info(f"New matches created: {matches_created}")
        print("=" * 60)

    except Exception as e:
        logger.error(f"Matching failed: {e}")
        db.rollback()
        raise

    finally:
        db.close()


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Run tender matching algorithm"
    )
    parser.add_argument(
        "--email", "-e",
        type=str,
        help="User email address to match for"
    )
    parser.add_argument(
        "--profile-id", "-p",
        type=int,
        help="Specific profile ID to match for"
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Run matching for all active profiles"
    )

    args = parser.parse_args()

    try:
        if args.all:
            await run_matching_all()
        elif args.email or args.profile_id:
            await run_matching_for_user(email=args.email, profile_id=args.profile_id)
        else:
            # Default: run for all profiles
            logger.info("No specific user/profile specified, running for all active profiles")
            await run_matching_all()

    except Exception as e:
        logger.error(f"Matching failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
