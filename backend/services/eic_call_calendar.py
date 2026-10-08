"""
The EIC batch calendar the Funding & Tenders Portal does not carry.

Why (8 Oct 2026): the portal gives the EIC Accelerator topic one end date
(17 December 2026) and a budget of 0, so the Tenderator feed counted down to
December while the real rhythm is a short-proposal batch on the first Tuesday of
every month and six full-proposal batches, and showed no budget for a EUR 634M
call. The calendar lives in backend/data/eic_call_calendar.json, sourced from the
2026 EIC Work Programme; the "next" date is computed with the same helper as the
Tender Docs templates, so the two can never disagree.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from services.funding_template_loader import next_deadline

logger = logging.getLogger(__name__)

CALENDAR_PATH = Path(__file__).resolve().parent.parent / "data" / "eic_call_calendar.json"

_cache: Optional[Dict[str, Any]] = None


def _topics() -> Dict[str, Any]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CALENDAR_PATH.read_text()).get("topics") or {}
        except (OSError, ValueError) as exc:
            logger.warning("EIC call calendar unreadable: %s", exc)
            _cache = {}
    return _cache


def wp_budget(topic_id: Optional[str]) -> Optional[float]:
    """The Work Programme's indicative budget for this topic, in euro, if curated."""
    entry = _topics().get((topic_id or "").upper())
    value = entry.get("indicative_budget_eur") if entry else None
    return float(value) if value else None


def next_batches(topic_id: Optional[str], now: Optional[datetime] = None) -> Optional[Dict[str, str]]:
    """The next evaluation batch(es) still open for a curated EIC topic, else None.

    Accelerator: {"short": ..., "full": ...}; STEP and Defence: {"batch": ...}.
    A kind whose dates are all past is omitted rather than shown as "next".
    """
    entry = _topics().get((topic_id or "").upper())
    if not entry:
        return None
    current = now or datetime.now().astimezone()
    out: Dict[str, str] = {}
    for kind, key in (("short", "short_proposals"), ("full", "full_proposals"), ("batch", "batches")):
        rule = entry.get(key)
        if not rule:
            continue
        nxt = next_deadline(rule, current)
        parsed = None
        if nxt:
            try:
                parsed = datetime.fromisoformat(nxt) if len(nxt) > 10 else datetime.fromisoformat(nxt + "T17:00:00+01:00")
            except ValueError:
                parsed = None
        if parsed is not None and parsed > current:
            out[kind] = nxt
    return out or None


def conflict_note(topic_id: Optional[str]) -> Optional[str]:
    entry = _topics().get((topic_id or "").upper())
    return entry.get("conflict_note") if entry else None
