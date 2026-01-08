"""
Hugging Face Tender Summarizer

Generates executive summaries of EU procurement tenders using BART.
Extracts key information for quick SME decision-making.

Usage:
    from backend.services.tenders.hf_tender_summarizer import summarize_tender

    summary = await summarize_tender(tender_dict)
    # {
    #     "one_liner": "IT services contract for DG DIGIT cloud migration",
    #     "what": "Cloud infrastructure and migration services",
    #     "who": "DG DIGIT, European Commission",
    #     "value": "€2-5 million estimated",
    #     "deadline": "January 15, 2025",
    #     "key_requirements": ["AWS/Azure certification", "GDPR compliance"],
    #     "award_focus": "70% quality, 30% price - focus on technical proposal"
    # }
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..ai.huggingface_service import get_huggingface_service

logger = logging.getLogger(__name__)


class TenderSummarizer:
    """
    Summarizes EU procurement tenders for quick review.

    Uses HuggingFace's BART model to generate concise summaries
    and extracts key information like requirements and deadlines.
    """

    def __init__(self):
        self._hf_service = None
        self._cache: Dict[str, Dict[str, Any]] = {}

    @property
    def hf_service(self):
        """Lazy load HuggingFace service."""
        if self._hf_service is None:
            self._hf_service = get_huggingface_service()
        return self._hf_service

    async def summarize(
        self,
        tender: Dict[str, Any],
        include_strategy: bool = True
    ) -> Dict[str, Any]:
        """
        Generate executive summary of a tender.

        Args:
            tender: Tender dictionary with title, description, etc.
            include_strategy: Include award criteria strategy advice

        Returns:
            Structured summary dictionary
        """
        tender_id = tender.get("publication_number") or str(tender.get("id"))

        # Check cache
        if tender_id and tender_id in self._cache:
            return self._cache[tender_id]

        # Build summary
        summary = {
            "tender_id": tender_id,
            "one_liner": await self._generate_one_liner(tender),
            "what": self._extract_what(tender),
            "who": self._extract_who(tender),
            "value": self._format_value(tender),
            "deadline": self._format_deadline(tender),
            "key_requirements": await self._extract_requirements(tender),
            "sme_assessment": self._assess_sme_fit(tender)
        }

        # Add award strategy if requested
        if include_strategy:
            summary["award_focus"] = self._format_award_strategy(tender)

        # Cache result
        if tender_id:
            self._cache[tender_id] = summary

        return summary

    async def _generate_one_liner(self, tender: Dict[str, Any]) -> str:
        """Generate a one-sentence summary."""
        title = tender.get("title", "")
        description = tender.get("description", "")

        if not description:
            return title[:150] if title else "No summary available"

        try:
            # Use BART to summarize
            text = f"{title}. {description[:1500]}"

            summary = await self.hf_service.summarize_text(
                text=text,
                max_length=80,
                min_length=20
            )

            return summary.strip() if summary else title[:150]

        except Exception as e:
            logger.warning(f"Summarization failed: {e}")
            return title[:150] if title else "Summary unavailable"

    def _extract_what(self, tender: Dict[str, Any]) -> str:
        """Extract what is being procured."""
        # Try to get from contract nature and CPV
        contract_nature = tender.get("contract_nature", "").replace("_", " ")
        cpv_main = tender.get("cpv_main", "")
        title = tender.get("title", "")

        parts = []

        if contract_nature:
            parts.append(contract_nature.title())

        if cpv_main:
            # Get CPV description from code
            cpv_desc = self._get_cpv_description(cpv_main)
            if cpv_desc:
                parts.append(cpv_desc)

        if not parts and title:
            # Extract key phrases from title
            parts.append(title[:100])

        return "; ".join(parts) if parts else "Details in tender documents"

    def _extract_who(self, tender: Dict[str, Any]) -> str:
        """Extract contracting authority information."""
        official_name = tender.get("official_name", "")
        country = tender.get("buyer_country", "")

        if official_name:
            if country:
                return f"{official_name} ({country})"
            return official_name

        return f"Contracting authority ({country})" if country else "Unknown"

    def _format_value(self, tender: Dict[str, Any]) -> str:
        """Format tender value for display."""
        value = tender.get("estimated_value")
        currency = tender.get("estimated_value_currency", "EUR")
        value_low = tender.get("value_range_low")
        value_high = tender.get("value_range_high")

        if value_low and value_high:
            return f"€{value_low:,.0f} - €{value_high:,.0f}"
        elif value:
            return f"€{value:,.0f} estimated"
        else:
            return "Value not disclosed"

    def _format_deadline(self, tender: Dict[str, Any]) -> str:
        """Format submission deadline."""
        deadline = tender.get("submission_deadline")

        if not deadline:
            return "Deadline not specified"

        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            except ValueError:
                return deadline

        if isinstance(deadline, datetime):
            # Calculate days remaining
            now = datetime.now(deadline.tzinfo) if deadline.tzinfo else datetime.utcnow()
            days_left = (deadline - now).days

            formatted = deadline.strftime("%B %d, %Y")

            if days_left < 0:
                return f"{formatted} (CLOSED)"
            elif days_left == 0:
                return f"{formatted} (TODAY!)"
            elif days_left <= 7:
                return f"{formatted} ({days_left} days left - URGENT)"
            elif days_left <= 30:
                return f"{formatted} ({days_left} days left)"
            else:
                return formatted

        return str(deadline)

    async def _extract_requirements(self, tender: Dict[str, Any]) -> List[str]:
        """Extract key requirements from tender."""
        requirements = []

        # Check selection criteria
        selection_criteria = tender.get("selection_criteria", {})
        if isinstance(selection_criteria, dict):
            for key, value in selection_criteria.items():
                if value:
                    requirements.append(f"{key}: {value}")

        # Check minimum requirements
        min_reqs = tender.get("minimum_requirements", {})
        if isinstance(min_reqs, dict):
            if min_reqs.get("turnover"):
                requirements.append(f"Min turnover: €{min_reqs['turnover']:,.0f}")
            if min_reqs.get("experience_years"):
                requirements.append(f"Experience: {min_reqs['experience_years']} years")

        # If no structured requirements, try to extract from description
        if not requirements and tender.get("description"):
            try:
                entities = await self.hf_service.extract_entities(
                    tender["description"][:2000]
                )
                # Look for requirement-like entities
                for entity in entities[:5]:
                    if entity.get("entity_group") in ["MISC", "ORG"]:
                        requirements.append(entity.get("word", ""))
            except Exception:
                pass

        # Limit to top 5 requirements
        return requirements[:5] if requirements else ["See tender documents for requirements"]

    def _assess_sme_fit(self, tender: Dict[str, Any]) -> Dict[str, Any]:
        """Quick SME suitability assessment."""
        sme_score = tender.get("sme_suitability_score", 50)
        value = tender.get("estimated_value")
        procedure = (tender.get("procedure_type") or "").lower()
        has_lots = tender.get("has_lots", False)

        # Determine rating
        if sme_score >= 70:
            rating = "Good fit"
            emoji = "✅"
        elif sme_score >= 50:
            rating = "Moderate fit"
            emoji = "⚠️"
        else:
            rating = "Challenging"
            emoji = "❌"

        # Collect reasons
        reasons = []

        if value:
            if value <= 500_000:
                reasons.append("Smaller contract value")
            elif value >= 5_000_000:
                reasons.append("Large contract - consider consortium")

        if "open" in procedure:
            reasons.append("Open procedure (accessible)")
        elif "restricted" in procedure:
            reasons.append("Restricted procedure (pre-qualification needed)")

        if has_lots:
            reasons.append("Multiple lots (partial bidding possible)")

        return {
            "score": sme_score,
            "rating": rating,
            "emoji": emoji,
            "reasons": reasons[:3]
        }

    def _format_award_strategy(self, tender: Dict[str, Any]) -> str:
        """Format award criteria strategy advice."""
        award_criteria = tender.get("award_criteria", {})

        if not award_criteria or not isinstance(award_criteria, dict):
            return "Award criteria not specified - review tender documents"

        # Extract weights
        quality = award_criteria.get("quality", 0)
        price = award_criteria.get("price", 0)
        cost = award_criteria.get("cost", 0)

        # Normalize
        total = quality + price + cost
        if total == 0:
            return "Award criteria weights not specified"

        if total != 100:
            quality = (quality / total) * 100
            price = (price / total) * 100
            cost = (cost / total) * 100

        # Generate strategy
        if quality >= 70:
            return f"{quality:.0f}% quality, {price:.0f}% price - Focus on technical excellence and methodology"
        elif price >= 70:
            return f"{quality:.0f}% quality, {price:.0f}% price - Price is critical, ensure competitive pricing"
        elif quality >= 50:
            return f"{quality:.0f}% quality, {price:.0f}% price - Balance quality with competitive pricing"
        else:
            return f"Mixed criteria ({quality:.0f}% quality, {price:.0f}% price) - Balanced approach recommended"

    def _get_cpv_description(self, cpv_code: str) -> Optional[str]:
        """Get CPV code description (basic mapping)."""
        cpv_map = {
            "72": "IT services",
            "48": "Software packages",
            "79": "Business services",
            "73": "Research and development",
            "80": "Education services",
            "85": "Health services",
            "90": "Environmental services",
            "71": "Engineering services",
            "45": "Construction work",
            "33": "Medical equipment",
            "50": "Repair and maintenance",
        }

        if cpv_code and len(cpv_code) >= 2:
            return cpv_map.get(cpv_code[:2])

        return None

    def clear_cache(self):
        """Clear the summary cache."""
        self._cache.clear()


# Global instance
_summarizer: Optional[TenderSummarizer] = None


def get_tender_summarizer() -> TenderSummarizer:
    """Get or create the global TenderSummarizer instance."""
    global _summarizer
    if _summarizer is None:
        _summarizer = TenderSummarizer()
    return _summarizer


# Convenience function
async def summarize_tender(
    tender: Dict[str, Any],
    include_strategy: bool = True
) -> Dict[str, Any]:
    """
    Generate executive summary of a tender.

    Example:
        >>> summary = await summarize_tender(tender_dict)
        >>> print(summary["one_liner"])
        "IT services contract for DG DIGIT cloud migration"

    Args:
        tender: Tender dictionary
        include_strategy: Include award criteria strategy

    Returns:
        Structured summary dictionary
    """
    summarizer = get_tender_summarizer()
    return await summarizer.summarize(tender, include_strategy)


async def summarize_tenders_batch(
    tenders: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Summarize multiple tenders.

    Args:
        tenders: List of tender dictionaries

    Returns:
        List of tender summaries
    """
    summarizer = get_tender_summarizer()
    summaries = []

    for tender in tenders:
        try:
            summary = await summarizer.summarize(tender)
            summaries.append(summary)
        except Exception as e:
            logger.error(f"Failed to summarize tender: {e}")
            summaries.append({
                "tender_id": tender.get("publication_number"),
                "error": str(e)
            })

    return summaries
