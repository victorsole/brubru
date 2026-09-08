"""
Plain-language explanations for OJ acts ("What this means").

Brubru exists to dissolve EU jargon. An OJ title like "Commission Implementing
Regulation (EU) 2026/1146 ... concerning the renewal of the authorisation of the
preparations of Lactiplantibacillus plantarum DSM 18112 ... as feed additives"
is impenetrable. This turns each into one plain sentence a non-expert gets.

COST / PROVIDER POLICY
----------------------
Cheap providers only, cached. Tries ``CerebrasProvider`` first and falls back to
``MistralProvider``. It does NOT use the multi-provider chain, so there is NO
Anthropic fallback and therefore ZERO Anthropic spend. If every listed provider
fails this is a graceful no-op: it returns {} and the acts keep a null
explanation until a provider recovers and the sync is re-run with --explain.
Generated once at sync time and cached in oj_entries.plain_explanation; never
called per page-view.

WHY CEREBRAS IS FIRST (8 September 2026)
----------------------------------------
This was Mistral-only, and Mistral's account allowance went to zero:

    HTTP/2 429
    x-ratelimit-limit-req-minute: 0        <- the LIMIT, not the remainder

A burst limit shows a non-zero limit with zero remaining. A limit of ZERO is a
lapsed plan. Explanations stopped dead after 3 September (59/59, 40/40 and 25/25
explained up to that date; 0 of 10, 0 of 53 and 0 of 32 after it), leaving 95
acts unexplained and every My OJ user looking at "L'explicació ha fallat,
torna-ho a provar" with a retry button that could never succeed.

Two lessons are baked in below:
  * ``is_available`` only checks that a key EXISTS. Mistral's key was perfectly
    valid; the quota was gone. So a provider that reports available can still
    throw on the first call, and the code must try the NEXT provider rather than
    give up.
  * A single-provider dependency with no fallback fails totally rather than
    degrading. Cerebras is the one provider actually serving Brubru traffic, and
    Mistral is kept as the second so a top-up restores redundancy automatically.
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
# Leading markdown / bullets Mistral sometimes adds when it skips the number
# on a single-item prompt (e.g. "**1.** ...", "- ...", "1) ...").
_LEAD_NOISE_RE = re.compile(r"^\s*(?:\*+\s*\d+[.)]?\s*\*+|\d+[.)]|[\-•*])\s*")
BATCH = 8

# ---------------------------------------------------------------------------
# Uninformative titles must NOT be explained (added 8 September 2026).
#
# Some OJ entries carry a title that names an instrument and says nothing else:
# "DECISION UNDER REGULATION (EU) 2023/2411", 17 of them in one backlog. Handed
# that and nothing more, a model does not decline -- it invents. Cerebras
# produced three DIFFERENT and entirely wrong explanations for three identical
# titles ("restrict exports to non-EU countries", "impose temporary bans on
# specific products", "suspend licences for particular imports") when the
# regulation in question is about geographical indications for craft and
# industrial products. An older Mistral run had already written "Approves a
# specific action under a financial services rule" for the same title.
#
# The models differ only in how they fail: Mistral hedged into vagueness,
# Cerebras invents specifics, which is worse. Neither can be right, because the
# information is not in the input.
#
# So: skip. The act keeps a null explanation, My OJ shows the official title and
# the "Explain with AI" button, and the user is not told something false. An
# absent explanation is a visible gap; a fabricated one is a lie with a citation.
_REF_ONLY_RE = re.compile(
    r"\(?(?:EU|UE|EC|CE|EEC|CEE|Euratom)\)?\s*(?:No\s*)?\d{1,4}/\d{2,4}"
    r"|\d{4}/\d{1,5}",
    re.IGNORECASE,
)
_BOILERPLATE_RE = re.compile(
    r"\b(?:decision|decisions|notice|notices|communication|communications|"
    r"information|informations|under|pursuant|to|of|the|a|an|and|or|for|in|on|"
    r"regulation|regulations|directive|directives|implementing|delegated|"
    r"commission|council|european|union|parliament|eu|ue)\b",
    re.IGNORECASE,
)


def _carries_subject_matter(title: str) -> bool:
    """False when the title is only a reference to another act.

    Strips instrument references and the boilerplate that surrounds them; if
    fewer than two content words remain, there is nothing to explain and the
    model would have to invent the subject.

    Threshold is TWO, not three: at three, "COMMISSION COMMUNICATION - European
    Capitals of Culture 2030" was skipped, and it plainly does have a subject.
    Measured over all 2,594 stored titles, two skips 39 (1.5%) with no false
    positive left.
    """
    if not title:
        return False
    rest = _BOILERPLATE_RE.sub(" ", _REF_ONLY_RE.sub(" ", title))
    words = [w for w in re.findall(r"[A-Za-zÀ-ÿ']{3,}", rest)]
    return len(words) >= 2


def _clean_single(text: str) -> str:
    """Single-item fallback: strip any leading bullet/number/markdown and pick
    the first non-empty line. These models often omit the "1." prefix for a
    single-item prompt — the strict regex would drop a perfectly valid answer."""
    for raw in (text or "").splitlines():
        line = _LEAD_NOISE_RE.sub("", raw).strip()
        if line:
            return line
    return ""


async def explain_batch(items: List[Dict[str, str]]) -> Dict[str, str]:
    """items: [{'key':..., 'title':...}]. Returns {key: plain_explanation}.

    Cerebras first, then Mistral; returns {} if none work (no Anthropic, no raise)."""
    if not items:
        return {}
    try:
        from services.ai.multi_provider_service import (
            CerebrasProvider, MistralProvider,
        )
    except Exception as e:  # pragma: no cover
        logger.warning(f"[OJ-EXPLAIN] cannot import providers: {e}")
        return {}

    # Cheap, open providers only. NEVER add Anthropic here: this runs over every
    # OJ act published and the whole point of the module is a capped cost.
    candidates = [CerebrasProvider, MistralProvider]
    provider = None
    for P in candidates:
        try:
            cand = P()
        except Exception as e:  # pragma: no cover
            logger.warning(f"[OJ-EXPLAIN] {P.__name__} construct failed: {e}")
            continue
        if not cand.is_available:
            logger.warning(f"[OJ-EXPLAIN] {P.__name__} has no key configured, trying next")
            continue
        # is_available only proves a key EXISTS. Mistral's key was valid while its
        # per-minute allowance was zero, so the only honest test is a real call.
        try:
            probe = await cand.generate(
                system_prompt="Reply with the single word OK.",
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=8, temperature=0,
            )
        except Exception as e:
            logger.warning(f"[OJ-EXPLAIN] {P.__name__} unusable ({type(e).__name__}: "
                           f"{str(e)[:120]}), trying next")
            continue
        if probe is None or probe.message is None:
            logger.warning(f"[OJ-EXPLAIN] {P.__name__} returned no message, trying next")
            continue
        provider = cand
        logger.info(f"[OJ-EXPLAIN] using {P.__name__}")
        break

    if provider is None:
        logger.error("[OJ-EXPLAIN] no cheap provider usable (tried %s) — returning {} so acts "
                     "keep a null explanation; re-run sync_oj.py --explain once one recovers",
                     ", ".join(P.__name__ for P in candidates))
        return {}

    # Drop reference-only titles BEFORE spending a call on them.
    skipped = [it for it in items if not _carries_subject_matter(it.get("title", ""))]
    items = [it for it in items if _carries_subject_matter(it.get("title", ""))]
    if skipped:
        logger.info("[OJ-EXPLAIN] skipping %d reference-only title(s) with no subject "
                    "matter (e.g. %r) — they keep a null explanation rather than an "
                    "invented one", len(skipped), (skipped[0].get("title") or "")[:70])
    if not items:
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
            logger.warning(f"[OJ-EXPLAIN] {type(provider).__name__} generate failed ({e}); stopping batch")
            break
        text = resp.message or ""
        # Strict numbered-list parse (multi-item batches need this to map back).
        for line in text.splitlines():
            m = _LINE_RE.match(line)
            if not m:
                continue
            idx = int(m.group(1)) - 1
            if 0 <= idx < len(chunk):
                out[chunk[idx]["key"]] = m.group(2).strip()
        # Single-item fallback: these models frequently return bare prose without
        # a "1." prefix when there is only one item — accept it.
        if len(chunk) == 1 and chunk[0]["key"] not in out:
            cleaned = _clean_single(text)
            if cleaned:
                out[chunk[0]["key"]] = cleaned
    return out
