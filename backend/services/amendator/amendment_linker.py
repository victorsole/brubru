"""
Amendment Linker Service

Priority #4: Amendator-Legislative Train Integration
Auto-links amendments to tracked legislative files based on CELEX numbers.
"""

from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from models.amendment import Amendment
from models.legislative_train import LegislativeCarriage, UserCarriageTrack


class AmendmentLinker:
    """
    Service to link amendments to tracked legislative carriages.

    When a user saves an amendment, this service checks if the document_id (CELEX)
    matches any of their tracked files and automatically links them.
    """

    def __init__(self, db: Session):
        self.db = db

    def find_matching_carriage(self, document_id: str, user_id: UUID) -> Optional[LegislativeCarriage]:
        """
        Find a tracked carriage that matches the given document_id (CELEX).

        Args:
            document_id: The CELEX number or document identifier
            user_id: The user's ID

        Returns:
            LegislativeCarriage if found, None otherwise
        """
        # Normalize CELEX (remove 'eurlex-' prefix if present)
        celex = document_id.replace('eurlex-', '').strip()

        # Find carriages that the user is tracking and have this CELEX
        carriage = self.db.query(LegislativeCarriage).join(
            UserCarriageTrack,
            UserCarriageTrack.carriage_id == LegislativeCarriage.id
        ).filter(
            and_(
                UserCarriageTrack.user_id == user_id,
                LegislativeCarriage.celex_numbers.contains([celex])
            )
        ).first()

        return carriage

    def auto_link_amendment(self, amendment: Amendment) -> bool:
        """
        Automatically link an amendment to a tracked carriage if matching CELEX found.

        Args:
            amendment: The Amendment to potentially link

        Returns:
            True if linked, False otherwise
        """
        if amendment.carriage_id:
            # Already linked
            return True

        carriage = self.find_matching_carriage(
            document_id=amendment.document_id,
            user_id=amendment.user_id
        )

        if carriage:
            amendment.carriage_id = carriage.id
            amendment.procedure_reference = carriage.oeil_procedure_ref
            return True

        return False

    def link_amendments_for_carriage(self, carriage_id: UUID, user_id: UUID) -> int:
        """
        Link all existing amendments that match a carriage's CELEX numbers.

        This can be called when a user starts tracking a new file to retroactively
        link any amendments they've already created for that legislation.

        Args:
            carriage_id: The carriage to link amendments to
            user_id: The user's ID

        Returns:
            Number of amendments linked
        """
        carriage = self.db.query(LegislativeCarriage).filter(
            LegislativeCarriage.id == carriage_id
        ).first()

        if not carriage or not carriage.celex_numbers:
            return 0

        linked_count = 0

        # Find user's amendments that match any of the carriage's CELEX numbers
        for celex in carriage.celex_numbers:
            # Match both 'eurlex-CELEX' and plain 'CELEX' formats
            amendments = self.db.query(Amendment).filter(
                and_(
                    Amendment.user_id == user_id,
                    Amendment.carriage_id.is_(None),
                    Amendment.document_id.in_([celex, f'eurlex-{celex}'])
                )
            ).all()

            for amendment in amendments:
                amendment.carriage_id = carriage_id
                amendment.procedure_reference = carriage.oeil_procedure_ref
                linked_count += 1

        if linked_count > 0:
            self.db.commit()

        return linked_count

    def get_amendments_for_carriage(self, carriage_id: UUID, user_id: UUID) -> list:
        """
        Get all amendments linked to a specific carriage.

        Args:
            carriage_id: The carriage ID
            user_id: The user's ID

        Returns:
            List of Amendment objects
        """
        return self.db.query(Amendment).filter(
            and_(
                Amendment.carriage_id == carriage_id,
                Amendment.user_id == user_id
            )
        ).order_by(Amendment.element_index).all()

    def count_amendments_by_carriage(self, user_id: UUID) -> dict:
        """
        Get amendment counts for all tracked carriages.

        Args:
            user_id: The user's ID

        Returns:
            Dict mapping carriage_id to amendment count
        """
        from sqlalchemy import func

        results = self.db.query(
            Amendment.carriage_id,
            func.count(Amendment.id).label('count')
        ).filter(
            and_(
                Amendment.user_id == user_id,
                Amendment.carriage_id.isnot(None)
            )
        ).group_by(Amendment.carriage_id).all()

        return {str(r.carriage_id): r.count for r in results}


def get_amendment_linker(db: Session) -> AmendmentLinker:
    """Factory function to get an AmendmentLinker instance."""
    return AmendmentLinker(db)
