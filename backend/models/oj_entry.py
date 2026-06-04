"""
OJ Entry model — one Official Journal act per row (MEUB "My OJ").

Public EP/EUR-Lex reference data (migration 099). Populated by
``scripts/sync_oj.py`` via ``services/scrapers/oj_scraper.py`` (Playwright fetch,
pure parsing, no Anthropic). ``carriage_id`` links an act back to a tracked
legislative dossier in My Tracked Files when the CELEX matches.
"""

from datetime import datetime

from sqlalchemy import Column, String, Date, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid

from core.database import Base


class OjEntry(Base):
    __tablename__ = "oj_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entry_key = Column(Text, nullable=False, unique=True)

    oj_date = Column(Date, nullable=False)
    series = Column(String, nullable=False)        # 'L' | 'C'
    oj_number = Column(String, nullable=False)     # '2026/1144' | 'C/2026/2942'
    oj_id = Column(String)                          # 'L_202601144'
    celex = Column(String)                          # '32026R1144' (L-series)

    title = Column(Text, nullable=False)
    act_type = Column(String)
    category = Column(String)
    institution = Column(String)
    eurlex_url = Column(Text)

    # "Cool modules" (migration 100)
    plain_explanation = Column(Text)   # AI one-liner (Mistral, cached; no Anthropic)
    change_kind = Column(String)       # new | amends | renews | repeals | extends | suspends | corrects
    theme = Column(String)             # plain-language topic cluster

    carriage_id = Column(UUID(as_uuid=True), ForeignKey("legislative_carriages.id"))
    matched_procedure_ref = Column(String)
    matched_ta_reference = Column(String)

    scraped_at = Column(DateTime, default=datetime.now)
    created_at = Column(DateTime, default=datetime.now)

    carriage = relationship("LegislativeCarriage", foreign_keys=[carriage_id])

    def __repr__(self):
        return f"<OjEntry {self.series} {self.oj_number}: {self.title[:40]}>"
