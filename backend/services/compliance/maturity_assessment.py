"""
Compliance Maturity Assessment.

Scores a Brubru user on four axes that together describe how mature their
EU compliance posture is:

  - awareness         Are they tracking enough in-flight files in the
                      policy areas they care about?
  - impact_analysis   Do they actually analyse impact — running position
                      analyses, taking stances, using Comparator?
  - advocacy          Do they engage upstream — drafting amendments,
                      producing position papers / briefings?
  - follow_through    Do they close the loop with compliance analyses on
                      adopted laws?

Every axis tops out at 25; the total maturity score is 0–100. Tier is
beginner < 25 < intermediate < 50 < advanced < 75 < expert.

Each axis exposes its raw signal counts so the frontend can show "you
have 4 tracked files; track 6 more to lift your awareness score by 5
points." This is grounded in real DB rows — never fabricated. If the
user has done nothing, they get a 0 with an honest empty-state
recommendation. The shareable benchmark card uses this same payload.

Built for the EU Law Comply "P6 maturity assessment" workstream
(May 2026). See memory/project_resilinc_eu_law_comply_assessment.md.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import List, Literal, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.user import User


logger = logging.getLogger(__name__)


MaturityTier = Literal["beginner", "intermediate", "advanced", "expert"]

AXIS_MAX = 25
SCORE_MAX = 4 * AXIS_MAX  # 100


@dataclass
class AxisScore:
    name: str
    score: int  # 0..AXIS_MAX
    max_score: int = AXIS_MAX
    signals: dict = field(default_factory=dict)
    rationale: str = ""


@dataclass
class MaturityRecommendation:
    axis: str  # awareness | impact_analysis | advocacy | follow_through
    action: str
    rationale: str
    expected_lift: int  # points the user would gain by acting on this


@dataclass
class MaturityAssessment:
    score: int  # 0..100
    tier: MaturityTier
    tier_label: str
    axes: List[AxisScore]
    recommendations: List[MaturityRecommendation]
    profile_complete: bool
    has_any_activity: bool

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "max_score": SCORE_MAX,
            "tier": self.tier,
            "tier_label": self.tier_label,
            "axes": [asdict(a) for a in self.axes],
            "recommendations": [asdict(r) for r in self.recommendations],
            "profile_complete": self.profile_complete,
            "has_any_activity": self.has_any_activity,
        }


def _classify_tier(score: int) -> MaturityTier:
    if score >= 75:
        return "expert"
    if score >= 50:
        return "advanced"
    if score >= 25:
        return "intermediate"
    return "beginner"


def _tier_label(tier: MaturityTier) -> str:
    return {
        "beginner": "Beginner — you have a Brubru account; the next steps are obvious",
        "intermediate": "Intermediate — you track files and run analyses",
        "advanced": "Advanced — you engage upstream and close compliance loops",
        "expert": "Expert — you operate Brubru as a continuous compliance copilot",
    }[tier]


# ---------------------------------------------------------------------------
# Axis 1: Awareness
# ---------------------------------------------------------------------------


def _score_awareness(db: Session, user: User) -> AxisScore:
    """
    Points for tracking files at all, tracking many files, tracking files in
    multiple policy areas, and for having declared policy interests.
    """
    has_interests = bool(user.policy_interests_list)

    try:
        track_row = db.execute(
            text(
                """
                SELECT
                    COUNT(*)                                   AS total_tracks,
                    COUNT(DISTINCT pa)                         AS distinct_areas
                FROM user_carriage_tracks t
                JOIN legislative_carriages lc ON lc.id = t.carriage_id
                LEFT JOIN LATERAL unnest(lc.policy_areas) AS pa ON TRUE
                WHERE t.user_id = :uid
                """
            ),
            {"uid": str(user.id)},
        ).mappings().first() or {}
    except Exception as exc:
        logger.warning("awareness query failed: %s", exc)
        db.rollback()
        track_row = {}

    total_tracks = int(track_row.get("total_tracks") or 0)
    distinct_areas = int(track_row.get("distinct_areas") or 0)

    score = 0
    if has_interests:
        score += 5
    if total_tracks >= 1:
        score += 5
    if total_tracks >= 5:
        score += 5
    if total_tracks >= 10:
        score += 5
    if distinct_areas >= 3:
        score += 5
    score = min(score, AXIS_MAX)

    parts: List[str] = []
    parts.append(
        f"{total_tracks} tracked file{'s' if total_tracks != 1 else ''}"
        + (f" across {distinct_areas} policy area{'s' if distinct_areas != 1 else ''}"
           if distinct_areas else "")
    )
    if has_interests:
        parts.append("policy interests declared")
    rationale = ". ".join(parts) + "."

    return AxisScore(
        name="awareness",
        score=score,
        signals={
            "tracked_files": total_tracks,
            "distinct_policy_areas": distinct_areas,
            "has_policy_interests": has_interests,
        },
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Axis 2: Impact analysis
# ---------------------------------------------------------------------------


def _score_impact_analysis(db: Session, user: User) -> AxisScore:
    """
    Points for: stances declared on tracked files; comparator grids; using
    Position Analysis (proxy: file_position_snapshots are computed on access,
    so we cannot easily measure this — use stances + comparator only).
    """
    try:
        stance_count = (
            db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM user_carriage_tracks
                    WHERE user_id = :uid
                      AND user_position IS NOT NULL
                      AND user_position::text != 'null'
                    """
                ),
                {"uid": str(user.id)},
            ).scalar()
            or 0
        )
    except Exception as exc:
        logger.warning("stance count failed: %s", exc)
        db.rollback()
        stance_count = 0

    try:
        comparator_count = (
            db.execute(
                text(
                    "SELECT COUNT(*) FROM comparator_grids WHERE user_id = :uid"
                ),
                {"uid": str(user.id)},
            ).scalar()
            or 0
        )
    except Exception as exc:
        logger.warning("comparator count failed: %s", exc)
        db.rollback()
        comparator_count = 0

    score = 0
    if stance_count >= 1:
        score += 5
    if stance_count >= 3:
        score += 5
    if stance_count >= 5:
        score += 5
    if comparator_count >= 1:
        score += 5
    if comparator_count >= 3:
        score += 5
    score = min(score, AXIS_MAX)

    parts: List[str] = []
    if stance_count:
        parts.append(
            f"{stance_count} stance{'s' if stance_count != 1 else ''} on tracked files"
        )
    else:
        parts.append("no stances yet")
    if comparator_count:
        parts.append(
            f"{comparator_count} Comparator grid{'s' if comparator_count != 1 else ''}"
        )
    rationale = ". ".join(parts) + "."

    return AxisScore(
        name="impact_analysis",
        score=score,
        signals={
            "stances_declared": int(stance_count),
            "comparator_grids": int(comparator_count),
        },
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Axis 3: Advocacy engagement
# ---------------------------------------------------------------------------


def _score_advocacy(db: Session, user: User) -> AxisScore:
    """
    Points for: amendments drafted, position papers / briefings generated.
    """
    try:
        amendment_count = (
            db.execute(
                text("SELECT COUNT(*) FROM amendments WHERE user_id = :uid"),
                {"uid": str(user.id)},
            ).scalar()
            or 0
        )
    except Exception as exc:
        logger.warning("amendment count failed: %s", exc)
        db.rollback()
        amendment_count = 0

    try:
        doc_count = (
            db.execute(
                text("SELECT COUNT(*) FROM user_documents WHERE user_id = :uid"),
                {"uid": str(user.id)},
            ).scalar()
            or 0
        )
    except Exception as exc:
        logger.warning("user_documents count failed: %s", exc)
        db.rollback()
        doc_count = 0

    score = 0
    if amendment_count >= 1:
        score += 5
    if amendment_count >= 3:
        score += 5
    if amendment_count >= 10:
        score += 5
    if doc_count >= 1:
        score += 5
    if doc_count >= 3:
        score += 5
    score = min(score, AXIS_MAX)

    parts: List[str] = []
    if amendment_count:
        parts.append(
            f"{amendment_count} amendment{'s' if amendment_count != 1 else ''} drafted"
        )
    else:
        parts.append("no amendments drafted")
    if doc_count:
        parts.append(
            f"{doc_count} document{'s' if doc_count != 1 else ''} produced"
        )
    rationale = ". ".join(parts) + "."

    return AxisScore(
        name="advocacy",
        score=score,
        signals={
            "amendments_drafted": int(amendment_count),
            "documents_produced": int(doc_count),
        },
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Axis 4: Follow-through
# ---------------------------------------------------------------------------


def _score_follow_through(db: Session, user: User) -> AxisScore:
    """
    Points for: completed compliance analyses (closing the gap-analysis loop
    on adopted laws).
    """
    try:
        comply_count = (
            db.execute(
                text(
                    "SELECT COUNT(*) FROM compliance_analyses WHERE user_id = :uid"
                ),
                {"uid": str(user.id)},
            ).scalar()
            or 0
        )
    except Exception as exc:
        logger.warning("compliance count failed: %s", exc)
        db.rollback()
        comply_count = 0

    score = 0
    if comply_count >= 1:
        score += 10
    if comply_count >= 3:
        score += 10
    if comply_count >= 5:
        score += 5
    score = min(score, AXIS_MAX)

    if comply_count == 1:
        rationale = "1 EU Law Comply analysis completed."
    elif comply_count > 1:
        rationale = f"{comply_count} EU Law Comply analyses completed."
    else:
        rationale = "No EU Law Comply gap analyses completed yet."

    return AxisScore(
        name="follow_through",
        score=score,
        signals={"compliance_analyses": int(comply_count)},
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Recommendations — point at the lowest axis with the highest expected lift
# ---------------------------------------------------------------------------


def _recommendations_for(
    axes: List[AxisScore],
) -> List[MaturityRecommendation]:
    by_name = {a.name: a for a in axes}
    recs: List[MaturityRecommendation] = []

    awareness = by_name["awareness"]
    impact = by_name["impact_analysis"]
    advocacy = by_name["advocacy"]
    follow = by_name["follow_through"]

    if not awareness.signals.get("has_policy_interests"):
        recs.append(
            MaturityRecommendation(
                axis="awareness",
                action="Declare your policy interests on the Profile page",
                rationale=(
                    "Policy interests power the Dashboard cockpit, calendar "
                    "filters, and impact briefings. Five points the moment you "
                    "save them."
                ),
                expected_lift=5,
            )
        )
    elif awareness.signals.get("tracked_files", 0) < 5:
        deficit = 5 - awareness.signals.get("tracked_files", 0)
        recs.append(
            MaturityRecommendation(
                axis="awareness",
                action=f"Track {deficit} more legislative file{'s' if deficit > 1 else ''}",
                rationale=(
                    "Tracking unlocks status alerts, calendar reminders, and "
                    "the Personalised Impact block. Each tracked file "
                    "compounds your awareness."
                ),
                expected_lift=5,
            )
        )

    if impact.signals.get("stances_declared", 0) == 0:
        recs.append(
            MaturityRecommendation(
                axis="impact_analysis",
                action="Declare a stance on at least one tracked file",
                rationale=(
                    "Open a tracked file, set your position (support / "
                    "oppose / abstain) and a one-line rationale. Five points."
                ),
                expected_lift=5,
            )
        )

    if advocacy.signals.get("documents_produced", 0) == 0:
        recs.append(
            MaturityRecommendation(
                axis="advocacy",
                action="Generate your first position paper or MEP briefing",
                rationale=(
                    "The Documents tab generates first drafts from your "
                    "tracked file + Brubru's context. Five points the moment "
                    "you save one."
                ),
                expected_lift=5,
            )
        )

    if follow.signals.get("compliance_analyses", 0) == 0:
        recs.append(
            MaturityRecommendation(
                axis="follow_through",
                action="Run an EU Law Comply gap analysis on one adopted law",
                rationale=(
                    "Pick a law in your policy areas, upload one internal "
                    "doc, run the analysis. Ten points and closes the "
                    "compliance loop."
                ),
                expected_lift=10,
            )
        )

    # Keep the top 3 highest-lift recommendations
    recs.sort(key=lambda r: r.expected_lift, reverse=True)
    return recs[:3]


# ---------------------------------------------------------------------------
# Top-level composer
# ---------------------------------------------------------------------------


def compose_maturity_assessment(db: Session, user: User) -> MaturityAssessment:
    axes = [
        _score_awareness(db, user),
        _score_impact_analysis(db, user),
        _score_advocacy(db, user),
        _score_follow_through(db, user),
    ]
    total = sum(a.score for a in axes)
    tier = _classify_tier(total)
    has_activity = any(
        sum(a.signals.values() if isinstance(a.signals, dict) else [0])
        > 0
        for a in axes
        if a.signals
    )

    has_role = bool((getattr(user, "role_title", None) or "").strip())
    sectors = getattr(user, "sectors", None) or []
    if isinstance(sectors, str):
        try:
            import json as _json

            sectors = _json.loads(sectors)
        except Exception:
            sectors = []
    has_sectors = bool(sectors)
    profile_complete = (
        bool(user.policy_interests_list)
        and bool((user.organization or "").strip())
        and bool((user.country or "").strip())
        and has_role
        and has_sectors
    )

    return MaturityAssessment(
        score=total,
        tier=tier,
        tier_label=_tier_label(tier),
        axes=axes,
        recommendations=_recommendations_for(axes),
        profile_complete=profile_complete,
        has_any_activity=has_activity,
    )
