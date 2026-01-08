"""
EC Newsletter Configuration

Configuration of European Commission newsletters to monitor.
Organized by strategic tier based on advocacy intelligence value.

Tier 1: Mission-critical newsletters for legislative tracking
Tier 2: High-value sector-specific newsletters
Tier 3: Specialized thematic newsletters
"""

from typing import List, Dict, Any


# Tier 1: Mission-Critical Newsletters (highest priority)
TIER1_NEWSLETTERS: List[Dict[str, Any]] = [
    {
        "dg_name": "DG COMP",
        "newsletter_name": "Competition Weekly e-News",
        "dg_code": "comp",
        "service_id": "2012",
        "subscription_url": "https://ec.europa.eu/newsroom/comp/user-subscriptions/2012/create",
        "archive_url": "https://ec.europa.eu/newsroom/comp/newsletter-archives/view/service/2012",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "weekly",
        "strategic_tier": "tier1",
        "description": "Antitrust investigations, merger decisions, state aid approvals, Digital Markets Act enforcement",
        "topics": ["Competition", "Antitrust", "Mergers", "State Aid", "Digital Markets"],
    },
    {
        "dg_name": "DG TAXUD",
        "newsletter_name": "EU Taxation and Customs News",
        "dg_code": "taxud",
        "service_id": "246",  # Found through research
        "subscription_url": "https://taxation-customs.ec.europa.eu/index_en",
        "archive_url": "https://ec.europa.eu/newsroom/taxud/newsletter-archives/view/service/246",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "monthly",
        "strategic_tier": "tier1",
        "description": "CBAM, VAT Digital Age, Pillar 2 minimum tax, customs policy",
        "topics": ["Taxation", "Customs", "CBAM", "VAT", "Tax Policy"],
    },
    {
        "dg_name": "DG ECFIN",
        "newsletter_name": "ECFIN e-news",
        "dg_code": "ecfin",
        "service_id": "121",
        "subscription_url": "https://economy-finance.ec.europa.eu/economic-and-financial-affairs-newsletter_en",
        "archive_url": "https://ec.europa.eu/newsroom/ecfin/newsletter-archives/view/service/121",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "fortnightly",
        "strategic_tier": "tier1",
        "description": "Economic forecasts, Recovery and Resilience Facility, European Semester, fiscal policy",
        "topics": ["Economic Policy", "Fiscal Policy", "RRF", "European Semester"],
    },
    {
        "dg_name": "DG CLIMA",
        "newsletter_name": "EU Climate Action Newsletter",
        "dg_code": "clima",
        "service_id": "1843",
        "subscription_url": "https://ec.europa.eu/newsroom/clima/user-subscriptions/1843/create",
        "archive_url": "https://ec.europa.eu/newsroom/clima/newsletter-archives/view/service/1843",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "monthly",
        "strategic_tier": "tier1",
        "description": "European Green Deal, Fit for 55, EU ETS, climate negotiations",
        "topics": ["Climate", "Green Deal", "Carbon Markets", "Climate Policy"],
    },
    {
        "dg_name": "Eurostat",
        "newsletter_name": "Eurostat News",
        "dg_code": "eurostat",
        "service_id": "estat",
        "subscription_url": "https://ec.europa.eu/eurostat/",
        "archive_url": None,
        "ingestion_method": "rss",
        "rss_feed_url": "https://ec.europa.eu/eurostat/api/dissemination/catalogue/rss/en/statistics-update.rss",
        "publication_frequency": "continuous",
        "strategic_tier": "tier1",
        "description": "Official EU statistics releases, economic indicators, population data",
        "topics": ["Statistics", "Economic Data", "Demographics", "Official Data"],
    },
    {
        "dg_name": "DG TRADE",
        "newsletter_name": "EU Trade Newsletter",
        "dg_code": "trade",
        "service_id": "230",
        "subscription_url": "https://ec.europa.eu/newsroom/trade/user-subscriptions/230/create",
        "archive_url": "https://ec.europa.eu/newsroom/trade/newsletter-archives/view/service/230",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "monthly",
        "strategic_tier": "tier1",
        "description": "Trade agreements, economic security, WTO, trade policy",
        "topics": ["Trade", "Trade Policy", "WTO", "Trade Agreements"],
    },
    {
        "dg_name": "DG GROW",
        "newsletter_name": "Internal Market, Industry, Entrepreneurship and SMEs Newsletter",
        "dg_code": "grow",
        "service_id": "2840",
        "subscription_url": "https://ec.europa.eu/newsroom/growth/user-subscriptions/2840/create",
        "archive_url": "https://ec.europa.eu/newsroom/grow/newsletter-archives/view/service/2840",
        "ingestion_method": "scrape",
        "rss_feed_url": "https://single-market-economy.ec.europa.eu/rss-feeds-dg-internal-market-industry-entrepreneurship-and-smes_en",
        "publication_frequency": "monthly",
        "strategic_tier": "tier1",
        "description": "Single market legislation, industrial policy, SME initiatives",
        "topics": ["Single Market", "Industry", "SMEs", "Industrial Policy"],
    },
    {
        "dg_name": "DG ENER",
        "newsletter_name": "DG Energy Newsletter",
        "dg_code": "ener",
        "service_id": "225",
        "subscription_url": "https://ec.europa.eu/newsroom/ener/subscription-quick-generic-form-fullpage.cfm?service_id=225",
        "archive_url": "https://ec.europa.eu/newsroom/ener/newsletter-archives/view/service/225",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "monthly",
        "strategic_tier": "tier1",
        "description": "Energy policy, renewable energy, energy efficiency, energy security",
        "topics": ["Energy", "Renewables", "Energy Efficiency", "Energy Policy"],
    },
    {
        "dg_name": "DG SANTE",
        "newsletter_name": "Health and Food Safety Newsletter",
        "dg_code": "sante",
        "service_id": "259",
        "subscription_url": "https://ec.europa.eu/newsroom/sante/user-subscriptions/259/create",
        "archive_url": "https://ec.europa.eu/newsroom/sante/newsletter-archives/view/service/259",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "monthly",
        "strategic_tier": "tier1",
        "description": "Farm to Fork, public health, EU4Health, food safety",
        "topics": ["Health", "Food Safety", "Farm to Fork", "Public Health"],
    },
    {
        "dg_name": "EUR-Lex",
        "newsletter_name": "EUR-Lex Newsletter",
        "dg_code": "eurlex",
        "service_id": "eurlex",
        "subscription_url": "https://eur-lex.europa.eu/newsletter/newsletterLatest.html",
        "archive_url": None,
        "ingestion_method": "rss",
        "rss_feed_url": None,  # EUR-Lex RSS requires EU Login
        "publication_frequency": "irregular",
        "strategic_tier": "tier1",
        "description": "Legislative database updates, search improvements, new features",
        "topics": ["EUR-Lex", "Legislation", "Database Updates"],
    },
]


# Tier 2: High-Value Sector-Specific Newsletters
TIER2_NEWSLETTERS: List[Dict[str, Any]] = [
    {
        "dg_name": "DG REGIO",
        "newsletter_name": "RegioFlash",
        "dg_code": "regio",
        "service_id": "1421",
        "subscription_url": "https://ec.europa.eu/regional_policy/information-sources/newsletter_en",
        "archive_url": "https://ec.europa.eu/newsroom/regio/newsletter-archives/view/service/1421",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "weekly",
        "strategic_tier": "tier2",
        "description": "Cohesion policy, regional development, structural funds (weekly Wed noon)",
        "topics": ["Regional Policy", "Cohesion", "Structural Funds", "Regional Development"],
    },
    {
        "dg_name": "DG FISMA",
        "newsletter_name": "Finance Newsletter",
        "dg_code": "fisma",
        "service_id": "263",
        "subscription_url": "https://ec.europa.eu/newsroom/fisma/user-subscriptions/263/create",
        "archive_url": "https://ec.europa.eu/newsroom/fisma/newsletter-archives/view/service/263",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "monthly",
        "strategic_tier": "tier2",
        "description": "Banking regulation, Capital Markets Union, crypto-assets, sustainable finance",
        "topics": ["Finance", "Banking", "CMU", "Crypto", "Sustainable Finance"],
    },
    {
        "dg_name": "DG HOME",
        "newsletter_name": "Migration and Home Affairs Newsletter",
        "dg_code": "home",
        "service_id": "1235",
        "subscription_url": "https://home-affairs.ec.europa.eu/whats-new/newsletter_en",
        "archive_url": "https://ec.europa.eu/newsroom/home/newsletter-archives/view/service/1235",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "irregular",
        "strategic_tier": "tier2",
        "description": "Migration Pact, asylum, Schengen, borders, internal security",
        "topics": ["Migration", "Asylum", "Schengen", "Internal Security", "Borders"],
    },
    {
        "dg_name": "DG JUST",
        "newsletter_name": "Justice and Consumers Newsletter",
        "dg_code": "just",
        "service_id": "1148",
        "subscription_url": "https://ec.europa.eu/newsroom/just/user-subscriptions/1148/create",
        "archive_url": "https://ec.europa.eu/newsroom/just/newsletter-archives/view/service/1148",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "irregular",
        "strategic_tier": "tier2",
        "description": "Justice programme funding, consumer rights, equality",
        "topics": ["Justice", "Consumer Rights", "Equality", "Funding"],
    },
    {
        "dg_name": "DG RTD",
        "newsletter_name": "R&I Data Express",
        "dg_code": "rtd",
        "service_id": "1875",
        "subscription_url": "https://ec.europa.eu/newsroom/rtd/user-subscriptions/1875/create",
        "archive_url": "https://ec.europa.eu/newsroom/rtd/newsletter-archives/view/service/1875",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "quarterly",
        "strategic_tier": "tier2",
        "description": "R&I indicators, Horizon Dashboard, R&D investment statistics",
        "topics": ["Research", "Innovation", "Horizon Europe", "R&D Statistics"],
    },
    {
        "dg_name": "CINEA",
        "newsletter_name": "CINEA Newsletter",
        "dg_code": "cinea",
        "service_id": "8813",
        "subscription_url": "https://ec.europa.eu/newsroom/cinea/user-subscriptions/8813/create",
        "archive_url": "https://ec.europa.eu/newsroom/cinea/newsletter-archives/view/service/8813",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "monthly",
        "strategic_tier": "tier2",
        "description": "Sustainable transport, clean energy, climate, environment programs",
        "topics": ["Transport", "Clean Energy", "Climate", "Environment", "Funding"],
    },
    {
        "dg_name": "JRC",
        "newsletter_name": "JRC Newsletter",
        "dg_code": "jrc",
        "service_id": "194",
        "subscription_url": "https://joint-research-centre.ec.europa.eu/jrc-newsletters_en",
        "archive_url": "https://ec.europa.eu/newsroom/jrc/newsletter-archives/view/service/194",
        "ingestion_method": "scrape",
        "rss_feed_url": None,
        "publication_frequency": "monthly",
        "strategic_tier": "tier2",
        "description": "Science and research supporting Commission policy across 25 portfolios",
        "topics": ["Science", "Research", "Policy Evidence", "JRC Research"],
    },
    {
        "dg_name": "Publications Office",
        "newsletter_name": "EU Publications Newsletter",
        "dg_code": "publications",
        "service_id": "publications",
        "subscription_url": "https://op.europa.eu/en/web/general-publications/newsletter-subscription",
        "archive_url": None,
        "ingestion_method": "rss",
        "rss_feed_url": None,  # Available but need to find exact URL
        "publication_frequency": "irregular",
        "strategic_tier": "tier2",
        "description": "Official EU publications, documents, reports",
        "topics": ["Publications", "Official Documents", "Reports"],
    },
]


# Combined list of all newsletters
ALL_NEWSLETTERS = TIER1_NEWSLETTERS + TIER2_NEWSLETTERS


def get_newsletters_by_tier(tier: str) -> List[Dict[str, Any]]:
    """Get newsletters by strategic tier"""
    return [n for n in ALL_NEWSLETTERS if n["strategic_tier"] == tier]


def get_newsletter_by_dg_code(dg_code: str) -> List[Dict[str, Any]]:
    """Get newsletters for a specific DG"""
    return [n for n in ALL_NEWSLETTERS if n["dg_code"] == dg_code]


def get_scrapable_newsletters() -> List[Dict[str, Any]]:
    """Get newsletters that use web scraping"""
    return [n for n in ALL_NEWSLETTERS if n["ingestion_method"] == "scrape"]


def get_rss_newsletters() -> List[Dict[str, Any]]:
    """Get newsletters that have RSS feeds"""
    return [n for n in ALL_NEWSLETTERS if n["ingestion_method"] == "rss" and n["rss_feed_url"]]
