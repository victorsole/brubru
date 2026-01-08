"""
AI Services

AI-powered context building and chat integration.
Part of Phase 13: AI Context Injection - Task 13.4+

Components:
- ContextBuilder: Build comprehensive EU context from user queries
- CitationTracker: Track sources and generate footnotes
- RAGChatbotService: Retrieval-Augmented Generation for compliance Q&A
"""

from .context_builder import (
    ContextBuilder,
    ContextData,
    ExtractedEntities,
    get_context_builder
)
from .citation_tracker import (
    CitationTracker,
    Citation,
    create_citation_from_search_result,
    create_citation_from_legislation,
    create_citation_from_procedure,
    create_citation_from_mep
)
from .rag_chatbot_service import RAGChatbotService, create_chatbot

__all__ = [
    'ContextBuilder',
    'ContextData',
    'ExtractedEntities',
    'get_context_builder',
    'CitationTracker',
    'Citation',
    'create_citation_from_search_result',
    'create_citation_from_legislation',
    'create_citation_from_procedure',
    'create_citation_from_mep',
    'RAGChatbotService',
    'create_chatbot'
]
