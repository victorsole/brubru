"""What a CELEX number says about itself: sector, year, descriptor, number, and the act a corrigendum corrects.

One copy for every reader (the LEG_2026-10 table builder, the laws API): the labels are the Publications Office's
tables "Types of documents in EUR-Lex" and "CELEX numbers", as read on 13 Oct 2026 into
knowledge_base/guides/celex_number_format.md. A CELEX carries sector (1 character) + year (4) + descriptor (1 to 3
letters) + number (4 to 6 digits), then optional suffixes: (NN) a further document under the same number, R(NN) a
corrigendum, -YYYYMMDD a consolidated version (sector 0).
"""
from __future__ import annotations

import re
from typing import Optional

SECTORS = {
    "1": "Treaties", "2": "International agreements", "3": "Legal acts", "4": "Complementary legislation",
    "5": "Preparatory documents", "6": "EU case-law", "7": "National transposition measures",
    "8": "National case-law", "9": "Parliamentary questions", "0": "Consolidated texts",
    "C": "OJ C series", "E": "EFTA documents",
}

# EUR-Lex "Types of documents in EUR-Lex", sector 3 and the sector-2 and sector-5 descriptors in the LEG_2026-10 export.
TYPE_LABELS = {
    ("3", "A"): "Opinion", ("3", "B"): "Budget", ("3", "C"): "Declaration", ("3", "D"): "Decision",
    ("3", "E"): "CFSP act (common position, joint action, common strategy)",
    ("3", "F"): "Police and judicial cooperation in criminal matters act",
    ("3", "G"): "Resolution", ("3", "H"): "Recommendation",
    ("3", "J"): "Non-opposition to a notified joint venture", ("3", "K"): "ECSC recommendation",
    ("3", "L"): "Directive", ("3", "M"): "Non-opposition to a notified concentration",
    ("3", "O"): "ECB guideline", ("3", "Q"): "Institutional arrangement",
    ("3", "R"): "Regulation", ("3", "S"): "ECSC decision of general interest",
    ("3", "X"): "Other document published in OJ L", ("3", "Y"): "Other document published in OJ C",
    ("5", "XG"): "Other document of the Council or the Member States",
    ("2", "A"): "Agreement with a non-member State or international organisation",
    ("2", "D"): "Act of a body created by an international agreement",
    ("2", "P"): "Act of a parliamentary body created by an international agreement",
    ("2", "X"): "Other act (international agreements)",
}

CELEX_RE = re.compile(r"^(?P<s>[0-9CE])(?P<y>\d{4})(?P<t>[A-Z]{1,3})(?P<n>\d{4,6})")
CORR_RE = re.compile(r"(?:R\(\d{2}\))+$")


def base_of(c: str) -> str:
    """CELEX without a corrigendum suffix R(NN); a plain (NN) is a different act and stays; a
    consolidated text (sector 0, -YYYYMMDD) maps to its sector-3 act."""
    if c.startswith("0"):
        c = "3" + c[1:]
    return CORR_RE.sub("", re.sub(r"-\d{8}$", "", c))


def celex_info(celex: Optional[str]) -> dict:
    """The parts a CELEX states: sector (+ name), year, document type code (+ EUR-Lex label), number, and for a
    corrigendum the CELEX of the act it corrects. Every value None when the string has no CELEX shape."""
    out = {"sector": None, "sector_name": None, "year": None, "document_type_code": None, "document_type": None,
           "number": None, "corrected_act": None}
    m = CELEX_RE.match(celex or "")
    if not m:
        return out
    s, t = m["s"], m["t"]
    out.update(sector=s, sector_name=SECTORS.get(s), year=int(m["y"]), document_type_code=t,
               document_type=TYPE_LABELS.get((s, t)), number=int(m["n"]))
    if CORR_RE.search(celex):
        out["corrected_act"] = CORR_RE.sub("", celex)
    return out


def type_codes_for(value: str) -> list:
    """(sector, code) pairs a document_type filter names: a code (R, XG) or an EUR-Lex label (regulation)."""
    v = (value or "").strip()
    if not v:
        return []
    by_label = [k for k, label in TYPE_LABELS.items() if label.lower() == v.lower()]
    if by_label:
        return by_label
    code = v.upper()
    known = [k for k in TYPE_LABELS if k[1] == code]
    # a descriptor with no label here (PC, DC, SC...) matches in any sector: (None, code)
    return known or ([(None, code)] if re.fullmatch(r"[A-Z]{1,3}", code) else [])
