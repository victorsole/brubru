"""
eForms SDK Data Extraction Script

Converts Genericode XML (.gc) codelists from the OP-TED eForms SDK
into JSON files for use in Tenderator.

Source: https://github.com/OP-TED/eForms-SDK

Usage:
    python -m backend.scripts.extract_eforms_sdk /path/to/eForms-SDK
"""

import xml.etree.ElementTree as ET
import json
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Genericode XML namespace
GC_NS = {'gc': 'http://docs.oasis-open.org/codelist/ns/genericode/1.0/'}

# Priority codelists to convert (filename without .gc extension)
PRIORITY_CODELISTS = [
    ('country', 'countries.json'),
    ('cpv', 'cpv_codes.json'),
    ('procurement-procedure-type', 'procedure_types.json'),
    ('currency', 'currencies.json'),
    ('exclusion-ground', 'exclusion_grounds.json'),
    ('selection-criterion', 'selection_criteria.json'),
    ('nuts', 'nuts_regions.json'),
    ('award-criterion-type', 'award_criteria.json'),
    ('legal-basis', 'legal_basis.json'),
    ('notice-type', 'notice_types.json'),
    ('form-type', 'form_types.json'),
    ('contract-nature', 'contract_nature.json'),
    ('buyer-legal-type', 'buyer_legal_types.json'),
    ('main-activity', 'main_activities.json'),
]


def parse_genericode(gc_file: Path) -> Dict[str, Any]:
    """
    Parse a Genericode XML file and extract metadata and rows.

    Returns:
        {
            "identification": {...},
            "columns": [...],
            "items": [...]
        }
    """
    tree = ET.parse(gc_file)
    root = tree.getroot()

    result = {
        "source_file": gc_file.name,
        "columns": [],
        "items": []
    }

    # Some elements have namespace prefix, some don't - try both
    def find_element(parent, tag):
        """Find element with or without namespace prefix."""
        elem = parent.find(f'gc:{tag}', GC_NS)
        if elem is None:
            elem = parent.find(tag)
        return elem

    def find_all_elements(parent, tag):
        """Find all elements with or without namespace prefix."""
        elems = parent.findall(f'.//gc:{tag}', GC_NS)
        if not elems:
            elems = parent.findall(f'.//{tag}')
        return elems

    # Extract identification metadata
    ident = find_element(root, 'Identification')
    if ident is not None:
        short_name = find_element(ident, 'ShortName')
        version = find_element(ident, 'Version')
        result["identification"] = {
            "short_name": short_name.text if short_name is not None else None,
            "version": version.text if version is not None else None
        }

    # Extract column definitions - try with namespace first, then without
    columns = root.findall('.//gc:Column', GC_NS)
    if not columns:
        columns = root.findall('.//Column')

    for col in columns:
        col_id = col.get('Id')
        col_use = col.get('Use', 'optional')
        result["columns"].append({
            "id": col_id,
            "use": col_use
        })

    # Extract rows - try with namespace first, then without
    rows = root.findall('.//gc:Row', GC_NS)
    if not rows:
        rows = root.findall('.//Row')

    for row in rows:
        item = {}
        # Try with namespace
        values = row.findall('gc:Value', GC_NS)
        if not values:
            values = row.findall('Value')

        for value in values:
            col_ref = value.get('ColumnRef')
            # Try with namespace
            simple_value = value.find('gc:SimpleValue', GC_NS)
            if simple_value is None:
                simple_value = value.find('SimpleValue')

            if simple_value is not None and simple_value.text:
                item[col_ref] = simple_value.text
        if item:
            result["items"].append(item)

    return result


def convert_codelist(gc_file: Path, output_file: Path) -> int:
    """
    Convert a single Genericode file to JSON.

    Returns:
        Number of items converted
    """
    try:
        data = parse_genericode(gc_file)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return len(data["items"])
    except ET.ParseError as e:
        logger.error(f"Failed to parse {gc_file}: {e}")
        return 0
    except Exception as e:
        logger.error(f"Error converting {gc_file}: {e}")
        return 0


def extract_sdk(sdk_path: Path, output_path: Path) -> Dict[str, int]:
    """
    Extract all priority codelists from the eForms SDK.

    Args:
        sdk_path: Path to cloned eForms-SDK repository
        output_path: Path to output directory for JSON files

    Returns:
        Dict mapping output filename to item count
    """
    codelists_dir = sdk_path / "codelists"

    if not codelists_dir.exists():
        raise FileNotFoundError(f"Codelists directory not found: {codelists_dir}")

    results = {}

    for gc_name, json_name in PRIORITY_CODELISTS:
        gc_file = codelists_dir / f"{gc_name}.gc"

        if not gc_file.exists():
            logger.warning(f"Codelist not found: {gc_file}")
            continue

        output_file = output_path / json_name
        count = convert_codelist(gc_file, output_file)

        if count > 0:
            logger.info(f"✓ {gc_name}.gc → {json_name} ({count} items)")
            results[json_name] = count
        else:
            logger.warning(f"✗ {gc_name}.gc → failed or empty")

    return results


def create_summary(results: Dict[str, int], output_path: Path):
    """Create a summary JSON file with extraction metadata."""
    summary = {
        "extraction_date": __import__('datetime').datetime.now().isoformat(),
        "source": "OP-TED eForms SDK",
        "repository": "https://github.com/OP-TED/eForms-SDK",
        "files": results,
        "total_items": sum(results.values())
    }

    summary_file = output_path / "codelists_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    logger.info(f"✓ Summary written to {summary_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Extract eForms SDK codelists to JSON"
    )
    parser.add_argument(
        "sdk_path",
        type=Path,
        help="Path to cloned eForms-SDK repository"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("backend/knowledge_base/tenders/codelists"),
        help="Output directory for JSON files"
    )

    args = parser.parse_args()

    logger.info(f"Extracting codelists from {args.sdk_path}")
    logger.info(f"Output directory: {args.output}")

    results = extract_sdk(args.sdk_path, args.output)

    if results:
        create_summary(results, args.output)
        logger.info(f"\n✓ Extraction complete: {len(results)} codelists, {sum(results.values())} total items")
    else:
        logger.error("No codelists were extracted")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
