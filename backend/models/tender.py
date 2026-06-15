"""
Tender Database Models

SQLAlchemy models for EU public procurement tenders from TED (Tenders Electronic Daily).
Part of the Tenderator feature for Blue-tier users.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, Index, ForeignKey, BigInteger, Date, Numeric, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from core.database import Base


class Tender(Base):
    """
    EU Public Procurement Tender

    Stores tender notices from TED (Tenders Electronic Daily).
    Extracted from eForms XML and enriched with AI analysis.

    Notice types:
    - Competition: Call for tenders (primary focus)
    - Planning: Prior information notices
    - Result: Contract award notices
    """

    __tablename__ = "tenders"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # TED identifiers
    publication_number = Column(String(50), unique=True, nullable=False, index=True)  # e.g., "1776-2025"
    notice_id = Column(String(100), index=True)  # eForms notice UUID
    form_type = Column(String(50), index=True)  # competition, planning, result
    notice_subtype = Column(String(20))  # 1-40, E1-E6, T01-T02

    # Basic info
    title = Column(Text, nullable=False)
    description = Column(Text)
    official_name = Column(String(500))  # Contracting authority
    buyer_country = Column(String(2), index=True)  # ISO 3166-1 alpha-2

    # Procedure
    procedure_type = Column(String(50), index=True)  # open, restricted, negotiated, competitive-dialogue
    legal_basis = Column(String(50))  # dir-2014-23-eu, dir-2014-24-eu, etc.

    # Classification
    cpv_codes = Column(ARRAY(String(20)), index=True)  # Common Procurement Vocabulary codes
    cpv_main = Column(String(20), index=True)  # Main CPV code
    nuts_codes = Column(ARRAY(String(10)))  # Place of performance
    contract_nature = Column(String(20))  # works, supplies, services

    # Value
    estimated_value = Column(Float)
    estimated_value_currency = Column(String(3), default="EUR")
    value_range_low = Column(Float)
    value_range_high = Column(Float)

    # Dates
    publication_date = Column(DateTime(timezone=True), index=True)
    submission_deadline = Column(DateTime(timezone=True), index=True)
    contract_start_date = Column(DateTime(timezone=True))
    contract_duration_months = Column(Integer)

    # Award criteria
    award_criteria_type = Column(String(50))  # quality, price, cost
    award_criteria = Column(JSONB)  # {"quality": 70, "price": 30, ...}

    # Requirements (extracted from notice)
    selection_criteria = Column(JSONB)  # ESPD Part IV criteria
    exclusion_grounds = Column(JSONB)  # ESPD Part III grounds
    minimum_requirements = Column(JSONB)  # Turnover, experience, etc.

    # Lots
    has_lots = Column(Boolean, default=False)
    lot_count = Column(Integer)
    lots = Column(JSONB)  # [{lot_id, title, cpv, value}, ...]

    # Documents and links
    ted_url = Column(String(500))  # Link to TED notice
    documents_url = Column(String(500))  # Link to tender documents
    submission_url = Column(String(500))  # E-submission URL

    # Raw data
    xml_content = Column(Text)  # Full eForms XML
    raw_json = Column(JSONB)  # Parsed JSON from XML

    # AI enrichment
    sme_suitability_score = Column(Float)  # 0-100 score
    sme_analysis = Column(JSONB)  # AI analysis for SMEs
    summary = Column(Text)  # AI-generated summary
    keywords = Column(ARRAY(String(100)))  # Extracted keywords
    embeddings_id = Column(String(100))  # Reference to vector embeddings

    # Status
    status = Column(String(20), default="open", index=True)  # open, closed, awarded, cancelled
    is_framework = Column(Boolean, default=False)  # Framework agreement
    is_joint_procurement = Column(Boolean, default=False)

    # Metadata
    source = Column(String(50), default="ted_api")  # ted_api, ted_sparql
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_synced_at = Column(DateTime(timezone=True))

    # Relationships
    matches = relationship("TenderMatch", back_populates="tender", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tender(id={self.id}, publication_number={self.publication_number}, title={self.title[:50]}...)>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "publication_number": self.publication_number,
            "notice_id": self.notice_id,
            "form_type": self.form_type,
            "title": self.title,
            "description": self.description,
            "official_name": self.official_name,
            "buyer_country": self.buyer_country,
            "procedure_type": self.procedure_type,
            "cpv_codes": self.cpv_codes,
            "cpv_main": self.cpv_main,
            "nuts_codes": self.nuts_codes,
            "contract_nature": self.contract_nature,
            "estimated_value": self.estimated_value,
            "estimated_value_currency": self.estimated_value_currency,
            "publication_date": self.publication_date.isoformat() if self.publication_date else None,
            "submission_deadline": self.submission_deadline.isoformat() if self.submission_deadline else None,
            "contract_duration_months": self.contract_duration_months,
            "award_criteria": self.award_criteria,
            "has_lots": self.has_lots,
            "lot_count": self.lot_count,
            "ted_url": self.ted_url,
            "status": self.status,
            "sme_suitability_score": self.sme_suitability_score,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def to_summary_dict(self):
        """Compact summary for list views"""
        return {
            "id": self.id,
            "publication_number": self.publication_number,
            "title": self.title,
            "official_name": self.official_name,
            "buyer_country": self.buyer_country,
            "cpv_main": self.cpv_main,
            "estimated_value": self.estimated_value,
            "submission_deadline": self.submission_deadline.isoformat() if self.submission_deadline else None,
            "status": self.status,
            "sme_suitability_score": self.sme_suitability_score
        }


class TenderProfile(Base):
    """
    User's Tender Preferences Profile

    Stores user preferences for tender matching.
    Only available to Blue-tier subscribers.
    """

    __tablename__ = "tender_profiles"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)

    # Company information
    company_name = Column(String(300))
    company_size = Column(String(20))  # micro, small, medium (SME categories)
    annual_turnover = Column(Float)  # For selection criteria matching
    employee_count = Column(Integer)
    years_in_business = Column(Integer)

    # Sector preferences
    cpv_categories = Column(ARRAY(String(20)))  # Preferred CPV code categories (e.g., "72" for IT)
    cpv_codes = Column(ARRAY(String(20)))  # Specific CPV codes of interest
    sectors_description = Column(Text)  # Free-text description of business sectors

    # Geographic preferences
    countries_of_interest = Column(ARRAY(String(2)))  # ISO country codes
    nuts_regions = Column(ARRAY(String(10)))  # NUTS regions of interest
    eu_wide = Column(Boolean, default=True)  # Open to all EU tenders

    # Value preferences
    min_tender_value = Column(Float)
    max_tender_value = Column(Float)
    preferred_currency = Column(String(3), default="EUR")

    # Procedure preferences
    preferred_procedures = Column(ARRAY(String(50)))  # open, restricted, etc.
    exclude_frameworks = Column(Boolean, default=False)
    exclude_joint_procurement = Column(Boolean, default=False)

    # Matching preferences
    keywords = Column(ARRAY(String(100)))  # Keywords to look for
    excluded_keywords = Column(ARRAY(String(100)))  # Keywords to exclude
    min_deadline_days = Column(Integer, default=30)  # Minimum days until deadline

    # Capabilities (for selection criteria matching)
    certifications = Column(ARRAY(String(200)))  # ISO 9001, ISO 27001, etc.
    past_contract_value = Column(Float)  # Largest past contract value
    references_count = Column(Integer)  # Number of references available

    # Notification preferences
    notification_frequency = Column(String(20), default="weekly")  # daily, weekly, bi-weekly
    notification_email = Column(Boolean, default=True)
    notification_in_app = Column(Boolean, default=True)
    max_matches_per_digest = Column(Integer, default=10)

    # Status
    is_active = Column(Boolean, default=True)
    last_matched_at = Column(DateTime(timezone=True))

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    user = relationship("User", backref="tender_profile")
    matches = relationship("TenderMatch", back_populates="profile", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<TenderProfile(id={self.id}, user_id={self.user_id}, company={self.company_name})>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "company_name": self.company_name,
            "company_size": self.company_size,
            "annual_turnover": self.annual_turnover,
            "employee_count": self.employee_count,
            "cpv_categories": self.cpv_categories,
            "cpv_codes": self.cpv_codes,
            "countries_of_interest": self.countries_of_interest,
            "nuts_regions": self.nuts_regions,
            "eu_wide": self.eu_wide,
            "min_tender_value": self.min_tender_value,
            "max_tender_value": self.max_tender_value,
            "preferred_procedures": self.preferred_procedures,
            "keywords": self.keywords,
            "min_deadline_days": self.min_deadline_days,
            "certifications": self.certifications,
            "notification_frequency": self.notification_frequency,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class TenderMatch(Base):
    """
    Tender-User Match

    Tracks which tenders have been matched to which users,
    with match scores and user actions (saved, dismissed, etc.).
    """

    __tablename__ = "tender_matches"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Foreign keys
    tender_id = Column(Integer, ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False, index=True)
    profile_id = Column(Integer, ForeignKey("tender_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Match scoring
    match_score = Column(Float, nullable=False)  # 0-100 overall match score
    match_reasons = Column(JSONB)  # {"cpv_match": 0.8, "country_match": 1.0, "value_match": 0.9, ...}
    match_details = Column(Text)  # Human-readable match explanation

    # User actions
    is_viewed = Column(Boolean, default=False)
    is_saved = Column(Boolean, default=False)
    is_dismissed = Column(Boolean, default=False)
    is_applied = Column(Boolean, default=False)

    # User notes
    user_notes = Column(Text)
    user_rating = Column(Integer)  # 1-5 relevance rating from user

    # Notification tracking
    notified_at = Column(DateTime(timezone=True))
    notification_method = Column(String(20))  # email, in_app

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Relationships
    tender = relationship("Tender", back_populates="matches")
    profile = relationship("TenderProfile", back_populates="matches")
    user = relationship("User", backref="tender_matches")

    def __repr__(self):
        return f"<TenderMatch(id={self.id}, tender_id={self.tender_id}, user_id={self.user_id}, score={self.match_score})>"

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "tender_id": self.tender_id,
            "user_id": str(self.user_id),
            "match_score": self.match_score,
            "match_reasons": self.match_reasons,
            "match_details": self.match_details,
            "is_viewed": self.is_viewed,
            "is_saved": self.is_saved,
            "is_dismissed": self.is_dismissed,
            "is_applied": self.is_applied,
            "user_notes": self.user_notes,
            "user_rating": self.user_rating,
            "notified_at": self.notified_at.isoformat() if self.notified_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }

    def to_dict_with_tender(self):
        """Include tender summary in response"""
        result = self.to_dict()
        if self.tender:
            result["tender"] = self.tender.to_summary_dict()
        return result


class TenderFetchJob(Base):
    """
    Tender Fetch Job Tracking

    Tracks scheduled and completed tender fetch jobs
    for monitoring and debugging.
    """

    __tablename__ = "tender_fetch_jobs"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(50), unique=True, nullable=False, index=True)

    # Job configuration
    job_type = Column(String(50))  # scheduled, manual, backfill
    source = Column(String(50))  # ted_api, ted_sparql
    query_params = Column(JSONB)  # Query parameters used

    # Results
    status = Column(String(20), default="pending", index=True)  # pending, running, completed, failed
    tenders_found = Column(Integer, default=0)
    tenders_new = Column(Integer, default=0)
    tenders_updated = Column(Integer, default=0)
    errors = Column(JSONB)  # List of error messages

    # Timing
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    duration_seconds = Column(Float)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<TenderFetchJob(id={self.id}, job_id={self.job_id}, status={self.status})>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            "id": self.id,
            "job_id": self.job_id,
            "job_type": self.job_type,
            "source": self.source,
            "status": self.status,
            "tenders_found": self.tenders_found,
            "tenders_new": self.tenders_new,
            "tenders_updated": self.tenders_updated,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds
        }


class TenderatorSettings(Base):
    """
    Tenderator System Settings

    Stores configuration for the Tenderator feature.
    Uses a singleton pattern - only one row should exist.
    """

    __tablename__ = "tenderator_settings"

    id = Column(Integer, primary_key=True, default=1)

    # Fetch settings
    default_max_value = Column(Float, default=5_000_000.0)
    fetch_frequency = Column(String(20), default="weekly")  # daily, weekly, bi-weekly
    enabled_countries = Column(ARRAY(String(2)))  # None means all
    enabled_cpv_codes = Column(ARRAY(String(20)))  # None means all

    # Matching settings
    auto_matching_enabled = Column(Boolean, default=True)
    match_score_threshold = Column(Float, default=50.0)

    # Notification settings
    auto_notifications_enabled = Column(Boolean, default=True)

    # Metadata
    updated_at = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    updated_by = Column(UUID(as_uuid=True))  # UUID to match users.id

    def to_dict(self) -> dict:
        return {
            "default_max_value": self.default_max_value,
            "fetch_frequency": self.fetch_frequency,
            "enabled_countries": self.enabled_countries,
            "enabled_cpv_codes": self.enabled_cpv_codes,
            "auto_matching_enabled": self.auto_matching_enabled,
            "match_score_threshold": self.match_score_threshold,
            "auto_notifications_enabled": self.auto_notifications_enabled,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


# Database indexes for performance
Index("idx_tenders_publication_date", Tender.publication_date.desc())
Index("idx_tenders_submission_deadline", Tender.submission_deadline)
Index("idx_tenders_cpv_main", Tender.cpv_main)
Index("idx_tenders_buyer_country", Tender.buyer_country)
Index("idx_tenders_status_deadline", Tender.status, Tender.submission_deadline)
Index("idx_tenders_sme_score", Tender.sme_suitability_score.desc())

Index("idx_tender_profiles_user", TenderProfile.user_id)
Index("idx_tender_profiles_active", TenderProfile.is_active)

Index("idx_tender_matches_user", TenderMatch.user_id)
Index("idx_tender_matches_tender", TenderMatch.tender_id)
Index("idx_tender_matches_profile", TenderMatch.profile_id)
Index("idx_tender_matches_score", TenderMatch.match_score.desc())
Index("idx_tender_matches_saved", TenderMatch.is_saved)


# ---------------------------------------------------------------------------
# Move 4 (15 Jun 2026): generic Tenderator pipeline. Any opportunity source
# (TED, F&T proposals/tenders/projects, agency, intl_coop) can be tracked
# through a configurable status pipeline. Replaces the TAS-style Excel
# tracker — and works for any organisation that needs CRM-lite over EU
# opportunities. Schema in migrations/143_tender_pipeline.sql.
# ---------------------------------------------------------------------------
class TenderPipeline(Base):
    """User's pipeline tracker for any unified-feed opportunity."""

    __tablename__ = "tender_pipeline"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Opportunity reference (source-qualified id from the unified feed).
    opportunity_id = Column(Text, nullable=False)
    source = Column(String(20), nullable=False)

    # Snapshot fields cached at add-time.
    title = Column(Text, nullable=False)
    organisation = Column(Text)
    country = Column(String(120))
    programme = Column(Text)
    deadline = Column(DateTime(timezone=True))
    budget = Column(Numeric)
    currency = Column(String(8), default="EUR")
    source_url = Column(Text)

    # Pipeline state. Allowed values enforced by DB CHECK constraint:
    # lead | drafting | submitted | awarded | executing | paid | lost | cancelled
    status = Column(String(20), nullable=False, default="lead")
    next_step = Column(Text)
    next_step_due = Column(Date)
    pm_assignee = Column(Text)
    notes = Column(Text)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "opportunity_id", name="tender_pipeline_user_opp_uk"),
    )

    def __repr__(self):
        return f"<TenderPipeline(id={self.id}, status={self.status}, opp={self.opportunity_id})>"

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": str(self.user_id),
            "opportunity_id": self.opportunity_id,
            "source": self.source,
            "title": self.title,
            "organisation": self.organisation,
            "country": self.country,
            "programme": self.programme,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "budget": float(self.budget) if self.budget is not None else None,
            "currency": self.currency or "EUR",
            "source_url": self.source_url,
            "status": self.status,
            "next_step": self.next_step,
            "next_step_due": self.next_step_due.isoformat() if self.next_step_due else None,
            "pm_assignee": self.pm_assignee,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
