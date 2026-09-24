"""Deliver in-app notifications by email: one summary per user.

WHY THIS EXISTS (24 September 2026)
-----------------------------------
Every notification Brubru creates -- carriage status changes, tender digests --
was in-app only. Nothing in the pipeline sent an email. In the week to 24 Sep,
42 status_change notifications reached 13 real recipients (EFPIA, GBSB,
Terraqui...) and 0 were read: the writing path works, nobody opens the bell. A
tracked file that moves and a tender that matches are promises of being told,
and the bell alone does not keep them.

GATED, OFF BY DEFAULT
---------------------
An email to a client is an outward-facing send, so the channel only sends when
NOTIFICATION_EMAIL_ENABLED=true. Otherwise it renders every email, reports who
WOULD receive what, and stamps nothing, so switching it on later delivers the
backlog of the last `window_days` once. NOTIFICATION_EMAIL_ONLY (comma-separated
addresses) restricts delivery to named recipients for a staged rollout.

Each notification is emailed at most once (`notifications.emailed_at`,
migration 239), and only unread ones are included: a notification the user has
already seen in the app is not repeated by email.
"""
from __future__ import annotations

import html
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

APP_URL = "https://brubru.beresol.eu"

# Notification types the channel carries, with the heading each one gets.
EMAIL_TYPES = {
    "status_change": "Your tracked files",
    "tender_digest": "Tender matches",
}
# Tender types honour the Tenderator profile's own email switch.
TENDER_TYPES = {"tender_digest"}

# Synthetic and reserved recipients never receive email: pre-provisioned
# prospects, demo rows and RFC 2606 domains.
_SYNTHETIC_SUFFIXES = ("@brubru.beresol.eu", "@example.com", "@example.org",
                       ".invalid", ".test", ".example", "@brubru.dev")


@dataclass
class Item:
    notification_id: str
    notification_type: str
    title: str
    message: str
    action_url: Optional[str]
    created_at: datetime


@dataclass
class Recipient:
    user_id: str
    email: str
    name: Optional[str]
    items: List[Item] = field(default_factory=list)


@dataclass
class RunSummary:
    enabled: bool
    recipients: int = 0
    items: int = 0
    emails_sent: int = 0
    send_failures: int = 0
    skipped_synthetic: int = 0
    skipped_not_allowed: int = 0
    skipped_tender_optout: int = 0
    would_send: List[str] = field(default_factory=list)

    def line(self) -> str:
        mode = "SENT" if self.enabled else "CHANNEL DISABLED (NOTIFICATION_EMAIL_ENABLED is not true)"
        return (f"{mode}: recipients={self.recipients} items={self.items} "
                f"emails_sent={self.emails_sent} failures={self.send_failures} "
                f"skipped_synthetic={self.skipped_synthetic} "
                f"skipped_not_allowed={self.skipped_not_allowed} "
                f"skipped_tender_optout={self.skipped_tender_optout}")


def channel_enabled() -> bool:
    return os.getenv("NOTIFICATION_EMAIL_ENABLED", "false").strip().lower() == "true"


def allowlist() -> Optional[set]:
    raw = os.getenv("NOTIFICATION_EMAIL_ONLY", "").strip()
    return {a.strip().lower() for a in raw.split(",") if a.strip()} or None


def is_synthetic(email: str) -> bool:
    e = (email or "").strip().lower()
    return not e or "@" not in e or e.endswith(_SYNTHETIC_SUFFIXES) or e.startswith("prospect+")


def render(recipient: Recipient) -> tuple[str, str, str]:
    """(subject, html, text). British English, no em-dashes, plain layout."""
    n = len(recipient.items)
    subject = f"Brubru: {n} update{'s' if n != 1 else ''} since your last visit"
    greeting = f"Hello {recipient.name}," if recipient.name else "Hello,"
    groups: Dict[str, List[Item]] = {}
    for it in sorted(recipient.items, key=lambda i: i.created_at, reverse=True):
        groups.setdefault(it.notification_type, []).append(it)

    html_parts = [f"<p>{html.escape(greeting)}</p>",
                  "<p>Here is what moved on the files and tenders you follow in Brubru.</p>"]
    text_parts = [greeting, "", "Here is what moved on the files and tenders you follow in Brubru.", ""]
    for ntype, items in groups.items():
        heading = EMAIL_TYPES.get(ntype, "Updates")
        html_parts.append(f"<h3 style=\"margin:18px 0 6px\">{html.escape(heading)}</h3><ul>")
        text_parts.append(heading.upper())
        for it in items:
            url = f"{APP_URL}{it.action_url}" if it.action_url and it.action_url.startswith("/") else (it.action_url or APP_URL)
            html_parts.append(
                f"<li style=\"margin-bottom:8px\"><a href=\"{html.escape(url)}\">{html.escape(it.title)}</a>"
                f"<br><span style=\"color:#555\">{html.escape(it.message)}</span></li>")
            text_parts += [f"- {it.title}", f"  {it.message}", f"  {url}"]
        html_parts.append("</ul>")
        text_parts.append("")
    footer = ("You receive this because you asked Brubru to notify you about these files or tenders. "
              "To stop these emails, reply to hello@beresol.eu.")
    html_parts.append(f"<p style=\"color:#777;font-size:12px;margin-top:24px\">{html.escape(footer)}</p>")
    text_parts.append(footer)
    return subject, "\n".join(html_parts), "\n".join(text_parts)


def collect(db, window_days: int = 7) -> List[Recipient]:
    """Unread, un-emailed notifications of a carried type, grouped per user."""
    from sqlalchemy import text

    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    rows = db.execute(text("""
        SELECT n.id::text AS nid, n.user_id::text AS uid, n.notification_type AS t,
               n.title, n.message, n.action_url, n.created_at,
               u.email, u.full_name,
               COALESCE(tp.notification_email, false) AS tender_email
          FROM notifications n
          JOIN users u ON u.id = n.user_id
          LEFT JOIN tender_profiles tp ON tp.user_id = n.user_id AND tp.is_active
         WHERE n.emailed_at IS NULL
           AND n.is_read = false
           AND n.created_at >= :since
           AND n.notification_type = ANY(:types)
         ORDER BY n.user_id, n.created_at
    """), {"since": since, "types": list(EMAIL_TYPES)}).mappings().all()

    by_user: Dict[str, Recipient] = {}
    for r in rows:
        rec = by_user.setdefault(r["uid"], Recipient(r["uid"], r["email"] or "", r["full_name"]))
        if r["t"] in TENDER_TYPES and not r["tender_email"]:
            rec.items.append(Item(r["nid"], "__tender_optout__", r["title"], r["message"],
                                  r["action_url"], r["created_at"]))
            continue
        rec.items.append(Item(r["nid"], r["t"], r["title"], r["message"], r["action_url"], r["created_at"]))
    return list(by_user.values())


def run(db, *, enabled: Optional[bool] = None, only: Optional[set] = None,
        send: Optional[Callable[[str, str, str, str], bool]] = None,
        window_days: int = 7) -> RunSummary:
    """Send (or, when disabled, report) one summary email per user."""
    from sqlalchemy import text

    enabled = channel_enabled() if enabled is None else enabled
    only = allowlist() if only is None else only
    if send is None:
        from services.email_service import EmailService
        svc = EmailService()
        send = lambda to, subj, h, t: svc.send(to=to, subject=subj, html_body=h, text_body=t)  # noqa: E731

    summary = RunSummary(enabled=enabled)
    for rec in collect(db, window_days=window_days):
        optout = [i for i in rec.items if i.notification_type == "__tender_optout__"]
        summary.skipped_tender_optout += len(optout)
        rec.items = [i for i in rec.items if i.notification_type != "__tender_optout__"]
        if not rec.items:
            continue
        if is_synthetic(rec.email):
            summary.skipped_synthetic += 1
            continue
        if only is not None and rec.email.lower() not in only:
            summary.skipped_not_allowed += 1
            continue
        summary.recipients += 1
        summary.items += len(rec.items)
        subject, html_body, text_body = render(rec)
        if not enabled:
            summary.would_send.append(f"{rec.email}: {len(rec.items)} item(s)")
            continue
        ok = False
        try:
            ok = bool(send(rec.email, subject, html_body, text_body))
        except Exception:  # noqa: BLE001 -- one recipient must not stop the rest
            ok = False
        if not ok:
            summary.send_failures += 1
            continue
        # Count what was persisted: stamp only after a confirmed send.
        db.execute(text("UPDATE notifications SET emailed_at = now() WHERE id = ANY(CAST(:ids AS uuid[]))"),
                   {"ids": [i.notification_id for i in rec.items]})
        db.commit()
        summary.emails_sent += 1
    return summary
