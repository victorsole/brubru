"""Personalised impact composer.

Given a user profile and a legislative file, produces a structured
"what this means for you" briefing built entirely from real DB columns.
Never invents content; if a field is missing it is omitted from the block.
"""

from .personalised_impact import (
    ImpactBlock,
    compose_impact_for_carriage,
)

__all__ = ["ImpactBlock", "compose_impact_for_carriage"]
