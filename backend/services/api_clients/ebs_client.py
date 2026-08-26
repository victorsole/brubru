"""
EbS (Europe by Satellite / audiovisual.ec.europa.eu) discovery client.

The Commission audiovisual service exposes a public search API ("parrotfish")
returning video items, each with `solrVideoFiles` that include an AAC audio-only
track per language (qaa = floor, eng = English). We feed that audio URL straight
to the existing transcription pipeline (ffmpeg + Voxtral/faster-whisper/Whisper) —
no HLS demux needed. NO WAF on the API or the vod CDN.

Discovery only — no DB, no ASR here. Returns recording dicts ready to become
PENDING committee_meeting_transcripts rows (institution='EC').
"""

from __future__ import annotations

import html as _html
import logging
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

SEARCH_API = "https://8hwk2cyeyb.execute-api.eu-west-1.amazonaws.com/parrotfish-prod/search"
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0 Safari/537.36")
_TAG = re.compile(r"<[^>]+>")


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", _html.unescape(_TAG.sub(" ", s or ""))).strip()


def _title(item: Dict) -> str:
    titles = item.get("titles") or []
    en = [t.get("content") for t in titles if (t.get("language") or "").upper() == "EN"]
    pick = en[0] if en else (titles[0].get("content") if titles else "")
    return _clean(pick)


def _audio_url(item: Dict, prefer_lang: str = "EN") -> Optional[str]:
    """Pick the AAC audio-only track: preferred language, else floor/INT, else any."""
    files = [f for f in (item.get("solrVideoFiles") or []) if (f.get("type") or "").upper() == "AAC"]
    if not files:
        return None
    by_lang = {(f.get("language") or "").upper(): f.get("url") for f in files}
    for lang in (prefer_lang.upper(), "INT", "MUL", ""):
        if by_lang.get(lang):
            return by_lang[lang]
    return files[0].get("url")


def discover_recent(limit: int = 40, prefer_lang: str = "EN") -> List[Dict]:
    """Most recently published EbS videos that have a transcribable audio track."""
    try:
        import httpx
    except ImportError:
        logger.warning("[EBS] httpx not installed")
        return []
    params = {
        "mediaType": "VIDEO",
        "sortField": "search_date",
        "sortFieldDirection": "desc",
        "offset": 0,
        "limit": limit,
    }
    try:
        r = httpx.get(SEARCH_API, params=params, headers={"User-Agent": _UA}, timeout=30)
        if r.status_code != 200:
            logger.warning("[EBS] search HTTP %s: %s", r.status_code, r.text[:200])
            return []
        items = r.json().get("items") or []
    except Exception as e:
        logger.warning("[EBS] search failed: %s", e)
        return []

    out: List[Dict] = []
    for it in items:
        audio = _audio_url(it, prefer_lang)
        if not audio:
            continue  # no transcribable audio -> skip
        ref = it.get("reference")
        title = _title(it)
        if not ref or len(title) < 6:
            continue
        # date
        dt = None
        for key in ("startDateTime", "timestamp"):
            v = it.get(key)
            if v:
                try:
                    dt = datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)
                    break
                except ValueError:
                    pass
        summaries = it.get("summaries") or []
        en_sum = [s.get("content") for s in summaries if (s.get("language") or "").upper() == "EN"]
        out.append({
            "external_id": f"ebs-{ref}",
            "reference": ref,
            "title": title[:480],
            "summary": _clean(en_sum[0]) if en_sum else None,
            "meeting_date": dt,
            "audio_url": audio,
            "duration_seconds": int(it.get("duration") or 0) or None,
            "languages": it.get("languages") or [],
            "multimedia_url": f"https://audiovisual.ec.europa.eu/en/video/{ref}",
        })
    return out
