"""
Timeline Predictor - Phase 1.4

Baseline timeline predictions for legislative procedures.
Uses historical data and similar procedure analysis.

Features:
1. Status stagnation alerts (procedures stuck > 9 months)
2. Historical average timelines by status and procedure type
3. Similar procedure lookup for timeline reference
"""

import logging
from datetime import datetime, timezone, timedelta, date
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from core.database import SessionLocal

logger = logging.getLogger(__name__)


# Stagnation thresholds (in days)
STAGNATION_WARNING = 180  # 6 months
STAGNATION_ALERT = 270  # 9 months
STAGNATION_CRITICAL = 365  # 1 year


class StagnationLevel(str, Enum):
    """Level of procedure stagnation."""
    NORMAL = "normal"
    WARNING = "warning"  # 6-9 months
    ALERT = "alert"  # 9-12 months
    CRITICAL = "critical"  # > 12 months


@dataclass
class StagnationInfo:
    """Information about procedure stagnation."""
    procedure_ref: str
    title: str
    current_status: str
    days_in_status: int
    level: StagnationLevel
    last_update: Optional[datetime] = None
    expected_days: Optional[int] = None
    delay_factor: Optional[float] = None  # How much longer than average


@dataclass
class TimelineStats:
    """Statistics for a status transition."""
    from_status: str
    to_status: str
    procedure_type: str
    sample_size: int
    avg_days: float
    median_days: float
    min_days: int
    max_days: int
    percentile_25: float
    percentile_75: float


@dataclass
class TimelinePrediction:
    """Timeline prediction for a procedure."""
    procedure_ref: str
    current_status: str
    days_in_status: int
    predicted_days_remaining: Optional[int]
    confidence: float  # 0.0-1.0
    based_on: str  # 'historical_average', 'similar_procedures', 'model'
    similar_procedures: List[Dict[str, Any]] = field(default_factory=list)
    historical_stats: Optional[TimelineStats] = None


class TimelinePredictor:
    """
    Predicts legislative timelines using historical data.

    Usage:
        predictor = TimelinePredictor()
        alerts = await predictor.get_stagnation_alerts()
        prediction = await predictor.predict_timeline(procedure_ref)
    """

    def __init__(self, db: Optional[Session] = None):
        self._db = db
        self._owns_db = db is None
        self._stats_cache: Dict[str, TimelineStats] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(hours=6)

    @property
    def db(self) -> Session:
        if self._db is None:
            self._db = SessionLocal()
        return self._db

    def close(self):
        """Close database session if we own it."""
        if self._owns_db and self._db:
            self._db.close()
            self._db = None

    def _get_stagnation_level(self, days: int) -> StagnationLevel:
        """Determine stagnation level from days in status."""
        if days >= STAGNATION_CRITICAL:
            return StagnationLevel.CRITICAL
        elif days >= STAGNATION_ALERT:
            return StagnationLevel.ALERT
        elif days >= STAGNATION_WARNING:
            return StagnationLevel.WARNING
        return StagnationLevel.NORMAL

    async def get_stagnation_alerts(
        self,
        min_level: StagnationLevel = StagnationLevel.WARNING,
        limit: int = 50
    ) -> List[StagnationInfo]:
        """
        Get procedures that are stagnating (stuck in current status too long).

        Args:
            min_level: Minimum stagnation level to report
            limit: Maximum number of alerts to return

        Returns:
            List of StagnationInfo sorted by days_in_status (descending)
        """
        try:
            from models.legislative_train import LegislativeCarriage

            # Calculate minimum days based on level
            if min_level == StagnationLevel.CRITICAL:
                min_days = STAGNATION_CRITICAL
            elif min_level == StagnationLevel.ALERT:
                min_days = STAGNATION_ALERT
            else:
                min_days = STAGNATION_WARNING

            # Query carriages with high days_in_current_status
            carriages = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.days_in_current_status >= min_days,
                LegislativeCarriage.current_status.notin_(["ADOPTED", "WITHDRAWN", "BLOCKED"])
            ).order_by(
                LegislativeCarriage.days_in_current_status.desc()
            ).limit(limit).all()

            alerts = []
            for c in carriages:
                level = self._get_stagnation_level(c.days_in_current_status)

                alerts.append(StagnationInfo(
                    procedure_ref=c.oeil_procedure_ref or str(c.id),
                    title=c.title,
                    current_status=c.current_status.value if hasattr(c.current_status, 'value') else str(c.current_status),
                    days_in_status=c.days_in_current_status,
                    level=level,
                    last_update=c.last_updated
                ))

            return alerts

        except ImportError:
            logger.warning("LegislativeCarriage model not available")
            return []

    async def calculate_historical_stats(
        self,
        procedure_type: Optional[str] = None,
        force_refresh: bool = False
    ) -> Dict[str, TimelineStats]:
        """
        Calculate historical timeline statistics from completed procedures.

        Returns statistics for each status transition.
        """
        # Check cache
        if (
            not force_refresh
            and self._stats_cache
            and self._cache_timestamp
            and datetime.now(timezone.utc) - self._cache_timestamp < self._cache_ttl
        ):
            return self._stats_cache

        try:
            from models.legislative_train import CarriageStatusHistory, LegislativeCarriage

            # The historical-stats query used to assume from_status / to_status /
            # days_in_previous_status columns that the carriage_status_history
            # schema never shipped. The actual columns are status + changed_at +
            # duration_days. We compute pairwise transitions in Python from
            # ordered status rows per carriage. When this query yields nothing
            # (cold DB), the predictor falls through to baseline stats.
            rows = (
                self.db.query(
                    CarriageStatusHistory.carriage_id,
                    CarriageStatusHistory.status,
                    CarriageStatusHistory.duration_days,
                    CarriageStatusHistory.changed_at,
                )
                .filter(CarriageStatusHistory.duration_days.isnot(None))
                .filter(CarriageStatusHistory.duration_days > 0)
                .order_by(CarriageStatusHistory.carriage_id, CarriageStatusHistory.changed_at)
                .all()
            )

            # Reconstruct transitions: each (carriage_id, status, duration_days)
            # pair represents the time spent in `status` before transitioning to
            # the next ordered row's status for the same carriage_id.
            transitions: Dict[str, List[int]] = {}
            prev_carriage = None
            prev_status = None
            for carriage_id, status, duration, _changed_at in rows:
                if carriage_id == prev_carriage and prev_status is not None:
                    key = f"{prev_status}->{status}"
                    transitions.setdefault(key, []).append(int(duration))
                prev_carriage = carriage_id
                prev_status = status

            # Calculate statistics
            stats = {}
            for key, days_list in transitions.items():
                if len(days_list) < 3:  # Need minimum sample size
                    continue

                days_list.sort()
                n = len(days_list)

                from_status, to_status = key.split("->")

                stats[key] = TimelineStats(
                    from_status=from_status,
                    to_status=to_status,
                    procedure_type=procedure_type or "ALL",
                    sample_size=n,
                    avg_days=sum(days_list) / n,
                    median_days=days_list[n // 2],
                    min_days=days_list[0],
                    max_days=days_list[-1],
                    percentile_25=days_list[n // 4],
                    percentile_75=days_list[3 * n // 4]
                )

            # Cache results
            self._stats_cache = stats
            self._cache_timestamp = datetime.now(timezone.utc)

            return stats

        except ImportError:
            logger.warning("CarriageStatusHistory model not available")
            return {}

    async def find_similar_procedures(
        self,
        procedure_ref: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find similar completed procedures for timeline reference.

        Uses title similarity and procedure type matching.
        """
        try:
            from models.legislative_train import LegislativeCarriage

            # Get the target procedure
            target = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.oeil_procedure_ref == procedure_ref
            ).first()

            if not target:
                return []

            # Extract procedure type from reference
            proc_type = None
            if target.oeil_procedure_ref:
                import re
                match = re.search(r"\(([A-Z]{3})\)", target.oeil_procedure_ref)
                if match:
                    proc_type = match.group(1)

            # Find completed procedures of same type
            query = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.current_status.in_(["ADOPTED", "WITHDRAWN"]),
                LegislativeCarriage.id != target.id
            )

            if proc_type:
                query = query.filter(
                    LegislativeCarriage.oeil_procedure_ref.contains(f"({proc_type})")
                )

            # Get candidates
            candidates = query.order_by(
                LegislativeCarriage.last_updated.desc()
            ).limit(100).all()

            # Score by title similarity
            from services.matching.resolution_legislation_matcher import ResolutionLegislationMatcher
            matcher = ResolutionLegislationMatcher()

            scored = []
            for c in candidates:
                similarity = matcher.calculate_title_similarity(target.title, c.title)
                if similarity > 0.2:  # Minimum threshold
                    scored.append({
                        "procedure_ref": c.oeil_procedure_ref,
                        "title": c.title,
                        "similarity": similarity,
                        "final_status": str(c.current_status),
                        "total_days": c.days_in_current_status,
                        "last_updated": c.last_updated.isoformat() if c.last_updated else None
                    })

            # Sort by similarity and take top N
            scored.sort(key=lambda x: x["similarity"], reverse=True)
            return scored[:limit]

        except ImportError:
            logger.warning("Required models not available")
            return []

    async def predict_timeline(
        self,
        procedure_ref: str
    ) -> Optional[TimelinePrediction]:
        """
        Predict timeline for a procedure based on historical data and similar procedures.

        Args:
            procedure_ref: OEIL procedure reference or carriage ID

        Returns:
            TimelinePrediction with estimated days remaining
        """
        try:
            from models.legislative_train import LegislativeCarriage

            # Get the procedure
            carriage = self.db.query(LegislativeCarriage).filter(
                LegislativeCarriage.oeil_procedure_ref == procedure_ref
            ).first()

            if not carriage:
                return None

            current_status = carriage.current_status
            if hasattr(current_status, 'value'):
                current_status = current_status.value

            days_in_status = carriage.days_in_current_status or 0

            # Get historical stats
            stats = await self.calculate_historical_stats()

            # Find relevant transition stats
            relevant_stats = None
            for key, stat in stats.items():
                if stat.from_status == current_status:
                    relevant_stats = stat
                    break

            # Get similar procedures
            similar = await self.find_similar_procedures(procedure_ref, limit=5)

            # Calculate prediction
            predicted_days = None
            confidence = 0.0
            based_on = "insufficient_data"

            if relevant_stats and relevant_stats.sample_size >= 10:
                # Use historical average
                avg_total = relevant_stats.avg_days
                predicted_days = max(0, int(avg_total - days_in_status))
                confidence = min(0.8, 0.3 + (relevant_stats.sample_size / 100))
                based_on = "historical_average"

            elif similar:
                # Use similar procedures average
                avg_days = sum(p.get("total_days", 0) for p in similar) / len(similar)
                predicted_days = max(0, int(avg_days - days_in_status))
                confidence = 0.4 + (0.1 * len(similar))
                based_on = "similar_procedures"

            return TimelinePrediction(
                procedure_ref=procedure_ref,
                current_status=current_status,
                days_in_status=days_in_status,
                predicted_days_remaining=predicted_days,
                confidence=confidence,
                based_on=based_on,
                similar_procedures=similar,
                historical_stats=relevant_stats
            )

        except ImportError:
            logger.warning("Required models not available")
            return None

    async def get_timeline_summary(
        self,
        procedure_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get a summary of timeline statistics.

        Returns aggregated stats useful for UI display.
        """
        stats = await self.calculate_historical_stats(procedure_type)

        if not stats:
            return {"error": "No statistics available"}

        # Aggregate key transitions
        summary = {
            "procedure_type": procedure_type or "ALL",
            "total_transitions": len(stats),
            "transitions": []
        }

        for key, stat in stats.items():
            summary["transitions"].append({
                "from": stat.from_status,
                "to": stat.to_status,
                "avg_days": round(stat.avg_days, 1),
                "median_days": round(stat.median_days, 1),
                "range": f"{stat.min_days}-{stat.max_days}",
                "sample_size": stat.sample_size
            })

        # Sort by frequency
        summary["transitions"].sort(key=lambda x: x["sample_size"], reverse=True)

        return summary


# Singleton instance
_predictor_instance: Optional[TimelinePredictor] = None


def get_timeline_predictor() -> TimelinePredictor:
    """Get or create the timeline predictor instance."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = TimelinePredictor()
    return _predictor_instance
