"""
RSS AI Enrichment

Automatically enhance RSS feed entries with AI-generated content:
- Summaries for long articles
- Policy area classification
- Entity extraction (MEPs, legislation)
- Sentiment analysis

Uses Hugging Face models via huggingface_service.py
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from ..ai.huggingface_service import get_huggingface_service
from ...models.rss_entry import RSSEntry

logger = logging.getLogger(__name__)


class RSSAIEnricher:
    """
    Enrich RSS entries with AI-generated metadata.

    Features:
    - Auto-summarize articles without summaries
    - Classify into EU policy areas
    - Extract mentioned MEPs and legislation
    - Analyze sentiment

    Example:
        enricher = RSSAIEnricher()

        # Enrich single entry
        await enricher.enrich_entry(entry)

        # Batch enrich recent entries
        await enricher.enrich_recent_entries(db, hours=24)
    """

    def __init__(self):
        """Initialize AI enricher"""
        self.hf_service = get_huggingface_service()
        logger.info("Initialized RSS AI Enricher")

    async def enrich_entry(
        self,
        entry: RSSEntry,
        generate_summary: bool = True,
        classify_policy: bool = True,
        extract_entities: bool = True,
        analyze_sentiment: bool = False
    ) -> Dict[str, Any]:
        """
        Enrich a single RSS entry with AI-generated metadata.

        Args:
            entry: RSSEntry object to enrich
            generate_summary: Generate AI summary if missing
            classify_policy: Classify into policy areas
            extract_entities: Extract MEPs, legislation mentions
            analyze_sentiment: Analyze sentiment

        Returns:
            Dict with enrichment results:
            {
                "ai_summary": "Generated summary...",
                "policy_areas": ["Digital Economy", "Consumer Affairs"],
                "entities": {"meps": [...], "legislation": [...]},
                "sentiment": {"label": "POSITIVE", "score": 0.89},
                "enriched_at": datetime
            }

        Example:
            >>> entry = db.query(RSSEntry).first()
            >>> enrichment = await enricher.enrich_entry(entry)
            >>> entry.ai_summary = enrichment["ai_summary"]
            >>> db.commit()
        """
        logger.info(f"Enriching RSS entry: {entry.title[:50]}...")

        enrichment = {
            "enriched_at": datetime.now()
        }

        # Get text content (use summary or full content)
        text = entry.summary or entry.content or entry.title
        if not text or len(text) < 50:
            logger.warning(f"Entry too short to enrich: {entry.title}")
            return enrichment

        # 1. Generate AI summary if needed
        if generate_summary and not entry.ai_summary:
            summary = await self.hf_service.summarize_text(
                text,
                max_length=150,
                min_length=40
            )
            if summary:
                enrichment["ai_summary"] = summary
                logger.info(f"Generated summary: {summary[:100]}...")

        # 2. Classify into policy areas
        if classify_policy:
            classifications = await self.hf_service.classify_policy_area(
                text,
                multi_label=True
            )
            if classifications:
                # Take top 3 policy areas with score > 0.3
                policy_areas = [
                    c["label"]
                    for c in classifications[:3]
                    if c["score"] > 0.3
                ]
                enrichment["policy_areas"] = policy_areas
                logger.info(f"Policy areas: {', '.join(policy_areas)}")

        # 3. Extract entities
        if extract_entities:
            entities = await self.hf_service.extract_entities(text[:2000])  # Limit length
            if entities:
                # Group entities by type
                entity_groups = {
                    "people": [],
                    "organizations": [],
                    "locations": []
                }

                for entity in entities:
                    entity_type = entity.get("entity_group", entity.get("entity", ""))
                    word = entity.get("word", "")
                    score = entity.get("score", 0)

                    # Only keep high-confidence entities
                    if score > 0.8 and word:
                        if "PER" in entity_type:
                            entity_groups["people"].append(word)
                        elif "ORG" in entity_type:
                            entity_groups["organizations"].append(word)
                        elif "LOC" in entity_type:
                            entity_groups["locations"].append(word)

                enrichment["entities"] = entity_groups
                logger.info(f"Extracted entities: {sum(len(v) for v in entity_groups.values())} total")

        # 4. Analyze sentiment (optional - can be slow)
        if analyze_sentiment:
            sentiment = await self.hf_service.analyze_sentiment(text[:512])
            if sentiment:
                enrichment["sentiment"] = sentiment
                logger.info(f"Sentiment: {sentiment['label']} ({sentiment['score']:.2f})")

        logger.info(f"Enrichment complete for: {entry.title[:50]}")
        return enrichment

    async def enrich_recent_entries(
        self,
        db: Session,
        hours: int = 24,
        only_without_summary: bool = True,
        limit: int = 50
    ) -> Dict[str, int]:
        """
        Batch enrich recent RSS entries.

        Args:
            db: Database session
            hours: Process entries from last N hours
            only_without_summary: Only enrich entries without AI summary
            limit: Maximum entries to process

        Returns:
            Stats dict:
            {
                "processed": 42,
                "enriched": 38,
                "failed": 4
            }

        Example:
            >>> enricher = RSSAIEnricher()
            >>> stats = await enricher.enrich_recent_entries(db, hours=24)
            >>> print(f"Enriched {stats['enriched']} entries")
        """
        from datetime import timedelta

        logger.info(f"Starting batch enrichment (last {hours} hours, limit {limit})")

        # Query recent entries
        cutoff_time = datetime.now() - timedelta(hours=hours)
        query = db.query(RSSEntry).filter(
            RSSEntry.published_at >= cutoff_time
        )

        if only_without_summary:
            query = query.filter(
                (RSSEntry.ai_summary == None) | (RSSEntry.ai_summary == "")
            )

        entries = query.order_by(RSSEntry.published_at.desc()).limit(limit).all()

        logger.info(f"Found {len(entries)} entries to enrich")

        stats = {
            "processed": 0,
            "enriched": 0,
            "failed": 0
        }

        for entry in entries:
            try:
                stats["processed"] += 1

                # Enrich entry
                enrichment = await self.enrich_entry(
                    entry,
                    generate_summary=True,
                    classify_policy=True,
                    extract_entities=False,  # Skip for batch (slower)
                    analyze_sentiment=False   # Skip for batch (slower)
                )

                # Update entry in database
                if "ai_summary" in enrichment:
                    entry.ai_summary = enrichment["ai_summary"]

                if "policy_areas" in enrichment:
                    # Store policy areas in categories field (if available)
                    if not entry.categories:
                        entry.categories = enrichment["policy_areas"]
                    else:
                        # Merge with existing categories
                        entry.categories = list(set(entry.categories + enrichment["policy_areas"]))

                db.commit()
                stats["enriched"] += 1

                logger.info(f"Progress: {stats['processed']}/{len(entries)}")

            except Exception as e:
                logger.error(f"Failed to enrich entry {entry.id}: {str(e)}")
                stats["failed"] += 1
                db.rollback()

        logger.info(f"Batch enrichment complete: {stats}")
        return stats

    async def enrich_entry_with_legal_analysis(
        self,
        entry: RSSEntry,
        question: Optional[str] = None
    ) -> Optional[str]:
        """
        Use legal LLM (Saul-7B) to analyze legislative content in entry.

        Args:
            entry: RSS entry (should be about legislation)
            question: Specific question to ask (optional)

        Returns:
            Legal analysis text

        Example:
            >>> entry = db.query(RSSEntry).filter_by(title="New AI Act").first()
            >>> analysis = await enricher.enrich_entry_with_legal_analysis(
            ...     entry,
            ...     question="What are the key obligations for AI providers?"
            ... )
        """
        text = entry.summary or entry.content or entry.title

        if question:
            prompt = f"""Legal Document: {entry.title}

Content: {text[:2000]}

Question: {question}

Answer:"""
        else:
            prompt = f"""Analyze this EU legislative document and provide a brief summary of its key provisions:

Title: {entry.title}
Content: {text[:2000]}

Summary:"""

        analysis = await self.hf_service.query_legal_llm(
            prompt,
            max_tokens=512,
            temperature=0.3
        )

        return analysis


# Convenience function
async def enrich_rss_entry(
    entry: RSSEntry,
    db: Session
) -> RSSEntry:
    """
    Convenience function to enrich a single RSS entry.

    Args:
        entry: RSS entry to enrich
        db: Database session

    Returns:
        Enriched entry

    Example:
        >>> entry = await enrich_rss_entry(entry, db)
        >>> print(entry.ai_summary)
    """
    enricher = RSSAIEnricher()
    enrichment = await enricher.enrich_entry(entry)

    # Apply enrichments
    if "ai_summary" in enrichment:
        entry.ai_summary = enrichment["ai_summary"]

    if "policy_areas" in enrichment:
        entry.categories = enrichment["policy_areas"]

    db.commit()
    return entry
