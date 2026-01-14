"""
AI Amendment Generator

AI-powered amendment suggestions for legislative documents.
Part of Phase 13: AI Context Injection - Task 13.8

Features:
- Generate amendment text suggestions
- Analyze existing legislation for amendment opportunities
- Justify amendments with policy rationale
- Format amendments in proper EU legislative format
- Compare with similar amendments from other MEPs
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from anthropic import AsyncAnthropic

from services.ai.context_builder import ContextBuilder, get_context_builder

logger = logging.getLogger(__name__)


@dataclass
class AmendmentSuggestion:
    """Single amendment suggestion"""
    article: str  # e.g., "Article 5"
    paragraph: Optional[str]  # e.g., "Paragraph 2"
    original_text: str
    amended_text: str
    justification: str
    policy_area: str
    confidence: float  # 0-1, how confident AI is
    similar_amendments: List[Dict[str, Any]]  # Similar amendments by other MEPs


class AIAmendmentGenerator:
    """
    Generate AI-powered amendment suggestions.

    Workflow:
    1. User provides legislation text and amendment goal
    2. AI analyzes text and suggests specific amendments
    3. Generates proper EU legislative formatting
    4. Provides justification and policy rationale
    5. Finds similar amendments from other MEPs
    """

    MODEL = "claude-sonnet-4-20250514"

    def __init__(
        self,
        api_key: str,
        context_builder: ContextBuilder
    ):
        """
        Initialize amendment generator.

        Args:
            api_key: Anthropic API key
            context_builder: Context builder for research
        """
        self.client = AsyncAnthropic(api_key=api_key)
        self.context_builder = context_builder

        logger.info("Initialized AIAmendmentGenerator")

    async def suggest_amendments(
        self,
        legislation_text: str,
        celex: Optional[str] = None,
        amendment_goal: str = "",
        policy_focus: Optional[List[str]] = None,
        max_suggestions: int = 5
    ) -> List[AmendmentSuggestion]:
        """
        Generate amendment suggestions for legislation.

        Args:
            legislation_text: Full or partial text of legislation
            celex: CELEX number (optional, for context)
            amendment_goal: User's goal for amendments (e.g., "strengthen data protection")
            policy_focus: Policy areas to focus on
            max_suggestions: Maximum number of suggestions

        Returns:
            List of AmendmentSuggestion objects

        Example:
            >>> suggestions = await generator.suggest_amendments(
            ...     legislation_text="Article 5: Processing of personal data...",
            ...     celex="32016R0679",
            ...     amendment_goal="Strengthen consent requirements",
            ...     max_suggestions=3
            ... )
        """
        logger.info(f"Generating amendments for {celex or 'unknown legislation'}")

        # Build context
        context_str = await self._build_amendment_context(
            legislation_text=legislation_text,
            celex=celex,
            policy_focus=policy_focus
        )

        # Generate suggestions
        system_prompt = self._build_system_prompt()
        user_prompt = self._build_user_prompt(
            legislation_text=legislation_text,
            amendment_goal=amendment_goal,
            context=context_str,
            max_suggestions=max_suggestions
        )

        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=4000,
            temperature=0.7,
            system=system_prompt,
            messages=[{
                'role': 'user',
                'content': user_prompt
            }]
        )

        response_text = response.content[0].text if response.content else ""

        # Parse suggestions
        suggestions = self._parse_amendment_suggestions(response_text)

        logger.info(f"Generated {len(suggestions)} amendment suggestions")

        return suggestions[:max_suggestions]

    async def analyze_article(
        self,
        article_text: str,
        article_number: str,
        legislation_context: str = ""
    ) -> Dict[str, Any]:
        """
        Analyze a specific article for amendment opportunities.

        Args:
            article_text: Text of the article
            article_number: Article number (e.g., "Article 5")
            legislation_context: Broader legislative context

        Returns:
            Analysis dict with:
            - key_provisions: List of main provisions
            - potential_issues: Identified issues
            - amendment_opportunities: Where amendments could be made
            - related_articles: References to other articles
        """
        system_prompt = """You are an expert in EU legislative drafting and analysis.
Analyze articles of EU legislation to identify key provisions, potential issues, and amendment opportunities."""

        user_prompt = f"""Analyze this article from EU legislation:

ARTICLE: {article_number}

TEXT:
{article_text}

LEGISLATION CONTEXT:
{legislation_context}

Provide:
1. Key provisions (bullet points)
2. Potential issues or ambiguities
3. Amendment opportunities (where changes could improve clarity, effectiveness, or policy alignment)
4. Related articles or directives that should be considered

Format your response as structured JSON."""

        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=2000,
            temperature=0.5,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}]
        )

        response_text = response.content[0].text if response.content else ""

        # Parse response (simplified)
        analysis = {
            'article': article_number,
            'analysis_text': response_text,
            'timestamp': datetime.now().isoformat()
        }

        return analysis

    async def justify_amendment(
        self,
        original_text: str,
        amended_text: str,
        policy_rationale: str = ""
    ) -> str:
        """
        Generate justification for an amendment.

        Args:
            original_text: Original legislative text
            amended_text: Proposed amended text
            policy_rationale: Policy reason for amendment

        Returns:
            Formatted justification text
        """
        system_prompt = """You are an expert in EU legislative affairs.
Generate clear, persuasive justifications for legislative amendments."""

        user_prompt = f"""Generate a justification for this amendment:

ORIGINAL TEXT:
{original_text}

AMENDED TEXT:
{amended_text}

POLICY RATIONALE:
{policy_rationale}

Provide a concise justification (2-3 paragraphs) explaining:
1. Why the amendment is necessary
2. What specific improvements it makes
3. How it aligns with EU policy objectives
4. Expected impact

Use formal EU legislative language."""

        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=1000,
            temperature=0.6,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}]
        )

        justification = response.content[0].text if response.content else ""

        logger.debug(f"Generated justification: {len(justification)} chars")

        return justification

    async def compare_amendments(
        self,
        proposed_amendment: Dict[str, Any],
        existing_amendments: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Compare proposed amendment with existing amendments.

        Args:
            proposed_amendment: Your amendment
            existing_amendments: Amendments by other MEPs

        Returns:
            Comparison analysis
        """
        system_prompt = """You are an expert in legislative analysis.
Compare amendments to identify similarities, differences, and strategic opportunities."""

        # Build comparison prompt
        existing_summary = "\n".join([
            f"- Amendment {i+1} by {a.get('author', 'Unknown')}: {a.get('text', '')[:200]}"
            for i, a in enumerate(existing_amendments[:5])
        ])

        user_prompt = f"""Compare this proposed amendment with existing amendments:

PROPOSED AMENDMENT:
{proposed_amendment.get('text', '')}

EXISTING AMENDMENTS:
{existing_summary}

Analyze:
1. Similarities with existing amendments (potential coalition partners)
2. Key differences in approach
3. Strategic opportunities (amendments to support/oppose)
4. Recommendations for positioning

Format as structured analysis."""

        response = await self.client.messages.create(
            model=self.MODEL,
            max_tokens=1500,
            temperature=0.5,
            system=system_prompt,
            messages=[{'role': 'user', 'content': user_prompt}]
        )

        comparison_text = response.content[0].text if response.content else ""

        return {
            'comparison': comparison_text,
            'num_existing_amendments': len(existing_amendments),
            'timestamp': datetime.now().isoformat()
        }

    async def _build_amendment_context(
        self,
        legislation_text: str,
        celex: Optional[str],
        policy_focus: Optional[List[str]]
    ) -> str:
        """Build context for amendment generation"""
        context_parts = []

        # Get related legislation if CELEX provided
        if celex:
            try:
                context_data = await self.context_builder.build_context_for_query(
                    user_message=f"Legislation {celex} and related amendments",
                    use_live_apis=True,
                    use_rss=False
                )

                if context_data.legislation_details:
                    context_parts.append("RELATED LEGISLATION:")
                    for leg in context_data.legislation_details:
                        context_parts.append(f"- {leg.get('title', '')} ({leg.get('celex', '')})")

            except Exception as e:
                logger.error(f"Failed to build context: {str(e)}")

        # Add policy focus
        if policy_focus:
            context_parts.append(f"\nPOLICY FOCUS: {', '.join(policy_focus)}")

        return "\n".join(context_parts) if context_parts else ""

    def _build_system_prompt(self) -> str:
        """Build system prompt for amendment generation"""
        return """You are an expert in EU legislative drafting and amendment writing.

Your role is to:
- Analyze EU legislation for amendment opportunities
- Draft precise, well-formatted amendments
- Provide clear justifications aligned with EU policy objectives
- Ensure amendments are legally sound and technically correct

Guidelines:
- Use proper EU legislative formatting
- Be specific about article, paragraph, and text changes
- Provide policy-driven justifications
- Consider legal and technical implications
- Reference related EU legislation when relevant

Amendment format:
- Article and paragraph references
- Clear indication of text to be deleted/added
- Justification with policy rationale"""

    def _build_user_prompt(
        self,
        legislation_text: str,
        amendment_goal: str,
        context: str,
        max_suggestions: int
    ) -> str:
        """Build user prompt for amendment generation"""
        return f"""Analyze this legislation and suggest amendments:

LEGISLATION TEXT:
{legislation_text[:3000]}  # Truncate if too long

AMENDMENT GOAL:
{amendment_goal or "Improve clarity, effectiveness, and policy alignment"}

CONTEXT:
{context}

Generate up to {max_suggestions} specific amendment suggestions.

For each amendment, provide:
1. Article/Paragraph reference
2. Original text (exact quote)
3. Amended text (your proposed change)
4. Justification (why this amendment improves the legislation)
5. Policy area (e.g., "data protection", "environmental law")

Format each suggestion clearly with headers:
AMENDMENT 1
Article: [reference]
Original: [text]
Amended: [text]
Justification: [explanation]
Policy Area: [area]

[Repeat for each amendment]"""

    def _parse_amendment_suggestions(
        self,
        response_text: str
    ) -> List[AmendmentSuggestion]:
        """Parse AI response into AmendmentSuggestion objects"""
        suggestions = []

        # Simple parsing (in production, use more robust parsing)
        amendments = response_text.split('AMENDMENT ')

        for amendment_text in amendments[1:]:  # Skip first split (before first AMENDMENT)
            try:
                lines = amendment_text.strip().split('\n')

                article = ""
                original = ""
                amended = ""
                justification = ""
                policy_area = ""

                current_field = None

                for line in lines:
                    line = line.strip()

                    if line.startswith('Article:'):
                        article = line.replace('Article:', '').strip()
                        current_field = None
                    elif line.startswith('Original:'):
                        original = line.replace('Original:', '').strip()
                        current_field = 'original'
                    elif line.startswith('Amended:'):
                        amended = line.replace('Amended:', '').strip()
                        current_field = 'amended'
                    elif line.startswith('Justification:'):
                        justification = line.replace('Justification:', '').strip()
                        current_field = 'justification'
                    elif line.startswith('Policy Area:'):
                        policy_area = line.replace('Policy Area:', '').strip()
                        current_field = None
                    elif current_field and line:
                        # Continuation of previous field
                        if current_field == 'original':
                            original += ' ' + line
                        elif current_field == 'amended':
                            amended += ' ' + line
                        elif current_field == 'justification':
                            justification += ' ' + line

                if article and original and amended:
                    suggestion = AmendmentSuggestion(
                        article=article,
                        paragraph=None,
                        original_text=original,
                        amended_text=amended,
                        justification=justification,
                        policy_area=policy_area or "General",
                        confidence=0.8,  # Default confidence
                        similar_amendments=[]
                    )
                    suggestions.append(suggestion)

            except Exception as e:
                logger.error(f"Failed to parse amendment: {str(e)}")
                continue

        return suggestions


# Global singleton
_amendment_generator: Optional[AIAmendmentGenerator] = None


def get_amendment_generator(
    api_key: Optional[str] = None,
    context_builder: Optional[ContextBuilder] = None
) -> AIAmendmentGenerator:
    """
    Get global amendment generator instance.

    Args:
        api_key: Anthropic API key
        context_builder: Context builder

    Returns:
        AIAmendmentGenerator instance
    """
    global _amendment_generator

    if _amendment_generator is None:
        if api_key is None:
            raise ValueError("api_key required for first initialization")

        _amendment_generator = AIAmendmentGenerator(
            api_key=api_key,
            context_builder=context_builder or get_context_builder()
        )

    return _amendment_generator
