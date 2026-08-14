"""
AI Services

AI-powered context building and chat integration.
Part of Phase 13: AI Context Injection - Task 13.4+

Components:
- ContextBuilder: Build comprehensive EU context from user queries
- CitationTracker: Track sources and generate footnotes
- RAGChatbotService: Retrieval-Augmented Generation for compliance Q&A

--------------------------------------------------------------------------
Imports here are LAZY (PEP 562), the same fix already applied to
services/tenders/__init__.py.

They used to be eager, and importing any submodule runs this file first. So
`from services.ai.context_builder import get_context_builder`, which api/chat.py
and eight other routers do at boot, ran this file, which eagerly imported
rag_chatbot_service, which imports VectorSearchService from services.embeddings,
which drags in scikit-learn, scipy, onnxruntime, nltk and tokenizers. Measured
under production conditions (torch and sentence-transformers absent, as in
requirements-light.txt): +457 MB resident, paid on every process start including
every cron subprocess, for a retrieval chatbot that no user-facing endpoint
calls -- the production chat runs on the free multi-provider chain, not on local
embeddings.

`from services.ai import create_chatbot` still works and still returns the same
object; it is resolved on first attribute access instead of at import. Importing
the light submodules directly (`services.ai.context_builder`,
`services.ai.citation_tracker`) no longer pulls the embeddings stack.
"""

from typing import TYPE_CHECKING

# attribute name -> submodule it lives in
_EXPORTS = {
    # Context builder (light: no embeddings)
    "ContextBuilder": "context_builder",
    "ContextData": "context_builder",
    "ExtractedEntities": "context_builder",
    "get_context_builder": "context_builder",
    # Citation tracker (light: no embeddings)
    "CitationTracker": "citation_tracker",
    "Citation": "citation_tracker",
    "create_citation_from_search_result": "citation_tracker",
    "create_citation_from_legislation": "citation_tracker",
    "create_citation_from_procedure": "citation_tracker",
    "create_citation_from_mep": "citation_tracker",
    # RAG chatbot (HEAVY: pulls VectorSearchService -> embeddings stack).
    # Kept out of the boot path; loads only when actually used.
    "RAGChatbotService": "rag_chatbot_service",
    "RAGChatbotUnavailable": "rag_chatbot_service",
    "create_chatbot": "rag_chatbot_service",
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    """Resolve an export on first access (PEP 562)."""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value          # cache, so the next access is a plain lookup
    return value


def __dir__():
    return sorted(__all__)


# Type checkers cannot follow __getattr__, so give them the real thing. This
# block never runs at runtime.
if TYPE_CHECKING:  # pragma: no cover
    from .context_builder import (
        ContextBuilder,
        ContextData,
        ExtractedEntities,
        get_context_builder,
    )
    from .citation_tracker import (
        CitationTracker,
        Citation,
        create_citation_from_search_result,
        create_citation_from_legislation,
        create_citation_from_procedure,
        create_citation_from_mep,
    )
    from .rag_chatbot_service import (
        RAGChatbotService,
        RAGChatbotUnavailable,
        create_chatbot,
    )
