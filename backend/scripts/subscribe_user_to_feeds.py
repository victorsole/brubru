"""
Subscribe User to RSS Feeds

Automatically subscribes a user to RSS feeds based on their policy interests.
This creates the connection between user preferences and available feeds.

Usage:
    python -m backend.scripts.subscribe_user_to_feeds
"""

import pathlib

# Repo root derived from this file's location, so a repo move cannot break the script.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])


import sys
sys.path.insert(0, _REPO_ROOT)

from sqlalchemy.orm import Session
from backend.core.database import SessionLocal
from backend.models.user import User
from backend.models.rss_feed import RSSFeed
from backend.models.user_feed_subscription import UserFeedSubscription
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Policy Interest to RSS Feed Category mapping
POLICY_TO_CATEGORY_MAPPING = {
    # Core Economic and Market Policies
    "Single Market": ["General", "Press Releases", "Competition"],
    "Competition": ["Competition"],
    "Trade and Economic Security": ["Trade"],
    "Economic and Financial Affairs": ["Economy"],
    "Taxation": ["Economy"],
    "Customs": ["Trade"],
    "Business and Industry": ["Press Releases", "General"],

    # Sustainability and Environmental Policies
    "Climate Action": ["Environment", "Energy"],
    "Environment": ["Environment"],
    "Energy": ["Energy"],
    "Transport": ["Transport"],

    # Digital Transformation
    "Digital Policy and Digital Economy": ["Digital Policy"],
    "Communication Networks, Content and Technology": ["Digital Policy"],

    # Agriculture and Natural Resources
    "Agriculture": ["Agriculture"],
    "Maritime Affairs and Fisheries": ["Agriculture"],
    "Food Safety": ["Health", "Agriculture"],

    # Cohesion and Development
    "Regional Policy": ["Press Releases"],
    "Research and Innovation": ["Research"],
    "Education, Training and Youth": ["Press Releases"],
    "Culture": ["Press Releases"],

    # Social Policies
    "Employment and Social Affairs": ["Employment"],
    "Health": ["Health"],
    "Consumer Protection": ["Justice"],

    # Justice and Home Affairs
    "Justice and Fundamental Rights": ["Justice"],
    "Migration and Home Affairs": ["Migration"],
    "Women's Rights and Gender Equality": ["Press Releases"],

    # External Relations
    "Foreign and Security Policy": ["Press Releases", "Council", "European Council"],
    "Development and Cooperation": ["Press Releases"],
    "Neighbourhood and Enlargement": ["Press Releases"],
    "Human Rights and Democracy": ["Press Releases"],
    "Humanitarian Aid and Civil Protection": ["Press Releases"],

    # Emerging Strategic Areas
    "Defence and Security": ["Press Releases", "Council"],
    "Space Policy": ["Press Releases"],
    "Statistics": ["Statistics"],
}


def subscribe_user_to_feeds(user_email: str = "test@brubru.dev"):
    """Subscribe user to RSS feeds based on their policy interests"""
    db: Session = SessionLocal()

    try:
        logger.info("=" * 80)
        logger.info("📰 Subscribing User to RSS Feeds")
        logger.info("=" * 80)

        # Get user
        user = db.query(User).filter(User.email == user_email).first()
        if not user:
            logger.error(f"❌ User {user_email} not found")
            return

        logger.info(f"\n👤 User: {user.full_name} ({user.email})")

        # Parse policy interests
        policy_interests = []
        if user.policy_interests:
            try:
                policy_interests = json.loads(user.policy_interests) if isinstance(user.policy_interests, str) else user.policy_interests
                logger.info(f"📋 Policy Interests: {len(policy_interests)} areas")
                for interest in policy_interests[:5]:  # Show first 5
                    logger.info(f"   - {interest}")
                if len(policy_interests) > 5:
                    logger.info(f"   ... and {len(policy_interests) - 5} more")
            except Exception as e:
                logger.error(f"❌ Failed to parse policy interests: {e}")
                policy_interests = []

        if not policy_interests:
            logger.warning("⚠️  No policy interests found. Subscribing to general feeds...")
            # Subscribe to general feeds if no interests
            policy_interests = ["General"]

        # Get all RSS feeds
        all_feeds = db.query(RSSFeed).filter(RSSFeed.is_active == True).all()
        logger.info(f"\n📡 Available RSS Feeds: {len(all_feeds)}")

        # Match feeds to policy interests
        feeds_to_subscribe = set()

        for interest in policy_interests:
            categories = POLICY_TO_CATEGORY_MAPPING.get(interest, ["General"])

            for category in categories:
                matching_feeds = [f for f in all_feeds if f.category == category]
                for feed in matching_feeds:
                    feeds_to_subscribe.add(feed.id)

        logger.info(f"\n🎯 Matched Feeds: {len(feeds_to_subscribe)}")

        # Check existing subscriptions
        existing_subs = db.query(UserFeedSubscription).filter(
            UserFeedSubscription.user_id == user.id
        ).all()
        existing_feed_ids = {sub.feed_id for sub in existing_subs}

        logger.info(f"📊 Existing Subscriptions: {len(existing_subs)}")

        # Create new subscriptions
        added = 0
        for feed_id in feeds_to_subscribe:
            if feed_id not in existing_feed_ids:
                feed = db.query(RSSFeed).filter(RSSFeed.id == feed_id).first()

                new_sub = UserFeedSubscription(
                    user_id=user.id,
                    feed_id=feed_id,
                    is_active=True,
                    notification_enabled=False
                )
                db.add(new_sub)
                added += 1
                logger.info(f"✅ Subscribed to: {feed.name}")

        db.commit()

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✅ SUBSCRIPTION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"📊 Summary:")
        logger.info(f"  - New subscriptions: {added}")
        logger.info(f"  - Existing subscriptions: {len(existing_subs)}")
        logger.info(f"  - Total active subscriptions: {len(feeds_to_subscribe)}")

        logger.info("\n🎯 Next steps:")
        logger.info("  1. RSS scheduler will automatically fetch entries from subscribed feeds")
        logger.info("  2. Or run: python -m backend.scripts.fetch_rss_entries")
        logger.info("  3. Visit http://localhost:3000/my-eu-bubble to see your feed!")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error subscribing user to feeds: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Subscribe user to RSS feeds')
    parser.add_argument('--email', default='test@brubru.dev', help='User email')
    args = parser.parse_args()

    subscribe_user_to_feeds(args.email)
