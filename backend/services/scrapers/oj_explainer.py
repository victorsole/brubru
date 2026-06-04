"""
Plain-language explanations for OJ acts ("What this means").

Brubru exists to dissolve EU jargon. An OJ title like "Commission Implementing
Regulation (EU) 2026/1146 ... concerning the renewal of the authorisation of the
preparations of Lactiplantibacillus plantarum DSM 18112 ... as feed additives"
is impenetrable. This turns each into one plain sentence a non-expert gets.

COST / PROVIDER POLICY
----------------------
Cheap provider, cached (the user's choice). Uses ``MistralProvider`` DIRECTLY —
NOT the multi-provider chain — so there is NO Anthropic fallback and therefore
ZERO Anthropic spend. If Mistral is unavailable (e.g. the key is 401), this is a
graceful no-op: it returns {} and the acts keep a null explanation until the key
is refreshed and the sync is re-run with --explain. Generated once at sync time
and cached in oj_entries.plain_explanation; never called per page-view.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

_SYS = (
    "You explain European Union Official Journal acts to non-experts. For each "
    "numbered act title, write ONE short sentence in plain British English saying "
    "what the act actually does and who or what it affects. No jargon, no legal "
    "codes, no act numbers, no dates, no em-dashes. Start with a verb. Max 28 "
    "words. Reply ONLY with the numbered list, one line per act."
)
_LINE_RE = re.compile(r"^\s*(\d+)[.)]\s*(.+?)\s*$")
BATCH = 8


async def explain_batch(items: List[Dict[str, str]]) -> Dict[str, str]:
    """items: [{'key':..., 'title':...}]. Returns {key: plain_explanation}.

    Mistral-only; returns {} on any failure (no Anthropic, no raise)."""
    if not items:
        return {}
    try:
        from services.ai.multi_provider_service import MistralProvider
    except Exception as e:  # pragma: no cover
        logger.warning(f"[OJ-EXPLAIN] cannot import MistralProvider: {e}")
        return {}

    provider = MistralProvider()
    if not provider.is_available:
        logger.warning("[OJ-EXPLAIN] Mistral unavailable (key 401/missing) — skipping, no Anthropic fallback")
        return {}

    out: Dict[str, str] = {}
    for start in range(0, len(items), BATCH):
        chunk = items[start:start + BATCH]
        numbered = "\n".join(f"{i + 1}. {it['title']}" for i, it in enumerate(chunk))
        try:
            resp = await provider.generate(
                system_prompt=_SYS,
                messages=[{"role": "user", "content": numbered}],
                max_tokens=60 * len(chunk) + 60,
                temperature=0.3,
            )
        except Exception as e:
            logger.warning(f"[OJ-EXPLAIN] Mistral generate failed ({e}); stopping batch")
            break
        for line in (resp.message or "").splitlines():
            m = _LINE_RE.match(line)
            if not m:
                continue
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(chunk):
                out[chunk[idx]["key"]] = m.group(2).strip()
    return out
