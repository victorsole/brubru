"""Outreach campaign helpers (auto-link signups to private guides)."""
from .campaign_matcher import match_email_to_slug, auto_link_user_if_match

__all__ = ["match_email_to_slug", "auto_link_user_if_match"]
