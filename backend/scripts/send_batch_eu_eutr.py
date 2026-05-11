"""
/send-batch — EU-wide EUTR organisations targeted news alert (English).

Picks ~100 EUTR orgs from EU-27 + EFTA matching today's headline clusters,
sends an English outreach email tying that day's news to Brubru's value, with a
21-day no-repeat rotation tracked via pre_user_events (event_type='send_batch_eu_eutr').

SEPARATE rotation pool from `send_batch_es_eutr.py` (Spanish-only). The two never
contact the same org in the same 21-day window because the Spanish pool is
filtered by country=Spain (which is excluded here).

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

from sqlalchemy import text  # noqa: E402
from core.database import SessionLocal  # noqa: E402
from services.email_service import EmailService  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

BRUBRU_URL = "https://brubru.beresol.eu"
BATCH_SIZE = 100
NO_REPEAT_DAYS = 21
EVENT_TYPE = "send_batch_eu_eutr"

# Subject line — short list of today's hot files
ISSUES_THIS_WEEK_SHORT = "METSAF, Meta DSA, MFF 2028-2034, Mercosur, Better Regulation"

# Today's headlines as bullet items in English. Edit per send; the rest of the
# email is template. Each bullet starts with a <strong> headline + a 1-2 sentence
# value-dense follow-up. NEVER use double-dashes; use colons or em-dashes.
ISSUES_BULLETS = [
    "<strong>METSAF — Middle East crisis Temporary State aid Framework adopted on Wednesday 29 April</strong> (IP/26/894). Up to 70% of fuel and fertiliser cost spikes compensable for agriculture, fisheries, transport (road, rail, inland waterways, intra-EU short sea); €50,000 flat-rate option for SMEs; CISAF temporary adjustment lifts the electricity-cost ceiling for energy-intensive industry from 50% to 70%. In force until 31 December 2026.",
    "<strong>Meta DSA preliminary breach finding</strong> (IP/26/920). Commission preliminarily finds Instagram and Facebook in breach of the Digital Services Act for failing to keep under-13s off the platforms; roughly 10-12% of EU children under 13 are on those services despite Meta's own age limits. Fines up to 6% of worldwide annual turnover are now in scope. Same-day Recommendation urging Member States to roll out the EU age verification app by end-2026 (seven countries already integrating: France, Denmark, Greece, Italy, Spain, Cyprus, Ireland).",
    "<strong>MFF 2028-2034 — European Parliament adopted its negotiating position on Wednesday 29 April</strong> in Strasbourg. EP at 1.27% of EU GNI ceiling vs Commission proposal of 1.26%, NextGenerationEU debt-servicing outside the ceilings, inflation-protection mechanism, defence and competitiveness as new priorities. Co-rapporteurs Siegfried Mureşan (EPP, RO) and Carla Tavares (S&amp;D). Trilogue with the Cypriot Council Presidency now opens.",
    "<strong>EU-Mercosur — Interim Trade Agreement enters provisional application from Friday 1 May</strong> (Council Decision CELEX 22026A00184). Tariff reductions, quota access and origin rules under Chapter 3 become operational; bilateral safeguard regulation 2026/687 active in parallel. Changes the tariff reality for agri importers, automotive, textiles and leather across the EU.",
    "<strong>Better Regulation Communication COM(2026) 380</strong> adopted by the College of Commissioners on Tuesday 28 April. Annex I 'Regulatory Deep Cleaning Action Plan' identifies 12 priority areas (free movement of goods/services, financial services and banking, customs, taxation, health and food safety, agriculture, transport, energy, climate, environment, digital, housing and permitting), with named follow-up instruments including the European Product Act, the Public Procurement Act and the Banking Competitiveness Report.",
]

# EU-27 + EFTA (Norway, Iceland, Switzerland, Liechtenstein) + UK by name variants.
# Spain is EXCLUDED — Spanish orgs are covered by send_batch_es_eutr.py (separate
# rotation pool). The two scripts never contact the same org in the same
# 21-day window because of this country filter.
EU_COUNTRY_VARIANTS = [
    "Austria", "AT",
    "Belgium", "BE", "Belgique", "België",
    "Bulgaria", "BG",
    "Croatia", "HR", "Hrvatska",
    "Cyprus", "CY",
    "Czechia", "CZ", "Czech Republic",
    "Denmark", "DK", "Danmark",
    "Estonia", "EE", "Eesti",
    "Finland", "FI", "Suomi",
    "France", "FR",
    "Germany", "DE", "Deutschland",
    "Greece", "EL", "GR", "Hellas",
    "Hungary", "HU", "Magyarország",
    "Ireland", "IE", "Éire",
    "Italy", "IT", "Italia",
    "Latvia", "LV", "Latvija",
    "Lithuania", "LT", "Lietuva",
    "Luxembourg", "LU",
    "Malta", "MT",
    "Netherlands", "NL", "Nederland",
    "Poland", "PL", "Polska",
    "Portugal", "PT",
    "Romania", "RO", "România",
    "Slovakia", "SK", "Slovensko",
    "Slovenia", "SI", "Slovenija",
    "Sweden", "SE", "Sverige",
    "Norway", "NO", "Norge",
    "Iceland", "IS", "Ísland",
    "Switzerland", "CH", "Schweiz", "Suisse",
    "Liechtenstein", "LI",
    "United Kingdom", "UK", "GB",
]


def _select_recipients(db, batch_size: int = BATCH_SIZE) -> Tuple[List[dict], int, int]:
    """Pick top-N EU/EFTA orgs across relevant clusters, excluding those contacted in last 21 days
    (in either the EU pool or the Spanish pool — never double-contact)."""
    sql = text("""
        WITH eligible AS (
            SELECT t.id, t.name, t.contact_email, t.country, t.policy_cluster, t.calculated_cost,
                   COALESCE(MAX(p.created_at), '1970-01-01'::timestamptz) AS last_sent
            FROM transparency_register_orgs t
            LEFT JOIN pre_user_events p
              ON LOWER(p.event_metadata->>'email') = LOWER(t.contact_email)
             AND p.event_type IN ('send_batch_eu_eutr', 'send_batch_es_eutr')
            WHERE t.country IS NOT NULL
              AND t.country = ANY(:eu_countries)
              -- exclude Spain entirely (covered by send_batch_es_eutr)
              AND NOT (t.country ILIKE 'spain' OR t.country = 'ES' OR t.country ILIKE 'españa')
              AND t.contact_email IS NOT NULL
              AND t.contact_email != ''
              AND COALESCE(t.outreach_status, '') != 'bounced'
              AND t.policy_cluster IN ('trade','climate','energy','agriculture',
                                       'finance','research','digital','social')
            GROUP BY t.id, t.name, t.contact_email, t.country, t.policy_cluster, t.calculated_cost
        )
        SELECT id, name, contact_email, country, policy_cluster, calculated_cost, last_sent
        FROM eligible
        WHERE last_sent < (NOW() - INTERVAL ':days days')::timestamptz
        ORDER BY
            CASE policy_cluster
                WHEN 'trade' THEN 1
                WHEN 'agriculture' THEN 2
                WHEN 'climate' THEN 3
                WHEN 'energy' THEN 4
                WHEN 'finance' THEN 5
                WHEN 'research' THEN 6
                WHEN 'digital' THEN 7
                WHEN 'social' THEN 8
            END,
            calculated_cost DESC NULLS LAST,
            name
        LIMIT :limit
    """.replace(":days", str(NO_REPEAT_DAYS)))

    rows = db.execute(sql, {"eu_countries": EU_COUNTRY_VARIANTS, "limit": batch_size}).fetchall()
    recipients = [
        {
            "id": str(r[0]),
            "name": r[1],
            "email": r[2].strip().lower(),
            "country": r[3],
            "cluster": r[4],
            "cost": r[5],
            "last_sent": r[6],
        }
        for r in rows
    ]

    excluded_recently = db.execute(
        text("""
            SELECT COUNT(DISTINCT LOWER(t.contact_email))
            FROM transparency_register_orgs t
            JOIN pre_user_events p
              ON LOWER(p.event_metadata->>'email') = LOWER(t.contact_email)
             AND p.event_type IN ('send_batch_eu_eutr', 'send_batch_es_eutr')
             AND p.created_at >= (NOW() - INTERVAL ':days days')::timestamptz
            WHERE t.country = ANY(:eu_countries)
              AND NOT (t.country ILIKE 'spain' OR t.country = 'ES' OR t.country ILIKE 'españa')
              AND t.contact_email IS NOT NULL
        """.replace(":days", str(NO_REPEAT_DAYS))),
        {"eu_countries": EU_COUNTRY_VARIANTS},
    ).scalar() or 0

    excluded_bounced = db.execute(
        text("""
            SELECT COUNT(*)
            FROM transparency_register_orgs
            WHERE country = ANY(:eu_countries)
              AND NOT (country ILIKE 'spain' OR country = 'ES' OR country ILIKE 'españa')
              AND contact_email IS NOT NULL
              AND outreach_status = 'bounced'
        """),
        {"eu_countries": EU_COUNTRY_VARIANTS},
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
    <p>Good morning,</p>

    <p>we noticed your organisation on the EU Transparency Register and we believe you may be interested in Brubru and how it can help you with these European files that are moving this very week:</p>

    <ul style="padding-left: 20px;">
{bullets_html}
    </ul>

    <p>On Brubru you'll find a Chat where you can ask anything related to these files. You'll also be able to track in detail the European legislation in flight, draft amendments following the official European Parliament parameters, and see the prediction and institutional positioning per file.</p>

    <p>On Brubru you can also generate official EU documents (parliamentary questions, parliamentary resolutions, legislative summaries); assess the EU-law compliance of your organisation, product or service; and prepare your candidacy for EU tenders.</p>

    <p>Finally, you can also integrate Brubru into your organisation through our API.</p>

    <p style="margin-top: 24px;"><strong>Get in touch with us for a free demo!</strong></p>

    <p>Many thanks for your attention and have a good rest of the week.</p>

    <p>Kind regards,<br/>
    The Brubru team</p>

    <hr style="border: 0; border-top: 1px solid #e5e7eb; margin: 30px 0;"/>
    <p style="font-size: 11px; color: #999;">
        If you do not wish to receive further emails, reply with "UNSUBSCRIBE" in the subject.<br/>
        Brubru by Beresol BV · Brussels · {today_iso}
    </p>
    </div>
    """
    return _bold_link_brubru(body)


def _log_send(db, email: str, name: str, country: str | None) -> None:
    """Log a successful send to pre_user_events for 21-day rotation tracking."""
    db.execute(
        text("""
            INSERT INTO pre_user_events (id, pre_user_id, event_type, ab_variant, event_metadata, created_at)
            VALUES (gen_random_uuid(), gen_random_uuid()::text, :et, 'A',
                    jsonb_build_object('email', :email, 'org_name', :name,
                                       'country', :country,
                                       'campaign', 'eu_eutr_2026_04_30'),
                    NOW())
        """),
        {"et": EVENT_TYPE, "email": email, "name": name, "country": country},
    )


def _send_smtp_bcc_batch(recipients: List[dict], subject: str, html_body: str, db) -> Tuple[int, int]:
    """SMTP-level BCC: one connection, multiple RCPT TO calls. See feedback_send_batch_use_bcc.md."""
    import smtplib
    import time
    from email.mime.text import MIMEText

    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = (os.environ.get("SMTP_USER")
                 or os.environ.get("EMAIL_FROM")
                 or "hello@beresol.eu")
    smtp_pass = (os.environ.get("SMTP_PASSWORD")
                 or os.environ.get("SMTP_PASS")
                 or os.environ.get("EMAIL_PASSWORD"))
    if not smtp_pass:
        logger.error("[ERROR] No SMTP password env var found (tried SMTP_PASSWORD, SMTP_PASS, EMAIL_PASSWORD).")
        logger.error("        Set SMTP_PASSWORD in .env. Aborting send to avoid per-recipient connection rate-limit.")
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
                _log_send(db, r["email"], r["name"], r.get("country"))
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
    parser = argparse.ArgumentParser(description="Send batch to EU-wide EUTR orgs (English)")
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
        print(f"[INFO] Cluster mix: {dict(cluster_mix)}")
        print(f"[INFO] Country mix (top 10): {dict(country_mix.most_common(10))}")
        print(f"[INFO] Excluded as bounced: {excl_bounced}")
        print(f"[INFO] Excluded by 21-day rotation: {excl_recent}")
        print(f"[INFO] Subject: {subject}")
        print()

        if args.preview:
            print("[PREVIEW] First 10 recipients:")
            for r in recipients[:10]:
                print(f"  [{r['cluster']:>11s}] [{(r['country'] or '?')[:3]:<3s}] {r['name'][:50]:<50s} | {r['email']}")
            print(f"  ... and {max(0, len(recipients) - 10)} more")
            print()
            print("[PREVIEW] HTML body (first 800 chars):")
            print(html_body[:800])
            return 0

        if args.test:
            print("[TEST] Sending to hello@beresol.eu only")
            ok = EmailService().send(to="hello@beresol.eu", subject=f"[TEST] {subject}", html_body=html_body)
            print("[OK] Test sent" if ok else "[ERROR] test send failed")
            return 0 if ok else 1

        if args.send:
            if len(recipients) == 0:
                print("[ERROR] No eligible recipients")
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
