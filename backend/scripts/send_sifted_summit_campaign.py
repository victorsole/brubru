"""
/send-batch: Sifted Summit 2026 speakers (London, 30 September - 1 October 2026).

One personalised English email per speaker, four templates by tier (policy,
legal, AI builders, investors). Each email names the speaker's own session,
read from the live agenda at https://summit.sifted.eu/2026-agenda.

Recipients: docs/outreach/sifted_summit_2026_recipients.csv, columns
name, email, tier, organisation, session, source_url, salutation (optional).
Every address was lifted from a published page (source_url); none is guessed.
Generic inboxes are refused in code (feedback_no_generic_inbox_sends).

Each message is personalised, so it goes to one recipient (To = that person)
over ONE SMTP connection with a pause between messages. Logged to
pre_user_events as event_type 'send_sifted_summit_2026'; an address already
logged is never sent twice.

    python3.12 scripts/send_sifted_summit_campaign.py --preview   # render all, write preview file
    python3.12 scripts/send_sifted_summit_campaign.py --test      # one per tier to hello@beresol.eu
    python3.12 scripts/send_sifted_summit_campaign.py --send      # real send, after Victor's OK
"""
import argparse
import csv
import html
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_REPO_ROOT = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(_REPO_ROOT / "backend" / ".env")
    load_dotenv(_REPO_ROOT / ".env")
except ImportError:
    pass

from sqlalchemy import text  # noqa: E402

CSV_PATH = _REPO_ROOT / "docs" / "outreach" / "sifted_summit_2026_recipients.csv"
PREVIEW_PATH = _REPO_ROOT / "docs" / "outreach" / "sifted_summit_2026_email_preview.md"
EVENT_TYPE = "send_sifted_summit_2026"
TEST_ADDRESS = "hello@beresol.eu"
BRUBRU_URL = "https://brubru.beresol.eu/"
PAUSE_SECONDS = 2.0

GENERIC_LOCAL_PARTS = {
    "info", "contact", "office", "hello", "mail", "support", "secretary", "admin",
    "webmaster", "enquiries", "inquiries", "help", "sales", "team", "press", "media",
    "hotline", "legal", "privacy", "careers", "jobs", "partnerships", "comms",
}

SUBJECTS = {
    "policy": "Your Sifted Summit session, and the EU files behind it",
    "legal": "Sifted Summit: the EU rules your clients will ask about next",
    "ai": "Sifted Summit: EU law, readable by your agents",
    "investor": "Sifted Summit: your portfolio's exposure to Brussels",
}

TIER_OF = {
    "A_policy": "policy",
    "A_legal_regtech": "legal",
    "B_ai_builder": "ai",
    "C_investor": "investor",
}

# Facts below were checked on 29 September 2026 against Brubru's own deep-dive
# pages (which cite the Commission proposals, OEIL and the committee records)
# and against the live consultations API. Fact-check table: session MD, item 6.
PARAGRAPHS = {
    "policy": [
        "I am Victor Sol&eacute;, and I built Brubru, an AI agent for EU public affairs. "
        "It follows the Brussels files that decide whether European startups can scale here, "
        "and reads them from the primary sources: the Commission proposals, the committee "
        "agendas, the amendments and the votes.",
        "Two files worth knowing before you go on stage:",
        "<ul style=\"padding-left:20px;\">"
        "<li style=\"margin-bottom:8px;\"><strong>EU Inc, the 28th regime</strong>, proposed by the "
        "Commission on 18 March 2026. In the European Parliament the Legal Affairs Committee "
        "debated the amendments on 7 September, and the Employment Committee adopted its "
        "opinion on 10 September, 26 votes to 19. "
        "<a href=\"https://brubru.beresol.eu/eu-inc/\" style=\"color:#0693e3;\">Where the file stands</a>.</li>"
        "<li style=\"margin-bottom:8px;\"><strong>The Cloud and AI Development Act and Chips Act 2.0</strong>, "
        "both proposed on 3 June 2026 in the Tech Sovereignty Package and now in Parliament. "
        "<a href=\"https://brubru.beresol.eu/cloud-ai-act/\" style=\"color:#0693e3;\">Cloud and AI</a> and "
        "<a href=\"https://brubru.beresol.eu/chips-act-2/\" style=\"color:#0693e3;\">Chips</a>, article by article.</li>"
        "</ul>",
        "If it helps your preparation, ask Brubru anything about them. The first 14 days are free.",
    ],
    "legal": [
        "I am Victor Sol&eacute;, and I built Brubru, an AI agent for EU public affairs "
        "and EU law.",
        "Two parts of it are built for lawyers. <strong>EU Law Comply</strong> checks a company "
        "against the obligations of an EU act, article by article, and says where the gaps are. "
        "The <strong>Brubru API</strong> puts the EU's legislative data in one place: acts, "
        "procedures, votes, and 4,015 public consultations from 14 EU bodies.",
        "One file your startup clients will raise: <strong>EU Inc, the 28th regime</strong>, "
        "proposed by the Commission on 18 March 2026 and now in the European Parliament, where "
        "the Legal Affairs Committee debated the amendments on 7 September. "
        "<a href=\"https://brubru.beresol.eu/eu-inc/\" style=\"color:#0693e3;\">Where it stands</a>.",
        "The first 14 days are free, if you would like to try it on a question from a real matter.",
    ],
    "ai": [
        "I am Victor Sol&eacute;, and I built Brubru, an AI agent for EU public affairs.",
        "Everything Brubru knows is also available to other agents: a REST API over the EU's "
        "legislative data (acts, procedures, votes, and 4,015 public consultations from 14 EU "
        "bodies), and an MCP connector that plugs the same data into Claude and other MCP clients.",
        "The rules that reach AI companies are moving too. The AI Act's obligations for "
        "general-purpose AI models have applied since 2 August 2025, and the "
        "<a href=\"https://brubru.beresol.eu/cloud-ai-act/\" style=\"color:#0693e3;\">Cloud and AI Development Act</a>, "
        "proposed on 3 June 2026, is now in Parliament.",
        "The first 14 days are free. I would be glad to hear what your team would want from it.",
    ],
    "investor": [
        "I am Victor Sol&eacute;, and I built Brubru, an AI agent for EU public affairs.",
        "Funds use it to see a portfolio's exposure to Brussels: track the EU files that touch "
        "each company, see when one moves, and ask plain questions about any of them.",
        "Two files that reach most European portfolios: "
        "<a href=\"https://brubru.beresol.eu/eu-inc/\" style=\"color:#0693e3;\">EU Inc</a>, the 28th "
        "regime proposed on 18 March 2026, and the "
        "<a href=\"https://brubru.beresol.eu/cloud-ai-act/\" style=\"color:#0693e3;\">Cloud and AI Development Act</a>, "
        "proposed on 3 June 2026. Both are now in the European Parliament.",
        "The first 14 days are free, if you would like to try it on your portfolio.",
    ],
}


def _is_generic(email: str) -> bool:
    return email.split("@", 1)[0].lower() in GENERIC_LOCAL_PARTS


def load_recipients():
    rows = []
    with open(CSV_PATH, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            email = (r.get("email") or "").strip().lower()
            tier = TIER_OF.get((r.get("tier") or "").strip())
            if not email or "@" not in email or not tier:
                continue
            if _is_generic(email):
                print(f"[INFO] refused generic inbox: {email}")
                continue
            if not (r.get("source_url") or "").strip():
                print(f"[INFO] refused, no source_url: {email}")
                continue
            rows.append({**r, "email": email, "t": tier})
    return rows


def render(r):
    first = r["name"].split()[0]
    salutation = (r.get("salutation") or "").strip() or first
    session = html.escape((r.get("session") or "").strip())
    end = "" if session[-1:] in "?!." else "."
    opener = (f"I saw that you are speaking at Sifted Summit this week, on "
              f"&ldquo;{session}&rdquo;{end}" if session else
              "I saw that you are speaking at Sifted Summit this week.")
    paras = [f"Dear {html.escape(salutation)},", opener] + PARAGRAPHS[r["t"]]
    body = "".join(p if p.startswith("<ul") else f"<p>{p}</p>" for p in paras)
    body += (f"<p>Best regards,<br/>Victor Sol&eacute;<br/>Brubru, by Beresol<br/>"
             f"hello@beresol.eu<br/><a href=\"{BRUBRU_URL}\" style=\"color:#0693e3;\">brubru.beresol.eu</a></p>"
             f"<p style=\"font-size:11px;color:#999;\">If you would rather not hear from me again, "
             f"reply with &ldquo;unsubscribe&rdquo; and I will not write again.</p>")
    return SUBJECTS[r["t"]], (
        "<div style=\"font-family: Georgia, 'Times New Roman', serif; font-size:15px; "
        f"line-height:1.6; color:#1a1a1a; max-width:640px;\">{body}</div>")


def already_sent(db, emails):
    if not emails:
        return set()
    rows = db.execute(text(
        "SELECT DISTINCT lower(event_metadata->>'email') FROM pre_user_events "
        "WHERE event_type = :et AND lower(event_metadata->>'email') = ANY(:e)"),
        {"et": EVENT_TYPE, "e": list(emails)}).fetchall()
    return {r[0] for r in rows}


def log_send(db, r):
    db.execute(text(
        "INSERT INTO pre_user_events (id, pre_user_id, event_type, ab_variant, event_metadata, created_at) "
        "VALUES (gen_random_uuid(), gen_random_uuid()::text, :et, :tier, "
        "jsonb_build_object('email', :email, 'name', :name, 'org_name', :org, "
        "'campaign', 'sifted_summit_2026', 'source_url', :src), NOW())"),
        {"et": EVENT_TYPE, "tier": r["t"], "email": r["email"], "name": r["name"],
         "org": r.get("organisation") or "", "src": r.get("source_url") or ""})
    db.commit()


def send_all(messages):
    """messages: list of (to_address, subject, html, row_or_None). One SMTP connection."""
    import smtplib
    from email.mime.text import MIMEText
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER") or "hello@beresol.eu"
    pw = os.environ.get("SMTP_PASSWORD")
    if not pw:
        print("[ERROR] SMTP_PASSWORD is not set; nothing sent.")
        return 0, len(messages)
    ok = fail = 0
    db = None
    if any(m[3] is not None for m in messages):
        from core.database import SessionLocal
        db = SessionLocal()
    try:
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls()
            s.login(user, pw)
            for to, subject, body, row in messages:
                msg = MIMEText(body, "html", "utf-8")
                msg["Subject"] = subject
                msg["From"] = f"Victor Solé <{user}>"
                msg["To"] = to
                msg["Reply-To"] = "hello@beresol.eu"
                try:
                    s.sendmail(user, [to], msg.as_string())
                    ok += 1
                    print(f"[OK] {to}")
                    if row is not None:
                        log_send(db, row)
                except smtplib.SMTPException as e:
                    fail += 1
                    print(f"[ERROR] {to}: {e}")
                time.sleep(PAUSE_SECONDS)
    finally:
        if db is not None:
            db.close()
    return ok, fail


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--preview", action="store_true")
    g.add_argument("--test", action="store_true")
    g.add_argument("--send", action="store_true")
    args = ap.parse_args()

    rows = load_recipients()
    print(f"[INFO] eligible recipients in CSV: {len(rows)}")

    if args.preview:
        out = [f"# Sifted Summit 2026 outreach preview ({len(rows)} recipients)\n"]
        for r in rows:
            subject, body = render(r)
            out.append(f"## {r['name']} ({r.get('organisation')}) <{r['email']}> [{r['t']}]\n\n"
                       f"Source: {r.get('source_url')}\n\n**{subject}**\n\n{body}\n")
        PREVIEW_PATH.write_text("\n".join(out), encoding="utf-8")
        print(f"[OK] preview written: {PREVIEW_PATH}")
        return 0

    if args.test:
        seen, msgs = set(), []
        for r in rows:
            if r["t"] in seen:
                continue
            seen.add(r["t"])
            subject, body = render(r)
            msgs.append((TEST_ADDRESS, f"[TEST] {subject}", body, None))
        ok, fail = send_all(msgs)
        print(f"[OK] test sent {ok}, failed {fail} (one per tier, to {TEST_ADDRESS})")
        return 0 if fail == 0 else 1

    from core.database import SessionLocal
    db = SessionLocal()
    try:
        done = already_sent(db, [r["email"] for r in rows])
    finally:
        db.close()
    todo = [r for r in rows if r["email"] not in done]
    print(f"[INFO] already sent: {len(done)}; to send now: {len(todo)}")
    msgs = [(r["email"],) + render(r) + (r,) for r in todo]
    ok, fail = send_all(msgs)
    print(f"[OK] sent {ok}, failed {fail}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
