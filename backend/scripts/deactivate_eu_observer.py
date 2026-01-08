"""
Deactivate EU Observer RSS Feed

Simple script to deactivate the EU Observer feed from My EU Bubble.
"""

import sys
sys.path.insert(0, '/Users/victorsole/Documents/GitHub/brubru')

from dotenv import load_dotenv
load_dotenv('/Users/victorsole/Documents/GitHub/brubru/.env')

from backend.core.database import SessionLocal
from backend.models.rss_feed import RSSFeed
from uuid import UUID

def deactivate_eu_observer():
    """Deactivate EU Observer feed"""
    db = SessionLocal()

    try:
        # Find and deactivate EU Observer feed
        feed_id = UUID('f8084c1a-e41b-4d3a-a33f-1992f20b3721')
        feed = db.query(RSSFeed).filter(RSSFeed.id == feed_id).first()

        if feed:
            print(f"Deactivating feed: {feed.name}")
            feed.is_active = False
            db.commit()
            print("✅ EU Observer feed has been deactivated")
            print(f"   - Name: {feed.name}")
            print(f"   - URL: {feed.url}")
            print(f"   - Status: Active = {feed.is_active}")
        else:
            print("❌ Feed not found")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    deactivate_eu_observer()
