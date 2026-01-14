"""
Legislative Tracking Service

Tracks EU legislation and procedure progress for personalized monitoring.
Part of My EU Bubble - Phase 5: Advanced Features

Features:
- Track legislation by CELEX number
- Monitor OEIL procedure progress
- Detect status changes
- Generate progress summaries
- Alert on key milestones
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from models.user_document import UserDocument
from models.rss_entry import RSSEntry
from .scrapers.oeil_scraper import OEILScraper
from .ai.content_analyzer import ContentAnalyzer

logger = logging.getLogger(__name__)


class LegislativeTracker:
    """
    Service for tracking EU legislative procedures and documents.

    Monitors:
    - CELEX-referenced legislation status
    - OEIL procedure progress
    - Related amendments and committee opinions
    - Voting schedules and results
    """

    def __init__(self, db_session: Session):
        """
        Initialize legislative tracker.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.oeil_scraper = OEILScraper()
        self.content_analyzer = ContentAnalyzer()
        logger.info("Initialized Legislative Tracker")

    async def track_legislation_by_celex(
        self,
        celex_number: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Track specific legislation by CELEX number.

        Args:
            celex_number: CELEX identifier (e.g., "32024R1234")
            user_id: User UUID

        Returns:
            Tracking information including related documents
        """
        logger.info(f"Tracking legislation {celex_number} for user {user_id}")

        tracking_info = {
            "celex_number": celex_number,
            "status": "unknown",
            "related_amendments": [],
            "related_rss_entries": [],
            "procedure_reference": None,
            "last_update": None
        }

        try:
            # Find related user documents (amendments, analyses)
            stmt = select(UserDocument).where(
                and_(
                    UserDocument.user_id == user_id,
                    UserDocument.celex_number == celex_number
                )
            )
            user_docs = self.db.execute(stmt).scalars().all()

            tracking_info["related_amendments"] = [
                {
                    "id": str(doc.id),
                    "title": doc.title,
                    "type": doc.document_type,
                    "status": doc.amendment_status if hasattr(doc, 'amendment_status') else None,
                    "updated_at": doc.updated_at.isoformat()
                }
                for doc in user_docs
            ]

            # Find related RSS entries
            stmt = select(RSSEntry).where(
                RSSEntry.metadata.op('@>')({'celex_numbers': [celex_number]})
            )
            rss_entries = self.db.execute(stmt).scalars().all()

            tracking_info["related_rss_entries"] = [
                {
                    "id": str(entry.id),
                    "title": entry.title,
                    "published_at": entry.published_at.isoformat(),
                    "source": entry.institution,
                    "link": entry.link
                }
                for entry in rss_entries[:10]  # Limit to 10 most recent
            ]

            # Try to extract procedure reference from CELEX
            if celex_number:
                tracking_info["procedure_reference"] = self._extract_procedure_from_celex(celex_number)

            tracking_info["last_update"] = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            logger.error(f"Failed to track legislation {celex_number}: {e}")
            tracking_info["error"] = str(e)

        return tracking_info

    async def track_procedure(
        self,
        procedure_reference: str,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Track OEIL procedure progress.

        Args:
            procedure_reference: OEIL procedure reference (e.g., "2024/0123(COD)")
            user_id: User UUID

        Returns:
            Procedure tracking information
        """
        logger.info(f"Tracking procedure {procedure_reference} for user {user_id}")

        tracking_info = {
            "procedure_reference": procedure_reference,
            "status": "unknown",
            "current_stage": None,
            "timeline": [],
            "related_documents": [],
            "next_milestone": None,
            "last_update": None
        }

        try:
            # Fetch procedure details from OEIL
            procedure_data = await self.oeil_scraper.get_procedure_details(procedure_reference)

            if procedure_data:
                tracking_info.update({
                    "title": procedure_data.get("title"),
                    "status": procedure_data.get("status"),
                    "current_stage": procedure_data.get("current_stage"),
                    "timeline": procedure_data.get("events", []),
                    "committees": procedure_data.get("committees", []),
                    "rapporteurs": procedure_data.get("rapporteurs", [])
                })

                # Detect next milestone
                tracking_info["next_milestone"] = self._detect_next_milestone(
                    procedure_data.get("events", [])
                )

            # Find related user documents
            stmt = select(UserDocument).where(
                and_(
                    UserDocument.user_id == user_id,
                    UserDocument.procedure_reference == procedure_reference
                )
            )
            user_docs = self.db.execute(stmt).scalars().all()

            tracking_info["related_documents"] = [
                {
                    "id": str(doc.id),
                    "title": doc.title,
                    "type": doc.document_type,
                    "updated_at": doc.updated_at.isoformat()
                }
                for doc in user_docs
            ]

            tracking_info["last_update"] = datetime.now(timezone.utc).isoformat()

        except Exception as e:
            logger.error(f"Failed to track procedure {procedure_reference}: {e}")
            tracking_info["error"] = str(e)

        return tracking_info

    async def get_user_tracked_items(
        self,
        user_id: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get all tracked items for a user.

        Args:
            user_id: User UUID

        Returns:
            Dictionary with tracked legislation and procedures
        """
        logger.info(f"Getting tracked items for user {user_id}")

        tracked_items = {
            "legislation": [],
            "procedures": [],
            "amendments": []
        }

        try:
            # Get all user documents with CELEX or procedure references
            stmt = select(UserDocument).where(
                and_(
                    UserDocument.user_id == user_id,
                    or_(
                        UserDocument.celex_number.isnot(None),
                        UserDocument.procedure_reference.isnot(None)
                    )
                )
            ).order_by(UserDocument.updated_at.desc())

            user_docs = self.db.execute(stmt).scalars().all()

            # Extract unique CELEX numbers and procedures
            celex_numbers = set()
            procedures = set()

            for doc in user_docs:
                if doc.celex_number:
                    celex_numbers.add(doc.celex_number)
                if doc.procedure_reference:
                    procedures.add(doc.procedure_reference)

                if doc.document_type == 'amendment':
                    tracked_items["amendments"].append({
                        "id": str(doc.id),
                        "title": doc.title,
                        "celex_number": doc.celex_number,
                        "procedure_reference": doc.procedure_reference,
                        "status": doc.amendment_status,
                        "updated_at": doc.updated_at.isoformat()
                    })

            # Add unique legislation
            tracked_items["legislation"] = [
                {"celex_number": celex} for celex in celex_numbers
            ]

            # Add unique procedures
            tracked_items["procedures"] = [
                {"procedure_reference": proc} for proc in procedures
            ]

        except Exception as e:
            logger.error(f"Failed to get tracked items for user {user_id}: {e}")

        return tracked_items

    async def detect_status_changes(
        self,
        user_id: str,
        since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Detect status changes in tracked legislation/procedures.

        Args:
            user_id: User UUID
            since_hours: Check for changes in last N hours

        Returns:
            List of detected changes
        """
        logger.info(f"Detecting status changes for user {user_id} (last {since_hours}h)")

        changes = []

        try:
            # Get tracked items
            tracked = await self.get_user_tracked_items(user_id)

            # Check each tracked procedure for updates
            for proc_item in tracked["procedures"]:
                proc_ref = proc_item["procedure_reference"]

                try:
                    # Fetch latest procedure data
                    procedure_data = await self.oeil_scraper.get_procedure_details(proc_ref)

                    if procedure_data and procedure_data.get("events"):
                        # Check if there are recent events
                        recent_events = [
                            event for event in procedure_data["events"]
                            if self._is_recent_event(event, since_hours)
                        ]

                        if recent_events:
                            changes.append({
                                "type": "procedure_update",
                                "procedure_reference": proc_ref,
                                "title": procedure_data.get("title"),
                                "recent_events": recent_events,
                                "detected_at": datetime.now(timezone.utc).isoformat()
                            })

                except Exception as e:
                    logger.warning(f"Failed to check procedure {proc_ref}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to detect status changes: {e}")

        return changes

    def _extract_procedure_from_celex(self, celex_number: str) -> Optional[str]:
        """
        Extract procedure reference from CELEX number if possible.

        Args:
            celex_number: CELEX identifier

        Returns:
            Procedure reference or None
        """
        # This is a simplified extraction - actual implementation would query EUR-Lex
        # For now, return None as we don't have direct mapping
        return None

    def _detect_next_milestone(self, events: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Detect next milestone in procedure timeline.

        Args:
            events: List of procedure events

        Returns:
            Next milestone information or None
        """
        if not events:
            return None

        # Sort events by date
        sorted_events = sorted(
            events,
            key=lambda x: x.get("date", ""),
            reverse=False
        )

        # Find first future event
        now = datetime.now(timezone.utc)

        for event in sorted_events:
            event_date_str = event.get("date")
            if event_date_str:
                try:
                    event_date = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
                    if event_date > now:
                        return {
                            "date": event_date_str,
                            "type": event.get("type"),
                            "description": event.get("description")
                        }
                except Exception:
                    continue

        return None

    def _is_recent_event(self, event: Dict[str, Any], hours: int) -> bool:
        """
        Check if event occurred in last N hours.

        Args:
            event: Event dictionary
            hours: Hours threshold

        Returns:
            True if event is recent
        """
        event_date_str = event.get("date")
        if not event_date_str:
            return False

        try:
            event_date = datetime.fromisoformat(event_date_str.replace("Z", "+00:00"))
            now = datetime.now(timezone.utc)
            time_diff = (now - event_date).total_seconds() / 3600

            return 0 <= time_diff <= hours

        except Exception:
            return False

    async def generate_progress_summary(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Generate summary of legislative progress for user.

        Args:
            user_id: User UUID

        Returns:
            Progress summary with statistics and highlights
        """
        logger.info(f"Generating progress summary for user {user_id}")

        summary = {
            "total_tracked": 0,
            "active_procedures": 0,
            "pending_amendments": 0,
            "recent_updates": [],
            "upcoming_milestones": [],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        try:
            # Get tracked items
            tracked = await self.get_user_tracked_items(user_id)

            summary["total_tracked"] = (
                len(tracked["legislation"]) +
                len(tracked["procedures"])
            )
            summary["active_procedures"] = len(tracked["procedures"])
            summary["pending_amendments"] = len([
                a for a in tracked["amendments"]
                if a.get("status") in ["draft", "submitted"]
            ])

            # Get recent changes
            recent_changes = await self.detect_status_changes(user_id, since_hours=72)
            summary["recent_updates"] = recent_changes[:5]  # Top 5

        except Exception as e:
            logger.error(f"Failed to generate progress summary: {e}")
            summary["error"] = str(e)

        return summary
