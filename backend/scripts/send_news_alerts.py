"""
Targeted News Alert Emails to EU Transparency Register Organisations

Sends policy-relevant EU news to lobby organisations whose sector matches
today's headlines. BCC batch sending (not personalised).

Flow:
  1. Read today's daily brief headlines from DB
  2. Classify each headline into policy clusters (energy, digital, trade, etc.)
  3. Determine which clusters are "hot" (1+ matching headlines)
  4. Build a news alert email per cluster with matching headlines
  5. Send BCC batch to all orgs in that cluster from lobby_orgs_emails.csv

Usage:
    python3.12 scripts/send_news_alerts.py                     # Preview: show clusters + counts
    python3.12 scripts/send_news_alerts.py --send              # Send to all hot clusters
    python3.12 scripts/send_news_alerts.py --send --cluster energy  # Send to one cluster
    python3.12 scripts/send_news_alerts.py --test              # Send all hot clusters to hello@beresol.eu
"""

import argparse
import csv
import logging
import os
import sys
import urllib.parse
from datetime import date
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(message)s")

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

BRUBRU_URL = "https://brubru.beresol.eu"
BRUBRU_CHAT_URL = f"{BRUBRU_URL}/chat"
BRUBRU_SIGNUP_URL = f"{BRUBRU_URL}/signup"
BRUBRU_LOGO = f"{BRUBRU_URL}/assets/brubru_mainlogo.png"

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "emails")
LOBBY_CSV = os.path.join(DATA_DIR, "lobby_orgs_emails.csv")

HEADLINE_HOVER_COLORS = [
    "#0693e3", "#9b51e0", "#059669", "#d97706", "#dc2626",
    "#0693e3", "#9b51e0", "#059669", "#d97706", "#dc2626",
]

# --------------------------------------------------------------------------- #
# Cluster definitions (keywords for headline classification)
# --------------------------------------------------------------------------- #

CLUSTER_HEADLINE_KEYWORDS: Dict[str, List[str]] = {
    "digital": [
        "artificial intelligence", "ai act", "ai regulation", "digital", "data",
        "platform", "dsa", "dma", "gdpr", "cyber", "algorithm", "machine learning",
        "tech", "software", "startup", "cloud", "interoperability", "copyright",
        "genai", "generative ai", "deepfake", "disinformation",
    ],
    "climate": [
        "green deal", "climate", "carbon", "emission", "cbam", "ets",
        "biodiversity", "circular economy", "sustainability", "net zero",
        "deforestation", "pollution", "waste", "nature restoration",
        "environmental", "fit for 55",
    ],
    "finance": [
        "banking", "fintech", "payment", "insurance", "capital market",
        "aml", "money laundering", "crypto", "mica", "psd3", "ecb",
        "financial", "investment", "fiscal", "euro", "monetary",
        "stock", "bond", "credit", "basel",
    ],
    "trade": [
        "trade", "tariff", "customs", "wto", "mercosur", "fta",
        "supply chain", "due diligence", "csddd", "single market",
        "consumer", "product safety", "e-commerce", "competition",
        "antitrust", "state aid", "industrial",
    ],
    "agriculture": [
        "agriculture", "cap", "farm", "food", "pesticide", "fertiliser",
        "organic", "animal welfare", "fisheries", "aquaculture", "gmo",
        "rural", "wine", "grain", "crop", "livestock", "dairy",
    ],
    "health": [
        "health", "pharmaceutical", "medical", "vaccine", "clinical",
        "biotech", "ema", "ehds", "tobacco", "alcohol", "patient",
        "disease", "pandemic", "drug", "therapy", "cancer",
    ],
    "energy": [
        "energy", "renewable", "hydrogen", "nuclear", "solar", "wind",
        "gas", "electricity", "grid", "battery", "repowereu",
        "lng", "oil", "coal", "power", "smr", "clean energy",
        "energy efficiency", "energy package",
    ],
    "transport": [
        "transport", "aviation", "rail", "maritime", "vehicle",
        "electric vehicle", "shipping", "infrastructure", "mobility",
        "road", "port", "airport", "logistics", "freight", "ten-t",
    ],
    "defence": [
        "defence", "defense", "military", "nato", "arms", "security",
        "csdp", "edip", "space", "satellite", "migration", "asylum",
        "border", "frontex", "europol", "terrorism",
    ],
    "social": [
        "employment", "labour", "labor", "pension", "wage", "equality",
        "gender", "disability", "education", "housing", "social",
        "skill", "training", "youth", "child", "erasmus", "platform work",
    ],
    "research": [
        "research", "innovation", "horizon", "quantum", "semiconductor",
        "chips act", "startup", "sme", "patent", "intellectual property",
        "r&d", "science", "university", "academic",
    ],
    "civil_society": [
        "human rights", "democracy", "transparency", "rule of law",
        "ngo", "media freedom", "whistleblower", "anti-corruption",
        "fundamental rights", "civil society", "press freedom",
        "ombudsman", "access to documents",
    ],
}

CLUSTER_NAMES = {
    "digital": "Digital & AI",
    "climate": "Climate & Environment",
    "finance": "Finance & Banking",
    "trade": "Trade & Industry",
    "agriculture": "Agriculture & Food",
    "health": "Health & Pharma",
    "energy": "Energy",
    "transport": "Transport & Mobility",
    "defence": "Defence & Security",
    "social": "Social & Employment",
    "research": "Research & Innovation",
    "civil_society": "Civil Society & Human Rights",
}


# --------------------------------------------------------------------------- #
# Headline classification
# --------------------------------------------------------------------------- #

def classify_headline(headline: str, snippet: str = "") -> List[str]:
    """Classify a headline into one or more policy clusters."""
    text = f"{headline} {snippet}".lower()
    matches = []
    for cluster, keywords in CLUSTER_HEADLINE_KEYWORDS.items():
        for kw in keywords:
            if kw in text:
                matches.append(cluster)
                break
    return matches if matches else []


def get_hot_clusters(headlines: List[dict]) -> Dict[str, List[dict]]:
    """Map today's headlines to clusters. Returns {cluster: [headline_dicts]}."""
    cluster_headlines: Dict[str, List[dict]] = {}
    for h in headlines:
        clusters = classify_headline(h["headline"], h.get("snippet", ""))
        for c in clusters:
            cluster_headlines.setdefault(c, []).append(h)
    return cluster_headlines


# --------------------------------------------------------------------------- #
# Org loading from CSV
# --------------------------------------------------------------------------- #

def load_orgs_by_cluster() -> Dict[str, List[str]]:
    """Load lobby_orgs_emails.csv and classify orgs into clusters. Returns {cluster: [emails]}."""
    if not os.path.exists(LOBBY_CSV):
        logger.error(f"[ERROR] CSV not found: {LOBBY_CSV}")
        return {}

    # Import classify_org from send_lobby_campaign
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from send_lobby_campaign import classify_org

    cluster_emails: Dict[str, List[str]] = {}
    with open(LOBBY_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            email = (row.get("contact_email") or "").strip()
            if not email or "@" not in email:
                continue
            cluster = classify_org(row)
            if cluster and cluster != "other":
                cluster_emails.setdefault(cluster, []).append(email)

    # Deduplicate
    for c in cluster_emails:
        cluster_emails[c] = sorted(set(cluster_emails[c]))

    return cluster_emails


# --------------------------------------------------------------------------- #
# Email template (Daily Brief style, BCC-friendly)
# --------------------------------------------------------------------------- #

def build_news_alert_html(cluster: str, headlines: List[dict], brief_date: str) -> str:
    """Build a news alert email for a specific policy cluster."""
    cluster_name = CLUSTER_NAMES.get(cluster, "EU Policy")

    try:
        d = date.fromisoformat(brief_date)
        formatted_date = d.strftime("%A, %d %B %Y")
    except (ValueError, TypeError):
        formatted_date = brief_date or "Today"

    # Build headline rows
    headline_rows = ""
    for i, h in enumerate(headlines):
        color = HEADLINE_HOVER_COLORS[i % len(HEADLINE_HOVER_COLORS)]
        brubru_link = f"{BRUBRU_CHAT_URL}?q={urllib.parse.quote(h.get('suggested_query', h['headline']))}"
        headline_rows += f"""
    <tr class="headline-row headline-{i}">
      <td style="padding: 12px 0; border-bottom: 1px solid #f3f4f6; border-left: 3px solid transparent; transition: border-color 0.2s;">
        <a href="{h['url']}" class="headline-link-{i}" style="color: #111827; text-decoration: none; font-size: 15px; font-weight: 500; line-height: 1.4;">
          {h['headline']}
        </a>
        <div style="margin-top: 4px; font-size: 12px; color: #9ca3af;">
          <a href="{h['url']}" style="color: #6b7280; text-decoration: underline;">Source</a> &middot;
          <a href="{brubru_link}" style="color: {color}; text-decoration: underline;">Ask Brubru about this</a>
        </div>
      </td>
    </tr>"""

    # Hover CSS
    hover_css = "\n".join(
        f"      .headline-{i} td:hover {{ border-left-color: {HEADLINE_HOVER_COLORS[i % len(HEADLINE_HOVER_COLORS)]} !important; }}\n"
        f"      .headline-{i} td:hover .headline-link-{i} {{ color: {HEADLINE_HOVER_COLORS[i % len(HEADLINE_HOVER_COLORS)]} !important; }}"
        for i in range(len(headlines))
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style type="text/css">
      .cta-btn:hover {{
        background: linear-gradient(135deg, #0693e3 0%, #9b51e0 50%, #059669 100%) !important;
        box-shadow: 0 4px 12px rgba(6, 147, 227, 0.35) !important;
      }}
{hover_css}
  </style>
</head>
<body style="margin: 0; padding: 0; background: #f9fafb; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <div style="max-width: 560px; margin: 0 auto; padding: 32px 16px;">

    <!-- Header -->
    <div style="text-align: center; margin-bottom: 24px;">
      <a href="{BRUBRU_URL}">
        <img src="{BRUBRU_LOGO}" alt="Brubru" style="height: 40px; margin-bottom: 12px;" />
      </a>
      <h1 style="font-size: 20px; font-weight: 600; color: #111827; margin: 0 0 4px 0;">
        {cluster_name}: what happened today in the EU
      </h1>
      <p style="font-size: 13px; color: #9ca3af; margin: 0;">{formatted_date}</p>
    </div>

    <!-- Card -->
    <div style="background: #ffffff; border-radius: 12px; padding: 24px; border: 1px solid #e5e7eb;">
      <p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 20px 0;">
        The EU institutions just moved on {cluster_name.lower()}. Here is what you need to know:
      </p>

      <!-- Headlines -->
      <table width="100%" cellpadding="0" cellspacing="0" style="border-collapse: collapse;">
        {headline_rows}
      </table>

      <!-- Brubru pitch -->
      <div style="margin-top: 20px; padding: 16px; background: #f0f9ff; border-radius: 8px; border: 1px solid #bae6fd;">
        <p style="font-size: 13px; font-weight: 600; color: #0693e3; margin: 0 0 8px 0;">
          What is Brubru?
        </p>
        <p style="font-size: 13px; color: #374151; line-height: 1.5; margin: 0;">
          Brubru is an AI-powered EU policy assistant. It tracks 500+ legislative files, 54 policy guides,
          and 6 institutional calendars. Ask it anything about EU policy, draft amendments,
          generate position papers, and stay ahead of what matters to your organisation.
        </p>
      </div>

      <!-- CTA -->
      <div style="text-align: center; margin-top: 24px;">
        <a href="{BRUBRU_SIGNUP_URL}" class="cta-btn" style="display: inline-block; padding: 12px 28px; background: #0693e3; color: #ffffff; text-decoration: none; border-radius: 8px; font-size: 14px; font-weight: 600; transition: background 0.3s, box-shadow 0.3s;">
          Try Brubru free for 14 days
        </a>
      </div>
    </div>

    <!-- Footer -->
    <div style="text-align: center; margin-top: 16px; padding-top: 16px; border-top: 1px solid #e5e7eb;">
      <p style="font-size: 11px; color: #9ca3af; margin: 0;">
        Brubru by <a href="https://beresol.eu" style="color: #9ca3af;">Beresol</a> &middot; Brussels, Belgium
      </p>
      <p style="font-size: 11px; color: #9ca3af; margin: 8px 0 0 0;">
        You received this because your organisation is registered in the
        <a href="https://ec.europa.eu/transparencyregister/" style="color: #9ca3af;">EU Transparency Register</a>
        and works on {cluster_name.lower()} policy.
        This is a one-time alert, not a subscription.
      </p>
    </div>

  </div>
</body>
</html>"""


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #

def send_cluster_alert(cluster: str, headlines: List[dict], brief_date: str,
                       recipients: List[str], dry_run: bool = True) -> dict:
    """Send news alert BCC batch to a cluster's orgs."""
    from scripts.collect_institution_emails import send_bcc_campaign

    cluster_name = CLUSTER_NAMES.get(cluster, "EU Policy")
    html = build_news_alert_html(cluster, headlines, brief_date)
    subject = f"{cluster_name}: today in the EU ({brief_date})"

    return send_bcc_campaign(
        recipients=recipients,
        subject=subject,
        html_body=html,
        dry_run=dry_run,
    )


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main():
    parser = argparse.ArgumentParser(description="Send targeted news alerts to Transparency Register orgs")
    parser.add_argument("--send", action="store_true", help="Send alerts to matching orgs")
    parser.add_argument("--test", action="store_true", help="Send all hot clusters to hello@beresol.eu")
    parser.add_argument("--cluster", metavar="KEY", help="Only send to this cluster (e.g. energy, digital)")
    parser.add_argument("--top", type=int, default=3,
                        help="Only send to the N hottest clusters, ranked by headline count (default: 3)")
    parser.add_argument("--max-recipients", type=int, default=1500,
                        help="Max total recipients across all clusters (default: 1500, reserves ~500 for daily brief)")
    parser.add_argument("--min-headlines", type=int, default=2,
                        help="Minimum headlines to consider a cluster hot (default: 2)")
    args = parser.parse_args()

    # 1. Fetch today's headlines from DB
    from core.database import SessionLocal
    from models.daily_brief import DailyBrief
    from datetime import timedelta

    db = SessionLocal()
    today = date.today().isoformat()
    items = (
        db.query(DailyBrief)
        .filter(DailyBrief.brief_date == today)
        .order_by(DailyBrief.priority.asc())
        .limit(10)
        .all()
    )
    if not items:
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        items = (
            db.query(DailyBrief)
            .filter(DailyBrief.brief_date == yesterday)
            .order_by(DailyBrief.priority.asc())
            .limit(10)
            .all()
        )
        brief_date = yesterday
    else:
        brief_date = today
    db.close()

    if not items:
        print("[WARN] No headlines found")
        return

    headlines = [
        {
            "headline": i.headline,
            "url": i.url,
            "source": i.source,
            "category": i.category,
            "snippet": i.snippet or "",
            "suggested_query": i.suggested_query or i.headline,
        }
        for i in items
    ]

    # 2. Classify headlines into clusters
    hot_clusters = get_hot_clusters(headlines)

    # Filter by min headlines
    hot_clusters = {c: hs for c, hs in hot_clusters.items() if len(hs) >= args.min_headlines}

    if args.cluster:
        if args.cluster not in hot_clusters:
            print(f"[WARN] Cluster '{args.cluster}' has no matching headlines today")
            return
        hot_clusters = {args.cluster: hot_clusters[args.cluster]}

    if not hot_clusters:
        print(f"[INFO] No clusters with {args.min_headlines}+ headlines today")
        return

    # 3. Load org emails by cluster
    org_clusters = load_orgs_by_cluster()

    # Rank clusters by headline count (descending), then apply --top limit
    ranked = sorted(hot_clusters.items(), key=lambda x: len(x[1]), reverse=True)
    if not args.cluster:
        ranked = ranked[:args.top]

    # Apply --max-recipients cap
    selected_clusters = {}
    cumulative = 0
    for cluster, cluster_headlines in ranked:
        org_count = len(org_clusters.get(cluster, []))
        if cumulative + org_count > args.max_recipients and cumulative > 0:
            break
        selected_clusters[cluster] = cluster_headlines
        cumulative += org_count

    hot_clusters = selected_clusters

    # Display
    print(f"\n  Headlines for {brief_date} ({len(headlines)} items):\n")
    for i, h in enumerate(headlines, 1):
        clusters = classify_headline(h["headline"], h.get("snippet", ""))
        tags = ", ".join(clusters) if clusters else "unclassified"
        print(f"  {i}. {h['headline']}")
        print(f"     Clusters: {tags}\n")

    print(f"  Selected Clusters (top {args.top}, max {args.max_recipients} recipients):\n")
    total_recipients = 0
    for cluster, cluster_headlines in sorted(hot_clusters.items(), key=lambda x: len(x[1]), reverse=True):
        org_count = len(org_clusters.get(cluster, []))
        total_recipients += org_count
        print(f"  [{cluster.upper()}] {CLUSTER_NAMES[cluster]}")
        print(f"    Headlines: {len(cluster_headlines)}, Orgs: {org_count}")
        for h in cluster_headlines:
            print(f"      - {h['headline']}")
        print()

    print(f"  Total emails to send: {total_recipients}")
    print(f"  Gmail budget: ~{args.max_recipients} for alerts + ~200 daily brief = ~{args.max_recipients + 200}/2,000")

    # 4. Send or preview
    if args.test:
        print(f"\n  [TEST] Sending all hot clusters to hello@beresol.eu\n")
        for cluster, cluster_headlines in sorted(hot_clusters.items()):
            cluster_name = CLUSTER_NAMES[cluster]
            html = build_news_alert_html(cluster, cluster_headlines, brief_date)
            subject = f"[TEST] {cluster_name}: today in the EU ({brief_date})"

            from scripts.collect_institution_emails import send_bcc_campaign
            send_bcc_campaign(
                recipients=["hello@beresol.eu"],
                subject=subject,
                html_body=html,
                dry_run=False,
            )
            print(f"  [OK] Test sent: {cluster_name}")
        print()
        return

    if args.send:
        print(f"\n  [SEND] Sending alerts to {total_recipients} recipients across {len(hot_clusters)} clusters\n")
        total_sent = 0
        total_failed = 0
        for cluster, cluster_headlines in sorted(hot_clusters.items()):
            recipients = org_clusters.get(cluster, [])
            if not recipients:
                print(f"  [{cluster.upper()}] No orgs with emails, skipping")
                continue
            result = send_cluster_alert(
                cluster, cluster_headlines, brief_date,
                recipients=recipients, dry_run=False,
            )
            total_sent += result.get("sent", 0)
            total_failed += result.get("failed", 0)
            print(f"  [{cluster.upper()}] Sent: {result.get('sent', 0)}, Failed: {result.get('failed', 0)}")

        print(f"\n  [DONE] Total sent: {total_sent}, Failed: {total_failed}\n")
    else:
        print(f"\n  Run with --send to deliver, or --test for hello@beresol.eu\n")


if __name__ == "__main__":
    main()
