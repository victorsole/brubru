"""
Consultation Analyser

AI-powered analysis of EC public consultations.
Analyses consultation structure, key questions, requirements, and related legislation.

Created: January 2026
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

from anthropic import Anthropic

from core.config import settings
from models.public_consultation import PublicConsultation, ConsultationDocument
from knowledge_base.ec_consultations import get_dg_full_name, POLICY_AREA_LABELS, PolicyArea

logger = logging.getLogger(__name__)

# Singleton instance
_consultation_analyser: Optional['ConsultationAnalyser'] = None


@dataclass
class ConsultationAnalysis:
    """Result of AI consultation analysis."""
    consultation_id: str
    executive_summary: str
    key_questions: List[str]
    stakeholder_categories: List[str]
    submission_requirements: str
    legislation_context: str
    key_provisions_under_review: List[str]
    potential_impacts: List[str]
    recommended_focus_areas: List[str]
    confidence_score: float
    tokens_used: int
    generated_at: datetime


class ConsultationAnalyser:
    """
    AI-powered analysis of EC public consultations.

    Analyses:
    - Consultation structure and requirements
    - Key questions being asked
    - Related legislation context
    - Stakeholder categories targeted
    - Recommended focus areas for response
    """

    ANALYSIS_PROMPT = """You are an expert EU policy analyst helping users understand and respond to European Commission public consultations.

Analyse the following public consultation and provide a comprehensive analysis.

## Consultation Details

**Title:** {title}
**Type:** {consultation_type}
**Status:** {status}
**Directorate-General:** {dg_responsible} ({dg_name})
**Policy Areas:** {policy_areas}
**Deadline:** {end_date}
**Feedback Count:** {feedback_count}

**Description:**
{description}

{objectives_section}

{target_group_section}

{related_legislation_section}

{documents_section}

## Your Task

Provide a thorough analysis in JSON format with the following structure:

{{
  "executive_summary": "A clear 2-3 sentence summary of what this consultation is about and why it matters",
  "key_questions": ["List the main questions or topics the EC is seeking feedback on (3-7 items)"],
  "stakeholder_categories": ["List the types of stakeholders most relevant to respond (e.g., 'SMEs', 'Consumer organisations', 'Industry associations')"],
  "submission_requirements": "Describe what format responses should take and any specific requirements",
  "legislation_context": "Explain the legislative context - what laws are being reviewed, amended, or proposed",
  "key_provisions_under_review": ["List specific legal provisions, articles, or mechanisms being examined (2-5 items)"],
  "potential_impacts": ["List potential impacts on different stakeholders if proposals go forward (3-5 items)"],
  "recommended_focus_areas": ["Suggest areas where responses could have most impact (2-4 items)"],
  "confidence_score": 0.85
}}

Be specific and actionable. Focus on helping a policy professional prepare an effective response.
Respond ONLY with the JSON object, no additional text."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """Initialise the analyser."""
        self.model = model
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        logger.info(f"[OK] ConsultationAnalyser initialised with model {model}")

    async def analyse_consultation(
        self,
        consultation: PublicConsultation,
        documents: List[ConsultationDocument] = None
    ) -> ConsultationAnalysis:
        """
        Analyse a consultation and return structured analysis.

        Args:
            consultation: The consultation to analyse
            documents: Optional list of consultation documents

        Returns:
            ConsultationAnalysis with AI-generated insights
        """
        logger.info(f"[START] Analysing consultation: {consultation.initiative_id}")

        try:
            # Build prompt sections
            objectives_section = ""
            if consultation.objectives:
                objectives_section = f"**Objectives:**\n{consultation.objectives}"

            target_group_section = ""
            if consultation.target_group:
                target_group_section = f"**Target Group:**\n{consultation.target_group}"

            # Related legislation
            related_legislation_section = ""
            refs = []
            if consultation.com_references:
                refs.extend([f"COM reference: {ref}" for ref in consultation.com_references])
            if consultation.celex_numbers:
                refs.extend([f"CELEX: {celex}" for celex in consultation.celex_numbers])
            if refs:
                related_legislation_section = "**Related Legislation:**\n" + "\n".join(f"- {r}" for r in refs)

            # Documents summary
            documents_section = ""
            if documents:
                doc_list = [f"- {doc.title} ({doc.document_type})" for doc in documents[:10]]
                documents_section = "**Available Documents:**\n" + "\n".join(doc_list)
            elif consultation.documents:
                doc_list = [f"- {doc.title} ({doc.document_type})" for doc in consultation.documents[:10]]
                documents_section = "**Available Documents:**\n" + "\n".join(doc_list)

            # Policy areas labels
            policy_areas_str = ", ".join(consultation.policy_areas) if consultation.policy_areas else "Not specified"

            # Format the prompt
            prompt = self.ANALYSIS_PROMPT.format(
                title=consultation.title,
                consultation_type=consultation.consultation_type.value if hasattr(consultation.consultation_type, 'value') else str(consultation.consultation_type),
                status=consultation.status.value if hasattr(consultation.status, 'value') else str(consultation.status),
                dg_responsible=consultation.dg_responsible or "Not specified",
                dg_name=get_dg_full_name(consultation.dg_responsible) if consultation.dg_responsible else "Not specified",
                policy_areas=policy_areas_str,
                end_date=consultation.end_date.isoformat() if consultation.end_date else "Not specified",
                feedback_count=consultation.feedback_count or 0,
                description=consultation.full_description or consultation.description or "No description provided",
                objectives_section=objectives_section,
                target_group_section=target_group_section,
                related_legislation_section=related_legislation_section,
                documents_section=documents_section,
            )

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Parse response
            response_text = response.content[0].text.strip()

            # Extract JSON from response
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            analysis_data = json.loads(response_text)

            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            analysis = ConsultationAnalysis(
                consultation_id=str(consultation.id),
                executive_summary=analysis_data.get("executive_summary", "Analysis not available"),
                key_questions=analysis_data.get("key_questions", []),
                stakeholder_categories=analysis_data.get("stakeholder_categories", []),
                submission_requirements=analysis_data.get("submission_requirements", ""),
                legislation_context=analysis_data.get("legislation_context", ""),
                key_provisions_under_review=analysis_data.get("key_provisions_under_review", []),
                potential_impacts=analysis_data.get("potential_impacts", []),
                recommended_focus_areas=analysis_data.get("recommended_focus_areas", []),
                confidence_score=analysis_data.get("confidence_score", 0.7),
                tokens_used=tokens_used,
                generated_at=datetime.now()
            )

            logger.info(f"[OK] Analysis complete for {consultation.initiative_id}, used {tokens_used} tokens")
            return analysis

        except json.JSONDecodeError as e:
            logger.error(f"[ERROR] Failed to parse AI response as JSON: {e}")
            # Return a minimal analysis
            return ConsultationAnalysis(
                consultation_id=str(consultation.id),
                executive_summary=f"This consultation from {consultation.dg_responsible or 'the European Commission'} seeks feedback on {consultation.title}.",
                key_questions=["Review the consultation documents for specific questions"],
                stakeholder_categories=["All interested parties"],
                submission_requirements="Submit via the Have Your Say portal",
                legislation_context="See related legislation references above",
                key_provisions_under_review=[],
                potential_impacts=[],
                recommended_focus_areas=[],
                confidence_score=0.3,
                tokens_used=0,
                generated_at=datetime.now()
            )
        except Exception as e:
            logger.error(f"[ERROR] Failed to analyse consultation: {e}")
            raise


def get_consultation_analyser(model: str = "claude-sonnet-4-20250514") -> ConsultationAnalyser:
    """Get or create the singleton ConsultationAnalyser instance."""
    global _consultation_analyser
    if _consultation_analyser is None:
        _consultation_analyser = ConsultationAnalyser(model=model)
    return _consultation_analyser
