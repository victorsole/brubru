"""
Canonical response envelope for /api/v1/*.

Shape mirrors the GovClipping Postman convention so existing partner
integrations feel familiar. Every paginated endpoint returns this shape.

Phase 3 of docs/applications/euvoc.md (May 2026): the envelope was
extended with an `op_core` block carrying OP Core Metadata
(Dublin-Core-derived) properties — dct:title, dct:identifier, dct:type,
dct:language, dct:isPartOf, dct:date, dct:publisher,
dct:isReferencedBy. The block is ADDITIVE — every existing field is
preserved verbatim. No partner integration should break from this
change; pre-existing payloads simply gain a new `op_core` key.
"""

from datetime import date, datetime
from math import ceil
from typing import Generic, Literal, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")

DetailLevel = Literal["Minimal", "Summary", "Full"]


class Meta(BaseModel):
    """Legacy meta block. NOT included in PaginatedResponse anymore (Jordi
    feedback 30 April 2026 — the same provenance information is on
    `X-Powered-By` / `X-Source` response headers). Kept for the citations
    endpoint until that one is migrated."""
    source: str = "brubru.beresol.eu"
    powered_by: str = "Brubru"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class OPCoreMetadata(BaseModel):
    """
    OP Core Metadata block (Dublin-Core-derived) carried on every v1
    paginated envelope. Mirrors the element set used by Cellar so a
    partner harvester can ingest a Brubru response without translation.

    All fields are optional — every endpoint populates the ones that
    apply to its content type and leaves the rest at their default.

    Reference: https://op.europa.eu/en/web/eu-vocabularies/opcm
    """

    model_config = ConfigDict(populate_by_name=True)

    title: Optional[str] = Field(None, alias="dct:title", description="Title of the listing / collection.")
    identifier: Optional[str] = Field(None, alias="dct:identifier", description="Stable identifier — typically the canonical request URL.")
    type: Optional[str] = Field(None, alias="dct:type", description="Resource type — e.g. 'EU legislation', 'Procedure', 'MEP'.")
    language: Optional[str] = Field(None, alias="dct:language", description="ISO-639 lang tag of the response content (default 'en').")
    is_part_of: Optional[str] = Field(None, alias="dct:isPartOf", description="Parent collection IRI — defaults to the Brubru DCAT-AP catalogue.")
    date: Optional[datetime] = Field(None, alias="dct:date", description="Server timestamp when this response was generated.")
    publisher: Optional[str] = Field("https://brubru.beresol.eu/.well-known/publisher", alias="dct:publisher")
    is_referenced_by: list[str] = Field(
        default_factory=list,
        alias="dct:isReferencedBy",
        description="Related v1 endpoints partners can follow for richer detail (e.g. /api/v1/discover/cellar/celex/{celex}/relationships).",
    )
    conforms_to: str = Field(
        "https://op.europa.eu/en/web/eu-vocabularies/opcm",
        alias="dct:conformsTo",
        description="OP Core Metadata application profile this envelope conforms to.",
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response envelope used by every v1 endpoint."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    total: int = Field(..., description="Total matching items across all pages")
    returned: int = Field(..., description="Items in this page (len(data))")
    pages: int = Field(..., description="Total number of pages")
    page: int = Field(..., description="Current page (1-indexed)")
    limit: int = Field(..., description="Items per page used for this response")
    has_more: bool
    next_page: Optional[int] = None
    remaining_pages: int = 0
    coverage_complete: bool = Field(True, description="True for DB-backed results; False if upstream/live fetch may be partial")

    published_from: Optional[date] = None
    published_to: Optional[date] = None
    # GovClipping-compatible alias. Same value as published_to; partners who built against GovClipping see what they expect.
    published_end: Optional[date] = None
    updated_from: Optional[datetime] = None
    updated_to: Optional[datetime] = None
    updated_end: Optional[datetime] = None
    detail_level: DetailLevel = "Full"

    # Phase 3 of docs/applications/euvoc.md — additive OP Core Metadata block.
    op_core: Optional[OPCoreMetadata] = Field(
        None,
        description="OP Core Metadata block (Dublin-Core-derived). Populated by build_envelope() unless suppressed.",
    )

    data: list[T]


_BRUBRU_CATALOG_IRI = "https://brubru.beresol.eu/.well-known/dcat-ap-catalog"


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
    coverage_complete: bool = True,
    # Phase 3 of docs/applications/euvoc.md — OP Core Metadata enrichment.
    op_core_title: Optional[str] = None,
    op_core_type: Optional[str] = None,
    op_core_identifier: Optional[str] = None,
    op_core_language: str = "en",
    op_core_referenced_by: Optional[list[str]] = None,
) -> PaginatedResponse[T]:
    """Populate all pagination fields consistently.

    Phase 3 (May 2026): also populates the additive `op_core` block by
    default. Pass `op_core_title`, `op_core_type`, etc. on the call site
    to fill in the resource-specific details. Endpoints that opt out can
    pass empty kwargs and the block will still render with default
    values (no semantic loss for harvesters).
    """
    pages = max(1, ceil(total / limit)) if total > 0 else 0
    has_more = page < pages
    next_page = page + 1 if has_more else None
    remaining = max(0, pages - page)

    op_core = OPCoreMetadata(
        title=op_core_title,
        type=op_core_type,
        identifier=op_core_identifier,
        language=op_core_language,
        is_part_of=_BRUBRU_CATALOG_IRI,
        date=datetime.utcnow(),
        is_referenced_by=op_core_referenced_by or [],
    )

    return PaginatedResponse[T](
        total=total,
        returned=len(items),
        pages=pages,
        page=page,
        limit=limit,
        has_more=has_more,
        next_page=next_page,
        remaining_pages=remaining,
        coverage_complete=coverage_complete,
        published_from=published_from,
        published_to=published_to,
        published_end=published_to,
        updated_from=updated_from,
        updated_to=updated_to,
        updated_end=updated_to,
        detail_level=detail_level,
        op_core=op_core,
        data=items,
    )
