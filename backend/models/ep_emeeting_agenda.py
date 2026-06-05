"""
EP eMeeting committee-agenda model.

One row per European Parliament committee OJ (agenda) ingested from the eMeeting
open JSON API. The full item/document tree lives in ``items`` (JSONB);
``procedure_refs`` + ``rapporteurs`` are denormalised for filtering and MEUB
anchor linking. See migration 110 and services/scrapers/ep_emeeting_client.py.
"""

from sqlalchemy import Column, String, Text, Date, DateTime, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func
import uuid

from core.database import Base


class EpEmeetingAgenda(Base):
    __tablename__ = "ep_emeeting_agendas"
    __table_args__ = (
        UniqueConstraint("oj_reference", name="ep_emeeting_agendas_oj_reference_unique"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    oj_reference = Column(Text, nullable=False)
    committee_code = Column(String(10), nullable=False, index=True)
    committee_name = Column(Text)
    meeting_date = Column(Date, index=True)
    meeting_reference = Column(Text)

    title = Column(Text, nullable=False)
    public_url = Column(Text)
    body_txt = Column(Text)
    body_html = Column(Text)
    agenda_pdf_url = Column(Text)

    items = Column(JSONB, default=list)
    procedure_refs = Column(ARRAY(Text), default=list)
    rapporteurs = Column(ARRAY(Text), default=list)
    document_count = Column(Integer, default=0)
    event_reference = Column(Text)

    source_url = Column(Text)
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
