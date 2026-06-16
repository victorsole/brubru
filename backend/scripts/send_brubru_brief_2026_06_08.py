"""
Brubru Brief issue: Friday 22 May 2026 (plenary closing-week recap).

Format per `memory/feedback_brubru_brief_new_format.md` (11 May 2026) and
modelled on `send_brubru_brief_2026_05_18.py`.

- Subject: "Brubru Brief: What nobody else tells you about the EU Bubble - Friday 22 May 2026"
- Hero: institutional read-out of yesterday's plenary closing-week outcomes,
  with operational depth mainstream press will not carry today.
- 5 headlines, each: title + 2-3 sentence snippet + Ask Brubru + Go to feature + Source
- No em-dashes, no emojis, no institutional codes in lead (treaty articles + popular acronyms OK)

Usage:
    python3.12 scripts/send_brubru_brief_2026_05_22.py --test         # to hello@beresol.eu
    python3.12 scripts/send_brubru_brief_2026_05_22.py --preview      # show recipient counts
    python3.12 scripts/send_brubru_brief_2026_05_22.py --send-base    # base subscribers (live)
    python3.12 scripts/send_brubru_brief_2026_05_22.py --send-eutr    # matched EUTR orgs (live)
    python3.12 scripts/send_brubru_brief_2026_05_22.py --send-all     # both pools (live)
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
            "metadata": '{{"email": "{e}", "org_name": "{o}", "policy_cluster": "{c}", "issue": "2026-06-08"}}'.format(
                e=email.replace('"', ''),
                o=(org_name or '').replace('"', ''),
                c=(policy_cluster or '').replace('"', ''),
            ),
            "ts": _dt.utcnow(),
        }
    )


SUBJECT = "Brubru Brief: What nobody else tells you about the EU Bubble - Monday 8 June 2026"
BRUBRU_CHAT = "https://brubru.beresol.eu/main"


HEADLINE_CLUSTERS = {
    "customs_parcels": ["trade"],
    "fishing_2027": ["environment"],
    "efpia_animal_testing": ["health"],
    "afme_trading_book": ["finance"],
    "ecb_euro_role": ["finance"],
    "justice_scoreboard": ["civil_society"],
    "western_balkans": ["foreign_affairs"],
    "eca_youth": ["civil_society"],
}


HEADLINES = [
    {
        "title": "The EU just put a price on every cheap parcel: a 3 euro charge from 1 July",
        "source": "Official Journal of the EU, Friday 5 June 2026",
        "snippet": (
            "The Commission published the implementing rules for a temporary 3 euro customs charge on "
            "distance-sold imports with an intrinsic value up to 150 euro, the bracket that covers almost "
            "the entire flood of low-value e-commerce parcels entering the single market. It is an interim "
            "step under the Union Customs Code implementing rules, designed to bridge to the wider customs "
            "reform that will eventually remove the 150 euro duty relief altogether. The charge takes effect "
            "on 1 July 2026, so the operational clock for marketplaces, carriers, and customs brokers is "
            "already running, not waiting on the full reform's much later timeline."
        ),
        "ask": "What is the EU's new temporary customs duty on low-value imported parcels?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#0693e3",
    },
    {
        "title": "The EU set its 2027 fishing rules the same week the Ocean Pact turned one",
        "source": "European Commission, Maritime Affairs and Fisheries, Friday 5 June 2026",
        "snippet": (
            "The Commission published its sustainable-fishing orientations for 2027, the framework that "
            "shapes the autumn proposals on catch limits and quotas before Member States negotiate them. "
            "It reads out progress towards maximum sustainable yield, the health of stocks by sea basin, "
            "and the state of the landing obligation, with the candid line that sustainability is improving "
            "but real challenges remain. It landed in the same week as the first anniversary of the European "
            "Ocean Pact and World Oceans Day, a deliberate framing of the quota debate inside the wider "
            "ocean-governance push rather than as a standalone fisheries file."
        ),
        "ask": "What are the EU's sustainable fishing orientations for 2027 and the European Ocean Pact?",
        "feature_label": "My EU Calendar",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=eu_calendar",
        "color": "#9b51e0",
    },
    {
        "title": "Big pharma's verdict on the animal-testing phase-out",
        "source": "EFPIA, Monday 1 June 2026",
        "snippet": (
            "EFPIA, the research-based pharmaceutical industry's Brussels federation, welcomed the "
            "Commission's roadmap to phase out animal testing for chemical safety assessments. The detail "
            "mainstream coverage skipped: the roadmap sets 22 actions under three pillars and targets 15 "
            "domains, including chemical pharmaceuticals, built on the 3Rs principles of replacement, "
            "reduction, and refinement. EFPIA stresses close work with the European Medicines Agency on "
            "implementation, which is the part that decides whether the ambition reaches the lab bench. "
            "The industry position itself is the signal that a calendar-driven newsletter will miss."
        ),
        "ask": "What is the EU roadmap to phase out animal testing for chemical safety assessments?",
        "feature_label": "Lobby Meetings",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=lobby_meetings",
        "color": "#059669",
    },
    {
        "title": "Europe's biggest finance lobby is backing a delay to the trading-book capital rules",
        "source": "AFME, Thursday 4 June 2026",
        "snippet": (
            "AFME, the Association for Financial Markets in Europe and one of the highest-spending lobbies "
            "in the register, publicly supported the Commission's delegated act on the market-risk framework, "
            "the Fundamental Review of the Trading Book that governs capital for banks' trading desks. The act "
            "keeps the 1 January 2027 start date but adds a multiplier that effectively offsets the capital "
            "increases until 2029, and AFME presses for cross-jurisdiction alignment to avoid fragmentation "
            "for internationally active banks. Who is pushing for the delay, how hard, and through which "
            "instrument is exactly the lobbying-layer intelligence the headline coverage leaves out."
        ),
        "ask": "How active is AFME in lobbying the EU institutions?",
        "feature_label": "Lobby Meetings",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=lobby_meetings",
        "color": "#d97706",
    },
    {
        "title": "The ECB just measured the euro's global standing, and it is quietly gaining",
        "source": "European Central Bank, June 2026",
        "snippet": (
            "The European Central Bank published its annual report on the international role of the euro, "
            "and the headline finding is that the euro's global role increased moderately across reserves, "
            "cross-border payments, and international debt issuance. The report matters less for the level "
            "than for the timing: it lands while the EU is pushing a digital euro, deeper capital markets, "
            "and strategic autonomy, and while the dollar-diversification debate is live. The operational "
            "read is where the euro is actually gaining ground in invoicing and official reserves, and what "
            "that does to the Savings and Investments Union and digital-euro agendas that mainstream "
            "coverage treats as separate stories."
        ),
        "ask": "What does the ECB report on the international role of the euro show?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#dc2626",
    },
    {
        "title": "The EU's annual justice health-check is out, and it is a quiet rule-of-law instrument",
        "source": "European Commission, Thursday 4 June 2026",
        "snippet": (
            "The Commission published the 2026 EU Justice Scoreboard, its yearly comparative read on the "
            "independence, quality, and efficiency of national justice systems. The detail mainstream "
            "coverage skips: the Scoreboard is not just a ranking, it feeds directly into the annual Rule "
            "of Law Report and the European Semester, and perceived judicial independence among citizens "
            "and companies is one of the metrics the Commission tracks against specific Member States. It "
            "is the evidence base that later justifies country-specific recommendations and, in the sharper "
            "cases, the conditionality discussions."
        ),
        "ask": "What is the 2026 EU Justice Scoreboard and what did it find?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#0693e3",
    },
    {
        "title": "The EU told the Western Balkans that enlargement is now a security investment",
        "source": "EU-Western Balkans Summit, Friday 5 June 2026",
        "snippet": (
            "At the EU-Western Balkans Summit the Commission framed enlargement as a strategic investment "
            "in Europe's own peace, stability, and security, the clearest signal yet that the post-2022 "
            "geopolitical logic now drives the accession file. The operational layer mainstream coverage "
            "flattens: the Growth Plan's pre-accession funding is tied to concrete reform milestones, "
            "candidates can access parts of the single market before full membership, and the rule-of-law "
            "fundamentals remain the gating cluster that decides the pace. The politics made the headlines, "
            "the conditionality mechanics did not."
        ),
        "ask": "What did the EU-Western Balkans Summit decide and what is the state of EU enlargement?",
        "feature_label": "Council Watch",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=council_watch",
        "color": "#9b51e0",
    },
    {
        "title": "The EU's auditors checked the youth-jobs billions, and the results are uncomfortable",
        "source": "European Court of Auditors, Friday 5 June 2026",
        "snippet": (
            "The European Court of Auditors published a special report on EU cohesion support for youth "
            "employment, and the candid read is that the spending is hard to show results for. The detail "
            "worth the read: the auditors point to the recurring structural problems across cohesion "
            "instruments, weak targeting, data-quality gaps that make impact hard to measure, and "
            "absorption lagging the political ambition. It lands precisely as the next long-term budget is "
            "being designed, which is exactly when audit findings carry the most leverage over how the "
            "money is reshaped."
        ),
        "ask": "What did the European Court of Auditors find about EU support for youth employment?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#059669",
    },
]


HERO_HTML = """
<p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 12px 0;">
  A committee-week Monday with no plenary, but <strong>eight institutional moves</strong> across the
  Commission, the European Central Bank, the Court of Auditors, and the enlargement track, that the
  mainstream feeds (Politico, Euractiv, Euronews) and the Anglo financial press (FT, Bloomberg,
  Reuters) skipped or flattened. Two of them are the verdicts of Brussels' biggest-spending lobbies,
  the layer that calendar-driven newsletters never aggregate.
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
            Monday 8 June 2026, committee week
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
