"""
Procedure Alias Resolver
========================

Users rarely write the formal EP procedure reference "2025/0429(COD)". They write:
  - a nickname: "AI Act", "DSA", "CSAM Regulation"
  - a descriptive phrase: "ePrivacy Directive extension", "chat control"
  - a partial title: "extension of the temporary derogation"

This module maps any of those forms to a procedure_ref, and tells us which EP
committee leads it. It lets the committee-transcript chatbot path accept
natural-language queries instead of requiring the user to type "LIBE" and
"2025/0429(COD)".

Source
------
`backend/knowledge_base/institutions/procedure_aliases.json` — curated for the
highest-profile files. Not exhaustive; intended to cover the legislative files
that users actually discuss day-to-day. New files are added as they surface in
/morning briefs or user queries.

API
---
- `resolve_procedure(query)` -> Optional[dict] — best single match, or None.
  Returns {procedure_ref, lead_committee, title, matched_alias}.
- `find_procedure_matches(query)` -> list[dict] — every alias occurrence in
  order, with spans (useful for future HTML annotation).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_ALIASES_PATH = (
    Path(__file__).resolve().parents[2]
    / "knowledge_base"
    / "institutions"
    / "procedure_aliases.json"
)

_PROCEDURE_REF_PATTERN = re.compile(r"\b\d{4}/\d{4}\s*\([A-Z]{2,4}\)")


@dataclass
class ProcedureHit:
    raw: str
    start: int
    end: int
    alias: str
    procedure_ref: str
    lead_committee: str
    title: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@lru_cache(maxsize=1)
def _load_procedures() -> dict[str, dict[str, Any]]:
    """Load procedure_aliases.json. Returns empty dict if file missing."""
    try:
        with _ALIASES_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {}
    return data.get("procedures") or {}


@lru_cache(maxsize=1)
def _compiled_patterns() -> list[tuple[re.Pattern[str], str, str]]:
    """
    Build (pattern, alias, procedure_ref) tuples sorted longest-alias-first
    so multi-word names beat their prefixes ("Digital Services Act" beats
    "Digital").

    All aliases are matched case-insensitively with word boundaries that
    tolerate punctuation but reject mid-word matches.
    """
    entries: list[tuple[re.Pattern[str], str, str]] = []
    for proc_ref, payload in _load_procedures().items():
        aliases = payload.get("aliases") or []
        for alias in aliases:
            if len(alias) < 3:
                continue
            # Word-boundary aware pattern, case-insensitive.
            # (?<![A-Za-z0-9]) / (?![A-Za-z0-9]) avoid matching inside longer words.
            pattern = re.compile(
                rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",
                re.IGNORECASE,
            )
            entries.append((pattern, alias, proc_ref))
    entries.sort(key=lambda e: -len(e[1]))
    return entries


def find_procedure_matches(text: str) -> list[ProcedureHit]:
    """Return every alias occurrence in `text`, longest-first, de-overlapped."""
    if not text:
        return []
    procs = _load_procedures()
    patterns = _compiled_patterns()

    hits: list[ProcedureHit] = []
    for pat, alias, proc_ref in patterns:
        payload = procs[proc_ref]
        for m in pat.finditer(text):
            hits.append(
                ProcedureHit(
                    raw=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    alias=alias,
                    procedure_ref=proc_ref,
                    lead_committee=payload.get("lead_committee", ""),
                    title=payload.get("title", ""),
                )
            )

    # De-overlap: keep longest (already sorted longest-alias-first above, so
    # iterate in that order and drop shorter overlapping hits).
    hits.sort(key=lambda h: (h.start, -(h.end - h.start)))
    kept: list[ProcedureHit] = []
    for c in hits:
        if any(not (c.end <= k.start or c.start >= k.end) for k in kept):
            continue
        kept.append(c)
    kept.sort(key=lambda h: h.start)
    return kept


def resolve_procedure(query: str) -> Optional[dict[str, Any]]:
    """
    Best-effort resolution: return a single procedure match for a user query.

    Order of precedence:
      1. Explicit procedure_ref in the query ("2025/0429(COD)").
      2. First alias hit (longest-first ordering means the most specific
         nickname wins).
      3. None.
    """
    if not query:
        return None

    m = _PROCEDURE_REF_PATTERN.search(query)
    if m:
        proc_ref = m.group(0).replace(" ", "")
        payload = _load_procedures().get(proc_ref, {})
        return {
            "procedure_ref": proc_ref,
            "lead_committee": payload.get("lead_committee", ""),
            "title": payload.get("title", ""),
            "matched_alias": proc_ref,
            "source": "explicit_ref",
        }

    hits = find_procedure_matches(query)
    if not hits:
        return None
    top = hits[0]
    return {
        "procedure_ref": top.procedure_ref,
        "lead_committee": top.lead_committee,
        "title": top.title,
        "matched_alias": top.alias,
        "source": "alias",
    }


def extract_topic_keywords(query: str, min_len: int = 4) -> list[str]:
    """
    Pull content words from the query for fallback full-text search against
    transcript titles and text. Drops stop words and transcript-intent phrases
    that would otherwise poison the match.
    """
    if not query:
        return []
    stop_words = {
        "what", "when", "where", "which", "whose", "whom", "why", "how",
        "the", "and", "for", "about", "with", "from", "into", "onto",
        "that", "this", "these", "those", "there", "their",
        "was", "were", "been", "being", "have", "has", "had",
        "said", "say", "says", "told", "tells", "tell", "heard", "hear",
        "spoke", "speak", "spoken", "talk", "talked", "discussed", "discuss",
        "committee", "subcommittee", "meeting", "hearing", "transcript",
        "please", "could", "would", "should", "tell", "show", "give",
        "last", "this", "next", "week", "month", "year", "today",
    }
    # Drop punctuation, keep hyphens inside words
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9\-']+", query.lower())
    return [t for t in tokens if len(t) >= min_len and t not in stop_words]
