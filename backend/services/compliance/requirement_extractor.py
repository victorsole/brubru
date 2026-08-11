"""
Requirement Extractor Service

Extracts legal obligations/requirements from EU laws using NLP + LLM.

Process:
1. Load law text from XML/HTML files
2. Identify obligation phrases (shall, must, required to, etc.)
3. Extract article numbers and requirement text
4. Classify criticality (critical/important/recommended)
5. Parse deadlines and applicability
6. Store in law_requirements table
"""

import re
import logging
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy.orm import Session
from openai import OpenAI

from core.config import settings
from models.eu_law import EULaw, LawRequirement, LawCluster
from core.database import SessionLocal

logger = logging.getLogger(__name__)


class RequirementExtractionUnavailable(RuntimeError):
    """The extraction model could not be reached or returned nothing usable.

    Distinct from "this sentence contains no requirement". Conflating the two
    is how a dead API key writes fabricated obligations into the corpus.
    """

# Initialize OpenAI client
openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Lazy import for HF extractor (only when needed)
_hf_extractor = None


def get_hf_extractor(model_id='saul-7b'):
    """Get or create HuggingFace extractor instance"""
    global _hf_extractor
    if _hf_extractor is None:
        from .hf_requirement_extractor import HuggingFaceRequirementExtractor
        _hf_extractor = HuggingFaceRequirementExtractor(model_id=model_id)
    return _hf_extractor


class RequirementExtractor:
    """
    Extracts legal requirements from EU law documents.
    
    Uses a hybrid approach:
    1. Regex patterns for obligation phrases
    2. NLP for article structure parsing
    3. LLM for requirement classification and refinement
    """
    
    # Obligation keywords indicating mandatory requirements
    OBLIGATION_PATTERNS = [
        r'\bshall\b',
        r'\bmust\b',
        r'\brequired to\b',
        r'\bhas to\b',
        r'\bobliged to\b',
        r'\bis mandatory\b',
        r'\bmandatory\b'
    ]
    
    # Deadline patterns
    DEADLINE_PATTERNS = [
        r'within (\d+) (days?|weeks?|months?|years?)',
        r'by (\d{1,2}) (January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})',
        r'no later than (.+?)(?:\.|,)',
        r'before (.+?)(?:\.|,)'
    ]
    
    # Article number patterns
    ARTICLE_PATTERNS = [
        r'Article (\d+(?:\([a-z0-9]+\))?)',
        r'Art\.? (\d+(?:\([a-z0-9]+\))?)',
        r'Article (\d+)',
        r'§ ?(\d+)'
    ]
    
    def __init__(self, db: Session, model: str = 'gpt-4'):
        """
        Initialize requirement extractor.

        Args:
            db: Database session
            model: Model to use ('gpt-4', 'saul-7b', 'llama-3.1-8b', 'mistral-7b')
        """
        self.db = db
        self.model = model
        self.use_huggingface = model != 'gpt-4'

        # Initialize HF extractor if needed
        if self.use_huggingface:
            self.hf_extractor = get_hf_extractor(model_id=model)
            logger.info(f"Using Hugging Face model: {model}")
        else:
            logger.info("Using OpenAI GPT-4")
        
    def extract_requirements_for_cluster(self, cluster_id: int, max_laws: Optional[int] = None) -> int:
        """
        Extract requirements for all laws in a cluster.
        
        Args:
            cluster_id: ID of the law cluster
            max_laws: Maximum number of laws to process (for testing)
            
        Returns:
            Number of requirements extracted
        """
        logger.info(f"Starting requirement extraction for cluster {cluster_id}")
        
        # Get cluster
        cluster = self.db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
        if not cluster:
            logger.error(f"Cluster {cluster_id} not found")
            return 0
            
        # Get laws in cluster
        from models.eu_law import ClusterLaw
        cluster_laws = self.db.query(ClusterLaw).filter(
            ClusterLaw.cluster_id == cluster_id
        ).limit(max_laws if max_laws else 1000).all()
        
        total_extracted = 0
        
        for cluster_law in cluster_laws:
            # Get full law object
            law = self.db.query(EULaw).filter(EULaw.id == cluster_law.law_id).first()
            if not law:
                continue
                
            logger.info(f"Processing law: {law.celex} - {law.title[:100]}")
            
            try:
                # Extract requirements from this law
                requirements = self.extract_requirements_from_law(law, cluster_id)
                
                # Save to database
                for req in requirements:
                    self.db.add(req)
                
                self.db.commit()
                total_extracted += len(requirements)
                
                logger.info(f"Extracted {len(requirements)} requirements from {law.celex}")
                
            except Exception as e:
                logger.error(f"Error processing law {law.celex}: {str(e)}")
                self.db.rollback()
                continue
        
        logger.info(f"Extraction complete: {total_extracted} total requirements for cluster {cluster_id}")
        return total_extracted
    
    def extract_requirements_from_law(self, law: EULaw, cluster_id: int) -> List[LawRequirement]:
        """
        Extract requirements from a single law.
        
        Args:
            law: EULaw object
            cluster_id: ID of the cluster this law belongs to
            
        Returns:
            List of LawRequirement objects
        """
        requirements = []
        
        # Get law text (from XML file or title if XML not available)
        law_text = self._load_law_text(law)
        if not law_text:
            logger.warning(f"No text available for law {law.celex}")
            return requirements
        
        # Split into articles
        articles = self._split_into_articles(law_text)
        
        # Process each article
        for article_num, article_text in articles:
            # Find obligation sentences
            obligation_sentences = self._find_obligation_sentences(article_text)
            
            for sentence in obligation_sentences:
                # Use LLM to analyze and structure the requirement
                req_data = self._analyze_requirement_with_llm(
                    sentence, article_num, law, cluster_id
                )
                
                if req_data:
                    requirement = LawRequirement(
                        law_id=law.id,
                        cluster_id=cluster_id,
                        article=req_data['article'],
                        requirement_text=req_data['requirement_text'],
                        deadline=req_data.get('deadline'),
                        criticality=req_data['criticality'],
                        applicable_entity=req_data.get('applicable_entity'),
                        extra_metadata=req_data.get('metadata', {})
                    )
                    requirements.append(requirement)
        
        return requirements
    
    def _load_law_text(self, law: EULaw) -> Optional[str]:
        """
        Load full text of law from XML file.

        Parses Formex XML format used by EU Publications Office.
        """
        # If XML path exists, parse it
        if law.xml_path and Path(law.xml_path).exists():
            try:
                import xml.etree.ElementTree as ET

                # Parse XML file
                tree = ET.parse(law.xml_path)
                root = tree.getroot()

                # Extract all text content from XML
                # Formex XML uses various tags like P, TXT, TITLE, etc.
                def extract_text(element):
                    """Recursively extract text from element and all children"""
                    text_parts = []

                    # Add element's text
                    if element.text:
                        text_parts.append(element.text.strip())

                    # Process all children
                    for child in element:
                        child_text = extract_text(child)
                        if child_text:
                            text_parts.append(child_text)

                        # Add tail text (text after closing tag)
                        if child.tail:
                            text_parts.append(child.tail.strip())

                    return ' '.join(filter(None, text_parts))

                # Extract all text from document
                full_text = extract_text(root)

                if full_text:
                    logger.info(f"Loaded {len(full_text)} characters from {law.xml_path}")
                    return full_text
                else:
                    logger.warning(f"No text extracted from XML: {law.xml_path}")

            except Exception as e:
                logger.error(f"Error parsing XML for {law.celex}: {str(e)}")

        # Fallback: use title only (limited but better than nothing)
        logger.warning(f"Using title as fallback for {law.celex}")
        return law.title if law.title else None
    
    def _split_into_articles(self, text: str) -> List[Tuple[str, str]]:
        """
        Split law text into articles.
        
        Returns list of (article_number, article_text) tuples.
        """
        articles = []
        
        # Simple regex to find article boundaries
        article_pattern = r'(Article \d+(?:\([a-z0-9]+\))?)'
        matches = list(re.finditer(article_pattern, text, re.IGNORECASE))
        
        for i, match in enumerate(matches):
            article_num = match.group(1)
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            article_text = text[start:end].strip()
            
            if article_text:
                articles.append((article_num, article_text))
        
        # If no articles found, treat entire text as single article
        if not articles and text:
            articles.append(("General", text))
        
        return articles
    
    def _find_obligation_sentences(self, text: str) -> List[str]:
        """
        Find sentences containing obligation keywords.
        """
        sentences = re.split(r'[.;]\s+', text)
        obligation_sentences = []
        
        for sentence in sentences:
            # Check if sentence contains any obligation pattern
            for pattern in self.OBLIGATION_PATTERNS:
                if re.search(pattern, sentence, re.IGNORECASE):
                    obligation_sentences.append(sentence.strip())
                    break
        
        return obligation_sentences
    
    def _analyze_requirement_with_llm(
        self, sentence: str, article_num: str, law: EULaw, cluster_id: int
    ) -> Optional[Dict]:
        """
        Use LLM to analyze requirement and extract structured data.

        Supports both OpenAI GPT-4 and Hugging Face models.

        Returns dict with:
        - article: Article number
        - requirement_text: Clean requirement text
        - criticality: critical/important/recommended
        - applicable_entity: Who must comply
        - deadline: Parsed deadline (if any)
        - metadata: Additional context
        """
        try:
            if self.use_huggingface:
                # Use Hugging Face extractor
                result = self.hf_extractor.extract_requirement(sentence, article_num, law)
            else:
                # Use OpenAI GPT-4
                result = self._analyze_with_openai(sentence, article_num, law)

            # Parse deadline if present
            deadline = None
            if result.get('deadline_text'):
                deadline = self._parse_deadline(result['deadline_text'])

            return {
                'article': result.get('article', article_num),
                'requirement_text': result.get('requirement_text', sentence),
                'criticality': result.get('criticality', 'important'),
                'applicable_entity': result.get('applicable_entity'),
                'deadline': deadline,
                'metadata': {
                    'confidence': result.get('confidence', 0.7),
                    'deadline_text': result.get('deadline_text'),
                    'law_celex': law.celex,
                    'model': self.model
                }
            }

        except Exception as e:
            logger.error(f"LLM analysis failed for '{sentence[:100]}': {str(e)}")
            # Do NOT return a synthetic requirement here.
            #
            # This used to hand back the raw sentence as `requirement_text` with
            # criticality 'important' and a quiet `fallback: True` marker. When
            # the provider is unreachable -- which is exactly what happened to
            # the gap analyser on 8 Aug 2026, OpenAI returning
            # credit_balance_exhausted on every call -- that turns an outage
            # into hundreds of plausible-looking obligations written into the
            # compliance corpus, where they are indistinguishable from curated
            # ones and get scored against real companies.
            #
            # Raising means the caller's per-law `except` logs the law and moves
            # on, and the extraction reports fewer requirements rather than
            # fabricated ones. Fewer is recoverable; fabricated is not.
            raise RequirementExtractionUnavailable(
                f"model unavailable while extracting article {article_num}: {e}"
            ) from e

    def _analyze_with_openai(self, sentence: str, article_num: str, law: EULaw) -> Dict:
        """Analyze requirement using OpenAI GPT-4"""
        import json

        prompt = f"""Analyze this legal requirement and extract structured information.

Law: {law.title}
CELEX: {law.celex}
Article: {article_num}
Requirement text: "{sentence}"

Extract:
1. Criticality (critical/important/recommended):
   - critical: Mandatory with penalties/enforcement
   - important: Mandatory but less severe consequences
   - recommended: Best practice or "should" obligations

2. Applicable entity: Who must comply? (e.g., "VLOPs", "all platforms", "data controllers")

3. Deadline: Any time limit mentioned? (extract date or relative time)

4. Clean requirement text: Rewrite in clear, concise language

Respond in JSON format:
{{
  "article": "{article_num}",
  "requirement_text": "clean version",
  "criticality": "critical|important|recommended",
  "applicable_entity": "who must comply",
  "deadline_text": "deadline if mentioned",
  "confidence": 0.0-1.0
}}"""

        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are an EU law expert analyzing legal requirements."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )

        result_text = response.choices[0].message.content.strip()
        return json.loads(result_text)
    
    def _parse_deadline(self, deadline_text: str) -> Optional[datetime]:
        """
        Parse deadline text into absolute date.
        
        Handles:
        - "within 6 months" -> calculate from today
        - "by 17 February 2024" -> parse absolute date
        - "no later than..." -> parse
        """
        try:
            # Relative deadlines (within X days/months/years)
            relative_match = re.search(r'within (\d+) (days?|weeks?|months?|years?)', deadline_text, re.IGNORECASE)
            if relative_match:
                amount = int(relative_match.group(1))
                unit = relative_match.group(2).lower().rstrip('s')
                
                if unit == 'day':
                    return datetime.utcnow() + timedelta(days=amount)
                elif unit == 'week':
                    return datetime.utcnow() + timedelta(weeks=amount)
                elif unit == 'month':
                    return datetime.utcnow() + timedelta(days=amount * 30)  # Approximate
                elif unit == 'year':
                    return datetime.utcnow() + timedelta(days=amount * 365)
            
            # Absolute deadlines (by DD Month YYYY)
            absolute_match = re.search(
                r'(?:by |until |before )?(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})',
                deadline_text, re.IGNORECASE
            )
            if absolute_match:
                day = int(absolute_match.group(1))
                month_name = absolute_match.group(2)
                year = int(absolute_match.group(3))
                
                month_map = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month = month_map.get(month_name.lower())
                
                if month:
                    return datetime(year, month, day)
            
            return None
            
        except Exception as e:
            logger.error(f"Error parsing deadline '{deadline_text}': {str(e)}")
            return None


def main():
    """
    CLI for running requirement extraction.
    
    Usage:
        python -m backend.services.compliance.requirement_extractor --cluster-id 1
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract requirements from EU laws')
    parser.add_argument('--cluster-id', type=int, required=True, help='Cluster ID to process')
    parser.add_argument('--max-laws', type=int, help='Max laws to process (for testing)')
    
    args = parser.parse_args()
    
    # Create database session
    db = SessionLocal()
    
    try:
        extractor = RequirementExtractor(db)
        count = extractor.extract_requirements_for_cluster(args.cluster_id, args.max_laws)
        print(f"\n✅ Extracted {count} requirements for cluster {args.cluster_id}")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == '__main__':
    main()
