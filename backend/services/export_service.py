"""
Data Export Service

Provides functionality to export user data in various formats.
Part of My EU Bubble - Phase 5: Advanced Features

Supported formats:
- CSV: Reading lists, analytics data, document metadata
- JSON: Full data export with metadata
- Plain text: Document content export
"""

import logging
import csv
import json
from io import StringIO, BytesIO
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select, and_

from ..models.user_document import UserDocument
from ..models.user_feed_read import UserFeedRead
from ..models.user_saved_entry import UserSavedEntry
from ..models.rss_entry import RSSEntry

logger = logging.getLogger(__name__)


class ExportService:
    """
    Service for exporting user data in various formats.

    Supports:
    - Document exports (all types)
    - Reading history export
    - Analytics data export
    - Saved entries export
    """

    def __init__(self, db_session: Session):
        """
        Initialize export service.

        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        logger.info("Initialized Export Service")

    def export_documents_csv(self, user_id: str) -> str:
        """
        Export user documents as CSV.

        Args:
            user_id: User UUID

        Returns:
            CSV string
        """
        logger.info(f"Exporting documents as CSV for user {user_id}")

        try:
            # Get all user documents
            stmt = select(UserDocument).where(
                UserDocument.user_id == user_id
            ).order_by(UserDocument.created_at.desc())

            documents = self.db.execute(stmt).scalars().all()

            # Create CSV
            output = StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow([
                "ID",
                "Type",
                "Title",
                "Content Preview",
                "CELEX Number",
                "Procedure Reference",
                "Policy Areas",
                "Amendment Status",
                "Word Count",
                "Created At",
                "Updated At"
            ])

            # Write data
            for doc in documents:
                content_preview = (doc.content[:200] + "...") if doc.content else ""
                policy_areas = ", ".join(doc.policy_areas) if doc.policy_areas else ""

                writer.writerow([
                    str(doc.id),
                    doc.document_type,
                    doc.title,
                    content_preview,
                    doc.celex_number or "",
                    doc.procedure_reference or "",
                    policy_areas,
                    doc.amendment_status or "",
                    doc.word_count or 0,
                    doc.created_at.isoformat(),
                    doc.updated_at.isoformat()
                ])

            csv_content = output.getvalue()
            output.close()

            logger.info(f"Exported {len(documents)} documents as CSV")
            return csv_content

        except Exception as e:
            logger.error(f"Failed to export documents as CSV: {e}")
            raise

    def export_reading_list_csv(self, user_id: str) -> str:
        """
        Export user reading history as CSV.

        Args:
            user_id: User UUID

        Returns:
            CSV string
        """
        logger.info(f"Exporting reading list as CSV for user {user_id}")

        try:
            # Get user read entries with RSS entry details
            stmt = select(UserFeedRead).where(
                UserFeedRead.user_id == user_id
            ).order_by(UserFeedRead.read_at.desc())

            reads = self.db.execute(stmt).scalars().all()

            # Create CSV
            output = StringIO()
            writer = csv.writer(output)

            # Write header
            writer.writerow([
                "Entry ID",
                "Title",
                "Link",
                "Source",
                "Read At",
                "Reading Time (seconds)",
                "Read Count",
                "Clicked Link"
            ])

            # Write data
            for read in reads:
                # Get RSS entry details
                entry_stmt = select(RSSEntry).where(RSSEntry.id == read.rss_entry_id)
                entry = self.db.execute(entry_stmt).scalar_one_or_none()

                if entry:
                    writer.writerow([
                        str(entry.id),
                        entry.title,
                        entry.link,
                        entry.institution or "",
                        read.read_at.isoformat() if read.read_at else "",
                        read.reading_time_seconds or 0,
                        read.read_count,
                        read.clicked_link
                    ])

            csv_content = output.getvalue()
            output.close()

            logger.info(f"Exported {len(reads)} read entries as CSV")
            return csv_content

        except Exception as e:
            logger.error(f"Failed to export reading list as CSV: {e}")
            raise

    def export_analytics_json(self, user_id: str) -> Dict[str, Any]:
        """
        Export user analytics data as JSON.

        Args:
            user_id: User UUID

        Returns:
            Analytics dictionary
        """
        logger.info(f"Exporting analytics as JSON for user {user_id}")

        try:
            analytics = {
                "user_id": user_id,
                "exported_at": datetime.now().isoformat(),
                "documents": {},
                "reading_activity": {},
                "saved_entries": {}
            }

            # Document statistics
            stmt = select(UserDocument).where(UserDocument.user_id == user_id)
            documents = self.db.execute(stmt).scalars().all()

            analytics["documents"] = {
                "total": len(documents),
                "by_type": self._count_by_field(documents, "document_type"),
                "by_policy_area": self._count_policy_areas(documents),
                "total_word_count": sum(doc.word_count or 0 for doc in documents)
            }

            # Reading activity
            stmt = select(UserFeedRead).where(UserFeedRead.user_id == user_id)
            reads = self.db.execute(stmt).scalars().all()

            analytics["reading_activity"] = {
                "total_reads": len(reads),
                "total_reading_time_seconds": sum(r.reading_time_seconds or 0 for r in reads),
                "average_reading_time_seconds": (
                    sum(r.reading_time_seconds or 0 for r in reads) / len(reads)
                    if reads else 0
                ),
                "click_through_rate": (
                    sum(1 for r in reads if r.clicked_link) / len(reads)
                    if reads else 0
                )
            }

            # Saved entries
            stmt = select(UserSavedEntry).where(UserSavedEntry.user_id == user_id)
            saved = self.db.execute(stmt).scalars().all()

            analytics["saved_entries"] = {
                "total_saved": len(saved),
                "total_starred": sum(1 for s in saved if s.is_starred),
                "by_collection": self._count_by_field(saved, "collection_name")
            }

            logger.info("Exported analytics as JSON")
            return analytics

        except Exception as e:
            logger.error(f"Failed to export analytics as JSON: {e}")
            raise

    def export_full_data_json(self, user_id: str) -> Dict[str, Any]:
        """
        Export all user data as comprehensive JSON.

        Args:
            user_id: User UUID

        Returns:
            Complete data dictionary
        """
        logger.info(f"Exporting full data as JSON for user {user_id}")

        try:
            full_data = {
                "user_id": user_id,
                "exported_at": datetime.now().isoformat(),
                "documents": [],
                "reading_history": [],
                "saved_entries": [],
                "analytics": {}
            }

            # Export documents
            stmt = select(UserDocument).where(UserDocument.user_id == user_id)
            documents = self.db.execute(stmt).scalars().all()

            full_data["documents"] = [
                {
                    "id": str(doc.id),
                    "type": doc.document_type,
                    "title": doc.title,
                    "content": doc.content,
                    "celex_number": doc.celex_number,
                    "procedure_reference": doc.procedure_reference,
                    "policy_areas": doc.policy_areas,
                    "amendment_status": doc.amendment_status,
                    "word_count": doc.word_count,
                    "metadata": doc.metadata,
                    "created_at": doc.created_at.isoformat(),
                    "updated_at": doc.updated_at.isoformat()
                }
                for doc in documents
            ]

            # Export reading history
            stmt = select(UserFeedRead).where(UserFeedRead.user_id == user_id)
            reads = self.db.execute(stmt).scalars().all()

            for read in reads:
                entry_stmt = select(RSSEntry).where(RSSEntry.id == read.rss_entry_id)
                entry = self.db.execute(entry_stmt).scalar_one_or_none()

                if entry:
                    full_data["reading_history"].append({
                        "entry_id": str(entry.id),
                        "title": entry.title,
                        "link": entry.link,
                        "source": entry.institution,
                        "read_at": read.read_at.isoformat() if read.read_at else None,
                        "reading_time_seconds": read.reading_time_seconds,
                        "read_count": read.read_count,
                        "clicked_link": read.clicked_link
                    })

            # Export saved entries
            stmt = select(UserSavedEntry).where(UserSavedEntry.user_id == user_id)
            saved = self.db.execute(stmt).scalars().all()

            for save in saved:
                entry_stmt = select(RSSEntry).where(RSSEntry.id == save.rss_entry_id)
                entry = self.db.execute(entry_stmt).scalar_one_or_none()

                if entry:
                    full_data["saved_entries"].append({
                        "entry_id": str(entry.id),
                        "title": entry.title,
                        "link": entry.link,
                        "notes": save.notes,
                        "tags": save.tags,
                        "collection_name": save.collection_name,
                        "is_starred": save.is_starred,
                        "saved_at": save.saved_at.isoformat()
                    })

            # Include analytics
            full_data["analytics"] = self.export_analytics_json(user_id)

            logger.info("Exported full data as JSON")
            return full_data

        except Exception as e:
            logger.error(f"Failed to export full data as JSON: {e}")
            raise

    def export_documents_text(self, user_id: str, document_type: Optional[str] = None) -> str:
        """
        Export document content as plain text.

        Args:
            user_id: User UUID
            document_type: Optional filter by document type

        Returns:
            Plain text string
        """
        logger.info(f"Exporting documents as text for user {user_id}")

        try:
            stmt = select(UserDocument).where(UserDocument.user_id == user_id)

            if document_type:
                stmt = stmt.where(UserDocument.document_type == document_type)

            stmt = stmt.order_by(UserDocument.created_at.desc())
            documents = self.db.execute(stmt).scalars().all()

            text_content = f"Documents Export for User {user_id}\n"
            text_content += f"Exported at: {datetime.now().isoformat()}\n"
            text_content += f"Total documents: {len(documents)}\n"
            text_content += "=" * 80 + "\n\n"

            for doc in documents:
                text_content += f"Document ID: {doc.id}\n"
                text_content += f"Type: {doc.document_type}\n"
                text_content += f"Title: {doc.title}\n"
                text_content += f"Created: {doc.created_at.isoformat()}\n"

                if doc.celex_number:
                    text_content += f"CELEX: {doc.celex_number}\n"
                if doc.procedure_reference:
                    text_content += f"Procedure: {doc.procedure_reference}\n"
                if doc.policy_areas:
                    text_content += f"Policy Areas: {', '.join(doc.policy_areas)}\n"

                text_content += "\n--- Content ---\n"
                text_content += doc.content or "(No content)"
                text_content += "\n\n" + "=" * 80 + "\n\n"

            logger.info(f"Exported {len(documents)} documents as text")
            return text_content

        except Exception as e:
            logger.error(f"Failed to export documents as text: {e}")
            raise

    def _count_by_field(self, items: List, field_name: str) -> Dict[str, int]:
        """Count items by a specific field."""
        counts = {}
        for item in items:
            value = getattr(item, field_name, None)
            if value:
                counts[value] = counts.get(value, 0) + 1
        return counts

    def _count_policy_areas(self, documents: List[UserDocument]) -> Dict[str, int]:
        """Count documents by policy area."""
        counts = {}
        for doc in documents:
            if doc.policy_areas:
                for area in doc.policy_areas:
                    counts[area] = counts.get(area, 0) + 1
        return counts
