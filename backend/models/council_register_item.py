"""
Council of the EU register-item model.

Generic backing store for the eight Council-of-the-EU API endpoints that have
no dedicated table (meetings, voting results, register documents, OJ agendas,
preparatory bodies, press releases, research papers, treaties & agreements).
Every consilium.europa.eu surface is the same shape — a dated, titled item with
a public URL and a body — so one table with a ``content_type`` discriminator
serves all eight. Bodies are composed at scrape time and stored, so the API
never scrapes on the request path. See migration 109.
"""

from sqlalchemy import Column, String, Text, Date, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func
import uuid

from core.database import Base


class CouncilRegisterItem(Base):
    __tablename__ = "council_register_items"
    __table_args__ = (
        UniqueConstraint("item_key", name="council_register_items_item_key_unique"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    item_key = Column(Text, nullable=False)        # '<content_type>:<ref-or-url-slug>'
    content_type = Column(String(40), nullable=False, index=True)

    title = Column(Text, nullable=False)
    public_url = Column(Text)

    body_txt = Column(Text)
    body_html = Column(Text)

    document_date = Column(Date, index=True)
    document_ref = Column(Text)
    council_configuration = Column(String(20), index=True)
    interinstitutional_ref = Column(Text, index=True)
    subject_matters = Column(ARRAY(Text), default=list)
    pdf_url = Column(Text)
    policy_areas = Column(ARRAY(Text), default=list)

    source_url = Column(Text)
    extra = Column(JSONB, default=dict)

    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
