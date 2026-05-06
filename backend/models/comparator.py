"""
Comparator Models

SQLAlchemy models for the Comparator feature: spreadsheet-style legislative-file
comparison grids with verifiable per-cell citations.

Schema lives in migrations/054_comparator.sql.
"""

from sqlalchemy import Column, String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from core.database import Base


class ComparatorGrid(Base):
    """A user-owned grid: rows are legislative-file refs, columns are aspects."""

    __tablename__ = "comparator_grids"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    name = Column(Text, nullable=False)
    file_refs = Column(JSONB, nullable=False, default=list)
    columns = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    cells = relationship(
        "ComparatorCell",
        back_populates="grid",
        cascade="all, delete-orphan",
    )


class ComparatorCell(Base):
    """One extracted cell: (grid_id, file_ref, column_key) -> value + citation."""

    __tablename__ = "comparator_cells"
    __table_args__ = (
        UniqueConstraint("grid_id", "file_ref", "column_key", name="uq_comparator_cell"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    grid_id = Column(
        UUID(as_uuid=True),
        ForeignKey("comparator_grids.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_ref = Column(Text, nullable=False)
    column_key = Column(Text, nullable=False)
    value_text = Column(Text, nullable=True)
    citation = Column(JSONB, nullable=True)
    computation_status = Column(Text, nullable=False, default="pending")
    computation_error = Column(Text, nullable=True)
    computed_at = Column(DateTime(timezone=True), nullable=True)

    grid = relationship("ComparatorGrid", back_populates="cells")
