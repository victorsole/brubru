"""
Comparator Pydantic schemas — request/response shapes for the Comparator API.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# Canonical column definitions for MVP. The frontend column picker uses this list.
# Backend cell extractors use the same `key` to dispatch to the right extractor.
COLUMN_DEFS: List[Dict[str, str]] = [
    {"key": "rapporteur", "label": "Rapporteur"},
    {"key": "status", "label": "Status"},
    {"key": "lead_committee", "label": "Lead Committee"},
    {"key": "amendments_deadline", "label": "Amendments Deadline"},
    {"key": "structure_counts", "label": "Recitals + Articles"},
    {"key": "last_key_event", "label": "Last Key Event"},
]
COLUMN_KEYS = {c["key"] for c in COLUMN_DEFS}


# ---------- Request bodies ----------

class GridColumn(BaseModel):
    key: str = Field(..., description="One of the canonical column keys (see COLUMN_KEYS)")
    label: Optional[str] = Field(None, description="Display label; defaults to canonical label")


class GridCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    file_refs: List[str] = Field(default_factory=list, description="CELEX or OEIL references")
    columns: List[GridColumn] = Field(default_factory=list)


class GridPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    file_refs: Optional[List[str]] = None
    columns: Optional[List[GridColumn]] = None


# ---------- Response bodies ----------

class CellOut(BaseModel):
    file_ref: str
    column_key: str
    value_text: Optional[str] = None
    citation: Optional[Dict[str, Any]] = None
    computation_status: str
    computation_error: Optional[str] = None
    computed_at: Optional[datetime] = None


class GridSummary(BaseModel):
    id: UUID
    name: str
    file_refs: List[str]
    columns: List[GridColumn]
    created_at: datetime
    updated_at: datetime
    cell_count: int = 0


class GridDetail(GridSummary):
    cells: List[CellOut] = Field(default_factory=list)
    file_metadata: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    """Per-file display labels keyed by file_ref. Populated by the resolver
    so the editor renders 'GDPR' instead of '32016R0679' immediately on load."""


class GridList(BaseModel):
    grids: List[GridSummary]
    total: int
    tier_limits: Dict[str, int]  # {"max_grids": 3, "max_rows": 5, "max_cols": 6}


class ComputeResponse(BaseModel):
    grid_id: UUID
    cells_computed: int
    cells_failed: int
    duration_seconds: float


class CatalogResponse(BaseModel):
    columns: List[Dict[str, str]]  # canonical column defs


# ---------- Search / picker ----------

class SearchHit(BaseModel):
    """One file the user can add to a Comparator grid."""
    file_ref: str                           # canonical key written into the grid (CELEX or OEIL ref)
    label: str                              # short human name to render (e.g. "GDPR", "Industrial Accelerator Act")
    subtitle: Optional[str] = None          # full title or short context line
    type: str                               # 'celex' | 'oeil'
    alias: Optional[str] = None             # if matched via the alias resolver
    source: str                             # 'alias' | 'celex' | 'oeil' | 'my_files' | 'suggested'
    committee: Optional[str] = None         # lead EP committee, for PI grouping/flagging
    deep_dive_url: Optional[str] = None     # Brubru deep-dive page if one exists for this file
    deep_dive_short_title: Optional[str] = None  # 'EU Inc.', 'Biotech Act', etc.


class SearchResponse(BaseModel):
    query: str
    hits: List[SearchHit]


class SuggestedResponse(BaseModel):
    """PI-relevant suggestions + the user's interest committees for the picker."""
    files: List[SearchHit]
    my_committees: List[str]


class ResolveRequest(BaseModel):
    refs: List[str]


class ResolveResponse(BaseModel):
    metadata: Dict[str, SearchHit]          # keyed by file_ref
