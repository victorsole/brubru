"""
Deterministic policy-area classifier (NO Anthropic).

Maps an EU object (news item, legislative carriage, ...) to canonical PI leaf
names from knowledge_base/policy_taxonomy.json, so every MEUB surface shares the
same `policy_areas` join key. Two signals:

  - body code (Commission DG / EP committee / Council config / agency) -> the
    leaves that list it (crosswalk reverse maps). High confidence.
  - curated `keywords` appearing in the title/summary -> those leaves.

Combination (precision first, honest blank last):
  body ∩ text  -> that intersection      (both agree: most precise)
  text only    -> the text leaves        (text-driven)
  one body leaf-> that leaf               (unambiguous body, e.g. DG AGRI)
  many body    -> all body leaves         (broad body remit, e.g. committee ENVI)
  nothing      -> []                      (leave blank, never force)
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from services.tracking.pi_committee_crosswalk import (
    leaves_for_agency,
    leaves_for_committee,
    leaves_for_council_config,
    leaves_for_dg,
)

_TAXONOMY_PATH = (
    Path(__file__).resolve().parents[2] / "knowledge_base" / "policy_taxonomy.json"
)


@lru_cache(maxsize=1)
def _leaf_patterns() -> List[tuple]:
    """Per leaf: list of (kind, pattern). Single-word keywords match on a LEFT
    word boundary (so 'vat' no longer matches 'innovation', while stems like
    'agricultur' still match 'agricultural'); spaced/padded keywords (e.g.
    ' ai ', 'data act') keep precise substring matching."""
    with _TAXONOMY_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    leaves = [pa for c in data.get("categories", []) for pa in c.get("policy_areas", [])]
    out = []
    for pa in leaves:
        pats = []
        for k in pa.get("keywords", []):
            kl = k.lower()
            if " " in k:  # phrase or space-padded token -> substring as-is
                pats.append(("sub", kl))
            else:         # single token -> left word-boundary
                pats.append(("wb", re.compile(r"\b" + re.escape(kl))))
        out.append((pa["name"], pats))
    return out


def _text_leaves(text: str) -> set:
    t = (text or "").lower()
    res = set()
    for name, pats in _leaf_patterns():
        for kind, p in pats:
            if (kind == "sub" and p in t) or (kind == "wb" and p.search(t)):
                res.add(name)
                break
    return res


def classify(
    title: str,
    summary: str = "",
    *,
    dg: Optional[str] = None,
    committee: Optional[str] = None,
    council_config: Optional[str] = None,
    agency: Optional[str] = None,
) -> List[str]:
    """Return canonical PI leaf names for this object (possibly empty)."""
    text_leaves = _text_leaves(f"{title or ''} {summary or ''}")

    body: set = set()
    for code, fn in (
        (dg, leaves_for_dg),
        (committee, leaves_for_committee),
        (council_config, leaves_for_council_config),
        (agency, leaves_for_agency),
    ):
        if code:
            body |= set(fn(code))

    inter = text_leaves & body
    if inter:
        return sorted(inter)
    if text_leaves:
        return sorted(text_leaves)
    if len(body) == 1:
        return list(body)
    if body:
        return sorted(body)
    return []
