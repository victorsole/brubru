"""
EU Law Database Models

SQLAlchemy models for storing EU legal documents from LEG_2025-11.
"""

from sqlalchemy import Column, Integer, String, Text, Date, TIMESTAMP, ARRAY, JSON, Boolean, Index
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import TSVECTOR
from ..core.database import Base


class EULaw(Base):
    """
    EU Legal Document

    Stores metadata and full text of EU regulations, directives, decisions, etc.
    from the LEG_2025-11 directory (50k+ documents).

    Each law has:
    - UUID (from directory name)
    - CELEX number (EU legal identifier)
    - Full bibliographic metadata
    - Legal relationships (basis, citations)
    - Full text for searching
    - Policy area classification
    """

    __tablename__ = "eu_laws"

    # Primary key
    id = Column(Integer, primary_key=True, index=True)

    # Identifiers
    uuid = Column(String(36), unique=True, nullable=False, index=True)
    celex = Column(String(30), index=True)  # Nullable because not all docs have CELEX (increased from 20)

    # Basic metadata
    doc_type = Column(Text)  # "Commission Implementing Decision", etc. (TEXT - no length limit)
    title = Column(Text, nullable=False)
    date = Column(Date, index=True)
    oj_reference = Column(String(100))  # Official Journal reference (e.g., "L 187/41") (increased from 50)

    # Classification
    policy_area = Column(String(200), index=True)  # From eu_policies.json (increased from 100)
    is_primary_legislation = Column(Boolean, default=True, index=True)  # TRUE for laws, FALSE for annexes/ToCs
    parent_law_uuid = Column(String(36), index=True)  # UUID of parent law (for annexes/amendments)

    # Legal relationships
    legal_basis = Column(ARRAY(Text))  # Laws this document is based on
    citations = Column(ARRAY(Text))  # Laws cited in this document
    subject_matter = Column(ARRAY(Text))  # Keywords/topics

    # File location
    xml_path = Column(Text, nullable=False)

    # Additional metadata
    extra_metadata = Column(JSON)  # Extra fields (language, pages, EEA relevance, etc.)

    # Timestamps
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Full-text search vector (auto-generated)
    # Note: This requires a PostgreSQL extension and is defined via migration
    # search_vector = Column(TSVECTOR)

    def __repr__(self):
        return f"<EULaw(celex={self.celex}, title={self.title[:50]}...)>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'uuid': self.uuid,
            'celex': self.celex,
            'doc_type': self.doc_type,
            'title': self.title,
            'date': self.date.isoformat() if self.date else None,
            'oj_reference': self.oj_reference,
            'policy_area': self.policy_area,
            'is_primary_legislation': self.is_primary_legislation,
            'parent_law_uuid': self.parent_law_uuid,
            'legal_basis': self.legal_basis,
            'citations': self.citations,
            'subject_matter': self.subject_matter,
            'xml_path': self.xml_path,
            'extra_metadata': self.extra_metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class LawCluster(Base):
    """
    Law Cluster

    Groups related laws together for compliance checking (EU Law Comply feature).

    Examples:
    - GDPR Package (Regulation 2016/679 + implementing acts)
    - DSA Package (Regulation 2022/2065 + delegated acts)
    - AI Act Package
    """

    __tablename__ = "law_clusters"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    primary_law_id = Column(Integer)  # References eu_laws.id (no FK for simplicity)

    description = Column(Text)
    applicability = Column(Text)  # Who this applies to
    policy_area = Column(String(100), index=True)
    priority_level = Column(String(20))  # "high", "medium", "low"

    created_at = Column(TIMESTAMP, server_default=func.now())

    def __repr__(self):
        return f"<LawCluster(name={self.name})>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'primary_law_id': self.primary_law_id,
            'description': self.description,
            'applicability': self.applicability,
            'policy_area': self.policy_area,
            'priority_level': self.priority_level,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class ClusterLaw(Base):
    """
    Law-Cluster Relationship

    Many-to-many relationship between laws and clusters.
    """

    __tablename__ = "cluster_laws"

    cluster_id = Column(Integer, primary_key=True)
    law_id = Column(Integer, primary_key=True)
    relationship_type = Column(String(50))  # "primary", "implementing", "delegated", "amending"

    def __repr__(self):
        return f"<ClusterLaw(cluster={self.cluster_id}, law={self.law_id}, type={self.relationship_type})>"


class LawRequirement(Base):
    """
    Legal Requirement

    Individual obligation extracted from a law for compliance checking.

    Examples:
    - "Designate a data protection officer" (GDPR Article 37)
    - "Publish terms of service in plain language" (DSA Article 14)
    """

    __tablename__ = "law_requirements"

    id = Column(Integer, primary_key=True, index=True)
    law_id = Column(Integer, index=True)  # References eu_laws.id
    cluster_id = Column(Integer, index=True)  # References law_clusters.id
    article = Column(String(50))  # "Article 15", "Article 37(1)"

    requirement_text = Column(Text, nullable=False)
    deadline = Column(Date)  # Compliance deadline (if specified)
    criticality = Column(String(20))  # "critical", "important", "recommended"

    # Additional metadata
    applicable_entity = Column(String(100))  # "platform", "user", "member state"
    extra_metadata = Column(JSON)

    created_at = Column(TIMESTAMP, server_default=func.now())

    def __repr__(self):
        return f"<LawRequirement(law_id={self.law_id}, article={self.article})>"

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'law_id': self.law_id,
            'article': self.article,
            'requirement_text': self.requirement_text,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'criticality': self.criticality,
            'applicable_entity': self.applicable_entity,
            'extra_metadata': self.extra_metadata
        }


# Indexes for performance
Index('idx_eu_laws_celex', EULaw.celex)
Index('idx_eu_laws_uuid', EULaw.uuid)
Index('idx_eu_laws_policy_area', EULaw.policy_area)
Index('idx_eu_laws_date', EULaw.date.desc())
Index('idx_law_clusters_policy_area', LawCluster.policy_area)
Index('idx_law_requirements_law_id', LawRequirement.law_id)
