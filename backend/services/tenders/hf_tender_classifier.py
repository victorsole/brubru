"""
Hugging Face Tender Classifier

Zero-shot classification of tenders into business sectors.
Uses BART-large-MNLI for classification aligned with CPV divisions.

Usage:
    from services.tenders.hf_tender_classifier import classify_tender_sector

    sectors = await classify_tender_sector(
        "Cloud Infrastructure Services",
        "Provision of cloud computing services for EU institutions..."
    )
    # [{"label": "IT and Digital Services", "score": 0.94}, ...]
"""

import logging
from typing import List, Dict, Any, Optional
from functools import lru_cache

from services.ai.huggingface_service import get_huggingface_service

logger = logging.getLogger(__name__)


# Tender sectors aligned with CPV top-level divisions
# CPV structure: first 2 digits = division
TENDER_SECTORS = [
    "IT and Digital Services",          # 72xxx - IT services, 48xxx - Software
    "Construction and Engineering",      # 45xxx - Construction, 71xxx - Engineering
    "Healthcare and Medical",            # 33xxx - Medical equipment, 85xxx - Health
    "Environmental Services",            # 90xxx - Sewage, waste, cleaning
    "Research and Development",          # 73xxx - R&D services
    "Training and Education",            # 80xxx - Education services
    "Legal and Consulting Services",     # 79xxx - Business services
    "Transport and Logistics",           # 60xxx - Transport, 63xxx - Logistics
    "Energy and Utilities",              # 09xxx - Petroleum, 65xxx - Utilities
    "Communication and Marketing",       # 79xxx - Advertising, 64xxx - Telecom
    "Food and Agriculture",              # 03xxx - Agriculture, 15xxx - Food
    "Security and Defense",              # 35xxx - Security, fire equipment
    "Financial Services",                # 66xxx - Financial, insurance
    "Office and Furniture",              # 39xxx - Furniture, 30xxx - Office equipment
    "Textiles and Clothing",             # 18xxx - Clothing, 19xxx - Leather
]

# CPV code to sector mapping (first 2 digits)
CPV_TO_SECTOR = {
    "03": "Food and Agriculture",
    "09": "Energy and Utilities",
    "14": "Construction and Engineering",
    "15": "Food and Agriculture",
    "16": "Food and Agriculture",
    "18": "Textiles and Clothing",
    "19": "Textiles and Clothing",
    "22": "Communication and Marketing",
    "24": "Healthcare and Medical",
    "30": "Office and Furniture",
    "31": "IT and Digital Services",
    "32": "IT and Digital Services",
    "33": "Healthcare and Medical",
    "34": "Transport and Logistics",
    "35": "Security and Defense",
    "37": "Training and Education",
    "38": "Research and Development",
    "39": "Office and Furniture",
    "42": "Construction and Engineering",
    "43": "Construction and Engineering",
    "44": "Construction and Engineering",
    "45": "Construction and Engineering",
    "48": "IT and Digital Services",
    "50": "Transport and Logistics",
    "51": "Construction and Engineering",
    "55": "Food and Agriculture",
    "60": "Transport and Logistics",
    "63": "Transport and Logistics",
    "64": "Communication and Marketing",
    "65": "Energy and Utilities",
    "66": "Financial Services",
    "70": "Legal and Consulting Services",
    "71": "Construction and Engineering",
    "72": "IT and Digital Services",
    "73": "Research and Development",
    "75": "Legal and Consulting Services",
    "76": "Energy and Utilities",
    "77": "Environmental Services",
    "79": "Legal and Consulting Services",
    "80": "Training and Education",
    "85": "Healthcare and Medical",
    "90": "Environmental Services",
    "92": "Communication and Marketing",
    "98": "Legal and Consulting Services",
}


class TenderClassifier:
    """
    Zero-shot classifier for tender sectors.

    Uses HuggingFace's BART-large-MNLI model for classification
    with caching to avoid repeated API calls.
    """

    def __init__(self, cache_size: int = 1000):
        """
        Initialize the classifier.

        Args:
            cache_size: Maximum number of cached classifications
        """
        self._hf_service = None
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
        self._cache_size = cache_size

    @property
    def hf_service(self):
        """Lazy load HuggingFace service."""
        if self._hf_service is None:
            self._hf_service = get_huggingface_service()
        return self._hf_service

    def _get_cache_key(self, title: str, description: str) -> str:
        """Generate cache key from input text."""
        text = f"{title}|{description[:200] if description else ''}"
        return text.lower().strip()

    async def classify(
        self,
        title: str,
        description: Optional[str] = None,
        cpv_code: Optional[str] = None,
        top_k: int = 3,
        threshold: float = 0.1
    ) -> List[Dict[str, Any]]:
        """
        Classify a tender into business sectors.

        Args:
            title: Tender title
            description: Tender description (optional but recommended)
            cpv_code: CPV code for validation (optional)
            top_k: Number of top sectors to return
            threshold: Minimum confidence threshold

        Returns:
            List of sector classifications with scores, e.g.:
            [{"label": "IT and Digital Services", "score": 0.94}, ...]
        """
        # Check cache
        cache_key = self._get_cache_key(title, description or "")
        if cache_key in self._cache:
            logger.debug("Returning cached classification")
            return self._cache[cache_key][:top_k]

        # If CPV code provided, use it as hint
        cpv_sector = None
        if cpv_code and len(cpv_code) >= 2:
            cpv_prefix = cpv_code[:2]
            cpv_sector = CPV_TO_SECTOR.get(cpv_prefix)

        # Prepare text for classification
        text = title
        if description:
            # Use first 500 chars of description
            text = f"{title}. {description[:500]}"

        try:
            # Use HuggingFace zero-shot classification
            results = await self.hf_service.classify_policy_area(
                text=text,
                candidate_labels=TENDER_SECTORS,
                multi_label=True
            )

            if not results:
                # Fallback to CPV-based classification
                if cpv_sector:
                    return [{"label": cpv_sector, "score": 0.8}]
                return []

            # Filter by threshold and sort by score
            filtered = [
                {"label": r["label"], "score": r["score"]}
                for r in results
                if r["score"] >= threshold
            ]
            filtered.sort(key=lambda x: x["score"], reverse=True)

            # Boost CPV-matching sector if present
            if cpv_sector:
                for item in filtered:
                    if item["label"] == cpv_sector:
                        item["score"] = min(1.0, item["score"] * 1.2)
                        item["cpv_matched"] = True
                filtered.sort(key=lambda x: x["score"], reverse=True)

            # Cache result
            self._add_to_cache(cache_key, filtered)

            return filtered[:top_k]

        except Exception as e:
            logger.error(f"Classification failed: {e}")

            # Fallback to CPV-based classification
            if cpv_sector:
                return [{"label": cpv_sector, "score": 0.7, "fallback": True}]

            return []

    def classify_by_cpv(self, cpv_code: str) -> Optional[str]:
        """
        Get sector from CPV code directly (no AI).

        Args:
            cpv_code: CPV code (at least 2 digits)

        Returns:
            Sector name or None
        """
        if not cpv_code or len(cpv_code) < 2:
            return None

        return CPV_TO_SECTOR.get(cpv_code[:2])

    def _add_to_cache(self, key: str, value: List[Dict[str, Any]]):
        """Add to cache with size limit."""
        if len(self._cache) >= self._cache_size:
            # Remove oldest entry (simple LRU)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = value

    def clear_cache(self):
        """Clear the classification cache."""
        self._cache.clear()

    def get_all_sectors(self) -> List[str]:
        """Get list of all tender sectors."""
        return TENDER_SECTORS.copy()

    def get_cpv_mapping(self) -> Dict[str, str]:
        """Get CPV code to sector mapping."""
        return CPV_TO_SECTOR.copy()


# Global instance
_classifier: Optional[TenderClassifier] = None


def get_tender_classifier() -> TenderClassifier:
    """Get or create the global TenderClassifier instance."""
    global _classifier
    if _classifier is None:
        _classifier = TenderClassifier()
    return _classifier


# Convenience functions
async def classify_tender_sector(
    title: str,
    description: Optional[str] = None,
    cpv_code: Optional[str] = None,
    top_k: int = 3
) -> List[Dict[str, Any]]:
    """
    Classify a tender into business sectors.

    Example:
        >>> sectors = await classify_tender_sector(
        ...     "Cloud Infrastructure Services",
        ...     "Provision of cloud computing services for EU institutions..."
        ... )
        >>> print(sectors[0])
        {"label": "IT and Digital Services", "score": 0.94}

    Args:
        title: Tender title
        description: Tender description
        cpv_code: Optional CPV code for validation
        top_k: Number of top results

    Returns:
        List of sector classifications with scores
    """
    classifier = get_tender_classifier()
    return await classifier.classify(title, description, cpv_code, top_k)


def get_sector_from_cpv(cpv_code: str) -> Optional[str]:
    """
    Get sector directly from CPV code (no AI).

    Args:
        cpv_code: CPV code

    Returns:
        Sector name or None
    """
    classifier = get_tender_classifier()
    return classifier.classify_by_cpv(cpv_code)


async def classify_tenders_batch(
    tenders: List[Dict[str, Any]],
    top_k: int = 1
) -> List[Dict[str, Any]]:
    """
    Classify multiple tenders.

    Args:
        tenders: List of tender dicts with title, description, cpv_code
        top_k: Number of top sectors per tender

    Returns:
        List of tenders with added 'sectors' field
    """
    classifier = get_tender_classifier()

    results = []
    for tender in tenders:
        sectors = await classifier.classify(
            title=tender.get("title", ""),
            description=tender.get("description"),
            cpv_code=tender.get("cpv_main") or tender.get("cpv_code"),
            top_k=top_k
        )

        tender_result = tender.copy()
        tender_result["sectors"] = sectors
        tender_result["primary_sector"] = sectors[0]["label"] if sectors else None
        results.append(tender_result)

    return results
