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

import asyncio
import json
import logging
import math
import os
import random
import re
from typing import List, Dict, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from models.eu_law import LawRequirement
from models.compliance import ComplianceAnalysis, GapFinding
from .document_processor import DocumentProcessor

logger = logging.getLogger(__name__)


class GapAnalysisUnavailable(RuntimeError):
    """The model could not be reached or returned nothing usable.

    Distinct from "the requirement is not met". Conflating the two is what let
    an unfunded API key present itself to users as 0% compliance.
    """


_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Very common words carry no retrieval signal and skew TF-IDF towards long
# chunks. Deliberately short: legal text is domain-specific enough that an
# aggressive stoplist removes real signal.
_STOPWORDS = frozenset("""
a an and are as at be by for from has have in is it its of on or shall that the
their they this to was were which with within must may not
""".split())


def _tokenise(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall((text or "").lower())
            if len(t) > 2 and t not in _STOPWORDS]


def _parse_json_object(raw: str) -> Optional[dict]:
    """Extract a JSON object from a model response.

    The free chain has no response_format=json_object equivalent, so models
    wrap output in prose or ```json fences. Try the whole string, then the
    outermost balanced braces.
    """
    if not raw:
        return None
    s = raw.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s).strip()
    try:
        parsed = json.loads(s)
        return parsed if isinstance(parsed, dict) else None
    except (ValueError, TypeError):
        pass
    start, depth = s.find("{"), 0
    if start == -1:
        return None
    for i in range(start, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(s[start:i + 1])
                    return parsed if isinstance(parsed, dict) else None
                except (ValueError, TypeError):
                    return None
    return None

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
    
    # Tunable without a redeploy. Chosen by measurement, not intuition: the
    # same 38-requirement cluster and document, timed end to end, gave
    #   sequential  ~125s, 37/38 findings (one lost to an unretried 429)
    #   concurrency 2   176s, 38/38
    #   concurrency 4   226s, 38/38
    #   concurrency 8    95s, 38/38
    # Higher concurrency provokes more 429s but the retries absorb them in
    # parallel, so wall-clock falls even as the warning count rises. Coverage
    # is full from 2 upwards; the retry, not the concurrency, is what fixed
    # the dropped requirement.
    DEFAULT_CONCURRENCY = 8
    DEFAULT_MAX_ATTEMPTS = 3
    DEFAULT_RETRY_BASE_DELAY = 2.0

    def __init__(self, db: Session):
        self.db = db
        self.doc_processor = DocumentProcessor()
        self.concurrency = int(os.environ.get("COMPLY_ANALYSIS_CONCURRENCY",
                                              self.DEFAULT_CONCURRENCY))
        self.max_attempts = int(os.environ.get("COMPLY_ANALYSIS_MAX_ATTEMPTS",
                                               self.DEFAULT_MAX_ATTEMPTS))
        self.retry_base_delay = float(os.environ.get("COMPLY_ANALYSIS_RETRY_DELAY",
                                                     self.DEFAULT_RETRY_BASE_DELAY))
        self._chunks: List[str] = []
        self._idf: Dict[str, float] = {}
        self._doc_vectors: List[Dict[str, float]] = []
    
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

            # Index once, then query per requirement.
            self._build_index(all_chunks)

            # Track statistics
            requirements_met = 0
            requirements_partial = 0
            requirements_gap = 0
            requirements_na = 0
            analysis_errors = 0

            # Analyse requirements with bounded concurrency and backoff.
            #
            # Strictly sequential at full speed exhausted every free provider in
            # turn: a single 38-requirement run produced Cerebras 429 (requests
            # per minute), Gemini 429, Groq 429 on its 12k tokens-per-minute
            # ceiling and NVIDIA 503. Each requirement burns several provider
            # calls because the chain fails over on the first refusal, so the
            # rate of *provider* calls is a multiple of the requirement rate.
            #
            # Two changes: a semaphore so a few requirements are in flight at
            # once (throughput without a thundering herd), and a retry with
            # exponential backoff around the whole chain so a momentary 429
            # waits rather than consuming the next provider's budget too.
            sem = asyncio.Semaphore(self.concurrency)

            async def analyse_one(requirement):
                async with sem:
                    delay = self.retry_base_delay
                    for attempt in range(self.max_attempts):
                        try:
                            return requirement, await self._analyze_requirement(
                                requirement, all_chunks, analysis_id
                            ), None
                        except GapAnalysisUnavailable as exc:
                            if attempt == self.max_attempts - 1:
                                return requirement, None, exc
                            # Jitter so retries from parallel workers do not
                            # land on the provider in lockstep.
                            await asyncio.sleep(delay + random.uniform(0, delay / 2))
                            delay *= 2
                    return requirement, None, None

            results = await asyncio.gather(*(analyse_one(r) for r in requirements))

            # DB writes stay on this coroutine: the Session is not safe to use
            # from several tasks at once.
            for requirement, finding, error in results:
                if error is not None or finding is None:
                    analysis_errors += 1
                    continue
                self.db.add(finding)

                if finding.status == 'met':
                    requirements_met += 1
                elif finding.status == 'partial':
                    requirements_partial += 1
                elif finding.status == 'gap':
                    requirements_gap += 1
                else:
                    requirements_na += 1

            # If the model never answered, this is a failed run, not a company
            # that complies with nothing. Reporting 0% here is worse than
            # reporting nothing: it is a confident, wrong, client-facing number.
            if analysis_errors and requirements_met + requirements_partial + requirements_gap + requirements_na == 0:
                logger.error(
                    f"Analysis {analysis_id}: all {analysis_errors} requirements failed to "
                    f"analyse. Marking failed rather than reporting 0% compliance."
                )
                analysis.status = 'failed'
                analysis.total_requirements = len(requirements)
                analysis.completed_at = datetime.utcnow()
                analysis.analysis_params = {
                    'error': 'model_unavailable',
                    'failed_requirements': analysis_errors,
                }
                self.db.commit()
                return

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
            if analysis_errors:
                # Partial run: surfaced so the score is read in context rather
                # than as a verdict over the full requirement set.
                analysis.analysis_params = {
                    'partial': True,
                    'failed_requirements': analysis_errors,
                    'analysed_requirements': len(requirements) - analysis_errors,
                }

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
        # Phase 1: lexical retrieval against the index built once per analysis
        relevant_chunks = self._search(requirement.requirement_text, top_k=5)
        
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
    
    def _build_index(self, chunks: List[str]) -> None:
        """Build a TF-IDF index over the document chunks, once per analysis.

        This replaces per-requirement OpenAI embedding calls. Two reasons:

        1. It was billing-dependent. When the OpenAI balance hit zero the
           embedding call raised, the except branch silently returned
           `chunks[:top_k]` -- the FIRST five chunks of the document,
           regardless of the requirement -- and the analysis carried on as if
           retrieval had worked.
        2. It re-embedded every chunk once per requirement. For the 401
           requirements in the GDPR package that is 401 full passes over the
           document to answer 401 questions about the same text.

        TF-IDF over a handful of policy documents is a fair match for this
        task: requirement text and policy text share concrete vocabulary
        ("authorised representative", "producer register", "unsold"). numpy is
        already a hard dependency in requirements-light.
        """
        self._chunks = chunks
        docs_tokens = [_tokenise(c) for c in chunks]
        df: Dict[str, int] = {}
        for toks in docs_tokens:
            for term in set(toks):
                df[term] = df.get(term, 0) + 1
        n = max(len(chunks), 1)
        self._idf = {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}
        self._doc_vectors = []
        for toks in docs_tokens:
            tf: Dict[str, float] = {}
            for term in toks:
                tf[term] = tf.get(term, 0.0) + 1.0
            vec = {t: (1.0 + math.log(c)) * self._idf.get(t, 0.0) for t, c in tf.items()}
            norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
            self._doc_vectors.append({t: v / norm for t, v in vec.items()})

    def _search(self, query: str, top_k: int = 5) -> List[str]:
        """Return the top-k chunks most lexically similar to the requirement."""
        if not self._chunks:
            return []
        q_tokens = _tokenise(query)
        if not q_tokens:
            return self._chunks[:top_k]
        qtf: Dict[str, float] = {}
        for term in q_tokens:
            qtf[term] = qtf.get(term, 0.0) + 1.0
        qvec = {t: (1.0 + math.log(c)) * self._idf.get(t, 0.0) for t, c in qtf.items()}
        qnorm = math.sqrt(sum(v * v for v in qvec.values())) or 1.0
        qvec = {t: v / qnorm for t, v in qvec.items()}

        scores = []
        for i, dvec in enumerate(self._doc_vectors):
            # Iterate the shorter vector; cosine of two unit vectors is the dot.
            small, large = (qvec, dvec) if len(qvec) <= len(dvec) else (dvec, qvec)
            scores.append((sum(v * large.get(t, 0.0) for t, v in small.items()), i))
        scores.sort(reverse=True)
        return [self._chunks[i] for score, i in scores[:top_k] if score > 0] or self._chunks[:top_k]
    
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
FIRST decide who this requirement binds. EU legal texts mix obligations on
companies with obligations on Member States, national authorities, producer
responsibility organisations, online platform providers and other third
parties. A duty addressed to someone other than this company is
not_applicable, no matter how much the company documentation fails to mention
it. So is a duty whose scope thresholds exclude this company, and one whose
implementing act has not been adopted yet.

Read the requirement's grammatical subject. "Member States shall...",
"Providers of online platforms shall...", "Producer responsibility
organisations shall..." are NOT obligations on the company unless the company
is itself that actor. Selling through a marketplace does not make a company an
online platform provider.

THEN, only for requirements that do bind this company, decide:
- met: Fully compliant
- partial: Some elements in place, others missing or incomplete
- gap: Not compliant
- not_applicable: The requirement does not bind this company, or its scope
  thresholds exclude it, or it is not yet in force for it

Absence of evidence about a duty the company does not owe is not a gap.

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

        # Runs on the shared free open-model chain, not OpenAI. The previous
        # implementation called gpt-4o-mini directly; when the OpenAI balance
        # reached zero every single call raised, the except branch below
        # returned a synthetic 'gap' for every requirement, and the analysis
        # still completed and reported a 0% compliance score. A client reading
        # that would conclude they comply with nothing. See the analysis_errors
        # accounting in analyze_compliance: a run where the model never
        # answered is now recorded as failed, not as zero compliance.
        try:
            from services.ai.multi_provider_service import get_multi_provider_service

            service = get_multi_provider_service()
            response = await service.generate(
                system_prompt=(
                    "You are an EU compliance expert analysing company documentation "
                    "against a legal requirement. Respond with a single valid JSON "
                    "object and nothing else: no prose, no markdown fences."
                ),
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1,
            )
            result = _parse_json_object(response.message)
            if result is None:
                raise ValueError(
                    f"provider {response.provider} returned no parseable JSON object"
                )
            return result

        except Exception as e:
            logger.error(f"LLM gap analysis failed: {str(e)}")
            # Signal the failure to the caller instead of returning a verdict.
            # Returning status='gap' here is what made a dead API key look like
            # a compliance finding.
            raise GapAnalysisUnavailable(str(e)) from e
    
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
