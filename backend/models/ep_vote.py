"""
EP Vote models — committee + plenary roll-call results.

One ``EpVote`` per vote (a committee final vote, or a plenary roll-call on one
minutes sub-item), one ``EpVoteRecord`` per MEP. Both are public EP reference
data (see migration 098). Keyed by the OEIL procedure ref / carriage so a vote
links to the same dossier the rest of MEUB aligns on.

Populated by ``scripts/sync_ep_votes.py`` via ``services/scrapers/ep_votes_scraper.py``.
"""

from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, Boolean, Date, DateTime, Text, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class EpVote(Base):
    """A single EP vote (committee final vote or plenary roll-call sub-item).

    Distinct from the dormant HowTheyVote ``EPVote`` (table ``ep_votes``); this
    is the doceo-sourced roll-call store backing the MEUB "Votes" feature.
    """
    __tablename__ = "ep_roll_call_votes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Stable dedup key: 'committee|<report_ref>' or 'plenary|<sitting>|<item>'.
    vote_key = Column(Text, nullable=False, unique=True)

    level = Column(String, nullable=False)  # 'committee' | 'plenary'

    # Cross-references
    procedure_ref = Column(String)          # OEIL ref, e.g. "2025/0413(NLE)"
    carriage_id = Column(UUID(as_uuid=True), ForeignKey("legislative_carriages.id"))
    report_ref = Column(String)             # "A10-0144/2026"
    ta_reference = Column(String)           # "P10_TA(2026)0188"

    # Labels
    title = Column(Text)
    subject = Column(Text)
    committee_code = Column(String)

    # When / where
    vote_date = Column(Date)
    sitting_date = Column(Date)
    item_number = Column(String)            # "8.1"

    # Outcome
    result = Column(String)                 # '+', '-', 'adopted', 'rejected'
    votes_for = Column(Integer)
    votes_against = Column(Integer)
    votes_abstention = Column(Integer)
    vote_type = Column(String)              # 'rcv', 'final'

    # Pre-computed aggregates (so list cards never load records)
    group_breakdown = Column(JSONB, default=dict)     # {"ECR": {"+":44,"-":1,"0":1}, ...}
    country_breakdown = Column(JSONB, default=dict)   # v2
    total_records = Column(Integer, nullable=False, default=0)

    source_url = Column(Text)
    scraped_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    records = relationship(
        "EpVoteRecord", back_populates="vote", cascade="all, delete-orphan"
    )
    carriage = relationship("LegislativeCarriage", foreign_keys=[carriage_id])

    def __repr__(self):
        return f"<EpVote {self.level} {self.report_ref or self.item_number} {self.result}>"


class EpVoteRecord(Base):
    """One MEP's choice within a vote."""
    __tablename__ = "ep_roll_call_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    vote_id = Column(UUID(as_uuid=True), ForeignKey("ep_roll_call_votes.id"), nullable=False)
    mep_name = Column(Text, nullable=False)
    political_group = Column(String)        # "ECR", "S&D", "Verts/ALE", "The Left", "NI"
    country = Column(String)                # v2
    vote_choice = Column(String, nullable=False)  # '+', '-', '0'
    is_intention = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.now)

    vote = relationship("EpVote", back_populates="records")

    def __repr__(self):
        return f"<EpVoteRecord {self.mep_name} {self.vote_choice} ({self.political_group})>"
