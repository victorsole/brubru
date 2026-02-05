"""
Matching Services

Services for matching and linking different data sources.
"""

from .resolution_legislation_matcher import (
    ResolutionLegislationMatcher,
    ResolutionIndicator,
    get_resolution_matcher,
    find_resolutions_for_legislation,
    find_related_resolutions_by_similarity,
)

__all__ = [
    "ResolutionLegislationMatcher",
    "ResolutionIndicator",
    "get_resolution_matcher",
    "find_resolutions_for_legislation",
    "find_related_resolutions_by_similarity",
]
