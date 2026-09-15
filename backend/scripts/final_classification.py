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
from backend.scripts.eu_law_policy_keywords import AGGRESSIVE_KEYWORDS  # noqa: E402

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
