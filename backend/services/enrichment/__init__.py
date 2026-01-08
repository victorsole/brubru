"""
Enrichment Services

Real-time data enrichment for chat conversations.
Part of Phase 13: AI Context Injection - Task 13.6

Components:
- RealTimeEnricher: Detect entities and fetch live data during chat
"""

from .real_time_enricher import (
    RealTimeEnricher,
    EnrichmentResult,
    get_real_time_enricher
)

__all__ = [
    'RealTimeEnricher',
    'EnrichmentResult',
    'get_real_time_enricher'
]
