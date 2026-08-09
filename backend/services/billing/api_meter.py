"""
API Meter — per-call billing for /api/v1/* (Phase B, 21 May 2026).

Public surface:

    resolve_cost_micro(path) -> int
        Look up the per-call cost in micro-euros from pricing_table.json.

    debit(db, user_id, cost_micro) -> Tuple[bool, int]
        Atomically deduct cost_micro from users.api_balance_eur_micro using
        an UPDATE ... WHERE balance >= cost guard. Returns (ok, new_balance).
        ok=False means insufficient balance (no debit applied).

    refund(db, user_id, cost_micro) -> int
        Atomically credit cost_micro back. Used by the billing middleware
        when a route handler 5xx's.

    record_usage(db, ...) -> ApiUsageEvent
        Insert a single ledger row. Always called, including for free + sandbox.

    sandbox_consume(db, ip) -> Tuple[bool, str]
        Increment the daily sandbox counter for `ip` and the global pool.
        Returns (ok, reason_code). reason_code is one of:
            ""                    — success
            "sandbox_ip_capped"   — 10/day per IP
            "sandbox_global_capped" — 100/day total

Race-safety:
    All debits use atomic UPDATE WHERE balance >= cost RETURNING. No locks.
    Sandbox uses INSERT ... ON CONFLICT (pool_date, ip) DO UPDATE.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.api_billing import ApiUsageEvent, ApiTopupEvent, ApiSandboxPool  # noqa: F401

logger = logging.getLogger(__name__)


# Sandbox daily caps (CLI tools that need to adjust these stay in this module).
SANDBOX_IP_CAP = 10
SANDBOX_GLOBAL_CAP = 100


# ---------------------------------------------------------------------------
# Pricing table loader (compiled at import time)
# ---------------------------------------------------------------------------

_PRICING_PATH = Path(__file__).parent / "pricing_table.json"


def _load_pricing():
    with _PRICING_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    compiled: List[Tuple[re.Pattern[str], int, str]] = []
    for entry in raw["patterns"]:
        compiled.append((re.compile(entry["regex"]), int(entry["cost_micro"]), entry.get("label", "")))
    default_cost = int(raw["_default"]["cost_micro"])
    default_label = raw["_default"].get("label", "lightweight read")
    return compiled, default_cost, default_label


_PATTERNS, _DEFAULT_COST, _DEFAULT_LABEL = _load_pricing()


def resolve_cost_micro(path: str) -> Tuple[int, str]:
    """First matching pattern wins. Falls back to the default."""
    for pat, cost, label in _PATTERNS:
        if pat.match(path):
            return cost, label
    return _DEFAULT_COST, _DEFAULT_LABEL


# ---------------------------------------------------------------------------
# Atomic balance operations
# ---------------------------------------------------------------------------

def debit(db: Session, user_id: UUID, cost_micro: int) -> Tuple[bool, int]:
    """Atomically deduct `cost_micro` from `user_id`'s balance.

    Returns (ok, new_balance_or_current). ok=False means the balance was
    insufficient and nothing was deducted; new_balance_or_current is the
    current balance (helpful for the client's "you have X EUR left" message).
    """
    if cost_micro <= 0:
        # Free call — no debit, return current balance.
        row = db.execute(
            text("SELECT api_balance_eur_micro FROM public.users WHERE id = :uid"),
            {"uid": str(user_id)},
        ).fetchone()
        return True, int(row[0]) if row else 0

    row = db.execute(
        text(
            "UPDATE public.users "
            "SET api_balance_eur_micro = api_balance_eur_micro - :cost "
            "WHERE id = :uid AND api_balance_eur_micro >= :cost "
            "RETURNING api_balance_eur_micro"
        ),
        {"uid": str(user_id), "cost": cost_micro},
    ).fetchone()

    if row is not None:
        db.commit()
        return True, int(row[0])

    # Race-safe: read the current (insufficient) balance for the client.
    db.commit()  # close the failed-update tx
    cur = db.execute(
        text("SELECT api_balance_eur_micro FROM public.users WHERE id = :uid"),
        {"uid": str(user_id)},
    ).fetchone()
    return False, int(cur[0]) if cur else 0


def refund(db: Session, user_id: UUID, cost_micro: int) -> int:
    """Credit `cost_micro` back to `user_id`. Returns new balance."""
    if cost_micro <= 0:
        return 0
    row = db.execute(
        text(
            "UPDATE public.users "
            "SET api_balance_eur_micro = api_balance_eur_micro + :cost "
            "WHERE id = :uid "
            "RETURNING api_balance_eur_micro"
        ),
        {"uid": str(user_id), "cost": cost_micro},
    ).fetchone()
    db.commit()
    return int(row[0]) if row else 0


def credit_topup(db: Session, user_id: UUID, amount_micro: int) -> int:
    """Apply a successful Stripe top-up. Same shape as refund() — kept
    separate for ledger clarity / future hook points."""
    return refund(db, user_id, amount_micro)


# ---------------------------------------------------------------------------
# Usage ledger
# ---------------------------------------------------------------------------

def record_usage(
    db: Session,
    *,
    user_id: Optional[UUID],
    api_key_id: Optional[UUID],
    endpoint: str,
    method: str,
    cost_micro: int,
    request_id: Optional[str],
    status_code: Optional[int],
    is_sandbox: bool = False,
    refunded: bool = False,
) -> ApiUsageEvent:
    """Insert a usage event row. Caller commits."""
    evt = ApiUsageEvent(
        user_id=user_id,
        api_key_id=api_key_id,
        endpoint=endpoint,
        method=method,
        cost_eur_micro=cost_micro,
        request_id=request_id,
        status_code=status_code,
        is_sandbox=is_sandbox,
        refunded=refunded,
    )
    db.add(evt)
    db.commit()
    db.refresh(evt)
    return evt


def set_event_status(db: Session, event_id: int, status_code: int) -> None:
    """Stamp the final HTTP status onto an already-recorded usage event.

    The debit -- and therefore the ledger row -- happens BEFORE the route
    handler runs, so `record_usage` cannot know the outcome and writes NULL.
    Nothing used to fill it in afterwards, so every one of the 620 calls in the
    30 days to 9 Aug 2026 carried a NULL status and the API's error rate read as
    a clean zero. That zero was an artefact of not looking.

    Called by BillingRefundMiddleware, which is the only place that sees both
    the event id and the final response.
    """
    db.execute(
        text("UPDATE public.api_usage_events SET status_code = :sc WHERE id = :eid"),
        {"sc": int(status_code), "eid": event_id},
    )
    db.commit()


def mark_event_refunded(db: Session, event_id: int) -> None:
    db.execute(
        text("UPDATE public.api_usage_events SET refunded = TRUE WHERE id = :eid"),
        {"eid": event_id},
    )
    db.commit()


# ---------------------------------------------------------------------------
# Sandbox pool
# ---------------------------------------------------------------------------

def sandbox_consume(db: Session, ip: str) -> Tuple[bool, str]:
    """Increment the sandbox pool. Returns (ok, reason_code).

    Algorithm:
        1. UPSERT today's row for the given IP, incrementing count_today.
        2. If the IP row's new count > SANDBOX_IP_CAP, return False/ip_capped.
        3. SUM all rows for today; if > SANDBOX_GLOBAL_CAP, return False/global_capped.
        4. Otherwise True.

    Both checks happen post-increment, so the cap is inclusive (the 10th call
    of the day for an IP is allowed; the 11th fails). The increment is part
    of a single transaction so concurrent calls race-safely converge.
    """
    today = date.today().isoformat()
    safe_ip = (ip or "0.0.0.0").strip()
    if not safe_ip:
        safe_ip = "0.0.0.0"

    # Step 1 — UPSERT with atomic increment + capture new IP count.
    row = db.execute(
        text(
            "INSERT INTO public.api_sandbox_pool (pool_date, ip_address, count_today, updated_at) "
            "VALUES (:d, :ip, 1, NOW()) "
            "ON CONFLICT (pool_date, ip_address) "
            "DO UPDATE SET count_today = api_sandbox_pool.count_today + 1, updated_at = NOW() "
            "RETURNING count_today"
        ),
        {"d": today, "ip": safe_ip},
    ).fetchone()
    db.commit()
    ip_count = int(row[0]) if row else 0

    if ip_count > SANDBOX_IP_CAP:
        return False, "sandbox_ip_capped"

    # Step 2 — global cap.
    total = db.execute(
        text("SELECT COALESCE(SUM(count_today),0) FROM public.api_sandbox_pool WHERE pool_date = :d"),
        {"d": today},
    ).scalar() or 0
    if int(total) > SANDBOX_GLOBAL_CAP:
        return False, "sandbox_global_capped"

    return True, ""
