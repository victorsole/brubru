"""
Dashboard cockpit response schemas.

Six tiles that aggregate signals from existing sub-tabs of My EU Bubble.
Every tile is either populated with real data from the DB, or returns an
honest empty state pointing the user at the right action.

Never returns mock or synthetic items.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Empty-state contract
# ---------------------------------------------------------------------------


class TileEmptyState(BaseModel):
    """
    Honest empty-state payload. When a tile has no real data to surface, it
    must explain why and offer the user one concrete next action.
    """

    reason: Literal[
        "no_profile",
        "no_tracked_files",
        "no_recent_activity",
        "no_matches",
    ]
    message: str = Field(
        ...,
        description="One sentence the user reads on the empty tile.",
    )
    cta_label: str = Field(
        ...,
        description="Button label for the empty-state CTA.",
    )
    cta_path: str = Field(
        ...,
        description="Internal route the CTA links to (e.g. /profile).",
    )


# ---------------------------------------------------------------------------
# Tile items (one per tile)
# ---------------------------------------------------------------------------


class NewThisWeekItem(BaseModel):
    """A legislative file that landed in the last 7 days and matches the user."""

    carriage_id: str
    title: str
    procedure_ref: Optional[str] = None
    current_status: Optional[str] = None
    policy_areas: List[str] = Field(default_factory=list)
    matched_interests: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class TrackedFileMovingItem(BaseModel):
    """A tracked file whose status moved in the last 7 days."""

    carriage_id: str
    title: str
    procedure_ref: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    changed_at: Optional[datetime] = None


class PositionStressItem(BaseModel):
    """A tracked file with a position snapshot that recently shifted."""

    carriage_id: str
    title: str
    procedure_ref: Optional[str] = None
    signal: Literal["snapshot_refreshed", "amendments_tabled", "status_moved"]
    detail: str
    detected_at: Optional[datetime] = None


class CalendarEventItem(BaseModel):
    """An event in the next 7 days."""

    event_id: str
    title: str
    institution: Optional[str] = None
    event_type: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    source_url: Optional[str] = None
    policy_areas: List[str] = Field(default_factory=list)


class ComplianceSignalItem(BaseModel):
    """An adopted EU law in the user's policy areas."""

    eu_law_id: int
    celex: Optional[str] = None
    title: str
    policy_area: Optional[str] = None
    adopted_on: Optional[date] = None


class VoiceOpportunityItem(BaseModel):
    """An open consultation, soon-closing, in the user's policy areas."""

    consultation_id: str
    title: str
    initiative_id: Optional[str] = None
    end_date: Optional[date] = None
    days_until_deadline: Optional[int] = None
    policy_areas: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Per-tile envelope
# ---------------------------------------------------------------------------


class TileBase(BaseModel):
    """
    Common envelope: a tile is either `items` (real rows) or `empty_state`.
    Never both. Never neither.
    """

    total: int = 0
    empty_state: Optional[TileEmptyState] = None
    drill_down_path: str = Field(
        ...,
        description="Internal path users land on when they click the tile header.",
    )
    chat_handoff_prompt: Optional[str] = Field(
        None,
        description=(
            "Pre-filled Chat prompt for the tile-level "
            "'Talk to Brubru about this' CTA. None means handoff is hidden."
        ),
    )


class NewThisWeekTile(TileBase):
    items: List[NewThisWeekItem] = Field(default_factory=list)


class TrackedFilesMovingTile(TileBase):
    items: List[TrackedFileMovingItem] = Field(default_factory=list)


class PositionsUnderStressTile(TileBase):
    items: List[PositionStressItem] = Field(default_factory=list)


class NextSevenDaysTile(TileBase):
    items: List[CalendarEventItem] = Field(default_factory=list)


class ComplianceSignalsTile(TileBase):
    items: List[ComplianceSignalItem] = Field(default_factory=list)


class VoiceOpportunitiesTile(TileBase):
    items: List[VoiceOpportunityItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------


class DashboardTiles(BaseModel):
    new_this_week: NewThisWeekTile
    tracked_files_moving: TrackedFilesMovingTile
    positions_under_stress: PositionsUnderStressTile
    next_seven_days: NextSevenDaysTile
    compliance_signals: ComplianceSignalsTile
    voice_opportunities: VoiceOpportunitiesTile


class ProfileCompleteness(BaseModel):
    """
    How much of the user's profile is filled in.

    Each component contributes a fraction; total in [0, 1]. The Dashboard uses
    this to decide whether to surface a "complete your profile" banner.
    """

    score: float = Field(..., ge=0.0, le=1.0)
    has_policy_interests: bool
    has_organisation: bool
    has_country: bool
    has_tracked_files: bool
    has_sectors: bool = False
    has_role_title: bool = False


class DashboardResponse(BaseModel):
    tiles: DashboardTiles
    profile_completeness: ProfileCompleteness
    generated_at: datetime
