"""
Brubru Brief issue: Monday 18 May 2026 (Strasbourg plenary week 21).

Format per `memory/feedback_brubru_brief_new_format.md` (11 May 2026):
- Subject: "Brubru Brief: What nobody else tells you about the EU Bubble - Monday 18 May 2026"
- Hero: institutional content NOT covered by mainstream EU press OR Anglo financial press
- 5 headlines, each: title + 2-3 sentence snippet + Ask Brubru + Go to feature + Source
- No em-dashes, no emojis, no institutional codes in lead

Usage:
    python3.12 scripts/send_brubru_brief_2026_05_18.py --test   # to hello@beresol.eu
    python3.12 scripts/send_brubru_brief_2026_05_18.py --send   # base subscribers + matched EUTR (live)
"""
import argparse
import os
import smtplib
import sys
import time
import uuid as _uuid
from datetime import datetime as _dt
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


def _all_clusters_today() -> list:
    s = set()
    for clusters in HEADLINE_CLUSTERS.values():
        s.update(clusters)
    return sorted(s)


# Generic local-parts that must NEVER receive marketing/outreach emails (per
# memory/feedback_no_generic_inbox_sends.md, set 18 May 2026). These almost always
# bounce or get filtered. Filter at SQL time, not at send time. hello@beresol.eu is
# our own test inbox and goes through a different path (EXTRAS / test), not the bulk pool.
GENERIC_LOCAL_PARTS = (
    'info', 'contact', 'office', 'mail', 'support', 'secretary', 'admin',
    'webmaster', 'enquiries', 'inquiries', 'hello',
)


def _fetch_eutr_matched_emails(db_session, exclude_emails: set) -> list:
    clusters = _all_clusters_today()
    query = text("""
        SELECT o.contact_email AS email, o.name, o.country, o.policy_cluster
        FROM transparency_register_orgs o
        WHERE o.contact_email IS NOT NULL
          AND o.email_verified = true
          AND o.outreach_status NOT IN ('bounced', 'unsubscribed')
          AND LOWER(SPLIT_PART(o.contact_email, '@', 1)) <> ALL(:generic_parts)
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
    rows = db_session.execute(query, {"clusters": clusters, "generic_parts": list(GENERIC_LOCAL_PARTS)}).fetchall()
    out, seen = [], set()
    for r in rows:
        email = (r.email or "").strip().lower()
        if not email or email in exclude_emails or email in seen:
            continue
        seen.add(email)
        out.append((email, r.name, r.country, r.policy_cluster))
    return out


def _log_eutr_send(db_session, email: str, org_name: str, policy_cluster: str):
    db_session.execute(
        text("""
            INSERT INTO pre_user_events (id, pre_user_id, event_type, ab_variant, event_metadata, created_at)
            VALUES (:id, :pre_user_id, 'send_brubru_brief_eutr', 'A', CAST(:metadata AS jsonb), :ts)
        """),
        {
            "id": str(_uuid.uuid4()),
            "pre_user_id": str(_uuid.uuid4()),
            "metadata": '{{"email": "{e}", "org_name": "{o}", "policy_cluster": "{c}", "issue": "2026-05-18"}}'.format(
                e=email.replace('"', ''),
                o=(org_name or '').replace('"', ''),
                c=(policy_cluster or '').replace('"', ''),
            ),
            "ts": _dt.utcnow(),
        }
    )


SUBJECT = "Brubru Brief: What nobody else tells you about the EU Bubble - Monday 18 May 2026"
BRUBRU_CHAT = "https://brubru.beresol.eu/main"


# Today's headline-to-EUTR-cluster mapping. Per memory format spec.
HEADLINE_CLUSTERS = {
    "eu_china_wto_art28": ["trade"],
    "eprivacy_csam_extension": ["civil_society"],
    "eppo_chief_prosecutor": ["civil_society"],
    "afco_institutional_cluster": ["civil_society"],
    "peti_strasbourg_cluster": ["civil_society"],
}


HEADLINES = [
    {
        "title": "The EU and China formalise a WTO concession-schedule adjustment in today's Official Journal",
        "source": "Official Journal of the European Union, L series, Monday 18 May 2026",
        "snippet": (
            "An exchange of letters between the European Union and the People's Republic of China "
            "under Article XXVIII of the General Agreement on Tariffs and Trade 1994 was published "
            "in today's Official Journal. Article XXVIII is the WTO procedure for renegotiating "
            "previously bound tariff commitments, the bilateral adjustment fits inside the broader "
            "EU economic-security framing on China. Mainstream press will summarise the political "
            "narrative, not the legal mechanics."
        ),
        "ask": "What does the new EU-China GATT Article XXVIII letter exchange change for EU importers and exporters?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#0693e3",
    },
    {
        "title": "The ePrivacy derogation expired on 3 April, the Strasbourg plenary from Tuesday is the most plausible adoption window",
        "source": "EP LIBE committee draft report, Monday 18 May",
        "snippet": (
            "The temporary derogation that lets messaging platforms voluntarily scan for child sexual "
            "abuse material expired on 3 April 2026. LIBE's draft report on the extension surfaced "
            "again on the committee portal today as the Strasbourg plenary opens. With the file in "
            "close-to-adoption status and six weeks of legal limbo behind it, the Tuesday-to-Friday "
            "window is the most credible adoption slot. The broader CSAM Regulation remains a "
            "separate and contested file."
        ),
        "ask": "Why has the voluntary CSAM scanning derogation been in legal limbo since 3 April 2026?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#9b51e0",
    },
    {
        "title": "Who replaces Laura Codruta Kovesi at the EPPO, LIBE keeps the consent procedure moving in Strasbourg week",
        "source": "EP LIBE committee draft report, Monday 18 May",
        "snippet": (
            "Laura Codruta Kovesi's seven-year term as European Chief Prosecutor ends in October 2026. "
            "The Council-EP joint shortlist for her successor remains confidential. LIBE's draft report "
            "on the consent procedure resurfaced today, but no plenary vote is scheduled this week. The "
            "file is in committee-stage preparation, the earliest plenary consent vote is June or July."
        ),
        "ask": "What is the consent procedure for appointing the next European Chief Prosecutor at the EPPO?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#059669",
    },
    {
        "title": "AFCO drops four institutional draft reports today, on the Defence Union, the Parliament-Commission relationship, Article 19 TEU, and agency appointments",
        "source": "EP AFCO committee portal, Monday 18 May",
        "snippet": (
            "The Constitutional Affairs committee filed four draft reports on Monday morning. They "
            "cover the architecture of the Common European Defence Union, the Framework Agreement "
            "between the Parliament and the Commission, the EU institutional framework under Article 19 "
            "TEU (the treaty article requiring national courts to provide remedies under Union law), "
            "and Rule 135 of the EP Rules of Procedure on appointments to Union agencies. None of "
            "these are in mainstream press today."
        ),
        "ask": "What is AFCO proposing on the institutional architecture of the Common European Defence Union?",
        "feature_label": "Position Analysis",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=position_analysis",
        "color": "#d97706",
    },
    {
        "title": "The long-term EU budget for 2028 to 2034 returns to Parliament with the PETI opinion tabled today",
        "source": "EP PETI committee portal, Monday 18 May",
        "snippet": (
            "PETI tabled its opinion on the multiannual financial framework for 2028 to 2034 this "
            "morning. The Commission proposal sets a total commitment of around 1.763 trillion euro "
            "in 2025 prices (about 1.26 percent of EU GNI), simplifies the architecture from seven "
            "headings to four, and folds the previous 52 programmes into 16. Around 35 percent is "
            "earmarked for climate spending, with NextGenerationEU debt repayment baked in. PETI's "
            "opinion lands alongside seven other plenary-week files from the same committee."
        ),
        "ask": "What is the structure and timeline of the European Union long-term budget for 2028 to 2034?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#dc2626",
    },
]


HERO_HTML = """
<p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 12px 0;">
  Strasbourg plenary opens tomorrow. Below are <strong>five institutional moves</strong> from this
  week that mainstream EU press (Politico, Euractiv, Euronews) and the Anglo financial press
  (FT, Bloomberg, Reuters) do not cover today.
</p>
<p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 20px 0;">
  Each one is answerable in Brubru's chat in six languages, and each one points to the
  Brubru product surface where you can act on it.
</p>
"""

FOOTER_INTRO_HTML = """
<p style="font-size: 14px; color: #6b7280; line-height: 1.6; margin: 20px 0 12px 0; padding-top: 16px; border-top: 1px solid #e5e7eb;">
  The Brubru Brief lands only when there is institutional signal worth your time, not on a
  calendar. For the rolling daily stream, the chat at
  <a href="https://brubru.beresol.eu" style="color: #0693e3; text-decoration: none;">brubru.beresol.eu</a>
  and
  <a href="https://www.linkedin.com/company/105185376/" style="color: #0693e3; text-decoration: none;">our LinkedIn page</a>
  carry it.
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
    headline_rows = "\n".join(_build_headline_block(h, i) for i, h in enumerate(HEADLINES))
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
            Monday 18 May 2026, Strasbourg plenary week
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
          you were captured via a Brubru email, or your organisation is registered with the EU
          Transparency Register in a policy area covered by today's headlines.
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
    else:
        print("[ERROR] Test send failed")
        sys.exit(1)


def _collect_recipients(include_base: bool, include_eutr: bool) -> dict:
    base_emails = []
    n_reg = n_pre = 0
    eutr_rows = []
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
    all_emails = list(base_emails) + [r[0] for r in eutr_rows]
    return {
        "base": base_emails, "eutr": eutr_rows, "all": all_emails,
        "n_base": len(base_emails), "n_reg": n_reg, "n_pre": n_pre, "n_eutr": len(eutr_rows),
    }


def preview():
    info = _collect_recipients(include_base=True, include_eutr=True)
    print(f"BASE subscribers: {info['n_base']} ({info['n_reg']} registered + {info['n_pre']} pre-user)")
    print(f"EUTR matched orgs: {info['n_eutr']} (clusters: {', '.join(_all_clusters_today())})")
    print(f"TOTAL unique recipients: {len(info['all'])}")
    by_c = {}
    by_co = {}
    for _e, _n, country, cluster in info["eutr"]:
        by_c[cluster] = by_c.get(cluster, 0) + 1
        by_co[country] = by_co.get(country, 0) + 1
    if by_c:
        print("\nEUTR by cluster:")
        for c, n in sorted(by_c.items(), key=lambda kv: -kv[1]):
            print(f"  {c}: {n}")


def send_live(include_base: bool, include_eutr: bool):
    info = _collect_recipients(include_base=include_base, include_eutr=include_eutr)
    base_emails = info["base"]
    eutr_rows = info["eutr"]
    print(f"Recipients: {len(info['all'])} (base {info['n_base']} + eutr {info['n_eutr']})")
    if not info["all"]:
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--send-base", action="store_true")
    parser.add_argument("--send-eutr", action="store_true")
    parser.add_argument("--send-all", action="store_true")
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
        parser.print_help()
