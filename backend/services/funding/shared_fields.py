"""The funding standard's shared fields (Phase 2 step 3, 28 Oct 2026).

Every funding item carries item_type, title, summary, status, body_code, body_name and amount_eur,
null where the item has no such thing. Victor's choices of 28 Oct: the item_type values already in
use, and a summary cut from the item's own text where a list had none. Here, not in the v2 funding
package, so the v1 handlers behind the F&T and TED routes can use it without an import cycle.
"""
from __future__ import annotations

import html
import re
import time
from typing import Dict, Iterable, Optional

from sqlalchemy import text

SUMMARY_CHARS = 300
_TAG = re.compile(r"<[a-zA-Z/][^>]*>")


def cut_summary(source: Optional[str], limit: int = SUMMARY_CHARS) -> Optional[str]:
    """The item's own text as a summary: whitespace collapsed, cut at the last word end before `limit`
    characters and closed with an ellipsis when cut."""
    if not source:
        return None
    # Some buyers type HTML into a plain-text field (88 of 65,676 TED descriptions, 28 Oct 2026): the
    # summary is plain text, the body keeps what was published.
    s = " ".join(html.unescape(_TAG.sub(" ", str(source))).split())
    if len(s) <= limit:
        return s or None
    cut = s[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return (cut or s[:limit]) + "\u2026"


# The funds are not bodies in economy_bodies: their lists and /funding/all name them by lower(fund) of
# the finance tables (body=erdf), so the cohesion outcomes of ESF+ and Interreg use the same codes.
FUND_NAMES = {
    "erdf": "European Regional Development Fund",
    "esf": "European Social Fund Plus",
    "cf": "Cohesion Fund",
    "jtf": "Just Transition Fund",
    "interreg": "Interreg (European Territorial Cooperation)",
    "emfaf": "European Maritime, Fisheries and Aquaculture Fund",
    "amif": "Asylum, Migration and Integration Fund",
    "isf": "Internal Security Fund",
    "eagf": "European Agricultural Guarantee Fund",
    "eafrd": "European Agricultural Fund for Rural Development",
    "eusf": "European Union Solidarity Fund",
}

_BODY_NAMES: Dict[str, str] = {}
_BODY_NAMES_READ_AT: Optional[float] = None


def body_names(db, codes: Iterable[Optional[str]]) -> Dict[str, Optional[str]]:
    """code -> name: the funds from FUND_NAMES, every other body from economy_bodies (read once per
    process, and again when a code is missing, at most every 15 minutes)."""
    global _BODY_NAMES_READ_AT
    codes = {c for c in codes if c}
    missing = {c for c in codes if c not in FUND_NAMES and c not in _BODY_NAMES}
    if missing and (_BODY_NAMES_READ_AT is None or time.monotonic() - _BODY_NAMES_READ_AT > 900):
        _BODY_NAMES_READ_AT = time.monotonic()
        for r in db.execute(text("SELECT code, name FROM economy_bodies")).fetchall():
            code, name = getattr(r, "code", None), getattr(r, "name", None)
            if isinstance(code, str) and isinstance(name, str):
                _BODY_NAMES[code] = name
    return {c: FUND_NAMES.get(c) or _BODY_NAMES.get(c) for c in codes}


def with_body_names(db, items: list) -> list:
    """Fill body_name on every item (a model or a dict) from its body_code."""
    names = body_names(db, [(i.get("body_code") if isinstance(i, dict) else getattr(i, "body_code", None)) for i in items])
    for i in items:
        if isinstance(i, dict):
            i["body_name"] = names.get(i.get("body_code"))
        else:
            i.body_name = names.get(getattr(i, "body_code", None))
    return items


def eur(amount, currency: Optional[str]) -> Optional[float]:
    """amount_eur until step 6 (ECB rates): the amount when it is already in euros, else null."""
    if amount is None or (currency or "").strip().upper() != "EUR":
        return None
    return float(amount)
