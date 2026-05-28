"""
Tenant-scoped audience resolution for chat card injection + EU CONTEXT.

The chat surface ships a public daily news card today. For client pilots
(EFPIA from 28 May 2026, others to follow) we want the same card slot to
carry a tenant-specific brief instead. The audience map lives in
backend/data/audience_users.json and is read at process start.

Two callers:
  - chat-card injection (the "Daily News DD/MM/YYYY" card that fronts every
    new conversation in `daily_briefs.priority=0` slot).
  - EU CONTEXT builder (the block of recent headlines / snippets injected
    into the system prompt for every chat completion).

Both call `resolve_audience(email)` and add a `WHERE audience = :aud OR
audience IS NULL`-style filter to their daily_briefs query.
"""

from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_AUDIENCE_FILE = Path(__file__).resolve().parents[1] / "data" / "audience_users.json"


@lru_cache(maxsize=1)
def _load_audience_map() -> Dict[str, List[str]]:
    """Email-lowercased map: { email: [audience_slug, ...] }."""

    if not _AUDIENCE_FILE.is_file():
        logger.warning("audience_users.json missing at %s -- audience injection disabled", _AUDIENCE_FILE)
        return {}

    try:
        with _AUDIENCE_FILE.open() as fh:
            payload = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        logger.warning("failed to load audience_users.json: %s", exc)
        return {}

    audiences = payload.get("audiences") or {}
    email_to_audiences: Dict[str, List[str]] = {}
    for slug, emails in audiences.items():
        if not slug or not isinstance(emails, list):
            continue
        slug_clean = str(slug).strip().lower()
        if not slug_clean:
            continue
        for email in emails:
            if not isinstance(email, str):
                continue
            key = email.strip().lower()
            if not key:
                continue
            email_to_audiences.setdefault(key, []).append(slug_clean)

    return email_to_audiences


def reload_audience_map() -> None:
    """Drop the cache so a hot edit of audience_users.json takes effect."""

    _load_audience_map.cache_clear()


def resolve_audience(email: Optional[str]) -> Optional[str]:
    """
    Return the first audience slug the email is mapped to, or None.

    We return at most one slug for now -- a user belongs to one tenant or none.
    If a future client needs multi-tenant membership we can expand the return
    type without breaking callers.
    """

    if not email:
        return None
    key = email.strip().lower()
    if not key:
        return None

    # Env-driven override useful for staging / local testing without editing
    # the JSON file. AUDIENCE_OVERRIDE_<EMAIL_SAFE>=<slug>.
    env_key = "AUDIENCE_OVERRIDE_" + "".join(c if c.isalnum() else "_" for c in key.upper())
    env_val = os.environ.get(env_key)
    if env_val:
        return env_val.strip().lower() or None

    mapping = _load_audience_map()
    audiences = mapping.get(key)
    if not audiences:
        return None
    return audiences[0]


def all_emails_for_audience(slug: str) -> List[str]:
    """Reverse lookup: every email registered for a given audience."""

    if not slug:
        return []
    slug_clean = slug.strip().lower()
    out = []
    for email, audiences in _load_audience_map().items():
        if slug_clean in audiences:
            out.append(email)
    return sorted(out)
