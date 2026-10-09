"""What an OEIL procedure status line means. One rule, read by every job that needs it.

OEIL prints a status line on each procedure page ("Awaiting committee decision", "Procedure
completed", ...). Used by scripts/sync_oeil_procedures.py (which pages to re-read) and
scripts/backfill_resolution_dates.py (when a procedure is closed without a resolution).
"""
from typing import Optional


def is_finished(status: Optional[str]) -> bool:
    """True for statuses after which Parliament does nothing more on the file.

    'Procedure completed, awaiting publication in Official Journal' is not finished: the OJ
    reference is still to come.
    """
    s = (status or "").strip().lower()
    if s.startswith("procedure completed"):
        return "awaiting" not in s
    return s.startswith(("procedure rejected", "procedure lapsed", "procedure withdrawn"))
