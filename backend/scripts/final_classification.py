"""
Final Classification Push for eu_laws Table

Classifies remaining ~3,689 unclassified primary laws using three strategies:
1. Citation network propagation
2. Preamble/institution heuristic
3. Aggressive title keyword scan

Usage:
    cd backend
    python3.12 -m backend.scripts.final_classification [--dry-run] [--verbose] [--strategy 1|2|3|all]
"""

import sys
import os
import argparse
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import Counter
from typing import Optional, Dict, List, Tuple

# Add project root to path
PROJECT_ROOT = str(Path(__file__).parent.parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BATCH_SIZE = 200

# -----------------------------------------------------------------
# Strategy 3: Aggressive keyword map (extends the existing classifier)
# -----------------------------------------------------------------
AGGRESSIVE_KEYWORDS: Dict[str, List[Tuple[str, float]]] = {
    "Climate Action": [
        ("climate", 3.0), ("emission", 3.0), ("carbon", 3.0), ("greenhouse", 3.0),
        ("ets", 3.0), ("co2", 3.0), ("decarbonisation", 3.0), ("net zero", 2.0),
        ("ozone", 2.0), ("fluorinated", 2.0),
    ],
    "Environment": [
        ("environment", 3.0), ("environmental", 3.0), ("pollution", 3.0), ("waste", 3.0),
        ("water", 2.0), ("air quality", 2.0), ("biodiversity", 2.0), ("nature", 2.0),
        ("habitat", 2.0), ("species", 2.0), ("conservation", 2.0), ("recycling", 2.0),
        ("hazardous", 1.5), ("chemical", 1.5), ("pesticide", 2.0),
    ],
    "Digital Policy and Digital Economy": [
        ("digital", 3.0), ("platform", 2.0), ("data", 1.5), ("online", 2.0),
        ("internet", 2.0), ("e-commerce", 3.0), ("artificial intelligence", 3.0),
        ("algorithm", 2.0), ("cybersecurity", 2.0), ("electronic signature", 2.0),
        ("software", 2.0),
    ],
    "Energy": [
        ("energy", 3.0), ("renewable", 3.0), ("electricity", 3.0), ("gas", 2.0),
        ("nuclear", 2.5), ("power plant", 2.0), ("solar", 2.0), ("wind energy", 2.0),
        ("hydropower", 2.0), ("energy efficiency", 3.0), ("atomic", 2.0),
        ("euratom", 3.0), ("radioactive", 2.0), ("reactor", 2.0),
    ],
    "Transport": [
        ("transport", 3.0), ("aviation", 3.0), ("maritime", 2.5), ("railway", 3.0),
        ("road", 2.0), ("vehicle", 2.5), ("shipping", 2.0), ("aircraft", 2.5),
        ("mobility", 2.0), ("traffic", 2.0), ("airport", 2.5), ("aerospace", 2.5),
        ("motor", 2.0), ("driver", 2.0), ("tyre", 2.0), ("airline", 3.0),
        ("inland waterway", 3.0), ("navigation", 1.5), ("rail", 2.0),
    ],
    "Competition": [
        ("competition", 3.0), ("antitrust", 3.0), ("merger", 3.0), ("state aid", 3.0),
        ("cartel", 3.0), ("dominant position", 2.0), ("concentration", 1.5),
    ],
    "Single Market": [
        ("single market", 3.0), ("internal market", 3.0), ("free movement", 3.0),
        ("harmonisation", 2.0), ("mutual recognition", 2.0), ("establishment", 1.5),
        ("textile", 2.0), ("cosmetic", 2.0), ("toy", 2.0), ("machinery", 2.0),
        ("labelling", 1.5), ("packaging", 1.5), ("marking", 1.0),
        ("type-approval", 2.5), ("standardisation", 2.0), ("conformity", 2.0),
    ],
    "Trade and Economic Security": [
        ("trade", 3.0), ("tariff", 3.0), ("import", 2.0), ("export", 2.0),
        ("trade agreement", 3.0), ("anti-dumping", 3.0), ("trade defence", 3.0),
        ("quota", 2.0), ("countervailing", 3.0), ("safeguard measure", 2.0),
        ("generalised scheme of preferences", 3.0), ("originating product", 2.0),
        ("third country", 1.5),
    ],
    "Agriculture": [
        ("agriculture", 3.0), ("agricultural", 3.0), ("farming", 3.0), ("rural", 3.0),
        ("common agricultural policy", 3.0), ("crop", 2.0), ("livestock", 2.0),
        ("wine", 2.0), ("olive", 2.0), ("sugar", 2.0), ("cereal", 2.0),
        ("fruit", 1.5), ("vegetable", 1.5), ("tobacco", 2.0), ("seed", 1.5),
        ("plant health", 2.5), ("phytosanitary", 3.0), ("plant protection", 2.5),
        ("organic farming", 3.0), ("geographical indication", 2.5),
        ("designation of origin", 2.5), ("beef", 2.0), ("pork", 2.0),
        ("poultry", 2.0), ("milk", 2.0), ("dairy", 2.0), ("cotton", 2.0),
        ("hops", 2.0), ("flax", 2.0), ("hemp", 2.0),
    ],
    "Maritime Affairs and Fisheries": [
        ("fisheries", 3.0), ("fishing", 3.0), ("fish", 2.0), ("aquaculture", 3.0),
        ("common fisheries policy", 3.0), ("catch", 1.5), ("vessel", 2.0),
        ("tuna", 2.0), ("cod", 2.0), ("herring", 2.0), ("mackerel", 2.0),
        ("total allowable catch", 3.0),
    ],
    "Food Safety": [
        ("food safety", 3.0), ("food", 2.0), ("hygiene", 3.0), ("foodstuff", 3.0),
        ("nutrition", 2.0), ("food additive", 3.0), ("efsa", 2.0), ("novel food", 3.0),
        ("veterinary", 3.0), ("animal health", 3.0), ("zoonoses", 3.0),
        ("feed", 1.5), ("slaughter", 2.0), ("animal welfare", 2.5),
        ("animal by-product", 3.0), ("contaminant", 2.0), ("residue", 1.5),
        ("maximum residue", 3.0), ("flavouring", 2.0), ("sweetener", 2.0),
    ],
    "Health": [
        ("health", 2.5), ("medicine", 3.0), ("pharmaceutical", 3.0), ("medical", 3.0),
        ("medicinal product", 3.0), ("medical device", 3.0), ("public health", 3.0),
        ("disease", 2.0), ("vaccine", 3.0), ("clinical trial", 3.0),
        ("orphan medicinal", 3.0), ("blood", 2.0), ("tissue", 2.0), ("organ", 2.0),
    ],
    "Employment and Social Affairs": [
        ("employment", 3.0), ("worker", 3.0), ("labour", 3.0), ("social", 2.0),
        ("working conditions", 3.0), ("workplace", 2.0), ("employee", 2.0),
        ("social security", 3.0), ("posted worker", 3.0), ("occupational safety", 3.0),
        ("collective redundancy", 3.0), ("working time", 3.0), ("equal pay", 3.0),
    ],
    "Consumer Protection": [
        ("consumer", 3.0), ("product safety", 3.0), ("consumer rights", 3.0),
        ("consumer protection", 3.0), ("unfair commercial", 3.0),
        ("product liability", 2.0), ("warranty", 2.0),
    ],
    "Justice and Fundamental Rights": [
        ("justice", 3.0), ("fundamental rights", 3.0), ("data protection", 3.0),
        ("privacy", 3.0), ("gdpr", 3.0), ("personal data", 3.0),
        ("judicial cooperation", 3.0), ("rule of law", 2.0), ("charter", 2.0),
        ("drug", 2.0), ("narcotic", 3.0), ("precursor", 2.0),
        ("criminal", 2.5), ("prosecution", 2.5), ("victim", 2.0),
        ("money laundering", 3.0), ("terrorist", 2.0), ("fraud", 2.0),
        ("mutual legal assistance", 3.0), ("extradition", 3.0),
    ],
    "Migration and Home Affairs": [
        ("migration", 3.0), ("asylum", 3.0), ("border", 3.0), ("visa", 3.0),
        ("schengen", 3.0), ("refugee", 2.0), ("immigration", 3.0),
        ("frontex", 2.0), ("residence permit", 3.0), ("third-country national", 3.0),
    ],
    "Research and Innovation": [
        ("research", 3.0), ("innovation", 3.0), ("horizon", 3.0), ("r&d", 3.0),
        ("science", 2.0), ("framework programme", 3.0), ("laboratory", 2.0),
    ],
    "Education, Training and Youth": [
        ("education", 3.0), ("training", 2.0), ("erasmus", 3.0), ("student", 2.0),
        ("youth", 3.0), ("learning", 2.0), ("vocational", 2.5), ("diploma", 2.5),
        ("qualification", 2.0),
    ],
    "Regional Policy": [
        ("regional", 3.0), ("cohesion", 3.0), ("structural funds", 3.0),
        ("regional development", 3.0), ("erdf", 3.0), ("cohesion fund", 3.0),
        ("outermost region", 3.0), ("interreg", 3.0),
    ],
    "Taxation": [
        ("tax", 3.0), ("taxation", 3.0), ("vat", 3.0), ("excise", 3.0),
        ("fiscal", 2.0), ("tax avoidance", 3.0), ("tax evasion", 3.0),
        ("duty", 1.5), ("stamp duty", 2.0),
    ],
    "Economic and Financial Affairs": [
        ("financial", 3.0), ("banking", 3.0), ("finance", 3.0), ("capital markets", 3.0),
        ("payment", 2.0), ("financial services", 3.0), ("monetary", 2.0),
        ("accounting", 2.5), ("audit", 2.0), ("insurance", 3.0), ("credit", 2.0),
        ("bank", 2.5), ("securities", 2.5), ("investment fund", 3.0), ("euro", 2.0),
        ("exchange rate", 2.5), ("central bank", 3.0), ("ecb", 3.0),
        ("prudential", 3.0), ("solvency", 3.0),
    ],
    "Defence and Security": [
        ("defence", 3.0), ("defense", 3.0), ("military", 3.0), ("armament", 3.0),
        ("defence industry", 3.0), ("arms", 2.0), ("dual-use", 2.5),
        ("weapon", 2.5), ("explosive", 2.0), ("firearm", 3.0),
    ],
    "Foreign and Security Policy": [
        ("foreign policy", 3.0), ("external action", 3.0), ("cfsp", 3.0),
        ("eeas", 2.0), ("sanctions", 3.0), ("restrictive measure", 3.0),
        ("embargo", 3.0), ("common position", 2.0), ("joint action", 2.0),
        ("association agreement", 3.0), ("partnership agreement", 2.0),
    ],
    "Communication Networks, Content and Technology": [
        ("telecommunication", 3.0), ("spectrum", 3.0), ("broadband", 3.0),
        ("5g", 3.0), ("telecom", 3.0), ("electronic communications", 3.0),
        ("roaming", 3.0), ("frequency", 2.0), ("postal", 2.0),
    ],
    "Customs": [
        ("customs", 3.0), ("customs union", 3.0), ("customs code", 3.0),
        ("customs procedure", 3.0), ("customs duty", 3.0), ("customs tariff", 3.0),
        ("combined nomenclature", 3.0), ("tariff classification", 3.0),
        ("inward processing", 3.0), ("outward processing", 3.0),
    ],
    "Business and Industry": [
        ("industry", 3.0), ("industrial", 3.0), ("sme", 2.0),
        ("small and medium", 2.0), ("manufacturing", 2.0), ("company law", 3.0),
        ("corporate governance", 3.0), ("insolvency", 2.5), ("patent", 2.5),
        ("trademark", 2.5), ("intellectual property", 3.0), ("copyright", 2.5),
        ("design protection", 2.5),
    ],
    "Culture": [
        ("culture", 3.0), ("cultural", 3.0), ("heritage", 3.0), ("creative", 2.0),
        ("audiovisual", 3.0), ("media", 2.0), ("broadcasting", 2.5), ("film", 2.0),
        ("sport", 2.0),
    ],
    "Space Policy": [
        ("space", 3.0), ("satellite", 3.0), ("galileo", 3.0), ("copernicus", 3.0),
        ("space programme", 3.0), ("orbit", 2.0),
    ],
    "Statistics": [
        ("statistics", 3.0), ("statistical", 3.0), ("eurostat", 3.0),
        ("census", 2.0), ("nomenclature", 1.5), ("nace", 2.5),
    ],
    "Development and Cooperation": [
        ("development cooperation", 3.0), ("development aid", 3.0),
        ("developing countries", 3.0), ("acp", 2.0), ("overseas", 2.0),
    ],
    "Neighbourhood and Enlargement": [
        ("enlargement", 3.0), ("neighbourhood", 3.0), ("candidate country", 3.0),
        ("accession", 3.0), ("pre-accession", 3.0), ("stabilisation", 2.0),
    ],
    "Human Rights and Democracy": [
        ("human rights", 3.0), ("democracy", 3.0), ("civil society", 2.0),
        ("fundamental freedom", 3.0), ("non-discrimination", 2.5), ("equality", 2.0),
    ],
    "Humanitarian Aid and Civil Protection": [
        ("humanitarian", 3.0), ("civil protection", 3.0), ("disaster", 2.0),
        ("emergency", 2.0), ("relief", 2.0),
    ],
    "Budget and Financial Management": [
        ("budget", 3.0), ("budgetary", 3.0), ("financial regulation", 3.0),
        ("revenue", 2.0), ("expenditure", 2.0), ("own resources", 3.0),
        ("multiannual financial framework", 3.0), ("appropriation", 2.0),
        ("court of auditors", 3.0), ("discharge", 2.0),
    ],
    "Institutional Affairs": [
        ("institutional", 2.5), ("interinstitutional", 3.0), ("staff regulation", 3.0),
        ("official", 1.5), ("seat", 1.5), ("protocol", 1.0),
        ("privileges and immunities", 3.0), ("rules of procedure", 3.0),
    ],
}

# -----------------------------------------------------------------
# Strategy 2: Institution -> Policy area mapping
# -----------------------------------------------------------------
INSTITUTION_MAP: Dict[str, str] = {
    "THE EUROPEAN CENTRAL BANK": "Economic and Financial Affairs",
    "THE COURT OF AUDITORS": "Budget and Financial Management",
    "THE COMMITTEE OF THE REGIONS": "Regional Policy",
    "THE EUROPEAN COURT OF AUDITORS": "Budget and Financial Management",
}

# Preamble domain keywords (catch terms the title might not have)
PREAMBLE_DOMAIN_KEYWORDS: Dict[str, List[str]] = {
    "Economic and Financial Affairs": [
        "prudential supervision", "credit institution", "financial stability",
        "bank recovery", "resolution mechanism",
    ],
    "Justice and Fundamental Rights": [
        "judicial cooperation in criminal matters",
        "european arrest warrant", "mutual recognition of judgments",
    ],
    "Migration and Home Affairs": [
        "area of freedom, security and justice",
        "border management", "smart borders",
    ],
    "Foreign and Security Policy": [
        "common foreign and security policy",
        "restrictive measures", "arms embargo",
    ],
    "Agriculture": [
        "common organisation of the markets", "common market organisation",
        "agricultural product",
    ],
    "Maritime Affairs and Fisheries": [
        "common fisheries policy", "total allowable catches",
    ],
    "Energy": [
        "euratom", "nuclear safety", "radioactive waste",
    ],
}


# -----------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------

def _extract_citation_refs(citations: Optional[List[str]]) -> List[str]:
    """
    Extract short reference patterns from citation strings.
    E.g. "Regulation (EU) 2016/679" -> "2016/679"
    """
    if not citations:
        return []
    refs = []
    pattern = re.compile(r'(\d{4}/\d{1,5})')
    for cite in citations:
        for match in pattern.findall(str(cite)):
            refs.append(match)
    return refs


def _score_title_keywords(title: str, threshold: float = 0.1) -> Optional[Tuple[str, float]]:
    """
    Score a title against AGGRESSIVE_KEYWORDS. Return (area, score) or None.
    """
    title_lower = title.lower()
    scores: Dict[str, float] = {}

    for area, keywords in AGGRESSIVE_KEYWORDS.items():
        total = 0.0
        for kw, weight in keywords:
            count = title_lower.count(kw)
            if count > 0:
                total += weight * min(count, 3)
        if total > 0:
            scores[area] = total

    if not scores:
        return None

    best_area = max(scores, key=scores.get)
    best_score = scores[best_area]

    # Normalise to 0-1 range (rough: max realistic score ~ 20)
    confidence = min(best_score / 20.0, 1.0)
    if confidence < threshold:
        return None

    return (best_area, confidence)


def _parse_xml_preamble(xml_path: str) -> Tuple[Optional[str], str]:
    """
    Parse XML for institution name and first recital text.
    Returns (institution_name_or_None, first_recital_text).
    """
    institution = None
    first_recital = ""

    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Look for PREAMBLE.INIT (may have namespace)
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

            if tag == "PREAMBLE.INIT":
                text = "".join(elem.itertext()).strip()
                if text:
                    institution = text.upper()
                break

        # Look for AUTHOR element
        if not institution:
            for elem in root.iter():
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "AUTHOR":
                    text = (elem.text or "").strip()
                    if text:
                        institution = text.upper()
                    break

        # Get first recital/GR.VISA text for domain keyword scanning
        recital_texts = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag in ("GR.CONSID", "CONSID", "GR.VISA", "VISA"):
                text = "".join(elem.itertext()).strip()
                if text:
                    recital_texts.append(text)
                if len(recital_texts) >= 3:
                    break

        first_recital = " ".join(recital_texts)

    except ET.ParseError:
        pass
    except Exception:
        pass

    return institution, first_recital


# -----------------------------------------------------------------
# Strategy runners
# -----------------------------------------------------------------

def run_strategy_1(session, unclassified: List[EULaw], verbose: bool, dry_run: bool) -> Dict[str, int]:
    """Citation network propagation."""
    logger.info("[INFO] Strategy 1: Citation network propagation")

    # Build a lookup: reference string -> policy_area
    # We search classified laws for common ref patterns in their title
    classified = session.query(EULaw.title, EULaw.policy_area).filter(
        EULaw.policy_area.isnot(None),
        EULaw.is_primary_legislation == True,
    ).all()

    ref_to_area: Dict[str, str] = {}
    ref_pattern = re.compile(r'(\d{4}/\d{1,5})')
    for title, area in classified:
        for match in ref_pattern.findall(title):
            # Only store if consistent (first wins -- majority would be better but this is fast)
            if match not in ref_to_area:
                ref_to_area[match] = area

    logger.info(f"[INFO] Built reference lookup with {len(ref_to_area)} entries")

    stats: Dict[str, int] = {}
    total = 0

    for i, law in enumerate(unclassified):
        citation_refs = _extract_citation_refs(law.citations)
        if not citation_refs:
            continue

        area_counts: Counter = Counter()
        for ref in citation_refs:
            if ref in ref_to_area:
                area_counts[ref_to_area[ref]] += 1

        if not area_counts:
            continue

        best_area, best_count = area_counts.most_common(1)[0]

        # Need 3+ matching citations, or 2 if no rival
        assign = False
        if best_count >= 3:
            assign = True
        elif best_count == 2:
            # Check that no other area also has 2
            if len([c for _, c in area_counts.most_common() if c >= 2]) == 1:
                assign = True

        if assign:
            if verbose:
                logger.info(f"  [OK] S1: {law.celex or law.uuid} -> {best_area} ({best_count} citations)")
            if not dry_run:
                law.policy_area = best_area
            stats[best_area] = stats.get(best_area, 0) + 1
            total += 1

        # Batch commit
        if not dry_run and total > 0 and total % BATCH_SIZE == 0:
            session.commit()
            logger.info(f"[INFO] S1 committed batch ({total} so far)")

    if not dry_run and total > 0:
        session.commit()

    logger.info(f"[OK] Strategy 1 classified {total} laws")
    return stats


def run_strategy_2(session, unclassified: List[EULaw], verbose: bool, dry_run: bool) -> Dict[str, int]:
    """Preamble/institution heuristic + domain keywords."""
    logger.info("[INFO] Strategy 2: Preamble/institution heuristic")

    stats: Dict[str, int] = {}
    total = 0
    skipped_no_file = 0

    for law in unclassified:
        # Skip already classified (by Strategy 1)
        if law.policy_area is not None:
            continue

        xml_path = law.xml_path
        if xml_path and not os.path.isabs(xml_path):
            xml_path = os.path.join(PROJECT_ROOT, xml_path)
        if not xml_path or not os.path.exists(xml_path):
            skipped_no_file += 1
            continue

        institution, recital_text = _parse_xml_preamble(xml_path)

        assigned_area = None

        # Check institution mapping
        if institution:
            for inst_key, area in INSTITUTION_MAP.items():
                if inst_key in institution:
                    assigned_area = area
                    break

        # If no institution match, check recital domain keywords
        if not assigned_area and recital_text:
            recital_lower = recital_text.lower()
            best_match = None
            best_count = 0
            for area, kw_list in PREAMBLE_DOMAIN_KEYWORDS.items():
                count = sum(1 for kw in kw_list if kw in recital_lower)
                if count > best_count:
                    best_count = count
                    best_match = area
            if best_count >= 1:
                assigned_area = best_match

        if assigned_area:
            if verbose:
                logger.info(f"  [OK] S2: {law.celex or law.uuid} -> {assigned_area}")
            if not dry_run:
                law.policy_area = assigned_area
            stats[assigned_area] = stats.get(assigned_area, 0) + 1
            total += 1

            if not dry_run and total > 0 and total % BATCH_SIZE == 0:
                session.commit()
                logger.info(f"[INFO] S2 committed batch ({total} so far)")

    if skipped_no_file > 0:
        logger.info(f"[WARN] S2 skipped {skipped_no_file} laws (xml_path not found on disk)")

    if not dry_run and total > 0:
        session.commit()

    logger.info(f"[OK] Strategy 2 classified {total} laws")
    return stats


def run_strategy_3(session, unclassified: List[EULaw], verbose: bool, dry_run: bool) -> Dict[str, int]:
    """Aggressive title keyword scan with low threshold."""
    logger.info("[INFO] Strategy 3: Aggressive title keyword scan (threshold=0.1)")

    stats: Dict[str, int] = {}
    total = 0

    for law in unclassified:
        if law.policy_area is not None:
            continue

        result = _score_title_keywords(law.title, threshold=0.1)
        if result:
            area, confidence = result
            if verbose:
                logger.info(f"  [OK] S3: {law.celex or law.uuid} -> {area} (conf={confidence:.2f})")
            if not dry_run:
                law.policy_area = area
            stats[area] = stats.get(area, 0) + 1
            total += 1

            if not dry_run and total > 0 and total % BATCH_SIZE == 0:
                session.commit()
                logger.info(f"[INFO] S3 committed batch ({total} so far)")

    if not dry_run and total > 0:
        session.commit()

    logger.info(f"[OK] Strategy 3 classified {total} laws")
    return stats


# -----------------------------------------------------------------
# Main
# -----------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Final classification push for eu_laws table")
    parser.add_argument("--dry-run", action="store_true", help="Do not write to database")
    parser.add_argument("--verbose", action="store_true", help="Print each classification")
    parser.add_argument("--strategy", default="all", choices=["1", "2", "3", "all"],
                        help="Which strategy to run (default: all)")
    args = parser.parse_args()

    if args.dry_run:
        logger.info("[INFO] DRY RUN -- no database writes")

    session = SessionLocal()

    try:
        # Count initial state
        total_primary = session.query(EULaw).filter(EULaw.is_primary_legislation == True).count()
        initial_unclassified = session.query(EULaw).filter(
            EULaw.is_primary_legislation == True,
            EULaw.policy_area.is_(None),
        ).count()

        logger.info(f"[INFO] Total primary laws: {total_primary}")
        logger.info(f"[INFO] Unclassified at start: {initial_unclassified}")
        logger.info(f"[INFO] Already classified: {total_primary - initial_unclassified}")

        # Fetch all unclassified (we re-check policy_area in each strategy for those set by prior strategy)
        unclassified = session.query(EULaw).filter(
            EULaw.is_primary_legislation == True,
            EULaw.policy_area.is_(None),
        ).all()

        logger.info(f"[INFO] Loaded {len(unclassified)} unclassified laws into memory")

        all_stats: Dict[str, Dict[str, int]] = {}

        # Run strategies in order
        strategies = {
            "1": ("Citation Network", run_strategy_1),
            "2": ("Preamble/Institution", run_strategy_2),
            "3": ("Aggressive Keywords", run_strategy_3),
        }

        run_list = ["1", "2", "3"] if args.strategy == "all" else [args.strategy]

        for s_num in run_list:
            name, func = strategies[s_num]
            logger.info(f"\n{'='*60}")
            logger.info(f"[START] Strategy {s_num}: {name}")
            logger.info(f"{'='*60}")
            stats = func(session, unclassified, args.verbose, args.dry_run)
            all_stats[f"S{s_num} ({name})"] = stats

        # Final counts
        if args.dry_run:
            # In dry run, count how many still have None
            remaining = sum(1 for law in unclassified if law.policy_area is None)
        else:
            remaining = session.query(EULaw).filter(
                EULaw.is_primary_legislation == True,
                EULaw.policy_area.is_(None),
            ).count()

        classified_this_run = initial_unclassified - remaining

        # Print per-strategy breakdown
        logger.info(f"\n{'='*60}")
        logger.info("[INFO] CLASSIFICATION SUMMARY")
        logger.info(f"{'='*60}")

        for strategy_name, stats in all_stats.items():
            strategy_total = sum(stats.values())
            logger.info(f"\n{strategy_name}: {strategy_total} laws")
            if stats:
                for area in sorted(stats.keys()):
                    logger.info(f"  {area}: {stats[area]}")

        logger.info(f"\n{'='*60}")
        logger.info(f"[INFO] Total classified this run: {classified_this_run}")
        logger.info(f"[INFO] Remaining unclassified: {remaining}")
        if initial_unclassified > 0:
            pct = (classified_this_run / initial_unclassified) * 100
            logger.info(f"[INFO] Improvement: {pct:.1f}% of previously unclassified laws now classified")
            total_classified = total_primary - remaining
            coverage = (total_classified / total_primary) * 100 if total_primary else 0
            logger.info(f"[INFO] Overall coverage: {total_classified}/{total_primary} ({coverage:.1f}%)")
        logger.info(f"{'='*60}")

    except Exception as e:
        logger.error(f"[ERROR] {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
