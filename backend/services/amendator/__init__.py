"""
Amendator Services

AI-powered amendment generation and analysis.
Part of Phase 13: AI Context Injection - Task 13.8

Components:
- AIAmendmentGenerator: Generate AI-powered amendment suggestions
"""

from .ai_amendment_generator import (
    AIAmendmentGenerator,
    AmendmentSuggestion,
    get_amendment_generator
)

__all__ = [
    'AIAmendmentGenerator',
    'AmendmentSuggestion',
    'get_amendment_generator'
]
