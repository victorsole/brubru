"""
RAG Chatbot Service

Retrieval-Augmented Generation chatbot for EU Law Comply.
Uses LangChain + vector search to answer compliance questions.
"""

import logging
from typing import List, Dict, Optional
from langchain.prompts import ChatPromptTemplate
from langchain.schema import HumanMessage, AIMessage, SystemMessage
from langchain.chains import LLMChain
from sqlalchemy.orm import Session
from openai import OpenAI

from core.config import settings
from models.eu_law import LawRequirement, EULaw, LawCluster
from services.embeddings import VectorSearchService

logger = logging.getLogger(__name__)


class RAGChatbotUnavailable(RuntimeError):
    """Retrieval or generation failed. Distinct from "no relevant requirement
    was found", which is a legitimate empty result the caller should render."""


class RAGChatbotService:
    """
    RAG-powered chatbot for EU law compliance assistance.

    Features:
    - Semantic search to retrieve relevant requirements
    - Context-aware responses using GPT-4
    - Cluster-specific expertise
    - Citation of source laws
    """

    def __init__(self, db: Session, cluster_id: Optional[int] = None):
        """
        Initialize RAG chatbot.

        Args:
            db: Database session
            cluster_id: Optional cluster ID to focus chatbot on specific domain
        """
        self.db = db
        self.cluster_id = cluster_id
        self.vector_search = VectorSearchService(db)

        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Conversation history (in-memory, should use Redis/DB in production)
        self.conversation_history: List[Dict] = []

        # Load cluster context if specified
        self.cluster_context = None
        if cluster_id:
            cluster = db.query(LawCluster).filter(LawCluster.id == cluster_id).first()
            if cluster:
                self.cluster_context = {
                    'name': cluster.name,
                    'policy_area': cluster.policy_area,
                    'description': cluster.description,
                    'applicability': cluster.applicability
                }

    def answer_question(
        self,
        question: str,
        top_k: int = 5,
        include_sources: bool = True
    ) -> Dict:
        """
        Answer a compliance question using RAG.

        Args:
            question: User's question
            top_k: Number of relevant requirements to retrieve
            include_sources: Include source requirements in response

        Returns:
            Dict with answer, sources, and metadata
        """
        try:
            # Step 1: Retrieve relevant requirements
            logger.info(f"Retrieving relevant requirements for: {question}")
            retrieved_requirements = self.vector_search.search_requirements(
                query=question,
                top_k=top_k,
                cluster_id=self.cluster_id,
                min_score=0.4  # Lower threshold for RAG
            )

            if not retrieved_requirements:
                return {
                    'answer': "I couldn't find relevant requirements to answer your question. Please try rephrasing or asking about a different aspect of EU law compliance.",
                    'sources': [],
                    'confidence': 0.0
                }

            # Step 2: Build context from retrieved requirements
            context = self._build_context(retrieved_requirements)

            # Step 3: Generate answer using GPT-4
            answer = self._generate_answer(question, context)

            # Step 4: Format response
            response = {
                'answer': answer,
                'confidence': self._estimate_confidence(retrieved_requirements),
                'retrieved_count': len(retrieved_requirements)
            }

            if include_sources:
                response['sources'] = self._format_sources(retrieved_requirements)

            # Add to conversation history
            self.conversation_history.append({
                'question': question,
                'answer': answer,
                'sources_count': len(retrieved_requirements)
            })

            return response

        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            # Raise rather than return an answer-shaped dict.
            #
            # This is currently unrouted, but the previous shape was a trap for
            # whoever wires it up: `{'answer': ..., 'sources': [], 'confidence':
            # 0.0, 'error': ...}` reads as a legitimate "nothing found" result
            # to any caller that renders `answer` and `sources` without checking
            # `error`. That is the same failure-as-a-business-answer pattern
            # that made a dead OpenAI key present itself as 0% compliance in
            # EU Law Comply on 8 Aug 2026.
            #
            # Note this service still calls OpenAI directly (self.openai_client)
            # while the rest of Brubru runs on the free open-model chain, so it
            # will fail on every call until it is migrated or funded. Fail
            # loudly so that is discovered at wiring time, not in production.
            raise RAGChatbotUnavailable(str(e)) from e

    def _build_context(self, requirements: List[Dict]) -> str:
        """
        Build context string from retrieved requirements.

        Args:
            requirements: List of requirement dicts from vector search

        Returns:
            Formatted context string
        """
        context_parts = []

        for i, req_data in enumerate(requirements, 1):
            req = req_data['requirement']

            # Get law information
            law = self.db.query(EULaw).filter(EULaw.id == req.law_id).first()

            context_part = f"""
Requirement {i}:
- Law: {law.celex if law else 'Unknown'} - {law.title[:100] if law else ''}
- Article: {req.article}
- Criticality: {req.criticality}
- Applicable to: {req.applicable_entity or 'General'}
- Requirement: {req.requirement_text}
- Relevance Score: {req_data['score']:.2f}
"""
            context_parts.append(context_part)

        return "\n".join(context_parts)

    def _generate_answer(self, question: str, context: str) -> str:
        """
        Generate answer using GPT-4 with retrieved context.

        Args:
            question: User's question
            context: Retrieved requirements context

        Returns:
            Generated answer
        """
        # Build system prompt
        system_prompt = """You are an expert EU law compliance assistant specializing in helping organizations understand their legal obligations.

Your role:
- Answer questions about EU law requirements clearly and accurately
- Base your answers on the provided relevant requirements
- Cite specific laws and articles when possible
- Explain criticality levels (critical, important, recommended)
- Identify who the requirement applies to
- Provide actionable guidance

Guidelines:
- Be precise and professional
- If the context doesn't contain enough information, say so
- Highlight the most relevant requirements
- Explain technical legal terms when needed
"""

        # Add cluster-specific context if available
        if self.cluster_context:
            system_prompt += f"""

You are currently focused on: {self.cluster_context['name']}
Policy Area: {self.cluster_context['policy_area']}
Description: {self.cluster_context['description']}
Applicable to: {self.cluster_context['applicability']}
"""

        # Build user prompt
        user_prompt = f"""Based on the following EU law requirements, please answer this question:

Question: {question}

Relevant Requirements:
{context}

Please provide a clear, comprehensive answer that:
1. Directly addresses the question
2. References specific laws and articles
3. Explains the criticality and applicability
4. Provides actionable guidance if applicable
"""

        # Call OpenAI
        response = self.openai_client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # Lower temperature for more factual responses
            max_tokens=1000
        )

        return response.choices[0].message.content.strip()

    def _estimate_confidence(self, requirements: List[Dict]) -> float:
        """
        Estimate confidence in answer based on retrieval scores.

        Args:
            requirements: Retrieved requirements

        Returns:
            Confidence score (0-1)
        """
        if not requirements:
            return 0.0

        # Use average of top 3 scores
        top_scores = [req['score'] for req in requirements[:3]]
        avg_score = sum(top_scores) / len(top_scores)

        return round(avg_score, 2)

    def _format_sources(self, requirements: List[Dict]) -> List[Dict]:
        """
        Format source requirements for response.

        Args:
            requirements: Retrieved requirements

        Returns:
            List of formatted source dicts
        """
        sources = []

        for req_data in requirements:
            req = req_data['requirement']

            # Get law info
            law = self.db.query(EULaw).filter(EULaw.id == req.law_id).first()

            sources.append({
                'requirement_id': req.id,
                'law_celex': law.celex if law else None,
                'law_title': law.title if law else None,
                'article': req.article,
                'requirement_text': req.requirement_text,
                'criticality': req.criticality,
                'applicable_entity': req.applicable_entity,
                'relevance_score': req_data['score']
            })

        return sources

    def get_conversation_summary(self) -> Dict:
        """
        Get summary of conversation.

        Returns:
            Summary dict with question count and topics
        """
        return {
            'question_count': len(self.conversation_history),
            'cluster_id': self.cluster_id,
            'cluster_name': self.cluster_context['name'] if self.cluster_context else None,
            'history': self.conversation_history[-5:]  # Last 5 exchanges
        }

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []


def create_chatbot(
    db: Session,
    cluster_id: Optional[int] = None
) -> RAGChatbotService:
    """
    Factory function to create a chatbot instance.

    Args:
        db: Database session
        cluster_id: Optional cluster to focus on

    Returns:
        RAGChatbotService instance
    """
    return RAGChatbotService(db, cluster_id=cluster_id)
