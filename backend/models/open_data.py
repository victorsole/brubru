"""
data.europa.eu open-data models (migration 112).

`OpenDataDataset` — one row per data.europa.eu dataset (full DCAT record).
`OpenDataCatalogue` — one row per catalogue (~90 EU + member-state catalogues).
Ingested by scripts/sync_open_data.py from the data.europa.eu open JSON API.
"""

from sqlalchemy import Column, String, Text, Date, DateTime, Integer, Boolean, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.sql import func
import uuid

from core.database import Base


class OpenDataDataset(Base):
    __tablename__ = "open_data_datasets"
    __table_args__ = (
        UniqueConstraint("dataset_id", name="open_data_datasets_dataset_id_unique"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(Text, nullable=False)

    title = Column(Text, nullable=False)
    description = Column(Text)
    publisher = Column(Text, index=True)
    catalogue = Column(Text, index=True)
    country = Column(Text)
    country_code = Column(String(8), index=True)
    themes = Column(ARRAY(Text), default=list)
    keywords = Column(ARRAY(Text), default=list)
    formats = Column(ARRAY(Text), default=list)
    is_hvd = Column(Boolean, default=False, index=True)
    distributions = Column(JSONB, default=list)
    quality_score = Column(Numeric)

    public_url = Column(Text)
    body_txt = Column(Text)
    body_html = Column(Text)
    issued = Column(Date)
    modified = Column(Date, index=True)

    source_url = Column(Text)
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class OpenDataCatalogue(Base):
    __tablename__ = "open_data_catalogues"
    __table_args__ = (
        UniqueConstraint("catalogue_id", name="open_data_catalogues_catalogue_id_unique"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    catalogue_id = Column(Text, nullable=False)
    title = Column(Text)
    country = Column(Text)
    dataset_count = Column(Integer)
    public_url = Column(Text)
    body_txt = Column(Text)
    body_html = Column(Text)
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
