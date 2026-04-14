"""
Law Alias Resolver
==================

Users rarely write "32016R0679". They write:
  - an acronym: GDPR, DSA, DMA, CRR, Solvency II
  - a nickname: "AI Act", "Chips Act", "EU Inc"
  - a vague description: "the data protection regulation", "that law about AI"
  - a copy-pasted full title: "Regulation of the European Parliament and of the Council (EU) 2024/1689..."

This module maps any of those forms to a CELEX so that every Brubru feature
(cross-reference resolver, recital-article linker, definition store, chatbot
context builder) can resolve citations the way users actually write them.

Sources
-------
1. `backend/knowledge_base/institutions/legislation_acronyms.json`
   (auto-extracted from the LEG_2025-11 corpus, ~670 entries; some noisy)
2. `backend/knowledge_base/institutions/legislation_acronyms_manual.json`
   (Brubru-curated well-known acronyms and nicknames; authoritative overrides)

The manual file wins on conflicts. The combined map is cached for the life of
the process.

API
---
- `resolve_alias(text)` -> Optional[dict] — exact match of a single token
  (case-sensitive for short acronyms; case-insensitive for nicknames)
- `find_alias_matches(text)` -> list[AliasHit] — all alias occurrences in text,
  with span offsets suitable for HTML annotation
- `resolve_law_reference(text)` -> Optional[str] CELEX — main helper used by
  chatbot path: takes a free-form user query, returns the best CELEX match,
  or None

Design choices
--------------
- We do NOT implement fuzzy title matching here (would need embeddings and
  would slow down the chatbot hot path). Instead we route vague queries
  ("the data protection regulation") through the knowledge-guide trigger
  system that already exists in `knowledge_base/knowledge_loader.py`.
- Short acronyms (<=4 chars, e.g. GDPR, DSA, DMA, CBAM) are matched with
  strict word boundaries and remain case-sensitive to avoid false positives
  like "dsa" appearing inside "usage". Longer forms (nicknames, multiword
  names) are case-insensitive.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_INSTITUTIONS_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / "institutions"
_AUTO_PATH = _INSTITUTIONS_DIR / "legislation_acronyms.json"
_MANUAL_PATH = _INSTITUTIONS_DIR / "legislation_acronyms_manual.json"


@dataclass
class AliasHit:
    raw: str
    start: int
    end: int
    alias: str
    celex: str
    full_title: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@lru_cache(maxsize=1)
def _load_acronyms() -> dict[str, dict[str, Any]]:
    """Merge the two JSON files, manual wins."""
    combined: dict[str, dict[str, Any]] = {}

    def _merge(path: Path) -> None:
        try:
            with path.open(encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            return
        entries = data.get("acronyms") or {}
        for alias, payload in entries.items():
            celex = (payload or {}).get("celex")
            if not celex:
                continue
            combined[alias] = {
                "celex": celex,
                "full_title": payload.get("full_title", ""),
                "type": payload.get("type", ""),
                "year": payload.get("year"),
                "full_name": payload.get("full_name", alias),
            }

    _merge(_AUTO_PATH)
    _merge(_MANUAL_PATH)  # manual wins
    return combined


def resolve_alias(alias: str) -> Optional[dict[str, Any]]:
    """Exact lookup (case-sensitive for short acronyms, else case-insensitive)."""
    m = _load_acronyms()
    # Try exact match first
    hit = m.get(alias)
    if hit:
        return hit
    # Case-insensitive fallback for multiword names (nicknames)
    if " " in alias or len(alias) > 6:
        low = alias.lower()
        for k, v in m.items():
            if k.lower() == low:
                return v
    return None


@lru_cache(maxsize=1)
def _compiled_patterns() -> list[tuple[re.Pattern[str], str]]:
    """
    Build per-alias regexes, sorted longest-first so multi-word nicknames
    ("Critical Raw Materials Act") win over their prefixes.

    Short acronyms (ALL-CAPS, <=6 chars): case-SENSITIVE, word-boundary-strict,
    to avoid matching "dsa" inside "usage". Long/multiword: case-insensitive.
    """
    entries = []
    for alias in _load_acronyms().keys():
        # Skip single-letter or overly short aliases that would match noise
        if len(alias) < 3:
            continue
        # Skip super-common false positives
        if alias.upper() in {"EC", "EU", "EEC", "EEA"}:
            continue
        short_acronym = (
            len(alias) <= 6
            and " " not in alias
            and alias == alias.upper()
            and alias.isalnum()
        )
        if short_acronym:
            pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])")
        else:
            # Allow leading "the ", tolerate plural/possessive apostrophe
            pattern = re.compile(
                rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])",
                re.IGNORECASE,
            )
        entries.append((pattern, alias))
    # Longest alias first so "Critical Raw Materials Act" beats "Act"
    entries.sort(key=lambda e: -len(e[1]))
    return entries


def find_alias_matches(text: str) -> list[AliasHit]:
    """
    Return every alias occurrence in `text`, in text order.
    Overlapping matches are resolved in favour of the longest alias.
    """
    if not text:
        return []
    map_ = _load_acronyms()
    patterns = _compiled_patterns()

    # Pass 1: collect candidate spans
    candidates: list[AliasHit] = []
    for pat, alias in patterns:
        payload = map_[alias]
        for m in pat.finditer(text):
            candidates.append(
                AliasHit(
                    raw=m.group(0),
                    start=m.start(),
                    end=m.end(),
                    alias=alias,
                    celex=payload["celex"],
                    full_title=payload.get("full_title", ""),
                )
            )

    # Pass 2: deduplicate overlaps. Because patterns was sorted longest-first,
    # earlier candidates are longer; keep them and drop overlapping shorter ones.
    candidates.sort(key=lambda h: (h.start, -(h.end - h.start)))
    kept: list[AliasHit] = []
    for c in candidates:
        if any(not (c.end <= k.start or c.start >= k.end) for k in kept):
            continue
        kept.append(c)
    kept.sort(key=lambda h: h.start)
    return kept


def resolve_law_reference(query: str) -> Optional[str]:
    """
    Best-effort: return a single CELEX for the law the user is talking about.

    Rules (applied in order):
    1. If the query contains an explicit CELEX (e.g. "32016R0679"), return it.
    2. If find_alias_matches returns at least one hit, return the first hit's CELEX.
    3. Otherwise, return None.

    Intentionally conservative: never guesses from a vague description
    ("the data protection regulation"). Those go through the knowledge-guide
    trigger system, not this resolver.
    """
    if not query:
        return None
    # CELEX pattern: 3YYYY[R|L|D|H][NNNN]
    m = re.search(r"\b3\d{4}[RLDHCB]\d{4}\b", query)
    if m:
        return m.group(0)
    hits = find_alias_matches(query)
    if hits:
        return hits[0].celex
    return None


def find_aliases_with_celex(text: str) -> dict[str, str]:
    """
    Returns {alias: celex} for every unique alias found in text.
    Useful for the chatbot context builder when one query can touch several
    laws (e.g. "how does GDPR interact with DSA Article 17?").
    """
    out: dict[str, str] = {}
    for hit in find_alias_matches(text):
        if hit.alias not in out:
            out[hit.alias] = hit.celex
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Resolve law aliases to CELEX numbers")
    ap.add_argument("text", nargs="+", help="Query or text to resolve")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    text = " ".join(args.text)
    hits = find_alias_matches(text)
    if args.json:
        print(json.dumps([h.to_dict() for h in hits], indent=2, ensure_ascii=False))
        return 0
    print(f"Found {len(hits)} aliases")
    for h in hits:
        print(f"  [{h.start:>3}-{h.end:>3}] {h.alias:<30} -> {h.celex}  {h.full_title[:70]}")
    best = resolve_law_reference(text)
    print(f"\nresolve_law_reference -> {best}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
