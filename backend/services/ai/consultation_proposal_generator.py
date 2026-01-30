"""
Consultation Proposal Generator

AI-powered generation of response proposals for EC public consultations.
Uses user's documents and profile to generate personalised input suggestions.

Blue tier only feature.

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
from models.user_document import UserDocument
from models.user import User
from .consultation_analyser import ConsultationAnalysis

logger = logging.getLogger(__name__)

# Singleton instance
_proposal_generator: Optional['ConsultationProposalGenerator'] = None


@dataclass
class ConsultationProposal:
    """A single proposal for a consultation response."""
    id: int
    question_addressed: str
    proposed_response: str
    supporting_arguments: List[str]
    evidence_citations: List[str]
    source_documents: List[str]
    tone_suggestion: str
    confidence_score: float


@dataclass
class ProposalSet:
    """Complete set of proposals for a consultation."""
    consultation_id: str
    proposals: List[ConsultationProposal]
    overall_strategy: str
    recommended_tone: str
    key_messages: List[str]
    tokens_used: int
    generated_at: datetime


class ConsultationProposalGenerator:
    """
    Generate personalised input proposals for EC consultations.

    Uses:
    - Consultation analysis
    - User's uploaded documents
    - User's Brubru documents (position papers, briefings)
    - User profile and interests

    Blue tier only feature.
    """

    PROPOSAL_PROMPT = """You are an expert EU policy consultant helping a user respond to a European Commission public consultation.

## Consultation Information

**Title:** {title}
**Type:** {consultation_type}
**DG Responsible:** {dg_responsible}
**Deadline:** {end_date}
**Description:** {description}

## Consultation Analysis

**Executive Summary:** {executive_summary}

**Key Questions:**
{key_questions}

**Submission Requirements:** {submission_requirements}

## User Context

**Organisation/Role:** {user_context}

**User's Documents/Positions:**
{user_documents}

## Your Task

Based on the consultation requirements and the user's documented positions, generate personalised response proposals.

Provide your response in JSON format:

{{
  "overall_strategy": "Brief description of the recommended approach to this consultation",
  "recommended_tone": "The tone to adopt (e.g., 'constructive and solution-oriented', 'cautiously supportive', 'critical but constructive')",
  "key_messages": ["3-5 key messages to convey throughout the response"],
  "proposals": [
    {{
      "id": 1,
      "question_addressed": "The specific question or topic this proposal addresses",
      "proposed_response": "A draft response paragraph (150-300 words) that the user can adapt",
      "supporting_arguments": ["Key arguments supporting this position (2-4 points)"],
      "evidence_citations": ["References to specific evidence, data, or examples"],
      "source_documents": ["User documents that informed this proposal"],
      "tone_suggestion": "Specific tone guidance for this response",
      "confidence_score": 0.8
    }}
  ]
}}

Generate 3-6 proposals covering the main aspects of the consultation.
Make proposals specific, actionable, and aligned with the user's documented positions.
Where the user's documents don't directly address a topic, note this and provide general best-practice guidance.

Respond ONLY with the JSON object, no additional text."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """Initialise the proposal generator."""
        self.model = model
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        logger.info(f"[OK] ConsultationProposalGenerator initialised with model {model}")

    async def generate_proposals(
        self,
        consultation: PublicConsultation,
        analysis: ConsultationAnalysis,
        user: User,
        user_documents: List[UserDocument] = None,
    ) -> ProposalSet:
        """
        Generate personalised response proposals.

        Args:
            consultation: The consultation to respond to
            analysis: Pre-computed consultation analysis
            user: The user generating proposals
            user_documents: User's documents to use as context

        Returns:
            ProposalSet with AI-generated proposals
        """
        logger.info(f"[START] Generating proposals for {consultation.initiative_id} for user {user.id}")

        try:
            # Build user context
            user_context = user.organization or user.full_name or "Policy professional"
            if user.policy_interests:
                user_context += f" (interests: {', '.join(user.policy_interests[:5])})"

            # Build documents context
            user_documents_text = "No specific documents provided."
            if user_documents:
                doc_summaries = []
                for doc in user_documents[:5]:  # Limit to 5 docs
                    summary = f"- **{doc.title}** ({doc.document_type})"
                    if doc.content:
                        # Include first 500 chars of content
                        content_preview = doc.content[:500].replace('\n', ' ')
                        summary += f": {content_preview}..."
                    doc_summaries.append(summary)
                user_documents_text = "\n".join(doc_summaries)

            # Format key questions
            key_questions_text = "\n".join(f"- {q}" for q in analysis.key_questions) if analysis.key_questions else "See consultation description"

            # Format the prompt
            prompt = self.PROPOSAL_PROMPT.format(
                title=consultation.title,
                consultation_type=consultation.consultation_type.value if hasattr(consultation.consultation_type, 'value') else str(consultation.consultation_type),
                dg_responsible=consultation.dg_responsible or "Not specified",
                end_date=consultation.end_date.isoformat() if consultation.end_date else "Not specified",
                description=consultation.description or "No description provided",
                executive_summary=analysis.executive_summary,
                key_questions=key_questions_text,
                submission_requirements=analysis.submission_requirements or "Submit via Have Your Say portal",
                user_context=user_context,
                user_documents=user_documents_text,
            )

            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
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

            proposal_data = json.loads(response_text)

            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            # Build proposals
            proposals = []
            for p in proposal_data.get("proposals", []):
                proposals.append(ConsultationProposal(
                    id=p.get("id", len(proposals) + 1),
                    question_addressed=p.get("question_addressed", ""),
                    proposed_response=p.get("proposed_response", ""),
                    supporting_arguments=p.get("supporting_arguments", []),
                    evidence_citations=p.get("evidence_citations", []),
                    source_documents=p.get("source_documents", []),
                    tone_suggestion=p.get("tone_suggestion", ""),
                    confidence_score=p.get("confidence_score", 0.7),
                ))

            proposal_set = ProposalSet(
                consultation_id=str(consultation.id),
                proposals=proposals,
                overall_strategy=proposal_data.get("overall_strategy", ""),
                recommended_tone=proposal_data.get("recommended_tone", "constructive"),
                key_messages=proposal_data.get("key_messages", []),
                tokens_used=tokens_used,
                generated_at=datetime.now()
            )

            logger.info(f"[OK] Generated {len(proposals)} proposals for {consultation.initiative_id}, used {tokens_used} tokens")
            return proposal_set

        except json.JSONDecodeError as e:
            logger.error(f"[ERROR] Failed to parse AI response as JSON: {e}")
            raise ValueError("Failed to generate proposals - AI response parsing error")
        except Exception as e:
            logger.error(f"[ERROR] Failed to generate proposals: {e}")
            raise

    async def refine_proposal(
        self,
        proposal: ConsultationProposal,
        user_feedback: str,
        consultation: PublicConsultation
    ) -> ConsultationProposal:
        """
        Refine a proposal based on user feedback.

        Args:
            proposal: The original proposal
            user_feedback: User's refinement instructions
            consultation: The consultation context

        Returns:
            Refined ConsultationProposal
        """
        logger.info(f"[START] Refining proposal {proposal.id} for consultation {consultation.initiative_id}")

        refine_prompt = f"""You are refining a draft response for an EU consultation.

**Consultation:** {consultation.title}

**Original Proposal:**
Question Addressed: {proposal.question_addressed}
Response: {proposal.proposed_response}
Supporting Arguments: {', '.join(proposal.supporting_arguments)}

**User's Feedback:**
{user_feedback}

**Your Task:**
Revise the proposal based on the user's feedback. Keep the same JSON structure:

{{
  "question_addressed": "{proposal.question_addressed}",
  "proposed_response": "The revised response incorporating user feedback",
  "supporting_arguments": ["Revised supporting arguments"],
  "evidence_citations": ["Any evidence citations"],
  "tone_suggestion": "Updated tone guidance",
  "confidence_score": 0.85
}}

Respond ONLY with the JSON object."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1500,
                messages=[
                    {"role": "user", "content": refine_prompt}
                ]
            )

            response_text = response.content[0].text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]

            refined_data = json.loads(response_text)

            refined = ConsultationProposal(
                id=proposal.id,
                question_addressed=refined_data.get("question_addressed", proposal.question_addressed),
                proposed_response=refined_data.get("proposed_response", proposal.proposed_response),
                supporting_arguments=refined_data.get("supporting_arguments", proposal.supporting_arguments),
                evidence_citations=refined_data.get("evidence_citations", proposal.evidence_citations),
                source_documents=proposal.source_documents,
                tone_suggestion=refined_data.get("tone_suggestion", proposal.tone_suggestion),
                confidence_score=refined_data.get("confidence_score", proposal.confidence_score),
            )

            logger.info(f"[OK] Refined proposal {proposal.id}")
            return refined

        except Exception as e:
            logger.error(f"[ERROR] Failed to refine proposal: {e}")
            raise


def get_consultation_proposal_generator(model: str = "claude-sonnet-4-20250514") -> ConsultationProposalGenerator:
    """Get or create the singleton ConsultationProposalGenerator instance."""
    global _proposal_generator
    if _proposal_generator is None:
        _proposal_generator = ConsultationProposalGenerator(model=model)
    return _proposal_generator
