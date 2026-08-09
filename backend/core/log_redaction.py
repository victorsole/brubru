"""Keep credentials out of the logs.

The Gemini provider used to put its API key in the query string, and httpx
logs every request URL at INFO, so the live key was written into the backend
output and therefore into Railway's log retention. That call site now sends
the key as a header, but the class of bug is easy to reintroduce -- any
library that logs a URL can leak any secret a caller puts in one.

This module is the backstop: a filter that rewrites secret-looking values out
of log records before a handler can emit them.
"""

import logging
import re
from typing import Iterable

REDACTED = "[REDACTED]"

# Query-string credentials (?key=..., &api_key=..., &access_token=...) and
# Authorization headers, in whatever text a library happens to log.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"([?&](?:key|api[_-]?key|access[_-]?token|token|auth|password|secret)=)[^&\s\"']+", re.I),
    # Header name and value may each be quoted, as in a logged dict literal:
    # headers={'Authorization': 'Bearer eyJ...'}. Allow the quotes between the
    # name and the separator, and before the value.
    re.compile(
        r"((?:Authorization|X-Goog-Api-Key|X-Api-Key)[\"']?\s*[:=]\s*[\"']?)"
        r"(?:Bearer\s+)?[^\s\"',}]+",
        re.I,
    ),
    # JWTs are recognisable on their own, wherever they appear.
    re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{4,}\.[A-Za-z0-9_\-]+"),
    # Vendor key shapes that are recognisable on their own, in case one is
    # logged without a surrounding parameter name.
    re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}"),          # Google
    re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}"),           # OpenAI-style
    re.compile(r"\bcsk-[A-Za-z0-9_\-]{20,}"),          # Cerebras
)


def scrub(text: str) -> str:
    """Replace any credential-looking substring with a marker."""
    out = text
    for pattern in _PATTERNS:
        if pattern.groups == 2:
            out = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", out)
        elif pattern.groups == 1:
            out = pattern.sub(lambda m: f"{m.group(1)}{REDACTED}", out)
        else:
            out = pattern.sub(REDACTED, out)
    return out


class SecretRedactingFilter(logging.Filter):
    """Scrub the message and its args before a handler formats them."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            if record.args:
                # Format first, then scrub the result. Scrubbing the template
                # separately can consume the "%s" itself -- "Authorization:
                # 'Bearer %s'" matches the header pattern placeholder and all
                # -- leaving a template with no placeholder and an argument
                # still to apply, which raises TypeError inside logging.
                record.msg = scrub(record.getMessage())
                record.args = ()
            elif isinstance(record.msg, str) and record.msg:
                record.msg = scrub(record.msg)
        except Exception:  # never let logging hygiene break a request
            pass
        return True


def install_secret_redaction(extra_loggers: Iterable[str] = ()) -> None:
    """
    Attach the filter to every root handler and quieten httpx.

    Filters on a *logger* only see records logged directly to it, not records
    propagated up from children -- so the filter goes on the root *handlers*,
    which every propagated record must pass through. Call this after the
    server has configured logging, or the handlers do not exist yet.
    """
    redactor = SecretRedactingFilter()
    root = logging.getLogger()
    for handler in root.handlers:
        if not any(isinstance(f, SecretRedactingFilter) for f in handler.filters):
            handler.addFilter(redactor)

    for name in ("uvicorn", "uvicorn.access", "uvicorn.error", *extra_loggers):
        for handler in logging.getLogger(name).handlers:
            if not any(isinstance(f, SecretRedactingFilter) for f in handler.filters):
                handler.addFilter(redactor)

    # httpx logs "HTTP Request: POST <full url>" at INFO for every call. The
    # URLs no longer carry secrets, and the line is pure noise at our volume.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
