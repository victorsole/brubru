"""
API Billing Models — Phase B (21 May 2026).

Three tables, one file, because they form one cohesive sub-system:

  - ApiUsageEvent   per-call debit ledger (what was charged for what)
  - ApiTopupEvent   Stripe top-up ledger (what Victor sees in Stripe is also here)
  - ApiSandboxPool  daily counter for the shared sandbox key (100/day global,
                    10/IP/day) — keyed by (date, ip).

All monetary fields are BIGINT micro-euros (μEUR, 6dp). 1 EUR = 1_000_000.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.sql import func

from core.database import Base


# ===========================================================================
# Per-call debit ledger
# ===========================================================================

class ApiUsageEvent(Base):
    """One row per /api/v1/* call that crossed the metering middleware."""

    __tablename__ = "api_usage_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    api_key_id = Column(
        UUID(as_uuid=True),
        ForeignKey("api_keys.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    endpoint = Column(Text, nullable=False)
    method = Column(Text, nullable=False)
    cost_eur_micro = Column(BigInteger, nullable=False, default=0)
    request_id = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)
    is_sandbox = Column(Boolean, nullable=False, default=False)
    refunded = Column(Boolean, nullable=False, default=False)
    # Our own synthetic traffic, set from the X-Brubru-Probe header (migration 222).
    # FALSE means "not marked", never "proven human" -- exclude from user metrics.
    is_probe = Column(Boolean, nullable=False, default=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


# ===========================================================================
# Stripe top-up ledger
# ===========================================================================

class ApiTopupEvent(Base):
    """One row per Stripe PaymentIntent for API credits.

    Status flow:
        pending -> succeeded (most cases)
        pending -> failed    (card declined, 3DS abandoned, etc.)
        succeeded -> refunded (manual refund — rare)
    """

    __tablename__ = "api_topup_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    amount_eur_micro = Column(BigInteger, nullable=False)
    stripe_payment_intent_id = Column(Text, nullable=False, unique=True)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    succeeded_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "amount_eur_micro >= 1000000",
            name="api_topup_events_amount_eur_micro_check",
        ),
        CheckConstraint(
            "status IN ('pending','succeeded','failed','refunded')",
            name="api_topup_events_status_check",
        ),
    )


# ===========================================================================
# Sandbox-pool daily counter
# ===========================================================================

class ApiSandboxPool(Base):
    """Daily counter for the shared public sandbox API key.

    Compound PK on (pool_date, ip_address). Aggregate the day with
    `SELECT SUM(count_today) FROM api_sandbox_pool WHERE pool_date = CURRENT_DATE`.

    The application uses INSERT ... ON CONFLICT (pool_date, ip_address) DO UPDATE
    SET count_today = count_today + 1 ... to atomically advance the counter.
    """

    __tablename__ = "api_sandbox_pool"

    pool_date = Column(Date, nullable=False)
    ip_address = Column(INET, nullable=False)
    count_today = Column(Integer, nullable=False, default=0)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        PrimaryKeyConstraint("pool_date", "ip_address", name="api_sandbox_pool_pkey"),
    )
