"""
Seed RSS Feeds

Populates the database with real EU institution RSS feeds.
These feeds will be available for users to subscribe to in My EU Bubble.

Usage:
    python -m backend.scripts.seed_rss_feeds
"""

import sys
sys.path.insert(0, '/Users/victorsole/Documents/GitHub/brubru')

from sqlalchemy.orm import Session
from backend.core.database import SessionLocal
from backend.models.rss_feed import RSSFeed
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Real EU RSS Feeds categorized by policy area
EU_RSS_FEEDS = [
    # European Parliament - Multiple feeds
    {
        "name": "European Parliament - Top Stories",
        "url": "https://www.europarl.europa.eu/rss/doc/top-stories/en.xml",
        "source": "European Parliament",
        "language": "en",
        "category": "General",
        "description": "Top stories from the European Parliament",
        "is_active": True
    },
    {
        "name": "European Parliament - Press Releases",
        "url": "https://www.europarl.europa.eu/rss/doc/press-releases/en.xml",
        "source": "European Parliament",
        "language": "en",
        "category": "Press Releases",
        "description": "Official press releases from the European Parliament",
        "is_active": True
    },
    {
        "name": "European Parliament - Committee News",
        "url": "https://www.europarl.europa.eu/rss/doc/last-news-committees/en.xml",
        "source": "European Parliament",
        "language": "en",
        "category": "Committee News",
        "description": "Latest news from EP committees",
        "is_active": True
    },
    {
        "name": "European Parliament - Texts Adopted",
        "url": "https://www.europarl.europa.eu/rss/doc/texts-adopted/en.xml",
        "source": "European Parliament",
        "language": "en",
        "category": "Legislation",
        "description": "Recently adopted texts and resolutions",
        "is_active": True
    },
    {
        "name": "European Parliament - Reports",
        "url": "https://www.europarl.europa.eu/rss/doc/reports/en.xml",
        "source": "European Parliament",
        "language": "en",
        "category": "Reports",
        "description": "Parliamentary reports and recommendations",
        "is_active": True
    },
    {
        "name": "European Parliament - Plenary Agendas",
        "url": "https://www.europarl.europa.eu/rss/doc/agendas-plenary/en.xml",
        "source": "European Parliament",
        "language": "en",
        "category": "Plenary",
        "description": "Plenary session agendas",
        "is_active": True
    },
    {
        "name": "European Parliament - Week Ahead",
        "url": "https://www.europarl.europa.eu/rss/doc/agendas-news/en.xml",
        "source": "European Parliament",
        "language": "en",
        "category": "Agendas",
        "description": "Weekly agenda and upcoming events",
        "is_active": True
    },
    {
        "name": "European Parliament - Newsletters",
        "url": "https://www.europarl.europa.eu/rss/doc/newsletters/en.xml",
        "source": "European Parliament",
        "language": "en",
        "category": "Newsletters",
        "description": "Official EP newsletters",
        "is_active": True
    },

    # Alternative EU News Sources (Official EC feeds have bot protection)
    {
        "name": "Euractiv - EU News",
        "url": "https://www.euractiv.com/feed/",
        "source": "Euractiv",
        "language": "en",
        "category": "General",
        "description": "Independent EU policy news and analysis",
        "is_active": True
    },
    {
        "name": "Politico Europe - EU Politics",
        "url": "https://www.politico.eu/feed/",
        "source": "Politico Europe",
        "language": "en",
        "category": "General",
        "description": "EU politics and policy news",
        "is_active": True
    },
    {
        "name": "EU Observer - EU Affairs",
        "url": "https://euobserver.com/rss",
        "source": "EU Observer",
        "language": "en",
        "category": "General",
        "description": "Independent EU news and analysis",
        "is_active": True
    },

    # EUR-Lex - Recent Publications
    {
        "name": "EUR-Lex - Latest EU Law",
        "url": "https://eur-lex.europa.eu/EN/rss_www.xml",
        "source": "Publications Office",
        "language": "en",
        "category": "Legislation",
        "description": "Latest publications in EUR-Lex",
        "is_active": True
    },

    # Digital Policy
    {
        "name": "Digital Single Market - News",
        "url": "https://ec.europa.eu/newsroom/dae/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Digital Policy",
        "description": "News about the Digital Single Market",
        "is_active": True
    },

    # Environment & Climate
    {
        "name": "Environment - News",
        "url": "https://ec.europa.eu/newsroom/env/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Environment",
        "description": "News on environment and climate policy",
        "is_active": True
    },

    # Trade Policy
    {
        "name": "Trade Policy - News",
        "url": "https://ec.europa.eu/newsroom/trade/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Trade",
        "description": "News on EU trade policy",
        "is_active": True
    },

    # Competition Policy
    {
        "name": "Competition Policy - News",
        "url": "https://ec.europa.eu/newsroom/comp/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Competition",
        "description": "News on competition and antitrust policy",
        "is_active": True
    },

    # Energy Policy
    {
        "name": "Energy Policy - News",
        "url": "https://ec.europa.eu/newsroom/ener/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Energy",
        "description": "News on EU energy policy",
        "is_active": True
    },

    # Agriculture & Food
    {
        "name": "Agriculture & Rural Development - News",
        "url": "https://ec.europa.eu/newsroom/agri/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Agriculture",
        "description": "News on agriculture and rural development",
        "is_active": True
    },

    # Research & Innovation
    {
        "name": "Research & Innovation - News",
        "url": "https://ec.europa.eu/newsroom/rtd/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Research",
        "description": "News on EU research and innovation",
        "is_active": True
    },

    # Justice & Home Affairs
    {
        "name": "Justice & Consumers - News",
        "url": "https://ec.europa.eu/newsroom/just/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Justice",
        "description": "News on justice and consumer policy",
        "is_active": True
    },

    # Migration & Home Affairs
    {
        "name": "Migration & Home Affairs - News",
        "url": "https://ec.europa.eu/newsroom/home/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Migration",
        "description": "News on migration and home affairs",
        "is_active": True
    },

    # Economy & Finance
    {
        "name": "Economy & Finance - News",
        "url": "https://ec.europa.eu/newsroom/ecfin/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Economy",
        "description": "News on economic and financial affairs",
        "is_active": True
    },

    # Employment & Social Affairs
    {
        "name": "Employment & Social Affairs - News",
        "url": "https://ec.europa.eu/newsroom/empl/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Employment",
        "description": "News on employment and social affairs",
        "is_active": True
    },

    # Transport & Mobility
    {
        "name": "Transport & Mobility - News",
        "url": "https://ec.europa.eu/newsroom/move/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Transport",
        "description": "News on transport and mobility",
        "is_active": True
    },

    # Health Policy
    {
        "name": "Health & Food Safety - News",
        "url": "https://ec.europa.eu/newsroom/sante/rss.cfm",
        "source": "European Commission",
        "language": "en",
        "category": "Health",
        "description": "News on health and food safety",
        "is_active": True
    },

    # Council of the EU
    {
        "name": "Council of the EU - Press Releases",
        "url": "https://www.consilium.europa.eu/en/press/press-releases/rss/",
        "source": "Council of the EU",
        "language": "en",
        "category": "Council",
        "description": "Press releases from the Council of the EU",
        "is_active": True
    },

    # European Council
    {
        "name": "European Council - News",
        "url": "https://www.consilium.europa.eu/en/european-council/press-releases/rss/",
        "source": "European Council",
        "language": "en",
        "category": "European Council",
        "description": "News from the European Council",
        "is_active": True
    },

    # European Commission Newsletters (from EC Newsroom)
    {
        "name": "EC Competition Weekly e-News",
        "url": "https://ec.europa.eu/newsroom/comp/rss-feeds/comp-newsletter.xml",
        "source": "EC Newsletters",
        "language": "en",
        "category": "Newsletters",
        "description": "European Commission Competition DG newsletter",
        "is_active": True
    },
    {
        "name": "EC Climate Action Newsletter",
        "url": "https://ec.europa.eu/newsroom/clima/rss-feeds/clima-newsletter.xml",
        "source": "EC Newsletters",
        "language": "en",
        "category": "Newsletters",
        "description": "European Commission Climate Action newsletter",
        "is_active": True
    },
    {
        "name": "EC Trade Newsletter",
        "url": "https://ec.europa.eu/newsroom/trade/rss-feeds/trade-newsletter.xml",
        "source": "EC Newsletters",
        "language": "en",
        "category": "Newsletters",
        "description": "European Commission Trade DG newsletter",
        "is_active": True
    },
    {
        "name": "EC Energy Newsletter",
        "url": "https://ec.europa.eu/newsroom/ener/rss-feeds/ener-newsletter.xml",
        "source": "EC Newsletters",
        "language": "en",
        "category": "Newsletters",
        "description": "European Commission Energy DG newsletter",
        "is_active": True
    },
    {
        "name": "EC Internal Market Newsletter",
        "url": "https://ec.europa.eu/newsroom/grow/rss-feeds/grow-newsletter.xml",
        "source": "EC Newsletters",
        "language": "en",
        "category": "Newsletters",
        "description": "European Commission Internal Market, Industry, Entrepreneurship and SMEs newsletter",
        "is_active": True
    },
    {
        "name": "EC Health and Food Safety Newsletter",
        "url": "https://ec.europa.eu/newsroom/sante/rss-feeds/sante-newsletter.xml",
        "source": "EC Newsletters",
        "language": "en",
        "category": "Newsletters",
        "description": "European Commission Health and Food Safety newsletter",
        "is_active": True
    },
    {
        "name": "EC Regional Development Newsletter",
        "url": "https://ec.europa.eu/newsroom/regio/rss-feeds/regio-newsletter.xml",
        "source": "EC Newsletters",
        "language": "en",
        "category": "Newsletters",
        "description": "European Commission Regional and Urban Policy newsletter (RegioFlash)",
        "is_active": True
    },
    {
        "name": "EC Finance Newsletter",
        "url": "https://ec.europa.eu/newsroom/fisma/rss-feeds/fisma-newsletter.xml",
        "source": "EC Newsletters",
        "language": "en",
        "category": "Newsletters",
        "description": "European Commission Financial Stability and Capital Markets Union newsletter",
        "is_active": True
    },

    # Eurostat - Statistics
    {
        "name": "Eurostat - Main Feed",
        "url": "https://ec.europa.eu/eurostat/web/rss",
        "source": "Eurostat",
        "language": "en",
        "category": "Statistics",
        "description": "Main RSS feed from Eurostat",
        "is_active": True
    },
    {
        "name": "Eurostat - All News",
        "url": "https://ec.europa.eu/eurostat/api/rss/news",
        "source": "Eurostat",
        "language": "en",
        "category": "Statistics",
        "description": "Latest statistical news from Eurostat",
        "is_active": True
    },
    {
        "name": "Eurostat - Population & Social Conditions",
        "url": "https://ec.europa.eu/eurostat/api/rss/news?category=population",
        "source": "Eurostat",
        "language": "en",
        "category": "Statistics",
        "description": "Statistics on population and social conditions",
        "is_active": True
    },
    {
        "name": "Eurostat - Economy & Finance",
        "url": "https://ec.europa.eu/eurostat/api/rss/news?category=economy",
        "source": "Eurostat",
        "language": "en",
        "category": "Statistics",
        "description": "Economic and financial statistics",
        "is_active": True
    },
    {
        "name": "Eurostat - Environment & Energy",
        "url": "https://ec.europa.eu/eurostat/api/rss/news?category=environment",
        "source": "Eurostat",
        "language": "en",
        "category": "Statistics",
        "description": "Environmental and energy statistics",
        "is_active": True
    },
    {
        "name": "Eurostat - Industry, Trade & Services",
        "url": "https://ec.europa.eu/eurostat/api/rss/news?category=industry",
        "source": "Eurostat",
        "language": "en",
        "category": "Statistics",
        "description": "Statistics on industry, trade and services",
        "is_active": True
    },
    {
        "name": "Eurostat - Agriculture & Fisheries",
        "url": "https://ec.europa.eu/eurostat/api/rss/news?category=agriculture",
        "source": "Eurostat",
        "language": "en",
        "category": "Statistics",
        "description": "Statistics on agriculture and fisheries",
        "is_active": True
    },
]


def seed_rss_feeds():
    """Seed RSS feeds into the database"""
    db: Session = SessionLocal()

    try:
        logger.info("=" * 80)
        logger.info("📰 Seeding EU RSS Feeds")
        logger.info("=" * 80)

        # Check existing feeds
        existing_count = db.query(RSSFeed).count()
        logger.info(f"\n📊 Current feeds in database: {existing_count}")

        added = 0
        skipped = 0
        updated = 0

        for feed_data in EU_RSS_FEEDS:
            # Check if feed already exists
            existing_feed = db.query(RSSFeed).filter(
                RSSFeed.url == feed_data["url"]
            ).first()

            if existing_feed:
                # Update existing feed
                for key, value in feed_data.items():
                    setattr(existing_feed, key, value)
                updated += 1
                logger.info(f"🔄 Updated: {feed_data['name']}")
            else:
                # Create new feed
                new_feed = RSSFeed(**feed_data)
                db.add(new_feed)
                added += 1
                logger.info(f"✅ Added: {feed_data['name']}")

        db.commit()

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("✅ RSS FEEDS SEEDED SUCCESSFULLY")
        logger.info("=" * 80)
        logger.info(f"📊 Summary:")
        logger.info(f"  - Added: {added} new feeds")
        logger.info(f"  - Updated: {updated} existing feeds")
        logger.info(f"  - Skipped: {skipped} feeds")
        logger.info(f"  - Total in database: {db.query(RSSFeed).count()} feeds")

        # Show categories
        all_feeds = db.query(RSSFeed).all()
        all_categories = set()
        for feed in all_feeds:
            if feed.category:
                all_categories.add(feed.category)

        logger.info(f"\n📁 Available categories ({len(all_categories)}):")
        for category in sorted(all_categories):
            count = sum(1 for f in all_feeds if f.category == category)
            logger.info(f"  - {category}: {count} feeds")

        logger.info("\n🎯 Next steps:")
        logger.info("  1. Go to http://localhost:3000/profile")
        logger.info("  2. Select your Policy Interests")
        logger.info("  3. Click 'Save' to subscribe to relevant feeds")
        logger.info("  4. Visit http://localhost:3000/my-eu-bubble to see your personalized feed")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"❌ Error seeding RSS feeds: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_rss_feeds()
