"""
EP eMeeting document model (document-level; sibling to EpEmeetingAgenda).

One row per document attached to a committee agenda item — draft reports,
amendments, voting lists, compromise amendments, reports, opinions, agendas,
minutes — with ALL language PDF URLs and the linking anchors. See migration 111.
"""

from sqlalchemy import Column, String, Text, Date, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func
import uuid

from core.database import Base


class EpEmeetingDocument(Base):
    __tablename__ = "ep_emeeting_documents"
    __table_args__ = (
        UniqueConstraint("document_key", name="ep_emeeting_documents_document_key_unique"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    document_key = Column(Text, nullable=False)
    gepro_code = Column(String(10), index=True)
    gepro_description = Column(Text)
    doc_kind = Column(String(30), index=True)
    reference = Column(Text)
    visual_reference = Column(Text)
    title = Column(Text)

    committee_code = Column(String(10), index=True)
    committee_name = Column(Text)
    meeting_date = Column(Date, index=True)
    oj_reference = Column(Text, index=True)
    agenda_id = Column(UUID(as_uuid=True))
    dossier_reference = Column(Text)
    procedure_ref = Column(Text, index=True)
    item_title = Column(Text)
    document_set_type = Column(String(10))
    rapporteurs = Column(ARRAY(Text), default=list)

    pdf_url = Column(Text)
    pdf_urls = Column(JSONB, default=dict)
    languages = Column(ARRAY(Text), default=list)

    body_txt = Column(Text)
    body_html = Column(Text)
    source_url = Column(Text)
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
