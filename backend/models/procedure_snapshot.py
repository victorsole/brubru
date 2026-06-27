"""
Procedure Snapshot model — Phase 3, step 3.2.

One row per legislative procedure (carriage) per day, written by the Phase 3.3
daily job from services.snapshots.snapshot_builder.build_snapshot(). It records the
procedure's SLOW state plus the 5 FAST-SIGNAL counts so the predictors can see count
TRAJECTORIES day over day, not just the current single-snapshot view.

Schema mirrors migrations/191_procedure_snapshots.sql exactly.
"""

from sqlalchemy import (
    Column, BigInteger, Integer, Boolean, Text, Date, DateTime, ForeignKey,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.sql import func

from core.database import Base


class ProcedureSnapshot(Base):
    __tablename__ = "procedure_snapshots"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    carriage_id = Column(
        UUID(as_uuid=True),
        ForeignKey("legislative_carriages.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_date = Column(Date, nullable=False)
    oeil_procedure_ref = Column(Text, nullable=True)

    # slow state (canonical, off the carriage row)
    current_status = Column(Text, nullable=True)
    days_in_current_status = Column(Integer, nullable=False, default=0)
    lead_committee = Column(Text, nullable=True)
    rapporteur_mep_id = Column(Text, nullable=True)
    text_type = Column(Text, nullable=True)
    policy_areas = Column(ARRAY(Text), nullable=False, default=list)
    celex_numbers = Column(ARRAY(Text), nullable=False, default=list)
    num_opinion_committees = Column(Integer, nullable=False, default=0)
    num_status_changes = Column(Integer, nullable=False, default=0)

    # fast-signal counts (the value the predictors are blind to)
    num_amendments = Column(Integer, nullable=False, default=0)
    num_documents = Column(Integer, nullable=False, default=0)
    num_committee_work = Column(Integer, nullable=False, default=0)
    num_lobby_meetings = Column(Integer, nullable=False, default=0)
    num_eprs_briefings = Column(Integer, nullable=False, default=0)

    # reconciliation flags (honest)
    ref_linked = Column(Boolean, nullable=False, default=False)
    is_estimated = Column(Boolean, nullable=False, default=False)

    # 'daily' = fully measured live; 'bootstrap' = OEIL-events history (counts not measured)
    snapshot_source = Column(Text, nullable=False, default="daily")

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("carriage_id", "snapshot_date", name="procedure_snapshots_carriage_date_uq"),
        Index("idx_procedure_snapshots_carriage_date", "carriage_id", "snapshot_date"),
        Index("idx_procedure_snapshots_date", "snapshot_date"),
    )
