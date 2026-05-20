"""Auto-link new signups to a pre-staged private guide.

When a new user signs up (via /auth/signup, /auth/google, or /auth/linkedin),
this module checks if the user's email domain matches an entry in the
committed runtime mapping `backend/services/outreach/domain_to_slug.json`.
If yes, it flips users.private_guide_status='ready' and points
users.private_guide_slug at the matching slug.

The private guide content must already exist in the private_guides table
(synced via backend/scripts/sync_private_guides_to_db.py). This hook only
flips the user-side gate; it does not touch disk-based campaign CSVs at
runtime (those live in gitignored data/outreach/ and feed the regen script
that produces this JSON).

Wrapped so it NEVER blocks signup. Any exception is logged and swallowed.
"""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger("brubru.outreach.matcher")

PUBLIC_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "yahoo.co.uk", "yahoo.es", "yahoo.fr", "icloud.com",
    "me.com", "mac.com", "protonmail.com", "proton.me", "pm.me",
    "fastmail.com", "tutanota.com", "tuta.io", "gmx.com", "gmx.net",
    "aol.com", "msn.com", "mail.com", "zoho.com",
}

_MAPPING_PATH = Path(__file__).resolve().parent / "domain_to_slug.json"

# In-process cache keyed on mapping mtime so a redeploy or hot-reload picks
# up changes without restarting the worker.
_CACHE: dict[float, dict[str, str]] = {}


def _domain_of(email_or_url: str) -> str:
    s = (email_or_url or "").strip().lower()
    if not s:
        return ""
    if "@" in s:
        s = s.split("@", 1)[1]
    s = re.sub(r"^https?://", "", s)
    s = s.split("/", 1)[0].split(":", 1)[0]
    if s.startswith("www."):
        s = s[4:]
    return s.strip()


def _load_mapping() -> dict[str, str]:
    if not _MAPPING_PATH.exists():
        return {}
    try:
        mtime = _MAPPING_PATH.stat().st_mtime
    except FileNotFoundError:
        return {}

    if mtime in _CACHE:
        return _CACHE[mtime]

    try:
        data = json.loads(_MAPPING_PATH.read_text())
        mapping = data.get("domain_to_slug") or {}
        # Normalise: lowercase domains, strip whitespace.
        mapping = {k.strip().lower(): v.strip() for k, v in mapping.items() if k and v}
    except Exception as e:
        log.warning("failed to load %s: %s", _MAPPING_PATH, e)
        mapping = {}

    _CACHE.clear()
    _CACHE[mtime] = mapping
    return mapping


def match_email_to_slug(email: str) -> str | None:
    """Return the private-guide slug matching this email's domain, or None."""
    if not email or "@" not in email:
        return None
    domain = _domain_of(email)
    if not domain or domain in PUBLIC_DOMAINS:
        return None
    return _load_mapping().get(domain)


def _slug_is_synced(db: Session, slug: str) -> bool:
    row = db.execute(
        text("SELECT count(*) FROM private_guides WHERE slug = :slug"),
        {"slug": slug},
    ).fetchone()
    return bool(row and row[0] > 0)


def auto_link_user_if_match(db: Session, user_id, user_email: str) -> str | None:
    """Match the user to a private-guide slug and flip their status to 'ready'.

    Returns the slug that was linked, or None if no match.
    Never raises: signup must never fail because of this side-effect.
    """
    try:
        slug = match_email_to_slug(user_email)
        if not slug:
            return None
        if not _slug_is_synced(db, slug):
            log.warning(
                "auto-link skipped for %s -> %s: slug not in private_guides table",
                user_email, slug,
            )
            return None

        db.execute(
            text(
                """
                UPDATE users
                   SET private_guide_slug       = :slug,
                       private_guide_status     = 'ready',
                       private_guide_updated_at = :now
                 WHERE id = :user_id
                """
            ),
            {
                "slug": slug,
                "user_id": user_id,
                "now": datetime.now(timezone.utc),
            },
        )
        db.commit()
        log.info("auto-linked user %s to private guide slug=%s", user_email, slug)
        return slug
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        log.exception("auto-link failed for %s: %s", user_email, e)
        return None
