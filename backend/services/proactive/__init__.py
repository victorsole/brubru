"""Proactive Chat trigger engine.

Surfaces briefings the user has not asked for but should care about:
morning summary, new files matching profile, tracked-file movement,
amendment surges. Computed at request time from real DB state; never
synthesises content.
"""

from .trigger_engine import (
    ProactiveBriefing,
    TriggerSource,
    compute_pending_briefings,
)

__all__ = [
    "ProactiveBriefing",
    "TriggerSource",
    "compute_pending_briefings",
]
