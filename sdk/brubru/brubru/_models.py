"""Typed objects over the Brubru v2 contract.

Every data item exposes the five Brubru datapoints (public_url, body_txt,
body_html, document_date, creation_date) plus title/summary. body_* are null
on list calls and full on detail calls, exactly as the API documents. Unknown
fields are preserved in `.raw` so the models never lose data the API adds later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


def _dt(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 string to datetime; tolerate a trailing Z and None."""
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


@dataclass
class Item:
    """Base shape shared by every list/detail item: the 5 datapoints + title."""

    title: Optional[str] = None
    summary: Optional[str] = None
    public_url: Optional[str] = None
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[datetime] = None
    creation_date: Optional[datetime] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def _base_kwargs(cls, d: Dict[str, Any]) -> Dict[str, Any]:
        return dict(
            title=d.get("title"),
            summary=d.get("summary"),
            public_url=d.get("public_url"),
            body_txt=d.get("body_txt"),
            body_html=d.get("body_html"),
            document_date=_dt(d.get("document_date")),
            creation_date=_dt(d.get("creation_date")),
            raw=d,
        )


@dataclass
class ExtractedItem(Item):
    item_type: Optional[str] = None
    source_kind: Optional[str] = None
    guid: Optional[str] = None
    eurovoc_descriptors: List[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExtractedItem":
        return cls(item_type=d.get("item_type"), source_kind=d.get("source_kind"),
                   guid=d.get("guid"), eurovoc_descriptors=d.get("eurovoc_descriptors") or [],
                   **cls._base_kwargs(d))


@dataclass
class ExtractResult:
    """Return of Client.extract() — not a paginated envelope, a direct result."""

    url: str
    platform: str
    fetched_via: str
    item_count: int
    items: List[ExtractedItem]
    body_code: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ExtractResult":
        return cls(url=d.get("url", ""), platform=d.get("platform", ""),
                   fetched_via=d.get("fetched_via", ""), item_count=d.get("item_count", 0),
                   items=[ExtractedItem.from_dict(i) for i in d.get("items", [])],
                   body_code=d.get("body_code"), raw=d)

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)


@dataclass
class SocialPost(Item):
    id: Optional[int] = None
    account_id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_key: Optional[str] = None
    entity_name: Optional[str] = None
    platform: Optional[str] = None
    handle: Optional[str] = None
    like_count: Optional[int] = None
    repost_count: Optional[int] = None
    reply_count: Optional[int] = None
    view_count: Optional[int] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SocialPost":
        return cls(id=d.get("id"), account_id=d.get("account_id"), entity_type=d.get("entity_type"),
                   entity_key=d.get("entity_key"), entity_name=d.get("entity_name"),
                   platform=d.get("platform"), handle=d.get("handle"), like_count=d.get("like_count"),
                   repost_count=d.get("repost_count"), reply_count=d.get("reply_count"),
                   view_count=d.get("view_count"), **cls._base_kwargs(d))


@dataclass
class SocialAccount(Item):
    id: Optional[int] = None
    entity_type: Optional[str] = None
    entity_key: Optional[str] = None
    entity_name: Optional[str] = None
    platform: Optional[str] = None
    scope: Optional[str] = None
    handle: Optional[str] = None
    status: Optional[str] = None
    verified: Optional[bool] = None
    discovery_source: Optional[str] = None
    content_fetch_enabled: Optional[bool] = None

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SocialAccount":
        return cls(id=d.get("id"), entity_type=d.get("entity_type"), entity_key=d.get("entity_key"),
                   entity_name=d.get("entity_name"), platform=d.get("platform"), scope=d.get("scope"),
                   handle=d.get("handle"), status=d.get("status"), verified=d.get("verified"),
                   discovery_source=d.get("discovery_source"),
                   content_fetch_enabled=d.get("content_fetch_enabled"), **cls._base_kwargs(d))


@dataclass
class SocialPlatform:
    code: str
    name: str
    fetch_tier: str
    notes: Optional[str] = None
    account_count: int = 0
    post_count: int = 0
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SocialPlatform":
        return cls(code=d.get("code", ""), name=d.get("name", ""), fetch_tier=d.get("fetch_tier", ""),
                   notes=d.get("notes"), account_count=d.get("account_count", 0),
                   post_count=d.get("post_count", 0), raw=d)


@dataclass
class Page:
    """One page of a PaginatedResponse envelope. Iterate it for the items on
    this page; use Client.iter_paginated() / Social.iter_* to stream all pages."""

    items: List[Any]
    total: int
    page: int
    pages: int
    limit: int
    has_more: bool
    next_page: Optional[int]
    raw: Dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_envelope(cls, env: Dict[str, Any], item_cls) -> "Page":
        data = env.get("data", []) or []
        items = [item_cls.from_dict(x) if hasattr(item_cls, "from_dict") else x for x in data]
        return cls(items=items, total=env.get("total", len(items)), page=env.get("page", 1),
                   pages=env.get("pages", 1), limit=env.get("limit", len(items)),
                   has_more=bool(env.get("has_more")), next_page=env.get("next_page"), raw=env)

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)
