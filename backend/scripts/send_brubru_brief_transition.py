"""
One-off transition issue for the new Brubru Brief format.
Monday 11 May 2026 launch.

Subject: Brubru Brief: What nobody else tells you about the EU Bubble - Monday 11 May 2026

New positioning: institutional content NOT covered by mainstream press
(Politico, Euractiv, Euronews, FT, Bloomberg, Reuters).

After today, this script is single-use. The /daily-brief skill + curator
will be rewritten to enforce no-overlap filter + variable cadence.

Hard rules applied in this issue:
- No em-dashes (use commas / periods / colons / semicolons)
- No emojis
- No institutional codes in headlines / snippets / Ask Brubru queries
  (per the 7 May 2026 rule: COM/COD/INI/CELEX/A-/PE-/T-/IP-/Reg/Dir numbers
   never appear in newsletter hero text)

Usage:
    python3.12 scripts/send_brubru_brief_transition.py --test   # to hello@beresol.eu
    python3.12 scripts/send_brubru_brief_transition.py --send   # to all subscribers via SMTP-BCC
"""
import argparse
import os
import smtplib
import sys
import time
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

_project_root = Path(__file__).resolve().parents[2]
_env_path = _project_root / ".env"
load_dotenv(_env_path)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from core.database import SessionLocal
from services.daily_brief_email import _get_all_recipient_emails
from services.email_service import EmailService


# Each headline maps to one or more EUTR policy_cluster values. Used to
# narrow the EUTR org pool to only those whose policy area matches at
# least one of today's headlines.
HEADLINE_CLUSTERS = {
    "mobility_package": ["transport"],
    "afco_article_19": ["civil_society"],
    "ets_review": ["climate", "energy"],
    "ehds_dialogue": ["health"],
    "russia_sanctions": ["defence", "trade", "transport"],
}


def _all_clusters_today() -> list:
    s = set()
    for clusters in HEADLINE_CLUSTERS.values():
        s.update(clusters)
    return sorted(s)


def _fetch_eutr_matched_emails(db_session, exclude_emails: set) -> list:
    """Return (email, name, country, policy_cluster) tuples for EUTR orgs
    whose policy_cluster matches one of today's headline clusters.

    Excludes:
      - bounced status
      - any email already in exclude_emails (e.g. base subscribers, dedup)
      - any email that received a Brubru Brief via this channel in the
        last 7 days (rotation block via pre_user_events)
    """
    clusters = _all_clusters_today()
    query = text("""
        SELECT
          o.contact_email AS email,
          o.name,
          o.country,
          o.policy_cluster
        FROM transparency_register_orgs o
        WHERE o.contact_email IS NOT NULL
          AND o.outreach_status NOT IN ('bounced', 'unsubscribed')
          AND o.policy_cluster = ANY(:clusters)
          AND NOT EXISTS (
            SELECT 1 FROM pre_user_events e
            WHERE e.event_type = 'send_brubru_brief_eutr'
              AND LOWER(e.event_metadata->>'email') = LOWER(o.contact_email)
              AND e.created_at >= NOW() - INTERVAL '7 days'
          )
          AND NOT EXISTS (
            SELECT 1 FROM pre_user_events u
            WHERE u.event_type IN ('daily_brief_unsubscribe', 'unsubscribe')
              AND LOWER(u.event_metadata->>'email') = LOWER(o.contact_email)
          )
    """)
    rows = db_session.execute(query, {"clusters": clusters}).fetchall()
    out = []
    seen = set()
    for r in rows:
        email = (r.email or "").strip().lower()
        if not email or email in exclude_emails or email in seen:
            continue
        seen.add(email)
        out.append((email, r.name, r.country, r.policy_cluster))
    return out


def _log_eutr_send(db_session, email: str, org_name: str, policy_cluster: str):
    """Log a Brubru Brief send to an EUTR org for rotation + audit."""
    import uuid as _uuid
    from datetime import datetime as _dt
    db_session.execute(
        text("""
            INSERT INTO pre_user_events (id, pre_user_id, event_type, ab_variant, event_metadata, created_at)
            VALUES (:id, :pre_user_id, 'send_brubru_brief_eutr', 'A', CAST(:metadata AS jsonb), :ts)
        """),
        {
            "id": str(_uuid.uuid4()),
            "pre_user_id": str(_uuid.uuid4()),
            "metadata": '{{"email": "{e}", "org_name": "{o}", "policy_cluster": "{c}", "issue": "transition_2026-05-11"}}'.format(
                e=email.replace('"', ''),
                o=(org_name or '').replace('"', ''),
                c=(policy_cluster or '').replace('"', ''),
            ),
            "ts": _dt.utcnow(),
        }
    )


SUBJECT = "Brubru Brief: What nobody else tells you about the EU Bubble - Monday 11 May 2026"

BRUBRU_CHAT = "https://brubru.beresol.eu/main"

HEADLINES = [
    {
        "title": "The EU Commission adopts the Mobility Package on Wednesday 13 May",
        "source": "Commission tentative agenda",
        "snippet": (
            "The College tentative agenda confirms Vice-President Fitto tables three "
            "regulations on Wednesday: Multimodal Digital Mobility Services, Single "
            "Digital Booking and Ticketing, and a revision of rail passengers' rights. "
            "Mainstream press will not cover this until adoption day. You have a "
            "48-hour head start."
        ),
        "ask": "What is in the Mobility Package the Commission adopts on Wednesday 13 May?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#0693e3",
    },
    {
        "title": "AFCO tabled six draft reports on Monday, one rewrites the EU's national-courts relationship",
        "source": "AFCO committee portal",
        "snippet": (
            "The EP Constitutional Affairs committee filed six new draft reports "
            "today. The central one revisits the EU's institutional framework and "
            "Article 19 TEU, the treaty article that requires national courts to "
            "provide remedies under Union law. AFCO is also revisiting Rule 135 on "
            "agency appointments and tabling three new own-initiative reports. No "
            "press coverage anywhere."
        ),
        "ask": "What is AFCO doing on the EU institutional framework and Article 19 TEU?",
        "feature_label": "My Files",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=files",
        "color": "#9b51e0",
    },
    {
        "title": "The EU ETS Review starts tomorrow with the Commission's first stakeholder roundtable",
        "source": "EU Calendar",
        "snippet": (
            "President von der Leyen announced the ETS Review initiative at the "
            "March European Council. Tomorrow Tuesday 12 May, the Commission hosts "
            "the first High-Level Stakeholder Roundtable in Brussels. Industry, "
            "civil society, and Member State representatives feed into the "
            "legislative proposal expected late this year. Topics include price "
            "stability mechanisms after 2030, free-allocation phase-out, ETS2 "
            "preparation, and the interaction with the Carbon Border Adjustment "
            "Mechanism."
        ),
        "ask": "What is the EU ETS Review and what is being discussed at the Tuesday 12 May High-Level Roundtable?",
        "feature_label": "My EU Calendar",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=calendar",
        "color": "#059669",
    },
    {
        "title": "Commissioner Varhelyi hosts the first European Health Data Space implementation dialogue tomorrow",
        "source": "DG SANTE",
        "snippet": (
            "Tuesday 12 May: DG SANTE convenes the first formal implementation "
            "dialogue under the European Health Data Space regulation. Health data "
            "access bodies, hospital systems, research organisations, patient "
            "federations, and commercial operators are in scope. Topics include "
            "MyHealth@EU rollout, HealthData@EU secondary-use procedures, "
            "secondary-use price ceilings, and interoperability standards. EHDS "
            "applies from March next year. Tomorrow sets the pace."
        ),
        "ask": "What is the European Health Data Space and how is it being implemented?",
        "feature_label": "Predictions",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=predictions",
        "color": "#d97706",
    },
    {
        "title": "The next EU sanctions package targets Russia's shadow fleet, and an Information Note on dual-use exports lands in the Official Journal",
        "source": "Council + Official Journal",
        "snippet": (
            "Three institutional moves on Russia this week that the headline-level "
            "press will compress into one story. First, the next EU sanctions "
            "package is in preparation, with over a hundred additional tanker "
            "vessels expected to be listed, plus new flag-state due-diligence "
            "requirements and EU-port denial-of-service rules. Council adoption is "
            "expected late May or early June. Second, an Information Note on the "
            "EU dual-use export controls framework was published in the Official "
            "Journal C series, clarifying brokering and technical-assistance "
            "obligations for any company handling listed items. Third, Frontex "
            "flags post-war arms-smuggling risk to organised crime networks, with "
            "implications for the future Russia-property reconstruction mechanism."
        ),
        "ask": "What is the new EU sanctions package against Russia and how does it interact with dual-use export controls?",
        "feature_label": "EU Law Comply",
        "feature_url": "https://brubru.beresol.eu/eulawcomply",
        "color": "#dc2626",
    },
]


HERO_HTML = """
<p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 12px 0;">
  Starting today, the <strong>Brubru Brief</strong> drops only when EU
  institutional moves justify it, not on a fixed schedule. You will receive
  it one to three times a week, with only the news that mainstream EU press
  (Politico, Euractiv, Euronews) and the Anglo financial press (FT, Bloomberg,
  Reuters) do not cover.
</p>
<p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 20px 0;">
  Today's transition issue: <strong>5 institutional signals</strong> from this
  week worth your minute. None of them are in the press.
</p>
"""


FOOTER_INTRO_HTML = """
<p style="font-size: 14px; color: #6b7280; line-height: 1.6; margin: 20px 0 12px 0; padding-top: 16px; border-top: 1px solid #e5e7eb;">
  From now on, the Brubru Brief lands only when there is institutional signal
  worth your time, not on a calendar. If you want the rest of what we do
  daily, the chat at
  <a href="https://brubru.beresol.eu" style="color: #0693e3; text-decoration: none;">brubru.beresol.eu</a>
  and
  <a href="https://www.linkedin.com/company/105185376/admin/dashboard/" style="color: #0693e3; text-decoration: none;">our LinkedIn page</a>
  carry the rolling stream.
</p>
"""


def _build_headline_block(h: dict, index: int) -> str:
    color = h["color"]
    ask_url = f"{BRUBRU_CHAT}?q={quote(h['ask'])}"
    return f"""
    <tr>
      <td style="padding: 18px 0; border-bottom: 1px solid #f3f4f6;">
        <div style="color: #111827; font-size: 16px; font-weight: 600; line-height: 1.4; margin-bottom: 8px;">
          {index + 1}. {h['title']}
        </div>
        <div style="color: #374151; font-size: 14px; line-height: 1.6; margin-bottom: 10px;">
          {h['snippet']}
        </div>
        <div style="margin-bottom: 6px;">
          <a href="{ask_url}" style="color: {color}; font-size: 14px; font-style: italic; text-decoration: none; line-height: 1.4;">
            &ldquo;{h['ask']}&rdquo;
          </a>
        </div>
        <div style="margin-bottom: 6px;">
          <a href="{ask_url}" style="display: inline-block; padding: 5px 14px; font-size: 12px; font-weight: 600; color: {color}; border: 1px solid {color}; border-radius: 4px; text-decoration: none; margin-right: 6px;">
            Ask Brubru
          </a>
          <a href="{h['feature_url']}" style="display: inline-block; padding: 5px 14px; font-size: 12px; font-weight: 600; color: #ffffff; background: {color}; border: 1px solid {color}; border-radius: 4px; text-decoration: none;">
            Go to {h['feature_label']}
          </a>
        </div>
        <div style="font-size: 11px; color: #9ca3af; margin-top: 6px;">
          Source: {h['source']}
        </div>
      </td>
    </tr>"""


def _build_html(recipient: str) -> str:
    headline_rows = "\n".join(
        _build_headline_block(h, i) for i, h in enumerate(HEADLINES)
    )
    unsub_url = (
        "https://brubru-production.up.railway.app/api/daily-brief/unsubscribe?email="
        + quote(recipient)
    )
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Brubru Brief: What nobody else tells you about the EU Bubble</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f9fafb; padding: 24px 0;">
    <tr><td align="center">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="640" style="max-width: 640px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">
        <tr><td style="padding: 32px 32px 8px 32px;">
          <div style="font-family: 'Adobe Caslon Pro', Georgia, serif; font-size: 28px; font-weight: 700; color: #111827; letter-spacing: -0.5px;">
            Brubru Brief
          </div>
          <div style="font-size: 14px; color: #6b7280; margin-top: 4px;">
            Monday 11 May 2026, transition issue
          </div>
        </td></tr>
        <tr><td style="padding: 16px 32px 0 32px;">
          {HERO_HTML}
        </td></tr>
        <tr><td style="padding: 0 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            {headline_rows}
          </table>
        </td></tr>
        <tr><td style="padding: 0 32px;">
          {FOOTER_INTRO_HTML}
        </td></tr>
        <tr><td style="padding: 20px 32px 28px 32px; font-size: 11px; color: #9ca3af; line-height: 1.5;">
          You are receiving the Brubru Brief because you signed up at
          <a href="https://brubru.beresol.eu" style="color: #9ca3af; text-decoration: underline;">brubru.beresol.eu</a>,
          you were captured via a Brubru email, or your organisation is
          registered with the EU Transparency Register in a policy area
          covered by today's headlines.
          <br>
          <a href="{unsub_url}" style="color: #9ca3af; text-decoration: underline;">Unsubscribe</a>
          &middot;
          <a href="https://brubru.beresol.eu" style="color: #9ca3af; text-decoration: underline;">brubru.beresol.eu</a>
          &middot;
          <a href="https://beresol.eu" style="color: #9ca3af; text-decoration: underline;">Beresol</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_test():
    test_email = "hello@beresol.eu"
    html = _build_html(test_email)
    service = EmailService()
    ok = service.send(
        to=test_email,
        subject=f"[TEST] {SUBJECT}",
        html_body=html,
    )
    if ok:
        print(f"[OK] Test sent to {test_email}")
        print(f"     Subject: [TEST] {SUBJECT}")
        print(f"     Headlines: {len(HEADLINES)}")
        print(f"     Review in inbox. If approved, run --send.")
    else:
        print(f"[ERROR] Test failed.")
        sys.exit(1)


def _collect_recipients(include_base: bool, include_eutr: bool) -> dict:
    """Return dict with 'base', 'eutr', 'all' lists and breakdown counts.

    'all' is base + eutr deduplicated (case-insensitive).
    """
    base_emails = []
    n_reg = n_pre = 0
    eutr_rows = []  # (email, name, country, cluster)

    db = SessionLocal()
    try:
        if include_base:
            registered, preuser_only = _get_all_recipient_emails(db)
            n_reg = len(registered)
            n_pre = len(preuser_only)
            base_emails = sorted(set(registered) | set(preuser_only))
        base_set = {e.strip().lower() for e in base_emails if e}
        if include_eutr:
            eutr_rows = _fetch_eutr_matched_emails(db, exclude_emails=base_set)
    finally:
        db.close()

    all_emails = list(base_emails)
    for row in eutr_rows:
        all_emails.append(row[0])

    return {
        "base": base_emails,
        "eutr": eutr_rows,
        "all": all_emails,
        "n_base": len(base_emails),
        "n_reg": n_reg,
        "n_pre": n_pre,
        "n_eutr": len(eutr_rows),
    }


def preview():
    """Show recipient breakdown without sending."""
    info = _collect_recipients(include_base=True, include_eutr=True)
    print(f"BASE subscribers: {info['n_base']} ({info['n_reg']} registered + {info['n_pre']} pre-user)")
    print(f"EUTR matched orgs: {info['n_eutr']} (today's clusters: {', '.join(_all_clusters_today())})")
    print(f"TOTAL unique recipients: {len(info['all'])}")
    # Breakdown by cluster
    by_cluster = {}
    by_country = {}
    for _email, _name, country, cluster in info["eutr"]:
        by_cluster[cluster] = by_cluster.get(cluster, 0) + 1
        by_country[country] = by_country.get(country, 0) + 1
    print("\nEUTR breakdown by cluster:")
    for c, n in sorted(by_cluster.items(), key=lambda kv: -kv[1]):
        print(f"  {c}: {n}")
    print("\nEUTR breakdown by country:")
    for c, n in sorted(by_country.items(), key=lambda kv: -kv[1]):
        print(f"  {c}: {n}")


def send_live(include_base: bool, include_eutr: bool):
    info = _collect_recipients(include_base=include_base, include_eutr=include_eutr)
    base_emails = info["base"]
    eutr_rows = info["eutr"]
    all_emails = info["all"]

    print(f"Recipients: {len(all_emails)} (base {info['n_base']} + eutr {info['n_eutr']})")
    if not all_emails:
        print("[ERROR] No recipients.")
        sys.exit(1)

    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER") or os.environ.get("SMTP_USERNAME")
    pwd = os.environ.get("SMTP_PASSWORD")

    if not (user and pwd):
        print("[ERROR] SMTP_USER + SMTP_PASSWORD must be set in .env")
        sys.exit(1)

    sent = 0
    failed = 0

    # Send to base subscribers first
    with smtplib.SMTP(host, port, timeout=60) as smtp:
        smtp.starttls()
        smtp.login(user, pwd)

        for i, rcpt in enumerate(base_emails, 1):
            try:
                html = _build_html(rcpt)
                msg = MIMEText(html, "html")
                msg["From"] = f"Brubru <{user}>"
                msg["To"] = "hello@beresol.eu"
                msg["Subject"] = SUBJECT
                msg["Reply-To"] = "hello@beresol.eu"
                smtp.sendmail(user, [rcpt], msg.as_string())
                sent += 1
                if i % 50 == 0:
                    print(f"  [base {i}/{len(base_emails)}] sent")
                time.sleep(0.5)
            except Exception as exc:
                failed += 1
                print(f"  [FAIL base] {rcpt}: {exc}")

        # Then EUTR-matched orgs, log each
        db = SessionLocal()
        try:
            for i, (rcpt, name, country, cluster) in enumerate(eutr_rows, 1):
                try:
                    html = _build_html(rcpt)
                    msg = MIMEText(html, "html")
                    msg["From"] = f"Brubru <{user}>"
                    msg["To"] = "hello@beresol.eu"
                    msg["Subject"] = SUBJECT
                    msg["Reply-To"] = "hello@beresol.eu"
                    smtp.sendmail(user, [rcpt], msg.as_string())
                    _log_eutr_send(db, rcpt, name or "", cluster or "")
                    sent += 1
                    if i % 50 == 0:
                        db.commit()
                        print(f"  [eutr {i}/{len(eutr_rows)}] sent")
                    time.sleep(0.5)
                except Exception as exc:
                    failed += 1
                    print(f"  [FAIL eutr] {rcpt}: {exc}")
            db.commit()
        finally:
            db.close()

    print(f"\n[OK] Live send complete: {sent} sent, {failed} failed (base {info['n_base']} + eutr {info['n_eutr']})")


def main():
    parser = argparse.ArgumentParser(description="Send Brubru Brief transition issue (Mon 11 May 2026)")
    parser.add_argument("--test", action="store_true", help="Send TEST to hello@beresol.eu only")
    parser.add_argument("--preview", action="store_true", help="Show recipient breakdown (base + matched EUTR)")
    parser.add_argument("--send-base", action="store_true", help="Send LIVE to base subscribers only")
    parser.add_argument("--send-eutr", action="store_true", help="Send LIVE to matched EUTR orgs only")
    parser.add_argument("--send-all", action="store_true", help="Send LIVE to base + matched EUTR (dedup)")
    args = parser.parse_args()
    if args.test:
        send_test()
    elif args.preview:
        preview()
    elif args.send_base:
        send_live(include_base=True, include_eutr=False)
    elif args.send_eutr:
        send_live(include_base=False, include_eutr=True)
    elif args.send_all:
        send_live(include_base=True, include_eutr=True)
    else:
        print("Specify --test, --preview, --send-base, --send-eutr, or --send-all")
        sys.exit(1)


if __name__ == "__main__":
    main()
