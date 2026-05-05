"""
/send-batch — EU-wide English EUTR organisations news alert (3 days/week routine).

Picks ~100 EU lobby orgs from EU Transparency Register across 10 countries
matching today's headline clusters, sends an English-language outreach email
tying that day's news to Brubru's value, with a 21-day no-repeat rotation
tracked via pre_user_events (event_type='send_batch_eu_eutr').

Countries covered: Belgium, Germany, France, Netherlands, Italy, Austria,
Poland, Ireland, Sweden, Denmark.

Every "Brubru" mention is bold + hyperlinked to https://brubru.beresol.eu.

Usage:
    python3.12 scripts/send_batch_eu_eutr.py --preview         # show recipients + email body
    python3.12 scripts/send_batch_eu_eutr.py --test            # send to hello@beresol.eu only
    python3.12 scripts/send_batch_eu_eutr.py --send            # SMTP-level BCC to all 100
"""
import argparse
import logging
import os
import sys
from datetime import date
from typing import List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# load_dotenv required: raw smtplib path reads SMTP_PASSWORD via os.environ.get directly.
# EmailService (--test) auto-loads internally; smtplib (--send) does not.
# See memory/feedback_send_script_dotenv_required.md.
try:
    from dotenv import load_dotenv  # type: ignore
    _env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        ".env",
    )
    if os.path.isfile(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from services.email_service import EmailService  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

BRUBRU_URL = "https://brubru.beresol.eu"
BATCH_SIZE = 100
NO_REPEAT_DAYS = 21
EVENT_TYPE = "send_batch_eu_eutr"

EU_COUNTRIES = (
    "BELGIUM", "GERMANY", "FRANCE", "NETHERLANDS",
    "ITALY", "AUSTRIA", "POLAND", "IRELAND", "SWEDEN", "DENMARK",
)

# Today's headlines as bullet items in English.
# Edit these per-day; the rest of the email is template.
ISSUES_THIS_WEEK_SHORT = "METSAF, Meta DSA, MFF 2028-2034, Mercosur, Better Regulation"
ISSUES_BULLETS = [
    "<strong>METSAF Regulation — EP plenary adopted the text on Wednesday 30 April in Strasbourg</strong>. The Methane and SF6 Abatement Framework sets binding reduction targets across energy, agriculture and waste sectors by 2030 and 2035. Rapporteur: Bas Eickhout (Greens/EFA, NL). Enters force 20 days after OJ publication.",
    "<strong>Meta DSA enforcement — Commission opened formal proceedings on Meta's advertising-targeting practices</strong> under Article 26(3) DSA (Regulation (EU) 2022/2065, CELEX 32022R2065). Third major 2026 enforcement action after X/Twitter and TikTok. Non-compliance risks fines of up to 6% of global turnover.",
    "<strong>EU–Mercosur Interim Trade Agreement entered provisional application on Friday 1 May</strong> (CELEX 22026A00184). Tariff changes are now live for agricultural importers, automotive, textiles and leather across all ten countries covered by this wave.",
    "<strong>MFF 2028–2034 — first trilogue round expected this week, EP position adopted 29 April</strong>. Co-rapporteurs Mureşan (EPP, RO) and Tavares (S&D); Parliament's ask: 1.27% GNI cap, NextGenerationEU debt-service outside the ceiling, new defence and competitiveness headings.",
    "<strong>Better Regulation and Enforcement Communication adopted 30 April by the College of Commissioners</strong> (EVP Dombrovskis). First time simplification and Article 258 TFEU infringement strategy are unified in a single document — directly affects any organisation currently under a Pilot procedure or formal infringement.",
]


def _select_recipients(db, batch_size: int = BATCH_SIZE) -> Tuple[List[dict], int, int]:
    """Pick top-N EU orgs across relevant clusters, excluding those contacted in last 21 days."""
    country_list = ", ".join(f"'{c}'" for c in EU_COUNTRIES)
    sql = text(f"""
        WITH eligible AS (
            SELECT t.id, t.name, t.contact_email, t.policy_cluster, t.calculated_cost, t.country,
                   COALESCE(MAX(p.created_at), '1970-01-01'::timestamptz) AS last_sent
            FROM transparency_register_orgs t
            LEFT JOIN pre_user_events p
              ON LOWER(p.event_metadata->>'email') = LOWER(t.contact_email)
             AND p.event_type = :event_type
            WHERE UPPER(t.country) IN ({country_list})
              AND t.contact_email IS NOT NULL
              AND t.contact_email != ''
              AND COALESCE(t.outreach_status, '') != 'bounced'
              AND t.policy_cluster IN ('trade','climate','energy','agriculture',
                                       'finance','research','digital','social')
            GROUP BY t.id, t.name, t.contact_email, t.policy_cluster, t.calculated_cost, t.country
        )
        SELECT id, name, contact_email, policy_cluster, calculated_cost, country, last_sent
        FROM eligible
        WHERE last_sent < (NOW() - INTERVAL '{NO_REPEAT_DAYS} days')::timestamptz
        ORDER BY
            CASE policy_cluster
                WHEN 'trade'        THEN 1
                WHEN 'climate'      THEN 2
                WHEN 'energy'       THEN 3
                WHEN 'agriculture'  THEN 4
                WHEN 'finance'      THEN 5
                WHEN 'research'     THEN 6
                WHEN 'digital'      THEN 7
                WHEN 'social'       THEN 8
            END,
            calculated_cost DESC NULLS LAST,
            name
        LIMIT :limit
    """)

    rows = db.execute(sql, {"event_type": EVENT_TYPE, "limit": batch_size}).fetchall()
    recipients = [
        {
            "id": str(r[0]),
            "name": r[1],
            "email": r[2].strip().lower(),
            "cluster": r[3],
            "cost": r[4],
            "country": r[5],
            "last_sent": r[6],
        }
        for r in rows
    ]

    excluded_recently = db.execute(
        text(f"""
            SELECT COUNT(DISTINCT LOWER(t.contact_email))
            FROM transparency_register_orgs t
            JOIN pre_user_events p
              ON LOWER(p.event_metadata->>'email') = LOWER(t.contact_email)
             AND p.event_type = :event_type
             AND p.created_at >= (NOW() - INTERVAL '{NO_REPEAT_DAYS} days')::timestamptz
            WHERE UPPER(t.country) IN ({country_list})
              AND t.contact_email IS NOT NULL
        """),
        {"event_type": EVENT_TYPE},
    ).scalar() or 0

    excluded_bounced = db.execute(
        text(f"""
            SELECT COUNT(*)
            FROM transparency_register_orgs
            WHERE UPPER(country) IN ({country_list})
              AND contact_email IS NOT NULL
              AND outreach_status = 'bounced'
        """)
    ).scalar() or 0

    return recipients, excluded_recently, excluded_bounced


def _bold_link_brubru(text_str: str) -> str:
    """Replace every 'Brubru' with bold + linked HTML. Idempotent for <strong>Brubru</strong>."""
    linked = f'<a href="{BRUBRU_URL}" style="color: #0693e3; text-decoration: none; font-weight: 700;">Brubru</a>'
    text_str = text_str.replace("<strong>Brubru</strong>", "Brubru")
    return text_str.replace("Brubru", linked)


def _build_email_html(today_iso: str) -> str:
    bullets_html = "\n".join(f"<li style=\"margin-bottom: 10px;\">{b}</li>" for b in ISSUES_BULLETS)
    body = f"""
    <div style="font-family: Georgia, 'Times New Roman', serif; font-size: 15px; line-height: 1.6; color: #1a1a1a; max-width: 640px;">
    <p>Dear colleague,</p>

    <p>we noticed your organisation on the EU Transparency Register and believe you may find Brubru useful for the EU policy files moving this week:</p>

    <ul style="padding-left: 20px;">
{bullets_html}
    </ul>

    <p>In Brubru you can ask any question about these files in our AI-powered Chat, track legislation in real time, draft amendments following the official European Parliament format, and see predicted institutional positions for each law.</p>

    <p>Brubru also lets you generate official EU documents (e.g. parliamentary questions, legislative summaries, position papers); assess your organisation's compliance with EU law; and prepare bids for EU tenders.</p>

    <p>You can also integrate Brubru into your organisation's workflows through our API.</p>

    <p style="margin-top: 24px;"><strong>Contact us for a free demo!</strong></p>

    <p>Thank you for your time and have a good week.</p>

    <p>Kind regards,<br/>
    The Brubru team</p>

    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 30px 0;"/>
    <p style="font-size: 11px; color: #999;">
        If you would prefer not to receive further emails, please reply with "UNSUBSCRIBE" in the subject line.<br/>
        Brubru by Beresol BV &middot; Brussels &middot; {today_iso}
    </p>
    </div>
    """
    return _bold_link_brubru(body)


def _log_send(db, email: str, name: str) -> None:
    """Log a successful send to pre_user_events for 21-day rotation tracking."""
    db.execute(
        text("""
            INSERT INTO pre_user_events (id, pre_user_id, event_type, ab_variant, event_metadata, created_at)
            VALUES (gen_random_uuid(), gen_random_uuid()::text, :et, 'A',
                    jsonb_build_object('email', :email, 'org_name', :name, 'campaign', 'eu_eutr_2026_05'),
                    NOW())
        """),
        {"et": EVENT_TYPE, "email": email, "name": name},
    )


def _send_smtp_bcc_batch(recipients: List[dict], subject: str, html_body: str, db) -> Tuple[int, int]:
    """Send via SMTP-level BCC pattern (see memory/feedback_send_batch_use_bcc.md):
    - One MIMEText envelope, To=hello@beresol.eu (visible address)
    - Single SMTP connection reused for all RCPT TO calls
    - 0.5s delay between sends to respect Gmail per-second cap
    """
    import smtplib
    import time
    from email.mime.text import MIMEText

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = (os.environ.get("SMTP_USER")
                 or os.environ.get("EMAIL_FROM")
                 or "hello@beresol.eu")
    smtp_pass = os.environ.get("SMTP_PASSWORD")
    if not smtp_pass:
        logger.error("[ERROR] SMTP_PASSWORD env var not set. Aborting to avoid per-recipient rate-limit.")
        logger.error("        Add SMTP_PASSWORD to .env — see memory/feedback_send_script_dotenv_required.md.")
        return 0, len(recipients)

    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = "hello@beresol.eu"

    sent_n, failed_n = 0, 0
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(smtp_user, smtp_pass)
        for i, r in enumerate(recipients, 1):
            try:
                server.sendmail(smtp_user, [r["email"]], msg.as_string())
                _log_send(db, r["email"], r["name"])
                sent_n += 1
                if i % 10 == 0:
                    logger.info(f"  [{i}/{len(recipients)}] sent so far")
            except Exception as e:  # noqa: BLE001
                logger.error(f"[ERROR] Failed to send to {r['email']}: {e}")
                failed_n += 1
            time.sleep(0.5)
    db.commit()
    return sent_n, failed_n


def main() -> int:
    parser = argparse.ArgumentParser(description="Send batch to EU-wide EUTR orgs (English, 3 days/week)")
    parser.add_argument("--preview", action="store_true", help="Show recipients + email, do not send")
    parser.add_argument("--test", action="store_true", help="Send to hello@beresol.eu only")
    parser.add_argument("--send", action="store_true", help="Send to all selected recipients")
    parser.add_argument("--limit", type=int, default=BATCH_SIZE, help=f"Number of recipients (default {BATCH_SIZE})")
    args = parser.parse_args()

    today_iso = date.today().isoformat()
    subject = f"Brubru for your EU public-affairs work: {ISSUES_THIS_WEEK_SHORT}"
    html_body = _build_email_html(today_iso)

    db = SessionLocal()
    try:
        recipients, excl_recent, excl_bounced = _select_recipients(db, args.limit)

        from collections import Counter
        cluster_mix = Counter(r["cluster"] for r in recipients)
        country_mix = Counter(r["country"] for r in recipients)
        print(f"\n[INFO] Today: {today_iso}")
        print(f"[INFO] Recipients eligible: {len(recipients)}")
        print(f"[INFO] Cluster mix:  {dict(cluster_mix)}")
        print(f"[INFO] Country mix:  {dict(country_mix)}")
        print(f"[INFO] Excluded as bounced: {excl_bounced}")
        print(f"[INFO] Excluded by 21-day rotation: {excl_recent}")
        print(f"[INFO] Subject: {subject}")
        print()

        if args.preview:
            print("[PREVIEW] First 10 recipients:")
            for r in recipients[:10]:
                print(f"  [{r['cluster']:>11s}] [{r['country']:>12s}] {r['name'][:50]:<50s} | {r['email']}")
            print(f"  ... and {max(0, len(recipients) - 10)} more")
            print()
            print("[PREVIEW] HTML body (first 600 chars):")
            print(html_body[:600])
            return 0

        if args.test:
            print("[TEST] Sending to hello@beresol.eu only")
            ok = EmailService().send(to="hello@beresol.eu", subject=f"[TEST] {subject}", html_body=html_body)
            print("[OK] Test sent" if ok else "[ERROR] Test send failed")
            return 0 if ok else 1

        if args.send:
            if len(recipients) == 0:
                print("[ERROR] No eligible recipients — run Steps 1-2 from the prep checklist first")
                return 1
            print(f"[SEND] Sending to {len(recipients)} recipients via SMTP-level BCC")
            sent_n, failed_n = _send_smtp_bcc_batch(recipients, subject, html_body, db)
            print(f"\n[OK] Sent: {sent_n}  Failed: {failed_n}")
            return 0 if failed_n == 0 else 1

        print("[INFO] Use --preview / --test / --send")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
