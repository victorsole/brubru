"""
Match a lobbying organisation name to its EU Transparency Register record, to
enrich Lobby Meetings (Commission + Parliament) with the org's website, register
profile link, and lobbying metadata.

The register is already ingested (eu_transparency_register, 17.6k rows). We build a
process-cached normalised-name + acronym index once, then match by id (when known),
exact normalised name, or acronym. NO Anthropic.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Optional

from sqlalchemy import text as sqla_text

logger = logging.getLogger(__name__)

_INDEX: Optional[Dict[str, dict]] = None  # norm_name / acronym -> record
_BY_ID: Optional[Dict[str, dict]] = None


def _norm(s: str) -> str:
    s = (s or "").lower().strip()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"\b(aisbl|asbl|gmbh|s\.a\.|sa|ag|ltd|llp|inc|e\.v\.|ev|sarl|bv|nv|plc|se)\b", " ", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _valid_url(u: Optional[str]) -> Optional[str]:
    """Only return well-formed http(s) URLs (be careful what we hyperlink)."""
    if not u:
        return None
    u = u.strip()
    if u.lower().startswith("www."):
        u = "https://" + u
    return u if re.match(r"^https?://", u, re.I) else None


def _record(row) -> dict:
    return {
        "tr_id": row.identification_code,
        "name": row.original_name,
        "website": _valid_url(row.website_url),
        "register_url": _valid_url(row.public_url),
        "category": row.registration_category,
        "country": row.head_office_country,
        "fte": row.members_fte,
        "ep_passes": row.ep_accredited_number,
        "costs_min": row.costs_min,
        "costs_max": row.costs_max,
    }


def _build_index(db):
    global _INDEX, _BY_ID
    _INDEX, _BY_ID = {}, {}
    rows = db.execute(sqla_text(
        "SELECT identification_code, original_name, acronym, website_url, public_url, "
        "registration_category, head_office_country, members_fte, ep_accredited_number, "
        "costs_min, costs_max FROM eu_transparency_register")).fetchall()
    for r in rows:
        rec = _record(r)
        _BY_ID[str(r.identification_code)] = rec
        nm = _norm(r.original_name)
        if nm and nm not in _INDEX:
            _INDEX[nm] = rec
        if r.acronym:
            ac = (r.acronym or "").lower().strip()
            if len(ac) >= 3 and ac not in _INDEX:
                _INDEX[ac] = rec
    logger.info("[tr-match] index built: %d names, %d ids", len(_INDEX), len(_BY_ID))


def match_org(name: Optional[str], db, tr_id: Optional[str] = None) -> Optional[dict]:
    """Return the register record for an org (by id first, then normalised name)."""
    global _INDEX, _BY_ID
    if _INDEX is None:
        try:
            _build_index(db)
        except Exception as e:
            logger.warning("[tr-match] index build failed: %s", e)
            return None
    if tr_id and str(tr_id) in _BY_ID:
        return _BY_ID[str(tr_id)]
    if not name:
        return None
    return _INDEX.get(_norm(name))
