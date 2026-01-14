"""
Hugging Face Award Criteria Explainer

AI-powered explanation of award criteria for bidding strategy.
Helps SMEs understand how to position their bids.

Usage:
    from services.tenders.hf_award_explainer import explain_award_criteria

    advice = await explain_award_criteria(tender_dict)
    # {
    #     "strategy": "quality_focused",
    #     "recommendation": "Focus bid narrative on technical excellence...",
    #     "quality_weight": 70,
    #     "price_weight": 30,
    #     "tips": [
    #         "Emphasize past performance and case studies",
    #         "Detail your methodology thoroughly",
    #         "Don't undercut price too aggressively"
    #     ]
    # }
"""

import logging
from typing import Dict, Any, Optional, List

from services.ai.huggingface_service import get_huggingface_service

logger = logging.getLogger(__name__)


# Common award criteria patterns
AWARD_STRATEGIES = {
    "quality_focused": {
        "threshold": 65,  # Quality >= 65%
        "description": "Quality is the primary evaluation factor",
        "general_tips": [
            "Focus your bid narrative on technical excellence and methodology",
            "Highlight team expertise, qualifications, and relevant experience",
            "Provide detailed case studies demonstrating past performance",
            "Price should be competitive but not the lowest",
            "Don't sacrifice quality commitments for lower price"
        ]
    },
    "price_focused": {
        "threshold": 65,  # Price >= 65%
        "description": "Price is the primary evaluation factor",
        "general_tips": [
            "Ensure your pricing is highly competitive",
            "Optimize costs without compromising minimum quality requirements",
            "Consider lean delivery models to reduce price",
            "Quality proposal should meet requirements, not exceed them",
            "Every euro matters in the evaluation"
        ]
    },
    "balanced": {
        "threshold": 40,  # Both between 40-60%
        "description": "Quality and price are equally important",
        "general_tips": [
            "Balance technical excellence with competitive pricing",
            "Neither sacrifice quality nor over-engineer",
            "Present clear value for money proposition",
            "Demonstrate efficiency in your methodology",
            "Competitive price + solid quality = winning combination"
        ]
    }
}


class AwardCriteriaExplainer:
    """
    AI-powered award criteria analysis for bidding strategy.

    Analyzes tender award criteria to provide:
    - Strategy classification (quality, price, or balanced focus)
    - Specific tips for bid preparation
    - Pricing positioning advice
    - Common pitfalls to avoid
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

    async def explain(
        self,
        tender: Dict[str, Any],
        include_ai_advice: bool = True
    ) -> Dict[str, Any]:
        """
        Explain award criteria and provide bidding strategy.

        Args:
            tender: Tender dictionary with award criteria
            include_ai_advice: Include AI-generated specific advice

        Returns:
            Strategy and tips dictionary
        """
        tender_id = tender.get("publication_number") or str(tender.get("id"))

        # Check cache
        if tender_id and tender_id in self._cache:
            return self._cache[tender_id]

        # Extract award criteria
        criteria = tender.get("award_criteria", {})
        criteria_type = tender.get("award_criteria_type", "")

        # Parse criteria weights
        quality_weight, price_weight = self._parse_criteria_weights(criteria, criteria_type)

        # Determine strategy
        strategy = self._determine_strategy(quality_weight, price_weight)

        # Build base explanation
        explanation = {
            "tender_id": tender_id,
            "quality_weight": quality_weight,
            "price_weight": price_weight,
            "other_weight": 100 - quality_weight - price_weight,
            "strategy": strategy["name"],
            "strategy_description": strategy["description"],
            "general_tips": strategy["tips"][:5],
            "price_positioning": self._get_price_positioning(quality_weight, price_weight),
            "common_mistakes": self._get_common_mistakes(strategy["name"]),
            "success_factors": self._get_success_factors(strategy["name"])
        }

        # Add AI-specific advice
        if include_ai_advice:
            try:
                ai_advice = await self._get_ai_advice(tender, strategy["name"], quality_weight, price_weight)
                explanation["ai_advice"] = ai_advice
            except Exception as e:
                logger.warning(f"AI advice generation failed: {e}")
                explanation["ai_advice"] = None

        # Generate final recommendation
        explanation["recommendation"] = self._generate_recommendation(explanation)

        # Cache result
        if tender_id:
            self._cache[tender_id] = explanation

        return explanation

    def _parse_criteria_weights(
        self,
        criteria: Dict[str, Any],
        criteria_type: str
    ) -> tuple:
        """Parse quality and price weights from criteria."""
        quality_weight = 0
        price_weight = 0

        if not criteria:
            # Default based on criteria type
            if "price" in criteria_type.lower():
                return 0, 100
            elif "quality" in criteria_type.lower():
                return 100, 0
            else:
                return 50, 50

        if isinstance(criteria, dict):
            # Try different field names
            quality_weight = (
                criteria.get("quality", 0) or
                criteria.get("technical", 0) or
                criteria.get("qualitative", 0)
            )
            price_weight = (
                criteria.get("price", 0) or
                criteria.get("cost", 0) or
                criteria.get("financial", 0)
            )

            # Handle percentage strings
            if isinstance(quality_weight, str):
                quality_weight = int(quality_weight.replace("%", "").strip())
            if isinstance(price_weight, str):
                price_weight = int(price_weight.replace("%", "").strip())

        # Normalize to 100 if needed
        total = quality_weight + price_weight
        if total > 0 and total != 100:
            factor = 100 / total
            quality_weight = round(quality_weight * factor)
            price_weight = round(price_weight * factor)

        # Default if still 0
        if quality_weight == 0 and price_weight == 0:
            quality_weight = 50
            price_weight = 50

        return quality_weight, price_weight

    def _determine_strategy(self, quality_weight: int, price_weight: int) -> Dict[str, Any]:
        """Determine the bidding strategy based on weights."""
        if quality_weight >= AWARD_STRATEGIES["quality_focused"]["threshold"]:
            return {
                "name": "quality_focused",
                "description": AWARD_STRATEGIES["quality_focused"]["description"],
                "tips": AWARD_STRATEGIES["quality_focused"]["general_tips"]
            }
        elif price_weight >= AWARD_STRATEGIES["price_focused"]["threshold"]:
            return {
                "name": "price_focused",
                "description": AWARD_STRATEGIES["price_focused"]["description"],
                "tips": AWARD_STRATEGIES["price_focused"]["general_tips"]
            }
        else:
            return {
                "name": "balanced",
                "description": AWARD_STRATEGIES["balanced"]["description"],
                "tips": AWARD_STRATEGIES["balanced"]["general_tips"]
            }

    def _get_price_positioning(self, quality_weight: int, price_weight: int) -> Dict[str, Any]:
        """Get price positioning advice."""
        if price_weight >= 70:
            return {
                "aggressiveness": "high",
                "advice": "Price is critical. Aim for the lowest compliant price.",
                "margin_guidance": "Minimize margins. Every euro counts in evaluation.",
                "risk": "Low price may signal quality concerns to evaluators"
            }
        elif price_weight >= 50:
            return {
                "aggressiveness": "medium",
                "advice": "Be competitive but not necessarily the cheapest.",
                "margin_guidance": "Market-rate pricing with modest discount.",
                "risk": "Being significantly above average will hurt you"
            }
        else:
            return {
                "aggressiveness": "low",
                "advice": "Price is secondary. Focus on demonstrating value.",
                "margin_guidance": "Standard margins acceptable. Invest in quality.",
                "risk": "Very high prices may still disqualify you"
            }

    def _get_common_mistakes(self, strategy: str) -> List[str]:
        """Get common mistakes for the strategy."""
        mistakes = {
            "quality_focused": [
                "Cutting corners on quality to lower price",
                "Generic technical proposals without specifics",
                "Underestimating the importance of references",
                "Poor formatting or presentation",
                "Missing the evaluators' key priorities"
            ],
            "price_focused": [
                "Pricing too high without justification",
                "Over-engineering the solution unnecessarily",
                "Ignoring cost optimization opportunities",
                "Assuming quality will compensate for price",
                "Hidden costs that surface during evaluation"
            ],
            "balanced": [
                "Failing to find the right quality-price balance",
                "Being mediocre on both dimensions",
                "Not clearly articulating value for money",
                "Inconsistency between price and quality claims",
                "Neglecting either dimension entirely"
            ]
        }
        return mistakes.get(strategy, mistakes["balanced"])

    def _get_success_factors(self, strategy: str) -> List[str]:
        """Get success factors for the strategy."""
        factors = {
            "quality_focused": [
                "Strong, relevant reference projects",
                "Clearly qualified and experienced team",
                "Innovative and well-thought methodology",
                "Understanding of buyer's specific needs",
                "Professional, well-structured proposal"
            ],
            "price_focused": [
                "Competitive pricing with clear breakdown",
                "Efficient delivery model",
                "Cost optimization without quality loss",
                "Transparent pricing with no hidden costs",
                "Meeting all technical requirements at minimum cost"
            ],
            "balanced": [
                "Best value for money proposition",
                "Good quality at competitive price",
                "Clear demonstration of efficiency",
                "Strong team without over-staffing",
                "Practical, realistic methodology"
            ]
        }
        return factors.get(strategy, factors["balanced"])

    async def _get_ai_advice(
        self,
        tender: Dict[str, Any],
        strategy: str,
        quality_weight: int,
        price_weight: int
    ) -> Dict[str, Any]:
        """Get AI-generated specific advice for this tender."""
        prompt = f"""You are an EU public procurement expert advising an SME on bid strategy.

Tender: {tender.get('title', 'Unknown')}
Award Criteria: {quality_weight}% quality, {price_weight}% price
Strategy: {strategy.replace('_', ' ')}
Procedure: {tender.get('procedure_type', 'Unknown')}
Value: €{tender.get('estimated_value', 0):,.0f}

Provide specific, actionable advice for winning this tender:

1. KEY FOCUS AREAS: What should the bidder emphasize most?
2. DIFFERENTIATORS: How to stand out from competition?
3. PRICING APPROACH: Specific pricing strategy for this criteria mix
4. RED FLAGS: What could disqualify or significantly hurt the bid?

Be concise and practical. Focus on actionable insights."""

        try:
            response = await self.hf_service.query_legal_llm(prompt, max_tokens=600)

            if not response:
                return None

            return {
                "raw_advice": response,
                "parsed": self._parse_ai_advice(response)
            }

        except Exception as e:
            logger.error(f"AI advice query failed: {e}")
            return None

    def _parse_ai_advice(self, response: str) -> Dict[str, Any]:
        """Parse AI advice into structured format."""
        parsed = {
            "focus_areas": [],
            "differentiators": [],
            "pricing_approach": "",
            "red_flags": []
        }

        current_section = None
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()
            upper = line.upper()

            if "FOCUS AREA" in upper or "KEY FOCUS" in upper:
                current_section = "focus_areas"
            elif "DIFFERENTIATOR" in upper:
                current_section = "differentiators"
            elif "PRICING" in upper:
                current_section = "pricing_approach"
            elif "RED FLAG" in upper:
                current_section = "red_flags"
            elif line.startswith("- ") or line.startswith("• "):
                item = line[2:].strip()
                if current_section in ["focus_areas", "differentiators", "red_flags"]:
                    parsed[current_section].append(item)
            elif current_section == "pricing_approach" and line:
                parsed["pricing_approach"] += " " + line

        parsed["pricing_approach"] = parsed["pricing_approach"].strip()

        return parsed

    def _generate_recommendation(self, explanation: Dict[str, Any]) -> str:
        """Generate final recommendation summary."""
        strategy = explanation["strategy"]
        quality = explanation["quality_weight"]
        price = explanation["price_weight"]

        rec = f"Award criteria: {quality}% quality, {price}% price. "

        if strategy == "quality_focused":
            rec += "Focus on demonstrating technical excellence, team expertise, and methodology. "
            rec += "Price should be competitive but not your main selling point. "
        elif strategy == "price_focused":
            rec += "Price is the primary factor. Ensure your pricing is highly competitive. "
            rec += "Meet quality requirements but don't over-engineer. "
        else:
            rec += "Balance quality and price in your proposal. "
            rec += "Demonstrate clear value for money. "

        rec += f"Key success factor: {explanation['success_factors'][0] if explanation['success_factors'] else 'Strong overall proposal'}."

        return rec

    def clear_cache(self):
        """Clear the explanation cache."""
        self._cache.clear()


# Global instance
_explainer: Optional[AwardCriteriaExplainer] = None


def get_award_explainer() -> AwardCriteriaExplainer:
    """Get or create the global AwardCriteriaExplainer instance."""
    global _explainer
    if _explainer is None:
        _explainer = AwardCriteriaExplainer()
    return _explainer


# Convenience function
async def explain_award_criteria(
    tender: Dict[str, Any],
    include_ai_advice: bool = True
) -> Dict[str, Any]:
    """
    Explain award criteria and provide bidding strategy.

    Example:
        >>> advice = await explain_award_criteria(tender_dict)
        >>> print(advice["strategy"])
        "quality_focused"
        >>> print(advice["recommendation"])
        "Focus on demonstrating technical excellence..."

    Args:
        tender: Tender dictionary with award criteria
        include_ai_advice: Include AI-generated specific advice

    Returns:
        Strategy and tips dictionary
    """
    explainer = get_award_explainer()
    return await explainer.explain(tender, include_ai_advice)


def get_strategy_for_weights(quality: int, price: int) -> str:
    """
    Quick strategy determination without full analysis.

    Args:
        quality: Quality weight percentage
        price: Price weight percentage

    Returns:
        Strategy name
    """
    if quality >= 65:
        return "quality_focused"
    elif price >= 65:
        return "price_focused"
    else:
        return "balanced"
