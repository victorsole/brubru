"""
Legislative File AI Analysis Service

Provides AI-powered analysis for EU legislative files with fallback chain:
1. Hugging Face Legal LLM (primary)
2. OpenAI GPT-4 (fallback)
3. Anthropic Claude (final fallback)

Features:
- Summarization in British English
- Policy area classification using Brubru's EU policy taxonomy
- Named entity extraction (MEPs, committees, legislation)

Uses backend/knowledge_base/institutions/eu_policies.json for policy classification.
"""

import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
import openai
import anthropic

from .huggingface_service import get_huggingface_service
from core.config import settings

logger = logging.getLogger(__name__)


class LegislativeFileAIService:
    """
    AI service specifically for legislative file analysis.

    Features:
    - British English summarization
    - EU policy area classification using Brubru taxonomy
    - Entity extraction for MEPs, committees, legislation
    """

    def __init__(self):
        """Initialize the service and load EU policy taxonomy."""
        self.hf_service = get_huggingface_service()
        self.policy_taxonomy = self._load_policy_taxonomy()
        logger.info(f"Initialized Legislative File AI Service with {len(self.policy_taxonomy)} policy areas")

    def _load_policy_taxonomy(self) -> List[str]:
        """
        Load EU policy areas from Brubru's knowledge base.

        Returns:
            List of policy area names for classification
        """
        try:
            # Load eu_policies.json
            json_path = Path(__file__).parent.parent.parent / "knowledge_base" / "institutions" / "eu_policies.json"

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Extract all policy area names
            policy_areas = []
            for category in data.get("policy_categories", []):
                for policy in category.get("policy_areas", []):
                    policy_areas.append(policy["name"])

            logger.info(f"Loaded {len(policy_areas)} policy areas from taxonomy")
            return policy_areas

        except Exception as e:
            logger.error(f"Failed to load policy taxonomy: {str(e)}")
            # Fallback to basic list
            return [
                "Single Market", "Competition", "Trade and Economic Security",
                "Climate Action", "Environment", "Energy", "Transport",
                "Digital Policy and Digital Economy", "Agriculture", "Maritime Affairs and Fisheries",
                "Employment and Social Affairs", "Health", "Justice and Fundamental Rights",
                "Migration and Home Affairs", "Foreign and Security Policy", "Defence and Security"
            ]

    async def analyze_legislative_file(
        self,
        title: str,
        description: Optional[str] = None,
        full_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive AI analysis on a legislative file.

        Args:
            title: Legislative file title
            description: Optional description/summary from scraper
            full_text: Optional full legislative text

        Returns:
            Analysis results:
            {
                "ai_summary": "British English summary...",
                "ai_policy_classifications": [
                    {"label": "Climate Action", "score": 0.92},
                    {"label": "Energy", "score": 0.78}
                ],
                "ai_entities": [
                    {"entity": "PER", "word": "Frans Timmermans", "score": 0.95},
                    {"entity": "ORG", "word": "ENVI Committee", "score": 0.89}
                ]
            }
        """
        logger.info(f"Analyzing legislative file: {title[:100]}")

        results = {
            "ai_summary": None,
            "ai_policy_classifications": [],
            "ai_entities": []
        }

        # Combine available text for analysis
        analysis_text = self._prepare_text(title, description, full_text)

        if not analysis_text:
            logger.warning("No text available for analysis")
            return results

        # 1. Generate British English summary
        try:
            summary = await self._generate_british_summary(analysis_text)
            results["ai_summary"] = summary
        except Exception as e:
            logger.error(f"Summary generation failed: {str(e)}")

        # 2. Classify policy areas
        try:
            classifications = await self.hf_service.classify_policy_area(
                text=analysis_text,
                candidate_labels=self.policy_taxonomy,
                multi_label=True
            )
            # Keep top 3 policy areas with score > 0.3
            results["ai_policy_classifications"] = [
                c for c in classifications[:3] if c["score"] > 0.3
            ]
        except Exception as e:
            logger.error(f"Policy classification failed: {str(e)}")

        # 3. Extract entities
        try:
            entities = await self.hf_service.extract_entities(analysis_text[:2000])  # Limit for NER
            results["ai_entities"] = self._filter_relevant_entities(entities)
        except Exception as e:
            logger.error(f"Entity extraction failed: {str(e)}")

        logger.info(f"Analysis complete: summary={len(results['ai_summary'] or '')} chars, "
                   f"policies={len(results['ai_policy_classifications'])}, "
                   f"entities={len(results['ai_entities'])}")

        return results

    def _prepare_text(
        self,
        title: str,
        description: Optional[str],
        full_text: Optional[str]
    ) -> str:
        """
        Combine available text for analysis.

        Prioritizes: full_text > description > title
        """
        if full_text and len(full_text) > 200:
            return full_text[:5000]  # Limit to 5000 chars
        elif description and len(description) > 50:
            return f"{title}. {description}"
        else:
            return title

    async def _generate_british_summary(self, text: str) -> Optional[str]:
        """
        Generate summary in British English with fallback chain:
        1. Hugging Face Legal LLM
        2. OpenAI GPT-4
        3. Anthropic Claude

        Uses intelligent prompting to generate meaningful summaries
        even when only a title is available.
        """
        # Build prompt based on text length
        if len(text) > 1000:
            prompt = f"""Summarise the following EU legislative proposal in British English (use British spelling like "analyse", "organisation", etc.):

{text[:3000]}

Provide a concise summary (2-3 sentences) focusing on the key objectives, scope, and expected impact."""

        elif len(text) > 300:
            prompt = f"""Based on this EU legislative proposal title and description, provide a concise summary in British English (use British spelling):

{text}

Explain in 2-3 sentences what this legislation aims to achieve, who it affects, and its main objectives."""

        else:
            prompt = f"""Based on this EU legislative proposal title:

"{text}"

Provide a brief explanatory summary (2-3 sentences) in British English that explains:
1. What policy area this legislation addresses
2. What type of changes or regulations it likely involves
3. Who or what sectors would be affected

Use British spelling (analyse, organisation, etc.)."""

        # Try 1: Hugging Face Legal LLM
        try:
            logger.info("Attempting summary with Hugging Face Legal LLM")
            summary = await self.hf_service.query_legal_llm(
                prompt=prompt,
                max_tokens=250,
                temperature=0.4
            )
            if summary and len(summary) > 50:
                logger.info("✅ Hugging Face Legal LLM succeeded")
                return self._convert_to_british_english(summary)
        except Exception as e:
            logger.warning(f"Hugging Face Legal LLM failed: {str(e)}")

        # Try 2: OpenAI GPT-4
        try:
            logger.info("Attempting summary with OpenAI GPT-4 (fallback)")
            openai.api_key = settings.OPENAI_API_KEY
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are an expert in EU legislation. Always use British English spelling."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250,
                temperature=0.4
            )
            summary = response.choices[0].message.content
            if summary and len(summary) > 50:
                logger.info("✅ OpenAI GPT-4 succeeded")
                return self._convert_to_british_english(summary)
        except Exception as e:
            logger.warning(f"OpenAI GPT-4 failed: {str(e)}")

        # Try 3: Anthropic Claude
        try:
            logger.info("Attempting summary with Anthropic Claude (final fallback)")
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=250,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            summary = message.content[0].text
            if summary and len(summary) > 50:
                logger.info("✅ Anthropic Claude succeeded")
                return self._convert_to_british_english(summary)
        except Exception as e:
            logger.error(f"Anthropic Claude failed: {str(e)}")

        # Final fallback: basic summarization
        logger.warning("All LLMs failed, attempting basic Hugging Face summarization")
        summary = await self.hf_service.summarize_text(
            text=text,
            max_length=150,
            min_length=40
        )

        # Post-process to British English (basic replacements)
        if summary:
            summary = self._convert_to_british_english(summary)

        return summary

    def _convert_to_british_english(self, text: str) -> str:
        """
        Convert American spellings to British English.
        """
        replacements = {
            'analyze': 'analyse',
            'analyzed': 'analysed',
            'analyzing': 'analysing',
            'organization': 'organisation',
            'organizations': 'organisations',
            'realize': 'realise',
            'realized': 'realised',
            'recognize': 'recognise',
            'recognized': 'recognised',
            'favor': 'favour',
            'labor': 'labour',
            'defense': 'defence',
            'offense': 'offence',
            'center': 'centre',
            'fiber': 'fibre',
            'liter': 'litre',
            'meter': 'metre',
            'color': 'colour',
            'honor': 'honour',
            'behavior': 'behaviour'
        }

        result = text
        for american, british in replacements.items():
            # Replace whole words only
            result = result.replace(f' {american} ', f' {british} ')
            result = result.replace(f' {american.capitalize()} ', f' {british.capitalize()} ')

        return result

    def _filter_relevant_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Filter and clean extracted entities.

        Focus on high-confidence entities relevant to EU legislation:
        - People (MEPs, Commissioners)
        - Organizations (Committees, DGs, Parliament)
        - Legislation references
        """
        relevant = []
        seen_words = set()

        for entity in entities:
            # Skip low confidence
            if entity.get("score", 0) < 0.7:
                continue

            word = entity.get("word", "").strip()

            # Skip duplicates
            if word.lower() in seen_words:
                continue

            # Skip very short entities
            if len(word) < 3:
                continue

            # Keep if it's a person, organization, or likely legislation
            entity_type = entity.get("entity", "")
            if any(t in entity_type for t in ["PER", "ORG", "MISC"]):
                relevant.append({
                    "type": entity_type,
                    "text": word,
                    "confidence": round(entity.get("score", 0), 2)
                })
                seen_words.add(word.lower())

        return relevant[:20]  # Limit to top 20 entities


# Global singleton
_legislative_file_ai_service: Optional[LegislativeFileAIService] = None


def get_legislative_file_ai_service() -> LegislativeFileAIService:
    """
    Get global Legislative File AI service instance.

    Returns:
        LegislativeFileAIService instance
    """
    global _legislative_file_ai_service

    if _legislative_file_ai_service is None:
        _legislative_file_ai_service = LegislativeFileAIService()

    return _legislative_file_ai_service
