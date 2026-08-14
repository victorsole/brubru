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
        OR (u.pre_provisioned_at IS NOT NULL AND u.claimed_at IS NULL)
        OR u.email IS NULL OR u.email = ''
        OR u.email ILIKE '%beresol%'
        OR u.email ILIKE '%@example.com'
        OR u.email ILIKE '%demo.invalid'
        OR u.email ILIKE '%@brubru.dev'
        OR u.email ILIKE 'test%'
        OR u.email ILIKE 'prospect+%'
        OR u.email ILIKE 'v2_%'
        OR u.email ILIKE 'v2sec_%'
    )
"""

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
        WHEN {INTERNAL_USER_SQL} THEN 'internal'
        WHEN u.subscription_tier IN ('yellow', 'blue') THEN 'subscriber'
        ELSE 'free'
    END
"""

REAL_SEGMENTS = ("pre-user", "subscriber", "free")


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
    """Matches Brubru computed vs whether any human reacted to them.

    Reactions are cumulative flags, not timestamped, so the reaction counts are
    all-time for matches created in the window. Zero across the board means the
    matcher is talking to nobody.
    """
    filt = "" if include_internal else f"AND NOT {INTERNAL_USER_SQL}"
    return q(
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
        start=start,
        end=end,
    )


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


def section_meub_tracking(conn, start, end, include_internal):
    """What users put under watch in My EU Bubble."""
    filt = "" if include_internal else f"AND NOT {INTERNAL_USER_SQL}"
    tables = [
        ("My Tracked Files", "user_carriage_tracks", "tracked_since"),
        ("Commission docs", "user_commission_doc_tracks", "tracked_since"),
        ("Committee work", "user_committee_work_tracks", "tracked_since"),
        ("Consultations", "user_consultation_tracks", "tracked_since"),
        ("Texts adopted", "user_text_adopted_tracks", "tracked_since"),
        ("Votes", "user_vote_tracks", "tracked_since"),
        ("Calendar subs", "user_calendar_subscriptions", "created_at"),
        ("Saved entries", "user_saved_entries", "saved_at"),
        ("Feed subs", "user_feed_subscriptions", "created_at"),
        ("Comparator grids", "comparator_grids", "created_at"),
    ]
    out = []
    for label, table, ts in tables:
        rows = q(
            conn,
            f"""
            SELECT count(*) AS n, count(DISTINCT t.user_id) AS actors
            FROM {table} t
            LEFT JOIN users u ON u.id = t.user_id
            WHERE t.{ts} >= :start AND t.{ts} < :end {filt}
            """,
            start=start,
            end=end,
        )
        if errored(rows):
            out.append({"surface": label, "n": None, "actors": None, "note": rows[0]["__error__"]})
        else:
            out.append({"surface": label, "n": rows[0]["n"], "actors": rows[0]["actors"]})
    return out


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
            SELECT u.id, u.email, u.subscription_tier
            FROM users u
            WHERE u.subscription_tier IN ('yellow', 'blue')
              AND u.is_active IS NOT FALSE
              AND NOT {INTERNAL_USER_SQL}
        ),
        acted AS (
            SELECT user_id, 'chat' AS action FROM chats
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'document' FROM user_documents
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'tracked file' FROM user_carriage_tracks
                WHERE tracked_since >= :start AND tracked_since < :end
            UNION ALL
            SELECT user_id, 'amendment' FROM amendments
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'compliance run' FROM compliance_analyses
                WHERE created_at >= :start AND created_at < :end
            UNION ALL
            SELECT user_id, 'api' FROM api_usage_events
                WHERE created_at >= :start AND created_at < :end
        )
        SELECT p.email, p.subscription_tier,
               count(a.action) AS actions,
               string_agg(DISTINCT a.action, ', ') AS surfaces
        FROM paid p
        LEFT JOIN acted a ON a.user_id = p.id
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
                "ok": bool(lag is not None and lag <= 1),
                "detail": f"messages to {r['msgs_max']}, analytics to {r['analytics_max']} "
                f"(lag {lag}d); window: {r['answers']} answers vs {r['analytics_rows']} analytics rows",
                "means": "Lag > 1d: the streaming path is not writing analytics. "
                "Provider mix, latency and citation counts are stale -- do not quote them.",
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
                "ok": r["calls"] == 0 or r["with_status"] > 0,
                "detail": f"{r['with_status']}/{r['calls']} calls carry a status_code",
                "means": "All NULL: zero errors is an artefact of not recording them. "
                "The metering path writes the row before the response is known.",
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

    # 4. Tenderator: matches computed but never surfaced to a human.
    rows = q(
        conn,
        """
        SELECT count(*) AS matches,
               count(*) FILTER (WHERE is_viewed) AS viewed,
               count(*) FILTER (WHERE notified_at IS NOT NULL) AS notified
        FROM tender_matches WHERE created_at >= :start AND created_at < :end
        """,
        start=start,
        end=end,
    )
    if not errored(rows):
        r = rows[0]
        checks.append(
            {
                "check": "tender matches reach a human",
                "ok": r["matches"] == 0 or r["viewed"] > 0 or r["notified"] > 0,
                "detail": f"{r['matches']} matches, {r['viewed']} viewed, {r['notified']} notified",
                "means": "Matches with no views and no notifications: compute is running "
                "into a void. Either the digest is not sending or the tab is not wired.",
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
                "detail": f"{r['sent']} sent, {r['read']} read",
                "means": "Sent but never read: check the bell renders and that is_read "
                "is actually persisted on open.",
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
        "",
        "-- 1. ACTORS ------------------------------------------------------------",
        _fmt(report["actors"]["segments"]),
        "",
        "  New accounts:",
        _fmt(report["actors"]["signups"], ["email", "subscription_tier", "organization", "created", "last_login"]),
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
        _fmt(report["tenderator"]),
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
        _fmt(report["meub"], ["surface", "n", "actors"]),
        "",
        "-- 10. FEEDBACK + NOTIFICATIONS ------------------------------------------",
        _fmt(report["feedback"]["feedback"], ["created", "feedback_type", "affected_feature", "status", "answered", "title"]),
        "",
        _fmt(report["feedback"]["notifications"]),
        "",
        "-- 11. INSTRUMENTATION BLIND SPOTS ---------------------------------------",
    ]
    for c in report["blind_spots"]:
        out.append(f"  [{'OK' if c['ok'] else 'FAIL'}] {c['check']}")
        out.append(f"         {c['detail']}")
        if not c["ok"]:
            out.append(f"         -> {c['means']}")
    out.append("")
    fails = [c for c in report["blind_spots"] if not c["ok"]]
    out.append(f"  {len(fails)} blind spot(s) -- treat any zero on those surfaces as UNPROVEN.")
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
            "actors": section_actors(conn, start, end_excl, args.include_internal),
            "chat": section_chat(conn, start, end_excl, args.include_internal),
            "preuser_funnel": section_preuser_funnel(conn, start, end_excl),
            "amendator": section_amendator(conn, start, end_excl, args.include_internal),
            "comply": section_comply(conn, start, end_excl, args.include_internal),
            "tenderator": section_tenderator(conn, start, end_excl, args.include_internal),
            "documents": section_documents(conn, start, end_excl, args.include_internal),
            "api": section_api(conn, start, end_excl, args.include_internal),
            "meub": section_meub_tracking(conn, start, end_excl, args.include_internal),
            "feedback": section_feedback(conn, start, end_excl),
            "blind_spots": section_blind_spots(conn, start, end_excl),
        }

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(render(report))


if __name__ == "__main__":
    main()
