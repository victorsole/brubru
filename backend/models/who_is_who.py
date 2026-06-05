"""
Who is Who models (migration 113) — the EU interinstitutional directory.

`WhoIsWhoDepartment` — one row per organisational unit (DG / directorate / unit).
`WhoIsWhoOfficial`   — one row per named official (name + position + department).
Ingested by scripts/sync_who_is_who.py from the EU SPARQL endpoint.
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid

from core.database import Base


class WhoIsWhoDepartment(Base):
    __tablename__ = "who_is_who_departments"
    __table_args__ = (UniqueConstraint("dept_key", name="who_is_who_departments_dept_key_unique"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dept_key = Column(Text, nullable=False)
    mnemonic = Column(Text, index=True)
    name = Column(Text, nullable=False)
    institution_uri = Column(Text)
    official_count = Column(Integer, default=0)
    public_url = Column(Text)
    body_txt = Column(Text)
    body_html = Column(Text)
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WhoIsWhoOfficial(Base):
    __tablename__ = "who_is_who_officials"
    __table_args__ = (UniqueConstraint("official_key", name="who_is_who_officials_official_key_unique"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    official_key = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    honorific = Column(Text)
    position = Column(Text, index=True)
    department = Column(Text, index=True)
    mnemonic = Column(Text, index=True)
    institution_uri = Column(Text)
    person_uri = Column(Text)
    public_url = Column(Text)
    body_txt = Column(Text)
    body_html = Column(Text)
    first_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    fetched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
