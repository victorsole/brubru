"""
Plain-language names for the machine codes TED and eForms put in our columns.

`tenders.procedure_type` stores eForms codes: "neg-w-call", "comp-dial",
"oth-single". `award_criteria_type` stores "best-value" / "cost" / "price" /
"quality". `contract_nature` stores "works" / "supplies" / "services". These are
internal identifiers from the eForms schema, and they were reaching users
verbatim -- in the Excel exports, in the tender detail's award-criteria line,
and in the block Chat reads before answering.

The frontend already had a good decoder for ONE of the three, and it was
unreachable: PROCEDURE_LABELS_I18N_KEYS lives inside tender_detail.tsx, so the
detail page rendered "Negotiated (with prior call)" while the spreadsheet of the
same tender said "neg-w-call" and Chat was told "Procedure: neg-w-call".

This module is the server-side half of that contract. The frontend keeps its
i18n keys, because its labels must be localised into Brubru's six languages;
this side serves the consumers that render server-side text. A test asserts the
two cover the same set of codes, so they cannot drift apart silently.

Vocabulary follows Directive 2014/24/EU: Articles 26-32 for the procedures,
Article 67 for the award criteria, Article 2(1)(6)-(9) for the contract nature.
"""
from __future__ import annotations

from typing import Dict, Optional

# eForms procedure codes. Keep in step with PROCEDURE_LABELS_I18N_KEYS in
# frontend/src/components/tenders/tender_detail.tsx.
PROCEDURE_TYPES: Dict[str, str] = {
    "open": "Open",
    "restricted": "Restricted",
    "comp-dial": "Competitive dialogue",
    "comp-tend": "Competitive with negotiation",
    "innovation": "Innovation partnership",
    "neg-w-call": "Negotiated (with prior call)",
    "neg-wo-call": "Negotiated (without prior call)",
    "exp-int": "Expression of interest",
    "des-cont": "Design contest",
    "oth-mult": "Other multistage",
    "oth-single": "Other single-stage",
    "open-1step": "Open (single stage)",
    "open-2step": "Open (two stage)",
}

# Directive 2014/24/EU Article 67: the basis on which the contract is awarded.
AWARD_CRITERIA_TYPES: Dict[str, str] = {
    "price": "Lowest price",
    "cost": "Cost (life-cycle costing)",
    "quality": "Quality",
    "best-value": "Best price-quality ratio",
}

# Directive 2014/24/EU Article 2(1)(6)-(9).
CONTRACT_NATURES: Dict[str, str] = {
    "works": "Works",
    "supplies": "Supplies",
    "services": "Services",
}


def _decode(mapping: Dict[str, str], code: Optional[str]) -> Optional[str]:
    """Plain-language name for a code.

    An unknown code comes back AS ITSELF rather than as None or a blank. A code
    we have not mapped yet is still more use to a reader than an empty cell, and
    it surfaces the gap instead of hiding it.
    """
    if not code:
        return None
    return mapping.get(str(code).strip().lower(), str(code))


def procedure_label(code: Optional[str]) -> Optional[str]:
    """e.g. "neg-w-call" -> "Negotiated (with prior call)"."""
    return _decode(PROCEDURE_TYPES, code)


def award_criteria_label(code: Optional[str]) -> Optional[str]:
    """e.g. "best-value" -> "Best price-quality ratio"."""
    return _decode(AWARD_CRITERIA_TYPES, code)


def contract_nature_label(code: Optional[str]) -> Optional[str]:
    """e.g. "supplies" -> "Supplies"."""
    return _decode(CONTRACT_NATURES, code)
