"""
Transcript summary + translation service (MEUB Transcripts moat).

Produces institutional summaries of long EP/EC/Council meeting transcripts in the
user's language. Pipeline:
  1. Qwen3-30B-A3B-Instruct-2507 (256K context) writes ONE canonical English
     summary of the full transcript, structured for a policy professional and
     anchored to the agenda items + procedure references.
  2. Qwen3-235B-A22B-Instruct-2507 translates that summary on demand into
     ES / FR / NL / IT / CA, preserving structure, codes and proper names.

Both run through the HF Inference Providers router (HUGGINGFACE_API_KEY). The 30B
is served by featherless-ai, so its provider is pinned in the model id. NO
Anthropic (transcript summarisation is non-chat).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from services.ai.huggingface_service import get_huggingface_service

logger = logging.getLogger(__name__)

SUMMARISER_MODEL = "Qwen/Qwen3-30B-A3B-Instruct-2507:featherless-ai"
TRANSLATOR_MODEL = "Qwen/Qwen3-235B-A22B-Instruct-2507"

SUPPORTED_LANGS = ["en", "es", "fr", "it", "nl", "ca"]
LANG_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French",
    "it": "Italian", "nl": "Dutch", "ca": "Catalan",
}

# Cap the transcript we send (generous; most committee meetings are 60-150k chars).
_MAX_TRANSCRIPT_CHARS = 180_000

_SUMMARY_SYSTEM = (
    "You are an EU policy analyst writing for a public-affairs professional. You "
    "summarise European Parliament / Commission / Council meeting transcripts "
    "accurately and concisely. British English. No emojis. Never invent names, "
    "figures, votes or document references that are not in the transcript."
)


def _summary_prompt(committee: str, date_str: str, title: str,
                    agenda_items: Optional[List[Dict]], transcript: str) -> str:
    agenda_block = ""
    if agenda_items:
        lines = []
        for it in agenda_items:
            ref = f" [{it.get('procedure_ref')}]" if it.get("procedure_ref") else ""
            lines.append(f"- Item {it.get('number')}: {it.get('title')}{ref}")
        agenda_block = "Agenda (for reference):\n" + "\n".join(lines) + "\n\n"
    return (
        f"Summarise this {committee} meeting of {date_str} ({title}).\n\n"
        f"{agenda_block}"
        "Write the summary in British English using these exact markdown sections:\n"
        "## Overview\n(2-3 sentences: what the meeting was and why it matters)\n\n"
        "## Main topics\n(one bullet per agenda item actually discussed; state the "
        "substance and cite procedure references such as 2025/0237(COD) where they appear)\n\n"
        "## Key positions\n(notable interventions: who said what, naming the speaker or "
        "political group only if clearly identifiable in the transcript)\n\n"
        "## Outcomes and next steps\n(decisions, votes, deadlines, what happens next)\n\n"
        "Be tight and factual. Output only the summary.\n\n"
        "TRANSCRIPT:\n" + transcript[:_MAX_TRANSCRIPT_CHARS]
    )


async def summarise_english(
    transcript_text: str,
    committee: str,
    date_str: str,
    title: str = "",
    agenda_items: Optional[List[Dict]] = None,
) -> Optional[str]:
    """Generate the canonical English institutional summary via Qwen3-30B."""
    if not transcript_text or len(transcript_text) < 400:
        return None
    hf = get_huggingface_service()
    return await hf.chat_completion(
        model=SUMMARISER_MODEL,
        messages=[
            {"role": "system", "content": _SUMMARY_SYSTEM},
            {"role": "user", "content": _summary_prompt(
                committee, date_str, title, agenda_items, transcript_text)},
        ],
        max_tokens=1400,
        temperature=0.2,
    )


async def translate_summary(summary_en: str, target_lang: str) -> Optional[str]:
    """Translate an English summary into target_lang via Qwen3-235B-Instruct-2507,
    preserving markdown structure, codes and names."""
    lang = (target_lang or "").lower()
    if lang == "en" or lang not in LANG_NAMES:
        return summary_en if lang == "en" else None
    name = LANG_NAMES[lang]
    extra = ""
    if lang == "ca":
        extra = (" Use correct Catalan with accents and apostrophe elision "
                 "(l'informe, d'execució, Brussel·les).")
    hf = get_huggingface_service()
    return await hf.chat_completion(
        model=TRANSLATOR_MODEL,
        messages=[
            {"role": "user", "content": (
                f"Translate the following EU policy meeting summary into {name}. "
                "Keep the markdown layout (the ## heading lines and the bullet "
                "structure) but TRANSLATE the heading text itself into "
                f"{name} as well. Keep procedure references (e.g. 2025/0237(COD)), "
                f"institutional acronyms and proper names unchanged.{extra} Output "
                "only the translation, with no preamble.\n\n" + summary_en)},
        ],
        max_tokens=1800,
        temperature=0.1,
    )
