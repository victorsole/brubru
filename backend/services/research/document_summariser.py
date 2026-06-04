"""
Full-document AI summaries for Research & Evidence (MEUB 4.2).

Fetches a publication (HTML or PDF), extracts its text, and produces a plain-language
summary plus a personalised "How this is useful to you" tied to the user's policy
interests.

PROVIDER POLICY
---------------
Non-chat code, so NO Anthropic (CLAUDE.md hard rule). Uses a resilient chain of
non-Anthropic providers: Mistral -> GPT-4 -> Gemini. Each summary is cached to
disk by URL hash so a document is summarised once. If no non-Anthropic provider
is available, this raises and the UI shows an honest "unavailable" state.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "research_summary_cache"
_MAX_CHARS = 14000           # text sent to the model
_MAX_BYTES = 12_000_000      # do not download more than ~12 MB
_BROWSER_UA = {"User-Agent": "Mozilla/5.0 (compatible; Brubru/1.0; +https://brubru.beresol.eu)"}


# ----------------------------------------------------------------- text extraction
class _TextExtractor(HTMLParser):
    _SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer", "form"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag.lower() in self._SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t:
                self.parts.append(t)


def _html_text(html: str) -> str:
    p = _TextExtractor()
    try:
        p.feed(html)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
    return re.sub(r"\s+\n", "\n", "\n".join(p.parts))


def _pdf_text(raw: bytes) -> str:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(raw))
    pages = reader.pages[:40]
    return "\n".join((pg.extract_text() or "") for pg in pages)


def _fetch_text(url: str) -> Tuple[str, str]:
    """Download a document and return (text, kind). Raises on transport failure."""
    req = urllib.request.Request(url, headers=_BROWSER_UA)
    with urllib.request.urlopen(req, timeout=25) as r:
        ct = (r.headers.get("content-type") or "").lower()
        raw = r.read(_MAX_BYTES)
    is_pdf = "pdf" in ct or url.lower().split("?")[0].endswith(".pdf")
    if is_pdf:
        return _pdf_text(raw), "pdf"
    return _html_text(raw.decode("utf-8", "replace")), "html"


# ----------------------------------------------------------------- non-Anthropic LLM
async def _summarise_text(text: str, url: str, pi: List[str]) -> Tuple[str, str]:
    from services.ai.multi_provider_service import MistralProvider, OpenAIProvider, GeminiProvider

    interests = ", ".join(pi) if pi else "EU policy"
    system_prompt = (
        "You are an EU policy analyst writing for a busy public-affairs professional. "
        "Summarise the document below in plain British English. No jargon, no legal "
        "codes, no em-dashes, no emojis. Use exactly these two sections with these "
        "Markdown headers:\n"
        "## Summary\n"
        "Four to six short bullet points covering what the document is, its key findings "
        "or arguments, and any conclusions or recommendations.\n"
        "## How this is useful to you\n"
        "Two or three sentences explaining concretely how someone working on these policy "
        f"interests can use this document: {interests}. Be specific about the angle, not generic."
    )
    messages = [{"role": "user", "content": f"Document URL: {url}\n\nDocument text:\n{text}"}]

    last_err = None
    for Provider in (MistralProvider, OpenAIProvider, GeminiProvider):
        try:
            provider = Provider()
            if not provider.is_available:
                continue
            resp = await provider.generate(
                system_prompt=system_prompt, messages=messages, max_tokens=900, temperature=0.3,
            )
            msg = (resp.message or "").strip() if resp else ""
            if msg:
                # House rule: no em-dashes in Brubru-surfaced text.
                msg = msg.replace(" — ", ", ").replace("—", ", ").replace("–", "-")
                return msg, getattr(provider, "name", Provider.__name__)
        except Exception as e:  # try the next non-Anthropic provider
            last_err = e
            logger.warning("[research-summary] %s failed: %s", Provider.__name__, e)
    raise RuntimeError(f"No non-Anthropic provider available ({last_err})")


# ----------------------------------------------------------------- public API
def _cache_path(url: str) -> Path:
    return _CACHE_DIR / f"{hashlib.sha256(url.encode('utf-8')).hexdigest()[:24]}.json"


async def summarise(url: str, pi: List[str]) -> dict:
    """Full-document summary (cached by URL). Personalised to the user's interests.

    Note: the cache key is the URL only, so the (short) personalised section is shared
    across users; acceptable for a launchpad and keeps each document a one-time cost."""
    cache = _cache_path(url)
    if cache.exists():
        try:
            return {**json.loads(cache.read_text(encoding="utf-8")), "cached": True}
        except Exception:
            pass

    text, kind = _fetch_text(url)
    text = (text or "").strip()
    if len(text) < 200:
        raise ValueError("document text too short or could not be extracted")
    text = text[:_MAX_CHARS]

    summary, model = await _summarise_text(text, url, pi)
    out = {"summary": summary, "model": model, "kind": kind, "url": url}
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning("[research-summary] cache write failed: %s", e)
    return {**out, "cached": False}
