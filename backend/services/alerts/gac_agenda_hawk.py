"""GAC Agenda Hawk.

Watches the upcoming General Affairs Council agenda from
`eu_calendar_events` (where the EU Calendar pipeline has already ingested
official Council calendar items). For each upcoming GAC meeting whose
agenda or description mentions the EU language regime, raises a
high-priority `notifications` row for every user who has an active
"linguistic minorities" / "official languages" type subscription.

KNOWN LIMITATION (2026-05-22): `eu_calendar_events` currently only
carries the meeting envelope (date + 1-sentence description). The
line-item draft agenda lives at
`consilium.europa.eu/en/meetings/gac/{YYYY}/{MM}/{DD}/` and needs a
dedicated scraper to ingest item titles. Until that lands, the Hawk
fires only when the meeting description itself names a language-regime
keyword — which Council's own copy-writers don't always do. TODO:
add `services/scrapers/gac_draft_agenda_scraper.py`.

Why a separate runner from the generic saved_search_runner?
1. Generic runner scans rows by `created_at`/`scraped_at` looking back N
   days. GAC items are about a FUTURE event (start_date), so the right
   trigger is "meeting is in the next 60 days" not "row was added".
2. Priority needs to be `urgent`, not `normal`.
3. We also enrich the notification with days-to-meeting and an opt-out
   for users who already have a manually-pinned subscription.

Fires once per (user, event_id). Idempotent via the
`(notification_type='gac_agenda_hawk', related_entity_type='eu_calendar_event',
related_entity_id)` triple.

CLI: python3.12 -m services.alerts.gac_agenda_hawk [--horizon-days N] [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import psycopg2
import psycopg2.extras

logger = logging.getLogger("alerts.gac_agenda_hawk")

# Words/phrases that mark a GAC item as "language-regime relevant".
# Case-insensitive. Matched against title + description + agenda body if any.
LANGUAGE_REGIME_PATTERNS = [
    r"\bofficial language(?:s)? of the (?:European )?Union\b",
    r"\blanguage(?:s)? of the (?:European )?Union\b",
    r"\blinguistic regime\b",
    r"\blanguage regime\b",
    r"\bRegulation (?:No |No\. )?1/1958\b",
    r"\bRegulation\s+1\s*/\s*1958\b",
    r"\b31958R0001\b",
    r"\bArticle 342 TFEU\b",
    r"\bArt(?:icle|\.|) 342\b.*TFEU",
    r"\bmultilingualism\b",
    r"\blinguistic diversity\b",
    r"\bminority languages?\b",
    r"\bregional languages?\b",
    r"\bECRML\b",
    r"\bCatalan\b",
    r"\bBasque\b",
    r"\bGalician\b",
    r"\bAranese\b",
    # Spain's August 2023 memorandum referencing patterns
    r"\bSpanish memorandum\b",
    r"\bofficiality.*EU\b",
]
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in LANGUAGE_REGIME_PATTERNS]


def _event_matches(text_blob: str) -> list[str]:
    """Return the list of pattern matches that fired. Empty list = no match."""
    if not text_blob:
        return []
    hits = []
    for p in COMPILED_PATTERNS:
        m = p.search(text_blob)
        if m:
            hits.append(m.group(0))
    return hits


def _target_users(cur) -> list[dict]:
    """Users who should get GAC hawk alerts.

    Criterion: any user with at least one active alert subscription whose
    `query_phrase` contains a language-regime keyword. That's the same
    eligibility the user already opted into for the corpus scan; the GAC
    hawk is the upcoming-event version of the same subscription.

    Returns dicts {id, email, label}.
    """
    cur.execute(
        """
        SELECT DISTINCT u.id, u.email, s.label
        FROM users u
        JOIN user_alert_subscriptions s ON s.user_id = u.id
        WHERE s.is_active = TRUE
          AND (
              s.query_phrase ILIKE '%official languages%' OR
              s.query_phrase ILIKE '%linguistic%' OR
              s.query_phrase ILIKE '%minority language%' OR
              s.query_phrase ILIKE '%regional language%' OR
              s.query_phrase ILIKE '%Catalan%' OR
              s.query_phrase ILIKE '%Basque%' OR
              s.query_phrase ILIKE '%Galician%' OR
              s.query_phrase ILIKE '%language regime%' OR
              s.query_phrase ILIKE '%1/1958%' OR
              s.query_phrase ILIKE '%multilingual%'
          )
        """
    )
    return [dict(r) for r in cur.fetchall()]


def _upcoming_gac_events(cur, horizon_days: int) -> list[dict]:
    cur.execute(
        """
        SELECT id, title, description, start_date, agenda_url, source_url, council_configuration
        FROM eu_calendar_events
        WHERE institution = 'COUNCIL'
          AND council_configuration ILIKE %s
          AND start_date >= CURRENT_DATE
          AND start_date <= CURRENT_DATE + make_interval(days => %s)
        ORDER BY start_date
        """,
        ('%gac%', horizon_days),
    )
    return [dict(r) for r in cur.fetchall()]


def _notification_exists(cur, user_id, event_id) -> bool:
    cur.execute(
        """
        SELECT 1 FROM notifications
        WHERE user_id = %s
          AND notification_type = 'gac_agenda_hawk'
          AND related_entity_type = 'eu_calendar_event'
          AND related_entity_id = %s
        LIMIT 1
        """,
        (user_id, event_id),
    )
    return cur.fetchone() is not None


def _create_notification(cur, user_id, event, matches: list[str]) -> None:
    title = f"GAC {event['start_date']}: agenda touches language regime"
    days_to = (event['start_date'] - datetime.now(timezone.utc).date()).days
    matches_preview = ", ".join(sorted(set(matches))[:3])
    msg = (
        f"Upcoming General Affairs Council on {event['start_date']} "
        f"({days_to} day{'s' if days_to != 1 else ''} away) — the agenda or "
        f"description mentions: {matches_preview}. "
        f"This is the Council formation that handles Regulation 1/1958 amendments."
    )
    action_url = event.get('agenda_url') or event.get('source_url') or (
        'https://www.consilium.europa.eu/en/council-eu/configurations/gac/'
    )
    cur.execute(
        """
        INSERT INTO notifications
            (id, user_id, notification_type, title, message, action_url,
             notif_metadata, related_entity_type, related_entity_id,
             priority, is_read, created_at)
        VALUES
            (%s, %s, 'gac_agenda_hawk', %s, %s, %s, %s::jsonb,
             'eu_calendar_event', %s, 'urgent', FALSE, NOW())
        """,
        (
            str(uuid4()),
            user_id,
            title[:500],
            msg[:5000],
            action_url,
            psycopg2.extras.Json(
                {
                    'event_id': str(event['id']),
                    'start_date': str(event['start_date']),
                    'days_to_meeting': days_to,
                    'pattern_hits': matches[:10],
                    'council_configuration': event.get('council_configuration'),
                    'source': 'gac_agenda_hawk',
                }
            ),
            event['id'],
        ),
    )


def run(horizon_days: int = 60, dry_run: bool = False) -> dict:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise RuntimeError('DATABASE_URL not set')
    conn = psycopg2.connect(db_url)
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    users = _target_users(cur)
    events = _upcoming_gac_events(cur, horizon_days)
    summary = {
        'eligible_users': len(users),
        'gac_events_scanned': len(events),
        'matched_events': 0,
        'notifications_created': 0,
        'events': [],
    }

    for ev in events:
        text_blob = (ev.get('title') or '') + '\n' + (ev.get('description') or '')
        matches = _event_matches(text_blob)
        event_record = {
            'id': str(ev['id']),
            'start_date': str(ev['start_date']),
            'title': (ev.get('title') or '')[:80],
            'matched': bool(matches),
            'matches': matches,
            'notified_users': 0,
        }
        if not matches:
            summary['events'].append(event_record)
            continue
        summary['matched_events'] += 1
        for u in users:
            if _notification_exists(cur, u['id'], ev['id']):
                continue
            if not dry_run:
                _create_notification(cur, u['id'], ev, matches)
            event_record['notified_users'] += 1
            summary['notifications_created'] += 1
        if not dry_run:
            conn.commit()
        summary['events'].append(event_record)

    cur.close()
    conn.close()
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--horizon-days', type=int, default=60)
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--verbose', '-v', action='store_true')
    args = p.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s %(message)s',
    )
    s = run(horizon_days=args.horizon_days, dry_run=args.dry_run)
    print('---')
    print(f'eligible_users:        {s["eligible_users"]}')
    print(f'gac_events_scanned:    {s["gac_events_scanned"]}')
    print(f'matched_events:        {s["matched_events"]}')
    print(f'notifications_created: {s["notifications_created"]}')
    for e in s['events']:
        flag = '[MATCH]' if e['matched'] else '[skip ]'
        print(f'  {flag} {e["start_date"]} {e["title"]}  notified={e["notified_users"]}  matches={e["matches"]}')


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    main()
