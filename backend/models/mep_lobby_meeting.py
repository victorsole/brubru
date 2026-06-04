"""
MEP lobby meetings - the Parliament side of MEUB Lobby Meetings.

One row per (MEP, organisation, date) meeting, unioned from OEIL Transparency +
MEP profile pages (source tracked + deduped). Carries the procedure_ref (dossier
anchor) and the matched Transparency Register identity (website, profile, id).
"""

from sqlalchemy import Column, String, Date, DateTime, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

from core.database import Base


class MepLobbyMeeting(Base):
    __tablename__ = "mep_lobby_meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    procedure_ref = Column(String(50), nullable=True, index=True)   # dossier anchor
    mep_id = Column(String(20), nullable=True, index=True)
    mep_name = Column(String(255), nullable=True)
    role = Column(String(80), nullable=True)                        # rapporteur / shadow / chair / member
    committee = Column(String(20), nullable=True)
    meeting_date = Column(Date, nullable=True, index=True)

    organisation = Column(String(500), nullable=False)
    organisation_norm = Column(String(500), nullable=True)
    transparency_register_id = Column(String(50), nullable=True)
    org_website = Column(Text, nullable=True)        # org's own site (Transparency Register)
    org_register_url = Column(Text, nullable=True)   # the register profile page

    source = Column(String(20), nullable=False, default="oeil")     # oeil | profile | both
    source_url = Column(Text, nullable=True)

    scraped_at = Column(DateTime, default=datetime.utcnow)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("mep_id", "organisation_norm", "meeting_date", name="uq_mep_meeting"),
        Index("ix_mep_meeting_org", "organisation_norm"),
    )
