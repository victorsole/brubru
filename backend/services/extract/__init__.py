"""EU extract engine (Phase 1) — input-first: any EU URL -> structured 5-datapoint Items.

classify (URL -> platform) -> fetch (anti-bot escalation) -> parse (platform handler).
Config-driven from config/platform_profiles.json (the taxonomy as data).
"""
from .engine import extract, classify  # noqa: F401
