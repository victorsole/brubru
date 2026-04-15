"""
Canonical response envelope for /api/v1/*.

Shape mirrors the GovClipping Postman convention so existing partner
integrations feel familiar. Every paginated endpoint returns this shape.
"""

from datetime import date, datetime
from math import ceil
from typing import Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

DetailLevel = Literal["Minimal", "Summary", "Full"]


class Meta(BaseModel):
    source: str = "brubru.beresol.eu"
    powered_by: str = "Brubru"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope used by every v1 endpoint."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    total: int = Field(..., description="Total matching items across all pages")
    pages: int = Field(..., description="Total number of pages")
    page: int = Field(..., description="Current page (1-indexed)")
    limit: int = Field(..., description="Items per page used for this response")
    has_more: bool
    next_page: Optional[int] = None
    remaining_pages: int = 0

    published_from: Optional[date] = None
    published_to: Optional[date] = None
    updated_from: Optional[datetime] = None
    updated_to: Optional[datetime] = None
    detail_level: DetailLevel = "Full"

    data: list[T]
    meta: Meta = Field(default_factory=Meta)


def build_envelope(
    items: list[T],
    total: int,
    page: int,
    limit: int,
    *,
    published_from: Optional[date] = None,
    published_to: Optional[date] = None,
    updated_from: Optional[datetime] = None,
    updated_to: Optional[datetime] = None,
    detail_level: DetailLevel = "Full",
) -> PaginatedResponse[T]:
    """Populate all pagination fields consistently."""
    pages = max(1, ceil(total / limit)) if total > 0 else 0
    has_more = page < pages
    next_page = page + 1 if has_more else None
    remaining = max(0, pages - page)
    return PaginatedResponse[T](
        total=total,
        pages=pages,
        page=page,
        limit=limit,
        has_more=has_more,
        next_page=next_page,
        remaining_pages=remaining,
        published_from=published_from,
        published_to=published_to,
        updated_from=updated_from,
        updated_to=updated_to,
        detail_level=detail_level,
        data=items,
    )
