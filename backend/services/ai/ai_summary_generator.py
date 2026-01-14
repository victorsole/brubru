"""
AI Summary Generator

Phase 5: Smart Summaries
Generates EPRS-style briefings using Claude when no human-written briefing exists.

This service:
1. Takes EU legal text (from EUR-Lex, OEIL, etc.)
2. Generates plain-language EPRS-style briefing using Claude
3. Mimics EPRS briefing format and style
4. Provides fallback when no EPRS publication exists
5. Can update outdated briefings with current information

Result: EVERY piece of legislation has an understandable explanation

Usage:
    generator = AISummaryGenerator()

    # Generate briefing for legislation without EPRS coverage
    briefing = await generator.generate_legislative_briefing(
        celex="32024R9999",
        title="Hypothetical EU Regulation",
        legal_text="Full text of regulation...",
        metadata={...}
    )

    # Update outdated briefing with new information
    updated = await generator.update_briefing(
        original_briefing="Old EPRS briefing...",
        new_information="Recent procedure updates..."
    )
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass
import anthropic

from core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AIBriefing:
    """AI-generated EPRS-style briefing"""
    title: str
    summary: str  # Executive summary (1-2 paragraphs)
    key_points: List[str]  # Bullet points of main provisions
    background: str  # Context and background
    main_provisions: str  # Detailed explanation of key provisions
    impact_assessment: Optional[str] = None  # Expected impacts
    procedure_status: Optional[str] = None  # Legislative procedure status
    next_steps: Optional[str] = None  # What happens next
    related_legislation: List[str] = None  # Related CELEX numbers
    confidence_score: float = 0.0  # How confident the AI is (0-1)
    generated_at: datetime = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.generated_at is None:
            self.generated_at = datetime.now()
        if self.related_legislation is None:
            self.related_legislation = []
        if self.metadata is None:
            self.metadata = {}


class AISummaryGenerator:
    """
    Generates EPRS-style briefings using Claude AI

    This provides a fallback when no human-written EPRS briefing exists,
    ensuring every piece of legislation has an understandable explanation.

    Key Features:
    - Mimics EPRS briefing style (plain language, structured)
    - Extracts key points from complex legal text
    - Provides context and background
    - Explains impacts and implications
    - Updates outdated briefings with new information

    Example:
        generator = AISummaryGenerator()

        # Generate briefing
        briefing = await generator.generate_legislative_briefing(
            celex="32024R1234",
            title="Digital Markets Act",
            legal_text=full_legal_text,
            metadata={"procedure_ref": "2020/0361(COD)"}
        )

        print(briefing.summary)
        print(briefing.key_points)
    """

    # EPRS briefing style guidelines
    EPRS_STYLE_GUIDELINES = """
You are generating an EPRS (European Parliament Research Service) briefing.

EPRS briefings are:
- Written in PLAIN LANGUAGE for non-experts
- Structured and well-organized
- Focused on KEY POINTS and IMPLICATIONS
- Neutral and fact-based
- Concise but comprehensive

Format:
1. Executive Summary: 1-2 paragraphs overview
2. Key Points: 5-7 bullet points covering main provisions
3. Background: Context - why this legislation exists
4. Main Provisions: Detailed explanation of key elements
5. Impact Assessment: Expected effects and implications
6. Procedure Status: Where it is in the legislative process
7. Next Steps: What happens next

Tone:
- Clear and accessible
- Avoid legal jargon (or explain it)
- Use short sentences
- Focus on "what this means in practice"

Example good phrasing:
✓ "This regulation sets limits on how companies can use AI systems"
✗ "This regulation establishes a comprehensive regulatory framework..."

Be helpful and educational, not just descriptive.
"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 3000,
        temperature: float = 0.3  # Low temperature for consistency
    ):
        """
        Initialize AI Summary Generator

        Args:
            api_key: Anthropic API key (uses settings.ANTHROPIC_API_KEY if None)
            model: Claude model to use
            max_tokens: Maximum response length
            temperature: Sampling temperature (lower = more consistent)
        """
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize Anthropic client
        self.client = anthropic.Anthropic(api_key=self.api_key)

        logger.info(f"Initialized AI Summary Generator (model: {model})")

    async def generate_legislative_briefing(
        self,
        celex: str,
        title: str,
        legal_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        max_text_length: int = 15000
    ) -> AIBriefing:
        """
        Generate EPRS-style briefing for legislation

        Args:
            celex: CELEX number
            title: Legislation title
            legal_text: Full legal text (will be truncated if too long)
            metadata: Additional context (procedure ref, dates, etc.)
            max_text_length: Maximum legal text length to send to AI

        Returns:
            AIBriefing with generated content

        Example:
            briefing = await generator.generate_legislative_briefing(
                celex="32024R1689",
                title="Artificial Intelligence Act",
                legal_text=full_text,
                metadata={
                    "procedure_ref": "2021/0106(COD)",
                    "date": "2024-05-21",
                    "type": "Regulation"
                }
            )
        """
        logger.info(f"Generating AI briefing for {celex}: {title}")

        # Truncate legal text if too long
        truncated_text = legal_text[:max_text_length]
        if len(legal_text) > max_text_length:
            logger.warning(f"Legal text truncated from {len(legal_text)} to {max_text_length} chars")
            truncated_text += "\n\n[Text truncated due to length...]"

        # Build metadata context
        metadata_context = ""
        if metadata:
            metadata_parts = []
            if metadata.get("procedure_ref"):
                metadata_parts.append(f"Procedure: {metadata['procedure_ref']}")
            if metadata.get("date"):
                metadata_parts.append(f"Date: {metadata['date']}")
            if metadata.get("type"):
                metadata_parts.append(f"Type: {metadata['type']}")

            if metadata_parts:
                metadata_context = "\n\nAdditional Context:\n" + "\n".join(metadata_parts)

        # Build prompt
        prompt = f"""Generate an EPRS-style briefing for this EU legislation.

LEGISLATION:
CELEX: {celex}
Title: {title}{metadata_context}

LEGAL TEXT:
{truncated_text}

{self.EPRS_STYLE_GUIDELINES}

Generate a comprehensive briefing following the EPRS format above.
Return ONLY the briefing content, structured with clear headings.
"""

        try:
            # Call Claude API
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract text
            generated_text = response.content[0].text

            # Parse into structured briefing
            briefing = self._parse_generated_briefing(
                generated_text=generated_text,
                celex=celex,
                title=title,
                metadata=metadata
            )

            logger.info(f"Successfully generated AI briefing for {celex}")
            return briefing

        except Exception as e:
            logger.error(f"Failed to generate AI briefing: {str(e)}")

            # Return minimal briefing on error
            return AIBriefing(
                title=title,
                summary=f"AI briefing generation failed. This is {title} ({celex}).",
                key_points=[f"CELEX: {celex}"],
                background="Generation failed",
                main_provisions="Unable to generate briefing",
                confidence_score=0.0,
                metadata={"error": str(e), "celex": celex}
            )

    def _parse_generated_briefing(
        self,
        generated_text: str,
        celex: str,
        title: str,
        metadata: Optional[Dict[str, Any]]
    ) -> AIBriefing:
        """
        Parse Claude's response into structured AIBriefing

        Args:
            generated_text: Raw text from Claude
            celex: CELEX number
            title: Legislation title
            metadata: Original metadata

        Returns:
            Structured AIBriefing
        """
        # Simple section extraction based on common headings
        sections = {
            "summary": "",
            "key_points": [],
            "background": "",
            "main_provisions": "",
            "impact_assessment": "",
            "procedure_status": "",
            "next_steps": ""
        }

        # Split by common section headers
        lines = generated_text.split("\n")
        current_section = None
        current_content = []

        for line in lines:
            line_lower = line.lower().strip()

            # Detect section headers
            if any(header in line_lower for header in ["executive summary", "summary:"]):
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "summary"
                current_content = []
            elif "key point" in line_lower or "main point" in line_lower:
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "key_points"
                current_content = []
            elif "background" in line_lower:
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "background"
                current_content = []
            elif "main provision" in line_lower or "key provision" in line_lower:
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "main_provisions"
                current_content = []
            elif "impact" in line_lower:
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "impact_assessment"
                current_content = []
            elif "procedure" in line_lower or "legislative process" in line_lower:
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "procedure_status"
                current_content = []
            elif "next step" in line_lower:
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = "next_steps"
                current_content = []
            else:
                # Add to current section
                if current_section:
                    current_content.append(line)

        # Save last section
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        # Extract key points if it's a string (bullet points)
        key_points_list = []
        if isinstance(sections["key_points"], str) and sections["key_points"]:
            # Split by bullet points or numbers
            for line in sections["key_points"].split("\n"):
                line = line.strip()
                # Remove bullet markers
                line = line.lstrip("•-*123456789. ")
                if line:
                    key_points_list.append(line)

        # If no sections were detected, use the whole text as summary
        if not any(sections.values()):
            sections["summary"] = generated_text[:500]
            sections["main_provisions"] = generated_text

        # Calculate confidence score based on structure
        confidence = 0.5  # Base confidence
        if sections["summary"]:
            confidence += 0.1
        if key_points_list:
            confidence += 0.2
        if sections["background"]:
            confidence += 0.1
        if sections["main_provisions"]:
            confidence += 0.1

        # Create AIBriefing
        return AIBriefing(
            title=f"AI-Generated Briefing: {title}",
            summary=sections["summary"] or "No summary available",
            key_points=key_points_list or ["No key points extracted"],
            background=sections["background"] or "",
            main_provisions=sections["main_provisions"] or generated_text,
            impact_assessment=sections["impact_assessment"] or None,
            procedure_status=sections["procedure_status"] or None,
            next_steps=sections["next_steps"] or None,
            confidence_score=confidence,
            metadata={
                "celex": celex,
                "source": "ai_generated",
                "model": self.model,
                **(metadata or {})
            }
        )

    async def update_outdated_briefing(
        self,
        original_briefing: str,
        briefing_date: datetime,
        new_information: str,
        current_date: Optional[datetime] = None
    ) -> str:
        """
        Update an outdated EPRS briefing with new information

        Args:
            original_briefing: Original EPRS briefing text
            briefing_date: When original briefing was published
            new_information: New developments (e.g., procedure updates)
            current_date: Current date (defaults to now)

        Returns:
            Updated briefing text with new information incorporated

        Example:
            updated = await generator.update_outdated_briefing(
                original_briefing=old_eprs_text,
                briefing_date=datetime(2023, 1, 15),
                new_information="Regulation adopted on 2024-05-21. Now in force."
            )
        """
        if current_date is None:
            current_date = datetime.now()

        time_gap = (current_date - briefing_date).days

        logger.info(f"Updating briefing that is {time_gap} days old")

        prompt = f"""Update this EPRS briefing with new information.

ORIGINAL BRIEFING (from {briefing_date.strftime('%Y-%m-%d')}):
{original_briefing[:5000]}

NEW INFORMATION:
{new_information}

TASK:
The original briefing is {time_gap} days old. Update it to incorporate the new information.

Instructions:
1. Keep the original structure and style
2. Add an "UPDATE" section at the beginning highlighting what's new
3. Integrate new information into relevant sections
4. Mark updated sections with "[Updated: {current_date.strftime('%Y-%m-%d')}]"
5. Maintain EPRS plain-language style

Return the complete updated briefing.
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

            updated_text = response.content[0].text

            logger.info("Successfully updated briefing")
            return updated_text

        except Exception as e:
            logger.error(f"Failed to update briefing: {str(e)}")

            # Return original with error note
            return f"""[AI UPDATE FAILED]

Original briefing from {briefing_date.strftime('%Y-%m-%d')}:

{original_briefing}

---
Note: Attempted to update with new information but AI update failed.
New information: {new_information}
"""

    async def synthesize_multiple_briefings(
        self,
        briefings: List[Dict[str, Any]],
        topic: str
    ) -> str:
        """
        Synthesize multiple EPRS briefings into comprehensive overview

        Args:
            briefings: List of briefing dicts (title, text, date)
            topic: Topic/theme to focus on

        Returns:
            Synthesized briefing combining all sources

        Example:
            briefings = [
                {"title": "AI Act - At a Glance", "text": "...", "date": "2024-01"},
                {"title": "AI Act - In-Depth Analysis", "text": "...", "date": "2024-03"},
                {"title": "AI Act Impact Assessment", "text": "...", "date": "2024-02"}
            ]

            synthesis = await generator.synthesize_multiple_briefings(
                briefings=briefings,
                topic="AI Act"
            )
        """
        logger.info(f"Synthesizing {len(briefings)} briefings about '{topic}'")

        # Build briefings context
        briefings_text = ""
        for i, briefing in enumerate(briefings, 1):
            title = briefing.get("title", f"Briefing {i}")
            text = briefing.get("text", "")[:3000]  # Limit each to 3000 chars
            date = briefing.get("date", "Unknown")

            briefings_text += f"\n\n--- BRIEFING {i}: {title} ({date}) ---\n{text}\n"

        prompt = f"""Synthesize these EPRS briefings into a comprehensive overview.

TOPIC: {topic}

BRIEFINGS TO SYNTHESIZE:
{briefings_text}

TASK:
Create a single comprehensive briefing that combines insights from all sources.

Instructions:
1. Start with an executive summary
2. Organize by theme/topic (not by source)
3. Resolve any contradictions (note date-based evolution)
4. Highlight the most recent information
5. Include key points from all briefings
6. Use EPRS plain-language style
7. Cite which briefing provides each insight

Return a well-structured synthesis.
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

            synthesis = response.content[0].text

            logger.info(f"Successfully synthesized {len(briefings)} briefings")
            return synthesis

        except Exception as e:
            logger.error(f"Failed to synthesize briefings: {str(e)}")
            return f"Synthesis failed. {len(briefings)} briefings about {topic} are available separately."

    async def compare_with_impact_assessment(
        self,
        eprs_briefing: str,
        commission_impact_assessment: str,
        legislation_title: str
    ) -> str:
        """
        Compare EPRS briefing with Commission impact assessment

        Shows different perspectives and highlights key differences.

        Args:
            eprs_briefing: EPRS briefing text
            commission_impact_assessment: Commission impact assessment
            legislation_title: Title of legislation

        Returns:
            Comparative analysis

        Example:
            comparison = await generator.compare_with_impact_assessment(
                eprs_briefing=eprs_text,
                commission_impact_assessment=commission_ia,
                legislation_title="Digital Services Act"
            )
        """
        logger.info(f"Comparing EPRS briefing vs Commission IA for '{legislation_title}'")

        prompt = f"""Compare these two analyses of EU legislation.

LEGISLATION: {legislation_title}

EPRS BRIEFING (European Parliament Research Service):
{eprs_briefing[:4000]}

COMMISSION IMPACT ASSESSMENT:
{commission_impact_assessment[:4000]}

TASK:
Create a comparative analysis showing:
1. Areas of agreement
2. Key differences in perspective
3. Different emphasis/priorities
4. Unique insights from each source

Format:
- Executive Summary of comparison
- Side-by-side key points
- Analysis of differences
- Practical implications

Be balanced and highlight value of both perspectives.
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

            comparison = response.content[0].text

            logger.info("Successfully generated comparative analysis")
            return comparison

        except Exception as e:
            logger.error(f"Failed to generate comparison: {str(e)}")
            return f"Comparison failed for {legislation_title}"


# Global singleton
_ai_summary_generator: Optional[AISummaryGenerator] = None


def get_ai_summary_generator(
    model: str = "claude-sonnet-4-20250514"
) -> AISummaryGenerator:
    """
    Get global AI Summary Generator instance

    Args:
        model: Claude model to use

    Returns:
        AISummaryGenerator instance
    """
    global _ai_summary_generator

    if _ai_summary_generator is None:
        _ai_summary_generator = AISummaryGenerator(model=model)

    return _ai_summary_generator
