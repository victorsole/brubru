#!/usr/bin/env python3
"""
EU Institutional News Scraper

Scrapes latest headlines from 44 EU institutional news portals.
Used internally to keep Brubru's knowledge base, tracked files,
and chatbot guides up to date.

Usage:
    python3.12 scripts/scrape_eu_news.py                  # Last 24h, all portals
    python3.12 scripts/scrape_eu_news.py --hours 48       # Last 48h
    python3.12 scripts/scrape_eu_news.py --category ec    # Commission DGs only
    python3.12 scripts/scrape_eu_news.py --category ep    # EP only
    python3.12 scripts/scrape_eu_news.py --category council  # Council only
    python3.12 scripts/scrape_eu_news.py --top 20         # Top 20 items only
    python3.12 scripts/scrape_eu_news.py --json           # JSON output
"""

import asyncio
import argparse
import json
import sys
import os
import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import httpx
    from bs4 import BeautifulSoup
except ImportError:
    print("[ERROR] Required: pip install httpx beautifulsoup4")
    sys.exit(1)


# ─── Portal Definitions ──────────────────────────────────────────────────────

@dataclass
class NewsItem:
    title: str
    url: str
    date: Optional[str] = None
    source: str = ""
    category: str = ""  # ec, ep, council, ecb, agency
    priority: int = 99  # lower = higher priority
    snippet: str = ""

    def age_label(self) -> str:
        if not self.date:
            return ""
        try:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d %B %Y", "%B %d, %Y"):
                try:
                    dt = datetime.strptime(self.date, fmt)
                    days = (datetime.now() - dt).days
                    if days == 0:
                        return "today"
                    elif days == 1:
                        return "yesterday"
                    else:
                        return f"{days}d ago"
                except ValueError:
                    continue
        except Exception:
            pass
        return self.date


PORTALS = [
    # ── European Commission: Central ─────────────────────────────────────
    {"url": "https://ec.europa.eu/commission/presscorner/api/search?language=en&pageSize=20",
     "source": "EC Press Corner", "category": "ec", "priority": 1, "type": "json_api"},
    {"url": "https://commission.europa.eu/news-and-media/news_en",
     "source": "EC News", "category": "ec", "priority": 1},

    # ── Commission DGs ───────────────────────────────────────────────────
    {"url": "https://agriculture.ec.europa.eu/media/news_en",
     "source": "DG AGRI", "category": "ec", "priority": 3},
    {"url": "https://commission.europa.eu/news-and-media/news_en?f%5B0%5D=oe_news_departments%3Ahttp%3A//publications.europa.eu/resource/authority/corporate-body/BUDG#oe-list-page-filters-anchor",
     "source": "DG BUDG", "category": "ec", "priority": 4},
    {"url": "https://climate.ec.europa.eu/news-other-reads/news_en",
     "source": "DG CLIMA", "category": "ec", "priority": 3},
    {"url": "https://digital-strategy.ec.europa.eu/en/news",
     "source": "DG CNECT", "category": "ec", "priority": 2},
    {"url": "https://competition-policy.ec.europa.eu/about/news_en",
     "source": "DG COMP", "category": "ec", "priority": 3},
    {"url": "https://defence-industry-space.ec.europa.eu/newsroom/latest-news_en",
     "source": "DG DEFIS", "category": "ec", "priority": 3},
    {"url": "https://economy-finance.ec.europa.eu/ecfin-news_en",
     "source": "DG ECFIN", "category": "ec", "priority": 3},
    {"url": "https://employment-social-affairs.ec.europa.eu/news_en",
     "source": "DG EMPL", "category": "ec", "priority": 3},
    {"url": "https://energy.ec.europa.eu/news_en",
     "source": "DG ENER", "category": "ec", "priority": 3},
    {"url": "https://enlargement.ec.europa.eu/about-us/latest-news_en",
     "source": "DG NEAR", "category": "ec", "priority": 3},
    {"url": "https://environment.ec.europa.eu/news_en",
     "source": "DG ENV", "category": "ec", "priority": 3},
    {"url": "https://anti-fraud.ec.europa.eu/media-corner/news_en",
     "source": "OLAF", "category": "ec", "priority": 4},
    {"url": "https://civil-protection-humanitarian-aid.ec.europa.eu/news-stories/news_en",
     "source": "DG ECHO", "category": "ec", "priority": 3},
    {"url": "https://finance.ec.europa.eu/finance-news_en",
     "source": "DG FISMA", "category": "ec", "priority": 3},
    {"url": "https://food.ec.europa.eu/food-safety-news-0_en?prefLang=pl&f%5B0%5D=oe_news_types%3Ahttp%3A//publications.europa.eu/resource/authority/resource-type/ANNOUNC_NEWS&f%5B1%5D=oe_news_types%3Ahttp%3A//publications.europa.eu/resource/authority/resource-type/ARTICLE_NEWS",
     "source": "DG SANTE (Food)", "category": "ec", "priority": 3},
    {"url": "https://health.ec.europa.eu/latest-updates_en",
     "source": "DG SANTE (Health)", "category": "ec", "priority": 3},
    {"url": "https://health.ec.europa.eu/health-emergency-preparedness-and-response-hera/latest-updates_en",
     "source": "HERA", "category": "ec", "priority": 4},
    {"url": "https://fpi.ec.europa.eu/news_en",
     "source": "FPI", "category": "ec", "priority": 4},
    {"url": "https://single-market-economy.ec.europa.eu/news_en",
     "source": "DG GROW", "category": "ec", "priority": 3},
    {"url": "https://international-partnerships.ec.europa.eu/news-and-events/news_en",
     "source": "DG INTPA", "category": "ec", "priority": 3},
    {"url": "https://joint-research-centre.ec.europa.eu/news-announcements_en",
     "source": "JRC", "category": "ec", "priority": 4},
    {"url": "https://commission.europa.eu/news-and-media/news_en?f%5B0%5D=oe_news_departments%3Ahttp%3A//publications.europa.eu/resource/authority/corporate-body/JUST#oe-list-page-filters-anchor",
     "source": "DG JUST", "category": "ec", "priority": 3},
    {"url": "https://oceans-and-fisheries.ec.europa.eu/news_en",
     "source": "DG MARE", "category": "ec", "priority": 3},
    {"url": "https://north-africa-middle-east-gulf.ec.europa.eu/about-us/latest-news_en",
     "source": "DG NEAR (MENA)", "category": "ec", "priority": 4},
    {"url": "https://home-affairs.ec.europa.eu/whats-new/news_en",
     "source": "DG HOME", "category": "ec", "priority": 3},
    {"url": "https://transport.ec.europa.eu/news-events/news_en",
     "source": "DG MOVE", "category": "ec", "priority": 3},
    {"url": "https://op.europa.eu/en/home",
     "source": "Publications Office", "category": "ec", "priority": 5},
    {"url": "https://commission.europa.eu/about/departments-and-executive-agencies/reform-and-investment-task-force/latest_en",
     "source": "REFORM Task Force", "category": "ec", "priority": 4},
    {"url": "https://ec.europa.eu/regional_policy/whats-new/newsroom_en",
     "source": "DG REGIO", "category": "ec", "priority": 3},
    {"url": "https://research-and-innovation.ec.europa.eu/news/all-research-and-innovation-news_en",
     "source": "DG RTD", "category": "ec", "priority": 3},
    {"url": "https://taxation-customs.ec.europa.eu/news_en",
     "source": "DG TAXUD", "category": "ec", "priority": 3},
    {"url": "https://policy.trade.ec.europa.eu/news_en",
     "source": "DG TRADE", "category": "ec", "priority": 3},

    # ── Executive Agencies ───────────────────────────────────────────────
    {"url": "https://cinea.ec.europa.eu/news-events/news_en",
     "source": "CINEA", "category": "agency", "priority": 5},
    {"url": "https://www.eacea.ec.europa.eu/news-events/news_en",
     "source": "EACEA", "category": "agency", "priority": 5},
    {"url": "https://hadea.ec.europa.eu/news_en",
     "source": "HaDEA", "category": "agency", "priority": 5},
    {"url": "https://eismea.ec.europa.eu/news_en",
     "source": "EISMEA", "category": "agency", "priority": 5},
    {"url": "https://eu-careers.europa.eu/en/about-epso",
     "source": "EPSO", "category": "agency", "priority": 5},
    {"url": "https://rea.ec.europa.eu/news_en",
     "source": "REA", "category": "agency", "priority": 5},
    {"url": "https://ec.europa.eu/eurostat/en/web/main/news/news-articles",
     "source": "Eurostat", "category": "agency", "priority": 4},

    # ── European Parliament ──────────────────────────────────────────────
    {"url": "https://www.europarl.europa.eu/news/en",
     "source": "European Parliament", "category": "ep", "priority": 1},

    # ── EU Policy News (via Politico EU RSS, covers Council/Commission/EP) ──
    {"url": "https://www.politico.eu/feed/",
     "source": "Politico EU", "category": "ec", "priority": 1, "type": "politico_eu"},

    # ── ECB Press Releases (via RSS) ─────────────────────────────────
    {"url": "https://www.ecb.europa.eu/rss/press.html",
     "source": "ECB", "category": "ecb", "priority": 2},

    # ── Official Journal L-series (adopted legislation via EUR-Lex RSS) ─
    {"url": "https://eur-lex.europa.eu/EN/display-feed.rss?rssId=222",
     "source": "Official Journal (L)", "category": "ec", "priority": 1, "type": "oj_rss"},

    # ── Official Journal C-series (information/notices via EUR-Lex RSS) ─
    {"url": "https://eur-lex.europa.eu/EN/display-feed.rss?rssId=221",
     "source": "Official Journal (C)", "category": "ec", "priority": 2, "type": "oj_rss"},
]


# ─── Priority labels for news items ──────────────────────────────────────────

PRIORITY_KEYWORDS_HIGH = [
    # New laws / legislation
    r'\b(regulation|directive|decision)\s+\(eu\)',
    r'\badopt(s|ed|ion)\b.*\b(regulation|directive|legislation|law|package)\b',
    r'\benter(s|ed)?\s+into\s+force\b',
    r'\bofficial\s+journal\b',
    # Commission communications / proposals
    r'\bcommunication\b.*\bcommission\b',
    r'\bcommission\b.*\b(propos|adopt|present|publish)\b',
    r'\blegislative\s+propos',
    r'\baction\s+plan\b',
    r'\bwhite\s+paper\b',
    r'\bgreen\s+paper\b',
    r'\bpackage\b',
    # EP resolutions
    r'\bresolution\b',
    r'\bplenary\b.*\b(vote|adopt|approv)\b',
    # Council
    r'\bgeneral\s+approach\b',
    r'\bcouncil\b.*\b(adopt|agree|approv|position)\b',
    r'\btrilogue\b',
    r'\bpolitical\s+agreement\b',
]

PRIORITY_KEYWORDS_MEDIUM = [
    r'\bconsultation\b',
    r'\bpublic\s+hearing\b',
    r'\breport\b',
    r'\bstudy\b',
    r'\bstatistics\b',
    r'\bfunding\b',
    r'\bcall\s+for\s+(proposals|tender)',
    r'\binfringement\b',
]


def classify_priority(title: str, base_priority: int) -> int:
    """Adjust priority based on headline keywords."""
    title_lower = title.lower()
    for pattern in PRIORITY_KEYWORDS_HIGH:
        if re.search(pattern, title_lower):
            return min(base_priority, 1)
    for pattern in PRIORITY_KEYWORDS_MEDIUM:
        if re.search(pattern, title_lower):
            return min(base_priority, 2)
    return base_priority


# ─── Scraping Logic ──────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

# Date patterns commonly found on EU institutional pages
DATE_PATTERNS = [
    re.compile(r'(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})', re.I),
    re.compile(r'(\d{4})-(\d{2})-(\d{2})'),
    re.compile(r'(\d{1,2})/(\d{1,2})/(\d{4})'),
]

MONTH_MAP = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
}


def parse_date_text(text: str) -> Optional[str]:
    """Try to extract a date from text, return as YYYY-MM-DD or None."""
    if not text:
        return None
    for pattern in DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            groups = m.groups()
            try:
                if len(groups) == 3 and groups[1].isalpha():
                    day, month_name, year = groups
                    month = MONTH_MAP.get(month_name.lower())
                    if month:
                        return f"{year}-{month:02d}-{int(day):02d}"
                elif len(groups) == 3 and all(g.isdigit() for g in groups):
                    a, b, c = groups
                    if len(a) == 4:
                        return f"{a}-{b}-{c}"
                    elif len(c) == 4:
                        return f"{c}-{b}-{a}"
            except (ValueError, KeyError):
                continue
    return None


async def scrape_ec_press_corner_api(client: httpx.AsyncClient, portal: dict) -> List[NewsItem]:
    """Scrape EC Press Corner via their JSON API."""
    items = []
    source = portal["source"]
    try:
        response = await client.get(portal["url"], follow_redirects=True)
        response.raise_for_status()
        data = response.json()
        for doc in data.get("docuLanguageListResources", []):
            if doc.get("languageCode") != "EN":
                continue
            title = doc.get("title", "").strip()
            if not title:
                continue
            ref_code = doc.get("refCode", "")
            date = doc.get("eventDate", "")
            doc_type = doc.get("docutype", {}).get("code", "")
            # Build URL from reference code
            url = f"https://ec.europa.eu/commission/presscorner/detail/en/{ref_code.lower().replace('/', '_')}" if ref_code else ""
            # Boost priority for IP (press releases) and MEX (daily news)
            base_priority = 1
            if doc_type in ("IP", "MEX", "AC"):
                base_priority = 1
            elif doc_type == "SPEECH":
                base_priority = 3
            elif doc_type == "STATEMENT":
                base_priority = 2
            else:
                base_priority = 2
            priority = classify_priority(title, base_priority)
            items.append(NewsItem(
                title=f"[{doc_type}] {title}" if doc_type else title,
                url=url,
                date=date[:10] if date else None,
                source=source,
                category=portal["category"],
                priority=priority,
            ))
    except Exception as e:
        print(f"  [ERROR] {source} API: {str(e)[:80]}", file=sys.stderr)
    return items


async def scrape_politico_eu(portal: dict) -> List[NewsItem]:
    """Scrape Politico EU RSS for EU policy news (covers Council, Commission, EP).

    Since consilium.europa.eu is Cloudflare-blocked, Politico is the best source
    for Council and cross-institutional EU policy news.
    """
    items = []
    # Categories that signal EU institutional news (from Politico's RSS category tags)
    eu_categories = {
        'foreign affairs', 'diplomacy', 'enlargement', 'defense', 'defence',
        'trade', 'energy', 'climate', 'digital', 'migration', 'regulation',
        'competition', 'single market', 'eu budget', 'agriculture',
    }
    # Title keywords for Council-specific items
    council_keywords = [
        'council', 'minister', 'presidency', 'euco', 'european council',
        'member state', 'general approach', 'trilogue', 'coreper', 'summit',
        'heads of state', 'foreign affairs council', 'ecofin',
    ]
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(portal["url"], headers={'User-Agent': HEADERS['User-Agent']})
            if resp.status_code != 200:
                print(f"  [WARN] Politico RSS returned {resp.status_code}", file=sys.stderr)
                return items

            from xml.etree import ElementTree as ET
            root = ET.fromstring(resp.text)
            for item_el in root.findall('.//item'):
                title = (item_el.find('title').text or '').strip()
                link = (item_el.find('link').text or '').strip()
                pubdate_el = item_el.find('pubDate')
                pubdate = pubdate_el.text if pubdate_el is not None else ''

                # Check RSS categories for EU relevance
                item_cats = set()
                for cat_el in item_el.findall('category'):
                    if cat_el.text:
                        item_cats.add(cat_el.text.lower())

                title_lower = title.lower()

                # Determine if Council-specific or general EU
                is_council = any(kw in title_lower for kw in council_keywords)
                is_eu_policy = bool(item_cats & eu_categories) or any(
                    kw in title_lower for kw in [
                        'eu ', 'european', 'commission', 'parliament', 'brussels',
                        'von der leyen', 'regulation', 'directive',
                    ]
                )

                if is_council or is_eu_policy:
                    category = "council" if is_council else portal["category"]
                    date_str = parse_date_text(pubdate) if pubdate else None
                    priority = classify_priority(title, portal["priority"])
                    items.append(NewsItem(
                        title=title,
                        url=link,
                        date=date_str,
                        source="Politico EU",
                        category=category,
                        priority=priority,
                    ))
    except Exception as e:
        print(f"  [ERROR] Politico EU RSS: {str(e)[:80]}", file=sys.stderr)
    return items


async def scrape_oj_rss(portal: dict) -> List[NewsItem]:
    """Scrape Official Journal via EUR-Lex predefined RSS feeds.

    Uses rssId=222 for OJ L-series (legislation) and rssId=221 for OJ C-series.
    These feeds are maintained by the Publications Office and return up to 100 items.
    """
    items = []
    source = portal["source"]
    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            resp = await client.get(portal["url"], headers={
                'User-Agent': HEADERS['User-Agent'],
                'Accept': 'application/rss+xml, text/xml, */*',
            })
            if resp.status_code != 200:
                print(f"  [WARN] {source} RSS returned {resp.status_code}", file=sys.stderr)
                return items

            from xml.etree import ElementTree as ET
            root = ET.fromstring(resp.text)

            # Filter for significant legislation (skip corrections, court cases, etc.)
            skip_prefixes = ['Corrigendum', 'Rectificatif', 'Case ', 'Affaire ']

            for item_el in root.findall('.//item'):
                title_raw = (item_el.find('title').text or '').strip()
                link = (item_el.find('link').text or '').strip()
                pubdate_el = item_el.find('pubDate')
                pubdate = pubdate_el.text if pubdate_el is not None else ''

                # Extract CELEX from title (format: "CELEX:XXXXX: Title text")
                celex = ''
                title = title_raw
                if title_raw.startswith('CELEX:'):
                    parts = title_raw.split(':', 2)
                    if len(parts) >= 3:
                        celex = parts[1].strip()
                        title = parts[2].strip()
                    elif len(parts) == 2:
                        celex = parts[1].strip()

                # Skip corrections, court cases, and empty titles
                if not title or any(title.startswith(p) for p in skip_prefixes):
                    continue

                # Fix EUR-Lex relative URLs
                if link.startswith('.'):
                    link = f"https://eur-lex.europa.eu{link[1:]}"

                date_str = parse_date_text(pubdate) if pubdate else None
                priority = classify_priority(title, portal["priority"])

                display_title = f"{title[:200]}"
                if celex:
                    display_title = f"[{celex}] {display_title}"

                items.append(NewsItem(
                    title=display_title,
                    url=link,
                    date=date_str,
                    source=source,
                    category=portal["category"],
                    priority=priority,
                ))

            # Limit to top 15 most significant items (feeds return up to 100)
            items = items[:15]

    except Exception as e:
        print(f"  [ERROR] {source} RSS: {str(e)[:80]}", file=sys.stderr)
    return items


async def scrape_portal(client: httpx.AsyncClient, portal: dict) -> List[NewsItem]:
    """Scrape a single news portal for headlines."""
    items = []
    url = portal["url"]
    source = portal["source"]
    category = portal["category"]
    base_priority = portal["priority"]

    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        # Strategy: find article/news links
        # EU sites typically use <article>, <div class="views-row">,
        # or lists of links with dates

        # Try common EU site patterns
        candidates = []

        # Pattern 1: <article> tags
        for article in soup.find_all('article', limit=15):
            link = article.find('a', href=True)
            if link and link.text.strip():
                title = link.text.strip()
                href = link['href']
                date_el = article.find('time') or article.find(class_=re.compile(r'date|time|meta'))
                date_text = date_el.get('datetime', date_el.text) if date_el else ""
                candidates.append((title, href, date_text))

        # Pattern 2: <div> with news-related classes
        if not candidates:
            for div in soup.find_all('div', class_=re.compile(r'views-row|news-item|listing-item|card|teaser'), limit=15):
                link = div.find('a', href=True)
                if link and link.text.strip() and len(link.text.strip()) > 15:
                    title = link.text.strip()
                    href = link['href']
                    date_el = div.find('time') or div.find(class_=re.compile(r'date|time|meta'))
                    date_text = date_el.get('datetime', date_el.text) if date_el else ""
                    candidates.append((title, href, date_text))

        # Pattern 3: <h2> or <h3> with links (common on newer EC sites)
        if not candidates:
            for heading in soup.find_all(['h2', 'h3', 'h4'], limit=20):
                link = heading.find('a', href=True)
                if link and link.text.strip() and len(link.text.strip()) > 15:
                    title = link.text.strip()
                    href = link['href']
                    parent = heading.parent
                    date_el = parent.find('time') if parent else None
                    date_text = date_el.get('datetime', date_el.text) if date_el else ""
                    candidates.append((title, href, date_text))

        # Pattern 4: Generic link scan (fallback)
        if not candidates:
            for link in soup.find_all('a', href=True, limit=30):
                href = link.get('href', '')
                title = link.text.strip()
                if (title and len(title) > 20 and len(title) < 300
                        and '/news/' in href or '/press/' in href
                        or '/latest/' in href or '/whats-new/' in href):
                    candidates.append((title, href, ""))

        # Deduplicate and build items
        seen_titles = set()
        for title, href, date_text in candidates[:10]:
            # Clean title
            title = re.sub(r'\s+', ' ', title).strip()
            if title in seen_titles or len(title) < 10:
                continue
            seen_titles.add(title)

            # Normalise URL
            if href.startswith('/'):
                from urllib.parse import urlparse
                parsed = urlparse(url)
                href = f"{parsed.scheme}://{parsed.netloc}{href}"

            # Parse date
            date = parse_date_text(date_text) or parse_date_text(title)

            # Classify priority
            priority = classify_priority(title, base_priority)

            items.append(NewsItem(
                title=title,
                url=href,
                date=date,
                source=source,
                category=category,
                priority=priority,
            ))

    except httpx.TimeoutException:
        print(f"  [TIMEOUT] {source}: {url[:60]}...", file=sys.stderr)
    except Exception as e:
        print(f"  [ERROR] {source}: {str(e)[:80]}", file=sys.stderr)

    return items


def is_recent(item: NewsItem, hours: int) -> bool:
    """Check if a news item is within the time window."""
    if not item.date:
        return True  # Include undated items (they're likely recent)
    try:
        dt = datetime.strptime(item.date, "%Y-%m-%d")
        cutoff = datetime.now() - timedelta(hours=hours)
        return dt >= cutoff.replace(hour=0, minute=0, second=0, microsecond=0)
    except ValueError:
        return True


def format_news_report(items: List[NewsItem], hours: int) -> str:
    """Format news items into a readable report."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"EU INSTITUTIONAL NEWS DIGEST")
    lines.append(f"Generated: {now} | Window: last {hours}h | Items: {len(items)}")
    lines.append("=" * 70)

    # Group by priority
    high = [i for i in items if i.priority <= 1]
    medium = [i for i in items if i.priority == 2]
    standard = [i for i in items if i.priority == 3]
    low = [i for i in items if i.priority >= 4]

    if high:
        lines.append("")
        lines.append(f"HIGH PRIORITY ({len(high)} items)")
        lines.append("-" * 40)
        for item in high:
            date_label = f" [{item.date}]" if item.date else ""
            lines.append(f"  [{item.source}]{date_label}")
            lines.append(f"  {item.title}")
            lines.append(f"  {item.url}")
            lines.append("")

    if medium:
        lines.append(f"MEDIUM PRIORITY ({len(medium)} items)")
        lines.append("-" * 40)
        for item in medium:
            date_label = f" [{item.date}]" if item.date else ""
            lines.append(f"  [{item.source}]{date_label} {item.title}")
            lines.append(f"  {item.url}")
            lines.append("")

    if standard:
        lines.append(f"STANDARD ({len(standard)} items)")
        lines.append("-" * 40)
        for item in standard:
            date_label = f" [{item.date}]" if item.date else ""
            lines.append(f"  [{item.source}]{date_label} {item.title}")
        lines.append("")

    if low:
        lines.append(f"LOW PRIORITY / AGENCIES ({len(low)} items)")
        lines.append("-" * 40)
        for item in low:
            date_label = f" [{item.date}]" if item.date else ""
            lines.append(f"  [{item.source}]{date_label} {item.title}")
        lines.append("")

    # Stats
    lines.append("=" * 70)
    by_cat = {}
    for item in items:
        by_cat[item.category] = by_cat.get(item.category, 0) + 1
    stats = ", ".join(f"{k}: {v}" for k, v in sorted(by_cat.items()))
    lines.append(f"By category: {stats}")

    # Warn about missing categories
    expected_cats = {"ec", "ep", "council", "ecb"}
    missing = expected_cats - set(by_cat.keys())
    if missing:
        lines.append(f"[WARN] No items from: {', '.join(sorted(missing))} (Cloudflare/JS-rendered -- check manually)")

    return "\n".join(lines)


def fetch_committee_work_items(hours: int = 48) -> List[NewsItem]:
    """Fetch recent EP committee draft reports and amendments from the database.

    Requires sync_committee_work.py to have run first (called by --save flow).
    Returns NewsItems for draft reports, opinions, and amendments updated recently.
    """
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / '.env')

    items = []
    try:
        import psycopg2
        db_url = os.environ.get('DATABASE_URL', '')
        if not db_url:
            return items

        conn = psycopg2.connect(db_url)
        cur = conn.cursor()

        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()

        # Draft reports and opinions updated recently
        cur.execute("""
            SELECT procedure_ref, title, committee_code, committee_role,
                   rapporteur_name, status, ep_page_url, oeil_url, last_updated
            FROM committee_work_items
            WHERE last_updated >= %s
            ORDER BY last_updated DESC
            LIMIT 30
        """, (cutoff,))

        for row in cur.fetchall():
            proc_ref, title, committee, role, rapporteur, status, ep_url, oeil_url, last_updated = row
            # Build a clean headline
            role_label = "Draft Report" if role == "LEAD" else "Opinion"
            rapporteur_str = f" (rapporteur: {rapporteur})" if rapporteur else ""
            headline = f"{committee} {role_label}: {title}{rapporteur_str}"
            if proc_ref:
                headline += f" [{proc_ref}]"

            url = ep_url or oeil_url or f"https://oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do?reference={proc_ref}"
            date_str = last_updated.strftime('%Y-%m-%d') if last_updated else None

            items.append(NewsItem(
                title=headline,
                url=url,
                date=date_str,
                source=f"EP {committee}",
                category="ep",
                priority=2,  # High priority: committee legislative work
            ))

        # Also check for recent amendment documents
        cur.execute("""
            SELECT DISTINCT ad.procedure_reference, ad.pe_reference, ad.document_date,
                   ad.doceo_url, COUNT(ma.id) as amendment_count
            FROM amendment_documents ad
            JOIN mep_amendments ma ON ma.procedure_reference = ad.procedure_reference
                AND ma.pe_reference = ad.pe_reference
            WHERE ad.scraped_at >= %s
            GROUP BY ad.procedure_reference, ad.pe_reference, ad.document_date, ad.doceo_url
            ORDER BY ad.document_date DESC
            LIMIT 15
        """, (cutoff,))

        for row in cur.fetchall():
            proc_ref, pe_ref, doc_date, doceo_url, am_count = row
            headline = f"EP Amendments: {am_count} amendments filed on {proc_ref} ({pe_ref})"
            date_str = doc_date.strftime('%Y-%m-%d') if doc_date else None
            url = doceo_url or f"https://oeil.secure.europarl.europa.eu/oeil/popups/ficheprocedure.do?reference={proc_ref}"

            items.append(NewsItem(
                title=headline,
                url=url,
                date=date_str,
                source="EP Amendments",
                category="ep",
                priority=2,
            ))

        conn.close()
        print(f"  [OK] EP Committee Work: {len(items)} items from database", file=sys.stderr)

    except Exception as e:
        print(f"  [WARN] EP Committee Work fetch failed: {str(e)[:80]}", file=sys.stderr)

    return items


def run_committee_work_sync():
    """Run the committee work sync script before fetching items."""
    import subprocess
    script_path = os.path.join(os.path.dirname(__file__), 'sync_committee_work.py')
    if not os.path.exists(script_path):
        print("  [WARN] sync_committee_work.py not found, skipping", file=sys.stderr)
        return False
    try:
        result = subprocess.run(
            [sys.executable, script_path, '--max-pages', '2'],
            capture_output=True, text=True, timeout=180,
            cwd=os.path.join(os.path.dirname(__file__), '..')
        )
        if result.returncode == 0:
            print("  [OK] Committee work sync completed", file=sys.stderr)
            return True
        else:
            print(f"  [WARN] Committee work sync failed: {result.stderr[:100]}", file=sys.stderr)
            return False
    except subprocess.TimeoutExpired:
        print("  [WARN] Committee work sync timed out (3min limit)", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  [WARN] Committee work sync error: {str(e)[:80]}", file=sys.stderr)
        return False


async def main():
    parser = argparse.ArgumentParser(description='Scrape EU institutional news portals')
    parser.add_argument('--hours', type=int, default=24,
                        help='Time window in hours (default: 24)')
    parser.add_argument('--category', '-c', type=str, default=None,
                        choices=['ec', 'ep', 'council', 'ecb', 'agency'],
                        help='Filter by institution category')
    parser.add_argument('--top', type=int, default=None,
                        help='Show only top N items by priority')
    parser.add_argument('--json', action='store_true',
                        help='Output as JSON')
    parser.add_argument('--concurrency', type=int, default=5,
                        help='Max concurrent requests (default: 5)')
    parser.add_argument('--save', action='store_true',
                        help='Save top headlines to daily_briefs table for chat Daily Brief')
    parser.add_argument('--skip-committee-sync', action='store_true',
                        help='Skip running committee work sync (use existing DB data only)')
    args = parser.parse_args()

    # Filter portals
    portals = PORTALS
    if args.category:
        portals = [p for p in portals if p["category"] == args.category]

    # Use stderr for progress so --json stdout is clean
    log = lambda msg: print(msg, file=sys.stderr)
    log(f"[START] Scraping {len(portals)} EU news portals (last {args.hours}h)...")

    all_items = []

    async with httpx.AsyncClient(
        headers=HEADERS,
        timeout=20.0,
        follow_redirects=True,
    ) as client:
        # Process in batches for controlled concurrency
        sem = asyncio.Semaphore(args.concurrency)

        async def scrape_with_sem(portal):
            async with sem:
                portal_type = portal.get("type", "html")
                if portal_type == "json_api":
                    result = await scrape_ec_press_corner_api(client, portal)
                elif portal_type == "politico_eu":
                    result = await scrape_politico_eu(portal)
                elif portal_type == "oj_rss":
                    result = await scrape_oj_rss(portal)
                else:
                    result = await scrape_portal(client, portal)
                if result:
                    log(f"  [OK] {portal['source']}: {len(result)} items")
                else:
                    log(f"  [--] {portal['source']}: 0 items")
                return result

        tasks = [scrape_with_sem(p) for p in portals]
        results = await asyncio.gather(*tasks)

        for portal_items in results:
            all_items.extend(portal_items)

    # EP Committee Work: draft reports, opinions, amendments from database
    if not args.category or args.category == 'ep':
        log("\n[START] EP Committee Work (draft reports and amendments)...")
        if not args.skip_committee_sync:
            run_committee_work_sync()
        committee_items = fetch_committee_work_items(hours=args.hours * 2)  # wider window for DB items
        all_items.extend(committee_items)

    # Filter by time window
    all_items = [i for i in all_items if is_recent(i, args.hours)]

    # Sort: priority first, then date (newest first)
    all_items.sort(key=lambda x: (x.priority, x.date or "0000"), reverse=False)
    # For same priority, reverse date sort (newest first)
    all_items.sort(key=lambda x: (x.priority, -(hash(x.date) if x.date else 0)))

    # Deduplicate by title similarity
    seen = set()
    unique_items = []
    for item in all_items:
        key = re.sub(r'\s+', ' ', item.title.lower().strip())[:80]
        if key not in seen:
            seen.add(key)
            unique_items.append(item)
    all_items = unique_items

    # Filter out obvious non-news (staff pages, navigation links, etc.)
    NON_NEWS_PATTERNS = [
        r'^(director|head of|deputy|acting head|senior|acting)\s*[:\-]',  # EPSO staff listings
        r'^news in \d{4}$',  # DG HOME "News in 2022" type links
        r'^(eu research results|eur-lex online|widgets:|eu solidarity)$',  # Publications Office static links
    ]
    all_items = [
        item for item in all_items
        if not any(re.match(p, item.title.lower()) for p in NON_NEWS_PATTERNS)
    ]

    # Apply top-N filter
    if args.top:
        all_items = all_items[:args.top]

    log(f"\n[DONE] {len(all_items)} news items found\n")

    if args.json:
        output = [asdict(item) for item in all_items]
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        report = format_news_report(all_items, args.hours)
        print(report)

    # Save top headlines to database for Daily Brief feature
    if args.save:
        save_to_daily_briefs(all_items[:20])


def generate_suggested_query(headline: str) -> str:
    """Turn a news headline into a natural question for the chatbot."""
    # Strip EC Press Corner prefixes like [IP], [MEX], [QANDA], [FS]
    h = re.sub(r'^\[(?:IP|MEX|QANDA|FS|SPEECH|STATEMENT)\]\s*', '', headline).strip()
    # Strip common institution prefixes
    h = re.sub(r'^(commission|council|parliament|ep|ec)\s*:\s*', '', h, flags=re.IGNORECASE).strip()
    # If it already looks like a question, use it
    if h.endswith('?'):
        return h
    # Short headlines: prefix with "What is"
    if len(h.split()) <= 6:
        return f"What is the {h}?"
    # Longer headlines: "Tell me about"
    return f"Tell me about the {h[:120]}"


def save_to_daily_briefs(items: List[NewsItem]):
    """Save top headlines to the daily_briefs database table."""
    from pathlib import Path
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / '.env')

    try:
        import psycopg2
        db_url = os.environ.get('DATABASE_URL', '')
        if not db_url:
            print("[WARN] No DATABASE_URL, skipping save", file=sys.stderr)
            return

        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        today = datetime.now().strftime('%Y-%m-%d')
        saved = 0

        for item in items:
            try:
                # Clean headline: strip [IP], [MEX], etc. prefixes
                clean_headline = re.sub(r'^\[(?:IP|MEX|QANDA|FS|SPEECH|STATEMENT)\]\s*', '', item.title).strip()
                cur.execute(
                    """INSERT INTO daily_briefs (brief_date, headline, url, source, category, priority, snippet, suggested_query)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                       ON CONFLICT (brief_date, url) DO NOTHING""",
                    (today, clean_headline, item.url, item.source, item.category,
                     item.priority, item.snippet or None,
                     generate_suggested_query(item.title))
                )
                if cur.rowcount > 0:
                    saved += 1
            except Exception as e:
                print(f"  [ERROR] Failed to save: {str(e)[:60]}", file=sys.stderr)

        conn.close()
        print(f"[OK] Saved {saved} headlines to daily_briefs for {today}", file=sys.stderr)

    except Exception as e:
        print(f"[ERROR] Database save failed: {str(e)[:80]}", file=sys.stderr)


if __name__ == '__main__':
    asyncio.run(main())
