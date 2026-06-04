"""
Have Your Say (HYS) feedback collector - the positions-layer source.

EC "Have Your Say" exposes, per initiative, the public feedback submissions with the
submitting organisation, its Transparency Register number, type, country, language and
the feedback text. We use:
  * brpapi/groupInitiatives/{id}  -> the initiative's publications (+ feedback counts)
  * api/allFeedback?publicationId={pid} -> the submissions (Spring page, items in content[])

Org name + trNumber + feedback text is exactly the "ask" we need for Outcome Alignment.
Stateless HTTP (httpx); stance extraction is done separately via Qwen. NO Anthropic.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_UA = {"User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0)", "Accept": "application/json"}
_BRP = "https://ec.europa.eu/info/law/better-regulation/brpapi/groupInitiatives/{iid}"
_FB = "https://ec.europa.eu/info/law/better-regulation/api/allFeedback?publicationId={pid}&size={size}&page={page}"
_PORTAL = "https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/{iid}"

# Submitter types that represent an organisation (skip private citizens).
ORG_TYPES = {
    "COMPANY", "BUSINESS_ASSOCIATION", "NON_GOVERNMENTAL_ORGANISATION", "NGO",
    "TRADE_UNION", "PUBLIC_AUTHORITY", "ACADEMIC_RESEARCH_INSTITUTION",
    "CONSUMER_ORGANISATION", "ENVIRONMENTAL_ORGANISATION", "EU_CITIZEN_ORGANISATION",
    "OTHER", "TRADE_BUSINESS_ASSOCIATION",
}


def _to_iso(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    m = re.search(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", s)
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


def fetch_initiative(initiative_id: str) -> Optional[Dict]:
    """Return the initiative detail (title, unit/DG, publications with feedback counts)."""
    try:
        r = httpx.get(_BRP.format(iid=initiative_id), headers=_UA, timeout=40, follow_redirects=True)
        if r.status_code == 200:
            return r.json()
        logger.info("[hys] initiative %s -> HTTP %s", initiative_id, r.status_code)
    except Exception as e:
        logger.warning("[hys] initiative fetch failed %s: %s", initiative_id, e)
    return None


def publications_with_feedback(initiative: Dict) -> List[Dict]:
    """Publications that have at least one feedback submission."""
    out = []
    for p in (initiative.get("publications") or []):
        n = p.get("totalFeedback") or p.get("feedbackCount") or 0
        if p.get("id") and n:
            out.append({"id": str(p["id"]), "stage": p.get("frontEndStage"), "count": int(n)})
    return out


def fetch_feedback(publication_id: str, max_items: int = 200) -> List[Dict]:
    """All feedback submissions for a publication (paginated)."""
    items: List[Dict] = []
    page, size = 0, 50
    while len(items) < max_items:
        try:
            r = httpx.get(_FB.format(pid=publication_id, size=size, page=page), headers=_UA, timeout=45)
            if r.status_code != 200:
                break
            d = r.json()
            content = d.get("content") or []
            items.extend(content)
            if d.get("last") is True or not content:
                break
            page += 1
        except Exception as e:
            logger.warning("[hys] feedback fetch failed pub %s p%s: %s", publication_id, page, e)
            break
    return items[:max_items]


def parse_feedback(raw: Dict, initiative_id: str, title: Optional[str], dg: Optional[str],
                   policy_areas: Optional[List[str]], publication_id: str) -> Optional[Dict]:
    """Normalise one HYS feedback submission into a consultation_feedback row dict.
    Returns None for private-citizen submissions (no organisation)."""
    org = (raw.get("organization") or "").strip()
    if not org:
        return None   # private citizen / no organisation -> not a lobbying position
    fid = raw.get("id")
    text = (raw.get("feedback") or "").strip()
    return {
        "initiative_id": initiative_id,
        "publication_id": publication_id,
        "consultation_title": title,
        "dg_responsible": dg,
        "policy_areas": policy_areas or [],
        "organisation": org[:500],
        "transparency_register_id": (raw.get("trNumber") or None),
        "user_type": raw.get("userType"),
        "country": raw.get("country"),
        "language": raw.get("language"),
        "feedback_text": text,                 # consumed by stance extraction, not stored verbatim in full
        "feedback_excerpt": (text[:600] or None),
        "feedback_date": _to_iso(raw.get("dateFeedback")),
        "source_url": (f"{_PORTAL.format(iid=initiative_id)}/F{fid}_en" if fid else _PORTAL.format(iid=initiative_id)),
    }
