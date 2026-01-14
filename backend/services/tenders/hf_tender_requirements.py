"""
Hugging Face Tender Requirements Extractor

Extracts and structures requirements from tender notices for ESPD checklist generation.
Maps requirements to ESPD Part III (Exclusion) and Part IV (Selection).

Usage:
    from backend.services.tenders.hf_tender_requirements import extract_tender_requirements

    requirements = await extract_tender_requirements(tender_xml)
    # [
    #     {
    #         "type": "exclusion",
    #         "category": "A - Criminal convictions",
    #         "requirement": "No convictions for fraud...",
    #         "document_needed": "Criminal record certificate",
    #         "mandatory": True
    #     },
    #     ...
    # ]
"""

import logging
import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from services.ai.huggingface_service import get_huggingface_service

logger = logging.getLogger(__name__)


# ESPD Part III - Exclusion Grounds Categories
EXCLUSION_CATEGORIES = {
    "A": {
        "name": "Criminal convictions",
        "description": "Participation in criminal organisation, corruption, fraud, terrorist offences",
        "standard_document": "Criminal record certificate",
        "mandatory": True
    },
    "B": {
        "name": "Payment of taxes",
        "description": "Payment of taxes and social security contributions",
        "standard_document": "Tax compliance certificate",
        "mandatory": True
    },
    "C": {
        "name": "Insolvency",
        "description": "Bankruptcy, insolvency, winding-up, arrangement with creditors",
        "standard_document": "Declaration of solvency",
        "mandatory": True
    },
    "D": {
        "name": "Professional misconduct",
        "description": "Grave professional misconduct, conflict of interest",
        "standard_document": "Self-declaration",
        "mandatory": True
    }
}

# ESPD Part IV - Selection Criteria Categories
SELECTION_CATEGORIES = {
    "A": {
        "name": "Suitability",
        "description": "Enrolment in professional/trade register",
        "standard_document": "Trade register extract",
        "mandatory": True
    },
    "B": {
        "name": "Economic and financial standing",
        "description": "Turnover, financial ratios, insurance",
        "standard_document": "Audited financial statements",
        "mandatory": False
    },
    "C": {
        "name": "Technical and professional ability",
        "description": "References, qualifications, experience",
        "standard_document": "Reference list",
        "mandatory": False
    },
    "D": {
        "name": "Quality assurance",
        "description": "Quality management systems, environmental management",
        "standard_document": "ISO certificates",
        "mandatory": False
    }
}


class TenderRequirementsExtractor:
    """
    Extracts and structures tender requirements for ESPD checklist.

    Uses AI to identify requirements from tender text and maps them
    to standard ESPD categories for checklist generation.
    """

    def __init__(self):
        self._hf_service = None
        self._ecertis_data: Dict[str, Any] = {}
        self._load_ecertis_data()

    @property
    def hf_service(self):
        """Lazy load HuggingFace service."""
        if self._hf_service is None:
            self._hf_service = get_huggingface_service()
        return self._hf_service

    def _load_ecertis_data(self):
        """Load eCertis evidence data for country-specific documents."""
        ecertis_dir = Path("backend/knowledge_base/tenders/ecertis")

        if ecertis_dir.exists():
            for file_path in ecertis_dir.glob("criteria_*.json"):
                country_code = file_path.stem.replace("criteria_", "").upper()
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        self._ecertis_data[country_code] = json.load(f)
                except Exception as e:
                    logger.warning(f"Failed to load eCertis data for {country_code}: {e}")

    async def extract_requirements(
        self,
        tender: Dict[str, Any],
        include_country_evidence: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Extract structured requirements from a tender.

        Args:
            tender: Tender dictionary with full details
            include_country_evidence: Include country-specific evidence info

        Returns:
            List of requirement dictionaries with ESPD mapping
        """
        requirements = []

        # Extract from structured fields first (fast, no AI)
        structured_reqs = self._extract_from_structured_fields(tender)
        requirements.extend(structured_reqs)

        # Extract from description using AI
        if tender.get("description") or tender.get("xml_content"):
            text = tender.get("description") or tender.get("xml_content", "")[:5000]
            ai_reqs = await self._extract_from_text(text)
            requirements.extend(ai_reqs)

        # Add standard ESPD requirements
        standard_reqs = self._get_standard_espd_requirements()
        requirements.extend(standard_reqs)

        # Add country-specific evidence
        buyer_country = tender.get("buyer_country", "").upper()
        if include_country_evidence and buyer_country:
            for req in requirements:
                country_evidence = self._get_country_evidence(buyer_country, req["category"])
                if country_evidence:
                    req["country_evidence"] = country_evidence

        # Remove duplicates
        requirements = self._deduplicate_requirements(requirements)

        # Sort by type and category
        requirements.sort(key=lambda x: (
            0 if x["type"] == "exclusion" else 1,
            x.get("category", "Z")
        ))

        return requirements

    def _extract_from_structured_fields(self, tender: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract requirements from structured tender fields."""
        requirements = []

        # Selection criteria from tender
        selection_criteria = tender.get("selection_criteria", {})
        if isinstance(selection_criteria, dict):
            for key, value in selection_criteria.items():
                if value:
                    req = self._map_to_espd_category(key, str(value), "selection")
                    if req:
                        requirements.append(req)

        # Exclusion grounds from tender
        exclusion_grounds = tender.get("exclusion_grounds", {})
        if isinstance(exclusion_grounds, dict):
            for key, value in exclusion_grounds.items():
                if value:
                    req = self._map_to_espd_category(key, str(value), "exclusion")
                    if req:
                        requirements.append(req)

        # Minimum requirements
        min_reqs = tender.get("minimum_requirements", {})
        if isinstance(min_reqs, dict):
            if min_reqs.get("turnover"):
                requirements.append({
                    "type": "selection",
                    "category": "B - Economic and financial standing",
                    "requirement": f"Minimum annual turnover: €{min_reqs['turnover']:,.0f}",
                    "document_needed": "Audited financial statements (last 3 years)",
                    "mandatory": True,
                    "specific_value": min_reqs["turnover"]
                })

            if min_reqs.get("experience_years"):
                requirements.append({
                    "type": "selection",
                    "category": "C - Technical and professional ability",
                    "requirement": f"Minimum {min_reqs['experience_years']} years of experience",
                    "document_needed": "Reference project list",
                    "mandatory": True,
                    "specific_value": min_reqs["experience_years"]
                })

            if min_reqs.get("employees"):
                requirements.append({
                    "type": "selection",
                    "category": "C - Technical and professional ability",
                    "requirement": f"Minimum {min_reqs['employees']} employees",
                    "document_needed": "Staff declaration",
                    "mandatory": True,
                    "specific_value": min_reqs["employees"]
                })

        return requirements

    async def _extract_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract requirements from tender text using AI."""
        if not text or len(text) < 100:
            return []

        prompt = f"""Analyze this EU tender text and extract compliance requirements.

Text:
{text[:3000]}

Extract ONLY explicitly stated requirements. For each requirement identify:
1. Type: "exclusion" (disqualifying conditions) or "selection" (qualification criteria)
2. Category: A/B/C/D (see ESPD standard categories)
3. Requirement: What is required
4. Document: What document proves compliance

Format as JSON array:
[
  {{"type": "exclusion", "category": "A", "requirement": "...", "document": "..."}},
  {{"type": "selection", "category": "B", "requirement": "...", "document": "..."}}
]

Only include clear, explicit requirements. Return empty array if no clear requirements found."""

        try:
            response = await self.hf_service.query_legal_llm(prompt, max_tokens=800)

            if not response:
                return []

            # Parse JSON from response
            requirements = self._parse_requirements_json(response)
            return requirements

        except Exception as e:
            logger.error(f"AI requirement extraction failed: {e}")
            return []

    def _parse_requirements_json(self, response: str) -> List[Dict[str, Any]]:
        """Parse requirements from AI JSON response."""
        requirements = []

        # Try to extract JSON from response
        try:
            # Find JSON array in response
            start = response.find("[")
            end = response.rfind("]") + 1

            if start >= 0 and end > start:
                json_str = response[start:end]
                parsed = json.loads(json_str)

                for item in parsed:
                    if isinstance(item, dict) and item.get("type") and item.get("requirement"):
                        req = {
                            "type": item.get("type", "selection"),
                            "category": self._expand_category(item.get("category", ""), item.get("type", "")),
                            "requirement": item.get("requirement", ""),
                            "document_needed": item.get("document", "Self-declaration"),
                            "mandatory": True,
                            "ai_extracted": True
                        }
                        requirements.append(req)

        except json.JSONDecodeError:
            logger.warning("Failed to parse AI response as JSON")

        return requirements

    def _map_to_espd_category(
        self,
        field_name: str,
        value: str,
        req_type: str
    ) -> Optional[Dict[str, Any]]:
        """Map a field to an ESPD category."""
        field_lower = field_name.lower()

        if req_type == "exclusion":
            if "criminal" in field_lower or "conviction" in field_lower:
                cat = EXCLUSION_CATEGORIES["A"]
                return {
                    "type": "exclusion",
                    "category": f"A - {cat['name']}",
                    "requirement": value,
                    "document_needed": cat["standard_document"],
                    "mandatory": cat["mandatory"]
                }
            elif "tax" in field_lower or "contribution" in field_lower:
                cat = EXCLUSION_CATEGORIES["B"]
                return {
                    "type": "exclusion",
                    "category": f"B - {cat['name']}",
                    "requirement": value,
                    "document_needed": cat["standard_document"],
                    "mandatory": cat["mandatory"]
                }
            elif "insolvency" in field_lower or "bankrupt" in field_lower:
                cat = EXCLUSION_CATEGORIES["C"]
                return {
                    "type": "exclusion",
                    "category": f"C - {cat['name']}",
                    "requirement": value,
                    "document_needed": cat["standard_document"],
                    "mandatory": cat["mandatory"]
                }

        elif req_type == "selection":
            if "register" in field_lower or "enrol" in field_lower:
                cat = SELECTION_CATEGORIES["A"]
                return {
                    "type": "selection",
                    "category": f"A - {cat['name']}",
                    "requirement": value,
                    "document_needed": cat["standard_document"],
                    "mandatory": cat["mandatory"]
                }
            elif "turnover" in field_lower or "financial" in field_lower:
                cat = SELECTION_CATEGORIES["B"]
                return {
                    "type": "selection",
                    "category": f"B - {cat['name']}",
                    "requirement": value,
                    "document_needed": cat["standard_document"],
                    "mandatory": cat["mandatory"]
                }
            elif "technical" in field_lower or "reference" in field_lower or "experience" in field_lower:
                cat = SELECTION_CATEGORIES["C"]
                return {
                    "type": "selection",
                    "category": f"C - {cat['name']}",
                    "requirement": value,
                    "document_needed": cat["standard_document"],
                    "mandatory": cat["mandatory"]
                }
            elif "quality" in field_lower or "iso" in field_lower or "environmental" in field_lower:
                cat = SELECTION_CATEGORIES["D"]
                return {
                    "type": "selection",
                    "category": f"D - {cat['name']}",
                    "requirement": value,
                    "document_needed": cat["standard_document"],
                    "mandatory": cat["mandatory"]
                }

        return None

    def _expand_category(self, category: str, req_type: str) -> str:
        """Expand category code to full name."""
        if not category:
            return "Other"

        cat_code = category.upper()[0] if category else ""

        if req_type == "exclusion" and cat_code in EXCLUSION_CATEGORIES:
            return f"{cat_code} - {EXCLUSION_CATEGORIES[cat_code]['name']}"
        elif req_type == "selection" and cat_code in SELECTION_CATEGORIES:
            return f"{cat_code} - {SELECTION_CATEGORIES[cat_code]['name']}"

        return category

    def _get_standard_espd_requirements(self) -> List[Dict[str, Any]]:
        """Get standard ESPD requirements that apply to all tenders."""
        requirements = []

        # Standard exclusion grounds (always required)
        for code, cat in EXCLUSION_CATEGORIES.items():
            requirements.append({
                "type": "exclusion",
                "category": f"{code} - {cat['name']}",
                "requirement": cat["description"],
                "document_needed": cat["standard_document"],
                "mandatory": cat["mandatory"],
                "standard": True
            })

        # Standard selection criteria (usually required)
        for code, cat in SELECTION_CATEGORIES.items():
            requirements.append({
                "type": "selection",
                "category": f"{code} - {cat['name']}",
                "requirement": cat["description"],
                "document_needed": cat["standard_document"],
                "mandatory": cat["mandatory"],
                "standard": True
            })

        return requirements

    def _get_country_evidence(self, country_code: str, category: str) -> Optional[Dict[str, Any]]:
        """Get country-specific evidence requirements from eCertis data."""
        if country_code not in self._ecertis_data:
            return None

        ecertis = self._ecertis_data[country_code]
        criteria = ecertis.get("criteria", [])

        # Find matching criterion
        for criterion in criteria:
            if isinstance(criterion, dict):
                name = criterion.get("Name", {}).get("value", "")
                if category.lower() in name.lower():
                    evidence_info = []

                    # Extract evidence types
                    req_groups = criterion.get("RequirementGroup", [])
                    for group in req_groups:
                        evidence_types = group.get("TypeOfEvidence", [])
                        for evidence in evidence_types:
                            evidence_name = evidence.get("Name", {}).get("value", "")
                            issuer = ""
                            website = ""

                            issuers = evidence.get("EvidenceIssuerParty", [])
                            if issuers:
                                names = issuers[0].get("PartyName", [])
                                if names:
                                    issuer = names[0].get("Name", {}).get("value", "")
                                website = issuers[0].get("WebsiteURI", {}).get("value", "")

                            if evidence_name:
                                evidence_info.append({
                                    "name": evidence_name,
                                    "issuer": issuer,
                                    "website": website
                                })

                    if evidence_info:
                        return {
                            "country": country_code,
                            "evidence": evidence_info
                        }

        return None

    def _deduplicate_requirements(self, requirements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate requirements."""
        seen = set()
        unique = []

        for req in requirements:
            key = (req["type"], req["category"], req.get("requirement", "")[:100])
            if key not in seen:
                seen.add(key)
                unique.append(req)

        return unique


# Global instance
_extractor: Optional[TenderRequirementsExtractor] = None


def get_requirements_extractor() -> TenderRequirementsExtractor:
    """Get or create the global TenderRequirementsExtractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = TenderRequirementsExtractor()
    return _extractor


# Convenience function
async def extract_tender_requirements(
    tender: Dict[str, Any],
    include_country_evidence: bool = True
) -> List[Dict[str, Any]]:
    """
    Extract structured requirements from a tender for ESPD checklist.

    Example:
        >>> requirements = await extract_tender_requirements(tender_dict)
        >>> for req in requirements:
        ...     print(f"{req['type']}: {req['requirement']}")

    Args:
        tender: Tender dictionary
        include_country_evidence: Include country-specific evidence info

    Returns:
        List of requirement dictionaries
    """
    extractor = get_requirements_extractor()
    return await extractor.extract_requirements(tender, include_country_evidence)


def get_espd_categories() -> Dict[str, Any]:
    """Get ESPD category definitions."""
    return {
        "exclusion": EXCLUSION_CATEGORIES,
        "selection": SELECTION_CATEGORIES
    }
