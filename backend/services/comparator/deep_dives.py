"""
Brubru deep-dive mapping (procedure ref + CELEX -> deep-dive URL).

Source of truth lives in `frontend/src/utils/deep_dive_map.ts`. This module
is the Python mirror used by /search, /my-files, /resolve, and any future
backend surface that needs to remind users a Brubru deep-dive exists for a
given law.

Keep this list in sync manually until we wire a build-time exporter.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional, TypedDict


_BRUBRU_BASE = "https://brubru.beresol.eu"


class DeepDive(TypedDict):
    short_title: str
    title: str
    com_reference: Optional[str]
    procedure_ref: Optional[str]
    base_path: str
    celex_candidates: List[str]


# 8 deep-dives, mirrored from frontend/src/utils/deep_dive_map.ts (May 2026)
DEEP_DIVES: List[DeepDive] = [
    {
        "short_title": "EU Inc.",
        "title": "EU Inc. — the 28th Regime for European Companies",
        "com_reference": "COM(2026) 321",
        "procedure_ref": "2026/0074(COD)",
        "base_path": "/eu-inc",
        "celex_candidates": ["52026PC0321"],
    },
    {
        "short_title": "Biotech Act",
        "title": "European Biotech Act",
        "com_reference": "COM(2025) 1022",
        "procedure_ref": "2025/0406(COD)",
        "base_path": "/biotech-act",
        "celex_candidates": ["52025PC1022"],
    },
    {
        "short_title": "Industrial Accelerator",
        "title": "Industrial Accelerator Act",
        "com_reference": "COM(2026) 100",
        "procedure_ref": "2026/0068(COD)",
        "base_path": "/industrial-accelerator-act",
        "celex_candidates": ["52026PC0100"],
    },
    {
        "short_title": "Late Payments",
        "title": "Late Payments Regulation",
        "com_reference": "COM(2023) 533",
        "procedure_ref": "2023/0323(COD)",
        "base_path": "/late-payments",
        "celex_candidates": ["52023PC0533"],
    },
    {
        "short_title": "EU Pharma Laws",
        "title": "EU Pharmaceutical Laws — The Complete Framework",
        "com_reference": "COM(2023) 192 + COM(2023) 193",
        "procedure_ref": "2023/0131(COD)",
        "base_path": "/pharma-laws",
        "celex_candidates": ["52023PC0192", "52023PC0193"],
    },
    {
        "short_title": "Digital Networks Act",
        "title": "Digital Networks Act — Rewiring Europe's Telecoms",
        "com_reference": "COM(2026) 16",
        "procedure_ref": "2026/0013(COD)",
        "base_path": "/digital-networks-act",
        "celex_candidates": ["52026PC0016"],
    },
    {
        "short_title": "CSAM Regulation",
        "title": "CSAM Regulation — Combating Child Sexual Abuse Online",
        "com_reference": "COM(2022) 209",
        "procedure_ref": "2022/0155(COD)",
        "base_path": "/csam-regulation",
        "celex_candidates": ["52022PC0209"],
    },
    {
        "short_title": "EU-Andorra Agreement",
        "title": "EU-Andorra Association Agreement",
        "com_reference": "COM(2024) 191",
        "procedure_ref": "2024/0102(NLE)",
        "base_path": "/legislacio-ue-catala/eu-andorra",
        "celex_candidates": ["52024PC0191"],
    },
]


# Index built once at import time
_BY_PROCEDURE: Dict[str, DeepDive] = {dd["procedure_ref"]: dd for dd in DEEP_DIVES if dd.get("procedure_ref")}
_BY_CELEX: Dict[str, DeepDive] = {}
for _dd in DEEP_DIVES:
    for _c in _dd.get("celex_candidates") or []:
        _BY_CELEX[_c] = _dd


def deep_dive_url(base_path: str, lang: str = "en") -> str:
    """Build the canonical deep-dive URL. EN renders at /<base>/index.html;
    other languages render at /<base>/<lang>.html (per the existing layout
    in frontend/public/<base>/{ca,es,fr,it,nl}.html)."""
    if lang == "en" or not lang:
        return f"{_BRUBRU_BASE}{base_path}/index.html"
    return f"{_BRUBRU_BASE}{base_path}/{lang}.html"


def deep_dive_for_file_ref(file_ref: str, celex_candidates: Optional[List[str]] = None) -> Optional[Dict[str, str]]:
    """Return a deep-dive descriptor for a Comparator file_ref.

    The file_ref may be either an OEIL procedure ref ('2026/0074(COD)') or a
    CELEX ('52026PC0321' / '32016R0679'). We also accept the carriage's own
    `celex_numbers` list so OEIL refs whose proposal CELEX matches one of
    the deep-dive entries are resolved correctly.
    """
    if not file_ref:
        return None
    candidates: List[str] = []
    if file_ref:
        candidates.append(file_ref)
    if celex_candidates:
        candidates.extend(celex_candidates)

    for cand in candidates:
        if cand in _BY_PROCEDURE:
            dd = _BY_PROCEDURE[cand]
            return {
                "short_title": dd["short_title"],
                "title": dd["title"],
                "url": deep_dive_url(dd["base_path"], "en"),
            }
        if cand in _BY_CELEX:
            dd = _BY_CELEX[cand]
            return {
                "short_title": dd["short_title"],
                "title": dd["title"],
                "url": deep_dive_url(dd["base_path"], "en"),
            }
    return None
