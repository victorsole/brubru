"""
Amendment fidelity validation -- deterministic, no-LLM checks on AI output.

The Amendator's AI suggestion endpoints (/suggest, /suggest-batch) previously
returned model output verbatim with no fidelity check. That let three quality
defects through unnoticed:

  1. Fabricated "original" -- the model paraphrases the article it claims to
     quote, so the user reviews a diff against a baseline that never existed.
  2. Scope creep -- the model rewrites a whole paragraph when the policy goal
     asked for a one-clause tweak.
  3. Phantom references -- the proposed text cites "Article 17a" where no 17a
     exists in the loaded law.

These three checks are pure functions over data the endpoint already holds
(the real element text and the document's article-number set), so they run
server-side with zero extra LLM latency. Results are surfaced to the user as
per-suggestion badges; they never block a suggestion -- the user adjudicates.

The fourth layer (policy-alignment), which genuinely needs an LLM, is kept out
of this module on purpose: this file stays deterministic and unit-testable.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import List, Set

# A reference to "Article N" / "Article 17a" NOT immediately followed by "of"
# (an "Article 6 of Regulation (EU) 2016/679" points to another act, not this
# document, so we must not treat it as an internal phantom reference).
_INTERNAL_ARTICLE_REF_RE = re.compile(
    r"\bArticle\s+(\d+[a-z]?)\b(?!\s+of\b)",
    re.IGNORECASE,
)

# Closeness threshold above which the model's returned "original" is considered
# a faithful echo of the real element text. Below it, the model paraphrased.
_ORIGINAL_MATCH_THRESHOLD = 0.85

# Word-change fraction above which we warn the user about scope creep.
_SCOPE_CREEP_THRESHOLD = 0.6


def _norm(text: str) -> str:
    """Lowercase, collapse whitespace -- for tolerant comparison."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def verify_original(returned_original: str, actual_text: str) -> bool:
    """
    True if the AI-returned original matches the loaded element text closely.

    Exact match after normalisation -> True. Otherwise a token-ratio fallback
    tolerates trivial punctuation/whitespace noise but catches paraphrase.
    """
    a = _norm(returned_original)
    b = _norm(actual_text)
    if not a or not b:
        return False
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= _ORIGINAL_MATCH_THRESHOLD


def scope_ratio(original: str, proposed: str) -> float:
    """
    Fraction of the original that changed, 0.0 (identical) .. 1.0 (rewritten),
    computed at word granularity. A suppression (empty proposed) is 1.0.
    """
    o = _norm(original).split()
    p = _norm(proposed).split()
    if not o:
        return 1.0 if p else 0.0
    ratio = SequenceMatcher(None, o, p).ratio()
    return round(max(0.0, min(1.0, 1.0 - ratio)), 3)


def find_phantom_references(
    proposed_text: str,
    known_article_numbers: Set[str],
) -> List[str]:
    """
    Internal "Article N" references in the proposed text that do not exist in
    the loaded document's article-number set. References to other acts
    ("... of Regulation (EU) 2016/679") are excluded by the regex.

    `known_article_numbers` must be lowercase, e.g. {"1", "5", "17a"}.
    Returns a sorted, de-duplicated list of the offending numbers.
    """
    if not known_article_numbers:
        # No reliable article set -> cannot judge; return nothing rather than
        # flag every reference as phantom (false positives are worse here).
        return []
    found = {
        m.group(1).lower()
        for m in _INTERNAL_ARTICLE_REF_RE.finditer(proposed_text or "")
    }
    return sorted(n for n in found if n not in known_article_numbers)


def validate_suggestion(
    *,
    returned_original: str,
    actual_text: str,
    proposed_text: str,
    amendment_type: str,
    known_article_numbers: Set[str] | None = None,
) -> dict:
    """
    Run all deterministic fidelity checks on one suggestion.

    Returns a JSON-serialisable dict:
      {
        "original_verified": bool,   # did the model faithfully echo the source?
        "scope_ratio": float,        # 0..1 word-change fraction
        "phantom_references": [str], # internal article refs not in the document
        "flags": [str],              # human-readable warning labels
      }

    Never raises. A suppression skips the scope-creep flag (deleting text is
    100% change by definition and that is the user's explicit intent).
    """
    known = {n.lower() for n in (known_article_numbers or set())}
    original_verified = verify_original(returned_original, actual_text)
    ratio = scope_ratio(actual_text, proposed_text)
    phantoms = find_phantom_references(proposed_text, known)

    flags: List[str] = []
    if not original_verified:
        flags.append("original_mismatch")
    if amendment_type != "suppression" and ratio >= _SCOPE_CREEP_THRESHOLD:
        flags.append("scope_creep")
    if phantoms:
        flags.append("phantom_reference")

    return {
        "original_verified": original_verified,
        "scope_ratio": ratio,
        "phantom_references": phantoms,
        "flags": flags,
    }
