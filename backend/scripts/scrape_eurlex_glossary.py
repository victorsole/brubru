"""
EUR-Lex Glossary Scraper

Scrapes the official EUR-Lex glossary of EU legal terms (~200+ definitions)
and generates a knowledge guide markdown file.

Source: https://eur-lex.europa.eu/summary/glossary.html

Usage:
    python3.12 scripts/scrape_eurlex_glossary.py
    python3.12 scripts/scrape_eurlex_glossary.py --dry-run
    python3.12 scripts/scrape_eurlex_glossary.py --verbose
"""

import asyncio
import argparse
import sys
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import httpx
    from bs4 import BeautifulSoup
except ImportError:
    print("[ERROR] Required packages: pip install httpx beautifulsoup4")
    sys.exit(1)


GLOSSARY_INDEX_URL = "https://eur-lex.europa.eu/summary/glossary.html"
BASE_URL = "https://eur-lex.europa.eu"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}

OUTPUT_PATH = Path(__file__).parent.parent / "knowledge_base" / "guides" / "eu_glossary_eurlex.md"


async def fetch_glossary_index(client: httpx.AsyncClient) -> List[Tuple[str, str]]:
    """Fetch the glossary index page and extract term links.

    Returns:
        List of (term_name, term_url) tuples
    """
    print("[INFO] Fetching glossary index...")
    response = await client.get(GLOSSARY_INDEX_URL)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, 'html.parser')
    terms = []

    # The glossary page lists terms as links
    # Look for links that point to glossary term pages
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        # Glossary term URLs contain /summary/glossary/
        if '/summary/glossary/' in href and link.text.strip():
            term_name = link.text.strip()
            term_url = href if href.startswith('http') else BASE_URL + href
            terms.append((term_name, term_url))

    # Deduplicate while preserving order
    seen = set()
    unique_terms = []
    for name, url in terms:
        if url not in seen:
            seen.add(url)
            unique_terms.append((name, url))

    print(f"[INFO] Found {len(unique_terms)} glossary terms")
    return unique_terms


async def fetch_term_definition(
    client: httpx.AsyncClient,
    term_name: str,
    term_url: str,
    verbose: bool = False
) -> Tuple[str, str]:
    """Fetch a single glossary term definition.

    Returns:
        (term_name, definition_text)
    """
    try:
        response = await client.get(term_url)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Try multiple selectors for the definition content
        definition = ""

        # Look for the main content area
        content_div = (
            soup.find('div', class_='col-12 content-column') or
            soup.find('div', id='TexteOnly') or
            soup.find('div', class_='EurlexContent') or
            soup.find('article') or
            soup.find('main')
        )

        if content_div:
            # Get all paragraphs from the content
            paragraphs = content_div.find_all('p')
            definition_parts = []
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 10:
                    definition_parts.append(text)

            definition = ' '.join(definition_parts)

        # If no definition found via divs, try extracting from the whole page
        if not definition:
            # Get all paragraphs that seem like definitions
            all_paragraphs = soup.find_all('p')
            for p in all_paragraphs:
                text = p.get_text(strip=True)
                if len(text) > 50 and term_name.lower().split()[0] in text.lower():
                    definition = text
                    break

        # Cap at 500 chars
        if len(definition) > 500:
            # Try to cut at a sentence boundary
            cut_point = definition[:500].rfind('.')
            if cut_point > 200:
                definition = definition[:cut_point + 1]
            else:
                definition = definition[:497] + "..."

        if verbose and definition:
            print(f"  [OK] {term_name}: {len(definition)} chars")
        elif verbose:
            print(f"  [WARN] {term_name}: no definition extracted")

        return (term_name, definition)

    except Exception as e:
        if verbose:
            print(f"  [ERROR] {term_name}: {str(e)[:80]}")
        return (term_name, "")


def generate_guide_markdown(terms: List[Tuple[str, str]]) -> str:
    """Generate the knowledge guide markdown from scraped terms.

    Args:
        terms: List of (term_name, definition) tuples (sorted alphabetically)

    Returns:
        Markdown content
    """
    lines = [
        "# EUR-Lex Glossary of EU Legal Terms",
        "",
        "## Overview",
        "",
        f"This glossary contains {len(terms)} official EU legal terms and definitions,",
        "sourced from the EUR-Lex glossary (https://eur-lex.europa.eu/summary/glossary.html).",
        "These definitions reflect the official terminology used in EU legal texts,",
        "treaties, and institutional documents.",
        "",
        "## Terms",
        "",
    ]

    current_letter = ""
    for term_name, definition in terms:
        # Add letter heading
        first_letter = term_name[0].upper() if term_name else "?"
        if first_letter != current_letter:
            current_letter = first_letter
            lines.append(f"### {current_letter}")
            lines.append("")

        if definition:
            lines.append(f"**{term_name}**: {definition}")
        else:
            lines.append(f"**{term_name}**: (Definition not available)")
        lines.append("")

    lines.extend([
        "## Source",
        "",
        "EUR-Lex Glossary: https://eur-lex.europa.eu/summary/glossary.html",
        "",
        "## Related Brubru Features",
        "",
        "- **Brubru Chat**: Ask about any EU legal term for a plain-language explanation",
        "- **Amendator**: Understand legislative terminology when drafting amendments",
        "- **EU Law Comply**: Reference official definitions in compliance analysis",
    ])

    return '\n'.join(lines)


async def main():
    parser = argparse.ArgumentParser(description='Scrape EUR-Lex glossary of EU legal terms')
    parser.add_argument('--dry-run', action='store_true',
                        help='Only fetch index, do not scrape individual terms')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show progress for each term')
    parser.add_argument('--delay', type=float, default=2.0,
                        help='Delay between requests in seconds (default: 2.0)')
    args = parser.parse_args()

    async with httpx.AsyncClient(
        headers=HEADERS,
        follow_redirects=True,
        timeout=30.0
    ) as client:
        # Step 1: Get all term links from the index
        terms_links = await fetch_glossary_index(client)

        if not terms_links:
            print("[ERROR] No glossary terms found. The page structure may have changed.")
            sys.exit(1)

        if args.dry_run:
            print(f"\n[DRY-RUN] Would scrape {len(terms_links)} terms:")
            for name, url in terms_links[:20]:
                print(f"  - {name}: {url}")
            if len(terms_links) > 20:
                print(f"  ... and {len(terms_links) - 20} more")
            return

        # Step 2: Scrape each term definition
        print(f"\n[START] Scraping {len(terms_links)} glossary term definitions...")
        scraped_terms = []

        for i, (name, url) in enumerate(terms_links, 1):
            term_name, definition = await fetch_term_definition(
                client, name, url, verbose=args.verbose
            )
            if term_name:
                scraped_terms.append((term_name, definition))

            if i % 20 == 0:
                print(f"  ... scraped {i}/{len(terms_links)}")

            if i < len(terms_links):
                await asyncio.sleep(args.delay)

        # Sort alphabetically
        scraped_terms.sort(key=lambda x: x[0].lower())

        # Step 3: Generate markdown
        with_defs = sum(1 for _, d in scraped_terms if d)
        print(f"\n[INFO] Scraped {len(scraped_terms)} terms ({with_defs} with definitions)")

        markdown = generate_guide_markdown(scraped_terms)

        # Step 4: Write to file
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(markdown, encoding='utf-8')

        lines_count = len(markdown.splitlines())
        print(f"[OK] Generated {OUTPUT_PATH}")
        print(f"     {lines_count} lines, {len(markdown)} bytes")
        print(f"     {len(scraped_terms)} terms ({with_defs} with definitions)")


if __name__ == '__main__':
    asyncio.run(main())
