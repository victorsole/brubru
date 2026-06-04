"""
EU news item model — Commission/DG/agency news aggregated for MEUB "News".

Public reference data (migration 101). Populated by scripts/sync_dg_news.py via
services/scrapers/dg_news_scraper.py (browser-UA HTTP + ECL parsing; no Anthropic).
Tagged commission_dg so it's filterable by department + the user's Policy Interests.
Also the structured store the /news skill reads.
"""

from datetime import datetime

from sqlalchemy import Column, String, Date, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, ARRAY
import uuid

from core.database import Base


class EuNewsItem(Base):
    __tablename__ = "eu_news_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_key = Column(Text, nullable=False, unique=True)

    title = Column(Text, nullable=False)
    summary = Column(Text)
    news_date = Column(Date)

    institution = Column(String)
    commission_dg = Column(String)
    item_type = Column(String)        # news | publication | story | press | other
    source_key = Column(String)
    policy_areas = Column(ARRAY(String), default=list)

    image_url = Column(Text)
    source_url = Column(Text)

    scraped_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<EuNewsItem {self.commission_dg or self.institution} {self.title[:40]}>"
