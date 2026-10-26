"""Programme names for the codes ft_funded_projects stores (26 Oct 2026).

`framework_programme` holds the source's code, not a name: CORDIS writes HORIZON, H2020 and FP7, the
F&T Portal its programme abbreviations (ERASMUS2027, CREA2027, LIFE2027...). The filter was a
substring on that code, so the documented examples (`Horizon Europe`, `Horizon 2020`) matched
nothing. config/ft_programme_codes.json gives each code the portal's own name for it (FP7: CORDIS's).

The filter keeps the substring match on the code, so every value that matches a code today answers
exactly as it did (`HORIZON` stays Horizon Europe only, `CEF` both periods). `named_codes` adds the
codes whose name contains the value, and only for a value that is part of no known code: there a
name search can only turn an empty answer into an answer. Names and values are compared on letters
and digits alone, so `Erasmus+` finds the portal's "Erasmus (ERASMUS)". A code the file does not
know is reported by `unnamed`, which the daily status job prints as degraded.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Optional

_CONFIG = Path(__file__).resolve().parents[2] / "config" / "ft_programme_codes.json"


def _fold(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


@lru_cache(maxsize=1)
def programme_names() -> Dict[str, str]:
    """code -> the portal's name for it."""
    return {code: entry["name"] for code, entry in json.loads(_CONFIG.read_text())["codes"].items()}


def named_codes(value: str) -> List[str]:
    """The codes whose name contains `value`, to add to the substring match on the code; none when
    the value is part of a known code (today's answer stands) or has no letter or digit."""
    folded = _fold(value)
    names = programme_names()
    if not folded or any(value.strip().lower() in code.lower() for code in names):
        return []
    return sorted(code for code, name in names.items() if folded in _fold(name))


def unnamed(codes: Iterable[Optional[str]]) -> List[str]:
    """The stored codes the file gives no name for."""
    names = programme_names()
    return sorted({c for c in codes if c and c not in names})
