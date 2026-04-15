"""
WhatsApp command router.

Dispatches inbound WhatsApp messages to Brubru actions (/morning, /news,
/daily-brief, /send, /status) or to the chatbot for plain text. Long-running
commands run in the background and post status updates back via WhatsApp.

Critical safety rules (enforced here, NOT in the API layer):
  * Send-to-subscribers actions (/daily-brief, /send) NEVER auto-execute.
    They draft, then require an explicit "send" confirmation message.
  * /morning runs the read-only chain (/day-before, /news, /audit-queries) and
    drafts a daily brief; it never sends. Sending requires "send" reply.
  * Allowlist enforcement happens in the API layer before this module is hit.

Created: April 2026
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional

from services.whatsapp_send import send_text

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

# Per-sender pending state (in-memory; Railway is single-instance for now)
_PENDING: Dict[str, "PendingState"] = {}
_RATE_LIMIT: Dict[str, float] = {}  # last /morning timestamp per sender
RATE_LIMIT_SECONDS = 12 * 3600  # max one /morning per 12h per sender


@dataclass
class PendingState:
    """One pending multi-step action awaiting user confirmation."""
    kind: str  # "daily_brief" | "morning_send"
    created_at: float
    payload: Dict = field(default_factory=dict)


HELP_TEXT = (
    "Brubru WhatsApp commands:\n"
    "/morning -- run /day-before + /news + /audit-queries + draft daily brief (no send)\n"
    "/news -- scrape + sync only\n"
    "/daily-brief -- draft today's brief and ask you to confirm before sending\n"
    "/send -- confirm sending the last drafted brief to all subscribers\n"
    "/skip -- cancel the last pending action\n"
    "/status -- show pending actions\n"
    "/help -- this message\n"
    "Plain text -- routed to Brubru chat"
)


async def handle_message(sender: str, text: str) -> None:
    """Top-level dispatcher. Always replies via WhatsApp (no return value)."""
    text = (text or "").strip()
    if not text:
        return

    cmd = text.split()[0].lower() if text.startswith("/") else ""
    args = text[len(cmd):].strip() if cmd else ""

    try:
        if cmd in ("/help", "/?"):
            await send_text(sender, HELP_TEXT)
            return

        if cmd == "/status":
            await _cmd_status(sender)
            return

        if cmd == "/skip":
            removed = _PENDING.pop(sender, None)
            await send_text(sender, f"Cancelled pending {removed.kind}." if removed else "Nothing pending.")
            return

        if cmd == "/morning":
            await _cmd_morning(sender)
            return

        if cmd == "/news":
            await _cmd_news(sender)
            return

        if cmd == "/daily-brief":
            await _cmd_daily_brief(sender)
            return

        if cmd == "/send":
            await _cmd_send(sender)
            return

        # Plain text: route to chat
        await _cmd_chat(sender, text)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[whatsapp-router] handler crashed: %s", exc)
        await send_text(sender, f"Internal error: {exc}")


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #

async def _cmd_status(sender: str) -> None:
    pending = _PENDING.get(sender)
    if not pending:
        await send_text(sender, "Nothing pending.")
        return
    age = int(time.time() - pending.created_at)
    await send_text(sender, f"Pending: {pending.kind} (created {age}s ago). Reply 'send' to confirm or '/skip' to cancel.")


async def _cmd_morning(sender: str) -> None:
    last = _RATE_LIMIT.get(sender, 0.0)
    if time.time() - last < RATE_LIMIT_SECONDS:
        remaining = int((RATE_LIMIT_SECONDS - (time.time() - last)) / 3600)
        await send_text(sender, f"Already ran /morning recently. Try again in ~{remaining}h.")
        return
    _RATE_LIMIT[sender] = time.time()

    await send_text(sender, "Starting /morning. Read-only chain (no send). I'll ping you with progress.")
    asyncio.create_task(_run_morning_background(sender))


async def _cmd_news(sender: str) -> None:
    await send_text(sender, "Running /news (scrape + sync). I'll ping you when done.")
    asyncio.create_task(_run_news_background(sender))


async def _cmd_daily_brief(sender: str) -> None:
    await send_text(sender, "Drafting today's daily brief...")
    summary = await _draft_daily_brief()
    if not summary:
        await send_text(sender, "No headlines for today. Run /news first.")
        return
    _PENDING[sender] = PendingState(kind="daily_brief", created_at=time.time(),
                                    payload={"recipient_count": summary.get("recipient_count", 0)})
    msg = (
        f"Draft for {summary['date']} ({summary['recipient_count']} recipients):\n\n"
        + summary["headlines_text"]
        + "\n\nReply 'send' to send to all subscribers, '/skip' to cancel."
    )
    await send_text(sender, msg)


async def _cmd_send(sender: str) -> None:
    pending = _PENDING.get(sender)
    if not pending or pending.kind != "daily_brief":
        await send_text(sender, "Nothing to send. Run /daily-brief first.")
        return
    if time.time() - pending.created_at > 3600:
        await send_text(sender, "Pending draft is too old (>1h). Run /daily-brief again.")
        _PENDING.pop(sender, None)
        return
    await send_text(sender, "Sending...")
    result = await _send_daily_brief()
    _PENDING.pop(sender, None)
    if result["ok"]:
        await send_text(sender, f"Sent: {result['sent']} / Failed: {result['failed']}.")
    else:
        await send_text(sender, f"Send failed: {result.get('error', 'unknown')}")


async def _cmd_chat(sender: str, text: str) -> None:
    """Route plain text to /api/chat/message (loopback)."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            r = await client.post(
                "http://127.0.0.1:8000/api/chat/message",
                json={"message": text, "user_id": None, "conversation_id": None, "use_context": True},
            )
            data = r.json()
            reply = data.get("message", "(empty reply)")
    except Exception as exc:  # noqa: BLE001
        await send_text(sender, f"Chat error: {exc}")
        return
    await send_text(sender, reply)


# --------------------------------------------------------------------------- #
# Background runners (subprocess so we don't hold the event loop on heavy work)
# --------------------------------------------------------------------------- #

def _run_script(args: List[str], timeout: int = 600) -> tuple[int, str]:
    """Run a backend script and return (exit_code, last 1500 chars of output)."""
    try:
        proc = subprocess.run(
            ["python3.12"] + args,
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = proc.stdout + ("\n" + proc.stderr if proc.stderr else "")
        return proc.returncode, out[-1500:]
    except subprocess.TimeoutExpired:
        return 124, f"Timeout after {timeout}s"
    except Exception as exc:  # noqa: BLE001
        return 1, f"subprocess error: {exc}"


async def _run_news_background(sender: str) -> None:
    loop = asyncio.get_running_loop()
    code, out = await loop.run_in_executor(None, _run_script, ["scripts/scrape_eu_news.py", "--hours", "24", "--save"])
    head_match = "Saved" if "Saved" in out else "complete"
    await send_text(sender, f"/news done (exit {code}).\n{out[-800:]}")


async def _run_morning_background(sender: str) -> None:
    loop = asyncio.get_running_loop()
    # 1) news scrape + save
    await send_text(sender, "[1/3] /news running...")
    code, out = await loop.run_in_executor(None, _run_script, ["scripts/scrape_eu_news.py", "--hours", "24", "--save"])
    if code != 0:
        await send_text(sender, f"/news failed (exit {code}). Stopping.\n{out[-600:]}")
        return
    # 2) syncs (parallel-ish, sequential here for simplicity)
    await send_text(sender, "[2/3] OEIL + EUR-Lex + EPRS + committee minutes syncing...")
    for script_args in (
        ["scripts/sync_oeil_feeds.py", "--days", "3"],
        ["scripts/sync_eurlex_feeds.py", "--days", "3"],
        ["scripts/sync_eprs_publications.py", "--days", "7"],
        ["scripts/sync_committee_minutes.py", "--max-pages", "2"],
    ):
        await loop.run_in_executor(None, _run_script, script_args)
    # 3) draft daily brief (no send)
    await send_text(sender, "[3/3] Drafting daily brief...")
    summary = await _draft_daily_brief()
    if not summary:
        await send_text(sender, "/morning done. No headlines saved -- check /news output.")
        return
    _PENDING[sender] = PendingState(kind="daily_brief", created_at=time.time(),
                                    payload={"recipient_count": summary.get("recipient_count", 0)})
    msg = (
        f"/morning done. Draft for {summary['date']} ({summary['recipient_count']} recipients):\n\n"
        + summary["headlines_text"]
        + "\n\nReply 'send' to send, '/skip' to cancel."
    )
    await send_text(sender, msg)


# --------------------------------------------------------------------------- #
# Daily brief helpers (read DB + run send script in subprocess)
# --------------------------------------------------------------------------- #

async def _draft_daily_brief() -> Optional[Dict]:
    """Pull today's saved headlines from DB and count recipients. No send."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _draft_daily_brief_sync)


def _draft_daily_brief_sync() -> Optional[Dict]:
    try:
        from sqlalchemy import text
        from core.database import SessionLocal
        db = SessionLocal()
        try:
            rows = db.execute(text(
                "SELECT priority, headline FROM daily_briefs WHERE brief_date = :d ORDER BY priority"
            ), {"d": date.today().isoformat()}).fetchall()
            if not rows:
                return None
            user_count = db.execute(text(
                "SELECT COUNT(*) FROM users WHERE email IS NOT NULL "
                "AND COALESCE(preferences->>'daily_brief_unsubscribed','') <> 'true'"
            )).scalar() or 0
        finally:
            db.close()
        headlines_text = "\n".join(f"{r.priority}. {r.headline}" for r in rows)
        return {
            "date": date.today().isoformat(),
            "headlines_text": headlines_text,
            "recipient_count": int(user_count),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("[whatsapp-router] _draft_daily_brief failed: %s", exc)
        return None


async def _send_daily_brief() -> Dict:
    loop = asyncio.get_running_loop()
    code, out = await loop.run_in_executor(
        None,
        _run_script,
        ["scripts/send_daily_brief.py", "--send"],
    )
    if code != 0:
        return {"ok": False, "error": out[-400:]}
    sent = failed = 0
    for line in out.splitlines():
        if "Sent:" in line:
            try: sent = int(line.split(":")[1].strip().split()[0])
            except (IndexError, ValueError): pass
        if "Failed:" in line:
            try: failed = int(line.split(":")[1].strip().split()[0])
            except (IndexError, ValueError): pass
    return {"ok": True, "sent": sent, "failed": failed}
