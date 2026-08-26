"""
EUR-Lex Summary Scraper

Scrapes EUR-Lex "Summaries of EU Legislation" by policy chapter and generates
knowledge guide markdown files for use in the AI context builder.

EUR-Lex organises summaries into 32 numbered chapters. Each chapter page lists
summary pages, and each summary page contains structured information about
key EU legislation in that policy area.

Source: https://eur-lex.europa.eu/summary/chapter/{chapter_id}.html
"""

import logging
import re
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    import httpx
    from bs4 import BeautifulSoup
except ImportError:
    logger.error("Required packages: pip install httpx beautifulsoup4")
    raise


BASE_URL = "https://eur-lex.europa.eu"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


# The 20 chapters to scrape (not yet covered by existing guides)
CHAPTERS_TO_SCRAPE: Dict[int, Dict[str, str]] = {
    2: {"topic": "Fisheries", "filename": "eu_fisheries_policy"},
    3: {"topic": "Agriculture", "filename": "eu_agriculture_policy"},
    4: {"topic": "Humanitarian Aid and Civil Protection", "filename": "eu_humanitarian_civil_protection"},
    7: {"topic": "Trade", "filename": "eu_trade_policy"},
    9: {"topic": "Consumer Protection", "filename": "eu_consumer_protection"},
    10: {"topic": "Culture", "filename": "eu_culture_policy"},
    11: {"topic": "Development Cooperation", "filename": "eu_development_cooperation"},
    12: {"topic": "Customs", "filename": "eu_customs_policy"},
    13: {"topic": "Human Rights", "filename": "eu_human_rights"},
    15: {"topic": "Education, Youth and Sport", "filename": "eu_education_youth_sport"},
    16: {"topic": "Enlargement", "filename": "eu_enlargement_policy"},
    19: {"topic": "Enterprise and SME Policy", "filename": "eu_enterprise_sme_policy"},
    20: {"topic": "Environment and Climate", "filename": "eu_environment_climate"},
    21: {"topic": "Taxation", "filename": "eu_taxation_policy"},
    22: {"topic": "Fraud and Corruption", "filename": "eu_fraud_corruption"},
    23: {"topic": "Justice and Security", "filename": "eu_justice_security"},
    24: {"topic": "Internal Market", "filename": "eu_internal_market"},
    25: {"topic": "Foreign and Security Policy", "filename": "eu_foreign_security_policy"},
    28: {"topic": "External Relations", "filename": "eu_external_relations"},
    29: {"topic": "Public Health", "filename": "eu_public_health"},
}


# Map chapter IDs to relevant EU institutions/bodies
CHAPTER_INSTITUTIONS: Dict[int, List[Tuple[str, str]]] = {
    2: [("DG MARE (Maritime Affairs and Fisheries)", "Lead Commission DG for fisheries"),
        ("PECH committee (EP)", "EP committee for fisheries"),
        ("AGRIFISH Council", "Council configuration for agriculture and fisheries")],
    3: [("DG AGRI (Agriculture and Rural Development)", "Lead Commission DG for agriculture"),
        ("AGRI committee (EP)", "EP committee for agriculture"),
        ("AGRIFISH Council", "Council configuration for agriculture and fisheries")],
    4: [("DG ECHO (Civil Protection and Humanitarian Aid)", "Lead Commission DG"),
        ("DEVE committee (EP)", "EP committee for development"),
        ("FAC Council (Foreign Affairs)", "Council configuration")],
    7: [("DG TRADE", "Lead Commission DG for trade policy"),
        ("INTA committee (EP)", "EP committee for international trade"),
        ("FAC (Trade) Council", "Council configuration for trade")],
    9: [("DG JUST (Justice and Consumers)", "Lead Commission DG for consumer affairs"),
        ("IMCO committee (EP)", "EP committee for internal market and consumer protection"),
        ("COMPET Council", "Council configuration for competitiveness")],
    10: [("DG EAC (Education and Culture)", "Lead Commission DG"),
         ("CULT committee (EP)", "EP committee for culture and education")],
    11: [("DG INTPA (International Partnerships)", "Lead Commission DG for development"),
         ("DEVE committee (EP)", "EP committee for development"),
         ("FAC Council (Foreign Affairs)", "Council configuration")],
    12: [("DG TAXUD (Taxation and Customs Union)", "Lead Commission DG"),
         ("IMCO committee (EP)", "EP committee involved in customs"),
         ("ECOFIN Council", "Council configuration for economic and financial affairs")],
    13: [("DG JUST (Justice and Consumers)", "Lead Commission DG for fundamental rights"),
         ("LIBE committee (EP)", "EP committee for civil liberties"),
         ("FRA", "EU Agency for Fundamental Rights")],
    15: [("DG EAC (Education and Culture)", "Lead Commission DG"),
         ("CULT committee (EP)", "EP committee for culture and education"),
         ("EYCS Council", "Council for Education, Youth, Culture and Sport")],
    16: [("DG NEAR (Neighbourhood and Enlargement Negotiations)", "Lead Commission DG"),
         ("AFET committee (EP)", "EP committee for foreign affairs"),
         ("GAC Council", "Council for General Affairs")],
    19: [("DG GROW (Internal Market, Industry, Entrepreneurship and SMEs)", "Lead Commission DG"),
         ("ITRE committee (EP)", "EP committee for industry, research and energy"),
         ("COMPET Council", "Council configuration for competitiveness")],
    20: [("DG ENV (Environment)", "Lead Commission DG for environment"),
         ("DG CLIMA (Climate Action)", "Climate aspects"),
         ("ENVI committee (EP)", "EP committee for environment and public health"),
         ("ENVI Council", "Council configuration for environment")],
    21: [("DG TAXUD (Taxation and Customs Union)", "Lead Commission DG"),
         ("ECON committee (EP)", "EP committee for economic and monetary affairs (with FISC subcommittee)"),
         ("ECOFIN Council", "Council configuration for economic and financial affairs")],
    22: [("OLAF (European Anti-Fraud Office)", "EU body for fraud investigation"),
         ("EPPO (European Public Prosecutor's Office)", "EU body for financial crime prosecution"),
         ("CONT committee (EP)", "EP committee for budgetary control")],
    23: [("DG HOME (Migration and Home Affairs)", "Lead Commission DG for home affairs"),
         ("DG JUST (Justice and Consumers)", "Lead Commission DG for justice"),
         ("LIBE committee (EP)", "EP committee for civil liberties, justice and home affairs"),
         ("JHA Council", "Council for Justice and Home Affairs"),
         ("Europol", "EU law enforcement agency"),
         ("Eurojust", "EU judicial cooperation agency"),
         ("Frontex", "EU border and coast guard agency")],
    24: [("DG GROW (Internal Market, Industry, Entrepreneurship and SMEs)", "Lead Commission DG"),
         ("DG CNECT (Communications Networks, Content and Technology)", "Digital single market"),
         ("IMCO committee (EP)", "EP committee for internal market"),
         ("COMPET Council", "Council configuration for competitiveness")],
    25: [("EEAS (European External Action Service)", "EU diplomatic service"),
         ("High Representative / VP", "Leads EU foreign and security policy"),
         ("AFET committee (EP)", "EP committee for foreign affairs"),
         ("SEDE subcommittee (EP)", "EP subcommittee for security and defence"),
         ("FAC Council", "Council for Foreign Affairs")],
    28: [("EEAS (European External Action Service)", "EU diplomatic service"),
         ("DG INTPA (International Partnerships)", "Development partnerships"),
         ("AFET committee (EP)", "EP committee for foreign affairs"),
         ("FAC Council", "Council for Foreign Affairs")],
    29: [("DG SANTE (Health and Food Safety)", "Lead Commission DG for health"),
         ("ENVI committee (EP)", "EP committee for environment and public health"),
         ("EPSCO Council", "Council for Employment, Social Policy, Health and Consumer Affairs"),
         ("EMA (European Medicines Agency)", "EU agency for medicinal products"),
         ("ECDC (European Centre for Disease Prevention and Control)", "EU agency for disease surveillance"),
         ("HERA (Health Emergency Preparedness and Response Authority)", "EU health crisis preparedness")],
}

# Map chapter IDs to treaty bases
CHAPTER_TREATY_BASIS: Dict[int, str] = {
    2: "Articles 38-44 TFEU (Common Fisheries Policy)",
    3: "Articles 38-44 TFEU (Common Agricultural Policy)",
    4: "Article 214 TFEU (Humanitarian Aid), Article 196 TFEU (Civil Protection)",
    7: "Articles 206-207 TFEU (Common Commercial Policy)",
    9: "Article 169 TFEU (Consumer Protection)",
    10: "Article 167 TFEU (Culture)",
    11: "Articles 208-211 TFEU (Development Cooperation)",
    12: "Articles 28-32 TFEU (Customs Union)",
    13: "Articles 2-6 TEU, EU Charter of Fundamental Rights",
    15: "Articles 165-166 TFEU (Education and Vocational Training)",
    16: "Article 49 TEU (Accession)",
    19: "Articles 114-118 TFEU (Approximation of Laws), Article 173 TFEU (Industry)",
    20: "Articles 191-193 TFEU (Environment), Article 191 TFEU (Climate Action)",
    21: "Articles 110-113 TFEU (Tax Provisions)",
    22: "Article 325 TFEU (Combating Fraud), Directive (EU) 2017/1371 (PIF Directive)",
    23: "Title V TFEU (Area of Freedom, Security and Justice), Articles 67-89 TFEU",
    24: "Articles 26-27 TFEU (Internal Market), Articles 114-118 TFEU",
    25: "Title V TEU (CFSP), Articles 42-46 TEU (CSDP)",
    28: "Articles 216-219 TFEU (International Agreements)",
    29: "Article 168 TFEU (Public Health)",
}


@dataclass
class SummaryEntry:
    """A single summary entry from a chapter page."""
    title: str
    url: str
    celex: Optional[str] = None
    description: str = ""


@dataclass
class ChapterData:
    """Scraped data for a policy chapter."""
    chapter_id: int
    topic: str
    summaries: List[SummaryEntry] = field(default_factory=list)
    key_legislation: List[Dict[str, str]] = field(default_factory=list)
    overview_text: str = ""


class EURLexSummaryScraper:
    """Scrapes EUR-Lex summaries by policy chapter."""

    def __init__(self, delay: float = 3.0, timeout: int = 30):
        self.delay = delay
        self.timeout = timeout

    async def scrape_chapter(
        self,
        chapter_id: int,
        client: httpx.AsyncClient,
        max_summaries: int = 20,
        verbose: bool = False
    ) -> ChapterData:
        """Scrape a single policy chapter.

        Args:
            chapter_id: EUR-Lex chapter number
            client: httpx async client
            max_summaries: Max summary pages to scrape for legislation details
            verbose: Print progress

        Returns:
            ChapterData with scraped information
        """
        chapter_info = CHAPTERS_TO_SCRAPE.get(chapter_id)
        if not chapter_info:
            raise ValueError(f"Chapter {chapter_id} not in CHAPTERS_TO_SCRAPE")

        topic = chapter_info["topic"]
        chapter_data = ChapterData(chapter_id=chapter_id, topic=topic)

        # Step 1: Fetch chapter index page
        chapter_url = f"{BASE_URL}/summary/chapter/{chapter_id}.html"
        if verbose:
            print(f"  [INFO] Fetching chapter {chapter_id}: {topic}")

        try:
            response = await client.get(chapter_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Extract summary links from the chapter page
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if '/summary/' in href and '/chapter/' not in href and link.text.strip():
                    title = link.text.strip()
                    url = href if href.startswith('http') else BASE_URL + href
                    chapter_data.summaries.append(SummaryEntry(title=title, url=url))

            # Deduplicate
            seen_urls = set()
            unique_summaries = []
            for s in chapter_data.summaries:
                if s.url not in seen_urls:
                    seen_urls.add(s.url)
                    unique_summaries.append(s)
            chapter_data.summaries = unique_summaries

            if verbose:
                print(f"  [INFO] Found {len(chapter_data.summaries)} summary entries")

        except Exception as e:
            logger.error(f"Failed to fetch chapter {chapter_id}: {e}")
            if verbose:
                print(f"  [ERROR] Failed to fetch chapter index: {e}")

        # Step 2: Scrape individual summary pages for legislation details
        for i, summary in enumerate(chapter_data.summaries[:max_summaries]):
            try:
                await asyncio.sleep(self.delay)
                leg_entries = await self._scrape_summary_page(client, summary, verbose)
                chapter_data.key_legislation.extend(leg_entries)
            except Exception as e:
                if verbose:
                    print(f"    [WARN] Failed to scrape {summary.title[:50]}: {e}")

            if verbose and (i + 1) % 5 == 0:
                print(f"    ... scraped {i + 1}/{min(len(chapter_data.summaries), max_summaries)} summaries")

        # Deduplicate legislation by CELEX
        seen_celex = set()
        unique_legislation = []
        for entry in chapter_data.key_legislation:
            celex = entry.get('celex', '')
            if celex and celex not in seen_celex:
                seen_celex.add(celex)
                unique_legislation.append(entry)
            elif not celex:
                unique_legislation.append(entry)
        chapter_data.key_legislation = unique_legislation

        if verbose:
            print(f"  [OK] Chapter {chapter_id}: {len(chapter_data.key_legislation)} legislation entries")

        return chapter_data

    async def _scrape_summary_page(
        self,
        client: httpx.AsyncClient,
        summary: SummaryEntry,
        verbose: bool = False
    ) -> List[Dict[str, str]]:
        """Scrape a single summary page for legislation references.

        Returns:
            List of {"legislation": ..., "celex": ..., "subject": ...} dicts
        """
        entries = []

        response = await client.get(summary.url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Extract CELEX references from the page
        # Look for links to EUR-Lex legal content
        celex_pattern = re.compile(r'CELEX:(\d{1}[0-9]{4}[A-Z]{1,3}[0-9]{3,5})')

        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            celex_match = celex_pattern.search(href)
            if celex_match:
                celex = celex_match.group(1)
                title = link.text.strip()
                if title and len(title) > 5:
                    entries.append({
                        'legislation': title[:200],
                        'celex': celex,
                        'subject': summary.title[:100]
                    })

        # Also look for CELEX numbers in text
        text = soup.get_text()
        for match in celex_pattern.finditer(text):
            celex = match.group(1)
            if not any(e['celex'] == celex for e in entries):
                # Find surrounding text for context
                idx = match.start()
                start = max(0, idx - 100)
                context = text[start:idx].strip()
                entries.append({
                    'legislation': context[-100:] if context else 'Referenced legislation',
                    'celex': celex,
                    'subject': summary.title[:100]
                })

        return entries

    def generate_guide_markdown(self, chapter_data: ChapterData) -> str:
        """Generate a knowledge guide markdown file from chapter data.

        Args:
            chapter_data: Scraped chapter data

        Returns:
            Markdown content following the eu_energy_policy.md template
        """
        chapter_id = chapter_data.chapter_id
        topic = chapter_data.topic
        treaty_basis = CHAPTER_TREATY_BASIS.get(chapter_id, "See TFEU/TEU")
        institutions = CHAPTER_INSTITUTIONS.get(chapter_id, [])

        lines = [
            f"# EU {topic} Policy Framework",
            "",
            "## Overview",
            "",
            f"EU {topic.lower()} policy is governed by {treaty_basis}. "
            f"This guide covers the key legislation, institutional landscape, and recent developments "
            f"in this policy area.",
            "",
        ]

        # Key Legislation table
        if chapter_data.key_legislation:
            lines.extend([
                "## Key Legislation",
                "",
                "| Legislation | CELEX | Subject |",
                "|-------------|-------|---------|",
            ])

            # Show up to 30 entries
            for entry in chapter_data.key_legislation[:30]:
                legislation = entry.get('legislation', '').replace('|', '-')
                celex = entry.get('celex', 'N/A')
                subject = entry.get('subject', '').replace('|', '-')
                lines.append(f"| {legislation[:80]} | {celex} | {subject[:60]} |")

            lines.append("")

        # Summary topics
        if chapter_data.summaries:
            lines.extend([
                "## Policy Areas Covered",
                "",
            ])
            for s in chapter_data.summaries[:25]:
                lines.append(f"- {s.title}")
            lines.append("")

        # Institutional Landscape
        if institutions:
            lines.extend([
                "## Institutional Landscape",
                "",
                "| Institution | Role |",
                "|-------------|------|",
            ])
            for name, role in institutions:
                lines.append(f"| {name} | {role} |")
            lines.append("")

        # Recent Developments placeholder
        lines.extend([
            "## Recent Developments",
            "",
            f"For the latest developments in EU {topic.lower()} policy, consult:",
            f"- EUR-Lex summaries: https://eur-lex.europa.eu/summary/chapter/{chapter_id}.html",
            f"- European Parliament Legislative Observatory (OEIL): https://oeil.secure.europarl.europa.eu/oeil/home/home.do",
            "",
        ])

        # Related Brubru Features
        lines.extend([
            "## Related Brubru Features",
            "",
            f"- **My EU Bubble**: Track {topic.lower()} legislative files through the Legislative Train",
            f"- **Predictions**: Analyse voting patterns for {topic.lower()} legislation in EP and Council",
            f"- **Amendator**: Draft amendments to {topic.lower()} directives and regulations",
            f"- **EU Calendar**: Monitor relevant Council and EP committee sessions",
        ])

        return '\n'.join(lines)
