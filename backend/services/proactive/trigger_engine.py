"""
Proactive Chat trigger engine.

Given an authenticated user, computes a small list of briefings Brubru should
proactively surface in Chat. Each briefing is grounded in real DB rows; if no
real signal exists, the engine returns an empty list — never invents content.

Triggers
--------
- ``morning_brief``           First session of the day, summarises 1–3 events
                              relevant to the user (new files matching profile
                              + calendar today + tracked-file movement).
- ``new_file_match``          A legislative file appeared in the last 7 days
                              matching the user's policy interests.
- ``tracked_file_movement``   A file the user tracks moved status in the last
                              7 days.
- ``amendment_surge``         > 5 new amendments on a tracked file in 24h.

Hard cap: 3 briefings per user per request (and per day, enforced upstream
once we persist the deliveries — see migration 074 ``is_proactive`` flag).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import List, Literal, Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.user import User


logger = logging.getLogger(__name__)


TriggerSource = Literal[
    "morning_brief",
    "new_file_match",
    "tracked_file_movement",
    "amendment_surge",
    "learn_about_you",
]


MAX_BRIEFINGS_PER_REQUEST = 3
AMENDMENT_SURGE_THRESHOLD = 5
NEW_FILE_WINDOW_DAYS = 7
TRACKED_MOVEMENT_WINDOW_DAYS = 7
AMENDMENT_SURGE_WINDOW_HOURS = 24


# Human-readable labels for the raw institution enum values stored in
# eu_calendar_events.institution. Anything not in this map falls back to
# a sentence-cased version of the enum.
INSTITUTION_LABELS = {
    "EP": "The European Parliament",
    "COMMISSION": "The European Commission",
    "COUNCIL": "The Council of the EU",
    "EUROPEAN_COUNCIL": "The European Council",
    "ECB": "The European Central Bank",
    "COR": "The Committee of the Regions",
    "EESC": "The European Economic and Social Committee",
    "CJEU": "The Court of Justice of the EU",
    "THIRD_PARTY": "A Brussels policy event",
}


def _humanise_institution(raw: Optional[str]) -> str:
    if not raw:
        return "An EU institution"
    key = str(raw).strip().upper()
    if key in INSTITUTION_LABELS:
        return INSTITUTION_LABELS[key]
    return key.replace("_", " ").title()


@dataclass
class ProactiveBriefing:
    """One thing Brubru wants to tell the user without being asked."""

    trigger_source: TriggerSource
    title: str
    summary: str
    suggested_query: str
    evidence_refs: List[str] = field(default_factory=list)
    drill_down_path: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "trigger_source": self.trigger_source,
            "title": self.title,
            "summary": self.summary,
            "suggested_query": self.suggested_query,
            "evidence_refs": self.evidence_refs,
            "drill_down_path": self.drill_down_path,
        }


def _policy_interests(user: User) -> List[str]:
    interests = user.policy_interests_list
    if not interests:
        return []
    return [str(x).strip() for x in interests if x and str(x).strip()]


def _briefing_new_file_match(
    db: Session, user: User
) -> Optional[ProactiveBriefing]:
    interests = _policy_interests(user)
    if not interests:
        return None

    cutoff = datetime.now(timezone.utc) - timedelta(days=NEW_FILE_WINDOW_DAYS)
    try:
        rows = db.execute(
            text(
                """
                SELECT title, oeil_procedure_ref
                FROM legislative_carriages
                WHERE first_seen >= :cutoff
                  AND EXISTS (
                      SELECT 1 FROM unnest(policy_areas) AS area_v
                      WHERE EXISTS (
                          SELECT 1 FROM unnest(CAST(:interests AS text[])) AS interest_v
                          WHERE LOWER(area_v) = LOWER(interest_v)
                             OR LOWER(area_v) LIKE '%' || LOWER(interest_v) || '%'
                             OR LOWER(interest_v) LIKE '%' || LOWER(area_v) || '%'
                      )
                  )
                ORDER BY first_seen DESC
                LIMIT 3
                """
            ),
            {"cutoff": cutoff, "interests": interests},
        ).mappings().all()
    except Exception as exc:
        logger.warning("new_file_match query failed: %s", exc)
        db.rollback()
        return None

    if not rows:
        return None

    titles = [r["title"] for r in rows]
    refs = [r["oeil_procedure_ref"] for r in rows if r.get("oeil_procedure_ref")]
    count = len(rows)

    if count == 1:
        title = "A new legislative file landed in your policy areas"
        summary = f"In the last week, one file matched your interests: {titles[0]}."
    else:
        title = (
            f"{count} new legislative files landed in your policy areas this week"
        )
        summary = (
            "Recent matches include: "
            + "; ".join(titles[:3])
            + "."
        )

    return ProactiveBriefing(
        trigger_source="new_file_match",
        title=title,
        summary=summary,
        suggested_query=(
            "Brief me on the EU legislative files added in the last week "
            "that match my policy interests."
        ),
        evidence_refs=refs,
        drill_down_path="/my-eu-bubble?tab=my_files",
    )


def _briefing_tracked_file_movement(
    db: Session, user: User
) -> Optional[ProactiveBriefing]:
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=TRACKED_MOVEMENT_WINDOW_DAYS
    )
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    lc.title,
                    lc.oeil_procedure_ref AS procedure_ref,
                    h.status AS new_status,
                    h.changed_at
                FROM user_carriage_tracks uct
                JOIN legislative_carriages lc ON lc.id = uct.carriage_id
                JOIN carriage_status_history h ON h.carriage_id = lc.id
                WHERE uct.user_id = :uid
                  AND h.changed_at >= :cutoff
                ORDER BY h.changed_at DESC
                LIMIT 3
                """
            ),
            {"uid": str(user.id), "cutoff": cutoff},
        ).mappings().all()
    except Exception as exc:
        logger.warning("tracked_file_movement query failed: %s", exc)
        db.rollback()
        return None

    if not rows:
        return None

    refs = [r["procedure_ref"] for r in rows if r.get("procedure_ref")]
    count = len(rows)
    if count == 1:
        r = rows[0]
        status_text = (
            str(r["new_status"]).replace("_", " ").lower()
            if r.get("new_status")
            else "an unknown status"
        )
        title = f"One of your tracked files moved to {status_text}"
        summary = f"{r['title']} changed status this week."
    else:
        title = f"{count} of your tracked files moved this week"
        summary = (
            "Status changes on: "
            + "; ".join(r["title"] for r in rows[:3])
            + "."
        )

    return ProactiveBriefing(
        trigger_source="tracked_file_movement",
        title=title,
        summary=summary,
        suggested_query=(
            "Summarise the status changes on the files I track in the last "
            "week and what they mean for the procedure timeline."
        ),
        evidence_refs=refs,
        drill_down_path="/my-eu-bubble?tab=my_files",
    )


def _briefing_amendment_surge(
    db: Session, user: User
) -> Optional[ProactiveBriefing]:
    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=AMENDMENT_SURGE_WINDOW_HOURS
    )
    try:
        rows = db.execute(
            text(
                """
                SELECT
                    lc.title,
                    lc.oeil_procedure_ref AS procedure_ref,
                    COUNT(ma.id) AS amendment_count
                FROM user_carriage_tracks uct
                JOIN legislative_carriages lc ON lc.id = uct.carriage_id
                JOIN mep_amendments ma
                  ON ma.procedure_reference = lc.oeil_procedure_ref
                WHERE uct.user_id = :uid
                  AND ma.document_date >= :cutoff
                GROUP BY lc.id, lc.title, lc.oeil_procedure_ref
                HAVING COUNT(ma.id) >= :threshold
                ORDER BY amendment_count DESC
                LIMIT 1
                """
            ),
            {
                "uid": str(user.id),
                "cutoff": cutoff,
                "threshold": AMENDMENT_SURGE_THRESHOLD,
            },
        ).mappings().all()
    except Exception as exc:
        logger.debug("amendment_surge query unavailable: %s", exc)
        db.rollback()
        return None

    if not rows:
        return None

    r = rows[0]
    return ProactiveBriefing(
        trigger_source="amendment_surge",
        title=f"{r['amendment_count']} new amendments tabled on a file you track",
        summary=(
            f"{r['title']} received {r['amendment_count']} amendments in the "
            "last 24 hours. The centre of gravity may have moved."
        ),
        suggested_query=(
            f"Summarise the new amendments tabled in the last 24 hours on "
            f"procedure {r.get('procedure_ref') or r['title']}, and tell me "
            "which articles are most affected."
        ),
        evidence_refs=[r["procedure_ref"]] if r.get("procedure_ref") else [],
        drill_down_path="/my-eu-bubble?tab=amendments",
    )


def _briefing_morning(
    db: Session, user: User, today: date
) -> Optional[ProactiveBriefing]:
    """
    Morning briefing — fires only if the user has not already had one today
    AND there is at least one meaningful signal to mention.
    """
    interests = _policy_interests(user)

    # Pull one calendar event for today. Always prefer real EU institutional
    # events (EP / COMMISSION / COUNCIL / EUROPEAN_COUNCIL / ECB / COR / etc.)
    # over THIRD_PARTY euagenda.eu listings, then prefer those that match the
    # user's policy interests.
    today_event = None
    try:
        if interests:
            row = (
                db.execute(
                    text(
                        """
                        SELECT title, institution, source_url
                        FROM eu_calendar_events
                        WHERE start_date = :today
                          AND status != 'cancelled'
                          AND institution != 'THIRD_PARTY'
                          AND EXISTS (
                      SELECT 1 FROM unnest(policy_areas) AS area_v
                      WHERE EXISTS (
                          SELECT 1 FROM unnest(CAST(:interests AS text[])) AS interest_v
                          WHERE LOWER(area_v) = LOWER(interest_v)
                             OR LOWER(area_v) LIKE '%' || LOWER(interest_v) || '%'
                             OR LOWER(interest_v) LIKE '%' || LOWER(area_v) || '%'
                      )
                  )
                        ORDER BY start_time ASC NULLS LAST
                        LIMIT 1
                        """
                    ),
                    {"today": today, "interests": interests},
                )
                .mappings()
                .first()
            )
            today_event = row
        if not today_event:
            # Any real EU institutional event today.
            row = (
                db.execute(
                    text(
                        """
                        SELECT title, institution, source_url
                        FROM eu_calendar_events
                        WHERE start_date = :today
                          AND status != 'cancelled'
                          AND institution != 'THIRD_PARTY'
                        ORDER BY start_time ASC NULLS LAST
                        LIMIT 1
                        """
                    ),
                    {"today": today},
                )
                .mappings()
                .first()
            )
            today_event = row
        if not today_event:
            # Final fallback: third-party Brussels events. Better than nothing.
            row = (
                db.execute(
                    text(
                        """
                        SELECT title, institution, source_url
                        FROM eu_calendar_events
                        WHERE start_date = :today
                          AND status != 'cancelled'
                        ORDER BY start_time ASC NULLS LAST
                        LIMIT 1
                        """
                    ),
                    {"today": today},
                )
                .mappings()
                .first()
            )
            today_event = row
    except Exception as exc:
        logger.debug("morning_brief calendar query failed: %s", exc)
        db.rollback()
        today_event = None

    # Only emit a morning briefing if there's something real to say.
    if not today_event:
        return None

    institution = _humanise_institution(today_event.get("institution"))
    event_title = str(today_event["title"]).strip()
    summary = f"{institution} has on its agenda today: {event_title}."

    # The follow-through query matches what the panel actually said: ask
    # about the specific event, not a generic "what is on today's agenda".
    suggested_query = (
        f"Brief me on today's {event_title}: agenda, who is meeting, "
        "and what to watch."
    )

    return ProactiveBriefing(
        trigger_source="morning_brief",
        title="Your EU briefing for today",
        summary=summary,
        suggested_query=suggested_query,
        evidence_refs=[],
        drill_down_path="/my-eu-bubble?tab=eu_calendar",
    )


def _briefing_learn_about_you(
    db: Session, user: User
) -> Optional[ProactiveBriefing]:
    """
    Fired only when Brubru has nothing else to say AND the user has not
    told it what they care about. Companion ask-to-learn move.
    """
    interests = _policy_interests(user)
    if interests:
        return None

    try:
        count = db.execute(
            text("SELECT COUNT(*) FROM user_carriage_tracks WHERE user_id = :uid"),
            {"uid": str(user.id)},
        ).scalar()
    except Exception as exc:
        logger.debug("learn_about_you count query failed: %s", exc)
        db.rollback()
        return None

    if count and int(count) > 0:
        return None

    return ProactiveBriefing(
        trigger_source="learn_about_you",
        title="Tell me what you follow",
        summary=(
            "I do not know your portfolio yet. Tell me one EU file or topic "
            "you care about and I will keep an eye on it for you."
        ),
        suggested_query=(
            "I follow the following EU files and topics: "
        ),
        evidence_refs=[],
        drill_down_path="/profile",
    )


def compute_pending_briefings(
    db: Session,
    user: User,
    today: Optional[date] = None,
) -> List[ProactiveBriefing]:
    """
    Compute up to ``MAX_BRIEFINGS_PER_REQUEST`` briefings for the user.
    Order of priority: amendment surge → tracked-file movement →
    new-file match → morning brief.
    """
    if not user or not user.is_active:
        return []

    today = today or date.today()
    briefings: List[ProactiveBriefing] = []

    for fn in (
        lambda: _briefing_amendment_surge(db, user),
        lambda: _briefing_tracked_file_movement(db, user),
        lambda: _briefing_new_file_match(db, user),
        lambda: _briefing_morning(db, user, today),
        lambda: _briefing_learn_about_you(db, user),
    ):
        if len(briefings) >= MAX_BRIEFINGS_PER_REQUEST:
            break
        try:
            b = fn()
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("proactive trigger evaluation failed: %s", exc)
            db.rollback()
            continue
        if b is not None:
            briefings.append(b)

    return briefings
