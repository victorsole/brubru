"""
EU Official registry — backs /api/v1/officials.

Created: 25 April 2026 (W5 P2, Thursday brief 1.5).
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from core.database import Base


class EUOfficial(Base):
    __tablename__ = "eu_officials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    slug = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    role = Column(String(255), nullable=True)

    institution_slug = Column(String(100), nullable=False, index=True)
    dg = Column(String(20), nullable=True, index=True)
    cabinet = Column(String(100), nullable=True)

    country = Column(String(3), nullable=True)
    city = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    bio_url = Column(Text, nullable=True)
    photo_url = Column(Text, nullable=True)
    social_links = Column(JSONB, default=dict)

    appointed_date = Column(Date, nullable=True)
    term_end_date = Column(Date, nullable=True)

    portfolio = Column(Text, nullable=True)
    policy_areas = Column(ARRAY(String), default=list)

    is_active = Column(Boolean, nullable=False, default=True, index=True)

    scraped_at = Column(DateTime, default=datetime.now)
    first_seen = Column(DateTime, default=datetime.now, nullable=False)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
