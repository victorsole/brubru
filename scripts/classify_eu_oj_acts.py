#!/usr/bin/env python3
import argparse
import csv
import json
import os
import re
import sys
from typing import Dict, Optional, Tuple

try:
    # Python 3.9+
    import xml.etree.ElementTree as ET
except Exception as e:
    print(f"Failed to import XML parser: {e}", file=sys.stderr)
    sys.exit(1)


def load_policy_areas(policies_json_path: str) -> Dict[str, str]:
    with open(policies_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    # Flatten policy area names into a set for validation; mapping will be heuristic
    areas = {}
    for cat in data.get('policy_categories', []):
        for pa in cat.get('policy_areas', []):
            name = pa.get('name')
            if name:
                areas[name] = cat.get('category', '')
    return areas


LEGAL_VALUE_MAP = {
    'REG_IMPL': 'Implementing Regulation',
    'REG_DEL': 'Delegated Regulation',
    'REG': 'Regulation',
    'DIR': 'Directive',
    'DEC_IMPL': 'Implementing Decision',
    'DEC_DEL': 'Delegated Decision',
    'DEC': 'Decision',
    'RECOMM': 'Recommendation',
    'COMM': 'Communication',
    'CORRIG': 'Corrigendum',
    'NOTICE': 'Notice',
    'OPINION': 'Opinion',
}


TITLE_TYPE_REGEXES = [
    (re.compile(r"\bDelegated Regulation\b", re.I), 'Delegated Regulation'),
    (re.compile(r"\bImplementing Regulation\b", re.I), 'Implementing Regulation'),
    (re.compile(r"\bRegulation\b", re.I), 'Regulation'),
    (re.compile(r"\bDelegated Decision\b", re.I), 'Delegated Decision'),
    (re.compile(r"\bImplementing Decision\b", re.I), 'Implementing Decision'),
    (re.compile(r"\bDecision\b", re.I), 'Decision'),
    (re.compile(r"\bDirective\b", re.I), 'Directive'),
    (re.compile(r"\bRecommendation\b", re.I), 'Recommendation'),
    (re.compile(r"\bOpinion\b", re.I), 'Opinion'),
    (re.compile(r"\bNotice\b", re.I), 'Notice'),
    (re.compile(r"\bCommunication\b", re.I), 'Communication'),
]


def detect_type_of_law_from_title(title: str) -> Optional[str]:
    if not title:
        return None
    # Prefer the earliest occurring legal form in the title line
    best = None
    best_pos = 10**9
    search_text = title[:400]  # focus on the beginning where the legal form appears
    for rx, label in TITLE_TYPE_REGEXES:
        m = rx.search(search_text)
        if m and m.start() < best_pos:
            best = label
            best_pos = m.start()
    return best


def extract_text(elem: ET.Element) -> str:
    # Extract text recursively without tags
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        parts.append(extract_text(child))
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts)


def find_first(elem: ET.Element, paths: Tuple[str, ...]) -> Optional[ET.Element]:
    for p in paths:
        found = elem.find(p)
        if found is not None:
            return found
    return None


def extract_title_and_legal_value(xml_root: ET.Element) -> Tuple[Optional[str], Optional[str]]:
    # Try common locations for TITLE; schema may vary
    title_text = None
    legal_value = None

    # LEGAL.VALUE sometimes appears under DOC.MAIN.PUB in doc containers; for ACT may be absent
    lv_elem = xml_root.find('.//LEGAL.VALUE')
    if lv_elem is not None and lv_elem.text:
        legal_value = lv_elem.text.strip()

    # Try TITLE under root
    title_elem = find_first(xml_root, ('./TITLE', './/TITLE', './/TI'))
    if title_elem is not None:
        title_text = ' '.join(extract_text(title_elem).split()) or None

    # Fallback: sometimes PDF/TITLE exists in doc containers
    if not title_text:
        pdf_title = xml_root.find('.//PDF//TITLE')
        if pdf_title is not None:
            title_text = ' '.join(extract_text(pdf_title).split()) or None

    return title_text, legal_value


def extract_year_from_filename(path: str) -> Optional[str]:
    base = os.path.basename(path)
    m = re.search(r'^[LCI]?_([0-9]{4})', base)
    if m:
        return m.group(1)
    m = re.search(r'([12][0-9]{3})', base)
    if m:
        return m.group(1)
    return None


def extract_year_from_xml(xml_root: ET.Element) -> Optional[str]:
    # Try various DATE locations
    for date_elem in xml_root.findall('.//DATE'):
        val = (date_elem.get('ISO') or '').strip()
        if len(val) >= 4 and val[:4].isdigit():
            return val[:4]
        # text content fallback
        text = (date_elem.text or '').strip()
        m = re.search(r'([12][0-9]{3})', text)
        if m:
            return m.group(1)
    return None


def build_policy_keyword_map() -> Dict[str, str]:
    # Map lowercase keyword -> policy area name from eu_policies.json
    return {
        # Core Economic and Market Policies
        'state aid': 'Competition',
        'competition': 'Competition',
        'merger': 'Competition',
        'mergers': 'Competition',
        'block exemption': 'Competition',
        'gber': 'Competition',
        'antitrust': 'Competition',
        'abuse of dominance': 'Competition',
        'dominant position': 'Competition',
        'foreign subsidies': 'Competition',
        'trade defence': 'Trade and Economic Security',
        'trade defense': 'Trade and Economic Security',
        'trade': 'Trade and Economic Security',
        'anti-dumping': 'Trade and Economic Security',
        'countervailing': 'Trade and Economic Security',
        'safeguard': 'Trade and Economic Security',
        'export control': 'Trade and Economic Security',
        'dual-use': 'Trade and Economic Security',
        'import': 'Trade and Economic Security',
        'export': 'Trade and Economic Security',
        'cbam': 'Climate Action',
        'wto': 'Trade and Economic Security',
        'tariff': 'Customs',
        'customs': 'Customs',
        'combined nomenclature': 'Customs',
        'taric': 'Customs',
        'customs duty': 'Customs',
        'vat': 'Taxation',
        'excise': 'Taxation',
        'tax': 'Taxation',
        'banking': 'Economic and Financial Affairs',
        'capital requirements': 'Economic and Financial Affairs',
        'emir': 'Economic and Financial Affairs',
        'mifid': 'Economic and Financial Affairs',
        'mifir': 'Economic and Financial Affairs',
        'aifmd': 'Economic and Financial Affairs',
        'ucits': 'Economic and Financial Affairs',
        'csdr': 'Economic and Financial Affairs',
        'solvency': 'Economic and Financial Affairs',
        'insurance': 'Economic and Financial Affairs',
        'anti-money laundering': 'Economic and Financial Affairs',
        'aml': 'Economic and Financial Affairs',
        'capital markets': 'Economic and Financial Affairs',
        'internal market': 'Single Market',
        'single market': 'Single Market',
        'standardisation': 'Single Market',
        'standardization': 'Single Market',
        'ce marking': 'Single Market',
        'mutual recognition': 'Single Market',

        # Sustainability and Environmental Policies
        'emission': 'Climate Action',
        'ets': 'Climate Action',
        'greenhouse': 'Climate Action',
        'co2': 'Climate Action',
        'carbon border': 'Climate Action',
        'waste': 'Environment',
        'biodiversity': 'Environment',
        'chemicals': 'Environment',
        'reach': 'Environment',
        'clp': 'Environment',
        'rohs': 'Environment',
        'weee': 'Environment',
        'batteries': 'Environment',
        'packaging': 'Environment',
        'pollut': 'Environment',
        'air quality': 'Environment',
        'water': 'Environment',
        'habitat': 'Environment',
        'nitrates': 'Environment',
        'biocidal': 'Environment',
        'biocide': 'Environment',
        'energy': 'Energy',
        'electricity': 'Energy',
        'gas': 'Energy',
        'renewable': 'Energy',
        'hydrogen': 'Energy',
        'ecodesign': 'Energy',
        'acer': 'Energy',
        'entsoe': 'Energy',
        'entsog': 'Energy',
        'transport': 'Transport',
        'aviation': 'Transport',
        'single european sky': 'Transport',
        'air traffic': 'Transport',
        'air navigation': 'Transport',
        'rail': 'Transport',
        'road': 'Transport',
        'maritime': 'Transport',
        'ten-t': 'Transport',
        'easa': 'Transport',
        'type-approval': 'Transport',

        # Agriculture and Natural Resources
        'agricultur': 'Agriculture',  # match agriculture/agricultural
        'cap ': 'Agriculture',
        'olive oil': 'Agriculture',
        'wine': 'Agriculture',
        'cheese': 'Agriculture',
        'pgi': 'Agriculture',
        'pdo': 'Agriculture',
        'organic': 'Agriculture',
        'plant health': 'Agriculture',
        'animal health': 'Agriculture',
        'zootechnical': 'Agriculture',
        'fisher': 'Maritime Affairs and Fisheries',
        'tac and quota': 'Maritime Affairs and Fisheries',
        'quota': 'Maritime Affairs and Fisheries',
        'multiannual plan': 'Maritime Affairs and Fisheries',
        'food safety': 'Food Safety',
        'contaminant': 'Food Safety',
        'hygiene': 'Food Safety',

        # Cohesion and Development
        'cohesion': 'Regional Policy',
        'erdf': 'Regional Policy',
        'esf': 'Regional Policy',
        'horizon': 'Research and Innovation',
        'research': 'Research and Innovation',
        'innovation': 'Research and Innovation',
        'erasmus': 'Education, Training and Youth',
        'education': 'Education, Training and Youth',
        'culture': 'Culture',

        # Social Policies
        'employment': 'Employment and Social Affairs',
        'social': 'Employment and Social Affairs',
        'working conditions': 'Employment and Social Affairs',
        'public health': 'Health',
        'medicinal product': 'Health',
        'medical device': 'Health',
        'pharmacovigilance': 'Health',
        'consumer': 'Consumer Protection',
        'product safety': 'Consumer Protection',

        # Justice and Home Affairs
        'data protection': 'Justice and Fundamental Rights',
        'fundamental rights': 'Justice and Fundamental Rights',
        'asylum': 'Migration and Home Affairs',
        'schengen': 'Migration and Home Affairs',
        'border': 'Migration and Home Affairs',
        'europol': 'Migration and Home Affairs',
        'gender': 'Women\'s Rights and Gender Equality',

        # External Relations
        'cfsp': 'Foreign and Security Policy',
        'restrictive measures': 'Foreign and Security Policy',
        'sanctions': 'Foreign and Security Policy',
        'development cooperation': 'Development and Cooperation',
        'ipa': 'Neighbourhood and Enlargement',
        'enlargement': 'Neighbourhood and Enlargement',
        'neighbourhood': 'Neighbourhood and Enlargement',
        'human rights': 'Human Rights and Democracy',
        'humanitarian': 'Humanitarian Aid and Civil Protection',

        # Emerging Strategic Areas
        'defence': 'Defence and Security',
        'defense': 'Defence and Security',
        'pESCO': 'Defence and Security',
        'space': 'Space Policy',
        'galileo': 'Space Policy',
        'copernicus': 'Space Policy',
        'statistic': 'Statistics',
        'eurostat': 'Statistics',

        # Digital Transformation
        'digital markets': 'Digital Policy and Digital Economy',
        'dma': 'Digital Policy and Digital Economy',
        'digital services': 'Digital Policy and Digital Economy',
        'dsa': 'Digital Policy and Digital Economy',
        'ai act': 'Digital Policy and Digital Economy',
        'data act': 'Digital Policy and Digital Economy',
        'data governance': 'Digital Policy and Digital Economy',
        'cybersecurity': 'Digital Policy and Digital Economy',
        'nis': 'Digital Policy and Digital Economy',
        'eidas': 'Digital Policy and Digital Economy',
        'electronic communications': 'Communication Networks, Content and Technology',
        'broadband': 'Communication Networks, Content and Technology',
    }


def classify_policy_area(title: str, policy_names: Dict[str, str], full_text: Optional[str] = None) -> Optional[str]:
    # Try title first, then fall back to a broader text scan
    kw_map = build_policy_keyword_map()
    def match_area(text: str) -> Optional[str]:
        t = text.lower()
        for kw in sorted(kw_map.keys(), key=len, reverse=True):
            if kw in t:
                area = kw_map[kw]
                if area in policy_names:
                    return area
        return None

    if title:
        area = match_area(title)
        if area:
            return area
    if full_text:
        area = match_area(full_text[:50000])
        if area:
            return area
    # Broad fallback
    t = (title or '').lower()
    if 'regulation' in t or 'directive' in t:
        return 'Single Market' if 'market' in t else None
    return None


def parse_xml_file(path: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    # Returns (title, type_of_law, year, full_text_snippet)
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception:
        # As a fallback, try to extract year from filename only
        return None, None, extract_year_from_filename(path), None

    title, legal_value = extract_title_and_legal_value(root)
    type_of_law = None
    if legal_value and legal_value in LEGAL_VALUE_MAP:
        type_of_law = LEGAL_VALUE_MAP[legal_value]
    if not type_of_law:
        type_of_law = detect_type_of_law_from_title(title or '')
    # Simple heuristic: mark Annex when clearly indicated
    if (not type_of_law) and title and title.strip().upper().startswith('ANNEX'):
        type_of_law = 'Annex'

    year = extract_year_from_filename(path)
    if not year:
        year = extract_year_from_xml(root)

    # Build a full-text snippet to improve policy mapping
    try:
        full_text = ' '.join(extract_text(root).split())
    except Exception:
        full_text = None

    return title, type_of_law, year, full_text


def should_include_file(path: str) -> bool:
    # Include content XMLs; exclude containers and TOCs
    if not path.lower().endswith('.xml'):
        return False
    lower = path.lower()
    # Include .fmx.xml segments (they can contain <ACT> or Annex content)
    # but exclude doc/toc containers
    if lower.endswith('.doc.xml'):
        return False
    if lower.endswith('.toc.fmx.xml'):
        return False
    if lower.endswith('.doc.fmx.xml'):
        return False
    return True


def iter_input_files(input_dir: str, filter_year: Optional[str] = None, list_file: Optional[str] = None):
    if list_file:
        with open(list_file, 'r', encoding='utf-8') as f:
            for line in f:
                p = line.strip()
                if not p:
                    continue
                if not should_include_file(p):
                    continue
                if filter_year:
                    y = extract_year_from_filename(os.path.basename(p))
                    if y != filter_year:
                        continue
                yield p
        return
    for root, _, files in os.walk(input_dir):
        for name in files:
            path = os.path.join(root, name)
            if not should_include_file(path):
                continue
            if filter_year:
                y = extract_year_from_filename(name)
                if y != filter_year:
                    continue
            yield path


def main():
    ap = argparse.ArgumentParser(description='Classify EU OJ acts by policy area, extracting type, title, year.')
    ap.add_argument('--input-dir', required=True, help='Root directory (e.g., docs/LEG_2025-11)')
    ap.add_argument('--policies-json', required=True, help='Path to eu_policies.json')
    ap.add_argument('--output-csv', required=True, help='Output CSV path')
    ap.add_argument('--year', help='Filter by year (e.g., 2025)')
    ap.add_argument('--list-file', help='Optional prebuilt list of files to consider')
    ap.add_argument('--only-types', help='Comma-separated filters; keep rows whose type equals one of these (case-insensitive), e.g., "regulation,directive"')
    args = ap.parse_args()

    policy_names = load_policy_areas(args.policies_json)

    total = 0
    written = 0
    only_types = None
    if args.only_types:
        only_types = set(t.strip().lower() for t in args.only_types.split(',') if t.strip())

    with open(args.output_csv, 'w', newline='', encoding='utf-8') as out:
        w = csv.writer(out)
        w.writerow(['file_path', 'type_of_law', 'title', 'year', 'policy_area'])

        for path in iter_input_files(args.input_dir, filter_year=args.year, list_file=args.list_file):
            total += 1
            title, type_of_law, year, full_text = parse_xml_file(path)
            # Filter by requested legal types (exact, case-insensitive)
            if only_types:
                if not type_of_law:
                    continue
                low = type_of_law.lower()
                if low not in only_types:
                    continue
            policy_area = classify_policy_area(title or '', policy_names, full_text=full_text)
            w.writerow([path, type_of_law or '', title or '', year or '', policy_area or ''])
            written += 1

    print(f"Processed {written} entries (from {total} candidates)")


if __name__ == '__main__':
    main()
