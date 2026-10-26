"""One country code and one VAT key across the funding sources (26 Oct 2026, partner search).

CORDIS writes a country as the EU style code (EL for Greece, UK for the United Kingdom), the F&T
Portal's coordinators as either style (EL 1,985 and GR 455; UK 11,294 and GB 145), and the
Financial Transparency System as an English name (Belgium, Türkiye). config/country_codes.json,
read from the Publications Office's country table, gives every code its EU style code and English
names; everything here answers in the EU style, so the three sources meet on one value.
"""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

_CONFIG = Path(__file__).resolve().parents[2] / "config" / "country_codes.json"


def _fold(s: str) -> str:
    """Case, accents, spacing, a trailing "(the)" and the table's "*" ignored: "Cote d'Ivoire" is
    "Côte d'Ivoire", "Gambia (the)" is "Gambia". A name cut short ("Republ") still matches nothing."""
    s = unicodedata.normalize("NFKD", s.replace("*", "").replace("\u2019", "'"))
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"\s*\((the)\)\s*$", "", s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip().casefold()


@lru_cache(maxsize=1)
def _tables():
    codes = json.loads(_CONFIG.read_text())["codes"]
    eu: Dict[str, str] = {}
    by_name: Dict[str, str] = {}
    for alpha2, entry in codes.items():
        style = entry.get("eu_code") or alpha2
        eu[alpha2] = style
        eu[style] = style
        for name in entry["names"] + entry.get("former_names", []):
            by_name.setdefault(_fold(name), style)
    return eu, by_name


def eu_code(code: Optional[str]) -> Optional[str]:
    """The EU style code for a two-letter code in either style (GR -> EL, GB -> UK)."""
    if not code:
        return None
    c = code.strip().upper()
    return _tables()[0].get(c, c)


def both_styles(code: str) -> List[str]:
    """Every spelling a source may use for this country: ['EL', 'GR'] for Greece."""
    style = eu_code(code)
    return sorted({style, *(a for a, s in _tables()[0].items() if s == style)})


def country_code(name: Optional[str]) -> Optional[str]:
    """The EU style code for an English country name, as FTS writes it; None when not in the table."""
    if not name:
        return None
    return _tables()[1].get(_fold(name))


def vat_key(vat: Optional[str]) -> Optional[str]:
    """A VAT number as a join key: upper case, letters and digits only; None when nothing is left."""
    if not vat:
        return None
    k = re.sub(r"[^A-Za-z0-9]", "", vat).upper()   # as scripts/refresh_org_identities.py does in SQL
    return k or None
