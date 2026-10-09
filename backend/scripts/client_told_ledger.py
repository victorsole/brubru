#!/usr/bin/env python3.12
"""Record what a client has been sent, so the DPP watch can tell new from told.

Why: see services/clients/told_ledger.py. The watch called items URGENT every morning that the
client already had; this is the memory it was missing.

Usage (from backend/). Dry-run by default; --apply writes.

  # Record a sent mail. The text is read to find the links, references and dates it mentions;
  # it is NOT stored.
  python3.12 scripts/client_told_ledger.py record --client terraqui_dpp_tex \\
      --sent-at 2026-10-05T08:51:06Z --subject "Newsletter mensual: ..." \\
      --thread 1a10b4272a37d426 --file /path/to/mail.txt --apply

  # Record something the text cannot carry (a phone call, an item named by hand):
  python3.12 scripts/client_told_ledger.py record --client terraqui_dpp_tex \\
      --sent-at 2026-09-25 --subject "MCP improvements mail" --thread 1a0d7f30915f200b \\
      --identifier tris:2026/0266/ES --note "body not re-read" --apply

  # Record a REVIEWED-AND-DISMISSED item (a false positive), so it stops being urgent:
  python3.12 scripts/client_told_ledger.py record --client terraqui_dpp_tex --channel dismissed \\
      --sent-at 2026-10-09 --subject "not relevant: German concrete-structures guideline" \\
      --identifier tris:2026/0413/DE --apply

  python3.12 scripts/client_told_ledger.py list --client terraqui_dpp_tex

Sent the mail? Record it the same day (the /dpp-brief skill says so): an unrecorded mail is
indistinguishable from one never sent, and the item stays URGENT.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timezone

logging.disable(logging.WARNING)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from core.database import SessionLocal  # noqa: E402
from services.clients import told_ledger as tl  # noqa: E402


def _when(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def cmd_record(a) -> int:
    sent_at = _when(a.sent_at)
    ids: set[str] = set(a.identifier or [])
    dates: set[date] = set(date.fromisoformat(d) for d in (a.date or []))
    source = "manual"
    if a.file:
        text_ = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf8").read()
        ids |= tl.identifiers_from(text_)
        dates |= set(tl.extract_dates(text_, sent_at.date()))
        source = "scan"
    if not ids:
        print("[ERROR] nothing to record: no identifiers found in the text and none given with --identifier")
        return 2
    print(f"client      : {a.client}")
    print(f"sent        : {sent_at.isoformat()}  channel={a.channel}  thread={a.thread or '-'}")
    print(f"subject     : {a.subject}")
    print(f"source      : {source}")
    print(f"identifiers : {len(ids)}")
    for k in sorted(ids):
        print(f"   {k}")
    print(f"dates       : {', '.join(d.isoformat() for d in sorted(dates)) or '(none)'}")
    if not a.apply:
        print("\n[DRY-RUN] nothing written. Re-run with --apply.")
        return 0
    db = SessionLocal()
    try:
        out = tl.record_mail(db, client_key=a.client, sent_at=sent_at, subject=a.subject, identifiers=ids,
                             mentioned_dates=dates, thread_ref=a.thread, channel=a.channel, source=source,
                             note=a.note)
    finally:
        db.close()
    print(f"\n[OK] {out}")
    return 0


def cmd_list(a) -> int:
    db = SessionLocal()
    try:
        mails = tl.load_mails(db, a.client)
    finally:
        db.close()
    print(f"{a.client}: {len(mails)} entr{'y' if len(mails) == 1 else 'ies'} in the last {tl.LOOKBACK_DAYS} days")
    for m in mails:
        print(f"  {m['sent_at']:%Y-%m-%d %H:%M}  {m['channel']:<9} {len(m['identifiers']):>3} ids "
              f"{len(m['mentioned_dates']):>3} dates  {str(m['subject'])[:70]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record", help="record a sent mail (or a dismissal)")
    r.add_argument("--client", required=True, help="client key, e.g. terraqui_dpp_tex")
    r.add_argument("--sent-at", required=True, help="ISO date or datetime, e.g. 2026-10-05T08:51:06Z")
    r.add_argument("--subject", required=True)
    r.add_argument("--thread", help="Gmail thread/message id: re-recording the same one updates it")
    r.add_argument("--file", help="text of the sent mail ('-' = stdin); read for links, references, dates")
    r.add_argument("--identifier", action="append", help="repeatable, e.g. tris:2026/0266/ES or oeil:2025/0395(COD)")
    r.add_argument("--date", action="append", help="repeatable YYYY-MM-DD the mail covered")
    r.add_argument("--channel", default="email", help="email (default) | call | dismissed")
    r.add_argument("--note")
    r.add_argument("--apply", action="store_true")
    r.set_defaults(fn=cmd_record)
    l = sub.add_parser("list", help="show what is recorded for a client")
    l.add_argument("--client", required=True)
    l.set_defaults(fn=cmd_list)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
