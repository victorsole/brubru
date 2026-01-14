"""
AI Content Analyzer

Service for analyzing RSS entries and user documents using Claude AI.
Part of My EU Bubble - Phase 4: AI Enrichment

Features:
- Policy area classification
- Entity extraction (persons, organizations, legislation)
- CELEX number detection
- Procedure reference detection
- Sentiment analysis
- Topic modeling
- Relevance scoring
"""

import logging
import re
from typing import List, Dict, Any, Optional
from anthropic import Anthropic

from core.config import settings

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """
    AI-powered content analyzer for RSS entries and user documents.

    Uses Claude API to extract metadata and classify content.
    """

    def __init__(self):
        """Initialize content analyzer"""
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-20250514"

        # EU policy areas (from Brubru's 33 policy areas)
        self.policy_areas = [
            "Agriculture and Food",
            "Budget and Finance",
            "Climate Action",
            "Competition",
            "Consumer Protection",
            "Culture and Education",
            "Customs",
            "Development and Cooperation",
            "Digital Economy",
            "Employment and Social Affairs",
            "Energy",
            "Environment",
            "EU Institutions",
            "External Relations",
            "Foreign Affairs",
            "Health",
            "Home Affairs",
            "Human Rights",
            "Immigration and Asylum",
            "Industry",
            "Internal Market",
            "International Trade",
            "Justice",
            "Migration",
            "Regional Policy",
            "Research and Innovation",
            "Security and Defence",
            "Taxation",
            "Tourism",
            "Transport",
            "Youth and Sport",
        ]

        logger.info("Initialized AI Content Analyzer")

    def analyze_content(
        self,
        title: str,
        content: str,
        extract_entities: bool = True,
        detect_legislation: bool = True,
        classify_policy_areas: bool = True,
        analyze_sentiment: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze content and extract metadata.

        Args:
            title: Content title
            content: Main content text
            extract_entities: Extract named entities
            detect_legislation: Detect CELEX numbers and procedures
            classify_policy_areas: Classify into policy areas
            analyze_sentiment: Analyze sentiment

        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing content: {title[:50]}...")

        results = {}

        try:
            # Policy area classification
            if classify_policy_areas:
                results['policy_areas'] = self.classify_policy_areas(title, content)

            # Entity extraction
            if extract_entities:
                results['entities'] = self.extract_entities(title, content)

            # Legislation detection
            if detect_legislation:
                celex_numbers = self.detect_celex_numbers(content)
                procedures = self.detect_procedures(content)
                results['celex_numbers'] = celex_numbers
                results['procedures'] = procedures

            # Sentiment analysis
            if analyze_sentiment:
                results['sentiment'] = self.analyze_sentiment(title, content)

            # Generate AI summary
            results['ai_summary'] = self.generate_summary(title, content)

            logger.info(f"Analysis complete. Found {len(results.get('policy_areas', []))} policy areas")

            return results

        except Exception as e:
            logger.error(f"Content analysis failed: {str(e)}")
            return {
                'error': str(e),
                'policy_areas': [],
                'entities': {},
                'celex_numbers': [],
                'procedures': [],
                'sentiment': 'neutral'
            }

    def classify_policy_areas(self, title: str, content: str) -> List[str]:
        """
        Classify content into EU policy areas.

        Args:
            title: Content title
            content: Main content text

        Returns:
            List of relevant policy areas
        """
        try:
            # Truncate content if too long
            max_content_length = 3000
            truncated_content = content[:max_content_length] if content else ""

            prompt = f"""Analyze this EU policy document and identify which EU policy areas it relates to.

Title: {title}

Content: {truncated_content}

Policy Areas to choose from:
{', '.join(self.policy_areas)}

Instructions:
1. Select 1-5 most relevant policy areas from the list above
2. Return ONLY the policy area names, separated by commas
3. Be specific and accurate
4. If none match well, return "General EU Affairs"

Policy Areas:"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse response
            response_text = message.content[0].text.strip()

            # Extract policy areas from response
            areas = [area.strip() for area in response_text.split(',')]

            # Validate against known policy areas
            valid_areas = [area for area in areas if area in self.policy_areas]

            return valid_areas if valid_areas else []

        except Exception as e:
            logger.error(f"Policy area classification failed: {str(e)}")
            return []

    def extract_entities(self, title: str, content: str) -> Dict[str, List[str]]:
        """
        Extract named entities from content.

        Args:
            title: Content title
            content: Main content text

        Returns:
            Dictionary with entity types and values
        """
        try:
            # Truncate content if too long
            truncated_content = content[:2000] if content else ""

            prompt = f"""Extract key entities from this EU policy text:

Title: {title}
Content: {truncated_content}

Extract the following:
1. **People**: Names of MEPs, Commissioners, officials (max 5)
2. **Organizations**: EU institutions, NGOs, companies (max 5)
3. **Places**: Countries, cities, regions (max 5)
4. **Topics**: Key policy topics or themes (max 5)

Format your response as JSON:
{{
  "people": ["name1", "name2"],
  "organizations": ["org1", "org2"],
  "places": ["place1", "place2"],
  "topics": ["topic1", "topic2"]
}}

Entities:"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON response
            import json
            response_text = message.content[0].text.strip()

            # Try to extract JSON from response
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                entities = json.loads(json_match.group())
                return entities
            else:
                return {"people": [], "organizations": [], "places": [], "topics": []}

        except Exception as e:
            logger.error(f"Entity extraction failed: {str(e)}")
            return {"people": [], "organizations": [], "places": [], "topics": []}

    def detect_celex_numbers(self, content: str) -> List[str]:
        """
        Detect CELEX numbers in content using regex.

        Args:
            content: Content text

        Returns:
            List of CELEX numbers found
        """
        if not content:
            return []

        # CELEX number pattern
        # Format: XYYYY[A-Z]NNNN
        # Example: 32021R0241, 52020DC0562
        pattern = r'\b[0-9]{1}[0-9]{4}[A-Z]{1,2}[0-9]{4,6}\b'

        matches = re.findall(pattern, content)

        return list(set(matches))  # Remove duplicates

    def detect_procedures(self, content: str) -> List[str]:
        """
        Detect legislative procedure references in content.

        Args:
            content: Content text

        Returns:
            List of procedure references found
        """
        if not content:
            return []

        # Procedure reference pattern
        # Format: YYYY/NNNN(AAA)
        # Example: 2021/0106(COD), 2020/0350(NLE)
        pattern = r'\b[0-9]{4}/[0-9]{4}\([A-Z]{3,4}\)\b'

        matches = re.findall(pattern, content)

        return list(set(matches))  # Remove duplicates

    def analyze_sentiment(self, title: str, content: str) -> str:
        """
        Analyze sentiment of content.

        Args:
            title: Content title
            content: Main content text

        Returns:
            Sentiment: positive, negative, or neutral
        """
        try:
            # Truncate content
            truncated_content = content[:1000] if content else ""

            prompt = f"""Analyze the sentiment of this EU policy text:

Title: {title}
Content: {truncated_content}

Determine if the overall sentiment is:
- positive (supportive, optimistic, progressive)
- negative (critical, concerning, problematic)
- neutral (factual, balanced, informative)

Return ONLY ONE WORD: positive, negative, or neutral

Sentiment:"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}]
            )

            sentiment = message.content[0].text.strip().lower()

            # Validate response
            if sentiment in ['positive', 'negative', 'neutral']:
                return sentiment
            else:
                return 'neutral'

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {str(e)}")
            return 'neutral'

    def generate_summary(self, title: str, content: str, max_length: int = 200) -> str:
        """
        Generate concise AI summary of content.

        Args:
            title: Content title
            content: Main content text
            max_length: Maximum summary length in words

        Returns:
            AI-generated summary
        """
        try:
            # Truncate content
            truncated_content = content[:2500] if content else ""

            prompt = f"""Summarize this EU policy content in 2-3 sentences ({max_length} words max):

Title: {title}
Content: {truncated_content}

Focus on:
- Main topic and purpose
- Key policy implications
- Important stakeholders or decisions

Summary:"""

            message = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}]
            )

            summary = message.content[0].text.strip()

            return summary

        except Exception as e:
            logger.error(f"Summary generation failed: {str(e)}")
            # Fallback: return first 200 words of content
            words = content.split()[:max_length] if content else []
            return ' '.join(words) + '...' if words else title

    def calculate_relevance_score(
        self,
        content_policy_areas: List[str],
        user_policy_interests: List[str]
    ) -> int:
        """
        Calculate relevance score (0-100) based on policy area overlap.

        Args:
            content_policy_areas: Policy areas from content
            user_policy_interests: User's policy interests

        Returns:
            Relevance score (0-100)
        """
        if not user_policy_interests or not content_policy_areas:
            return 50  # Neutral score

        # Calculate overlap
        overlap = set(content_policy_areas) & set(user_policy_interests)
        overlap_count = len(overlap)

        if overlap_count == 0:
            return 20  # Low relevance
        elif overlap_count == 1:
            return 60  # Medium relevance
        elif overlap_count == 2:
            return 80  # High relevance
        else:
            return 100  # Very high relevance


# Global analyzer instance
_analyzer_instance = None


def get_analyzer() -> ContentAnalyzer:
    """Get global content analyzer instance"""
    global _analyzer_instance

    if _analyzer_instance is None:
        _analyzer_instance = ContentAnalyzer()

    return _analyzer_instance
