"""
MEP political-group + country cache.

Authoritative source: the EP MEP profile HTML at
https://www.europarl.europa.eu/meps/en/{mep_id}, which carries the full group
name in `<... class="sln-political-group-name">` and the country in a
neighbouring node. We fetch once per MEP and persist to a JSON cache file
in `backend/data/mep_groups_cache.json`.

The cache is read by the legislative-train key-players endpoint to enrich
entries that OEIL returns with `political_group = None`. No fabrication: if
the EP profile does not advertise a group, we leave the field blank.

Usage:
    from services.mep_groups_cache import enrich_political_group
    p = enrich_political_group({"name": "...", "mep_id": "256831", ...})
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------
# Group full-name -> short-code map (current 10th legislature)
# ----------------------------------------------------------------------------
GROUP_SHORT = {
    "Group of the European People's Party (Christian Democrats)": "EPP",
    "Group of the Progressive Alliance of Socialists and Democrats in the European Parliament": "S&D",
    "Patriots for Europe Group": "PfE",
    "European Conservatives and Reformists Group": "ECR",
    "Renew Europe Group": "Renew",
    "Group of the Greens/European Free Alliance": "Greens/EFA",
    "The Left group in the European Parliament - GUE/NGL": "The Left",
    "Europe of Sovereign Nations Group": "ESN",
    "Non-attached Members": "NI",
}

CACHE_PATH = Path(__file__).parent.parent / "data" / "mep_groups_cache.json"
_LOCK = threading.Lock()
_CACHE: Optional[Dict[str, dict]] = None  # mep_id (str) -> {"political_group": str, "country": str}

_GROUP_RE = re.compile(r'class="[^"]*sln-political-group-name[^"]*"[^>]*>([^<]+)<', re.IGNORECASE)


def _load_cache() -> Dict[str, dict]:
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    with _LOCK:
        if _CACHE is not None:
            return _CACHE
        try:
            if CACHE_PATH.exists():
                _CACHE = json.loads(CACHE_PATH.read_text())
            else:
                _CACHE = {}
        except Exception as e:
            logger.warning(f"mep_groups_cache: failed to load cache file: {e}")
            _CACHE = {}
    return _CACHE


def _persist_cache() -> None:
    cache = _load_cache()
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False, sort_keys=True))
    except Exception as e:
        logger.warning(f"mep_groups_cache: failed to persist cache: {e}")


def _fetch_from_ep(mep_id: str) -> Optional[dict]:
    """Hit the EP profile HTML and return {political_group, country} or None."""
    url = f"https://www.europarl.europa.eu/meps/en/{mep_id}"
    try:
        with httpx.Client(timeout=8.0, follow_redirects=True) as client:
            r = client.get(url)
            if r.status_code != 200:
                return None
            html = r.text
        m = _GROUP_RE.search(html)
        if not m:
            return None
        full = m.group(1).strip()
        short = GROUP_SHORT.get(full, full)
        return {"political_group": short, "country": None}
    except Exception as e:
        logger.debug(f"mep_groups_cache: EP fetch failed for {mep_id}: {e}")
        return None


def lookup(mep_id: Optional[str | int]) -> Optional[dict]:
    """Cached lookup. Returns {political_group, country} or None."""
    if mep_id is None:
        return None
    mid = str(mep_id)
    cache = _load_cache()
    if mid in cache:
        return cache[mid]
    # Skip live-fetch when the env explicitly disables it (test paths).
    if os.environ.get("MEP_GROUPS_OFFLINE") == "1":
        return None
    fetched = _fetch_from_ep(mid)
    if fetched:
        cache[mid] = fetched
        _persist_cache()
    return fetched


def enrich_political_group(player: dict) -> dict:
    """Fill missing political_group in-place when the EP profile knows it."""
    if not player.get("political_group") and player.get("mep_id"):
        looked_up = lookup(player.get("mep_id"))
        if looked_up and looked_up.get("political_group"):
            player["political_group"] = looked_up["political_group"]
    return player
