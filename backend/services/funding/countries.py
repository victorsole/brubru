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
def _codes() -> dict:
    return json.loads(_CONFIG.read_text())["codes"]


@lru_cache(maxsize=1)
def _tables():
    codes = _codes()
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


def alpha3_code(code: Optional[str]) -> Optional[str]:
    """The EU style code for an ISO alpha-3 code, as eForms (TED) writes a country: GRC -> EL."""
    if not code:
        return None
    c = code.strip().upper()
    return next((entry.get("eu_code") or alpha2 for alpha2, entry in _codes().items() if entry.get("alpha3") == c), None)


def country_code(name: Optional[str]) -> Optional[str]:
    """The EU style code for an English country name, as FTS writes it; None when not in the table."""
    if not name:
        return None
    return _tables()[1].get(_fold(name))


# The VAT number formats (VIES), by prefix; HU's 11 digits are its full tax number, VAT the first 8.
_VAT_PREFIX = {"EL": "EL", "UK": "GB"}
_VAT_FORMATS = {
    "AT": r"U\d{8}", "BE": r"[01]\d{9}", "BG": r"\d{9,10}", "CY": r"\d{8}[A-Z]", "CZ": r"\d{8,10}",
    "DE": r"\d{9}", "DK": r"\d{8}", "EE": r"\d{9}", "EL": r"\d{9}", "ES": r"[A-Z0-9]\d{7}[A-Z0-9]",
    "FI": r"\d{8}", "FR": r"[A-HJ-NP-Z0-9]{2}\d{9}", "HR": r"\d{11}", "HU": r"\d{8}(\d{3})?",
    "IE": r"\d[A-Z0-9+*]\d{5}[A-Z]{1,2}", "IT": r"\d{11}", "LT": r"\d{9}|\d{12}", "LU": r"\d{8}",
    "LV": r"\d{11}", "MT": r"\d{8}", "NL": r"\d{9}B\d{2}", "PL": r"\d{10}", "PT": r"\d{9}", "RO": r"\d{2,10}",
    "SE": r"\d{12}", "SI": r"\d{8}", "SK": r"\d{10}", "GB": r"\d{9}|\d{12}", "NO": r"\d{9}(MVA)?",
}


def vat_number(company_id: Optional[str], country: Optional[str]) -> Optional[str]:
    """A company identifier as a VAT key, only when it is shaped like its own country's VAT number
    (with or without the prefix): TED's company ids are VAT, register or tax numbers ("J03/610/2003",
    a Madrid register entry), and only a VAT number may join the CORDIS and FTS VAT keys."""
    k, cc = vat_key(company_id), eu_code(country)
    if not k or not cc:
        return None
    prefix = _VAT_PREFIX.get(cc, cc)
    pattern = _VAT_FORMATS.get(prefix)
    if pattern is None:
        return None
    # A label written before the number ("VAT ESB09707217", "NIP 5260250995").
    k = re.sub(r"^(VAT|TVA|IVA|BTW|NIF|CIF|NIP|UID|USTIDNR|MWST|MOMS|ALV|PVM|DIC|DDV|OIB|PIVA)(?=[A-Z0-9]{6})", "", k)
    if cc == "EL" and k.startswith("GR"):
        k = "EL" + k[2:]
    if k.startswith(prefix):
        body = k[len(prefix):]
    elif k[:2].isalpha():
        return None          # another country's prefix, or a register code
    else:
        body = k
    if not re.fullmatch(pattern, body):
        return None
    return prefix + (body[:8] if prefix == "HU" else body)


def vat_key(vat: Optional[str]) -> Optional[str]:
    """A VAT number as a join key: upper case, letters and digits only; None when nothing is left."""
    if not vat:
        return None
    k = re.sub(r"[^A-Za-z0-9]", "", vat).upper()   # as scripts/refresh_org_identities.py does in SQL
    return k or None
