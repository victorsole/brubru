"""
Gap Analyzer Service

Compares legal requirements against company documents to identify compliance gaps.

Process:
1. Load requirements for the selected cluster
2. Extract text from uploaded documents
3. Phase 1: Semantic search - find potential matches using embeddings
4. Phase 2: LLM refinement - analyze matches and generate gap findings
5. Create action plan with priorities and recommendations
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from openai import OpenAI
import numpy as np

from core.config import settings
from models.eu_law import LawRequirement
from models.compliance import ComplianceAnalysis, GapFinding
from .document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

# Initialize OpenAI client
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# Mirrors the valid_gap_status CHECK constraint on gap_findings.status.
VALID_GAP_STATUSES = {'met', 'partial', 'gap', 'not_applicable'}


def _normalise_confidence(value) -> Optional[float]:
    """Coerce an LLM confidence to a 0-100 float, or None if unusable.

    The prompt asks for 0.0-1.0 while the column is documented as 0-100. Accept either,
    store 0-100, and drop anything non-numeric rather than letting it reach the DB.
    """
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    return round(v * 100, 2) if v <= 1.0 else round(min(v, 100.0), 2)


class GapAnalyzer:
    """
    Analyzes compliance gaps using hybrid semantic + LLM approach.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.doc_processor = DocumentProcessor()
    
    async def analyze_compliance(
        self,
        analysis_id: int,
        requirements: List[LawRequirement],
        document_paths: List[str]
    ) -> None:
        """
        Run complete compliance analysis.
        
        Args:
            analysis_id: ID of the ComplianceAnalysis record
            requirements: List of requirements to check
            document_paths: Paths to uploaded documents
        """
        logger.info(f"Starting compliance analysis {analysis_id}")
        
        # Update analysis status
        analysis = self.db.query(ComplianceAnalysis).filter(
            ComplianceAnalysis.id == analysis_id
        ).first()
        
        if not analysis:
            logger.error(f"Analysis {analysis_id} not found")
            return
        
        try:
            # Process all documents
            all_chunks = []
            doc_metadata = []

            for doc_path in document_paths:
                result = self.doc_processor.process_document(doc_path)
                all_chunks.extend(result['chunks'])
                doc_metadata.append(result['metadata'])

            logger.info(f"Processed {len(document_paths)} documents, {len(all_chunks)} chunks")

            # Track statistics
            requirements_met = 0
            requirements_partial = 0
            requirements_gap = 0
            requirements_na = 0

            # Analyze each requirement
            for requirement in requirements:
                finding = await self._analyze_requirement(
                    requirement, all_chunks, analysis_id
                )
                self.db.add(finding)

                # Update counts
                if finding.status == 'met':
                    requirements_met += 1
                elif finding.status == 'partial':
                    requirements_partial += 1
                elif finding.status == 'gap':
                    requirements_gap += 1
                else:
                    requirements_na += 1

            # Calculate compliance score (met + 0.5*partial) / (total - na)
            total_applicable = requirements_met + requirements_partial + requirements_gap
            if total_applicable > 0:
                compliance_score = (requirements_met + 0.5 * requirements_partial) / total_applicable * 100
            else:
                compliance_score = 100.0

            # Update analysis with statistics
            analysis.total_requirements = len(requirements)
            analysis.requirements_met = requirements_met
            analysis.requirements_partial = requirements_partial
            analysis.requirements_gap = requirements_gap
            analysis.compliance_score = compliance_score
            analysis.status = 'completed'
            analysis.completed_at = datetime.utcnow()

            self.db.commit()

            logger.info(
                f"Compliance analysis {analysis_id} completed: "
                f"{requirements_met} met, {requirements_partial} partial, "
                f"{requirements_gap} gaps, score={compliance_score:.1f}%"
            )
            
        except Exception as e:
            logger.error(f"Error in compliance analysis {analysis_id}: {str(e)}")
            analysis.status = 'failed'
            self.db.commit()
            raise
    
    async def _analyze_requirement(
        self,
        requirement: LawRequirement,
        document_chunks: List[str],
        analysis_id: int
    ) -> GapFinding:
        """
        Analyze a single requirement against documents.
        
        Phase 1: Semantic search for relevant chunks
        Phase 2: LLM analysis to determine compliance status
        """
        # Phase 1: Semantic search
        relevant_chunks = await self._semantic_search(
            requirement.requirement_text,
            document_chunks,
            top_k=5
        )
        
        # Phase 2: LLM analysis
        llm_result = await self._llm_gap_analysis(
            requirement, relevant_chunks
        )
        
        # The LLM's JSON goes straight into columns carrying CHECK constraints, so a
        # single unexpected status value ('partially_met', 'n/a', ...) raises on commit
        # and takes the WHOLE analysis down, not just one finding. Coerce before writing.
        status = str(llm_result.get('status', '')).strip().lower().replace(' ', '_')
        if status not in VALID_GAP_STATUSES:
            logger.warning(
                f"LLM returned unrecognised status {llm_result.get('status')!r} for "
                f"requirement {requirement.id}; recording as 'gap' for manual review"
            )
            status = 'gap'

        # Store confidence on a 0-100 scale to match the column's documented range.
        # The prompt asks for 0.0-1.0, so scale it here rather than leaving two
        # incompatible scales in one column.
        confidence = _normalise_confidence(llm_result.get('confidence'))

        # Create gap finding
        finding = GapFinding(
            analysis_id=analysis_id,
            requirement_id=requirement.id,
            status=status,
            confidence_score=confidence,
            evidence_text=llm_result.get('evidence_text'),
            evidence_source=llm_result.get('evidence_source'),
            gap_description=llm_result.get('gap_description'),
            recommendation=llm_result.get('recommendation'),
            priority=self._calculate_priority(requirement, llm_result['status']),
            estimated_effort=llm_result.get('estimated_effort', 'moderate'),
            similarity_score=llm_result.get('similarity_score'),
            matched_chunks=relevant_chunks[:3]  # Store top 3 matches
        )
        
        return finding
    
    async def _semantic_search(
        self,
        query: str,
        chunks: List[str],
        top_k: int = 5
    ) -> List[str]:
        """
        Find most relevant document chunks using embeddings.

        Uses OpenAI text-embedding-3-small for efficiency.
        """
        if not chunks:
            return []

        try:
            # Get embedding for query (requirement)
            query_response = client.embeddings.create(
                model="text-embedding-3-small",
                input=query
            )
            query_embedding = np.array(query_response.data[0].embedding)

            # Get embeddings for chunks (batch for efficiency)
            truncated_chunks = [chunk[:8000] for chunk in chunks]
            chunk_response = client.embeddings.create(
                model="text-embedding-3-small",
                input=truncated_chunks
            )
            chunk_embeddings = [np.array(item.embedding) for item in chunk_response.data]

            # Calculate cosine similarities
            similarities = [
                np.dot(query_embedding, chunk_emb) /
                (np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb))
                for chunk_emb in chunk_embeddings
            ]

            # Get top-k chunks
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            relevant_chunks = [chunks[i] for i in top_indices]

            return relevant_chunks

        except Exception as e:
            logger.error(f"Semantic search failed: {str(e)}")
            # Fallback: return first k chunks
            return chunks[:top_k]
    
    async def _llm_gap_analysis(
        self,
        requirement: LawRequirement,
        relevant_chunks: List[str]
    ) -> Dict:
        """
        Use LLM to analyze if requirement is met.
        
        Returns status, evidence, gaps, and recommendations.
        """
        context = '\n\n---\n\n'.join(relevant_chunks)
        
        prompt = f"""Analyze if this legal requirement is met based on the company documents provided.

REQUIREMENT:
Article: {requirement.article}
Text: {requirement.requirement_text}
Criticality: {requirement.criticality}
Applies to: {requirement.applicable_entity or 'General'}

COMPANY DOCUMENTATION:
{context}

TASK:
Determine if the requirement is:
- met: Fully compliant
- partial: Partially compliant (some elements missing)
- gap: Not compliant (major gaps)
- not_applicable: Requirement doesn't apply

Provide:
1. Status (met/partial/gap/not_applicable)
2. Confidence (0.0-1.0)
3. Evidence text (quote from documents that addresses this)
4. Evidence source (which document/section)
5. Gap description (what's missing if status is partial/gap)
6. Recommendation (specific actionable steps to comply)
7. Estimated effort (quick/moderate/significant)

Respond in JSON:
{{
  "status": "met|partial|gap|not_applicable",
  "confidence": 0.0-1.0,
  "evidence_text": "quote from document",
  "evidence_source": "document name/section",
  "gap_description": "what's missing",
  "recommendation": "specific steps to take",
  "estimated_effort": "quick|moderate|significant"
}}"""

        try:
            import json
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Cost-effective for bulk analysis
                messages=[
                    {"role": "system", "content": "You are an EU compliance expert analyzing company documentation. Always respond with valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=800,
                response_format={"type": "json_object"}
            )

            result = json.loads(response.choices[0].message.content.strip())

            return result

        except Exception as e:
            logger.error(f"LLM gap analysis failed: {str(e)}")
            # Fallback: mark as unknown
            return {
                'status': 'gap',
                'confidence': 0.3,
                'evidence_text': None,
                'evidence_source': None,
                'gap_description': 'Unable to analyze - please review manually',
                'recommendation': 'Manual review required',
                'estimated_effort': 'moderate'
            }
    
    def _calculate_priority(self, requirement: LawRequirement, status: str) -> int:
        """
        Calculate priority (1-5) based on criticality, status, and deadline.
        
        1 = Highest priority (critical gaps with near deadlines)
        5 = Lowest priority (recommended requirements already met)
        """
        # Base priority on status
        status_priority = {
            'gap': 1,
            'partial': 2,
            'met': 5,
            'not_applicable': 5
        }
        
        priority = status_priority.get(status, 3)
        
        # Adjust for criticality
        if requirement.criticality == 'critical' and status in ['gap', 'partial']:
            priority = max(1, priority - 1)
        elif requirement.criticality == 'recommended':
            priority = min(5, priority + 1)
        
        # Adjust for deadline urgency
        if requirement.deadline:
            days_until = (requirement.deadline - datetime.utcnow().date()).days
            if days_until < 30 and status in ['gap', 'partial']:
                priority = 1  # Urgent!
            elif days_until < 90 and status in ['gap', 'partial']:
                priority = min(priority, 2)
        
        return priority
