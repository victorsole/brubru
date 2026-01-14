"""
Hugging Face SME Analyzer

AI-powered analysis of tender suitability for SMEs.
Uses Legal LLM (Saul-7B) to analyze requirements and identify barriers/opportunities.

Usage:
    from backend.services.tenders.hf_sme_analyzer import analyze_sme_suitability

    analysis = await analyze_sme_suitability(tender_dict)
    # {
    #     "sme_friendly_score": 0.75,
    #     "barriers": ["High turnover requirement", "5+ years experience needed"],
    #     "opportunities": ["Multiple lots available", "Open procedure"],
    #     "recommendation": "Suitable for medium-sized enterprises...",
    #     "consortium_suggestion": True
    # }
"""

import logging
import json
import re
from typing import Dict, Any, Optional, List

from services.ai.huggingface_service import get_huggingface_service

logger = logging.getLogger(__name__)


class SMEAnalyzer:
    """
    AI-powered SME suitability analyzer for EU tenders.

    Uses HuggingFace's Legal LLM to:
    - Identify barriers for SMEs
    - Find opportunities (lot division, simplified procedures)
    - Calculate SME suitability score
    - Recommend consortium formation
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

    async def analyze(
        self,
        tender: Dict[str, Any],
        company_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Analyze tender for SME suitability.

        Args:
            tender: Tender dictionary with full details
            company_profile: Optional company info for personalized analysis

        Returns:
            Analysis dictionary with score, barriers, opportunities, recommendations
        """
        tender_id = tender.get("publication_number") or str(tender.get("id"))

        # Check cache
        cache_key = f"{tender_id}:{json.dumps(company_profile or {}, sort_keys=True)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Build analysis
        analysis = {
            "tender_id": tender_id,
            "barriers": [],
            "opportunities": [],
            "risks": [],
            "recommendations": []
        }

        # Rule-based analysis (fast, no API)
        rule_analysis = self._rule_based_analysis(tender, company_profile)
        analysis["barriers"].extend(rule_analysis["barriers"])
        analysis["opportunities"].extend(rule_analysis["opportunities"])
        analysis["risks"].extend(rule_analysis["risks"])

        # AI-powered deep analysis
        try:
            ai_analysis = await self._ai_analysis(tender, company_profile)
            analysis["barriers"].extend(ai_analysis.get("barriers", []))
            analysis["opportunities"].extend(ai_analysis.get("opportunities", []))
            analysis["recommendations"].extend(ai_analysis.get("recommendations", []))
            analysis["ai_summary"] = ai_analysis.get("summary", "")
        except Exception as e:
            logger.warning(f"AI analysis failed, using rule-based only: {e}")
            analysis["ai_summary"] = "AI analysis unavailable"

        # Calculate final score
        analysis["sme_friendly_score"] = self._calculate_score(analysis, tender)

        # Consortium suggestion
        analysis["consortium_suggestion"] = self._should_suggest_consortium(analysis, tender)

        # Final recommendation
        analysis["recommendation"] = self._generate_recommendation(analysis, tender, company_profile)

        # Remove duplicates
        analysis["barriers"] = list(dict.fromkeys(analysis["barriers"]))
        analysis["opportunities"] = list(dict.fromkeys(analysis["opportunities"]))
        analysis["risks"] = list(dict.fromkeys(analysis["risks"]))

        # Cache result
        self._cache[cache_key] = analysis

        return analysis

    def _rule_based_analysis(
        self,
        tender: Dict[str, Any],
        company_profile: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Fast rule-based analysis without AI."""
        barriers = []
        opportunities = []
        risks = []

        value = tender.get("estimated_value")
        procedure = (tender.get("procedure_type") or "").lower()
        has_lots = tender.get("has_lots", False)
        lot_count = tender.get("lot_count", 0)
        min_reqs = tender.get("minimum_requirements", {})

        # Value-based analysis
        if value:
            if value > 5_000_000:
                barriers.append(f"High contract value (€{value:,.0f}) - significant financial capacity needed")
            elif value > 1_000_000:
                risks.append("Medium-sized contract may require substantial resources")
            else:
                opportunities.append("Contract value within typical SME capacity")

            # Check against company profile
            if company_profile:
                turnover = company_profile.get("annual_turnover", 0)
                if turnover and value > turnover * 0.5:
                    barriers.append("Contract value exceeds 50% of annual turnover")

        # Procedure type analysis
        if "open" in procedure:
            opportunities.append("Open procedure - accessible to all economic operators")
        elif "restricted" in procedure:
            barriers.append("Restricted procedure - pre-qualification phase required")
            risks.append("May require references similar to the contract")
        elif "negotiated" in procedure:
            barriers.append("Negotiated procedure - typically requires existing relationship")
        elif "competitive" in procedure and "dialogue" in procedure:
            barriers.append("Competitive dialogue - resource-intensive participation")

        # Lots analysis
        if has_lots and lot_count and lot_count > 1:
            opportunities.append(f"{lot_count} lots available - partial bidding possible")
            opportunities.append("Lot division allows specialized SMEs to participate")
        elif not has_lots:
            risks.append("Single contract - no partial bidding option")

        # Minimum requirements
        if isinstance(min_reqs, dict):
            turnover_req = min_reqs.get("turnover", 0)
            if turnover_req:
                if turnover_req > 1_000_000:
                    barriers.append(f"Minimum turnover requirement: €{turnover_req:,.0f}")
                if company_profile and company_profile.get("annual_turnover", 0) < turnover_req:
                    barriers.append("Company turnover below minimum requirement")

            experience_req = min_reqs.get("experience_years", 0)
            if experience_req >= 5:
                barriers.append(f"Requires {experience_req}+ years of experience")
            elif experience_req >= 3:
                risks.append(f"Requires {experience_req}+ years of experience")

        # Framework agreement check
        if tender.get("is_framework"):
            barriers.append("Framework agreement - may favor established suppliers")
            risks.append("Framework agreements typically have long durations")

        # Joint procurement check
        if tender.get("is_joint_procurement"):
            barriers.append("Joint procurement - complex buyer requirements")

        return {
            "barriers": barriers,
            "opportunities": opportunities,
            "risks": risks
        }

    async def _ai_analysis(
        self,
        tender: Dict[str, Any],
        company_profile: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """AI-powered deep analysis using Legal LLM."""
        # Build prompt
        tender_info = f"""
Tender: {tender.get('title', 'Unknown')}
Value: €{tender.get('estimated_value', 'Unknown'):,.0f}
Procedure: {tender.get('procedure_type', 'Unknown')}
Country: {tender.get('buyer_country', 'Unknown')}
Lots: {tender.get('lot_count', 1) if tender.get('has_lots') else 'No lots'}
Description: {tender.get('description', '')[:800]}
"""

        company_info = ""
        if company_profile:
            company_info = f"""
Company Profile:
- Size: {company_profile.get('size', 'Unknown')}
- Turnover: €{company_profile.get('annual_turnover', 0):,.0f}
- Employees: {company_profile.get('employees', 'Unknown')}
- Experience: {company_profile.get('experience_years', 'Unknown')} years
"""

        prompt = f"""You are an EU public procurement expert analyzing tender suitability for SMEs.

{tender_info}
{company_info}

Analyze this tender for SME (Small/Medium Enterprise) suitability. Provide:

1. BARRIERS: List specific obstacles for SMEs (financial requirements, experience, certifications, etc.)
2. OPPORTUNITIES: List advantages for SMEs (lot division, simplified procedures, SME set-asides)
3. RECOMMENDATIONS: Specific advice for an SME considering this tender

Be concise and specific. Focus on actionable insights.

Format your response as:
BARRIERS:
- barrier 1
- barrier 2

OPPORTUNITIES:
- opportunity 1
- opportunity 2

RECOMMENDATIONS:
- recommendation 1
- recommendation 2

SUMMARY: One paragraph overall assessment."""

        try:
            response = await self.hf_service.query_legal_llm(prompt, max_tokens=800)

            if not response:
                return {}

            return self._parse_ai_response(response)

        except Exception as e:
            logger.error(f"Legal LLM query failed: {e}")
            return {}

    def _parse_ai_response(self, response: str) -> Dict[str, Any]:
        """Parse structured AI response."""
        result = {
            "barriers": [],
            "opportunities": [],
            "recommendations": [],
            "summary": ""
        }

        current_section = None
        lines = response.strip().split("\n")

        for line in lines:
            line = line.strip()

            if line.upper().startswith("BARRIERS:"):
                current_section = "barriers"
            elif line.upper().startswith("OPPORTUNITIES:"):
                current_section = "opportunities"
            elif line.upper().startswith("RECOMMENDATIONS:"):
                current_section = "recommendations"
            elif line.upper().startswith("SUMMARY:"):
                current_section = "summary"
                summary_text = line.replace("SUMMARY:", "").strip()
                if summary_text:
                    result["summary"] = summary_text
            elif line.startswith("- ") and current_section in ["barriers", "opportunities", "recommendations"]:
                item = line[2:].strip()
                if item and len(item) > 5:  # Filter out very short items
                    result[current_section].append(item)
            elif current_section == "summary" and line:
                result["summary"] += " " + line

        result["summary"] = result["summary"].strip()

        return result

    def _calculate_score(self, analysis: Dict[str, Any], tender: Dict[str, Any]) -> float:
        """Calculate overall SME-friendliness score (0-1)."""
        score = 0.5  # Start neutral

        # Existing SME score from tender service
        existing_score = tender.get("sme_suitability_score")
        if existing_score:
            score = existing_score / 100  # Normalize to 0-1

        # Adjust based on analysis
        barrier_count = len(analysis.get("barriers", []))
        opportunity_count = len(analysis.get("opportunities", []))

        # Each barrier reduces score, each opportunity increases it
        score -= barrier_count * 0.08
        score += opportunity_count * 0.06

        # Clamp to 0-1
        score = max(0.0, min(1.0, score))

        return round(score, 2)

    def _should_suggest_consortium(
        self,
        analysis: Dict[str, Any],
        tender: Dict[str, Any]
    ) -> bool:
        """Determine if consortium formation should be suggested."""
        value = tender.get("estimated_value", 0)
        score = analysis.get("sme_friendly_score", 0.5)
        barrier_count = len(analysis.get("barriers", []))

        # Suggest consortium for:
        # - High value contracts (> €1M)
        # - Low SME score (< 0.5)
        # - Multiple barriers (> 3)
        if value > 1_000_000:
            return True
        if score < 0.4:
            return True
        if barrier_count > 3:
            return True

        return False

    def _generate_recommendation(
        self,
        analysis: Dict[str, Any],
        tender: Dict[str, Any],
        company_profile: Optional[Dict[str, Any]]
    ) -> str:
        """Generate overall recommendation."""
        score = analysis.get("sme_friendly_score", 0.5)
        consortium = analysis.get("consortium_suggestion", False)
        barriers = analysis.get("barriers", [])
        opportunities = analysis.get("opportunities", [])

        if score >= 0.7:
            rec = "Good fit for SMEs. "
            if opportunities:
                rec += f"Key advantages: {opportunities[0]}. "
        elif score >= 0.5:
            rec = "Moderate fit for SMEs. "
            if barriers:
                rec += f"Main challenge: {barriers[0]}. "
        else:
            rec = "Challenging for SMEs. "
            if barriers:
                rec += f"Significant barriers: {barriers[0]}. "

        if consortium:
            rec += "Consider forming a consortium to strengthen the bid. "

        if analysis.get("ai_summary"):
            rec += analysis["ai_summary"][:200]

        return rec.strip()

    def clear_cache(self):
        """Clear the analysis cache."""
        self._cache.clear()


# Global instance
_analyzer: Optional[SMEAnalyzer] = None


def get_sme_analyzer() -> SMEAnalyzer:
    """Get or create the global SMEAnalyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = SMEAnalyzer()
    return _analyzer


# Convenience function
async def analyze_sme_suitability(
    tender: Dict[str, Any],
    company_profile: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Analyze tender suitability for SMEs.

    Example:
        >>> analysis = await analyze_sme_suitability(tender_dict)
        >>> print(analysis["sme_friendly_score"])
        0.75
        >>> print(analysis["barriers"])
        ["High turnover requirement", "5+ years experience needed"]

    Args:
        tender: Tender dictionary
        company_profile: Optional company profile for personalized analysis

    Returns:
        Analysis dictionary with score, barriers, opportunities, recommendations
    """
    analyzer = get_sme_analyzer()
    return await analyzer.analyze(tender, company_profile)


async def batch_analyze_sme(
    tenders: List[Dict[str, Any]],
    company_profile: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Analyze multiple tenders for SME suitability.

    Args:
        tenders: List of tender dictionaries
        company_profile: Optional company profile

    Returns:
        List of analysis results
    """
    analyzer = get_sme_analyzer()
    results = []

    for tender in tenders:
        try:
            analysis = await analyzer.analyze(tender, company_profile)
            results.append(analysis)
        except Exception as e:
            logger.error(f"SME analysis failed for {tender.get('publication_number')}: {e}")
            results.append({
                "tender_id": tender.get("publication_number"),
                "error": str(e)
            })

    return results
