"""
Policy taxonomy API.

Serves the canonical Brubru policy-interest taxonomy (9 categories / 34
policy-area leaves) from knowledge_base/policy_taxonomy.json. This is the
SINGLE SOURCE OF TRUTH consumed by the frontend policy selector
(policy_preferences_selector.tsx) and injected into the Chat context for
policy-interest navigation queries. Keeping one file means the selector and
the chatbot can never drift on which leaves are actually selectable.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/policy-taxonomy", tags=["Policy Taxonomy"])

_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[1] / "knowledge_base" / "policy_taxonomy.json"
)


@lru_cache(maxsize=1)
def load_taxonomy() -> dict:
    """Load and cache the canonical taxonomy JSON (read once per process)."""
    with _TAXONOMY_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)


@router.get(
    "",
    summary="Get the list of EU policy areas you can follow",
    description=(
        "**What it does**\n"
        "Returns the full list of EU policy areas you can pick as your "
        "interests, grouped into plain-language categories (for example "
        "'Agriculture and Natural Resources' or 'Digital Transformation').\n\n"
        "**When to use it**\n"
        "To show or search the policy-area picker, or to check which areas "
        "exist before tagging a file or filtering your bubble.\n\n"
        "**Input**\n"
        "None.\n\n"
        "**Try it**\n"
        "Open it directly in your browser; no sign-in needed.\n\n"
        "**You get back**\n"
        "A set of categories, each with its policy areas. Every area has a "
        "name, a one-line description, and search keywords (so typing "
        "'drones' or 'refugees' finds the right area)."
    ),
)
def get_policy_taxonomy() -> dict:
    """Return the canonical policy taxonomy (categories -> policy areas)."""
    return load_taxonomy()
