"""The ``/api/v2/social`` surface as a namespace: ``client.social.*``.

The EU social directory (institutions, agencies, MEPs, Commissioners, EU
officials, EU-affairs journalists) and their posts on the open platforms
(Bluesky, Mastodon, YouTube, and X via the public syndication endpoint).
Instagram / LinkedIn / TikTok are mapping-only (no post content) by design.
"""
from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from ._models import Page, SocialAccount, SocialPlatform, SocialPost

__all__ = ["Social"]


class Social:
    def __init__(self, client):
        self._c = client

    def directory(self) -> Dict[str, Any]:
        """Coverage overview: totals, accounts by entity_type and by platform,
        posts by platform, and the content vs mapping-only note."""
        return self._c.get("/api/v2/social")

    def posts(self, *, platform: Optional[str] = None, entity_type: Optional[str] = None,
              entity_key: Optional[str] = None, account_id: Optional[int] = None,
              since: Optional[str] = None, q: Optional[str] = None,
              page: int = 1, limit: int = 50) -> Page:
        """One page of recent posts (newest first), filtered. body_* are null on
        list calls: use ``post(id)`` for the full text."""
        return self._c.get_page("/api/v2/social/posts", SocialPost, platform=platform,
                                entity_type=entity_type, entity_key=entity_key,
                                account_id=account_id, since=since, q=q, page=page, limit=limit)

    def iter_posts(self, *, max_items: Optional[int] = None, limit: int = 100,
                   **filters: Any) -> Iterator[SocialPost]:
        """Stream posts across all pages (same filters as ``posts``)."""
        return self._c.iter_paginated("/api/v2/social/posts", SocialPost,
                                      max_items=max_items, limit=limit, **filters)

    def post(self, post_id: int) -> SocialPost:
        """One post with its full body (all 5 datapoints populated)."""
        return SocialPost.from_dict(self._c.get(f"/api/v2/social/posts/{post_id}"))

    def accounts(self, *, entity_type: Optional[str] = None, platform: Optional[str] = None,
                 verified: Optional[bool] = None, q: Optional[str] = None,
                 page: int = 1, limit: int = 50) -> Page:
        """One page of mapped accounts, filtered."""
        v = None if verified is None else str(verified).lower()
        return self._c.get_page("/api/v2/social/accounts", SocialAccount, entity_type=entity_type,
                                platform=platform, verified=v, q=q, page=page, limit=limit)

    def iter_accounts(self, *, max_items: Optional[int] = None, limit: int = 100,
                      **filters: Any) -> Iterator[SocialAccount]:
        if "verified" in filters and filters["verified"] is not None:
            filters["verified"] = str(filters["verified"]).lower()
        return self._c.iter_paginated("/api/v2/social/accounts", SocialAccount,
                                      max_items=max_items, limit=limit, **filters)

    def account(self, account_id: int) -> SocialAccount:
        """One account with its composed profile body."""
        return SocialAccount.from_dict(self._c.get(f"/api/v2/social/accounts/{account_id}"))

    def entity(self, entity_type: str, entity_key: str, *, posts_limit: int = 20) -> Dict[str, Any]:
        """One entity's full social footprint: every mapped account + recent posts.
        Returns a dict with typed ``accounts`` and ``recent_posts`` lists."""
        d = self._c.get(f"/api/v2/social/entity/{entity_type}/{entity_key}", posts_limit=posts_limit)
        return {
            "entity_type": d.get("entity_type"),
            "entity_key": d.get("entity_key"),
            "entity_name": d.get("entity_name"),
            "accounts": [SocialAccount.from_dict(a) for a in d.get("accounts", [])],
            "recent_posts": [SocialPost.from_dict(p) for p in d.get("recent_posts", [])],
        }

    def platforms(self) -> List[SocialPlatform]:
        """The platform pick-list with each platform's content-fetch tier."""
        return [SocialPlatform.from_dict(p) for p in self._c.get("/api/v2/social/platforms")]
