"""Who may receive a notification or a lifecycle email (16 Oct 2026).

An UNCLAIMED SHELL is a profile we pre-provisioned for a prospect who has never
claimed it and never signed in: `pre_provisioned_at` set, `claimed_at` and
`last_login` empty. Same definition as `scripts/user_activity_report.INTERNAL_USER_SQL`.
Nobody reads such an account, and a lifecycle email to it would contact a prospect
we chose not to contact yet. On 16 Oct 2026 eight shells held notifications
(contact@legora.com, the prospect+ accounts...), all unread.

A shell that a human has signed into is a real account and is NOT excluded here.
"""
from __future__ import annotations

from typing import Optional, Set

from sqlalchemy import text


def unclaimed_shell_sql(alias: str = "u") -> str:
    """SQL predicate, true for an unclaimed shell, for a users table aliased `alias`."""
    a = alias
    return (f"({a}.pre_provisioned_at IS NOT NULL AND {a}.claimed_at IS NULL "
            f"AND {a}.last_login IS NULL)")


def is_unclaimed_shell(user) -> bool:
    """Same test on a loaded User row."""
    return (getattr(user, "pre_provisioned_at", None) is not None
            and getattr(user, "claimed_at", None) is None
            and getattr(user, "last_login", None) is None)


def unclaimed_shell_ids(db) -> Set[str]:
    """Ids of every unclaimed shell, as strings (one query)."""
    rows = db.execute(text(f"SELECT u.id FROM users u WHERE {unclaimed_shell_sql('u')}")).fetchall()
    return {str(r[0]) for r in rows}


class ShellFilter:
    """Per-run cache: one query, then O(1) checks by user id."""

    def __init__(self, db):
        self._db = db
        self._ids: Optional[Set[str]] = None

    def __call__(self, user_id) -> bool:
        if self._ids is None:
            self._ids = unclaimed_shell_ids(self._db)
        return str(user_id) in self._ids
