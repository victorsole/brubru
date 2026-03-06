"""
DG GROW Database Models

SQLAlchemy models for data from DG GROW (Internal Market, Industry, Entrepreneurship and SMEs).
Covers 4 databases: NANDO (notified bodies), TRIS (technical regulations),
TBT (trade barriers), EMI (industrial ecosystems).

Source: https://single-market-economy.ec.europa.eu/tools-databases_en
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.sql import func

from core.database import Base


class NotifiedBody(Base):
    """
    NANDO - Notified Body for Conformity Assessment

    Notified bodies are organisations designated by EU/EEA countries
    to assess conformity of products before being placed on the market.
    Source: Single Market Compliance Space (formerly NANDO-IS)
    """

    __tablename__ = "notified_bodies"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    nando_id = Column(String(20), unique=True, nullable=False, index=True)
    body_name = Column(String(500), nullable=False)
    body_number = Column(String(10), index=True)  # 4-digit notified body number

    # Location
    country = Column(String(2), nullable=False, index=True)  # ISO 3166-1 alpha-2
    address = Column(Text)
    city = Column(String(200))
    postal_code = Column(String(20))

    # Contact
    phone = Column(String(100))
    email = Column(String(300))
    website = Column(String(500))

    # Scope
    directives = Column(ARRAY(String(100)), index=True)  # EU directives covered
    directive_names = Column(ARRAY(String(300)))  # Human-readable directive names
    regulations = Column(ARRAY(String(100)))  # EU regulations covered
    product_areas = Column(ARRAY(String(200)))  # Product categories
    cpv_mapping = Column(ARRAY(String(20)))  # Mapped CPV codes for Tenderator matching

    # Status
    status = Column(String(20), default="active", index=True)  # active, suspended, withdrawn
    notification_date = Column(DateTime(timezone=True))
    expiry_date = Column(DateTime(timezone=True))

    # Source
    source_url = Column(String(500))
    raw_data = Column(JSONB)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<NotifiedBody(id={self.id}, number={self.body_number}, name={self.body_name[:50]})>"

    def to_dict(self):
        return {
            "id": self.id,
            "nando_id": self.nando_id,
            "body_name": self.body_name,
            "body_number": self.body_number,
            "country": self.country,
            "address": self.address,
            "city": self.city,
            "phone": self.phone,
            "email": self.email,
            "website": self.website,
            "directives": self.directives,
            "directive_names": self.directive_names,
            "regulations": self.regulations,
            "product_areas": self.product_areas,
            "cpv_mapping": self.cpv_mapping,
            "status": self.status,
            "source_url": self.source_url,
        }

    def to_summary_dict(self):
        return {
            "body_number": self.body_number,
            "body_name": self.body_name,
            "country": self.country,
            "directives": self.directives,
            "status": self.status,
            "email": self.email,
            "phone": self.phone,
            "website": self.website,
        }


class TechnicalRegulation(Base):
    """
    TRIS - Technical Regulation Information System

    Notifications of draft national technical regulations under
    Directive (EU) 2015/1535 (ex 98/34/EC procedure).
    Source: https://technical-regulation-information-system.ec.europa.eu
    """

    __tablename__ = "technical_regulations"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    notification_number = Column(Integer, unique=True, nullable=False, index=True)
    reference = Column(String(50), index=True)  # e.g., "2026/27736/DK"

    # Content
    title = Column(Text, nullable=False)
    description = Column(Text)
    product_sector = Column(String(200), index=True)
    product_description = Column(Text)

    # Origin
    country = Column(String(2), nullable=False, index=True)
    country_name = Column(String(100))

    # Dates
    notification_date = Column(DateTime(timezone=True), nullable=False, index=True)
    standstill_end_date = Column(DateTime(timezone=True))  # 3-month standstill
    adoption_date = Column(DateTime(timezone=True))

    # Status
    status = Column(String(30), default="notified", index=True)  # notified, standstill, adopted, withdrawn
    has_detailed_opinion = Column(Boolean, default=False)
    has_comments = Column(Boolean, default=False)

    # Relevant EU legislation
    related_eu_legislation = Column(ARRAY(String(100)))
    related_directives = Column(ARRAY(String(100)))

    # CPV mapping for Tenderator
    cpv_mapping = Column(ARRAY(String(20)))  # Mapped CPV codes

    # Links
    source_url = Column(String(500))
    document_url = Column(String(500))

    # Raw data
    raw_data = Column(JSONB)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<TechnicalRegulation(id={self.id}, number={self.notification_number}, country={self.country})>"

    def to_dict(self):
        return {
            "id": self.id,
            "notification_number": self.notification_number,
            "reference": self.reference,
            "title": self.title,
            "description": self.description,
            "product_sector": self.product_sector,
            "country": self.country,
            "country_name": self.country_name,
            "notification_date": self.notification_date.isoformat() if self.notification_date else None,
            "standstill_end_date": self.standstill_end_date.isoformat() if self.standstill_end_date else None,
            "status": self.status,
            "has_detailed_opinion": self.has_detailed_opinion,
            "related_eu_legislation": self.related_eu_legislation,
            "cpv_mapping": self.cpv_mapping,
            "source_url": self.source_url,
        }


class TradeBarrierNotification(Base):
    """
    TBT - Technical Barriers to Trade

    WTO TBT notifications and EU comments.
    Source: https://technical-barriers-trade.ec.europa.eu
    """

    __tablename__ = "trade_barrier_notifications"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    notification_id = Column(Integer, unique=True, nullable=False, index=True)
    symbol = Column(String(100), index=True)  # WTO symbol e.g., "G/TBT/N/EU/1023"

    # Content
    title = Column(Text, nullable=False)
    description = Column(Text)
    product_description = Column(Text)
    objective = Column(Text)

    # Origin
    country = Column(String(100), nullable=False, index=True)  # Full country name (not ISO - WTO uses full names)
    country_code = Column(String(3), index=True)  # ISO 3166-1 alpha-3 if available

    # Classification
    hs_codes = Column(ARRAY(String(20)))  # Harmonized System product codes
    ics_codes = Column(ARRAY(String(20)))  # International Classification for Standards
    product_area = Column(String(200), index=True)

    # Dates
    notification_date = Column(DateTime(timezone=True), nullable=False, index=True)
    comment_deadline = Column(DateTime(timezone=True))
    proposed_adoption_date = Column(DateTime(timezone=True))
    proposed_entry_into_force = Column(DateTime(timezone=True))

    # Status
    status = Column(String(30), default="notified", index=True)
    is_eu_notification = Column(Boolean, default=False, index=True)
    has_eu_comment = Column(Boolean, default=False)

    # Impact assessment
    trade_impact = Column(String(50))  # high, medium, low (AI-assessed)
    affected_eu_sectors = Column(ARRAY(String(100)))

    # CPV mapping for Tenderator
    cpv_mapping = Column(ARRAY(String(20)))

    # Links
    source_url = Column(String(500))

    # Raw data
    raw_data = Column(JSONB)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<TradeBarrierNotification(id={self.id}, notification_id={self.notification_id}, country={self.country})>"

    def to_dict(self):
        return {
            "id": self.id,
            "notification_id": self.notification_id,
            "symbol": self.symbol,
            "title": self.title,
            "description": self.description,
            "product_area": self.product_area,
            "country": self.country,
            "country_code": self.country_code,
            "notification_date": self.notification_date.isoformat() if self.notification_date else None,
            "comment_deadline": self.comment_deadline.isoformat() if self.comment_deadline else None,
            "status": self.status,
            "is_eu_notification": self.is_eu_notification,
            "has_eu_comment": self.has_eu_comment,
            "trade_impact": self.trade_impact,
            "affected_eu_sectors": self.affected_eu_sectors,
            "cpv_mapping": self.cpv_mapping,
            "source_url": self.source_url,
        }


class IndustrialEcosystemData(Base):
    """
    EMI - European Monitor of Industrial Ecosystems

    Tracks green and digital transition across 14 industrial ecosystems.
    Source: https://monitor-industrial-ecosystems.ec.europa.eu
    """

    __tablename__ = "industrial_ecosystem_data"

    id = Column(Integer, primary_key=True, index=True)

    # Identification
    ecosystem = Column(String(100), nullable=False, index=True)  # e.g., "Aerospace & Defence"
    country = Column(String(2), index=True)  # ISO 3166-1 alpha-2 (null = EU aggregate)
    indicator = Column(String(200), nullable=False, index=True)
    period = Column(String(20), nullable=False, index=True)  # e.g., "2024-Q4", "2025"

    # Data
    value = Column(Float)
    unit = Column(String(50))  # percentage, index, count, EUR millions
    previous_value = Column(Float)
    change_pct = Column(Float)  # Year-on-year change

    # Classification
    dimension = Column(String(50), index=True)  # impact, transition_efforts, enabling_framework
    sub_dimension = Column(String(100))  # environmental, digital, technology, investment, skills

    # CPV mapping for Tenderator sector analysis
    cpv_categories = Column(ARRAY(String(20)))

    # Source
    source_report = Column(String(300))
    source_url = Column(String(500))
    raw_data = Column(JSONB)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    def __repr__(self):
        return f"<IndustrialEcosystemData(ecosystem={self.ecosystem}, indicator={self.indicator}, period={self.period})>"

    def to_dict(self):
        return {
            "id": self.id,
            "ecosystem": self.ecosystem,
            "country": self.country,
            "indicator": self.indicator,
            "period": self.period,
            "value": self.value,
            "unit": self.unit,
            "change_pct": self.change_pct,
            "dimension": self.dimension,
            "sub_dimension": self.sub_dimension,
            "cpv_categories": self.cpv_categories,
            "source_report": self.source_report,
        }


# Indexes
Index("idx_notified_bodies_country_status", NotifiedBody.country, NotifiedBody.status)
Index("idx_notified_bodies_number", NotifiedBody.body_number)

Index("idx_technical_regulations_country_date", TechnicalRegulation.country, TechnicalRegulation.notification_date.desc())
Index("idx_technical_regulations_sector", TechnicalRegulation.product_sector)

Index("idx_tbt_country_date", TradeBarrierNotification.country, TradeBarrierNotification.notification_date.desc())
Index("idx_tbt_eu_notifications", TradeBarrierNotification.is_eu_notification)

Index("idx_emi_ecosystem_indicator", IndustrialEcosystemData.ecosystem, IndustrialEcosystemData.indicator)
Index("idx_emi_country_period", IndustrialEcosystemData.country, IndustrialEcosystemData.period)
