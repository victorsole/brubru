"""Draft the Dutch startups outreach campaign.

Reads data/outreach/dutch_startups_2026_05_20.csv, builds a bilingual
(Dutch + English) email per startup using a shared master template
plus a personalised paragraph derived from each row.

Modes:
  --review    -> write all 41 emails to data/outreach/dutch_startups_emails_2026_05_20.md
  --test      -> send ONE example email (Sustalium row) to hello@beresol.eu via SMTP
  --send-all  -> reserved; not implemented yet, requires explicit user OK

Rules honoured:
  - load_dotenv() at module top (memory: feedback_send_script_dotenv_required.md)
  - SMTP_PASSWORD env var name
  - No em-dashes anywhere in the email body (CLAUDE.md hard rule + user instruction)
  - British English in the English block
  - One CTA per email (https://brubru.beresol.eu/main)
  - Founder name with accent: Victor Sole Ferioli (HTML entity in display name)
  - Reply STOP instruction for opt-out (GDPR Article 21)
"""
from __future__ import annotations

import argparse
import csv
import os
import smtplib
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

CSV_PATH = _ROOT / "data" / "outreach" / "dutch_startups_2026_05_20.csv"
REVIEW_MD = _ROOT / "data" / "outreach" / "dutch_startups_emails_2026_05_20.md"
TEST_RECIPIENT = "hello@beresol.eu"
SENDER_NAME = "Victor Sole Ferioli"
SENDER_EMAIL = "victor@beresol.eu"

SECTOR_NL = {
    "SaaS-tools": "SaaS-bedrijven",
    "fintech": "fintechbedrijven",
    "cybersecurity": "cybersecuritybedrijven",
    "climate-tech": "climate-techbedrijven",
    "agritech": "agritechbedrijven",
    "marketplace": "marktplaatsen",
    "logistics": "logistieke bedrijven",
    "biotech": "biotechbedrijven",
    "edtech": "edtechbedrijven",
    "mobility": "mobiliteitsbedrijven",
    "real-estate-tech": "vastgoedtechbedrijven",
    "deeptech-AI": "deeptech AI-bedrijven",
}

SECTOR_EN = {
    "SaaS-tools": "SaaS companies",
    "fintech": "fintech companies",
    "cybersecurity": "cybersecurity companies",
    "climate-tech": "climate-tech companies",
    "agritech": "agritech companies",
    "marketplace": "marketplaces",
    "logistics": "logistics companies",
    "biotech": "biotech companies",
    "edtech": "edtech companies",
    "mobility": "mobility companies",
    "real-estate-tech": "real-estate-tech companies",
    "deeptech-AI": "deep-tech AI companies",
}


def split_laws(eu_laws_field: str) -> list[str]:
    """Split the comma-separated EU laws field into a clean list."""
    if not eu_laws_field:
        return []
    return [law.strip() for law in eu_laws_field.split(",") if law.strip()]


def top_laws(laws: list[str], n: int = 3) -> list[str]:
    return laws[:n]


def hook_nl(row: dict) -> str:
    """Two-line personalised hook in Dutch."""
    sector_nl = SECTOR_NL.get(row["sector"], row["sector"] + "-bedrijven")
    laws = split_laws(row["eu_laws_related"])
    return (
        f"We zijn het Nederlandse startup-ecosysteem in kaart aan het brengen "
        f"en {row['name']} viel ons op. Voor {sector_nl} zoals jullie zijn "
        f"de volgende EU-wetten doorgaans direct relevant:"
    )


def hook_en(row: dict) -> str:
    """Two-line personalised hook in British English."""
    sector_en = SECTOR_EN.get(row["sector"], row["sector"] + " companies")
    return (
        f"We have been mapping the Dutch startup ecosystem and {row['name']} caught "
        f"our eye. For {sector_en} like yours, the following EU laws typically apply right now:"
    )


def laws_bullet_block(laws: list[str]) -> str:
    """HTML bullet list of laws."""
    if not laws:
        return ""
    items = "\n".join(f"        <li>{law}</li>" for law in laws)
    return f"      <ul>\n{items}\n      </ul>"


def build_subject(row: dict) -> str:
    laws = split_laws(row["eu_laws_related"])
    n = len(laws)
    return f"{n} EU-wetten die {row['name']} raken / {n} EU laws that affect {row['name']}"


def build_html_body(row: dict) -> str:
    laws = top_laws(split_laws(row["eu_laws_related"]), n=5)
    laws_block = laws_bullet_block(laws)

    nl_block = f"""
    <p>Hallo {row['name']} team,</p>

    <p>Mijn naam is Victor Sole Ferioli, oprichter van Brubru (Beresol BV, Apeldoorn).
    {hook_nl(row)}</p>

{laws_block}

    <p>Brubru is een AI-assistent die EU-beleid en wetgeving uitlegt in begrijpelijke taal
    en koppelt aan de dagelijkse beslissingen van een startup. We hebben 246 expertgidsen,
    28.500+ EU-wetten gei&iuml;ndexeerd, een Comply-tool die verplichtingen op &eacute;&eacute;n
    blik laat zien, en een Tenderator voor EU-aanbestedingen en subsidies.</p>

    <p>Wil je het zelf eens proberen? Stel Brubru een vraag over &eacute;&eacute;n van bovenstaande
    wetten en zie wat er gebeurt:<br>
    &raquo; <a href="https://brubru.beresol.eu/main">https://brubru.beresol.eu/main</a></p>

    <p>Met vriendelijke groet,<br>
    Victor Sol&eacute; Ferioli<br>
    Founder, Brubru / Beresol BV<br>
    <a href="mailto:victor@beresol.eu">victor@beresol.eu</a></p>
"""

    en_block = f"""
    <p>Hi {row['name']} team,</p>

    <p>I am Victor Sole Ferioli, founder of Brubru (Beresol BV, based in Apeldoorn).
    {hook_en(row)}</p>

{laws_block}

    <p>Brubru is an AI assistant that explains EU policy and legislation in plain language
    and links it to the day-to-day decisions of a startup. We carry 246 expert guides,
    28,500+ EU laws indexed, a Comply tool that surfaces your obligations at a glance,
    and a Tenderator for EU procurement and grant opportunities.</p>

    <p>Want to try it? Ask Brubru anything about one of the laws above and see what comes back:<br>
    &raquo; <a href="https://brubru.beresol.eu/main">https://brubru.beresol.eu/main</a></p>

    <p>Kind regards,<br>
    Victor Sol&eacute; Ferioli<br>
    Founder, Brubru / Beresol BV<br>
    <a href="mailto:victor@beresol.eu">victor@beresol.eu</a></p>

    <p style="color:#888;font-size:12px;">
    PS: To stop receiving emails from Brubru, reply with "STOP" and we will remove you from our list.
    </p>
"""

    return f"""<html>
<body style="font-family: Georgia, serif; max-width: 640px; margin: 24px auto; color: #1a1a1a; line-height: 1.55;">
{nl_block}

  <hr style="border:0;border-top:1px solid #ddd;margin:24px 0;">

{en_block}
</body>
</html>"""


def build_plain_body(row: dict) -> str:
    """Plain-text fallback (some clients prefer it)."""
    laws = top_laws(split_laws(row["eu_laws_related"]), n=5)
    laws_text = "\n".join(f"  - {law}" for law in laws)

    return f"""Hallo {row['name']} team,

Mijn naam is Victor Sole Ferioli, oprichter van Brubru (Beresol BV, Apeldoorn).
{hook_nl(row)}

{laws_text}

Brubru is een AI-assistent die EU-beleid en wetgeving uitlegt in begrijpelijke taal
en koppelt aan de dagelijkse beslissingen van een startup. We hebben 246 expertgidsen,
28.500+ EU-wetten geindexeerd, een Comply-tool die verplichtingen op een blik laat zien,
en een Tenderator voor EU-aanbestedingen en subsidies.

Wil je het zelf eens proberen? Stel Brubru een vraag over een van bovenstaande wetten:
  https://brubru.beresol.eu/main

Met vriendelijke groet,
Victor Sole Ferioli
Founder, Brubru / Beresol BV
victor@beresol.eu

---

Hi {row['name']} team,

I am Victor Sole Ferioli, founder of Brubru (Beresol BV, based in Apeldoorn).
{hook_en(row)}

{laws_text}

Brubru is an AI assistant that explains EU policy and legislation in plain language
and links it to the day-to-day decisions of a startup. We carry 246 expert guides,
28,500+ EU laws indexed, a Comply tool that surfaces your obligations at a glance,
and a Tenderator for EU procurement and grant opportunities.

Want to try it? Ask Brubru anything about one of the laws above and see what comes back:
  https://brubru.beresol.eu/main

Kind regards,
Victor Sole Ferioli
Founder, Brubru / Beresol BV
victor@beresol.eu

PS: To stop receiving emails from Brubru, reply with "STOP" and we will remove you from our list.
"""


def assert_no_em_dashes(text: str, label: str) -> None:
    """Hard rule from user + CLAUDE.md."""
    if "—" in text or "–" in text:
        raise SystemExit(f"[ERROR] em-dash or en-dash detected in {label}; aborting.")


def load_rows() -> list[dict]:
    with CSV_PATH.open() as f:
        return list(csv.DictReader(f))


def write_review(rows: list[dict]) -> None:
    REVIEW_MD.parent.mkdir(parents=True, exist_ok=True)
    out = ["# Dutch startups outreach -- 41 personalised emails", "",
           "Master template: bilingual Dutch + English, no em-dashes.",
           "Per-startup variables: name, sector, EU laws (top 5).",
           "Test send target: hello@beresol.eu (Sustalium row).", "",
           f"Generated from `data/outreach/dutch_startups_2026_05_20.csv` ({len(rows)} rows).",
           "", "---", ""]

    for i, row in enumerate(rows, 1):
        subject = build_subject(row)
        plain = build_plain_body(row)
        assert_no_em_dashes(subject + plain, f"row {i} {row['name']}")
        out.append(f"## {i}. {row['name']} ({row['city']}, {row['sector']})")
        out.append("")
        out.append(f"- **Email:** `{row['email'] or '(no verified address)'}`")
        out.append(f"- **Website:** {row['website']}")
        out.append(f"- **Subject:** {subject}")
        out.append("")
        out.append("```")
        out.append(plain)
        out.append("```")
        out.append("")
        out.append("---")
        out.append("")

    REVIEW_MD.write_text("\n".join(out))
    print(f"[OK] wrote review file: {REVIEW_MD}")
    print(f"     {len(rows)} merged emails ready for inspection")


def send_test(rows: list[dict]) -> None:
    # Pick Sustalium as the test merge example
    target_row = next((r for r in rows if r["name"] == "Sustalium"), None)
    if target_row is None:
        print("[ERROR] Sustalium row not found in CSV; aborting test send.")
        sys.exit(1)

    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    if not (host and user and password):
        print("[ERROR] SMTP_HOST / SMTP_USER / SMTP_PASSWORD missing in .env; aborting.")
        sys.exit(1)

    subject = "[TEST -- Sustalium row] " + build_subject(target_row)
    html_body = build_html_body(target_row)
    plain_body = build_plain_body(target_row)
    assert_no_em_dashes(subject + plain_body + html_body, "test send")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    msg["To"] = TEST_RECIPIENT
    msg["Reply-To"] = SENDER_EMAIL
    msg.attach(MIMEText(plain_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    print(f"[INFO] connecting to {host}:{port} as {user}")
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(user, password)
        s.send_message(msg)
    print(f"[OK] test email sent to {TEST_RECIPIENT}")
    print(f"     subject: {subject}")
    print(f"     merge data: row for {target_row['name']} ({target_row['email']})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--review", action="store_true", help="write the 41-email review markdown")
    ap.add_argument("--test", action="store_true", help="send ONE test email (Sustalium) to hello@beresol.eu")
    args = ap.parse_args()

    if not (args.review or args.test):
        ap.print_help()
        sys.exit(1)

    rows = load_rows()
    print(f"[INFO] loaded {len(rows)} rows from {CSV_PATH}")

    if args.review:
        write_review(rows)
    if args.test:
        send_test(rows)


if __name__ == "__main__":
    main()
