"""
CELEX Number Validator

Validates all CELEX numbers found in knowledge base guides against the
CELLAR SPARQL endpoint to identify wrong or missing references.

Usage:
    python3.12 scripts/validate_celex_numbers.py --verbose
    python3.12 scripts/validate_celex_numbers.py --guide eu_energy_policy
"""

import asyncio
import argparse
import re
import sys
import os
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from services.api_clients.eurlex_client import EURLexClient


# CELEX number regex pattern
# Format: sector(1-2 digits) + year(4 digits) + type(1-3 letters) + number(4+ digits)
# Examples: 32023R1234, 32019L0944, 32009L0031, 32008R1099
CELEX_PATTERN = re.compile(r'\b([0-9]{1}[0-9]{4}[A-Z]{1,3}[0-9]{3,5})\b')


def extract_celex_from_file(filepath: Path) -> List[Tuple[str, int, str]]:
    """Extract all CELEX numbers from a markdown file.

    Returns:
        List of (celex, line_number, line_text) tuples
    """
    results = []
    try:
        content = filepath.read_text(encoding='utf-8')
        for i, line in enumerate(content.splitlines(), 1):
            for match in CELEX_PATTERN.finditer(line):
                celex = match.group(1)
                results.append((celex, i, line.strip()))
    except Exception as e:
        print(f"[ERROR] Failed to read {filepath}: {e}")
    return results


async def validate_celex(client: EURLexClient, celex: str) -> Tuple[str, bool, str]:
    """Validate a single CELEX number against CELLAR.

    Returns:
        (celex, is_valid, title_or_error)
    """
    try:
        result = await client.get_document_by_celex(celex)
        if result:
            title = result.get('title', 'No title in EN')
            return (celex, True, title or 'Found (no EN title)')
        else:
            return (celex, False, 'Not found in CELLAR')
    except Exception as e:
        return (celex, False, f'Query error: {str(e)[:100]}')


async def main():
    parser = argparse.ArgumentParser(description='Validate CELEX numbers in knowledge guides')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show all CELEX numbers (valid + invalid)')
    parser.add_argument('--guide', '-g', type=str, default=None,
                        help='Validate a specific guide (file stem, e.g. eu_energy_policy)')
    parser.add_argument('--delay', type=float, default=1.0,
                        help='Delay between SPARQL queries in seconds (default: 1.0)')
    args = parser.parse_args()

    guides_dir = Path(__file__).parent.parent / 'knowledge_base' / 'guides'
    if not guides_dir.exists():
        print(f"[ERROR] Guides directory not found: {guides_dir}")
        sys.exit(1)

    # Collect files to scan
    if args.guide:
        target = guides_dir / f"{args.guide}.md"
        if not target.exists():
            print(f"[ERROR] Guide not found: {target}")
            sys.exit(1)
        guide_files = [target]
    else:
        guide_files = sorted(guides_dir.glob('*.md'))

    print(f"[START] Scanning {len(guide_files)} guide(s) for CELEX numbers...")
    print()

    # Extract all CELEX numbers
    all_celex: Dict[str, List[Tuple[str, int, str]]] = {}  # celex -> [(file, line, text)]
    file_celex_count: Dict[str, int] = {}

    for filepath in guide_files:
        extracted = extract_celex_from_file(filepath)
        file_celex_count[filepath.stem] = len(extracted)
        for celex, line_num, line_text in extracted:
            if celex not in all_celex:
                all_celex[celex] = []
            all_celex[celex].append((filepath.stem, line_num, line_text))

    unique_celex = sorted(all_celex.keys())
    total_refs = sum(len(v) for v in all_celex.values())
    print(f"[INFO] Found {total_refs} CELEX references ({len(unique_celex)} unique) across {len(guide_files)} files")
    print()

    if not unique_celex:
        print("[OK] No CELEX numbers found to validate.")
        return

    # Validate against CELLAR
    client = EURLexClient()
    valid_count = 0
    invalid_count = 0
    error_count = 0
    invalid_entries = []

    try:
        for i, celex in enumerate(unique_celex, 1):
            celex_str, is_valid, detail = await validate_celex(client, celex)

            if is_valid:
                valid_count += 1
                if args.verbose:
                    locations = all_celex[celex]
                    files = ', '.join(set(loc[0] for loc in locations))
                    print(f"  [OK] {celex} -> {detail[:80]} ({files})")
            else:
                if 'Query error' in detail:
                    error_count += 1
                else:
                    invalid_count += 1
                invalid_entries.append((celex, detail, all_celex[celex]))
                locations = all_celex[celex]
                for file_stem, line_num, line_text in locations:
                    print(f"  [INVALID] {celex} in {file_stem}.md:{line_num} -> {detail}")

            # Progress indicator every 20
            if i % 20 == 0:
                print(f"  ... validated {i}/{len(unique_celex)}")

            # Delay between queries
            if i < len(unique_celex):
                await asyncio.sleep(args.delay)

    finally:
        await client.close()

    # Summary
    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"  Total unique CELEX numbers: {len(unique_celex)}")
    print(f"  Valid:   {valid_count}")
    print(f"  Invalid: {invalid_count}")
    print(f"  Errors:  {error_count}")
    print()

    if invalid_entries:
        print("INVALID CELEX NUMBERS:")
        for celex, detail, locations in invalid_entries:
            print(f"  {celex}: {detail}")
            for file_stem, line_num, line_text in locations:
                print(f"    -> {file_stem}.md:{line_num}")
    else:
        print("[OK] All CELEX numbers are valid.")

    # Per-file stats
    if args.verbose:
        print()
        print("PER-FILE CELEX COUNT:")
        for file_stem, count in sorted(file_celex_count.items(), key=lambda x: -x[1]):
            if count > 0:
                print(f"  {file_stem}: {count} references")


if __name__ == '__main__':
    asyncio.run(main())
