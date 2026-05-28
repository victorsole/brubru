"""
EFPIA daily pharma/health brief sender.

Cadence: Mon-Fri until 28 June 2026 inclusive (EFPIA pilot window).
Recipients: public-affairs@efpia.eu, david.devantcerezo@efpia.eu, athina.giannoutsou@efpia.eu.

Format: short hero, 5 EU pharma/health headlines (60-word so-what each) +
"Brubru is also tracking your files" block (from priority_files.json) +
"Brubru is also updated" block (guides changed in the last 24h from git +
backend/knowledge_base/guides/).

Headlines are read from a date-keyed JSON file:
    backend/data/efpia_brief/YYYY-MM-DD.json

Schema:
{
  "issue_date": "2026-05-29",
  "day_of_week": "Friday",
  "hero_intro": "<one-paragraph framing>",
  "headlines": [
    {
      "title": "...",
      "source": "...",
      "snippet": "...",
      "ask": "...",
      "feature_label": "Legislative Tracker" | "Chat" | "Position Analysis" | "EU Law Comply" | "My EU Calendar",
      "feature_url": "https://brubru.beresol.eu/...",
      "color": "#0693e3"
    },
    ... (exactly 5)
  ]
}

Anti-hallucination protocol (per CLAUDE.md "Daily brief send protocol"):
    1. python3.12 -m scripts.send_efpia_brief --date YYYY-MM-DD --verify-urls
    2. python3.12 -m scripts.send_efpia_brief --date YYYY-MM-DD --test
    3. wait for explicit OK from user
    4. python3.12 -m scripts.send_efpia_brief --date YYYY-MM-DD --send

Hard rules:
- SMTP-level BCC: ONE SMTP connection, RCPT TO per recipient, visible To = hello@beresol.eu
  (per memory/feedback_send_batch_use_bcc.md).
- load_dotenv() called at module top (per memory/feedback_send_script_dotenv_required.md).
- SMTP_PASSWORD env var (not SMTP_PASS).
- 0.5s delay between RCPT TOs.
- No em-dashes, no emojis, no institutional codes in hero text (per
  memory/feedback_brubru_brief_no_institutional_codes.md).
- Codes (CELEX / COM / OEIL ref) are allowed in priority-files block + footer references.

Created 28 May 2026 after EFPIA pilot kickoff.
"""

from __future__ import annotations

import argparse
import json
import os
import smtplib
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(_ENV_PATH)

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_ROOT))

_PRIORITY_FILES_PATH = _BACKEND_ROOT / "data" / "efpia_brief" / "priority_files.json"
_HEADLINES_DIR = _BACKEND_ROOT / "data" / "efpia_brief"
_GUIDES_DIR = _BACKEND_ROOT / "knowledge_base" / "guides"

BRUBRU_CHAT = "https://brubru.beresol.eu/main"
FROM_ADDRESS = "Brubru <hello@beresol.eu>"
TEST_RECIPIENT_DEFAULT = "hello@beresol.eu"

# Pharma/health guide prefixes used to detect "Brubru is also updated" items.
_PHARMA_GUIDE_PATTERNS = (
    "biotech_act",
    "critical_medicines",
    "pharma",
    "medicine",
    "medicinal_product",
    "clinical_trial",
    "ema_",
    "ema.md",
    "hta_",
    "health_",
    "vaccine",
    "amr_",
    "antimicrobial",
    "orphan_",
    "atmp",
    "advanced_therapy",
    "blood_tissues",
    "compulsory_licens",
    "patent_term_extension",
    "regulatory_data_protection",
)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _load_priority_config() -> dict:
    if not _PRIORITY_FILES_PATH.is_file():
        raise SystemExit(f"missing priority files config: {_PRIORITY_FILES_PATH}")
    with _PRIORITY_FILES_PATH.open() as fh:
        return json.load(fh)


def _load_headlines(issue_date: str) -> dict:
    path = _HEADLINES_DIR / f"{issue_date}.json"
    if not path.is_file():
        raise SystemExit(
            f"no headlines file at {path}. Curate 5 headlines into a JSON matching the schema "
            "at the top of send_efpia_brief.py."
        )
    with path.open() as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise SystemExit(f"{path} must contain a JSON object")
    headlines = data.get("headlines") or []
    if len(headlines) != 5:
        raise SystemExit(
            f"{path} must define exactly 5 headlines (got {len(headlines)})."
        )
    return data


def _guides_changed_last_24h() -> list[dict]:
    """Return pharma/health guide filenames changed in the last 24 h according to git."""
    try:
        out = subprocess.check_output(
            [
                "git",
                "log",
                "--name-only",
                "--pretty=format:",
                "--since=24 hours ago",
                "--",
                "backend/knowledge_base/guides/",
            ],
            cwd=str(_PROJECT_ROOT),
            stderr=subprocess.DEVNULL,
            timeout=15,
        ).decode()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []

    changed = set()
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        name = Path(line).name
        if not name.endswith(".md"):
            continue
        lower = name.lower()
        if any(lower.startswith(p) or p in lower for p in _PHARMA_GUIDE_PATTERNS):
            changed.add(name)

    items = []
    for name in sorted(changed):
        items.append(
            {
                "guide": name,
                "label": _guide_label(name),
            }
        )
    return items


def _guide_label(filename: str) -> str:
    stem = filename.replace(".md", "")
    return stem.replace("_", " ").title()


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _verify_url(url: str, timeout: float = 8.0) -> tuple[bool, int]:
    if not url:
        return True, 0
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "BrubruBriefVerifier/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400, resp.status
    except Exception:
        # Some hosts reject HEAD. Try GET with a tiny read.
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "BrubruBriefVerifier/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp.read(64)
                return resp.status < 400, resp.status
        except Exception as exc:  # noqa: BLE001
            print(f"  [WARN] {url} -> {type(exc).__name__}: {exc}")
            return False, 0


def _verify_all_urls(headlines: list[dict], priority_files: list[dict]) -> bool:
    print("Verifying URLs (HEAD + GET fallback)...")
    ok = True
    for i, h in enumerate(headlines, 1):
        feature = h.get("feature_url") or ""
        success, status = _verify_url(feature)
        flag = "OK" if success else "FAIL"
        print(f"  H{i} feature_url [{status}] [{flag}] {feature}")
        if not success:
            ok = False
    for pf in priority_files:
        url = pf.get("brubru_url") or ""
        success, status = _verify_url(url)
        flag = "OK" if success else "FAIL"
        print(f"  PF [{status}] [{flag}] {pf.get('label')} -> {url}")
        if not success:
            ok = False
    return ok


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def _build_headline_block(h: dict, index: int) -> str:
    color = h.get("color", "#0693e3")
    ask = h.get("ask") or ""
    ask_url = f"{BRUBRU_CHAT}?q={quote(ask)}" if ask else BRUBRU_CHAT
    feature_label = h.get("feature_label", "Chat")
    feature_url = h.get("feature_url", BRUBRU_CHAT)
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
            &ldquo;{ask}&rdquo;
          </a>
        </div>
        <div style="margin-bottom: 6px;">
          <a href="{ask_url}" style="display: inline-block; padding: 5px 14px; font-size: 12px; font-weight: 600; color: {color}; border: 1px solid {color}; border-radius: 4px; text-decoration: none; margin-right: 6px;">
            Ask Brubru
          </a>
          <a href="{feature_url}" style="display: inline-block; padding: 5px 14px; font-size: 12px; font-weight: 600; color: #ffffff; background: {color}; border: 1px solid {color}; border-radius: 4px; text-decoration: none;">
            Go to {feature_label}
          </a>
        </div>
        <div style="font-size: 11px; color: #9ca3af; margin-top: 6px;">
          Source: {h.get('source', '')}
        </div>
      </td>
    </tr>"""


def _build_tracking_block(priority_files: list[dict]) -> str:
    items = []
    for pf in priority_files:
        ref_bits = []
        if pf.get("oeil_ref"):
            ref_bits.append(pf["oeil_ref"])
        if pf.get("celex"):
            ref_bits.append(f"CELEX {pf['celex']}")
        refs = " &middot; ".join(ref_bits) if ref_bits else ""
        items.append(
            f"""
        <li style="margin-bottom: 8px;">
          <a href="{pf['brubru_url']}" style="color: #0693e3; text-decoration: none; font-weight: 600;">{pf['label']}</a>
          <div style="font-size: 12px; color: #6b7280; margin-top: 2px;">
            {refs} &mdash; {pf.get('status_note', '')}
          </div>
        </li>"""
        )
    body = "".join(items)
    return f"""
<div style="margin-top: 24px; padding: 18px 20px; background: #f9fafb; border-left: 3px solid #0693e3; border-radius: 6px;">
  <div style="font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 10px;">
    Brubru is also tracking your files
  </div>
  <ul style="margin: 0; padding-left: 18px; color: #374151; font-size: 13px; line-height: 1.5;">
    {body}
  </ul>
</div>
"""


def _build_updates_block(updates: list[dict]) -> str:
    if not updates:
        body = (
            "<div style=\"font-size: 13px; color: #6b7280;\">No pharma or health guides changed "
            "in the last 24 hours. The knowledge base is steady on your topics.</div>"
        )
    else:
        rows = []
        for u in updates:
            rows.append(
                f"""<li style="margin-bottom: 6px;">
                <code style="background: #fef3c7; padding: 1px 6px; border-radius: 3px; font-size: 12px; color: #92400e;">{u['guide']}</code>
                &nbsp;<span style="font-size: 13px; color: #374151;">{u['label']}</span>
              </li>"""
            )
        body = (
            "<ul style=\"margin: 0; padding-left: 18px; color: #374151; font-size: 13px; line-height: 1.5;\">"
            + "".join(rows)
            + "</ul>"
        )
    return f"""
<div style="margin-top: 16px; padding: 18px 20px; background: #fefce8; border-left: 3px solid #ca8a04; border-radius: 6px;">
  <div style="font-size: 14px; font-weight: 700; color: #111827; margin-bottom: 10px;">
    Brubru is also updated
  </div>
  {body}
</div>
"""


def _build_html(payload: dict, priority_files: list[dict], updates: list[dict]) -> str:
    issue_date = payload["issue_date"]
    day_label = payload.get("day_of_week", "")
    hero_intro = payload.get("hero_intro") or (
        "Five pharma and health policy moves from the EU institutional landscape and the "
        "industry around it, with the operational layer your colleagues will want this morning."
    )
    headline_rows = "\n".join(
        _build_headline_block(h, i) for i, h in enumerate(payload["headlines"])
    )
    tracking_block = _build_tracking_block(priority_files)
    updates_block = _build_updates_block(updates)
    pretty_date = _pretty_date(issue_date, day_label)

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Brubru EFPIA Brief - {pretty_date}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f9fafb;">
  <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%" style="background-color: #f9fafb; padding: 24px 0;">
    <tr><td align="center">
      <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="640" style="max-width: 640px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,0.06);">
        <tr><td style="padding: 32px 32px 8px 32px;">
          <div style="font-family: 'Adobe Caslon Pro', Georgia, serif; font-size: 26px; font-weight: 700; color: #111827; letter-spacing: -0.5px;">
            Brubru EFPIA Brief
          </div>
          <div style="font-size: 13px; color: #6b7280; margin-top: 4px;">
            {pretty_date} &middot; curated pharma and health policy
          </div>
        </td></tr>
        <tr><td style="padding: 16px 32px 0 32px;">
          <p style="font-size: 15px; color: #374151; line-height: 1.6; margin: 0 0 20px 0;">
            {hero_intro}
          </p>
        </td></tr>
        <tr><td style="padding: 0 32px;">
          <table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%">
            {headline_rows}
          </table>
        </td></tr>
        <tr><td style="padding: 0 32px 8px 32px;">
          {tracking_block}
          {updates_block}
        </td></tr>
        <tr><td style="padding: 20px 32px 28px 32px; font-size: 11px; color: #9ca3af; line-height: 1.5;">
          You are receiving the Brubru EFPIA Brief as part of the EFPIA pilot access window
          (28 May to 28 June 2026). Login: public-affairs@efpia.eu, david.devantcerezo@efpia.eu,
          athina.giannoutsou@efpia.eu. For anything, reply to this email or write to
          <a href="mailto:hello@beresol.eu" style="color: #9ca3af; text-decoration: underline;">hello@beresol.eu</a>.
          <br>
          <a href="https://brubru.beresol.eu" style="color: #9ca3af; text-decoration: underline;">brubru.beresol.eu</a>
          &middot;
          <a href="https://beresol.eu" style="color: #9ca3af; text-decoration: underline;">Beresol</a>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _pretty_date(issue_date: str, day_label: str) -> str:
    try:
        dt = datetime.strptime(issue_date, "%Y-%m-%d")
    except ValueError:
        return issue_date
    formatted = dt.strftime("%-d %B %Y")
    if day_label:
        return f"{day_label} {formatted}"
    return formatted


# ---------------------------------------------------------------------------
# SMTP send (BCC pattern)
# ---------------------------------------------------------------------------


def _build_subject(payload: dict) -> str:
    return f"Brubru EFPIA Brief - {_pretty_date(payload['issue_date'], payload.get('day_of_week', ''))}"


def _send_email(subject: str, html: str, recipients: list[str]) -> None:
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_user = os.environ.get("SMTP_USER") or os.environ.get("EMAIL_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD") or os.environ.get("EMAIL_PASSWORD")
    if not smtp_user or not smtp_password:
        raise SystemExit(
            "SMTP_USER / SMTP_PASSWORD missing in .env -- aborting (no per-recipient fallback)."
        )

    msg = MIMEText(html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = FROM_ADDRESS
    msg["To"] = "hello@beresol.eu"
    msg["X-Brubru-Channel"] = "efpia-daily-brief"

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        for rcpt in recipients:
            try:
                smtp.sendmail(smtp_user, [rcpt], msg.as_string())
                print(f"  [SENT] {rcpt}")
            except smtplib.SMTPRecipientsRefused as exc:
                print(f"  [REFUSED] {rcpt}: {exc}")
            time.sleep(0.5)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def main() -> int:
    parser = argparse.ArgumentParser(description="Send the Brubru EFPIA Brief.")
    parser.add_argument("--date", default=_today_iso(), help="Issue date YYYY-MM-DD (default: today UTC).")
    parser.add_argument("--preview", action="store_true", help="Print the rendered HTML to stdout and exit.")
    parser.add_argument("--write-html", help="Write the rendered HTML to this path and exit.")
    parser.add_argument("--verify-urls", action="store_true", help="HEAD-check every feature_url and priority brubru_url.")
    parser.add_argument("--test", action="store_true", help="Send to the test recipient only (hello@beresol.eu).")
    parser.add_argument("--send", action="store_true", help="Send to the live EFPIA recipients.")
    parser.add_argument("--test-to", default=TEST_RECIPIENT_DEFAULT, help="Override the test recipient.")
    args = parser.parse_args()

    config = _load_priority_config()
    payload = _load_headlines(args.date)
    updates = _guides_changed_last_24h()
    subject = _build_subject(payload)
    html = _build_html(payload, config["files"], updates)

    print(f"[INFO] Issue date    : {payload['issue_date']}")
    print(f"[INFO] Day of week   : {payload.get('day_of_week') or '(unset)'}")
    print(f"[INFO] Subject       : {subject}")
    print(f"[INFO] Headlines     : {len(payload['headlines'])}")
    print(f"[INFO] Priority files: {len(config['files'])}")
    print(f"[INFO] Updates       : {len(updates)}")

    if args.preview:
        print()
        print(html)
        return 0

    if args.write_html:
        Path(args.write_html).write_text(html, encoding="utf-8")
        print(f"[INFO] HTML written to {args.write_html}")
        return 0

    if args.verify_urls:
        ok = _verify_all_urls(payload["headlines"], config["files"])
        if not ok:
            print("[FAIL] one or more URLs are unreachable. Fix them before sending.")
            return 2
        print("[OK] all URLs reachable.")

    if args.test:
        print(f"[INFO] Sending test to {args.test_to} ...")
        _send_email(subject, html, [args.test_to])
        print("[OK] test sent. Wait for explicit OK before --send.")
        return 0

    if args.send:
        live = config["recipients"]["live"]
        print(f"[INFO] Sending live to {len(live)} EFPIA addresses: {', '.join(live)}")
        _send_email(subject, html, live)
        print("[OK] send complete.")
        return 0

    print("\nNothing to do. Pass one of: --preview, --write-html, --verify-urls, --test, --send")
    return 1


if __name__ == "__main__":
    sys.exit(main())
