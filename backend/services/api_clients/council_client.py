"""
Council newsroom (tvnewsroom.consilium.europa.eu) discovery client.

The Council audiovisual newsroom exposes a clean JSON API:
  - list:   newsroomapi.consilium.europa.eu/api/homepage/latestvideos
  - detail: newsroomapi.consilium.europa.eu/api/videos/{urlName}  -> formats.videos[]
Each video detail carries direct .mp4 files on cdne-newsroomnew-prd.azureedge.net
(video-files/{uuid}.mp4) — ffmpeg ingests them straight for audio. NO WAF.

Discovery only — returns recording dicts ready to become PENDING
committee_meeting_transcripts rows (institution='COUNCIL').
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

LIST_API = "https://newsroomapi.consilium.europa.eu/api/homepage/latestvideos"
DETAIL_API = "https://newsroomapi.consilium.europa.eu/api/videos/{slug}"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0 Safari/537.36")


def _pick_video(formats: Dict) -> Optional[str]:
    """Pick a transcribable .mp4: prefer the lighter Webcast preview, else any."""
    vids = (formats or {}).get("videos") or []
    if not vids:
        return None
    preview = [v for v in vids if v.get("isPreview") and (v.get("url") or "").endswith(".mp4")]
    if preview:
        return preview[0]["url"]
    mp4 = [v for v in vids if (v.get("url") or "").endswith(".mp4")]
    return mp4[0]["url"] if mp4 else None


def discover_recent(limit: int = 25) -> List[Dict]:
    """Most recent Council newsroom videos with a transcribable .mp4."""
    try:
        import httpx
    except ImportError:
        logger.warning("[COUNCIL] httpx not installed")
        return []
    try:
        with httpx.Client(headers={"User-Agent": _UA}, timeout=30) as c:
            lr = c.get(LIST_API)
            if lr.status_code != 200:
                logger.warning("[COUNCIL] list HTTP %s", lr.status_code)
                return []
            items = lr.json()
            items = items if isinstance(items, list) else (items.get("items") or [])
            out: List[Dict] = []
            for it in items:
                if (it.get("contentTypeAlias") or "").lower() != "video":
                    continue
                urln = it.get("urlName")
                mam = it.get("mamReferenceId")
                if not urln or not mam:
                    continue
                try:
                    dr = c.get(DETAIL_API.format(slug=urln))
                    if dr.status_code != 200:
                        continue
                    detail = dr.json()
                except Exception:
                    continue
                audio = _pick_video(detail.get("formats") or {})
                if not audio:
                    continue
                dt = None
                if detail.get("date"):
                    try:
                        dt = datetime.fromisoformat(detail["date"].replace("Z", ""))
                    except ValueError:
                        dt = None
                out.append({
                    "external_id": f"council-{mam}",
                    "title": (detail.get("title") or it.get("title") or "")[:480],
                    "summary": detail.get("description"),
                    "meeting_date": dt,
                    "audio_url": audio,
                    "duration_seconds": None,
                    "multimedia_url": f"https://tvnewsroom.consilium.europa.eu/video/{urln}",
                    "video_type": detail.get("videoTypeDescription"),
                })
                if len(out) >= limit:
                    break
            return out
    except Exception as e:
        logger.warning("[COUNCIL] discovery failed: %s", e)
        return []
