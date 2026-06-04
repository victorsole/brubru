"""
Consultation feedback - the "positions layer" for Tier-1 Outcome Alignment.

One row per organisation's feedback submission to an EC "Have Your Say" consultation
(public, attributable to a Transparency Register id). Carries the organisation's
STATED position (the ask) so Position Analysis can set it against a file's outcome.
Org-anchored (Option A): surfaced on a file via the lobbying-org register-id match,
NOT via a consultation-to-file CELEX link (HYS carries no CELEX). NO Anthropic.
"""

from sqlalchemy import Column, String, Date, DateTime, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from datetime import datetime
import uuid

from core.database import Base


class ConsultationFeedback(Base):
    __tablename__ = "consultation_feedback"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    initiative_id = Column(String(50), nullable=True, index=True)   # HYS initiative
    publication_id = Column(String(50), nullable=True)
    consultation_title = Column(Text, nullable=True)
    dg_responsible = Column(String(120), nullable=True)
    policy_areas = Column(ARRAY(String), default=[])

    organisation = Column(String(500), nullable=False)
    organisation_norm = Column(String(500), nullable=True, index=True)
    transparency_register_id = Column(String(50), nullable=True, index=True)  # = HYS trNumber
    user_type = Column(String(60), nullable=True)                   # COMPANY, NGO, BUSINESS_ASSOCIATION...
    country = Column(String(10), nullable=True)
    language = Column(String(10), nullable=True)

    stance = Column(String(20), nullable=True)        # support | oppose | amend | mixed | unclear | attachment_only
    stance_summary = Column(Text, nullable=True)      # Qwen one-line, grounded
    feedback_excerpt = Column(Text, nullable=True)    # source quote (first chars of the submission)

    feedback_date = Column(Date, nullable=True)
    source_url = Column(Text, nullable=True)

    scraped_at = Column(DateTime, default=datetime.utcnow)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint("publication_id", "organisation_norm", "feedback_date", name="uq_consultation_feedback"),
        Index("ix_cf_tr_id", "transparency_register_id"),
        Index("ix_cf_org_norm", "organisation_norm"),
    )
