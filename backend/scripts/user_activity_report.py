#!/usr/bin/env python3.12
"""
User activity report -- what pre-users and users actually DID in Brubru, across
every product surface, and how Brubru responded.

Backs the `/users` skill. `/audit-queries` reads what users TYPED to Chat and how
Chat answered; `/hotjar` reads how they BEHAVED client-side. This reads the
server-side system of record for ALL SIX products (Chat, Amendator, EU Law
Comply, Tenderator, Documents, API) plus My EU Bubble tracking and the pre-user
funnel.

Why a script and not inline SQL in the skill: three joins here are easy to get
wrong and each one silently inverts the conclusion.

  1. `users.tier` DOES NOT EXIST. The column is `subscription_tier`. A query
     naming `u.tier` errors out; one that omits tiering silently mixes
     subscribers with anonymous traffic.

  2. An anonymous chat still writes a NON-NULL `chats.user_id` -- a synthetic
     UUID derived from `pre_user_id`, with no row in `users`. Segmenting on
     `user_id IS NULL` therefore counts anonymous sessions as signed-in users.
     The only correct test is a LEFT JOIN with `users.id IS NULL`.

  3. Roughly half of recent chat traffic is OUR OWN deploy probes
     (`pre_user_id` = 'deploy-probe', 'verify-prod-0807', 'link-audit', ...).
     Real `pre_user_id`s are UUIDs; the harness ones are human-typed slugs.
     Counting them as users makes a dead week look healthy.

Usage:
    python3.12 scripts/user_activity_report.py --days 1
    python3.12 scripts/user_activity_report.py --since 2026-08-01 --until 2026-08-09
    python3.12 scripts/user_activity_report.py --days 7 --json
    python3.12 scripts/user_activity_report.py --days 7 --include-internal
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent
# Run as a script, sys.path[0] is scripts/, so `models.*` is not importable and
# the imports below fall back to empty sets -- which made the event-type check
# vanish from the report entirely rather than fail loudly.
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
load_dotenv(BACKEND_DIR.parent / ".env")


# --------------------------------------------------------------------------
# Segmentation
# --------------------------------------------------------------------------
# An actor is INTERNAL if it is us, a seeded fixture, or a pre-provisioned
# prospect shell. Internal actors are excluded by default: they are the loudest
# rows in every table and they are not evidence of anything.
#
# A pre-provisioned prospect shell is identified by the claim flow itself, NOT by
# a missing email. Until 14 Aug 2026 this test was "email IS NULL", on the
# assumption that a shell never carries one. It broke the day two dormant
# profiles were created together: the one with email NULL was excluded, and
# `support@cadence.com` was counted as a paying weekly-active user on the
# strength of ten actions that were all its own provisioning writes, four
# minutes after the row was created. Nobody at Cadence had been contacted.
#
# A row is a shell while `pre_provisioned_at` is set and `claimed_at` is not.
# On the day a human claims it, `claimed_at` fills in and the row becomes a real
# actor with real history. 19 unclaimed shells existed when this was written,
# against 3 ever claimed, so the default has to be exclusion.
INTERNAL_USER_SQL = """
    (
        u.role = 'admin'
        OR u.is_trainer IS TRUE
        -- U3 (27 Aug 2026): provisioned + unclaimed + NEVER LOGGED IN.
        -- The `last_login IS NULL` clause is the whole change. A shell a real
        -- human has signed into is not our own row, whatever its claim state:
        -- on 26 Aug two GBSB staff logged in during a live demo and this rule
        -- filed both as "internal", so Section 1 printed "(none)" on a day
        -- three people used Brubru. A binary flag could not express the third
        -- state; SEGMENT_SQL now carries `logged_in_unclaimed` for it.
        OR (u.pre_provisioned_at IS NOT NULL AND u.claimed_at IS NULL
            AND u.last_login IS NULL)
        OR u.email IS NULL OR u.email = ''
        OR u.email ILIKE '%beresol%'
        OR u.email ILIKE '%@example.com'
        OR u.email ILIKE '%demo.invalid'
        OR u.email ILIKE '%@brubru.dev'
        OR u.email ILIKE 'test%'
        OR u.email ILIKE 'prospect+%'
        OR u.email ILIKE 'v2_%'
        OR u.email ILIKE 'v2sec_%'
        -- U4 (10 Sep 2026). Hellobo 2025 SL is the founder's own company, and
        -- vsoleferioli@ is his personal account. Neither is a customer.
        --
        -- The account this rule was PROPOSED for, victor@hellobo.eu, was already
        -- caught by `is_trainer IS TRUE` above -- verified by running this very
        -- predicate against it. The finding that put it here came from a
        -- hand-typed ad-hoc filter in the morning's analysis, not from this
        -- report, and was wrongly attributed to the report. What the domain rule
        -- actually adds is the three OTHER hellobo.eu rows (Sergi Duarte,
        -- Meritxell Vicheto, Bo), which are seeded test users.
        OR u.email ILIKE '%@hellobo.eu'
        OR u.email = 'vsoleferioli@gmail.com'
    )
"""

# The 13 seeded test users (backend/scripts/seed_test_users.py, password test123)
# are NOT filtered here, and 7 of them currently read as customers. Listed rather
# than silently applied, because the call is a product judgement and not mine:
#
#   margapayola@gmail.com   blue,   8 tracks -- and the ONLY account that has ever
#                           received a notification (103 of them, 0 read). Today's
#                           /users run named her as a real actor with self-chosen
#                           tracking. She is a fixture.
#   j.gonzalez@bepassociation.eu   blue -- reported this morning as one of the six
#                           accounts "past expiry, still fully served".
#   danielroldan1989@gmail.com, aleixsarri@gmail.com, marc.desmond10@gmail.com,
#   andres.lopez1@alumni.esade.edu  -- blue/yellow, little or no activity.
#
# Some of these are real people who were given a seeded account, so filtering them
# would erase genuine usage; some are pure fixtures whose rows have already been
# read as customer engagement. Deciding which is which needs Victor.
# See memory/feedback_seed_fixtures_contaminate_prod.md -- same defect class as the
# synthetic transcript that fed the chatbot in April 2026.
SEEDED_TEST_USER_EMAILS_PENDING_DECISION = (
    "margapayola@gmail.com",
    "j.gonzalez@bepassociation.eu",
    "danielroldan1989@gmail.com",
    "aleixsarri@gmail.com",
    "marc.desmond10@gmail.com",
    "andres.lopez1@alumni.esade.edu",
)

# Our own traffic, two ways.
#
# Forward-looking: probes send `X-Brubru-Probe: 1`, which stamps
# chat_metadata.is_probe. This is the reliable signal -- use it for anything new.
#
# Historical: before 9 Aug 2026 probes were only identifiable by shape. Real
# pre_user_ids are client-generated UUIDs; ours were slugs typed by hand
# ('deploy-probe', 'multiturn-0807', 'picky-0807'). That heuristic still covers
# the back catalogue, but it never caught probe runs that sent no identifier at
# all -- 20 audit queries in 9 minutes on 7 Aug read as 20 anonymous users.
# Those remain miscounted in history and cannot be recovered; only the header
# fixes it going forward.
# COALESCE is load-bearing, not defensive noise. `chat_metadata` is NULL on
# almost every row, and `(NULL ->> 'is_probe') = 'true'` is NULL rather than
# false. NULL OR false is NULL, and `NOT NULL` is NULL, so a filter written as
# `AND NOT <synthetic>` silently drops every row it was meant to keep. Adding
# the probe clause without this turned the orphaned-anonymous-chat check from
# "51/60 FAIL" into "0/0 OK" -- a real defect reported as fixed.
SYNTHETIC_PRE_USER_SQL = r"""
    (
        COALESCE((c.chat_metadata ->> 'is_probe') = 'true', false)
        OR COALESCE(c.pre_user_id !~ '^[0-9a-f]{8}-[0-9a-f]{4}-', false)
    )
"""

SEGMENT_SQL = f"""
    CASE
        WHEN {SYNTHETIC_PRE_USER_SQL} THEN 'synthetic'
        WHEN u.id IS NULL THEN 'pre-user'
        -- A provisioned shell someone has actually signed into. Reported under
        -- its own name so a demo is visible instead of being folded into 'us'.
        WHEN u.pre_provisioned_at IS NOT NULL AND u.claimed_at IS NULL
             AND u.last_login IS NOT NULL THEN 'logged_in_unclaimed'
        WHEN {INTERNAL_USER_SQL} THEN 'internal'
        WHEN u.subscription_tier IN ('yellow', 'blue') THEN 'subscriber'
        ELSE 'free'
    END
"""

# `logged_in_unclaimed` is a REAL segment: a human signed in. It is not a
# paying subscriber, so it never reaches WAPU, but it must be visible.
REAL_SEGMENTS = ("pre-user", "subscriber", "free", "logged_in_unclaimed")


def _engine():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("[ERROR] DATABASE_URL not found in backend/.env")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return create_engine(url, pool_pre_ping=True)


def q(conn, sql, **params):
    """Run a query, returning list-of-dicts. Missing table -> [] with a note."""
    try:
        rows = conn.execute(text(sql), params).mappings().all()
        return [dict(r) for r in rows]
    except Exception as exc:  # noqa: BLE001 -- a missing table must not kill the run
        conn.rollback()
        msg = str(exc).split("\n")[0][:160]
        return [{"__error__": msg}]


def errored(rows):
    return bool(rows) and "__error__" in rows[0]


# --------------------------------------------------------------------------
# Report sections
# --------------------------------------------------------------------------
def section_actors(conn, start, end, include_internal):
    """Who showed up, in which segment, and on which surfaces."""
    seg_filter = "" if include_internal else "AND seg IN :real"
    rows = q(
        conn,
        f"""
        WITH acts AS (
            SELECT {SEGMENT_SQL} AS seg,
                   COALESCE(u.email, c.pre_user_id, c.user_id::text) AS actor,
                   count(*) AS chats
            FROM chats c
            LEFT JOIN users u ON u.id = c.user_id
            WHERE c.created_at >= :start AND c.created_at < :end
            GROUP BY 1, 2
        )
        SELECT seg, count(*) AS actors, sum(chats) AS chats
        FROM acts WHERE TRUE {seg_filter}
        GROUP BY 1 ORDER BY 3 DESC
        """,
        start=start,
        end=end,
        real=REAL_SEGMENTS,
    )
    signups = q(
        conn,
        f"""
        SELECT u.email, u.subscription_tier, u.organization,
               u.created_at::date AS created, u.last_login::date AS last_login,
               -- Presence, not re-authentication (migration 221). last_login
               -- stays frozen for a returning user whose token refreshes
               -- silently, so it must never be read as "last used". NULL here
               -- means not measured, never absent.
               u.last_seen_at::date AS last_seen,
               {INTERNAL_USER_SQL} AS internal
        FROM users u
        WHERE u.created_at >= :start AND u.created_at < :end
        ORDER BY u.created_at DESC
        """,
        start=start,
        end=end,
    )
    if not include_internal and not errored(signups):
        signups = [s for s in signups if not s.get("internal")]
    return {"segments": rows, "signups": signups}


def section_chat(conn, start, end, include_internal):
    """Chat volume by segment. Detail lives in /audit-queries; this is the frame."""
    seg_filter = "" if include_internal else f"AND {SEGMENT_SQL} IN :real"
    rows = q(
        conn,
        f"""
        SELECT {SEGMENT_SQL} AS segment,
               COALESCE(u.email, c.pre_user_id, 'anon:' || left(c.user_id::text, 8)) AS actor,
               count(DISTINCT c.id) AS chats,
               count(m.id) FILTER (WHERE m.role = 'user') AS user_msgs,
               count(m.id) FILTER (WHERE m.role = 'assistant') AS answers,
               min(c.created_at)::date AS first_seen,
               max(c.created_at)::date AS last_seen
        FROM chats c
        LEFT JOIN users u ON u.id = c.user_id
        LEFT JOIN chat_messages m ON m.chat_id = c.id
        WHERE c.created_at >= :start AND c.created_at < :end {seg_filter}
        GROUP BY 1, 2 ORDER BY 3 DESC
        """,
        start=start,
        end=end,
        real=REAL_SEGMENTS,
    )
    if errored(rows):
        return rows

    # One-shot anonymous sessions are the bulk of the rows and carry no
    # per-actor signal. Roll them into a single line so returning actors -- the
    # ones that matter for WAPU -- stay visible.
    kept, oneshot = [], []
    for r in rows:
        if r["chats"] == 1 and str(r["actor"]).startswith("anon:"):
            oneshot.append(r)
        else:
            kept.append(r)
    if oneshot:
        kept.append(
            {
                "segment": "pre-user",
                "actor": f"({len(oneshot)} one-shot anonymous sessions)",
                "chats": len(oneshot),
                "user_msgs": sum(r["user_msgs"] or 0 for r in oneshot),
                "answers": sum(r["answers"] or 0 for r in oneshot),
                "first_seen": min(r["first_seen"] for r in oneshot if r["first_seen"]),
                "last_seen": max(r["last_seen"] for r in oneshot if r["last_seen"]),
            }
        )
    return kept


def section_preuser_funnel(conn, start, end):
    """The anonymous funnel: page_load -> query_1 -> query_2/3 -> signed_up.

    `pre_user_events` also carries outreach bookkeeping written by the send
    scripts (send_batch_*, send_brubru_brief_*, unsubscribes). Those are things
    WE did, keyed by pre_user_id -- half the table by row count. They are
    labelled here so they can never be read as acquisition.
    """
    try:
        from models.pre_user_event import FUNNEL_EVENT_TYPES
    except Exception:  # noqa: BLE001
        # Label as unknown rather than silently calling outreach rows "funnel".
        FUNNEL_EVENT_TYPES = None
    rows = q(
        conn,
        """
        SELECT event_type, count(*) AS events,
               count(DISTINCT pre_user_id) AS actors
        FROM pre_user_events
        WHERE created_at >= :start AND created_at < :end
        GROUP BY 1 ORDER BY 2 DESC
        """,
        start=start,
        end=end,
    )
    if errored(rows):
        return rows
    for r in rows:
        if FUNNEL_EVENT_TYPES is None:
            r["kind"] = "UNKNOWN"
        else:
            r["kind"] = "funnel" if r["event_type"] in FUNNEL_EVENT_TYPES else "outreach"
    return rows


def section_amendator(conn, start, end, include_internal):
    """Amendments the user drafted, and alignment scores Brubru produced.

    These are two different things and must not be joined: `amendments` are the
    user's own drafts, while `amendment_alignment_scores` score MEP amendments
    (`mep_amendment_id`) against the user's policy position. There is no foreign
    key between them.
    """
    filt = "" if include_internal else f"AND NOT {INTERNAL_USER_SQL}"
    drafted = q(
        conn,
        f"""
        SELECT u.email, count(*) AS amendments,
               count(DISTINCT a.document_id) AS documents,
               count(*) FILTER (WHERE a.justification IS NULL OR a.justification = '') AS no_justification,
               count(DISTINCT a.procedure_reference) AS procedures
        FROM amendments a
        LEFT JOIN users u ON u.id = a.user_id
        WHERE a.created_at >= :start AND a.created_at < :end {filt}
        GROUP BY 1 ORDER BY 2 DESC
        """,
        start=start,
        end=end,
    )
    scored = q(
        conn,
        f"""
        SELECT u.email, count(*) AS mep_amendments_scored,
               count(DISTINCT s.procedure_reference) AS procedures,
               round(avg(s.score)::numeric, 1) AS avg_score,
               count(*) FILTER (WHERE s.explanation IS NULL OR s.explanation = '') AS no_explanation
        FROM amendment_alignment_scores s
        LEFT JOIN users u ON u.id = s.user_id
        WHERE s.scored_at >= :start AND s.scored_at < :end {filt}
        GROUP BY 1 ORDER BY 2 DESC
        """,
        start=start,
        end=end,
    )
    return {"drafted": drafted, "alignment": scored}


def section_comply(conn, start, end, include_internal):
    """Compliance runs + the quality of the answer Brubru gave back.

    A run that finishes with no score is a FAILED run, not a zero score -- the
    frontend guards against rendering it as 0% (compliance_report.tsx).
    """
    filt = "" if include_internal else f"AND NOT {INTERNAL_USER_SQL}"
    runs = q(
        conn,
        f"""
        SELECT u.email, a.id, a.analysis_name, a.status,
               a.total_requirements, a.compliance_score,
               a.requirements_met, a.requirements_partial, a.requirements_gap,
               a.created_at::date AS created
        FROM compliance_analyses a
        LEFT JOIN users u ON u.id = a.user_id
        WHERE a.created_at >= :start AND a.created_at < :end {filt}
        ORDER BY a.created_at DESC
        """,
        start=start,
        end=end,
    )
    findings = q(
        conn,
        """
        SELECT f.status, count(*) AS findings,
               round(avg(f.confidence_score)::numeric, 1) AS avg_confidence,
               count(*) FILTER (WHERE f.evidence_text IS NULL OR f.evidence_text = '') AS no_evidence,
               count(*) FILTER (WHERE f.confidence_score < 30) AS low_confidence
        FROM gap_findings f
        JOIN compliance_analyses a ON a.id = f.analysis_id
        WHERE f.created_at >= :start AND f.created_at < :end
        GROUP BY 1 ORDER BY 2 DESC
        """,
        start=start,
        end=end,
    )
    return {"runs": runs, "findings": findings}


def section_tenderator(conn, start, end, include_internal):
    """What users DID in Tenderator, not only what the matcher produced.

    Rewritten 11 September 2026. The previous version read `tender_matches`
    alone, which measures the matcher's OUTPUT and calls it usage. Three
    consequences, all of them measured that morning:

      - `tender_profiles` holds 29 profiles from 29 distinct users. Building a
        profile is a deliberate, effortful user action and it was invisible
        here, so the report said "none" while 29 people had set the tool up.
      - `tender_files` (11 rows, 4 users) and `tender_pipeline` were never read
        at all.
      - A user who ran Tenderator and got zero matches looked identical to a
        user who never opened it.

    Every engagement column on `tender_matches` -- is_viewed, is_saved,
    is_dismissed, is_applied, user_notes, user_rating, notified_at -- reads 0
    across all 902 matches ever created. That is NOT low engagement: grep finds
    ZERO assignments to `is_viewed` anywhere in api/ or services/, so no code
    path can set it. The reaction columns are reported here for continuity and
    must be read as "not instrumented", never as "nobody looked".
    """
    filt = "" if include_internal else f"AND NOT {INTERNAL_USER_SQL}"
    return {
        # Profiles: the setup action, and the one the report used to miss.
        "profiles": q(
            conn,
            f"""
            SELECT u.email, p.company_name, p.is_active,
                   cardinality(coalesce(p.cpv_codes, '{{}}')) AS cpv_codes,
                   cardinality(coalesce(p.countries_of_interest, '{{}}')) AS countries,
                   p.notification_frequency,
                   p.created_at::date AS created,
                   p.last_matched_at::date AS last_matched
            FROM tender_profiles p
            LEFT JOIN users u ON u.id = p.user_id
            WHERE p.created_at >= :start AND p.created_at < :end {filt}
            ORDER BY p.created_at DESC
            """,
            start=start, end=end,
        ),
        # Matches produced in the window, with the reaction columns.
        "matches": q(
            conn,
            f"""
            SELECT u.email, count(*) AS matches,
                   round(avg(m.match_score)::numeric, 1) AS avg_score,
                   count(*) FILTER (WHERE m.is_viewed) AS viewed,
                   count(*) FILTER (WHERE m.is_saved) AS saved,
                   count(*) FILTER (WHERE m.is_dismissed) AS dismissed,
                   count(*) FILTER (WHERE m.is_applied) AS applied,
                   count(*) FILTER (WHERE m.notified_at IS NOT NULL) AS notified
            FROM tender_matches m
            LEFT JOIN users u ON u.id = m.user_id
            WHERE m.created_at >= :start AND m.created_at < :end {filt}
            GROUP BY 1 ORDER BY 2 DESC
            """,
            start=start, end=end,
        ),
        # Tender files drafted, and pipeline rows worked.
        "files": q(
            conn,
            f"""
            SELECT u.email, f.programme, f.stage, f.status, count(*) AS files
            FROM tender_files f
            LEFT JOIN users u ON u.id = f.user_id
            WHERE f.created_at >= :start AND f.created_at < :end {filt}
            GROUP BY 1, 2, 3, 4 ORDER BY 5 DESC
            """,
            start=start, end=end,
        ),
        "pipeline": q(
            conn,
            f"""
            SELECT u.email, pl.status, count(*) AS rows_
            FROM tender_pipeline pl
            LEFT JOIN users u ON u.id = pl.user_id
            WHERE pl.created_at >= :start AND pl.created_at < :end {filt}
            GROUP BY 1, 2 ORDER BY 3 DESC
            """,
            start=start, end=end,
        ),
        # ALL-TIME health, so a quiet window cannot hide a stalled matcher.
        # This is the row that would have surfaced the 81-day stall on any day
        # since June, instead of reporting "unproven -- no data in window".
        "health": q(
            conn,
            """
            SELECT
              (SELECT count(*) FROM tender_profiles WHERE is_active) AS active_profiles,
              (SELECT count(*) FROM tenders) AS tenders_held,
              (SELECT max(created_at)::date FROM tenders) AS newest_tender,
              (SELECT max(created_at)::date FROM tender_matches) AS newest_match,
              (SELECT EXTRACT(DAY FROM now() - max(created_at))::int
                 FROM tender_matches) AS days_since_match,
              (SELECT count(*) FROM tender_matches) AS matches_all_time,
              (SELECT count(*) FROM tender_matches WHERE is_viewed) AS viewed_all_time,
              (SELECT count(*) FROM tender_matches WHERE notified_at IS NOT NULL) AS notified_all_time
            """,
        ),
    }


def section_documents(conn, start, end, include_internal):
    """Documents created or uploaded. `thin` = generated but near-empty."""
    filt = "" if include_internal else f"AND NOT {INTERNAL_USER_SQL}"
    return q(
        conn,
        f"""
        SELECT d.document_type, count(*) AS docs,
               count(DISTINCT d.user_id) AS actors,
               count(*) FILTER (WHERE d.content IS NULL OR length(d.content) < 200) AS thin,
               count(*) FILTER (WHERE d.include_in_ai_context) AS in_ai_context
        FROM user_documents d
        LEFT JOIN users u ON u.id = d.user_id
        WHERE d.created_at >= :start AND d.created_at < :end {filt}
        GROUP BY 1 ORDER BY 2 DESC
        """,
        start=start,
        end=end,
    )


def section_api(conn, start, end, include_internal):
    """API calls + what Brubru returned.

    NOTE: `status_code` is NULL on every row written by the current metering
    path, so an empty error column is NOT evidence of a healthy API. See the
    blind-spot section.
    """
    filt = "" if include_internal else f"AND NOT {INTERNAL_USER_SQL}"
    by_caller = q(
        conn,
        f"""
        SELECT u.email, count(*) AS calls,
               count(DISTINCT e.endpoint) AS endpoints,
               count(*) FILTER (WHERE e.status_code >= 400) AS errors,
               count(*) FILTER (WHERE e.status_code IS NULL) AS status_unrecorded,
               count(*) FILTER (WHERE e.is_sandbox) AS sandbox,
               count(*) FILTER (WHERE e.is_probe) AS probes,
               round(sum(e.cost_eur_micro) / 1000000.0, 4) AS eur
        FROM api_usage_events e
        LEFT JOIN users u ON u.id = e.user_id
        WHERE e.created_at >= :start AND e.created_at < :end {filt}
        GROUP BY 1 ORDER BY 2 DESC
        """,
        start=start,
        end=end,
    )
    by_endpoint = q(
        conn,
        f"""
        SELECT e.endpoint, count(*) AS calls,
               count(*) FILTER (WHERE e.status_code >= 400) AS errors
        FROM api_usage_events e
        LEFT JOIN users u ON u.id = e.user_id
        WHERE e.created_at >= :start AND e.created_at < :end {filt}
        GROUP BY 1 ORDER BY 2 DESC LIMIT 15
        """,
        start=start,
        end=end,
    )
    return {"by_caller": by_caller, "by_endpoint": by_endpoint}


# The six tables that carry `source` (migration 230). The other four tracking
# surfaces have no provenance column yet, so they report "n/a" rather than a
# blank -- a missing split must be visible, not silently read as "all user".
SOURCED_TRACK_TABLES = {
    "user_carriage_tracks",
    "user_commission_doc_tracks",
    "user_committee_work_tracks",
    "user_consultation_tracks",
    "user_text_adopted_tracks",
    "user_vote_tracks",
}

MEUB_TRACK_TABLES = [
    ("My Tracked Files", "user_carriage_tracks", "tracked_since"),
    ("Commission docs", "user_commission_doc_tracks", "tracked_since"),
    ("Committee work", "user_committee_work_tracks", "tracked_since"),
    ("Consultations", "user_consultation_tracks", "tracked_since"),
    ("Texts adopted", "user_text_adopted_tracks", "tracked_since"),
    # `user_vote_tracks` has created_at, not tracked_since, and
    # `user_feed_subscriptions` has subscribed_at, not created_at. Both were
    # wrong from the start, so both queries errored and both surfaces printed
    # "-" -- which reads as "nobody used it". 359 feed subscriptions were
    # invisible in every run before 10 Sep 2026. An empty output is never
    # absence: feedback_empty_result_is_a_broken_instrument.
    ("Votes", "user_vote_tracks", "created_at"),
    ("Calendar subs", "user_calendar_subscriptions", "created_at"),
    ("Saved entries", "user_saved_entries", "saved_at"),
    ("Feed subs", "user_feed_subscriptions", "subscribed_at"),
    ("Comparator grids", "comparator_grids", "created_at"),
]


def section_meub_tracking(conn, start, end, include_internal):
    """What users put under watch in My EU Bubble, SPLIT BY WHO PUT IT THERE.

    U2 (10 Sep 2026). A single `n` per surface is not reportable. On 10 September
    755 of 932 non-internal tracked items -- 81% -- turned out to be our own
    writes (dormant-claim provisioning and the Policy-Interest auto-populate),
    and reporting them as one number had already been read as engagement in at
    least two previous runs.

    Columns are three-state, never two:
      chosen       source='user'         the user picked this item
      provisnd     source='provisioned'  we wrote it on their behalf
      unknown      source IS NULL        written before migration 230

    `unknown` is NOT folded into `chosen`. That fold is the entire defect.
    """
    filt = "" if include_internal else f"AND NOT {INTERNAL_USER_SQL}"
    out = []
    for label, table, ts in MEUB_TRACK_TABLES:
        sourced = table in SOURCED_TRACK_TABLES
        split = (
            """,
                   count(*) FILTER (WHERE t.source = 'user') AS chosen,
                   count(*) FILTER (WHERE t.source = 'provisioned') AS provisnd,
                   count(*) FILTER (WHERE t.source IS NULL) AS unknown"""
            if sourced else ""
        )
        rows = q(
            conn,
            f"""
            SELECT count(*) AS n, count(DISTINCT t.user_id) AS actors{split}
            FROM {table} t
            LEFT JOIN users u ON u.id = t.user_id
            WHERE t.{ts} >= :start AND t.{ts} < :end {filt}
            """,
            start=start,
            end=end,
        )
        if errored(rows):
            out.append({"surface": label, "n": None, "actors": None,
                        "chosen": None, "provisnd": None, "unknown": None,
                        "note": rows[0]["__error__"]})
            continue
        row = {"surface": label, "n": rows[0]["n"], "actors": rows[0]["actors"]}
        if sourced:
            row.update(chosen=rows[0]["chosen"], provisnd=rows[0]["provisnd"],
                       unknown=rows[0]["unknown"])
        else:
            # No provenance column on this surface. Say so; never leave it blank.
            row.update(chosen="n/a", provisnd="n/a", unknown="n/a")
        out.append(row)
    return out


def section_tracking_provenance(conn, include_internal):
    """Corpus-level provenance of every tracked item. Deliberately ALL-TIME.

    Provenance is a property of the corpus, not of a window: a window with no
    tracking activity would print zeros and say nothing about the 932 rows that
    already exist. So this section ignores start/end, and says so in its header.

    For rows written before migration 230 (`source IS NULL`) the provenance is
    genuinely unknown, and it is NOT guessed here. A write-shape ESTIMATE is
    reported alongside, clearly labelled: an account whose entire tracking landed
    in <=2 distinct minutes was almost certainly bulk-written. That heuristic is
    decisive at 104-rows-in-one-minute and merely suggestive at 30, so it is
    printed as an estimate with its own rule stated, never merged into a count.
    """
    filt = "" if include_internal else f"AND NOT {INTERNAL_USER_SQL}"
    # All six sourced tables carry archived_at (verified against
    # information_schema, not assumed -- the first draft of this function
    # special-cased user_vote_tracks on the guess that it had none).
    union = "\n            UNION ALL\n            ".join(
        f"SELECT user_id, source, {ts} AS ts FROM {tbl} WHERE archived_at IS NULL"
        for _, tbl, ts in MEUB_TRACK_TABLES
        if tbl in SOURCED_TRACK_TABLES
    )

    totals = q(
        conn,
        f"""
        WITH t AS ({union})
        SELECT coalesce(t.source, 'unknown (pre-230)') AS provenance,
               count(*) AS items,
               count(DISTINCT t.user_id) AS holders
        FROM t LEFT JOIN users u ON u.id = t.user_id
        WHERE true {filt}
        GROUP BY 1 ORDER BY 2 DESC
        """,
    )

    # The write-shape estimate, over the UNKNOWN bucket only. Known rows need no
    # guessing, so guessing about them would only add noise.
    shape = q(
        conn,
        f"""
        WITH t AS ({union}),
        per_user AS (
            SELECT t.user_id,
                   count(*) AS items,
                   count(DISTINCT date_trunc('minute', t.ts)) AS write_minutes
            FROM t LEFT JOIN users u ON u.id = t.user_id
            WHERE t.source IS NULL {filt}
            GROUP BY 1
        )
        SELECT
            count(*) FILTER (WHERE write_minutes <= 2) AS bulk_holders,
            count(*) FILTER (WHERE write_minutes > 2) AS accrued_holders,
            coalesce(sum(items) FILTER (WHERE write_minutes <= 2), 0) AS bulk_items,
            coalesce(sum(items) FILTER (WHERE write_minutes > 2), 0) AS accrued_items
        FROM per_user
        """,
    )
    return {"totals": totals, "shape_estimate": shape}


def section_feedback(conn, start, end):
    """Explicit user voice: feedback submissions + whether we answered."""
    fb = q(
        conn,
        """
        SELECT f.feedback_type, f.status, f.title, f.affected_feature,
               (f.admin_response IS NOT NULL AND f.admin_response <> '') AS answered,
               f.created_at::date AS created
        FROM feedback_submissions f
        WHERE f.created_at >= :start AND f.created_at < :end
        ORDER BY f.created_at DESC
        """,
        start=start,
        end=end,
    )
    notif = q(
        conn,
        """
        SELECT notification_type, count(*) AS sent,
               count(*) FILTER (WHERE is_read) AS read
        FROM notifications
        WHERE created_at >= :start AND created_at < :end
        GROUP BY 1 ORDER BY 2 DESC
        """,
        start=start,
        end=end,
    )
    return {"feedback": fb, "notifications": notif}


def section_would_be_wapu(conn, end):
    """WAPU with the payment test removed, and nothing else changed.

    Added 11 September 2026. WAPU requires `stripe_subscription_id IS NOT NULL`
    -- tightened deliberately on 27 August after a pre-provisioned demo shell
    reported itself as a weekly active paid user. That guard is right and stays.

    But no account has EVER paid through Stripe, so WAPU reads 0 whatever anyone
    does, and on 11 September it read 0 on a week in which a client used the DPP
    MCP on three separate days. The north star cannot tell "nobody used Brubru"
    from "nobody pays by Stripe", and those demand opposite responses.

    This is a companion line, NOT a second north star. WAPU is untouched.

    The bulk-write marker matters as much as the count. WAPU's U1 guard drops
    actions that predate a claim, which caught provisioning written BEFORE the
    prospect claimed. It cannot catch the reverse: on 7 September a claim landed
    at 13:59 and the provisioning script wrote 104 tracked carriages at 14:00,
    one minute AFTER, so the guard passes them and the holder looks like the
    busiest user on the platform. `user_carriage_tracks.source` (migration 230)
    is the real fix and is not usable yet: all 722 rows read NULL, and nothing
    has been tracked since the column shipped on 10 September, so it is
    UNTESTED rather than broken. Until it carries data, the shape of the write
    is the only signal available -- an account whose entire tracking landed in
    one or two distinct minutes was written by us.
    """
    return q(
        conn,
        f"""
        WITH eligible AS (
            SELECT u.id, u.email, u.subscription_tier, u.claimed_at, u.pre_provisioned_at,
                   (u.stripe_subscription_id IS NOT NULL) AS pays
            FROM users u
            WHERE u.subscription_tier IN ('yellow', 'blue')
              AND u.is_active IS NOT FALSE
              AND NOT {INTERNAL_USER_SQL}
        ),
        acted AS (
            SELECT user_id, 'chat' AS action, created_at AS acted_at FROM chats
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'document', created_at FROM user_documents
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'tracked file', tracked_since FROM user_carriage_tracks
                WHERE tracked_since >= :start AND tracked_since < :end
            UNION ALL
            SELECT user_id, 'amendment', created_at FROM amendments
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'compliance run', created_at FROM compliance_analyses
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'api', created_at FROM api_usage_events
                WHERE created_at >= :start AND created_at < :end
                  AND NOT is_probe
        ),
        -- How many distinct MINUTES did this actor's tracking land in, ever?
        -- One or two means a script wrote it, not a person.
        track_shape AS (
            SELECT user_id,
                   count(DISTINCT date_trunc('minute', tracked_since)) AS distinct_minutes
            FROM user_carriage_tracks GROUP BY 1
        )
        SELECT e.email, e.subscription_tier,
               e.pays AS pays_stripe,
               count(a.action) AS actions,
               string_agg(DISTINCT a.action, ', ') AS surfaces,
               CASE
                 WHEN string_agg(DISTINCT a.action, ',') = 'tracked file'
                      AND coalesce(ts.distinct_minutes, 0) <= 2
                   THEN 'NOT engagement: tracking bulk-written by us'
                 ELSE ''
               END AS note
        FROM eligible e
        LEFT JOIN acted a
               ON a.user_id = e.id
              AND (e.pre_provisioned_at IS NULL
                   OR (e.claimed_at IS NOT NULL AND a.acted_at >= e.claimed_at))
        LEFT JOIN track_shape ts ON ts.user_id = e.id
        GROUP BY 1, 2, 3, ts.distinct_minutes
        HAVING count(a.action) > 0
        ORDER BY 4 DESC
        """,
        start=end - timedelta(days=7),
        end=end,
    )


def section_wapu(conn, end):
    """WAPU = paid subscriber + >=1 core action in the trailing 7 days.

    Core actions (memory/strategy.md): chat query, document generated, file
    tracked, amendment drafted, compliance run. API calls count too -- a paying
    integrator hitting /api/v2 is unambiguously active.

    Internal actors are always excluded here regardless of --include-internal:
    counting ourselves as a weekly active paid user would corrupt the north star.
    """
    return q(
        conn,
        f"""
        WITH paid AS (
            SELECT u.id, u.email, u.subscription_tier,
                   u.claimed_at, u.pre_provisioned_at,
                   -- U2 (27 Aug 2026): EVIDENCE of payment, not a tier string.
                   -- `subscription_tier` is set by the provisioning script as
                   -- readily as by Stripe, so a pre-provisioned demo shell
                   -- satisfied "paid subscriber" and reported itself as WAPU.
                   -- On 27 Aug all three blue rows carried stripe_customer_id
                   -- NULL and stripe_subscription_id NULL: nobody had paid us
                   -- anything, and the north star said 1.
                   (u.stripe_subscription_id IS NOT NULL) AS has_stripe_sub
            FROM users u
            WHERE u.subscription_tier IN ('yellow', 'blue')
              AND u.is_active IS NOT FALSE
              AND NOT {INTERNAL_USER_SQL}
        ),
        acted AS (
            SELECT user_id, 'chat' AS action, created_at AS acted_at FROM chats
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'document', created_at FROM user_documents
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'tracked file', tracked_since FROM user_carriage_tracks
                WHERE tracked_since >= :start AND tracked_since < :end
            UNION ALL
            SELECT user_id, 'amendment', created_at FROM amendments
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'compliance run', created_at FROM compliance_analyses
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'api', created_at FROM api_usage_events
                WHERE created_at >= :start AND created_at < :end
                  AND NOT is_probe   -- our own verification traffic is not a user action
        )
        SELECT p.email, p.subscription_tier,
               count(a.action) AS actions,
               string_agg(DISTINCT a.action, ', ') AS surfaces
        FROM paid p
        -- U1 (27 Aug 2026): a CLAIMED shell's history BEFORE the claim is OURS,
        -- not theirs. /dormant-claim writes a private-guide bundle into
        -- user_documents at provisioning time; when the prospect later claims
        -- the row, those writes became "their" actions retroactively. Xavier
        -- Arola's three credited document actions were written by the
        -- provisioning script at 13:42 on 25 Aug; he claimed at 08:49 on
        -- 26 Aug, nineteen hours later. The 14 Aug claim gate closed the
        -- unclaimed-shell hole and moved this one one step along.
        LEFT JOIN acted a
               ON a.user_id = p.id
              AND (p.pre_provisioned_at IS NULL
                   OR (p.claimed_at IS NOT NULL AND a.acted_at >= p.claimed_at))
        WHERE p.has_stripe_sub          -- U2: paid means paid
        GROUP BY 1, 2
        HAVING count(a.action) > 0
        ORDER BY 3 DESC
        """,
        start=end - timedelta(days=7),
        end=end,
    )


def section_blind_spots(conn, start, end):
    """Instrumentation checks. A silent recorder looks exactly like silence.

    Every check answers: 'if this surface were being used, would we see it?'
    A FAIL means today's zero is unproven, not proven.
    """
    checks = []

    # 1. chat_analytics must keep pace with chat_messages. The streaming path
    #    (/api/chat/stream) is the only route real users hit; if it does not
    #    write analytics, provider/latency/citation telemetry is fiction.
    rows = q(
        conn,
        """
        SELECT (SELECT max(created_at)::date FROM chat_messages) AS msgs_max,
               (SELECT max(created_at)::date FROM chat_analytics) AS analytics_max,
               (SELECT count(*) FROM chat_messages
                 WHERE created_at >= :start AND created_at < :end AND role = 'assistant') AS answers,
               (SELECT count(*) FROM chat_analytics
                 WHERE created_at >= :start AND created_at < :end) AS analytics_rows
        """,
        start=start,
        end=end,
    )
    if not errored(rows):
        r = rows[0]
        lag = None
        if r["msgs_max"] and r["analytics_max"]:
            lag = (r["msgs_max"] - r["analytics_max"]).days
        checks.append(
            {
                "check": "chat_analytics keeps pace with chat_messages",
                # Recency AND completeness. The old test was lag-only: it
                # printed "152 answers vs 102 analytics rows" in the detail and
                # ignored it in the verdict, so a third of the answers could go
                # unrecorded and the check still said OK (19 Aug 2026).
                "ok": bool(
                    lag is not None and lag <= 1
                    and (not r["answers"] or (r["analytics_rows"] / r["answers"]) >= 0.9)
                ),
                "unproven": not r["answers"],
                "detail": f"messages to {r['msgs_max']}, analytics to {r['analytics_max']} "
                f"(lag {lag}d); window: {r['answers']} answers vs {r['analytics_rows']} analytics rows",
                "means": "Either the analytics table lags by more than a day, or fewer "
                "than 90% of answers produced a row (the streaming path is the usual "
                "culprit -- it is the route real users hit). Provider mix, latency and "
                "citation counts are incomplete -- do not quote them.",
            }
        )

    # 1b. JOINABILITY. Recency and row counts say the table is being written;
    #     they say nothing about whether a row can be tied to the answer it
    #     describes. Until 11 September 2026 message_id and conversation_id
    #     were NULL on 100% of rows -- 217 of 217 in the week measured -- so
    #     chat_analytics held provider, latency and citation counts for answers
    #     nobody could identify, and the pace check above passed throughout.
    #
    #     Scoped to rows created AFTER the fix: every historic row is an orphan
    #     by construction and cannot be backfilled, so including them would
    #     leave this check failing forever and teach everyone to ignore it.
    rows = q(
        conn,
        """
        SELECT count(*) AS rows_since_fix,
               count(*) FILTER (WHERE a.message_id IS NOT NULL) AS have_msg_id,
               count(*) FILTER (WHERE m.id IS NOT NULL) AS msg_resolves,
               count(*) FILTER (WHERE a.conversation_id IS NOT NULL) AS have_conv_id,
               count(*) FILTER (WHERE c.id IS NOT NULL) AS conv_resolves
        FROM chat_analytics a
        LEFT JOIN chat_messages m ON m.id = a.message_id
        LEFT JOIN chats c ON c.id = a.conversation_id
        WHERE a.created_at >= TIMESTAMP '2026-09-11 12:00:00'
        """,
    )
    if not errored(rows):
        r = rows[0]
        n = r["rows_since_fix"] or 0
        resolves = r["msg_resolves"] or 0
        checks.append(
            {
                "check": "chat_analytics rows join to the answer they describe",
                # A row whose message_id does not resolve is not merely untidy:
                # it marks a generation that was measured and never persisted,
                # which is the 185-rows-vs-71-messages shape seen on 8 Sept.
                "ok": n == 0 or resolves == n,
                "unproven": n == 0,
                "detail": (
                    f"{n} rows since the fix, {r['have_msg_id']} carry a message_id, "
                    f"{resolves} resolve to a message, {r['conv_resolves']} resolve to a chat"
                ),
                "means": "A row that cannot be joined to its message cannot be used for "
                "per-query analysis: provider, latency and citation counts float free of "
                "the answer they measure. Rows that carry an id which does not resolve are "
                "generations that were measured but never saved; count them, do not hide them.",
            }
        )

    # 2. api_usage_events.status_code -- if always NULL, API health is unmeasured.
    rows = q(
        conn,
        """
        SELECT count(*) AS calls, count(status_code) AS with_status
        FROM api_usage_events WHERE created_at >= :start AND created_at < :end
        """,
        start=start,
        end=end,
    )
    if not errored(rows):
        r = rows[0]
        checks.append(
            {
                "check": "api_usage_events records status_code",
                # Coverage, not "ever non-null". The old test was
                # `calls == 0 or with_status > 0`, which ONE populated row out
                # of a million passed. On 19 Aug it returned OK while 43 of
                # 1,292 calls carried no status code at all.
                "ok": r["calls"] == 0 or (r["with_status"] / r["calls"]) >= 0.99,
                "unproven": r["calls"] == 0,
                "detail": f"{r['with_status']}/{r['calls']} calls carry a status_code",
                "means": "Under 99% coverage: the error rate is computed over calls whose "
                "outcome was never recorded, so a low count is partly an artefact. The "
                "metering path writes the row before the response is known.",
            }
        )

    # 3. pre_user_events must only carry event types the model declares valid;
    #    drift means the funnel chart silently misses steps. Imported rather
    #    than duplicated so the check cannot drift from the model it validates.
    try:
        from models.pre_user_event import VALID_EVENT_TYPES as valid
    except Exception as exc:  # noqa: BLE001
        # Report the breakage instead of dropping the check. Silently skipping
        # it is how a failing check disappears from the report and reads as
        # "nothing wrong here".
        checks.append({
            "check": "pre_user_events types match VALID_EVENT_TYPES",
            "ok": False,
            "detail": f"could not import the model: {type(exc).__name__}: {exc}",
            "means": "The check did not run. This is not a pass.",
        })
        valid = set()
    rows = q(
        conn,
        """
        SELECT DISTINCT event_type FROM pre_user_events
        WHERE created_at >= :start AND created_at < :end
        """,
        start=start,
        end=end,
    )
    if not errored(rows) and valid:
        seen = {r["event_type"] for r in rows}
        undeclared = sorted(seen - set(valid))
        checks.append(
            {
                "check": "pre_user_events types match VALID_EVENT_TYPES",
                "ok": not undeclared,
                "detail": f"undeclared: {undeclared or 'none'}",
                "means": "Undeclared types are written but not in the model's allow-list "
                "(models/pre_user_event.py) -- funnel code that switches on the "
                "declared set will drop them.",
            }
        )

    # 4. Tenderator: TWO checks, because the old single one could not fail.
    #
    # It asked "did matches created in this window reach a human", and marked
    # itself `unproven` whenever the window held no matches. From 22 June 2026
    # the matcher produced nothing at all, so every run for eighty-one days
    # reported "unproven -- no data in this window" and nobody learned that a
    # feature had stopped. A check that goes quiet exactly when the thing it
    # watches dies is not a check. [[feedback_zero_denominator_is_not_a_pass]]
    #
    # 4a. IS THE MATCHER STILL RUNNING AT ALL? Deliberately all-time, not
    #     windowed, so a quiet week cannot mask a dead scheduler.
    rows = q(
        conn,
        """
        SELECT (SELECT count(*) FROM tender_profiles WHERE is_active) AS active_profiles,
               (SELECT max(created_at)::date FROM tender_matches) AS newest_match,
               (SELECT EXTRACT(DAY FROM now() - max(created_at))::int
                  FROM tender_matches) AS days_since,
               (SELECT max(created_at)::date FROM tenders) AS newest_tender
        """,
    )
    if not errored(rows):
        r = rows[0]
        days = r["days_since"]
        profiles = r["active_profiles"] or 0
        # Only meaningful when somebody is actually waiting for a match.
        checks.append(
            {
                "check": "the tender matcher is still producing matches",
                "ok": profiles == 0 or (days is not None and days <= 14),
                "unproven": profiles == 0,
                "detail": (
                    f"{profiles} active profiles, newest match {r['newest_match']} "
                    f"({days} days ago), newest tender {r['newest_tender']}"
                ),
                "means": "Active profiles and fresh tenders but no recent match means the "
                "matcher is not running. It has NO scheduler: the only triggers are the "
                "admin-only POST /run-matching and POST /match, so it runs when somebody "
                "remembers. Same defect class as the notification scheduler.",
            }
        )

    # 4b. CAN a reaction even be recorded? Separate from whether one happened,
    #     because those are different failures with opposite fixes. Every
    #     engagement column reads 0 across all 902 matches ever created, and
    #     grep finds ZERO assignments to `is_viewed` in api/ or services/:
    #     the column cannot become true. Reporting that as "low engagement"
    #     would blame users for a missing writing path.
    rows = q(
        conn,
        """
        SELECT count(*) AS matches_all_time,
               count(*) FILTER (WHERE is_viewed) AS viewed,
               count(*) FILTER (WHERE is_saved OR is_dismissed OR is_applied) AS acted,
               count(*) FILTER (WHERE notified_at IS NOT NULL) AS notified
        FROM tender_matches
        """,
    )
    if not errored(rows):
        r = rows[0]
        total = r["matches_all_time"] or 0
        any_reaction = (r["viewed"] or 0) + (r["acted"] or 0) + (r["notified"] or 0)
        checks.append(
            {
                "check": "tender match reactions are instrumented",
                # A large history with not one reaction of any kind is evidence
                # about the CODE, not about the users.
                "ok": total == 0 or any_reaction > 0,
                "unproven": total == 0,
                "detail": (
                    f"{total} matches all time, {r['viewed']} viewed, "
                    f"{r['acted']} saved/dismissed/applied, {r['notified']} notified"
                ),
                "means": "Read this per column, not as one number -- the first version "
                "of this check said 'nothing writes these', which was true of is_viewed "
                "and WRONG of the rest. save_match() and dismiss_match() have written "
                "is_saved and is_dismissed since they were built, update_match() writes "
                "is_applied, user_notes and user_rating, and the Tenderator tab calls "
                "save and dismiss. Those zeros are genuine non-use. is_viewed had no "
                "writer at all until 11 Sep 2026 and is now set by POST "
                "/matches/{id}/view. notified_at has a writer but no scheduler: it fires "
                "only from an admin endpoint, the same defect the matcher had.",
            }
        )

    # 5. Notifications delivered but never opened.
    rows = q(
        conn,
        """
        SELECT count(*) AS sent, count(*) FILTER (WHERE is_read) AS read
        FROM notifications WHERE created_at >= :start AND created_at < :end
        """,
        start=start,
        end=end,
    )
    if not errored(rows):
        r = rows[0]
        checks.append(
            {
                "check": "notifications get read",
                "ok": r["sent"] == 0 or r["read"] > 0,
                "unproven": r["sent"] == 0,
                "detail": f"{r['sent']} sent, {r['read']} read",
                "means": "Sent but never read. The WRITING PATH IS INTACT, verified end "
                "to end on 11 Sep 2026: the bell calls markAsRead, the hook posts "
                "/notifications/{id}/read, and the model sets is_read AND read_at. A zero "
                "here is genuine non-use, not a missing writer -- do not repeat the 11 Sep "
                "error of reading one zero as a broken column. Until 10 Sep there was "
                "nothing recent to open: 103 notifications, one recipient, none since "
                "18 June.",
            }
        )

    # 6. Anonymous chats must carry a pre_user_id, otherwise they can never be
    #    joined to the funnel and activation is undercounted.
    rows = q(
        conn,
        f"""
        SELECT count(*) FILTER (WHERE c.pre_user_id IS NULL) AS orphaned,
               count(*) FILTER (WHERE c.pre_user_id IS NOT NULL) AS linked
        FROM chats c
        LEFT JOIN users u ON u.id = c.user_id
        WHERE u.id IS NULL AND c.created_at >= :start AND c.created_at < :end
          AND NOT {SYNTHETIC_PRE_USER_SQL}
        """,
        start=start,
        end=end,
    )
    if not errored(rows):
        r = rows[0]
        tot = (r["orphaned"] or 0) + (r["linked"] or 0)
        checks.append(
            {
                "check": "anonymous chats carry a pre_user_id",
                "ok": tot == 0 or r["orphaned"] == 0,
                "unproven": tot == 0,
                "detail": f"{r['orphaned']}/{tot} anonymous chats have no pre_user_id",
                "means": "Orphaned anonymous chats cannot be joined to pre_user_events, "
                "so query_1/2/3 undercount activation and the funnel looks worse "
                "than reality. Fix at the chat entry point, not in the funnel query.",
            }
        )

    # 7. Synthetic share of chat traffic.
    #
    # `marked` counts chats where the probe header was in play at all, whatever
    # its value. Without it this check certifies a false clean: on 13 Aug 2026 it
    # reported "0/7 (0.0%) are our own probes, 0 blind spots" while every one of
    # the seven was ours, because the probes carried well-formed UUIDs and sent
    # no header, so the shape heuristic matched nothing. A check that cannot see
    # probes must say so rather than pass. Same discipline as
    # feedback_null_propagation_and_silent_fallback_hide_failures: degrade to a
    # loud failure, never to a silent OK.
    rows = q(
        conn,
        f"""
        SELECT count(*) AS total,
               count(*) FILTER (WHERE {SYNTHETIC_PRE_USER_SQL}) AS synthetic,
               count(*) FILTER (WHERE c.chat_metadata ? 'is_probe') AS marked
        FROM chats c WHERE c.created_at >= :start AND c.created_at < :end
        """,
        start=start,
        end=end,
    )
    if not errored(rows):
        r = rows[0]
        total, marked = r["total"] or 0, r["marked"] or 0
        share = round(100.0 * r["synthetic"] / total, 1) if total else 0.0
        unverifiable = total > 0 and marked == 0
        if unverifiable:
            detail = (f"{r['synthetic']}/{total} chats ({share}%) matched the probe "
                      f"heuristic, but 0 chats carry the is_probe marker, so the "
                      f"share CANNOT BE VERIFIED")
            means = ("Probes that send `X-Brubru-Probe: 1` stamp chat_metadata.is_probe. "
                     "With no marked chat in the window, the only signal left is the "
                     "id-shape heuristic, which misses probes that use real UUIDs. Treat "
                     "this window's user counts as unproven and fix at the probe sender, "
                     "not here.")
        else:
            detail = f"{r['synthetic']}/{total} chats ({share}%) are our own probes"
            means = ("Above 50%: any unfiltered read of this table describes our "
                     "testing, not our users.")
        checks.append(
            {
                "check": "synthetic probe share of chat traffic",
                "ok": (total == 0) or (not unverifiable and share < 50.0),
                "unproven": total == 0,
                "detail": detail,
                "means": means,
            }
        )

    return checks


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------
def _fmt(rows, cols=None):
    if not rows:
        return "  (none)"
    if errored(rows):
        return f"  [WARN] query failed: {rows[0]['__error__']}"
    cols = cols or list(rows[0].keys())
    widths = {c: max(len(str(c)), *(len(str(r.get(c, ""))) for r in rows)) for c in cols}
    head = "  " + "  ".join(str(c).ljust(widths[c]) for c in cols)
    sep = "  " + "  ".join("-" * widths[c] for c in cols)
    body = [
        "  " + "  ".join(str(r.get(c, "") if r.get(c) is not None else "-").ljust(widths[c]) for c in cols)
        for r in rows
    ]
    return "\n".join([head, sep, *body])


def render(report):
    w = report["window"]
    out = [
        "=" * 78,
        f"BRUBRU USER ACTIVITY -- {w['start']} to {w['end']} ({w['days']}d)",
        f"internal/synthetic actors: {'INCLUDED' if w['include_internal'] else 'excluded'}",
        "=" * 78,
        "",
        f"-- 0. WAPU (paid + >=1 core action, trailing 7d to {w['end']}) ----------",
        f"  WAPU = {len(report['wapu']) if not errored(report['wapu']) else '?'}"
        "   (targets: 10 Phase A / 25 Phase B / 50 Phase C)",
        _fmt(report["wapu"]),
        # Companion line, not a second north star. WAPU above is untouched.
        # It requires evidence of payment and nobody has ever paid through
        # Stripe, so it reads 0 whatever anyone does. This says how many would
        # qualify on activity alone, which is the number that distinguishes
        # "nobody used Brubru" from "nobody pays us yet".
        f"  would-be WAPU = "
        f"{len(report['would_be_wapu']) if not errored(report['would_be_wapu']) else '?'}"
        "   (same test, payment evidence removed -- NOT the north star)",
        _fmt(report["would_be_wapu"],
             ["email", "subscription_tier", "pays_stripe", "actions", "surfaces", "note"]),
        "",
        "-- 1. ACTORS ------------------------------------------------------------",
        _fmt(report["actors"]["segments"]),
        "",
        "  New accounts:",
        _fmt(report["actors"]["signups"], ["email", "subscription_tier", "organization", "created", "last_login", "last_seen"]),
        "",
        "-- 2. CHAT (detail: /audit-queries) --------------------------------------",
        _fmt(report["chat"]),
        "",
        "-- 3. PRE-USER FUNNEL ----------------------------------------------------",
        _fmt(report["preuser_funnel"], ["kind", "event_type", "events", "actors"]),
        "",
        "-- 4. AMENDATOR ----------------------------------------------------------",
        "  Amendments drafted:",
        _fmt(report["amendator"]["drafted"]),
        "  MEP-amendment alignment scoring:",
        _fmt(report["amendator"]["alignment"]),
        "",
        "-- 5. EU LAW COMPLY ------------------------------------------------------",
        "  Runs:",
        _fmt(report["comply"]["runs"], ["email", "analysis_name", "status", "compliance_score",
                                        "total_requirements", "requirements_gap", "created"]),
        "  Findings quality:",
        _fmt(report["comply"]["findings"]),
        "",
        "-- 6. TENDERATOR ---------------------------------------------------------",
        "  Profiles built (the setup action):",
        _fmt(report["tenderator"]["profiles"]),
        "  Matches produced (reaction columns are NOT instrumented -- see below):",
        _fmt(report["tenderator"]["matches"]),
        "  Tender files drafted:",
        _fmt(report["tenderator"]["files"]),
        "  Pipeline rows:",
        _fmt(report["tenderator"]["pipeline"]),
        "  All-time health (a quiet window cannot hide a stalled matcher):",
        _fmt(report["tenderator"]["health"]),
        "",
        "-- 7. DOCUMENTS ----------------------------------------------------------",
        _fmt(report["documents"]),
        "",
        "-- 8. API ----------------------------------------------------------------",
        "  By caller:",
        _fmt(report["api"]["by_caller"]),
        "  By endpoint:",
        _fmt(report["api"]["by_endpoint"]),
        "",
        "-- 9. MY EU BUBBLE TRACKING ----------------------------------------------",
        "  (in window; chosen = the user picked it, provisnd = we wrote it,",
        "   unknown = pre-migration-230 rows whose provenance is not recorded)",
        _fmt(report["meub"], ["surface", "n", "actors", "chosen", "provisnd", "unknown"]),
        "",
        "-- 9b. TRACKING PROVENANCE (ALL TIME, not the window) ---------------------",
        _fmt(report["tracking_provenance"]["totals"], ["provenance", "items", "holders"]),
        "",
        "  Write-shape ESTIMATE for the `unknown` bucket only -- a guess, not a count.",
        "  Rule: an account whose entire tracking landed in <=2 distinct minutes was",
        "  bulk-written by us. Decisive at 104-rows-in-one-minute, only suggestive at 30.",
        _fmt(report["tracking_provenance"]["shape_estimate"]),
        "",
        "-- 10. FEEDBACK + NOTIFICATIONS ------------------------------------------",
        _fmt(report["feedback"]["feedback"], ["created", "feedback_type", "affected_feature", "status", "answered", "title"]),
        "",
        _fmt(report["feedback"]["notifications"]),
        "",
        "-- 11. INSTRUMENTATION BLIND SPOTS ---------------------------------------",
    ]
    # Three states, not two. A check whose denominator is zero has not passed:
    # it has not run. Printing that as [OK] is how a 3-day window reported six
    # verified instruments on 19 Aug 2026 when five of them had no data at all
    # -- and the same instrument that read [OK] over 3 days read [FAIL] over 14
    # (20 of 54 anonymous chats orphaned). Same code, same morning, opposite
    # verdicts, purely because of window size.
    for c in report["blind_spots"]:
        if c.get("unproven"):
            label = "----"
        elif c["ok"]:
            label = " OK "
        else:
            label = "FAIL"
        out.append(f"  [{label}] {c['check']}")
        out.append(f"         {c['detail']}")
        if c.get("unproven"):
            out.append("         -> NOT PROVEN: no data in this window. Widen the window "
                       "before reading this as healthy.")
        elif not c["ok"]:
            out.append(f"         -> {c['means']}")
    out.append("")
    fails = [c for c in report["blind_spots"] if not c["ok"] and not c.get("unproven")]
    unproven = [c for c in report["blind_spots"] if c.get("unproven")]
    line = f"  {len(fails)} blind spot(s) -- treat any zero on those surfaces as UNPROVEN."
    if unproven:
        line += f"\n  {len(unproven)} check(s) UNPROVEN (no data in window) -- not the same as passing."
    out.append(line)
    out.append("")
    return "\n".join(out)


def main():
    p = argparse.ArgumentParser(description="What users did in Brubru and how Brubru answered.")
    p.add_argument("--days", type=int, help="Window size ending today (default 1).")
    p.add_argument("--since", help="Start date YYYY-MM-DD (inclusive).")
    p.add_argument("--until", help="End date YYYY-MM-DD (inclusive).")
    p.add_argument("--include-internal", action="store_true",
                   help="Include admin/trainer/test/demo actors and our own probes.")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = p.parse_args()

    if args.until and not args.since and not args.days:
        sys.exit("[ERROR] --until needs either --since or --days to fix the window start")
    end_incl = datetime.fromisoformat(args.until).date() if args.until else date.today()
    if args.since:
        start = datetime.fromisoformat(args.since).date()
    else:
        start = end_incl - timedelta(days=(args.days or 1) - 1)
    if start > end_incl:
        sys.exit(f"[ERROR] window start {start} is after end {end_incl}")
    end_excl = end_incl + timedelta(days=1)
    days = (end_incl - start).days + 1

    engine = _engine()
    with engine.connect() as conn:
        report = {
            "window": {
                "start": str(start),
                "end": str(end_incl),
                "days": days,
                "include_internal": args.include_internal,
            },
            "wapu": section_wapu(conn, end_excl),
            "would_be_wapu": section_would_be_wapu(conn, end_excl),
            "actors": section_actors(conn, start, end_excl, args.include_internal),
            "chat": section_chat(conn, start, end_excl, args.include_internal),
            "preuser_funnel": section_preuser_funnel(conn, start, end_excl),
            "amendator": section_amendator(conn, start, end_excl, args.include_internal),
            "comply": section_comply(conn, start, end_excl, args.include_internal),
            "tenderator": section_tenderator(conn, start, end_excl, args.include_internal),
            "documents": section_documents(conn, start, end_excl, args.include_internal),
            "api": section_api(conn, start, end_excl, args.include_internal),
            "meub": section_meub_tracking(conn, start, end_excl, args.include_internal),
            "tracking_provenance": section_tracking_provenance(conn, args.include_internal),
            "feedback": section_feedback(conn, start, end_excl),
            "blind_spots": section_blind_spots(conn, start, end_excl),
        }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(render(report))


if __name__ == "__main__":
    main()
