"""
Chat validation observability model.

Backs services/ai/response_validator.py. One row per validator pass that ran
after a chat response was generated. Workstream 1 of the Chat AI architecture
evolution (see memory/project_chat_ai_architecture_evolution.md).

Created: 12 May 2026.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from core.database import Base


class ChatValidation(Base):
    __tablename__ = "chat_validations"

    id = Column(Integer, primary_key=True, autoincrement=True)

    query = Column(Text, nullable=False)
    response_excerpt = Column(Text, nullable=False)

    validator_model = Column(String(64), nullable=False)
    generator = Column(String(64), nullable=True)
    language = Column(String(8), nullable=True)

    passed = Column(Boolean, nullable=False)
    severity = Column(String(16), nullable=False)
    violation_count = Column(Integer, nullable=False, default=0)
    violations = Column(JSONB, nullable=False, default=list)

    latency_ms = Column(Integer, nullable=False)
    context_length = Column(Integer, nullable=True)

    shadow_mode = Column(Boolean, nullable=False, default=True)
    error = Column(Text, nullable=True)

    user_id = Column(UUID(as_uuid=True), nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
