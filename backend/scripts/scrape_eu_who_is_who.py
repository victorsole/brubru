#!/usr/bin/env python3.12
"""
EU Who Is Who Scraper

Scrapes the EU Who Is Who directory (op.europa.eu) using Playwright
to render the JS-heavy Liferay portal and extract the tree-view data.

Generates organigramme JSON files for:
- EURCOU (European Council)
- GSC (General Secretariat of the Council)
- COREPER (Permanent Representatives Committee)
- GOVREP (Government Representatives)
- COM DGs (European Commission DGs)

Usage:
    python3.12 scripts/scrape_eu_who_is_who.py --institution EURCOU
    python3.12 scripts/scrape_eu_who_is_who.py --institution GSC
    python3.12 scripts/scrape_eu_who_is_who.py --institution COM --dg TRADE
    python3.12 scripts/scrape_eu_who_is_who.py --all-council
    python3.12 scripts/scrape_eu_who_is_who.py --all-commission
    python3.12 scripts/scrape_eu_who_is_who.py --verbose
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger(__name__)

BASE_URL = "https://op.europa.eu/en/web/who-is-who"
ORGANIGRAMMES_DIR = Path(__file__).resolve().parent.parent / "knowledge_base" / "ec_organigrammes" / "json"

# Institution URL mappings
INSTITUTION_URLS = {
    "EURCOU": f"{BASE_URL}/organization/-/organization/EURCOU/EURCOU",
    "CM": f"{BASE_URL}/organization/-/organization/CM/CM",  # Council Ministers
    "CONSIL_SG": f"{BASE_URL}/organization/-/organization/CONSIL_SG/CONSIL_SG",
    "COREPER": f"{BASE_URL}/organization/-/organization/COREPER/COREPER",
    "GOVREP": f"{BASE_URL}/organization/-/organization/GOVREP/GOVREP",
    "EP": f"{BASE_URL}/organization/-/organization/EP/EP",
    "EP_SG": f"{BASE_URL}/organization/-/organization/EP_SG/EP_SG",
    "COM": f"{BASE_URL}/organization/-/organization/COM/COM",
}

# Commission DG codes -> URL patterns
# For COM DGs, the URL is: BASE_URL/organization/-/organization/COM/{DG_CODE}
COMMISSION_DGS = [
    "AGRI", "BUDG", "CLIMA", "CNECT", "COMM", "COMP", "DEFIS", "DGT",
    "EAC", "ECFIN", "ECHO", "EMPL", "ENER", "ENV", "EPSC", "ESTAT",
    "FISMA", "FPI", "GROW", "HOME", "HR", "IDEA", "INTPA", "JRC",
    "JUST", "MARE", "MOVE", "NEAR", "OIB", "OIL", "OLAF", "OP",
    "PMO", "REGIO", "RTD", "SANTE", "SCIC", "SG", "SJ", "TAXUD", "TRADE",
]


async def expand_all_nodes(page, max_depth: int = 6) -> None:
    """
    Expand all collapsed tree nodes by clicking the expand buttons.
    Repeats until no more collapsed nodes exist (up to max_depth iterations).
    """
    for depth in range(max_depth):
        # Find all collapsed node expand buttons
        collapsed = await page.query_selector_all('.tree-collapsed .tree-hitarea')
        if not collapsed:
            logger.debug(f"[OK] All nodes expanded after {depth} iterations")
            break

        logger.info(f"  Expanding {len(collapsed)} collapsed nodes (iteration {depth + 1})...")

        for btn in collapsed:
            try:
                await btn.click()
                # Small delay to let Liferay load children
                await asyncio.sleep(0.3)
            except Exception:
                pass  # Node may have already expanded

        # Wait for any AJAX loads to complete
        await asyncio.sleep(1.0)


def parse_tree_from_html(html: str) -> List[Dict[str, Any]]:
    """
    Parse the expanded tree-view HTML into structured data.
    Returns a list of top-level nodes with nested children.
    """
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, 'html.parser')
    root_ul = soup.find('ul', class_='tree-root-container')
    if not root_ul:
        # Try finding any tree container
        root_ul = soup.find('div', class_='treeViewComponent')
        if root_ul:
            root_ul = root_ul.find('ul', class_='tree-root-container')

    if not root_ul:
        logger.warning("[WARN] No tree-root-container found in HTML")
        return []

    return _extract_tree_nodes(root_ul)


def _extract_tree_nodes(container, depth: int = 0, max_depth: int = 10) -> List[Dict[str, Any]]:
    """Recursively extract tree nodes from a ul container."""
    results = []
    children = container.find_all('li', class_='tree-node', recursive=False)

    for child in children:
        content_div = child.find('div', class_='tree-node-content', recursive=False)
        if not content_div:
            continue

        org_link = content_div.find('a', href=re.compile(r'/organization/'))
        person_span = content_div.find('span', class_='wiw-sublevel-person-name')

        if org_link:
            org_name = org_link.get_text(strip=True)
            href = org_link.get('href', '')
            code_match = re.search(r'/organization/\w+/(\S+)', href)
            code = code_match.group(1) if code_match else ''

            # Clean org name - remove bracket codes like [ECFIN.A]
            clean_name = re.sub(r'^\[[^\]]+\]\s*', '', org_name)

            entry = {
                'code': code,
                'name': clean_name,
            }

            # Collect persons and sub-units
            persons = []
            units = []

            sub_ul = child.find('ul', class_='tree-container', recursive=False)
            if sub_ul and depth < max_depth:
                sub_items = _extract_tree_nodes(sub_ul, depth + 1, max_depth)
                for si in sub_items:
                    if si.get('_type') == 'person':
                        del si['_type']
                        persons.append(si)
                    else:
                        si.pop('_type', None)
                        units.append(si)

            if persons:
                entry['persons'] = persons
            if units:
                entry['units'] = units

            entry['_type'] = 'org'
            results.append(entry)

        elif person_span:
            name_link = person_span.find('a')
            name = name_link.get_text(strip=True) if name_link else person_span.get_text(strip=True)

            phone_span = person_span.find_next('span', class_='wiw-sublevel-person-field')
            phone = ''
            if phone_span:
                phone_link = phone_span.find('a', class_='wiwPhoneLink')
                if phone_link:
                    phone = phone_link.get_text(strip=True)

            entry = {'_type': 'person', 'name': name}
            if phone:
                entry['phone'] = phone
            results.append(entry)

    return results


async def scrape_institution(
    institution_code: str,
    url: Optional[str] = None,
    expand_depth: int = 6,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Scrape an institution page from EU Who Is Who using Playwright.

    Args:
        institution_code: e.g. 'EURCOU', 'GSC', 'COM'
        url: Override URL (default uses INSTITUTION_URLS mapping)
        expand_depth: Max tree expansion iterations
        verbose: Extra logging

    Returns:
        Structured organigramme data dict
    """
    from playwright.async_api import async_playwright

    if url is None:
        url = INSTITUTION_URLS.get(institution_code)
        if not url:
            raise ValueError(f"Unknown institution code: {institution_code}")

    logger.info(f"[START] Scraping {institution_code} from {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        page = await context.new_page()

        try:
            # Navigate and wait for tree to render
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Wait for tree-view component to appear
            await page.wait_for_selector('.treeViewComponent', timeout=30000)
            await asyncio.sleep(2.0)  # Let lazy-load finish

            # Expand all collapsed nodes
            await expand_all_nodes(page, max_depth=expand_depth)

            # Get the rendered HTML
            tree_html = await page.inner_html('.treeViewComponent')

            # Parse the tree
            structure = parse_tree_from_html(f'<div class="treeViewComponent">{tree_html}</div>')

            # Clean _type markers from top level
            for item in structure:
                item.pop('_type', None)
                _clean_types_recursive(item)

            # Count persons
            person_count = _count_persons(structure)
            logger.info(f"[OK] {institution_code}: {len(structure)} top-level nodes, {person_count} persons")

            return {
                'institution_code': institution_code,
                'source': 'EU Who Is Who (op.europa.eu)',
                'date_extracted': datetime.now().strftime('%Y-%m-%d'),
                'url': url,
                'structure': structure,
                'person_count': person_count,
            }

        finally:
            await browser.close()


async def scrape_commission_dg(dg_code: str, verbose: bool = False) -> Dict[str, Any]:
    """
    Scrape a specific Commission DG organigramme.

    The EU Who Is Who has Commission DGs at:
    /organization/-/organization/COM/{DG_CODE}
    """
    url = f"{BASE_URL}/organization/-/organization/COM/{dg_code}"
    data = await scrape_institution(f"COM_{dg_code}", url=url, verbose=verbose)
    data['institution_code'] = dg_code
    data['institution_name'] = f"DG {dg_code}"
    return data


def _clean_types_recursive(obj):
    """Remove _type markers from nested structure."""
    if isinstance(obj, dict):
        obj.pop('_type', None)
        for v in obj.values():
            _clean_types_recursive(v)
    elif isinstance(obj, list):
        for item in obj:
            _clean_types_recursive(item)


def _count_persons(obj) -> int:
    """Count total persons in nested structure."""
    count = 0
    if isinstance(obj, dict):
        if 'persons' in obj:
            count += len(obj['persons'])
        for v in obj.values():
            count += _count_persons(v)
    elif isinstance(obj, list):
        for item in obj:
            count += _count_persons(item)
    return count


def save_organigramme(data: Dict[str, Any], filename: str) -> Path:
    """Save organigramme data to JSON file."""
    ORGANIGRAMMES_DIR.mkdir(parents=True, exist_ok=True)
    filepath = ORGANIGRAMMES_DIR / f"{filename}.json"

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    logger.info(f"[OK] Saved {filepath} ({filepath.stat().st_size:,} bytes)")
    return filepath


async def scrape_council_group() -> None:
    """Scrape all Council-related institutions."""
    # European Council
    euco = await scrape_institution("EURCOU")
    euco['institution_name'] = "European Council"
    save_organigramme(euco, "EURCOU")

    await asyncio.sleep(3.0)

    # Council - this page contains GSC, COREPER, GOVREP in tabs
    # We scrape the main Council page which has all 3
    cm = await scrape_institution("CM", url=f"{BASE_URL}/organization/-/organization/CM/CM")
    if cm.get('structure'):
        # Split into sub-institutions
        for node in cm['structure']:
            code = node.get('code', '')
            if 'CONSIL_SG' in code or 'GSC' in node.get('name', '').upper():
                gsc_data = {
                    'institution_code': 'GSC',
                    'institution_name': 'General Secretariat of the Council',
                    'source': cm['source'],
                    'date_extracted': cm['date_extracted'],
                    'structure': node.get('units', [node]),
                }
                save_organigramme(gsc_data, "GSC")


async def main():
    parser = argparse.ArgumentParser(description="Scrape EU Who Is Who directory")
    parser.add_argument("--institution", "-i", help="Institution code (EURCOU, GSC, COM, EP, etc.)")
    parser.add_argument("--dg", help="Commission DG code (TRADE, GROW, etc.) - requires --institution COM")
    parser.add_argument("--all-council", action="store_true", help="Scrape all Council-related institutions")
    parser.add_argument("--all-commission", action="store_true", help="Scrape all Commission DGs")
    parser.add_argument("--url", help="Override URL to scrape")
    parser.add_argument("--output", "-o", help="Output JSON file path (default: auto)")
    parser.add_argument("--expand-depth", type=int, default=6, help="Max tree expansion iterations (default: 6)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--dry-run", action="store_true", help="Scrape but don't save")

    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.all_council:
        # Scrape EURCOU + Council (GSC, COREPER, GOVREP)
        logger.info("[START] Scraping all Council institutions...")

        for inst_code in ["EURCOU"]:
            try:
                data = await scrape_institution(inst_code, expand_depth=args.expand_depth, verbose=args.verbose)
                inst_names = {
                    "EURCOU": "European Council",
                }
                data['institution_name'] = inst_names.get(inst_code, inst_code)
                if not args.dry_run:
                    save_organigramme(data, inst_code)
                await asyncio.sleep(3.0)
            except Exception as e:
                logger.error(f"[ERROR] Failed to scrape {inst_code}: {e}")

        logger.info("[OK] Council scraping complete")

    elif args.all_commission:
        logger.info(f"[START] Scraping {len(COMMISSION_DGS)} Commission DGs...")
        for dg_code in COMMISSION_DGS:
            try:
                data = await scrape_commission_dg(dg_code, verbose=args.verbose)
                if not args.dry_run:
                    save_organigramme(data, dg_code)
                await asyncio.sleep(3.0)
            except Exception as e:
                logger.error(f"[ERROR] Failed to scrape DG {dg_code}: {e}")

        logger.info("[OK] Commission scraping complete")

    elif args.institution:
        if args.dg:
            # Scrape specific Commission DG
            data = await scrape_commission_dg(args.dg, verbose=args.verbose)
        else:
            url = args.url or INSTITUTION_URLS.get(args.institution)
            data = await scrape_institution(args.institution, url=url, expand_depth=args.expand_depth, verbose=args.verbose)

        if not args.dry_run:
            filename = args.output or (args.dg or args.institution)
            save_organigramme(data, filename)

        # Print summary
        print(f"\n{'='*60}")
        print(f"Institution: {data.get('institution_name', data.get('institution_code', ''))}")
        print(f"Persons: {data.get('person_count', 'N/A')}")
        print(f"Top-level nodes: {len(data.get('structure', []))}")
        print(f"{'='*60}")

    else:
        parser.print_help()
        print("\nExamples:")
        print("  python3.12 scripts/scrape_eu_who_is_who.py --institution EURCOU")
        print("  python3.12 scripts/scrape_eu_who_is_who.py --institution COM --dg TRADE")
        print("  python3.12 scripts/scrape_eu_who_is_who.py --all-council")


if __name__ == "__main__":
    asyncio.run(main())
