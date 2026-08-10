"""
Compliance Engine Models

SQLAlchemy models for EU Law Comply feature:
- Compliance analyses and gap findings
- Action tracking and exports
- Vector embeddings for semantic search

Note: The law_requirements table is defined in backend/models/eu_law.py
"""

from sqlalchemy import (
    Column, Integer, String, Text, Date, TIMESTAMP, ARRAY, JSON,
    ForeignKey, CheckConstraint, UniqueConstraint, DECIMAL, Boolean
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from core.database import Base


class ComplianceWorkspace(Base):
    """A durable compliance workspace: one per (user, cluster).

    The unit of work used to be a disposable analysis -- documents to /tmp,
    read once, deleted, nothing accumulating and so no reason to return. This
    is the object runs, uploads and remediation state hang off (migration 209).
    """

    __tablename__ = "compliance_workspaces"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'),
                     nullable=False, index=True)
    cluster_id = Column(Integer, ForeignKey('law_clusters.id', ondelete='CASCADE'),
                        nullable=False)
    name = Column(String(200))
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('user_id', 'cluster_id', name='uniq_workspace_user_cluster'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'cluster_id': self.cluster_id,
            'name': self.name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ComplianceAnalysis(Base):
    """
    Compliance Analysis Session

    Tracks a user's compliance check against a law cluster.
    Each analysis processes user documents and generates gap findings.
    """

    __tablename__ = "compliance_analyses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    cluster_id = Column(Integer, ForeignKey('law_clusters.id', ondelete='CASCADE'), nullable=False, index=True)

    # Analysis details
    analysis_name = Column(String(200))
    workspace_id = Column(Integer, ForeignKey('compliance_workspaces.id', ondelete='SET NULL'),
                          index=True)
    # DEAD. Declared ARRAY(Integer) against user_documents.id, which is a UUID,
    # so it could never be populated and is NULL on every row. Superseded by
    # document_uuids (migration 209); left in place rather than dropped so no
    # unseen reader breaks.
    document_ids = Column(ARRAY(Integer))
    # The uploads this run was actually performed against.
    document_uuids = Column(ARRAY(UUID(as_uuid=True)))

    # Status
    status = Column(String(50), nullable=False, default='processing', index=True)

    # Results summary
    total_requirements = Column(Integer)
    requirements_met = Column(Integer)
    requirements_partial = Column(Integer)
    requirements_gap = Column(Integer)

    # Overall compliance score (0-100)
    compliance_score = Column(DECIMAL(5, 2))

    # Timing
    started_at = Column(TIMESTAMP, server_default=func.now())
    completed_at = Column(TIMESTAMP)

    # Metadata
    analysis_params = Column(JSON)

    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    gap_findings = relationship("GapFinding", back_populates="analysis", cascade="all, delete-orphan")
    exports = relationship("AnalysisExport", back_populates="analysis", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('processing', 'completed', 'failed', 'cancelled')",
            name='valid_status'
        ),
    )

    def __repr__(self):
        return f"<ComplianceAnalysis(id={self.id}, name={self.analysis_name}, score={self.compliance_score})>"

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'cluster_id': self.cluster_id,
            'analysis_name': self.analysis_name,
            'status': self.status,
            'total_requirements': self.total_requirements,
            'requirements_met': self.requirements_met,
            'requirements_partial': self.requirements_partial,
            'requirements_gap': self.requirements_gap,
            'compliance_score': float(self.compliance_score) if self.compliance_score is not None else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class GapFinding(Base):
    """
    Individual Gap Finding

    Result of comparing one requirement against user's documentation.
    Status can be: met, partial, gap, not_applicable.
    """

    __tablename__ = "gap_findings"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey('compliance_analyses.id', ondelete='CASCADE'), nullable=False, index=True)
    requirement_id = Column(Integer, ForeignKey('law_requirements.id', ondelete='CASCADE'), nullable=False, index=True)

    # Compliance status
    status = Column(String(20), nullable=False, index=True)
    confidence_score = Column(DECIMAL(5, 2))  # LLM confidence (0-100)

    # Evidence
    evidence_text = Column(Text)
    evidence_source = Column(String(500))

    # Gap details
    gap_description = Column(Text)
    recommendation = Column(Text)

    # Action plan
    priority = Column(Integer, index=True)  # 1-5 (1=highest)
    estimated_effort = Column(String(50))  # 'quick', 'moderate', 'significant'
    action_owner = Column(String(200))

    # Semantic matching details
    similarity_score = Column(DECIMAL(5, 4))
    matched_chunks = Column(ARRAY(Text))
    # Values for the package's declared `extracted` review columns, keyed by
    # column id (migration 211). Null for the default review table.
    extra_fields = Column(JSON)

    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())

    # Relationships
    analysis = relationship("ComplianceAnalysis", back_populates="gap_findings")
    actions = relationship("ComplianceAction", back_populates="gap_finding", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('met', 'partial', 'gap', 'not_applicable')",
            name='valid_gap_status'
        ),
        CheckConstraint(
            "priority BETWEEN 1 AND 5",
            name='valid_priority'
        ),
    )

    def __repr__(self):
        return f"<GapFinding(id={self.id}, requirement={self.requirement_id}, status={self.status})>"

    def to_dict(self):
        return {
            'id': self.id,
            'analysis_id': self.analysis_id,
            'requirement_id': self.requirement_id,
            'status': self.status,
            'confidence_score': float(self.confidence_score) if self.confidence_score else None,
            'evidence_text': self.evidence_text,
            'evidence_source': self.evidence_source,
            'gap_description': self.gap_description,
            'recommendation': self.recommendation,
            'priority': self.priority,
            'estimated_effort': self.estimated_effort,
            'action_owner': self.action_owner,
            'similarity_score': float(self.similarity_score) if self.similarity_score else None
        }


class ComplianceAction(Base):
    """
    Compliance Action Item

    Tracks user progress on resolving identified gaps.
    """

    __tablename__ = "compliance_actions"

    id = Column(Integer, primary_key=True, index=True)
    # Pointer at the most recent finding this action was touched from. Useful
    # for tracing, never for identity: gap_findings are recreated on every
    # analysis run, so keying triage state here loses it the moment the user
    # re-runs the analysis (migration 207).
    gap_finding_id = Column(Integer, ForeignKey('gap_findings.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # The durable identity: one action per obligation, per user, per package.
    # This is what a re-run looks the state up by.
    requirement_id = Column(Integer, ForeignKey('law_requirements.id', ondelete='CASCADE'), index=True)
    cluster_id = Column(Integer, ForeignKey('law_clusters.id', ondelete='CASCADE'))

    # Action details
    action_title = Column(String(200), nullable=False)
    action_description = Column(Text)

    # Status tracking
    status = Column(String(50), nullable=False, default='pending', index=True)

    # Assignment
    assigned_to = Column(String(200))
    due_date = Column(Date, index=True)

    # Resolution
    resolution_notes = Column(Text)
    evidence_document_id = Column(Integer)  # References user_documents.id

    # Timing
    created_at = Column(TIMESTAMP, server_default=func.now())
    started_at = Column(TIMESTAMP)
    completed_at = Column(TIMESTAMP)

    # Relationships
    gap_finding = relationship("GapFinding", back_populates="actions")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'in_progress', 'completed', 'cancelled')",
            name='valid_action_status'
        ),
    )

    def __repr__(self):
        return f"<ComplianceAction(id={self.id}, title={self.action_title}, status={self.status})>"

    def to_dict(self):
        return {
            'id': self.id,
            'gap_finding_id': self.gap_finding_id,
            'requirement_id': self.requirement_id,
            'action_title': self.action_title,
            'action_description': self.action_description,
            'status': self.status,
            'assigned_to': self.assigned_to,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'resolution_notes': self.resolution_notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }



# RequirementEmbedding was removed on 8 Aug 2026 (migration 206). The table had
# no reader and no writer: VectorSearchService's similarly-named attributes are
# disk-cached numpy arrays, and the gap analyser now retrieves with TF-IDF
# rather than embeddings. pgvector stays imported nowhere in this module.


class AnalysisExport(Base):
    """
    Analysis Export

    Tracks exported compliance reports (DOCX, PDF, JSON, CSV).
    """

    __tablename__ = "analysis_exports"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(Integer, ForeignKey('compliance_analyses.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)

    # Export details
    export_format = Column(String(20), nullable=False)
    file_path = Column(Text)
    file_size_bytes = Column(Integer)

    # Access
    download_count = Column(Integer, default=0)
    last_downloaded_at = Column(TIMESTAMP)

    created_at = Column(TIMESTAMP, server_default=func.now(), index=True)
    expires_at = Column(TIMESTAMP)

    # Relationships
    analysis = relationship("ComplianceAnalysis", back_populates="exports")

    __table_args__ = (
        CheckConstraint(
            "export_format IN ('docx', 'pdf', 'json', 'csv')",
            name='valid_export_format'
        ),
    )

    def __repr__(self):
        return f"<AnalysisExport(id={self.id}, format={self.export_format})>"

    def to_dict(self):
        return {
            'id': self.id,
            'analysis_id': self.analysis_id,
            'export_format': self.export_format,
            'file_size_bytes': self.file_size_bytes,
            'download_count': self.download_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None
        }
