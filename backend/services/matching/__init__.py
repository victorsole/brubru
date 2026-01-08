"""
Matching Services

Phase 3: Intelligent Matching
Automatic linking between EU data sources and their explanatory materials.
"""

from .eprs_matcher import EPRSMatcher, get_eprs_matcher

__all__ = [
    'EPRSMatcher',
    'get_eprs_matcher',
]
