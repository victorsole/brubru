"""
Brubru Brief issue: Friday 12 June 2026 (Migration and Asylum Pact enters into application).

Format per `memory/feedback_brubru_brief_new_format.md` (11 May 2026) and
modelled on `send_brubru_brief_2026_06_08.py`.

- Subject: "Brubru Brief: What nobody else tells you about the EU Bubble - Friday 12 June 2026"
- Hero: the Pact enters into application today, plus the week's other institutional moves,
  with operational depth mainstream press flattens (the missing returns leg, the voluntary
  vs binding AI label duty, the not-yet-in-force Korea deal, the committee-room EDPB red line).
- 4 headlines, each: title + 2-3 sentence snippet + Ask Brubru + Go to feature + Source
- No em-dashes, no emojis, no institutional codes in lead (treaty articles + popular acronyms OK)

Usage:
    python3.12 scripts/send_brubru_brief_2026_06_12.py --test         # to hello@beresol.eu
    python3.12 scripts/send_brubru_brief_2026_06_12.py --preview      # show recipient counts
    python3.12 scripts/send_brubru_brief_2026_06_12.py --send-base    # base subscribers (live)
    python3.12 scripts/send_brubru_brief_2026_06_12.py --send-eutr    # matched EUTR orgs (live)
    python3.12 scripts/send_brubru_brief_2026_06_12.py --send-all     # both pools (live)
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
            "metadata": '{{"email": "{e}", "org_name": "{o}", "policy_cluster": "{c}", "issue": "2026-06-12"}}'.format(
                e=email.replace('"', ''),
                o=(org_name or '').replace('"', ''),
                c=(policy_cluster or '').replace('"', ''),
            ),
            "ts": _dt.utcnow(),
        }
    )


SUBJECT = "Brubru Brief: What nobody else tells you about the EU Bubble - Friday 12 June 2026"
BRUBRU_CHAT = "https://brubru.beresol.eu/main"


HEADLINE_CLUSTERS = {
    "migration_pact": ["civil_society", "social"],
    "ai_labelling": ["digital"],
    "korea_dta": ["trade", "digital"],
    "edpb_omnibus": ["digital", "civil_society"],
    "defence_simplification": ["defence"],
    "budget_2027": ["finance", "civil_society"],
    "eppo_fraud": ["civil_society", "finance"],
    "eusf": ["climate", "social"],
    "islands_coastal": ["climate", "social"],
    "cbam": ["climate", "trade"],
    "gi_food": ["agriculture", "trade"],
    "amif": ["civil_society", "social"],
}


HEADLINES = [
    {
        "title": "The EU's biggest asylum overhaul in a decade goes live today, without its returns engine",
        "source": "European Commission, Migration and Home Affairs, Friday 12 June 2026",
        "snippet": (
            "From today the EU Pact on Migration and Asylum enters into application across Member States, "
            "the largest reshaping of European asylum law since the Common European Asylum System. In practice "
            "that means mandatory screening of irregular arrivals within seven days at external borders and "
            "three inland, faster harmonised asylum procedures, EU-wide reception standards with free legal "
            "counselling, a mandatory needs-based solidarity mechanism that auto-activates when a Member State "
            "is overwhelmed, and the recast Eurodac biometric database now live. The operational gap the "
            "headlines skip: the returns leg, the part meant to fix the roughly four in five return decisions "
            "that are never enforced, is still stuck in trilogue and is not part of what takes effect today, "
            "and Hungary and Poland continue to refuse to apply the framework while their challenges run at "
            "the Court of Justice."
        ),
        "ask": "What changes now that the EU Migration and Asylum Pact applies?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#0693e3",
    },
    {
        "title": "The EU's rulebook for labelling AI content is here, and it is voluntary",
        "source": "European Commission, Digital Strategy, Wednesday 10 June 2026",
        "snippet": (
            "On 10 June the Commission published a Code of Practice to mark and label AI-generated content: "
            "labelling deepfakes, flagging manipulated public-interest text, telling users when they are "
            "talking to a chatbot, and machine-readable tags for synthetic audio, images, video, and text. "
            "The detail the coverage flattens: it is guidance, not law. The binding transparency duty, the one "
            "that actually carries enforcement weight under the AI Act, only starts on 2 August 2026. The Code "
            "is the operational bridge the Commission is offering companies in the meantime, and adopting it "
            "early is a compliance choice firms can make now."
        ),
        "ask": "What does the EU AI Act require for labelling AI-generated content?",
        "feature_label": "EU Law Comply",
        "feature_url": "https://brubru.beresol.eu/eu-law-comply",
        "color": "#9b51e0",
    },
    {
        "title": "The EU signed only its second-ever standalone digital trade deal, this time with Korea",
        "source": "European Commission, Trade and Economic Security, Wednesday 10 June 2026",
        "snippet": (
            "At the eleventh EU-Korea Summit on 10 June the two sides signed a standalone digital trade "
            "agreement, only the EU's second after Singapore: guaranteed cross-border data flows, no forced "
            "disclosure of source code, recognition of e-contracts and e-signatures, and online consumer "
            "protection. The caveat mainstream coverage flattens: it is signed, not in force. Parliament still "
            "has to give its consent before the Council can conclude it, so the legal clock has not started and "
            "the commitments are not yet enforceable. It builds on the EU-Korea trade agreement that has been "
            "running since 2011."
        ),
        "ask": "What is the EU-Korea Digital Trade Agreement?",
        "feature_label": "Council Watch",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=council_watch",
        "color": "#059669",
    },
    {
        "title": "Europe's privacy chief drew a red line through the simplification drive",
        "source": "European Parliament, civil liberties committee, Monday 8 June 2026",
        "snippet": (
            "At the Parliament's civil-liberties committee on 8 June, the chair of the European Data Protection "
            "Board, Anu Talus, backed much of the EU's digital simplification push but firmly rejected one "
            "piece: rewriting the legal definition of personal data. She reminded MEPs that national "
            "authorities issued 1.1 billion euro in data-protection fines in 2025, and argued that practical "
            "guidance on the recent court rulings, not surgery on the GDPR text, is the safer path to legal "
            "certainty. This is the committee-room layer that no calendar-driven newsletter transcribes, taken "
            "from the meeting webstream."
        ),
        "ask": "What is the EDPB position on the Digital Omnibus?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#d97706",
    },
    {
        "title": "Defence permits will run on a 42-day clock",
        "source": "European Parliament and Council negotiators, Monday 8 June 2026",
        "snippet": (
            "Parliament and Council negotiators provisionally agreed a defence simplification package that sets "
            "a default 42-working-day deadline for permit decisions on defence-readiness projects, alongside "
            "easier intra-EU transfers of defence products, lighter procurement, and smoother investment. The "
            "part the political coverage skips: this is provisional, both co-legislators still have to formally "
            "adopt it, and the 42-day clock is a hard administrative commitment Member States will have to "
            "resource. It sits inside the wider push to spend up to 800 billion euro on European defence "
            "readiness this decade."
        ),
        "ask": "What is the EU doing to simplify defence procurement?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#dc2626",
    },
    {
        "title": "The first numbers on the EU's 2027 budget are out, and the fights are already visible",
        "source": "European Commission, draft budget presentation, Wednesday 10 June 2026",
        "snippet": (
            "The Commission presented its draft EU budget for 2027, the annual spending plan that Parliament "
            "and Council now negotiate line by line before the year starts. The operational layer mainstream "
            "coverage flattens: this draft is the last annual budget built under the current long-term "
            "framework, so every margin and flexibility instrument is being read as a signal for the far "
            "bigger post-2027 framework fight that is starting in parallel. Where the Commission puts the "
            "headroom now is where the leverage sits later."
        ),
        "ask": "What is in the draft EU budget for 2027?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#0693e3",
    },
    {
        "title": "Europe's own prosecutor is chasing recovery-fund money in Italy",
        "source": "European Public Prosecutor's Office, June 2026",
        "snippet": (
            "The European Public Prosecutor's Office opened an investigation into suspected fraud involving "
            "recovery and resilience funding in Italy, the latest in a steady stream of cases the EU's own "
            "prosecutor is building against misuse of post-pandemic money. The point a calendar newsletter "
            "misses: the EPPO is a standing institution that investigates and prosecutes crimes against the "
            "EU budget directly, across participating Member States, rather than leaving it to national "
            "authorities alone. The recovery fund, with its scale and speed, is exactly the spending the "
            "office was built to watch."
        ),
        "ask": "What is the European Public Prosecutor's Office?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#9b51e0",
    },
    {
        "title": "The EU is sending 144 million euro to three countries hit by climate disasters",
        "source": "European Commission, Regional and Urban Policy, Friday 12 June 2026",
        "snippet": (
            "The Commission proposed 144 million euro from the European Union Solidarity Fund to help Spain, "
            "Romania, and Cyprus recover from climate-driven disasters. The mechanics worth knowing: the "
            "Solidarity Fund is the EU's standing instrument for major natural disasters, it is mobilised "
            "after a Member State request and a damage assessment, and the money is reconstruction support, "
            "not insurance. With climate-driven events rising, the Fund is being called on more often, which "
            "is the slow-burn budgetary story underneath each individual allocation."
        ),
        "ask": "What is the European Union Solidarity Fund?",
        "feature_label": "My EU Calendar",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=eu_calendar",
        "color": "#059669",
    },
    {
        "title": "The EU just wrote its first-ever strategy for islands and coastal communities",
        "source": "European Commission, June 2026",
        "snippet": (
            "The Commission set out its first dedicated strategies for the EU's islands and coastal "
            "communities, the places that carry the sharpest version of the connectivity, energy-cost, "
            "depopulation, and climate-exposure problems. The detail mainstream coverage skips: a strategy is "
            "not money, it is a framing document that decides which existing instruments, from cohesion funds "
            "to state-aid flexibility, get pointed at these regions, and which Commissioner owns the follow "
            "through. The test is whether it survives contact with the next budget."
        ),
        "ask": "What is the EU doing for islands and coastal communities?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#d97706",
    },
    {
        "title": "The EU's carbon border levy is moving from theory to the loading dock",
        "source": "European Commission, Taxation and Customs Union, Thursday 11 June 2026",
        "snippet": (
            "The Commission ran a follow-up session on making decarbonisation pay off under the Carbon Border "
            "Adjustment Mechanism, the levy that puts a carbon price on imports of steel, aluminium, cement, "
            "fertilisers, hydrogen, and electricity. The operational reality importers are now facing: the "
            "definitive regime means buying certificates tied to the embedded emissions of what they import, "
            "so the question shifts from whether CBAM exists to how a company actually measures, reports, and "
            "prices the carbon in its supply chain. That is the compliance work that lands on procurement "
            "teams, not press offices."
        ),
        "ask": "What is the EU Carbon Border Adjustment Mechanism?",
        "feature_label": "EU Law Comply",
        "feature_url": "https://brubru.beresol.eu/eu-law-comply",
        "color": "#dc2626",
    },
    {
        "title": "Protecting the name on the label: the EU keeps adding to its food-origin register",
        "source": "European Commission, Agriculture and Rural Development, Thursday 11 June 2026",
        "snippet": (
            "The Commission reiterated how it protects local food and drink names, the geographical-indication "
            "system that ties products like specific cheeses, hams, and wines to their place of origin. The "
            "layer worth knowing: the recently reformed regime strengthens protection online and gives "
            "producer groups more power to police misuse, and the register keeps growing week by week as new "
            "protected designations of origin and protected geographical indications are added. For producers "
            "it is an enforceable property right, not a marketing badge."
        ),
        "ask": "How does the EU protect geographical indications such as PDO and PGI?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#0693e3",
    },
    {
        "title": "The next fight over migration money is starting in committee",
        "source": "European Parliament, civil liberties committee, June 2026",
        "snippet": (
            "As the Pact goes live, Parliament's civil-liberties committee is already working on the migration "
            "fund that will pay for it after 2027, with the lead MEP pushing to restore integration as the "
            "fund's first objective rather than returns. The signal under the procedure: where the money is "
            "weighted, between integration, asylum systems, and returns, is where the political balance of the "
            "whole migration policy actually gets set, well before any plenary vote. The committee text is the "
            "leading indicator the daily feeds will not carry."
        ),
        "ask": "What is the Asylum, Migration and Integration Fund?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#9b51e0",
    },
]


HERO_HTML = """
<p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 12px 0;">
  Today the EU's <strong>Migration and Asylum Pact enters into application</strong>, the biggest overhaul
  of European asylum law in a decade. Around it, <strong>eleven more institutional moves</strong> across
  the Commission, the Parliament, the prosecutor's office, and the budget track that the mainstream feeds
  (Politico, Euractiv, Euronews) and the Anglo financial press (FT, Bloomberg, Reuters) either skipped or
  flattened: a voluntary AI-labelling code that is not the binding duty, a Korea digital-trade deal that is
  signed but not in force, a privacy-chief red line drawn inside a committee room, a defence permit clock, the
  first numbers on the 2027 budget, and the committee fight over migration money that has already begun.
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
            Friday 12 June 2026, the Pact goes live
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
