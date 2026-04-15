"""
Have Your Say Feedback Client.

On-demand fetch of stakeholder feedback contributions submitted to EC public
consultations via the Have Your Say portal. This is distinct from
HaveYourSayClient which fetches consultation metadata only.

API endpoint discovered April 2026:
  https://ec.europa.eu/info/law/better-regulation/api/allFeedback?publicationId={PID}

The publicationId corresponds to the integer key behind each consultation's
public URL (e.g., /initiatives/14094/feedback_en).

Created: April 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

FEEDBACK_API = "https://ec.europa.eu/info/law/better-regulation/api/allFeedback"
FEEDBACK_PUBLIC_URL = "https://ec.europa.eu/info/law/better-regulation/have-your-say/initiatives/{pid}/feedback_en"
USER_AGENT = "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)"
CACHE_TTL_SECONDS = 6 * 3600


@dataclass
class FeedbackItem:
    """One stakeholder feedback contribution."""
    feedback_id: int
    publication_id: int
    date: str  # ISO-like "2021/02/17 16:57:11"
    user_type: str  # BUSINESS_ASSOCIATION, CITIZEN, NGO, ACADEMIC_RESEARCH_INSTITUTION, COMPANY_SMES, etc.
    organisation: str
    country: str  # ISO-3 (e.g., BEL, FRA, DEU)
    language: str
    text: str
    company_size: Optional[str] = None
    transparency_register_number: Optional[str] = None
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    author_name: str = ""

    @property
    def public_url(self) -> str:
        return FEEDBACK_PUBLIC_URL.format(pid=self.publication_id)

    @property
    def short_text(self) -> str:
        if not self.text:
            return ""
        if len(self.text) <= 800:
            return self.text
        return self.text[:797].rstrip() + "..."


class HaveYourSayFeedbackClient:
    """
    Async client for the Have Your Say feedback API.

    Methods:
      - fetch_feedback(publication_id, limit, country?, user_type?, language?) -> list[FeedbackItem]
      - get_summary_counts(publication_id) -> dict (totals by user_type and country)
    """

    def __init__(self) -> None:
        self._cache: Dict[str, tuple[float, Any]] = {}

    def _cache_get(self, key: str) -> Optional[Any]:
        v = self._cache.get(key)
        if v is None:
            return None
        ts, payload = v
        if time.time() - ts > CACHE_TTL_SECONDS:
            self._cache.pop(key, None)
            return None
        return payload

    def _cache_put(self, key: str, payload: Any) -> None:
        self._cache[key] = (time.time(), payload)

    async def _get_json(self, params: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=15.0, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}) as client:
            r = await client.get(FEEDBACK_API, params=params)
            r.raise_for_status()
            return r.json()

    @staticmethod
    def _parse(item: Dict[str, Any]) -> FeedbackItem:
        first = (item.get("firstName") or "").strip()
        surname = (item.get("surname") or "").strip()
        author = " ".join(p for p in (first, surname) if p)
        return FeedbackItem(
            feedback_id=int(item.get("id") or 0),
            publication_id=int(item.get("publicationId") or 0),
            date=item.get("dateFeedback") or "",
            user_type=item.get("userType") or "",
            organisation=(item.get("organization") or "").strip(),
            country=item.get("country") or "",
            language=item.get("language") or "",
            text=(item.get("feedback") or "").strip(),
            company_size=item.get("companySize"),
            transparency_register_number=item.get("trNumber"),
            attachments=item.get("attachments") or [],
            author_name=author,
        )

    async def fetch_feedback(
        self,
        publication_id: int,
        limit: int = 20,
        country: Optional[str] = None,
        user_type: Optional[str] = None,
        language: str = "EN",
    ) -> List[FeedbackItem]:
        """Fetch up to `limit` feedback items, ordered by date desc.

        The EC API does NOT support filter-by-country/user_type server-side reliably,
        so we filter client-side after fetching.
        """
        if not publication_id:
            return []

        cache_key = f"fb:{publication_id}:{limit}:{country or '-'}:{user_type or '-'}:{language}"
        hit = self._cache_get(cache_key)
        if hit is not None:
            return hit

        # Page through up to 5 pages (size=20 each = 100) to satisfy server-side ordering quirks
        items: List[FeedbackItem] = []
        page = 0
        page_size = max(20, limit)
        try:
            while len(items) < limit and page < 5:
                payload = await self._get_json({
                    "publicationId": publication_id,
                    "size": page_size,
                    "page": page,
                })
                content = payload.get("content") or []
                if not content:
                    break
                for it in content:
                    item = self._parse(it)
                    if country and item.country.upper() != country.upper():
                        continue
                    if user_type and item.user_type.upper() != user_type.upper():
                        continue
                    items.append(item)
                    if len(items) >= limit:
                        break
                if payload.get("last"):
                    break
                page += 1
                await asyncio.sleep(0.5)  # be gentle
        except httpx.HTTPError as exc:
            logger.warning("[HYS-feedback] HTTP error pid=%s: %s", publication_id, exc)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("[HYS-feedback] parse error pid=%s: %s", publication_id, exc)
            return []

        self._cache_put(cache_key, items)
        return items

    async def get_summary_counts(self, publication_id: int) -> Dict[str, Any]:
        """Return aggregate counts by user_type and country across the first 200 items."""
        if not publication_id:
            return {"total": 0, "by_user_type": {}, "by_country": {}}

        cache_key = f"sum:{publication_id}"
        hit = self._cache_get(cache_key)
        if hit is not None:
            return hit

        items = await self.fetch_feedback(publication_id, limit=200)
        by_type: Dict[str, int] = {}
        by_country: Dict[str, int] = {}
        for it in items:
            if it.user_type:
                by_type[it.user_type] = by_type.get(it.user_type, 0) + 1
            if it.country:
                by_country[it.country] = by_country.get(it.country, 0) + 1
        out = {"total": len(items), "by_user_type": by_type, "by_country": by_country}
        self._cache_put(cache_key, out)
        return out


_singleton: Optional[HaveYourSayFeedbackClient] = None


def get_have_your_say_feedback_client() -> HaveYourSayFeedbackClient:
    global _singleton
    if _singleton is None:
        _singleton = HaveYourSayFeedbackClient()
    return _singleton
