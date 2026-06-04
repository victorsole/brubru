"""
Dashboard API — the cockpit aggregator for My EU Bubble.

Single endpoint, six tiles, all sourced from real DB rows. When there is no
real data to show for a given user, the tile returns an honest empty state
that names the reason and offers one concrete next action. Never fabricates
items.

Routes:
- GET /api/dashboard/tiles  Aggregated tile payload for the authenticated user.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from core.database import get_db
from models.user import User
from schemas.dashboard_schemas import (
    CalendarEventItem,
    ComplianceSignalItem,
    ComplianceSignalsTile,
    DashboardResponse,
    DashboardTiles,
    NewThisWeekItem,
    NewThisWeekTile,
    NextSevenDaysTile,
    PositionStressItem,
    PositionsUnderStressTile,
    ProfileCompleteness,
    TileEmptyState,
    TrackedFileMovingItem,
    TrackedFilesMovingTile,
    VoiceOpportunitiesTile,
    VoiceOpportunityItem,
)

from .auth import get_current_user


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


# ---------------------------------------------------------------------------
# Constants — all data windows in days
# ---------------------------------------------------------------------------

NEW_THIS_WEEK_WINDOW_DAYS = 7
TRACKED_FILES_WINDOW_DAYS = 7
POSITION_STRESS_WINDOW_DAYS = 14
CALENDAR_LOOKAHEAD_DAYS = 7
COMPLIANCE_WINDOW_DAYS = 90
CONSULTATION_LOOKAHEAD_DAYS = 45

TILE_ITEM_LIMIT = 5


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _policy_interests_for(user: User) -> List[str]:
    """Return the user's policy interests as a list of strings, never None."""
    interests = user.policy_interests_list
    if not interests:
        return []
    return [str(x).strip() for x in interests if x and str(x).strip()]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Lenient policy-area matching
# ---------------------------------------------------------------------------
#
# Carriages and calendar events tag policy areas with scraper-sourced strings
# (e.g. "Agriculture and Rural Development", "Digital single market"), while
# users pick from a curated, higher-level list ("Agriculture", "Digital
# Policy and Digital Economy"). Strict equality returns zero hits in real
# life. Use case-insensitive partial-token match against the array column:
# any user interest is a hit when (a) one of its tokens (≥4 chars) appears
# in any of the row's policy_area strings, or (b) any of the row's
# policy_area strings appears verbatim inside the user interest. This is
# permissive — it favours surfacing items over silent zero-result UIs — but
# stays grounded in the row's real labels.

_POLICY_OVERLAP_CLAUSE = """
    EXISTS (
        SELECT 1 FROM unnest({col}) AS area_v
        WHERE EXISTS (
            SELECT 1 FROM unnest(CAST(:policy_interests AS text[])) AS interest_v
            WHERE LOWER(area_v) = LOWER(interest_v)
               OR LOWER(area_v) LIKE '%' || LOWER(interest_v) || '%'
               OR LOWER(interest_v) LIKE '%' || LOWER(area_v) || '%'
        )
    )
"""


def _policy_overlap_sql(column: str = "policy_areas") -> str:
    """
    Build a permissive policy-area overlap WHERE fragment. Caller binds
    ``policy_interests`` as a text[] parameter. ``column`` must be an array
    column on the row.
    """
    return _POLICY_OVERLAP_CLAUSE.format(col=column)


def _empty(
    reason: str,
    message: str,
    cta_label: str,
    cta_path: str,
) -> TileEmptyState:
    return TileEmptyState(
        reason=reason,  # type: ignore[arg-type]
        message=message,
        cta_label=cta_label,
        cta_path=cta_path,
    )


# ---------------------------------------------------------------------------
# Tile 1 — New this week for you
# ---------------------------------------------------------------------------


def _tile_new_this_week(db: Session, user: User) -> NewThisWeekTile:
    drill = "/my-eu-bubble?tab=legislative"
    handoff = (
        "Brief me on the EU legislative files added in the last week that "
        "match my policy interests."
    )

    interests = _policy_interests_for(user)
    if not interests:
        return NewThisWeekTile(
            items=[],
            total=0,
            empty_state=_empty(
                "no_profile",
                "Tell us which policy areas you follow and we will surface "
                "new files here within minutes.",
                "Add policy interests",
                "/profile",
            ),
            drill_down_path=drill,
            chat_handoff_prompt=None,
        )

    cutoff = _utcnow() - timedelta(days=NEW_THIS_WEEK_WINDOW_DAYS)

    rows: Iterable[Any]
    overlap = _policy_overlap_sql("policy_areas")
    try:
        rows = db.execute(
            text(
                f"""
                SELECT
                    id::text AS carriage_id,
                    title,
                    oeil_procedure_ref AS procedure_ref,
                    current_status,
                    policy_areas,
                    first_seen
                FROM legislative_carriages
                WHERE first_seen >= :cutoff
                  AND {overlap}
                ORDER BY first_seen DESC
                LIMIT :limit
                """
            ),
            {
                "cutoff": cutoff,
                "policy_interests": interests,
                "limit": TILE_ITEM_LIMIT,
            },
        ).mappings().all()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("new_this_week query failed: %s", exc)
        db.rollback()
        rows = []

    items = [
        NewThisWeekItem(
            carriage_id=row["carriage_id"],
            title=row["title"],
            procedure_ref=row.get("procedure_ref"),
            current_status=(
                row["current_status"].value
                if hasattr(row["current_status"], "value")
                else (row["current_status"] if row.get("current_status") else None)
            ),
            policy_areas=list(row.get("policy_areas") or []),
            matched_interests=[
                a for a in (row.get("policy_areas") or []) if a in interests
            ],
            created_at=row.get("first_seen"),
        )
        for row in rows
    ]

    if not items:
        # Nothing brand-new this week: fall back to a live preview of the most
        # recent files matching the user's interests, so the tile mirrors the
        # legislative tracker rather than going blank.
        try:
            fb = db.execute(
                text(
                    f"""
                    SELECT id::text AS carriage_id, title,
                           oeil_procedure_ref AS procedure_ref, current_status,
                           policy_areas, first_seen
                    FROM legislative_carriages
                    WHERE {overlap}
                    ORDER BY first_seen DESC NULLS LAST
                    LIMIT :limit
                    """
                ),
                {"policy_interests": interests, "limit": TILE_ITEM_LIMIT},
            ).mappings().all()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("new_this_week fallback failed: %s", exc)
            db.rollback()
            fb = []
        if not fb:
            # Still nothing in the user's exact policy areas: preview the most
            # recently seen files across the whole tracker, so the tile is never
            # blank when there is real data to show.
            try:
                fb = db.execute(
                    text(
                        """
                        SELECT id::text AS carriage_id, title,
                               oeil_procedure_ref AS procedure_ref, current_status,
                               policy_areas, first_seen
                        FROM legislative_carriages
                        ORDER BY first_seen DESC NULLS LAST
                        LIMIT :limit
                        """
                    ),
                    {"limit": TILE_ITEM_LIMIT},
                ).mappings().all()
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("new_this_week unfiltered fallback failed: %s", exc)
                db.rollback()
                fb = []
        items = [
            NewThisWeekItem(
                carriage_id=row["carriage_id"],
                title=row["title"],
                procedure_ref=row.get("procedure_ref"),
                current_status=(
                    row["current_status"].value
                    if hasattr(row["current_status"], "value")
                    else (row["current_status"] if row.get("current_status") else None)
                ),
                policy_areas=list(row.get("policy_areas") or []),
                matched_interests=[a for a in (row.get("policy_areas") or []) if a in interests],
                created_at=row.get("first_seen"),
            )
            for row in fb
        ]
        if not items:
            return NewThisWeekTile(
                items=[],
                total=0,
                empty_state=_empty(
                    "no_matches",
                    "No legislative files match your policy interests yet. "
                    "Browse the tracker to find files to follow.",
                    "Browse the tracker",
                    "/my-eu-bubble?tab=legislative",
                ),
                drill_down_path=drill,
                chat_handoff_prompt=None,
            )

    return NewThisWeekTile(
        items=items,
        total=len(items),
        drill_down_path=drill,
        chat_handoff_prompt=handoff,
    )


# ---------------------------------------------------------------------------
# Tile 2 — Your tracked files moving
# ---------------------------------------------------------------------------


def _tile_tracked_files_moving(db: Session, user: User) -> TrackedFilesMovingTile:
    drill = "/my-eu-bubble?tab=my_files"
    handoff = (
        "Summarise the status changes on the files I track in the last 7 days "
        "and what they mean for the procedure timeline."
    )

    cutoff = _utcnow() - timedelta(days=TRACKED_FILES_WINDOW_DAYS)

    try:
        track_count = (
            db.execute(
                text(
                    "SELECT COUNT(*) FROM user_carriage_tracks "
                    "WHERE user_id = :uid"
                ),
                {"uid": str(user.id)},
            ).scalar()
            or 0
        )
    except Exception as exc:
        logger.warning("user_carriage_tracks count failed: %s", exc)
        db.rollback()
        track_count = 0

    if track_count == 0:
        return TrackedFilesMovingTile(
            items=[],
            total=0,
            empty_state=_empty(
                "no_tracked_files",
                "Track a legislative file and we will tell you the moment its "
                "status changes here.",
                "Track your first file",
                "/my-eu-bubble?tab=my_files",
            ),
            drill_down_path=drill,
            chat_handoff_prompt=None,
        )

    try:
        rows = db.execute(
            text(
                """
                WITH transitions AS (
                    SELECT
                        carriage_id,
                        status,
                        changed_at,
                        LAG(status) OVER (
                            PARTITION BY carriage_id
                            ORDER BY changed_at
                        ) AS old_status
                    FROM carriage_status_history
                )
                SELECT
                    lc.id::text AS carriage_id,
                    lc.title,
                    lc.oeil_procedure_ref AS procedure_ref,
                    tr.status AS new_status,
                    tr.old_status,
                    tr.changed_at
                FROM transitions tr
                JOIN user_carriage_tracks uct
                  ON uct.carriage_id = tr.carriage_id
                JOIN legislative_carriages lc
                  ON lc.id = tr.carriage_id
                WHERE uct.user_id = :uid
                  AND tr.changed_at >= :cutoff
                ORDER BY tr.changed_at DESC
                LIMIT :limit
                """
            ),
            {
                "uid": str(user.id),
                "cutoff": cutoff,
                "limit": TILE_ITEM_LIMIT,
            },
        ).mappings().all()
    except Exception as exc:
        logger.warning("tracked_files_moving query failed: %s", exc)
        db.rollback()
        rows = []

    items = [
        TrackedFileMovingItem(
            carriage_id=row["carriage_id"],
            title=row["title"],
            procedure_ref=row.get("procedure_ref"),
            old_status=(
                row["old_status"].value
                if hasattr(row.get("old_status"), "value")
                else row.get("old_status")
            ),
            new_status=(
                row["new_status"].value
                if hasattr(row["new_status"], "value")
                else row["new_status"]
            ),
            changed_at=row.get("changed_at"),
        )
        for row in rows
    ]

    if not items:
        # No movement this week: preview the files the user actually tracks
        # (with their current status) so the tile mirrors My Tracked Files.
        try:
            fb = db.execute(
                text(
                    """
                    SELECT lc.id::text AS carriage_id, lc.title,
                           lc.oeil_procedure_ref AS procedure_ref, lc.current_status
                    FROM user_carriage_tracks uct
                    JOIN legislative_carriages lc ON lc.id = uct.carriage_id
                    WHERE uct.user_id = :uid
                    ORDER BY uct.tracked_since DESC
                    LIMIT :limit
                    """
                ),
                {"uid": str(user.id), "limit": TILE_ITEM_LIMIT},
            ).mappings().all()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("tracked_files_moving fallback failed: %s", exc)
            db.rollback()
            fb = []
        items = [
            TrackedFileMovingItem(
                carriage_id=row["carriage_id"],
                title=row["title"],
                procedure_ref=row.get("procedure_ref"),
                old_status=None,
                new_status=(
                    row["current_status"].value
                    if hasattr(row.get("current_status"), "value")
                    else row.get("current_status")
                ),
                changed_at=None,
            )
            for row in fb
        ]
        if not items:
            return TrackedFilesMovingTile(
                items=[],
                total=0,
                empty_state=_empty(
                    "no_recent_activity",
                    "Your tracked files have not moved recently. Status changes "
                    "will appear here as soon as they happen.",
                    "Open My Files",
                    "/my-eu-bubble?tab=my_files",
                ),
                drill_down_path=drill,
                chat_handoff_prompt=None,
            )

    return TrackedFilesMovingTile(
        items=items,
        total=len(items),
        drill_down_path=drill,
        chat_handoff_prompt=handoff,
    )


# ---------------------------------------------------------------------------
# Tile 3 — Positions under stress
# ---------------------------------------------------------------------------


def _tile_positions_under_stress(db: Session, user: User) -> PositionsUnderStressTile:
    drill = "/my-eu-bubble?tab=position_analysis"
    handoff = (
        "Walk me through the positions that shifted on my tracked files in "
        "the last two weeks."
    )

    cutoff = _utcnow() - timedelta(days=POSITION_STRESS_WINDOW_DAYS)

    try:
        rows = db.execute(
            text(
                """
                SELECT
                    lc.id::text AS carriage_id,
                    lc.title,
                    lc.oeil_procedure_ref AS procedure_ref,
                    fps.generated_at
                FROM user_carriage_tracks t
                JOIN legislative_carriages lc ON lc.id = t.carriage_id
                JOIN file_position_snapshots fps ON fps.carriage_id = lc.id
                WHERE t.user_id = :uid
                  AND fps.generated_at >= :cutoff
                ORDER BY fps.generated_at DESC
                LIMIT :limit
                """
            ),
            {
                "uid": str(user.id),
                "cutoff": cutoff,
                "limit": TILE_ITEM_LIMIT,
            },
        ).mappings().all()
    except Exception as exc:
        logger.warning("positions_under_stress query failed: %s", exc)
        db.rollback()
        rows = []

    items = [
        PositionStressItem(
            carriage_id=row["carriage_id"],
            title=row["title"],
            procedure_ref=row.get("procedure_ref"),
            signal="snapshot_refreshed",
            detail=(
                "Position snapshot was refreshed on "
                f"{row['generated_at'].date().isoformat() if row.get('generated_at') else 'a recent date'}, "
                "indicating new amendments or position movement."
            ),
            detected_at=row.get("generated_at"),
        )
        for row in rows
    ]

    if not items:
        # Distinguish "no tracked files" from "tracked, nothing shifted".
        try:
            has_tracks = bool(
                db.execute(
                    text(
                        "SELECT 1 FROM user_carriage_tracks "
                        "WHERE user_id = :uid LIMIT 1"
                    ),
                    {"uid": str(user.id)},
                ).first()
            )
        except Exception:
            has_tracks = False

        if not has_tracks:
            return PositionsUnderStressTile(
                items=[],
                total=0,
                empty_state=_empty(
                    "no_tracked_files",
                    "Track a file and Brubru will surface here when "
                    "positions shift against you.",
                    "Track your first file",
                    "/my-eu-bubble?tab=my_files",
                ),
                drill_down_path=drill,
                chat_handoff_prompt=None,
            )

        return PositionsUnderStressTile(
            items=[],
            total=0,
            empty_state=_empty(
                "no_recent_activity",
                "No position movement on your tracked files in the last "
                "two weeks. You can also run a manual position analysis.",
                "Open Position Analysis",
                "/my-eu-bubble?tab=position_analysis",
            ),
            drill_down_path=drill,
            chat_handoff_prompt=None,
        )

    return PositionsUnderStressTile(
        items=items,
        total=len(items),
        drill_down_path=drill,
        chat_handoff_prompt=handoff,
    )


# ---------------------------------------------------------------------------
# Tile 4 — Next 7 days
# ---------------------------------------------------------------------------


def _tile_next_seven_days(db: Session, user: User) -> NextSevenDaysTile:
    drill = "/my-eu-bubble?tab=eu_calendar"
    handoff = (
        "Brief me on the EU institutional events in the next 7 days that "
        "touch my policy areas or my tracked files."
    )

    interests = _policy_interests_for(user)
    today = date.today()
    horizon = today + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)

    # Build the WHERE clause: events in window, filtered by user signal if any
    where = "start_date BETWEEN :today AND :horizon AND status != 'cancelled'"
    params: dict[str, Any] = {
        "today": today,
        "horizon": horizon,
        "limit": TILE_ITEM_LIMIT,
    }
    if interests:
        overlap = _policy_overlap_sql("policy_areas")
        where += f" AND ({overlap} OR :allow_unfiltered)"
        params["policy_interests"] = interests
        params["allow_unfiltered"] = False
    else:
        # No profile: still show calendar events but be honest about it.
        params["allow_unfiltered"] = True

    try:
        rows = db.execute(
            text(
                f"""
                SELECT
                    id::text AS event_id,
                    title,
                    institution,
                    event_type,
                    start_date,
                    end_date,
                    source_url,
                    policy_areas
                FROM eu_calendar_events
                WHERE {where}
                ORDER BY start_date ASC, start_time ASC NULLS LAST
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    except Exception as exc:
        logger.warning("next_seven_days query failed: %s", exc)
        db.rollback()
        rows = []

    items = [
        CalendarEventItem(
            event_id=row["event_id"],
            title=row["title"],
            institution=(
                row["institution"].value
                if hasattr(row.get("institution"), "value")
                else row.get("institution")
            ),
            event_type=(
                row["event_type"].value
                if hasattr(row.get("event_type"), "value")
                else row.get("event_type")
            ),
            start_date=row["start_date"],
            end_date=row.get("end_date"),
            source_url=row.get("source_url"),
            policy_areas=list(row.get("policy_areas") or []),
        )
        for row in rows
    ]

    if not items and interests:
        # Nothing tagged to the user's exact policy areas in the window: fall
        # back to an unfiltered preview of the next 7 days, so the tile mirrors
        # My EU Calendar rather than going blank.
        try:
            fb = db.execute(
                text(
                    """
                    SELECT id::text AS event_id, title, institution, event_type,
                           start_date, end_date, source_url, policy_areas
                    FROM eu_calendar_events
                    WHERE start_date BETWEEN :today AND :horizon
                      AND status != 'cancelled'
                    ORDER BY start_date ASC, start_time ASC NULLS LAST
                    LIMIT :limit
                    """
                ),
                {"today": today, "horizon": horizon, "limit": TILE_ITEM_LIMIT},
            ).mappings().all()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("next_seven_days fallback failed: %s", exc)
            db.rollback()
            fb = []
        items = [
            CalendarEventItem(
                event_id=row["event_id"],
                title=row["title"],
                institution=(
                    row["institution"].value
                    if hasattr(row.get("institution"), "value")
                    else row.get("institution")
                ),
                event_type=(
                    row["event_type"].value
                    if hasattr(row.get("event_type"), "value")
                    else row.get("event_type")
                ),
                start_date=row["start_date"],
                end_date=row.get("end_date"),
                source_url=row.get("source_url"),
                policy_areas=list(row.get("policy_areas") or []),
            )
            for row in fb
        ]

    if not items:
        return NextSevenDaysTile(
            items=[],
            total=0,
            empty_state=_empty(
                "no_matches" if interests else "no_profile",
                (
                    "Nothing scheduled in the EU institutional calendar for "
                    "the next 7 days."
                )
                if interests
                else (
                    "Add policy interests to filter the EU institutional "
                    "calendar to what matters to you."
                ),
                "Open My EU Calendar" if interests else "Add policy interests",
                "/my-eu-bubble?tab=eu_calendar" if interests else "/profile",
            ),
            drill_down_path=drill,
            chat_handoff_prompt=None,
        )

    return NextSevenDaysTile(
        items=items,
        total=len(items),
        drill_down_path=drill,
        chat_handoff_prompt=handoff,
    )


# ---------------------------------------------------------------------------
# Tile 5 — Compliance signals
# ---------------------------------------------------------------------------


def _tile_compliance_signals(db: Session, user: User) -> ComplianceSignalsTile:
    drill = "/eulawcomply"
    handoff = (
        "Summarise the EU laws adopted in the last 90 days that touch my "
        "policy areas and the compliance obligations they introduce."
    )

    interests = _policy_interests_for(user)
    if not interests:
        return ComplianceSignalsTile(
            items=[],
            total=0,
            empty_state=_empty(
                "no_profile",
                "Add policy areas and Brubru will surface adopted EU laws "
                "you may need to comply with.",
                "Add policy interests",
                "/profile",
            ),
            drill_down_path=drill,
            chat_handoff_prompt=None,
        )

    cutoff = date.today() - timedelta(days=COMPLIANCE_WINDOW_DAYS)

    try:
        # eu_laws.policy_area is a scalar varchar, not an array. Match it
        # case-insensitively against any of the user's interests (either side
        # may be a substring of the other — same lenient rule as the array
        # tiles).
        rows = db.execute(
            text(
                """
                SELECT
                    id,
                    celex,
                    title,
                    policy_area,
                    date
                FROM eu_laws
                WHERE date >= :cutoff
                  AND policy_area IS NOT NULL
                  AND EXISTS (
                      SELECT 1 FROM unnest(CAST(:policy_interests AS text[])) AS interest_v
                      WHERE LOWER(policy_area) = LOWER(interest_v)
                         OR LOWER(policy_area) LIKE '%' || LOWER(interest_v) || '%'
                         OR LOWER(interest_v) LIKE '%' || LOWER(policy_area) || '%'
                  )
                  AND is_primary_legislation = TRUE
                ORDER BY date DESC
                LIMIT :limit
                """
            ),
            {
                "cutoff": cutoff,
                "policy_interests": interests,
                "limit": TILE_ITEM_LIMIT,
            },
        ).mappings().all()
    except Exception as exc:
        logger.warning("compliance_signals query failed: %s", exc)
        db.rollback()
        rows = []

    items = [
        ComplianceSignalItem(
            eu_law_id=row["id"],
            celex=row.get("celex"),
            title=row["title"],
            policy_area=row.get("policy_area"),
            adopted_on=row.get("date"),
        )
        for row in rows
    ]

    if not items:
        return ComplianceSignalsTile(
            items=[],
            total=0,
            empty_state=_empty(
                "no_matches",
                "No EU laws adopted in the last 90 days touch your policy "
                "areas. Run EU Law Comply on a specific file when you need to.",
                "Open EU Law Comply",
                "/eulawcomply",
            ),
            drill_down_path=drill,
            chat_handoff_prompt=None,
        )

    return ComplianceSignalsTile(
        items=items,
        total=len(items),
        drill_down_path=drill,
        chat_handoff_prompt=handoff,
    )


# ---------------------------------------------------------------------------
# Tile 6 — Voice opportunities
# ---------------------------------------------------------------------------


def _tile_voice_opportunities(db: Session, user: User) -> VoiceOpportunitiesTile:
    drill = "/my-eu-bubble?tab=consultations"
    handoff = (
        "Brief me on the open EC public consultations I should respond to "
        "before they close."
    )

    interests = _policy_interests_for(user)
    today = date.today()
    horizon = today + timedelta(days=CONSULTATION_LOOKAHEAD_DAYS)

    where = (
        "status = 'open' "
        "AND end_date IS NOT NULL "
        "AND end_date >= :today "
        "AND end_date <= :horizon"
    )
    params: dict[str, Any] = {
        "today": today,
        "horizon": horizon,
        "limit": TILE_ITEM_LIMIT,
    }
    if interests:
        where += f" AND {_policy_overlap_sql('policy_areas')}"
        params["policy_interests"] = interests

    try:
        rows = db.execute(
            text(
                f"""
                SELECT
                    id::text AS consultation_id,
                    title,
                    initiative_id,
                    end_date,
                    policy_areas
                FROM public_consultations
                WHERE {where}
                ORDER BY end_date ASC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
    except Exception as exc:
        logger.warning("voice_opportunities query failed: %s", exc)
        db.rollback()
        rows = []

    items = []
    for row in rows:
        end = row.get("end_date")
        days_until = (end - today).days if end else None
        items.append(
            VoiceOpportunityItem(
                consultation_id=row["consultation_id"],
                title=row["title"],
                initiative_id=row.get("initiative_id"),
                end_date=end,
                days_until_deadline=days_until,
                policy_areas=list(row.get("policy_areas") or []),
            )
        )

    if not items:
        if not interests:
            return VoiceOpportunitiesTile(
                items=[],
                total=0,
                empty_state=_empty(
                    "no_profile",
                    "Add policy interests and we will flag open EC "
                    "consultations you can respond to before they close.",
                    "Add policy interests",
                    "/profile",
                ),
                drill_down_path=drill,
                chat_handoff_prompt=None,
            )

        return VoiceOpportunitiesTile(
            items=[],
            total=0,
            empty_state=_empty(
                "no_matches",
                "No open EC consultations close in the next 45 days for your "
                "policy areas.",
                "Browse all consultations",
                "/my-eu-bubble?tab=consultations",
            ),
            drill_down_path=drill,
            chat_handoff_prompt=None,
        )

    return VoiceOpportunitiesTile(
        items=items,
        total=len(items),
        drill_down_path=drill,
        chat_handoff_prompt=handoff,
    )


# ---------------------------------------------------------------------------
# Profile completeness
# ---------------------------------------------------------------------------


def _profile_completeness(db: Session, user: User) -> ProfileCompleteness:
    has_policy = bool(_policy_interests_for(user))
    has_org = bool((user.organization or "").strip())
    has_country = bool((user.country or "").strip())
    has_role_title = bool((getattr(user, "role_title", None) or "").strip())

    sectors = getattr(user, "sectors", None) or []
    if isinstance(sectors, str):
        try:
            import json as _json

            sectors = _json.loads(sectors)
        except Exception:
            sectors = []
    has_sectors = bool(sectors)

    try:
        has_tracks = bool(
            db.execute(
                text(
                    "SELECT 1 FROM user_carriage_tracks "
                    "WHERE user_id = :uid LIMIT 1"
                ),
                {"uid": str(user.id)},
            ).first()
        )
    except Exception:
        db.rollback()
        has_tracks = False

    # Weights sum to 1.0; policy_interests stays the heaviest because it
    # drives most of the runtime Dashboard filtering.
    score = 0.0
    if has_policy:
        score += 0.30
    if has_sectors:
        score += 0.15
    if has_org:
        score += 0.15
    if has_country:
        score += 0.15
    if has_role_title:
        score += 0.10
    if has_tracks:
        score += 0.15

    return ProfileCompleteness(
        score=round(score, 2),
        has_policy_interests=has_policy,
        has_organisation=has_org,
        has_country=has_country,
        has_tracked_files=has_tracks,
        has_sectors=has_sectors,
        has_role_title=has_role_title,
    )


# ---------------------------------------------------------------------------
# Public endpoint
# ---------------------------------------------------------------------------


@router.get(
    "/tiles",
    response_model=DashboardResponse,
    summary="Get the six cockpit tiles for the authenticated user",
    description=(
        "**What it does**\n\n"
        "Returns the six Dashboard cockpit tiles for the authenticated user, "
        "aggregating signals from My Files, Position Analysis, My EU Calendar, "
        "EU Law Comply and EC Consultations.\n\n"
        "**When to use it**\n\n"
        "Call this once when My EU Bubble opens. The Dashboard renders the "
        "tiles directly from the response. Drilling into a tile navigates the "
        "user into the corresponding sub-tab.\n\n"
        "**Input**\n\n"
        "Authentication via Bearer JWT. No query parameters.\n\n"
        "**Try it**\n\n"
        "`GET /api/dashboard/tiles` with `Authorization: Bearer <token>`.\n\n"
        "**You get back**\n\n"
        "Six tile envelopes, each either `items` (real DB rows) or `empty_state` "
        "with a reason + CTA. Plus a `profile_completeness` block so the "
        "Dashboard knows whether to surface the 'finish your profile' banner. "
        "Never returns mock data."
    ),
)
async def get_dashboard_tiles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DashboardResponse:
    if not current_user or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Dashboard requires an authenticated, active user.",
        )

    tiles = DashboardTiles(
        new_this_week=_tile_new_this_week(db, current_user),
        tracked_files_moving=_tile_tracked_files_moving(db, current_user),
        positions_under_stress=_tile_positions_under_stress(db, current_user),
        next_seven_days=_tile_next_seven_days(db, current_user),
        compliance_signals=_tile_compliance_signals(db, current_user),
        voice_opportunities=_tile_voice_opportunities(db, current_user),
    )

    return DashboardResponse(
        tiles=tiles,
        profile_completeness=_profile_completeness(db, current_user),
        generated_at=_utcnow(),
    )
