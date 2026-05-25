"""Saved-search alert runner.

Reads every active row in `user_alert_subscriptions`, scans the configured
corpora (eu_laws + texts_adopted + legislative_carriages + rss_entries) for
matches newer than the subscription's `last_run_at`, and writes one
`notifications` row per match. Existing notifications service handles the
chat-greeting + MEUB tile + email surfaces.

Idempotent: scoped on row `created_at`/`scraped_at`/`first_seen` (whichever
the table exposes), so re-running the same subscription twice never produces
duplicate notifications for the same corpus row in the same window.

CLI: python3.12 -m services.alerts.saved_search_runner [--user-email X] [--dry-run]
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from uuid import UUID, uuid4

import psycopg2
import psycopg2.extras

logger = logging.getLogger("alerts.saved_search_runner")

# Maximum new matches per subscription per run, to prevent a noisy keyword
# (e.g. "Catalan") from spamming a user's notification feed on the first run.
MAX_MATCHES_PER_SUB_PER_RUN = 25

# Lookback fallback when a subscription has never been run before. Avoids
# producing thousands of historical hits on first activation.
INITIAL_LOOKBACK_DAYS = 30


@dataclass
class CorpusQuery:
    """One scope's read query, parameterised by the subscription's tsquery
    and the last_run_at cut-off.
    """
    scope: str
    sql: str
    # Maps row -> dict(notification_type, title, message, action_url, related_*)
    formatter: callable


# ---------------------------------------------------------------------------
# Corpus queries
# ---------------------------------------------------------------------------


def _eu_laws_query() -> CorpusQuery:
    sql = """
    SELECT id, celex, title, date, doc_type, oj_reference, created_at
    FROM eu_laws
    WHERE search_vector @@ websearch_to_tsquery('simple', %(phrase)s)
      AND created_at > %(since)s
    ORDER BY created_at DESC
    LIMIT %(limit)s
    """

    def fmt(row, sub):
        celex = row['celex'] or ''
        title = (row['title'] or '')[:480]
        return {
            'notification_type': 'saved_search_alert',
            'title': title,
            'message': f'New EU instrument matches "{sub["label"]}". CELEX {celex}.',
            'action_url': f'https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}' if celex else None,
            'related_entity_type': 'eu_law',
            'related_entity_id': row['id'],
            'priority': 'normal',
            'notif_metadata': {
                'subscription_id': str(sub['id']),
                'subscription_label': sub['label'],
                'scope': 'eu_laws',
                'celex': celex,
                'doc_type': row['doc_type'],
                'oj_reference': row['oj_reference'],
                'date': str(row['date']) if row.get('date') else None,
            },
        }

    return CorpusQuery('eu_laws', sql, fmt)


def _texts_adopted_query() -> CorpusQuery:
    # No search_vector here; rely on ILIKE on title + full_text head.
    sql = """
    SELECT id, ta_reference, title, adoption_date, procedure_ref, scraped_at, first_seen,
           rapporteur_name, committees, source_url
    FROM texts_adopted
    WHERE (
        title ILIKE %(like_pattern)s
        OR description ILIKE %(like_pattern)s
        OR substring(coalesce(full_text,'') from 1 for 30000) ILIKE %(like_pattern)s
    )
      AND (first_seen > %(since)s OR scraped_at > %(since)s)
    ORDER BY first_seen DESC NULLS LAST, scraped_at DESC NULLS LAST
    LIMIT %(limit)s
    """

    def fmt(row, sub):
        ta_ref = row['ta_reference'] or ''
        return {
            'notification_type': 'saved_search_alert',
            'title': (row['title'] or ta_ref)[:480],
            'message': f'EP text adopted ({ta_ref}) matches "{sub["label"]}". Procedure {row["procedure_ref"] or "n/a"}.',
            'action_url': row['source_url'],
            'related_entity_type': 'text_adopted',
            'related_entity_id': row['id'],
            'priority': 'normal',
            'notif_metadata': {
                'subscription_id': str(sub['id']),
                'subscription_label': sub['label'],
                'scope': 'texts_adopted',
                'ta_reference': ta_ref,
                'procedure_ref': row['procedure_ref'],
                'rapporteur_name': row['rapporteur_name'],
                'adoption_date': str(row['adoption_date']) if row.get('adoption_date') else None,
            },
        }

    return CorpusQuery('texts_adopted', sql, fmt)


def _legislative_carriages_query() -> CorpusQuery:
    sql = """
    SELECT id, oeil_procedure_ref, lead_committee, current_status, title, text_type,
           last_updated, scraped_at, first_seen
    FROM legislative_carriages
    WHERE (
        title ILIKE %(like_pattern)s
        OR description ILIKE %(like_pattern)s
        OR coalesce(oeil_text_body,'') ILIKE %(like_pattern)s
    )
      AND (first_seen > %(since)s OR last_updated > %(since)s)
    ORDER BY first_seen DESC NULLS LAST, last_updated DESC NULLS LAST
    LIMIT %(limit)s
    """

    def fmt(row, sub):
        ref = row['oeil_procedure_ref'] or ''
        return {
            'notification_type': 'saved_search_alert',
            'title': (row['title'] or ref)[:480],
            'message': f'Legislative file ({ref or "no OEIL ref"}, {row["lead_committee"] or "?"}, {row["current_status"] or "?"}) matches "{sub["label"]}".',
            'action_url': (f'https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={ref}'
                           if ref else None),
            'related_entity_type': 'legislative_carriage',
            'related_entity_id': row['id'],
            'priority': 'normal',
            'notif_metadata': {
                'subscription_id': str(sub['id']),
                'subscription_label': sub['label'],
                'scope': 'legislative_carriages',
                'oeil_procedure_ref': ref,
                'lead_committee': row['lead_committee'],
                'current_status': row['current_status'],
                'text_type': row['text_type'],
            },
        }

    return CorpusQuery('legislative_carriages', sql, fmt)


def _rss_entries_query() -> CorpusQuery:
    sql = """
    SELECT id, title, summary, link, published_at, institution, policy_area
    FROM rss_entries
    WHERE (
        title ILIKE %(like_pattern)s
        OR coalesce(summary,'') ILIKE %(like_pattern)s
        OR substring(coalesce(content,'') from 1 for 20000) ILIKE %(like_pattern)s
    )
      AND published_at > %(since)s
    ORDER BY published_at DESC
    LIMIT %(limit)s
    """

    def fmt(row, sub):
        return {
            'notification_type': 'saved_search_alert',
            'title': (row['title'] or 'News item')[:480],
            'message': f'News from {row["institution"] or "EU source"} matches "{sub["label"]}".',
            'action_url': row['link'],
            'related_entity_type': 'rss_entry',
            'related_entity_id': row['id'],
            'priority': 'normal',
            'notif_metadata': {
                'subscription_id': str(sub['id']),
                'subscription_label': sub['label'],
                'scope': 'rss_entries',
                'institution': row['institution'],
                'policy_area': row['policy_area'],
                'published_at': row['published_at'].isoformat() if row.get('published_at') else None,
            },
        }

    return CorpusQuery('rss_entries', sql, fmt)


_SCOPE_QUERIES = {
    'eu_laws': _eu_laws_query(),
    'texts_adopted': _texts_adopted_query(),
    'legislative_carriages': _legislative_carriages_query(),
    'rss_entries': _rss_entries_query(),
}


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _derive_like_pattern(phrase: str) -> str:
    """Heuristic conversion of a query phrase to an ILIKE pattern when the
    target table lacks a search_vector.

    "official languages of the Union" -> '%official languages of the Union%'
    'Catalan OR Basque OR Galician'   -> use only first term '%Catalan%'
                                          (per-table ANY-of fallback handled
                                          by running the runner once per
                                          term — see _split_or_terms below).
    """
    return '%' + phrase.strip('%') + '%'


def _split_or_terms(phrase: str) -> list[str]:
    """If the phrase is `A OR B OR C` (case-insensitive), return [A, B, C].
    Otherwise return [phrase].
    """
    parts = re.split(r'\s+OR\s+', phrase, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


def _notification_exists(cur, user_id: str, related_entity_type: str, related_entity_id) -> bool:
    """Idempotency check: did we already write a notification for this row
    under this user? Saves us from double-firing on rerun."""
    cur.execute(
        """
        SELECT 1 FROM notifications
        WHERE user_id = %s
          AND notification_type = 'saved_search_alert'
          AND related_entity_type = %s
          AND related_entity_id = %s
        LIMIT 1
        """,
        (user_id, related_entity_type, related_entity_id),
    )
    return cur.fetchone() is not None


def _create_notification(cur, user_id: str, payload: dict) -> None:
    cur.execute(
        """
        INSERT INTO notifications
            (id, user_id, notification_type, title, message, action_url,
             notif_metadata, related_entity_type, related_entity_id,
             priority, is_read, created_at)
        VALUES
            (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, FALSE, NOW())
        """,
        (
            str(uuid4()),
            user_id,
            payload['notification_type'],
            payload['title'][:500],
            payload['message'][:5000],
            payload.get('action_url'),
            psycopg2.extras.Json(payload.get('notif_metadata') or {}),
            payload.get('related_entity_type'),
            payload.get('related_entity_id'),
            payload.get('priority', 'normal'),
        ),
    )


def _run_one_subscription(cur, sub: dict, dry_run: bool = False) -> int:
    """Run one subscription. Returns number of new notifications created."""
    user_id = str(sub['user_id'])
    label = sub['label']
    scopes = sub['scopes'] or ['eu_laws', 'texts_adopted', 'legislative_carriages', 'rss_entries']
    since = sub['last_run_at'] or (datetime.now(timezone.utc) - timedelta(days=INITIAL_LOOKBACK_DAYS))
    excludes = set(t.lower() for t in (sub.get('exclude_terms') or []))

    or_terms = _split_or_terms(sub['query_phrase'])
    created = 0

    for scope in scopes:
        q = _SCOPE_QUERIES.get(scope)
        if not q:
            logger.warning('Unknown scope %s for subscription %s', scope, sub['id'])
            continue

        for term in or_terms:
            if created >= MAX_MATCHES_PER_SUB_PER_RUN:
                break
            params = {
                'phrase': term,
                'like_pattern': _derive_like_pattern(term),
                'since': since,
                'limit': MAX_MATCHES_PER_SUB_PER_RUN - created,
                'lang_filter': sub.get('language_codes'),
            }
            try:
                cur.execute(q.sql, params)
            except Exception as e:  # pragma: no cover  one scope failure shouldn't kill run
                logger.error('Scope %s query failed for sub %s: %s', scope, sub['id'], e)
                continue
            rows = cur.fetchall()
            for r in rows:
                if created >= MAX_MATCHES_PER_SUB_PER_RUN:
                    break
                # Exclude-terms filter on title/message
                text_blob = ((r.get('title') or '') + ' ' + (r.get('summary') or r.get('description') or ''))[:1000].lower()
                if excludes and any(e in text_blob for e in excludes):
                    continue
                payload = q.formatter(r, sub)
                if sub.get('priority_override'):
                    payload['priority'] = sub['priority_override']
                related_id = payload.get('related_entity_id')
                if related_id is None:
                    continue
                if _notification_exists(cur, user_id, payload['related_entity_type'], related_id):
                    continue
                if not dry_run:
                    _create_notification(cur, user_id, payload)
                created += 1

    # Update last_run_at + counters even on dry-run? No — dry-run is read-only.
    if not dry_run:
        cur.execute(
            """
            UPDATE user_alert_subscriptions
            SET last_run_at = NOW(),
                last_match_count = %s,
                last_match_at = CASE WHEN %s > 0 THEN NOW() ELSE last_match_at END
            WHERE id = %s
            """,
            (created, created, sub['id']),
        )
    return created


def run_all(user_email: Optional[str] = None, dry_run: bool = False) -> dict:
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        raise RuntimeError('DATABASE_URL not set')
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    where = 'WHERE s.is_active = TRUE'
    params: tuple = ()
    if user_email:
        where += ' AND u.email = %s'
        params = (user_email,)
    cur.execute(
        f"""
        SELECT s.*, u.email AS user_email
        FROM user_alert_subscriptions s
        JOIN users u ON u.id = s.user_id
        {where}
        ORDER BY s.last_run_at NULLS FIRST
        """,
        params,
    )
    subs = cur.fetchall()
    summary = {'subscriptions_run': 0, 'notifications_created': 0, 'by_subscription': []}
    for sub in subs:
        try:
            n = _run_one_subscription(cur, sub, dry_run=dry_run)
        except Exception as e:
            logger.error('Subscription %s failed: %s', sub['id'], e)
            conn.rollback()
            continue
        if not dry_run:
            conn.commit()
        summary['subscriptions_run'] += 1
        summary['notifications_created'] += n
        summary['by_subscription'].append({
            'id': str(sub['id']),
            'user': sub['user_email'],
            'label': sub['label'],
            'new_notifications': n,
        })
    cur.close()
    conn.close()
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--user-email', help='Only run subscriptions owned by this email')
    p.add_argument('--dry-run', action='store_true', help='Scan but do not create notifications')
    p.add_argument('--verbose', '-v', action='store_true')
    args = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s')
    summary = run_all(user_email=args.user_email, dry_run=args.dry_run)
    print('---')
    print(f'subscriptions_run: {summary["subscriptions_run"]}')
    print(f'notifications_created: {summary["notifications_created"]}')
    for s in summary['by_subscription']:
        print(f'  [{s["new_notifications"]}] {s["user"]} - {s["label"]}')


if __name__ == '__main__':
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    main()
