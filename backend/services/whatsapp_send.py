"""
WhatsApp Cloud API outbound helper.

Sends text messages from Brubru's WhatsApp Business number via Meta's Cloud API.
Used by the WhatsApp router to reply to inbound commands.

Created: April 2026
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

GRAPH_API = "https://graph.facebook.com/v20.0"
WA_MAX_MESSAGE_LEN = 4000  # WhatsApp text message limit is 4096; leave headroom


def _config() -> tuple[Optional[str], Optional[str]]:
    return (
        os.getenv("WHATSAPP_ACCESS_TOKEN"),
        os.getenv("WHATSAPP_PHONE_NUMBER_ID"),
    )


async def send_text(to: str, body: str) -> bool:
    """Send a plain text message to `to` (E.164 format with leading +).

    Returns True on success, False otherwise. Long messages are split into
    multiple WhatsApp messages.
    """
    token, phone_id = _config()
    if not token or not phone_id:
        logger.error("[whatsapp-send] missing WHATSAPP_ACCESS_TOKEN or WHATSAPP_PHONE_NUMBER_ID")
        return False

    # Strip leading + (Meta expects msisdn without +)
    msisdn = to.lstrip("+").strip()
    if not msisdn.isdigit():
        logger.error("[whatsapp-send] invalid recipient: %r", to)
        return False

    chunks = _chunk(body, WA_MAX_MESSAGE_LEN)
    url = f"{GRAPH_API}/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "to": msisdn,
                "type": "text",
                "text": {"preview_url": False, "body": chunk},
            }
            try:
                r = await client.post(url, headers=headers, json=payload)
                if r.status_code >= 400:
                    logger.error("[whatsapp-send] HTTP %s: %s", r.status_code, r.text[:300])
                    return False
            except httpx.HTTPError as exc:
                logger.error("[whatsapp-send] HTTP error: %s", exc)
                return False
    return True


def _chunk(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    out: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= size:
            out.append(remaining)
            break
        # Try to split on a paragraph boundary, then a line boundary
        cut = remaining.rfind("\n\n", 0, size)
        if cut < size // 2:
            cut = remaining.rfind("\n", 0, size)
        if cut < size // 2:
            cut = size
        out.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()
    return out
