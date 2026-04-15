"""
WhatsApp Cloud API webhook.

Two endpoints:
  GET  /api/whatsapp/webhook   -> Meta verification handshake
  POST /api/whatsapp/webhook   -> inbound message events (signature-verified)

Inbound flow:
  1. Verify X-Hub-Signature-256 against WHATSAPP_APP_SECRET (HMAC-SHA256)
  2. Parse the message; reject if sender not in WHATSAPP_ALLOWED_NUMBERS
  3. Schedule message handling on the asyncio loop (returns 200 OK immediately
     so Meta does not retry)

Created: April 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import os
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request

from services.whatsapp_router import handle_message

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])


def _allowed_numbers() -> set[str]:
    raw = os.getenv("WHATSAPP_ALLOWED_NUMBERS", "")
    return {n.strip().lstrip("+") for n in raw.split(",") if n.strip()}


def _verify_signature(secret: str, body: bytes, signature_header: Optional[str]) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    received = signature_header.split("=", 1)[1].strip()
    return hmac.compare_digest(expected, received)


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    """Meta calls this once when you set the webhook URL."""
    expected = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    if hub_mode == "subscribe" and expected and hmac.compare_digest(hub_verify_token, expected):
        # Meta wants the raw challenge string back as int-castable text
        return int(hub_challenge) if hub_challenge.isdigit() else hub_challenge
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
):
    """Inbound message handler. Always returns 200 OK promptly."""
    secret = os.getenv("WHATSAPP_APP_SECRET", "")
    raw = await request.body()

    if not secret:
        logger.error("[whatsapp] WHATSAPP_APP_SECRET not configured; refusing")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    if not _verify_signature(secret, raw, x_hub_signature_256):
        logger.warning("[whatsapp] signature verification failed")
        raise HTTPException(status_code=403, detail="Bad signature")

    try:
        payload = await request.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("[whatsapp] non-JSON body: %s", exc)
        return {"status": "ignored"}

    allow = _allowed_numbers()
    for entry in payload.get("entry") or []:
        for change in entry.get("changes") or []:
            value = change.get("value") or {}
            for msg in value.get("messages") or []:
                if msg.get("type") != "text":
                    continue
                sender = (msg.get("from") or "").lstrip("+")
                if not sender:
                    continue
                if sender not in allow:
                    logger.info("[whatsapp] ignoring sender not in allowlist: %r", sender)
                    continue
                text = ((msg.get("text") or {}).get("body") or "").strip()
                if not text:
                    continue
                # Schedule and return immediately so Meta doesn't retry
                asyncio.create_task(handle_message("+" + sender, text))

    return {"status": "ok"}
