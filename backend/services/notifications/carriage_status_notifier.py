"""Notify users when a legislative file they track changes status.

WHY THIS EXISTS (audit, 25 August 2026)
---------------------------------------
Tracking is a promise of future notification, and Brubru had never kept it once.
613 carriage tracks existed; `last_notified_at` was set on zero of them, ever.
The `notifications` table held 103 rows, all of one type, none created since
18 June, and none ever read.

`services/notifications/proactive_notifier.py` looked like the thing that should
have been doing this. It is not: it has no caller, it does not import (it still
reaches for `scrapers` and `anthropic`, the latter removed from this codebase on
6 August), and it contains no reference to any tracking table. It watches RSS.
Wiring it into cron would not have delivered a single one of these.

DESIGN NOTES
------------
* **The anchor is `user_carriage_tracks.last_notified_status`** (migration 220),
  not the carriage's own history. `legislative_carriages.status_history` is
  empty on all 2,770 rows, so nothing records when a status changed, and
  `last_updated` bumps on every nightly sweep write (~221 a day) for reasons
  that are not status changes.

* **NULL baseline never notifies.** A track whose baseline is NULL has never
  been told anything, so it is seeded silently. Without that rule, switching
  this on fires 613 notifications at once, mostly about changes that happened
  before anyone was watching.

* **Silence is not success.** Every run returns a `NotifierRun` counting what
  was actually PERSISTED, not what was attempted, and any per-track failure is
  recorded and re-raised into the summary rather than swallowed. A run that
  could not write must not look like a quiet night.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Statuses that are worth waking someone up for, mapped to the priority the
# notification carries. Anything not listed still notifies, at normal priority:
# the user asked to hear about status changes, and silently filtering some of
# them is how the promise got broken in the first place.
_HIGH_PRIORITY_STATUSES = {
    "ADOPTED",
    "COMPLETED",
    "CLOSE_TO_ADOPTION",
    "REJECTED",
    "WITHDRAWN",
}

_STATUS_PROSE = {
    "TABLED": "has been tabled",
    "IN_COMMITTEE": "has moved into committee",
    "CLOSE_TO_ADOPTION": "is close to adoption",
    "ADOPTED": "has been adopted",
    "COMPLETED": "has completed its passage",
    "REJECTED": "has been rejected",
    "WITHDRAWN": "has been withdrawn",
    "BLOCKED": "is blocked",
}


def _norm(status: Any) -> Optional[str]:
    """Normalise a status to an UPPERCASE string, or None.

    This is not defensive padding, it is load-bearing. `current_status` is an
    Enum column: SQLAlchemy hands back `CarriageStatusEnum.CLOSE_TO_ADOPTION`,
    whose `.value` is lowercase `close_to_adoption`, while the raw column holds
    `CLOSE_TO_ADOPTION`. Comparing a value read one way against a value written
    the other way is always unequal, and "always unequal" here means a
    notification for every tracked file, for every user, every single night.

    So both sides of the comparison go through this, and the stored baseline is
    written in the same normalised form.
    """
    if status is None:
        return None
    raw = getattr(status, "value", status)
    text = str(raw).strip()
    return text.upper() or None


def _prose(status: Optional[str]) -> str:
    """Human phrasing for a status, in British English, no institutional codes.

    Falls back to the raw value made readable rather than to a code, because
    the message goes in front of a user (CLAUDE.md: no institutional codes in
    user-facing text).
    """
    if not status:
        return "has changed stage"
    return _STATUS_PROSE.get(status.upper(), f"is now at {status.replace('_', ' ').lower()}")


@dataclass
class NotifierRun:
    """What a single run actually did.

    Counts are of PERSISTED effects. `errors` is non-empty whenever any track
    failed, and the CLI turns that into a non-zero exit code -- a job that can
    fail must record the failure and must not exit 0.
    """
    tracks_examined: int = 0
    baselines_seeded: int = 0
    notifications_created: int = 0
    unchanged: int = 0
    skipped_no_baseline: int = 0
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"examined={self.tracks_examined} "
            f"created={self.notifications_created} "
            f"seeded={self.baselines_seeded} "
            f"unchanged={self.unchanged} "
            f"skipped_no_baseline={self.skipped_no_baseline} "
            f"errors={len(self.errors)}"
            + (" [DRY RUN]" if self.dry_run else "")
        )


class CarriageStatusNotifier:
    """Compare each tracked carriage's status against what its watcher last heard."""

    def __init__(self, db: Session):
        self.db = db

    def run(
        self,
        *,
        seed_baseline: bool = False,
        dry_run: bool = False,
        user_id: Optional[str] = None,
        since_status_only: bool = True,
    ) -> NotifierRun:
        """
        Args:
            seed_baseline: fill NULL baselines from the current status WITHOUT
                notifying. Required on first ever run; harmless afterwards.
            dry_run: compute everything, persist nothing.
            user_id: restrict to one user (used for the Terraqui backfill and
                for testing against a single account).
            since_status_only: only consider tracks with
                notify_on_status_change set. Kept as a parameter so a caller can
                deliberately widen it; the default honours the user's choice.
        """
        from models.legislative_train import LegislativeCarriage, UserCarriageTrack
        from models.notification import Notification

        run = NotifierRun(dry_run=dry_run)

        q = (
            self.db.query(UserCarriageTrack, LegislativeCarriage)
            .join(LegislativeCarriage, LegislativeCarriage.id == UserCarriageTrack.carriage_id)
            .filter(UserCarriageTrack.archived_at.is_(None))
        )
        if since_status_only:
            q = q.filter(UserCarriageTrack.notify_on_status_change.is_(True))
        if user_id:
            q = q.filter(UserCarriageTrack.user_id == user_id)

        rows = q.all()
        run.tracks_examined = len(rows)

        for track, carriage in rows:
            try:
                current = _norm(carriage.current_status)
                baseline = _norm(track.last_notified_status)

                if baseline is None:
                    # Never told this user anything about this file.
                    if seed_baseline:
                        if not dry_run:
                            track.last_notified_status = current
                        run.baselines_seeded += 1
                    else:
                        run.skipped_no_baseline += 1
                    continue

                if current == baseline:
                    run.unchanged += 1
                    continue

                title, message = self._compose(carriage, baseline, current)

                if not dry_run:
                    self.db.add(Notification(
                        user_id=track.user_id,
                        notification_type="status_change",
                        title=title,
                        message=message,
                        action_url=self._action_url(carriage),
                        related_entity_type="legislative_carriage",
                        related_entity_id=str(carriage.id),
                        priority="high" if current in _HIGH_PRIORITY_STATUSES else "normal",
                        notif_metadata={
                            "previous_status": baseline,
                            "new_status": current,
                            "oeil_procedure_ref": carriage.oeil_procedure_ref,
                        },
                    ))
                    track.last_notified_status = current
                    track.last_notified_at = datetime.utcnow()

                run.notifications_created += 1

            except Exception as exc:  # noqa: BLE001 -- recorded, never swallowed
                # Name the type: a bare message turned a TypeError into "empty
                # data" elsewhere in this codebase (17 Aug incident).
                msg = f"track={track.id} carriage={carriage.id}: {type(exc).__name__}: {exc}"
                logger.error("[carriage-notify] %s", msg, exc_info=True)
                run.errors.append(msg)

        if dry_run:
            self.db.rollback()
        else:
            try:
                self.db.commit()
            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                run.errors.append(f"commit failed: {type(exc).__name__}: {exc}")
                # The counts above described intended writes; none of them
                # landed. Say so rather than report a successful run.
                run.notifications_created = 0
                run.baselines_seeded = 0
                logger.error("[carriage-notify] commit failed", exc_info=True)

        logger.info("[carriage-notify] %s", run.summary())
        return run

    # -- helpers -------------------------------------------------------

    def _compose(self, carriage, previous: Optional[str], current: Optional[str]) -> tuple[str, str]:
        """Plain-language title and body.

        No institutional codes in the user-facing text (CLAUDE.md hard rule);
        the procedure reference travels in metadata and in the link.
        """
        name = (carriage.short_title or carriage.title or "A file you follow").strip()
        if len(name) > 160:
            name = name[:157].rstrip() + "..."

        title = f"{name} {_prose(current)}"
        message = (
            f"A file you track has moved. It {_prose(current)}, "
            f"having previously been at {(previous or 'an earlier stage').replace('_', ' ').lower()}. "
            f"Open it in My EU Bubble > Legislative Train: state of play to see what changed."
        )
        return title, message

    def _action_url(self, carriage) -> str:
        ref = (carriage.oeil_procedure_ref or "").strip()
        if ref:
            return f"/my-eu-bubble?tab=legislative-train&file_id={ref.lower()}"
        return "/my-eu-bubble?tab=legislative-train"
