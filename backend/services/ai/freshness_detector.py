"""
Freshness Detector

Phase 5: Smart Summaries
Detects when EPRS briefings have become outdated and need AI-generated updates.

This service:
1. Compares EPRS briefing date vs current procedure status
2. Detects significant procedural advances since briefing
3. Identifies when legislation has been adopted/amended after briefing
4. Flags briefings that need updates
5. Recommends when to use AI-generated supplement

Result: Users know when EPRS briefings are outdated and see AI-generated updates

Usage:
    detector = FreshnessDetector()

    # Check if briefing is outdated
    status = await detector.check_briefing_freshness(
        briefing_date=datetime(2023, 6, 15),
        procedure_ref="2021/0106(COD)",
        celex="32024R1689"
    )

    if status.is_outdated:
        print(f"Briefing is {status.days_outdated} days behind")
        print(f"Reason: {status.outdated_reason}")
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class FreshnessLevel(Enum):
    """Freshness levels for briefings"""
    CURRENT = "current"  # Up-to-date, no concerns
    SLIGHTLY_OUTDATED = "slightly_outdated"  # < 90 days behind
    OUTDATED = "outdated"  # 90-180 days behind
    SEVERELY_OUTDATED = "severely_outdated"  # > 180 days behind
    OBSOLETE = "obsolete"  # Legislation adopted/amended after briefing


@dataclass
class FreshnessStatus:
    """Status of briefing freshness"""
    freshness_level: FreshnessLevel
    is_outdated: bool
    days_since_briefing: int
    days_outdated: int  # How many days behind latest event
    outdated_reason: Optional[str] = None
    latest_event: Optional[str] = None
    latest_event_date: Optional[datetime] = None
    recommendation: Optional[str] = None
    needs_ai_update: bool = False
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class FreshnessDetector:
    """
    Detects when EPRS briefings are outdated

    Analyzes the gap between:
    1. EPRS briefing publication date
    2. Current legislative procedure status
    3. Legislation adoption/entry into force dates

    Flags outdated briefings and recommends AI-generated updates.

    Example:
        detector = FreshnessDetector()

        # Check freshness
        status = await detector.check_briefing_freshness(
            briefing_date=datetime(2023, 1, 15),
            procedure_data={
                "status": "Adopted",
                "timeline": [
                    {"date": "2024-05-21", "event": "Adopted by Council"}
                ]
            }
        )

        if status.is_outdated:
            print(status.recommendation)
    """

    # Thresholds for outdated determination
    SLIGHTLY_OUTDATED_DAYS = 90
    OUTDATED_DAYS = 180
    SEVERELY_OUTDATED_DAYS = 365

    # Significant procedure events that make briefings outdated
    SIGNIFICANT_EVENTS = [
        "Adopted",
        "Published",
        "Entry into force",
        "Trilogue agreement",
        "Committee vote",
        "Plenary vote",
        "Council position",
        "Commission proposal amended"
    ]

    def __init__(self):
        """Initialize Freshness Detector"""
        logger.info("Initialized Freshness Detector")

    async def check_briefing_freshness(
        self,
        briefing_date: datetime,
        procedure_ref: Optional[str] = None,
        celex: Optional[str] = None,
        procedure_data: Optional[Dict[str, Any]] = None,
        legislation_data: Optional[Dict[str, Any]] = None,
        current_date: Optional[datetime] = None
    ) -> FreshnessStatus:
        """
        Check if EPRS briefing is outdated

        Args:
            briefing_date: When briefing was published
            procedure_ref: Legislative procedure reference (e.g., "2021/0106(COD)")
            celex: CELEX number of legislation
            procedure_data: OEIL procedure data (status, timeline)
            legislation_data: EUR-Lex legislation data (status, dates)
            current_date: Current date (defaults to now)

        Returns:
            FreshnessStatus with detailed analysis

        Example:
            status = await detector.check_briefing_freshness(
                briefing_date=datetime(2023, 6, 1),
                procedure_data={
                    "status": "Adopted",
                    "timeline": [
                        {"date": "2024-05-21", "event": "Council adoption"},
                        {"date": "2024-04-24", "event": "EP vote"}
                    ]
                }
            )
        """
        if current_date is None:
            current_date = datetime.now()

        logger.info(f"Checking freshness of briefing from {briefing_date.strftime('%Y-%m-%d')}")

        # Calculate age
        days_since_briefing = (current_date - briefing_date).days

        # Find latest significant event
        latest_event_date = briefing_date
        latest_event_name = "Briefing published"

        # Check procedure timeline
        if procedure_data and "timeline" in procedure_data:
            for event in procedure_data["timeline"]:
                event_date_str = event.get("date")
                event_name = event.get("event") or event.get("description", "")

                if event_date_str:
                    try:
                        event_date = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))

                        # Check if this is after briefing and is significant
                        if event_date > briefing_date:
                            if any(sig_event.lower() in event_name.lower() for sig_event in self.SIGNIFICANT_EVENTS):
                                if event_date > latest_event_date:
                                    latest_event_date = event_date
                                    latest_event_name = event_name

                    except (ValueError, AttributeError):
                        continue

        # Check legislation dates
        if legislation_data:
            # Entry into force
            if legislation_data.get("entry_into_force_date"):
                try:
                    eif_date = datetime.fromisoformat(str(legislation_data["entry_into_force_date"]).replace("Z", "+00:00"))
                    if eif_date > briefing_date and eif_date > latest_event_date:
                        latest_event_date = eif_date
                        latest_event_name = "Entry into force"
                except (ValueError, AttributeError):
                    pass

            # Adoption date
            if legislation_data.get("date_document"):
                try:
                    adoption_date = datetime.fromisoformat(str(legislation_data["date_document"]).replace("Z", "+00:00"))
                    if adoption_date > briefing_date and adoption_date > latest_event_date:
                        latest_event_date = adoption_date
                        latest_event_name = "Adopted"
                except (ValueError, AttributeError):
                    pass

        # Calculate how many days briefing is behind
        days_outdated = (latest_event_date - briefing_date).days

        # Determine freshness level
        freshness_level, is_outdated = self._determine_freshness_level(
            days_since_briefing=days_since_briefing,
            days_outdated=days_outdated,
            latest_event_name=latest_event_name
        )

        # Generate recommendation
        recommendation = self._generate_recommendation(
            freshness_level=freshness_level,
            days_outdated=days_outdated,
            latest_event_name=latest_event_name
        )

        # Determine if AI update needed
        needs_ai_update = freshness_level in [
            FreshnessLevel.OUTDATED,
            FreshnessLevel.SEVERELY_OUTDATED,
            FreshnessLevel.OBSOLETE
        ]

        # Build outdated reason
        outdated_reason = None
        if is_outdated:
            outdated_reason = f"Briefing predates {latest_event_name} by {days_outdated} days"

        return FreshnessStatus(
            freshness_level=freshness_level,
            is_outdated=is_outdated,
            days_since_briefing=days_since_briefing,
            days_outdated=days_outdated,
            outdated_reason=outdated_reason,
            latest_event=latest_event_name,
            latest_event_date=latest_event_date,
            recommendation=recommendation,
            needs_ai_update=needs_ai_update,
            metadata={
                "procedure_ref": procedure_ref,
                "celex": celex,
                "briefing_date": briefing_date.isoformat(),
                "current_date": current_date.isoformat()
            }
        )

    def _determine_freshness_level(
        self,
        days_since_briefing: int,
        days_outdated: int,
        latest_event_name: str
    ) -> tuple[FreshnessLevel, bool]:
        """
        Determine freshness level and whether briefing is outdated

        Args:
            days_since_briefing: Days since briefing published
            days_outdated: Days between briefing and latest event
            latest_event_name: Name of latest significant event

        Returns:
            (FreshnessLevel, is_outdated)
        """
        # Check for obsolete (major lifecycle events after briefing)
        obsolete_keywords = ["adopted", "entry into force", "published"]
        if any(keyword in latest_event_name.lower() for keyword in obsolete_keywords):
            if days_outdated > 30:  # Allow 30-day grace period
                return (FreshnessLevel.OBSOLETE, True)

        # Check time-based freshness
        if days_outdated <= 0:
            # Briefing is current (no events after it)
            return (FreshnessLevel.CURRENT, False)
        elif days_outdated < self.SLIGHTLY_OUTDATED_DAYS:
            # Slightly behind but acceptable
            return (FreshnessLevel.SLIGHTLY_OUTDATED, False)
        elif days_outdated < self.OUTDATED_DAYS:
            # Noticeably outdated
            return (FreshnessLevel.OUTDATED, True)
        elif days_outdated < self.SEVERELY_OUTDATED_DAYS:
            # Severely outdated
            return (FreshnessLevel.SEVERELY_OUTDATED, True)
        else:
            # Very old
            return (FreshnessLevel.SEVERELY_OUTDATED, True)

    def _generate_recommendation(
        self,
        freshness_level: FreshnessLevel,
        days_outdated: int,
        latest_event_name: str
    ) -> str:
        """
        Generate recommendation based on freshness level

        Args:
            freshness_level: Determined freshness level
            days_outdated: Days behind latest event
            latest_event_name: Latest event name

        Returns:
            Recommendation string
        """
        if freshness_level == FreshnessLevel.CURRENT:
            return "Briefing is current. No action needed."

        elif freshness_level == FreshnessLevel.SLIGHTLY_OUTDATED:
            return f"Briefing is slightly outdated ({days_outdated} days behind {latest_event_name}). Consider mentioning recent developments."

        elif freshness_level == FreshnessLevel.OUTDATED:
            return f"Briefing is outdated ({days_outdated} days behind {latest_event_name}). Recommend AI-generated update supplement."

        elif freshness_level == FreshnessLevel.SEVERELY_OUTDATED:
            return f"Briefing is severely outdated ({days_outdated} days behind {latest_event_name}). Strongly recommend AI-generated update or new briefing."

        elif freshness_level == FreshnessLevel.OBSOLETE:
            return f"Briefing is obsolete - legislation {latest_event_name.lower()} after briefing. Use AI-generated briefing based on current text."

        return "Unknown freshness level"

    async def batch_check_freshness(
        self,
        briefings: List[Dict[str, Any]]
    ) -> List[FreshnessStatus]:
        """
        Check freshness for multiple briefings

        Args:
            briefings: List of briefing dicts with dates and metadata

        Returns:
            List of FreshnessStatus results

        Example:
            briefings = [
                {
                    "briefing_date": datetime(2023, 1, 1),
                    "procedure_ref": "2021/0106(COD)",
                    "procedure_data": {...}
                },
                ...
            ]

            statuses = await detector.batch_check_freshness(briefings)
        """
        logger.info(f"Batch checking freshness for {len(briefings)} briefings")

        statuses = []

        for briefing in briefings:
            try:
                status = await self.check_briefing_freshness(
                    briefing_date=briefing.get("briefing_date"),
                    procedure_ref=briefing.get("procedure_ref"),
                    celex=briefing.get("celex"),
                    procedure_data=briefing.get("procedure_data"),
                    legislation_data=briefing.get("legislation_data")
                )
                statuses.append(status)

            except Exception as e:
                logger.error(f"Failed to check freshness for briefing: {str(e)}")
                # Add error status
                statuses.append(FreshnessStatus(
                    freshness_level=FreshnessLevel.CURRENT,
                    is_outdated=False,
                    days_since_briefing=0,
                    days_outdated=0,
                    recommendation="Error checking freshness",
                    metadata={"error": str(e)}
                ))

        # Log summary
        outdated_count = sum(1 for s in statuses if s.is_outdated)
        logger.info(f"Freshness check complete: {outdated_count}/{len(statuses)} outdated")

        return statuses

    def get_freshness_summary(
        self,
        statuses: List[FreshnessStatus]
    ) -> Dict[str, Any]:
        """
        Get summary statistics for freshness check results

        Args:
            statuses: List of FreshnessStatus results

        Returns:
            Summary statistics dictionary
        """
        total = len(statuses)

        if total == 0:
            return {
                "total": 0,
                "current": 0,
                "outdated": 0,
                "needs_ai_update": 0
            }

        current_count = sum(1 for s in statuses if s.freshness_level == FreshnessLevel.CURRENT)
        slightly_outdated = sum(1 for s in statuses if s.freshness_level == FreshnessLevel.SLIGHTLY_OUTDATED)
        outdated = sum(1 for s in statuses if s.freshness_level == FreshnessLevel.OUTDATED)
        severely_outdated = sum(1 for s in statuses if s.freshness_level == FreshnessLevel.SEVERELY_OUTDATED)
        obsolete = sum(1 for s in statuses if s.freshness_level == FreshnessLevel.OBSOLETE)
        needs_ai_update = sum(1 for s in statuses if s.needs_ai_update)

        avg_days_outdated = sum(s.days_outdated for s in statuses) / total if total > 0 else 0

        return {
            "total": total,
            "current": current_count,
            "slightly_outdated": slightly_outdated,
            "outdated": outdated,
            "severely_outdated": severely_outdated,
            "obsolete": obsolete,
            "needs_ai_update": needs_ai_update,
            "avg_days_outdated": int(avg_days_outdated),
            "freshness_rate": (current_count / total * 100) if total > 0 else 0
        }


# Global singleton
_freshness_detector: Optional[FreshnessDetector] = None


def get_freshness_detector() -> FreshnessDetector:
    """
    Get global Freshness Detector instance

    Returns:
        FreshnessDetector instance
    """
    global _freshness_detector

    if _freshness_detector is None:
        _freshness_detector = FreshnessDetector()

    return _freshness_detector
