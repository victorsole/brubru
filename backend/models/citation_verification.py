"""
Citation verification cache model.

Backs services/citation_verifier.py. One row per canonical ref the AI has
ever written. Sprint 1a (April 2026) of the CoCounsel-inspired citation-
verification gap closure (see docs/training/quality_report.html section 2).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Column, String, Integer, DateTime, Text

from core.database import Base


class CitationVerification(Base):
    __tablename__ = "citation_verifications"

    ref = Column(String(64), primary_key=True)
    kind = Column(String(16), nullable=False)
    status = Column(String(16), nullable=False)
    resolved_url = Column(Text, nullable=True)
    http_status = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    original_form = Column(String(128), nullable=True)
    verified_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
