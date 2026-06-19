"""
Brubru Brief issue: Friday 19 June 2026 (EP June plenary week in review + European Council).

Format per `memory/feedback_brubru_brief_new_format.md` (11 May 2026) and
modelled on `send_brubru_brief_2026_06_08.py`.

- Subject: "Brubru Brief: What nobody else tells you about the EU Bubble - Friday 19 June 2026"
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
            "metadata": '{{"email": "{e}", "org_name": "{o}", "policy_cluster": "{c}", "issue": "2026-06-19"}}'.format(
                e=email.replace('"', ''),
                o=(org_name or '').replace('"', ''),
                c=(policy_cluster or '').replace('"', ''),
            ),
            "ts": _dt.utcnow(),
        }
    )


SUBJECT = "Brubru Brief: What nobody else tells you about the EU Bubble - Friday 19 June 2026"
BRUBRU_CHAT = "https://brubru.beresol.eu/main"


HEADLINE_CLUSTERS = {
    "ai_omnibus": ["digital"],
    "elv": ["climate"],
    "euco_enlargement": ["finance", "civil_society"],
    "balkans_reports": ["civil_society"],
    "rrf_digital": ["digital", "finance"],
    "return_regulation": ["civil_society", "social"],
    "tech_sovereignty": ["digital"],
    "children_crime": ["civil_society", "social"],
    "transport_electrification": ["climate"],
}


HEADLINES = [
    {
        "title": "The EU just put its AI rulebook on a fixed clock, and pushed the hardest rules to 2027",
        "source": "European Parliament press-room, Tuesday 16 June 2026",
        "snippet": (
            "On Tuesday the Parliament adopted the AI Act simplification package by 423 votes to 57. "
            "Mainstream coverage frames it as a delay; the operational change is that the high-risk "
            "deadlines are now fixed calendar dates instead of the Commission's earlier conditional "
            "trigger. Standalone high-risk systems, the ones used in recruitment, credit scoring, "
            "biometrics, critical infrastructure, education and border control, must comply by 2 December "
            "2027; AI built into regulated products such as medical devices, machinery and vehicles by 2 "
            "August 2028; content watermarking by 2 December 2026. The same text writes a new prohibition "
            "into the AI Act: tools that generate non-consensual intimate imagery or child sexual abuse "
            "material are banned, with compliance due by 2 December 2026. Only the Council's formal sign-off "
            "now remains."
        ),
        "ask": "What are the new AI Act high-risk deadlines after the 2026 simplification package?",
        "feature_label": "EU Law Comply",
        "feature_url": "https://brubru.beresol.eu/eu-law-comply",
        "color": "#0693e3",
    },
    {
        "title": "Europe rewrote the rules for scrapping a car, and banned repair-blocking software",
        "source": "European Parliament press-room, Thursday 18 June 2026",
        "snippet": (
            "On Thursday the Parliament gave final approval, by 437 votes to 112, to the vehicle-circularity "
            "regulation, merging two ageing directives into one rulebook covering a car's whole life. The "
            "detail the political coverage skips: carmakers must design new vehicles so parts come out easily "
            "for reuse and recycling, hit recycled-plastic content targets, and they are barred from pushing "
            "software updates that block repairs, a direct hit at planned obsolescence. Used cars may only be "
            "exported if roadworthy, with tighter customs checks to stop write-offs leaving the EU dressed as "
            "working vehicles. The timeline diverges by vehicle type: cars and vans get about a year after "
            "entry into force, while lorries, buses and motorcycles get five, with military, emergency and "
            "heritage vehicles carved out."
        ),
        "ask": "What are the new EU end-of-life vehicles circularity rules?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#9b51e0",
    },
    {
        "title": "Ukraine and Moldova opened the first chapter of EU membership, as leaders met in Brussels",
        "source": "European Council, Brussels, 18-19 June 2026",
        "snippet": (
            "At this week's European Council, EU leaders welcomed the opening on 15 June of the first "
            "negotiating cluster, the fundamentals, with both Ukraine and Moldova, the substantive start of "
            "their accession tracks. What the summit coverage compresses is that the budget machinery moved "
            "in parallel: days earlier the Council agreed partial general approaches on three building blocks "
            "of the next long-term budget for 2028 to 2034, the national and regional partnership plans, the "
            "European Competitiveness Fund, and the external-action instrument, while leaders debated a "
            "revised negotiating box and the new own-resources package. The budget needs unanimity, and the "
            "net-contributor versus cohesion split is already visible."
        ),
        "ask": "Where do the EU 2028 to 2034 budget negotiations and enlargement stand?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#059669",
    },
    {
        "title": "Parliament named the two countries most likely to be the EU's next members",
        "source": "European Parliament press-room, Wednesday 17 June 2026",
        "snippet": (
            "The Parliament adopted its annual progress reports on Montenegro and Albania, and the framing "
            "matters more than the votes. Montenegro is treated as the front-runner, on track to close "
            "accession negotiations by the end of 2026 and join as the 28th Member State by 2028; Albania is "
            "praised for aiming to close talks by the end of 2027. The reports land the same week the "
            "European Council takes up enlargement, and they tie continued progress to rule-of-law alignment "
            "and the milestones that unlock Reform and Growth Facility money for the Western Balkans, the "
            "conditionality that mainstream coverage rarely spells out."
        ),
        "ask": "Which Western Balkans countries are closest to joining the EU?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#d97706",
    },
    {
        "title": "The EU's recovery fund quietly became a digital investment engine worth 219 billion euro",
        "source": "Joint Research Centre, Wednesday 17 June 2026",
        "snippet": (
            "A new Joint Research Centre technical report put a number on something the recovery-fund debate "
            "usually leaves vague: the digital investments financed through the EU's post-pandemic recovery "
            "plan are estimated to generate around 219 billion euro in economic returns. The detail worth "
            "holding onto is where the money went, into connectivity, digital public services, and the "
            "digital skills and business uptake the Commission counts toward its Digital Decade targets, "
            "rather than the headline infrastructure projects. As the recovery facility heads toward its 2026 "
            "spending deadline, the JRC estimate becomes a reference point for the fight over what replaces it "
            "in the next budget."
        ),
        "ask": "What economic return are the digital investments in the EU recovery plan expected to generate?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#dc2626",
    },
    {
        "title": "The EU is building one return system to replace 27, and it allows return hubs outside Europe",
        "source": "European Parliament, Civil Liberties Committee, week of 15 June 2026",
        "snippet": (
            "Parliament advanced its work this week on the new Return Regulation, the law meant to replace the "
            "patchwork left by the 2008 Returns Directive with a single EU-wide procedure. The operational "
            "shift the headlines miss: a return decision issued by one Member State would be mutually "
            "recognised and enforceable across the others, ending the practice of moving country to reset the "
            "clock, and the text opens the door to return hubs in third countries for people with no right to "
            "stay. It is the enforcement leg deliberately left out of the Migration and Asylum Pact that began "
            "applying last week, and it is still moving through the Parliament rather than adopted."
        ),
        "ask": "What is the EU's new Return Regulation and how does it change deportations?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#0693e3",
    },
    {
        "title": "MEPs pushed the Commission to turn its tech-sovereignty talk into money and rules",
        "source": "European Parliament plenary debate, Tuesday 16 June 2026",
        "snippet": (
            "On Tuesday MEPs debated the EU's tech-sovereignty package with the Commission, pressing on the "
            "gap between ambition and delivery. The thread mainstream coverage drops: the debate tied together "
            "the simplification drives already moving across chemicals, defence and artificial intelligence "
            "with the question of how the next budget will actually fund European capacity in chips, cloud and "
            "AI, rather than treating sovereignty as a slogan. It set the tone for the One Europe, one market "
            "roadmap that leaders took up at the European Council two days later."
        ),
        "ask": "What is the EU tech sovereignty package?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#9b51e0",
    },
    {
        "title": "Parliament set out how it wants to stop crime networks recruiting children online",
        "source": "European Parliament press-room, Thursday 18 June 2026",
        "snippet": (
            "In a resolution adopted on Thursday, MEPs laid out proposals to counter the recruitment of "
            "children by organised crime, including the recruitment that now happens through social media and "
            "messaging apps. The detail beyond the headline: the text presses for prevention, cross-border "
            "police cooperation and support for the children pulled into drug-running and other criminal "
            "activity, treating them as victims rather than only offenders, and connects to the EU's wider "
            "online-safety and child-protection work. It lands the same plenary week as the AI law's new ban "
            "on child sexual abuse material generators."
        ),
        "ask": "What is the EU doing to stop organised crime recruiting children?",
        "feature_label": "Research and Evidence",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=research_evidence",
        "color": "#059669",
    },
    {
        "title": "Europe's plan to electrify transport ran straight into the energy-price debate",
        "source": "European Parliament plenary debate, week of 15 June 2026",
        "snippet": (
            "MEPs debated the resilience of the transport sector this week and heard the Commission set out "
            "its action plan to boost the use of clean electricity in transport. What the coverage flattens: "
            "the push to electrify cars, lorries and rail collides with the ongoing pressure on energy prices, "
            "and the action plan has to answer how electrification stays affordable for hauliers and "
            "households at the same time as the grid build-out the EU is funding through its energy networks "
            "package. It is the demand-side companion to the supply-side grid debate."
        ),
        "ask": "What is the EU doing to electrify the transport sector?",
        "feature_label": "Legislative Tracker",
        "feature_url": "https://brubru.beresol.eu/my-eu-bubble?tab=legislative",
        "color": "#d97706",
    },
]


HERO_HTML = """
<p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 12px 0;">
  The European Parliament closed its June session in Strasbourg this week with <strong>two laws adopted</strong>,
  a fixed new timetable for the AI Act and a circular-economy rulebook for cars, while EU leaders met in Brussels
  for the European Council. Below are <strong>nine outcomes</strong> from the week that the mainstream feeds
  (Politico, Euractiv, Euronews) and the Anglo financial press (FT, Bloomberg, Reuters) either skipped or
  flattened: the binding AI deadlines that replaced a conditional trigger, the repair-blocking software ban
  inside the vehicle law, the budget building blocks moving under the enlargement headlines, and a research
  number that reframes the recovery fund.
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
            Friday 19 June 2026, the plenary week in review
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
