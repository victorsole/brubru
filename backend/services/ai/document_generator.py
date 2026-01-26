"""
Document Generator Service

AI-powered generation of EU advocacy documents:
- Position Papers
- MEP Briefing Notes
- Talking Points

Priority #3: Position Paper Generator
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
import anthropic

from core.config import settings
from schemas.document_generation import (
    GeneratePositionPaperRequest,
    GenerateMEPBriefingRequest,
    GenerateTalkingPointsRequest,
    GeneratedDocument,
    KeyAsk,
)

logger = logging.getLogger(__name__)


class DocumentGenerator:
    """
    AI-powered document generator for EU advocacy documents.

    Generates professional-quality position papers, MEP briefings,
    and talking points using Claude AI with EU-specific prompts.
    """

    # EU Advocacy Writing Style Guidelines
    EU_STYLE_GUIDELINES = """
WRITING STYLE FOR EU ADVOCACY DOCUMENTS:

Language:
- Use British English spelling (analyse, organisation, colour, programme)
- Formal but accessible tone
- Clear, concise sentences
- Avoid jargon or explain it when used

Structure:
- Clear section headings
- Numbered lists for recommendations
- Bullet points for supporting arguments
- Specific article/recital references where applicable

EU Conventions:
- Reference articles as "Article X" not "Art. X"
- Reference recitals as "Recital X"
- Use formal institutional names (European Commission, European Parliament)
- Include procedure references where known (e.g., 2021/0106(COD))

Tone Guidelines:
- CONSTRUCTIVE: Focus on improvement, acknowledge positives, propose solutions
- CRITICAL: Direct concerns, highlight problems, but remain professional
- TECHNICAL: Focus on legal/technical aspects, precise language
- DIPLOMATIC: Balanced, acknowledges multiple perspectives, seeks common ground

Quality Standards:
- Be specific, not vague ("Article 6(2) should be amended" not "changes are needed")
- Support arguments with evidence or examples
- Include clear, actionable recommendations
- Maintain professional credibility
"""

    POSITION_PAPER_PROMPT = """Generate a professional EU advocacy position paper.

ORGANISATION: {organisation_name}
ORGANISATION TYPE: {organisation_type}
ORGANISATION DESCRIPTION: {organisation_description}

LEGISLATION: {legislation_title}
PROCEDURE REFERENCE: {procedure_reference}
CELEX: {celex_number}

POSITION: {position}

KEY ASKS:
{key_asks_formatted}

SECTOR IMPACT: {sector_impact}
ADDITIONAL CONTEXT: {additional_context}

TONE: {tone}

{style_guidelines}

Generate a complete position paper with the following structure:

1. **EXECUTIVE SUMMARY** (2-3 paragraphs)
   - Brief description of legislation
   - Overall position statement
   - Summary of key recommendations

2. **ABOUT {organisation_name}**
   - Brief description of the organisation
   - Relevance to this policy area

3. **CONTEXT AND BACKGROUND**
   - Why this legislation matters
   - Current status in legislative process
   - Key provisions being addressed

4. **OVERALL POSITION**
   - Clear statement of position
   - Key points summary

5. **DETAILED ANALYSIS AND RECOMMENDATIONS**
   For each key ask:
   - Current text analysis
   - Our assessment (concerns or support)
   - Specific recommendation
   - Proposed amendment text (if applicable)
   - Rationale and evidence

6. **IMPACT ASSESSMENT**
   - Economic impact on sector
   - Operational implications
   - Broader EU implications

7. **CONCLUSION**
   - Restate main position
   - Call to action

8. **CONTACT INFORMATION**
   - Placeholder for organisation contact details

Format the output in clean Markdown with proper headings.
Include specific article references where possible.
Make recommendations concrete and actionable.
"""

    MEP_BRIEFING_PROMPT = """Generate a professional MEP briefing note for an EU advocacy meeting.

TARGET MEP: {mep_name}
POLITICAL GROUP: {political_group}
NATIONALITY: {nationality}
COMMITTEE: {committee}

LEGISLATION: {legislation_title}
PROCEDURE REFERENCE: {procedure_reference}

POSITION: {position}
THE ASK: {the_ask}
VOTING RECOMMENDATION: {voting_recommendation}

KEY POINTS:
{key_points_formatted}

ORGANISATION: {organisation_name}
CONTACT: {contact_name} ({contact_email})

MEP'S KNOWN PRIORITIES: {mep_priorities}
NATIONAL ANGLE: {national_angle}

{style_guidelines}

Generate a concise, impactful MEP briefing note with:

1. **KEY MESSAGES** (30 seconds read)
   - THE ASK: One clear sentence of what you want
   - WHY IT MATTERS: One sentence on impact
   - POSITION IN ONE LINE: Concise statement

2. **EXECUTIVE SUMMARY** (2 minutes read)
   - The issue (2-3 sentences)
   - What's at stake (for citizens, businesses, MEP's constituency)
   - Our recommendation
   - Supporting evidence (2-3 data points)

3. **BACKGROUND AND CONTEXT**
   - Legislative procedure status
   - Why this file matters
   - Current stage and upcoming milestones

4. **DETAILED POSITION**
   - What we support (with rationale)
   - What we oppose (with alternatives)

5. **SPECIFIC AMENDMENT PROPOSALS** (if applicable)
   - Current text
   - Proposed amendment
   - Justification

6. **ARGUMENTS TAILORED TO {mep_name}**
   - Political group priorities
   - National interest angle
   - Personal focus areas

7. **KEY FACTS AND FIGURES**
   - Compelling data points
   - Statistics supporting position

8. **Q&A PREPARATION**
   - Likely questions and responses

9. **WHY YOUR VOTE MATTERS**
   - Personalised message about their influence

10. **NEXT STEPS**
    - Immediate action requested
    - Timeline
    - Contact for follow-up

Keep it concise - MEPs have limited time.
Make the ask crystal clear.
Tailor arguments to their known priorities.
"""

    TALKING_POINTS_PROMPT = """Generate professional talking points for an EU advocacy meeting.

MEETING WITH: {meeting_with}
INSTITUTION: {meeting_institution}
PURPOSE: {meeting_purpose}

TOPIC: {topic}
PROCEDURE REFERENCE: {procedure_reference}

KEY MESSAGES:
{key_messages_formatted}

KEY ASKS:
{key_asks_formatted}

ORGANISATION: {organisation_name}

TOPICS TO AVOID: {topics_to_avoid}
ANTICIPATED QUESTIONS: {anticipated_questions}

{style_guidelines}

Generate structured talking points with:

1. **QUICK REFERENCE CARD** (one-page summary)
   - TOP 3 MESSAGES (brief bullet points)
   - TOP 3 ASKS (specific requests)
   - DON'T FORGET (critical reminders)
   - RED LINES (non-negotiable positions)
   - LIKELY DIFFICULT QUESTION + RESPONSE

2. **MEETING OBJECTIVES**
   - Primary objective
   - Secondary objectives
   - Success criteria

3. **CORE MESSAGES**
   For each key message:
   - Full message (2-3 sentences)
   - Supporting points
   - Why this matters to them

4. **SPECIFIC ASKS**
   For each ask:
   - What we want (precise description)
   - Why (rationale)
   - How they can help
   - If they say no (fallback)

5. **Q&A PREPARATION**
   For anticipated questions:
   - Recommended response
   - Key points to include
   - What NOT to say

6. **ARGUMENTS AND COUNTER-ARGUMENTS**
   - Our key arguments with evidence
   - Their likely counter-arguments
   - Our rebuttals

7. **DOS AND DON'TS**
   - Specific guidance for this meeting
   - Topics to avoid
   - How to handle sensitive issues

8. **FOLLOW-UP ACTIONS**
   - Immediate follow-up
   - Materials to send
   - Next engagement

Keep talking points concise and memorable.
Make messages punchy and impactful.
Prepare for pushback.
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4000,
        temperature: float = 0.4
    ):
        """
        Initialize Document Generator.

        Args:
            api_key: Anthropic API key
            model: Claude model to use
            max_tokens: Maximum response length
            temperature: Sampling temperature
        """
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        self.client = anthropic.Anthropic(api_key=self.api_key)

        logger.info(f"Initialized Document Generator (model: {model})")

    async def generate_position_paper(
        self,
        request: GeneratePositionPaperRequest,
        legislative_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedDocument:
        """
        Generate a position paper.

        Args:
            request: Position paper generation request
            legislative_context: Optional additional context from legislative tracker

        Returns:
            Generated document
        """
        logger.info(f"Generating position paper for: {request.legislation_title}")

        # Format key asks
        key_asks_formatted = "\n".join([
            f"- {i+1}. {ask.summary}"
            + (f"\n     Detail: {ask.detail}" if ask.detail else "")
            + (f"\n     Article: {ask.article_reference}" if ask.article_reference else "")
            for i, ask in enumerate(request.key_asks)
        ])

        # Build prompt
        prompt = self.POSITION_PAPER_PROMPT.format(
            organisation_name=request.organisation_name,
            organisation_type=request.organisation_type.replace("_", " ").title(),
            organisation_description=request.organisation_description or "Not provided",
            legislation_title=request.legislation_title,
            procedure_reference=request.procedure_reference or "Not specified",
            celex_number=request.celex_number or "Not specified",
            position=request.position.replace("_", " ").title(),
            key_asks_formatted=key_asks_formatted,
            sector_impact=request.sector_impact or "Not specified",
            additional_context=request.additional_context or "None",
            tone=request.tone.upper(),
            style_guidelines=self.EU_STYLE_GUIDELINES
        )

        # Generate
        content = await self._generate(prompt)

        # Parse sections
        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="position_paper",
            title=f"Position Paper: {request.legislation_title}",
            content=content,
            sections=sections,
            word_count=len(content.split()),
            language=request.language,
            legislative_context=legislative_context,
            editable_sections=list(sections.keys())
        )

    async def generate_mep_briefing(
        self,
        request: GenerateMEPBriefingRequest,
        legislative_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedDocument:
        """
        Generate an MEP briefing note.

        Args:
            request: MEP briefing generation request
            legislative_context: Optional additional context

        Returns:
            Generated document
        """
        logger.info(f"Generating MEP briefing for: {request.mep_name} on {request.legislation_title}")

        key_points_formatted = "\n".join([f"- {point}" for point in request.key_points])

        prompt = self.MEP_BRIEFING_PROMPT.format(
            mep_name=request.mep_name,
            political_group=request.political_group or "Not specified",
            nationality=request.nationality or "Not specified",
            committee=request.committee or "Not specified",
            legislation_title=request.legislation_title,
            procedure_reference=request.procedure_reference or "Not specified",
            position=request.position.replace("_", " ").title(),
            the_ask=request.the_ask,
            voting_recommendation=request.voting_recommendation or "Not specified",
            key_points_formatted=key_points_formatted,
            organisation_name=request.organisation_name,
            contact_name=request.contact_name or "[Contact Name]",
            contact_email=request.contact_email or "[contact@email.com]",
            mep_priorities=", ".join(request.mep_priorities) if request.mep_priorities else "Not specified",
            national_angle=request.national_angle or "Not specified",
            style_guidelines=self.EU_STYLE_GUIDELINES
        )

        content = await self._generate(prompt)
        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="mep_briefing",
            title=f"MEP Briefing: {request.mep_name} - {request.legislation_title}",
            content=content,
            sections=sections,
            word_count=len(content.split()),
            language=request.language,
            legislative_context=legislative_context,
            editable_sections=list(sections.keys())
        )

    async def generate_talking_points(
        self,
        request: GenerateTalkingPointsRequest,
        legislative_context: Optional[Dict[str, Any]] = None
    ) -> GeneratedDocument:
        """
        Generate talking points for a meeting.

        Args:
            request: Talking points generation request
            legislative_context: Optional additional context

        Returns:
            Generated document
        """
        logger.info(f"Generating talking points for meeting with: {request.meeting_with}")

        key_messages_formatted = "\n".join([f"- {msg}" for msg in request.key_messages])
        key_asks_formatted = "\n".join([f"- {ask}" for ask in request.key_asks])

        prompt = self.TALKING_POINTS_PROMPT.format(
            meeting_with=request.meeting_with,
            meeting_institution=request.meeting_institution or "Not specified",
            meeting_purpose=request.meeting_purpose,
            topic=request.topic,
            procedure_reference=request.procedure_reference or "Not specified",
            key_messages_formatted=key_messages_formatted,
            key_asks_formatted=key_asks_formatted,
            organisation_name=request.organisation_name,
            topics_to_avoid=", ".join(request.topics_to_avoid) if request.topics_to_avoid else "None specified",
            anticipated_questions="\n".join([f"- {q}" for q in request.anticipated_questions]) if request.anticipated_questions else "None specified",
            style_guidelines=self.EU_STYLE_GUIDELINES
        )

        content = await self._generate(prompt)
        sections = self._parse_sections(content)

        return GeneratedDocument(
            document_type="talking_points",
            title=f"Talking Points: Meeting with {request.meeting_with}",
            content=content,
            sections=sections,
            word_count=len(content.split()),
            language=request.language,
            legislative_context=legislative_context,
            editable_sections=list(sections.keys())
        )

    async def _generate(self, prompt: str) -> str:
        """
        Call Claude API to generate content.

        Args:
            prompt: The generation prompt

        Returns:
            Generated text content
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Document generation failed: {str(e)}")
            raise

    def _parse_sections(self, content: str) -> Dict[str, str]:
        """
        Parse generated content into named sections.

        Args:
            content: Full document content

        Returns:
            Dictionary of section name -> section content
        """
        sections = {}
        current_section = "preamble"
        current_content = []

        lines = content.split("\n")

        for line in lines:
            # Detect section headers (## or **HEADER**)
            if line.startswith("## ") or (line.startswith("**") and line.endswith("**")):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()

                # Start new section
                current_section = line.strip("#* ").lower().replace(" ", "_")
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections


# Global singleton
_document_generator: Optional[DocumentGenerator] = None


def get_document_generator(model: str = "claude-sonnet-4-20250514") -> DocumentGenerator:
    """
    Get global Document Generator instance.

    Args:
        model: Claude model to use

    Returns:
        DocumentGenerator instance
    """
    global _document_generator

    if _document_generator is None:
        _document_generator = DocumentGenerator(model=model)

    return _document_generator
