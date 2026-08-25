"""
Notification Services

Components:
- CarriageStatusNotifier: tell users when a legislative file they track moves.
  This is the one that runs. Wired into api/cron.py; CLI wrapper at
  scripts/notify_carriage_status.py.

- ProactiveNotifier: RSS-era experiment. DEAD CODE as of 25 August 2026 --
  it has no caller anywhere, it references no tracking table, and it does not
  even import: it reaches for a top-level `scrapers` package that no longer
  exists and for `anthropic`, which was removed from this codebase on
  6 August 2026.

  It is NOT re-exported here on purpose. It used to be, and that made the whole
  package unimportable: `from services.notifications import anything` raised
  ModuleNotFoundError before reaching the working module. Anyone who wants the
  old experiment can import it by its full path and deal with the ImportError
  themselves.

  Deliberately left on disk rather than deleted -- deleting someone else's
  prototype is not this audit's call. It should either be repaired or removed
  in a session that owns it.
"""

from .carriage_status_notifier import CarriageStatusNotifier, NotifierRun

__all__ = [
    'CarriageStatusNotifier',
    'NotifierRun',
]
