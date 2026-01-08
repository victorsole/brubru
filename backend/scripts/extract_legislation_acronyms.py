"""
Extract Legislation Acronyms from LEG_2025-11 Directory

Parses 50k+ EU law XML files to build a comprehensive acronym-to-CELEX mapping database.
Extracts:
- Law titles
- CELEX numbers
- Acronyms (from parentheses in titles)
- Document types (Regulation, Directive, etc.)
- Years

Output: backend/knowledge_base/institutions/legislation_acronyms.json
"""

import os
import re
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, List, Optional, Set
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class LegislationAcronymExtractor:
    """Extract acronyms from EU legislation XML files"""

    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self.acronym_map: Dict[str, Dict] = {}
        self.stats = {
            'total_directories': 0,
            'processed_files': 0,
            'acronyms_found': 0,
            'errors': 0
        }

    def extract_celex_from_title(self, title: str) -> Optional[str]:
        """
        Extract CELEX number from title.
        Examples:
        - "Regulation (EU) 2023/956" -> 32023R0956
        - "Directive (EU) 2022/2555" -> 32022L2555
        - "Decision (EU) 2022/2391" -> 32022D2391
        """
        # Pattern: (Type) (EU|EC|EEC|EURATOM) YYYY/NNNN
        patterns = [
            (r'Regulation\s+\((?:EU|EC|EEC|EURATOM)\)\s+(?:No\s+)?(\d{4})/(\d+)', 'R'),
            (r'Directive\s+\((?:EU|EC|EEC|EURATOM)\)\s+(?:No\s+)?(\d{4})/(\d+)', 'L'),
            (r'Decision\s+\((?:EU|EC|EEC|EURATOM)\)\s+(?:No\s+)?(\d{4})/(\d+)', 'D'),
            # Alternative: (EU) No NNNN/YYYY format
            (r'Regulation\s+\((?:EU|EC|EEC|EURATOM)\)\s+No\s+(\d+)/(\d{4})', 'R'),
            (r'Directive\s+\((?:EU|EC|EEC|EURATOM)\)\s+No\s+(\d+)/(\d{4})', 'L'),
            (r'Decision\s+\((?:EU|EC|EEC|EURATOM)\)\s+No\s+(\d+)/(\d{4})', 'D'),
        ]

        for pattern, doc_type in patterns:
            match = re.search(pattern, title)
            if match:
                # Check which group has the year (4 digits)
                group1, group2 = match.groups()
                if len(group1) == 4:  # Year first: YYYY/NNNN
                    year, number = group1, group2
                else:  # Number first: NNNN/YYYY
                    number, year = group1, group2

                return f"3{year}{doc_type}{number.zfill(4)}"

        return None

    def extract_acronyms_from_title(self, title: str) -> List[str]:
        """
        Extract acronyms from title text.
        Looks for patterns like:
        - "Name (ACRONYM)"
        - "Name (ACRONYM 1, ACRONYM 2)"
        - Common patterns with parentheses
        """
        acronyms = []

        # Pattern 1: Text (ACRONYM) - most common
        # Look for uppercase acronyms in parentheses
        pattern1 = r'\(([A-Z][A-Z0-9&\-/]+(?:\s+[IVX]+)?)\)'
        matches1 = re.findall(pattern1, title)
        acronyms.extend(matches1)

        # Pattern 2: Multiple acronyms separated by comma/slash
        # e.g., "(CBAM/ETS)"
        for match in matches1:
            if '/' in match or ',' in match:
                # Split and add individual parts
                parts = re.split(r'[/,]', match)
                acronyms.extend([p.strip() for p in parts if len(p.strip()) > 1])

        # Pattern 3: Well-known multi-word acronyms
        # "AI Act", "Data Act", etc.
        pattern3 = r'\b((?:[A-Z][a-z]*\s+)+Act)\b'
        matches3 = re.findall(pattern3, title)
        acronyms.extend(matches3)

        # Clean and deduplicate
        cleaned = []
        for acr in acronyms:
            acr = acr.strip()
            # Filter out very short (single letter) or very long acronyms
            if 2 <= len(acr) <= 50:
                # Avoid common words that might be uppercase
                if acr.upper() not in ['THE', 'AND', 'FOR', 'WITH', 'FROM']:
                    cleaned.append(acr)

        return list(set(cleaned))  # Deduplicate

    def extract_title_from_xml(self, xml_path: Path) -> Optional[str]:
        """Extract title from FormEx XML"""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()

            # FormEx XML structure: <ACT><TITLE><TI><P>...</P></TI></TITLE>
            # Find all text in TITLE element
            title_elem = root.find('.//TITLE')
            if title_elem is not None:
                # Get all text content, joining with spaces
                text_parts = []
                for elem in title_elem.iter():
                    if elem.text:
                        text_parts.append(elem.text.strip())
                    if elem.tail:
                        text_parts.append(elem.tail.strip())

                title = ' '.join(text_parts)
                # Clean up extra whitespace
                title = re.sub(r'\s+', ' ', title).strip()
                return title

            return None

        except Exception as e:
            logger.debug(f"Failed to parse XML {xml_path}: {str(e)}")
            return None

    def extract_doc_type_and_year(self, title: str) -> tuple:
        """Extract document type and year from title"""
        doc_type = "Unknown"
        year = None

        # Extract type
        if "Regulation" in title:
            doc_type = "Regulation"
        elif "Directive" in title:
            doc_type = "Directive"
        elif "Decision" in title:
            doc_type = "Decision"
        elif "Recommendation" in title:
            doc_type = "Recommendation"
        elif "Opinion" in title:
            doc_type = "Opinion"

        # Extract year (look for patterns like "2023/956" or "No 956/2023")
        year_match = re.search(r'(?:20\d{2})/\d+|No\s+\d+/(20\d{2})', title)
        if year_match:
            year_str = year_match.group()
            year = int(re.search(r'20\d{2}', year_str).group())

        return doc_type, year

    def process_directory(self, dir_path: Path) -> None:
        """Process a single law directory"""
        self.stats['total_directories'] += 1

        # Look for XML files in fmx4 subdirectory
        fmx4_dir = dir_path / 'fmx4'
        if not fmx4_dir.exists():
            return

        # Process all XML files (excluding .doc.xml and .doc.fmx.xml files, and .toc.fmx.xml)
        xml_files = [f for f in fmx4_dir.glob('*.xml')
                    if not f.name.endswith('.doc.xml')
                    and not f.name.endswith('.doc.fmx.xml')
                    and not f.name.endswith('.toc.fmx.xml')]

        for xml_file in xml_files:
            try:
                # Extract title
                title = self.extract_title_from_xml(xml_file)
                if not title:
                    continue

                # Extract CELEX number from title
                celex = self.extract_celex_from_title(title)
                if not celex:
                    continue

                # Extract acronyms from title
                acronyms = self.extract_acronyms_from_title(title)

                # Extract type and year
                doc_type, year = self.extract_doc_type_and_year(title)

                # Store each acronym
                for acronym in acronyms:
                    # If acronym already exists, only keep if this is a more important document
                    if acronym in self.acronym_map:
                        # Prefer Regulations over Directives over Decisions
                        existing_type = self.acronym_map[acronym].get('type', '')
                        type_priority = {'Regulation': 3, 'Directive': 2, 'Decision': 1}
                        existing_priority = type_priority.get(existing_type, 0)
                        new_priority = type_priority.get(doc_type, 0)

                        if new_priority <= existing_priority:
                            continue  # Keep existing

                    self.acronym_map[acronym] = {
                        'celex': celex,
                        'full_title': title[:200],  # Truncate to 200 chars
                        'type': doc_type,
                        'year': year,
                        'source_file': xml_file.name
                    }
                    self.stats['acronyms_found'] += 1

                self.stats['processed_files'] += 1

                # Log progress every 1000 files
                if self.stats['processed_files'] % 1000 == 0:
                    logger.info(f"Processed {self.stats['processed_files']} files, "
                              f"found {len(self.acronym_map)} unique acronyms")

            except Exception as e:
                self.stats['errors'] += 1
                logger.debug(f"Error processing {xml_file}: {str(e)}")

    def process_all(self) -> None:
        """Process all law directories"""
        logger.info(f"Starting extraction from {self.source_dir}")
        logger.info(f"Scanning directories...")

        # Get all subdirectories
        law_dirs = [d for d in self.source_dir.iterdir() if d.is_dir() and not d.name.startswith('.')]
        total_dirs = len(law_dirs)

        logger.info(f"Found {total_dirs} law directories to process")

        for i, law_dir in enumerate(law_dirs, 1):
            self.process_directory(law_dir)

            # Log progress every 1000 directories
            if i % 1000 == 0:
                logger.info(f"Progress: {i}/{total_dirs} directories ({i/total_dirs*100:.1f}%)")

        logger.info("Extraction complete!")
        logger.info(f"Statistics:")
        logger.info(f"  Total directories: {self.stats['total_directories']}")
        logger.info(f"  Processed files: {self.stats['processed_files']}")
        logger.info(f"  Unique acronyms found: {len(self.acronym_map)}")
        logger.info(f"  Errors: {self.stats['errors']}")

    def save_to_json(self, output_path: Path) -> None:
        """Save acronym database to JSON, merging with manual curated list"""
        # Load manual curated acronyms
        manual_path = output_path.parent / 'legislation_acronyms_manual.json'
        manual_acronyms = {}

        if manual_path.exists():
            try:
                with open(manual_path, 'r', encoding='utf-8') as f:
                    manual_data = json.load(f)
                    manual_acronyms = manual_data.get('acronyms', {})
                    logger.info(f"Loaded {len(manual_acronyms)} manually curated acronyms")
            except Exception as e:
                logger.warning(f"Could not load manual acronyms: {e}")

        # Merge: manual acronyms take precedence over auto-extracted ones
        merged_acronyms = self.acronym_map.copy()
        for acronym, data in manual_acronyms.items():
            merged_acronyms[acronym] = data
            logger.debug(f"Added manual acronym: {acronym}")

        output_data = {
            'metadata': {
                'title': 'EU Legislation Acronyms - Complete Database',
                'description': 'Comprehensive acronym-to-CELEX mapping from automated extraction + manual curation',
                'source': 'docs/LEG_2025-11/ + manual curation',
                'extraction_date': '2025-11-19',
                'total_entries': len(merged_acronyms),
                'auto_extracted': len(self.acronym_map),
                'manually_curated': len(manual_acronyms),
                'extraction_stats': self.stats
            },
            'acronyms': merged_acronyms
        }

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save with pretty printing
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved acronym database to {output_path}")
        logger.info(f"File size: {output_path.stat().st_size / 1024:.1f} KB")


def main():
    """Main execution"""
    # Paths
    source_dir = Path(__file__).parent.parent.parent / 'docs' / 'LEG_2025-11'
    output_path = Path(__file__).parent.parent / 'knowledge_base' / 'institutions' / 'legislation_acronyms.json'

    # Check if source directory exists
    if not source_dir.exists():
        logger.error(f"Source directory not found: {source_dir}")
        return

    # Extract acronyms
    extractor = LegislationAcronymExtractor(str(source_dir))
    extractor.process_all()

    # Save results
    extractor.save_to_json(output_path)

    # Print sample entries
    logger.info("\nSample entries:")
    for i, (acronym, data) in enumerate(list(extractor.acronym_map.items())[:10]):
        logger.info(f"  {acronym}: {data['celex']} - {data['full_title'][:80]}...")
        if i >= 9:
            break


if __name__ == '__main__':
    main()
