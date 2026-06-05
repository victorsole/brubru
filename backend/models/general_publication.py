"""EU general publication model (migration 114) — Cellar PUB_GEN works."""
from sqlalchemy import Column, String, Text, Date, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from core.database import Base


class EuGeneralPublication(Base):
    __tablename__ = "eu_general_publications"
    __table_args__ = (UniqueConstraint("publication_id", name="eu_general_publications_publication_id_unique"),)
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publication_id = Column(Text, nullable=False)
    cellar_uri = Column(Text)
    title = Column(Text, nullable=False)
    publication_date = Column(Date, index=True)
    public_url = Column(Text)
    body_txt = Column(Text)
    body_html = Column(Text)
    source_url = Column(Text)
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
