"""
Environment-driven settings for the response validator.

History:
- 12 May 2026: validator scaffolded, defaults OFF + shadow mode.
- 28 May 2026: after the EFPIA-demo Biotech Act / Andriukaitis fabrication
  incident, flipped defaults so the validator is ON in production by default
  and runs in CRITICAL_OVERRIDE mode (replaces the response with a safe
  refusal template when severity=critical). Backend now Mistral-only per
  hard rule.

Workstream 1 of the Chat AI architecture evolution (see
memory/project_chat_ai_architecture_evolution.md).
"""

from __future__ import annotations

import os


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


# Top-level kill switch. ON by default since 28 May 2026.
VALIDATOR_ENABLED = _env_bool("VALIDATOR_ENABLED", True)

# Shadow mode: validate + log, but never modify the shipped response.
# OFF by default since 28 May 2026 -- we now act on critical findings.
VALIDATOR_SHADOW_MODE = _env_bool("VALIDATOR_SHADOW_MODE", False)

# Action on critical violation:
#   "override" -- replace the assistant response with a safe refusal template
#                 that names the violation types (default since 28 May 2026,
#                 lowest-latency option).
#   "regenerate" -- run one regeneration pass with a hardened constraint
#                   citing the violations (higher latency, more compute).
#   "log"        -- only log the violation, do not modify the response (use
#                   for measurement windows; equivalent to shadow mode for
#                   critical-only).
VALIDATOR_CRITICAL_ACTION = os.environ.get("VALIDATOR_CRITICAL_ACTION", "override").strip().lower()

# Maximum regeneration retries when VALIDATOR_CRITICAL_ACTION="regenerate".
VALIDATOR_MAX_RETRIES = _env_int("VALIDATOR_MAX_RETRIES", 1)

# Validator model. Claude Haiku 4.5 (cheap, fast, sufficient for bounded
# fact-checking task). Override only for experiments. Chat-related code stays
# on Anthropic per memory/feedback_chat_must_use_anthropic.md.
VALIDATOR_MODEL = os.environ.get("VALIDATOR_MODEL", "claude-haiku-4-5-20251001")

# Hard cap on the context fed to the validator.
VALIDATOR_CONTEXT_CHAR_CAP = _env_int("VALIDATOR_CONTEXT_CHAR_CAP", 80_000)

# Hard cap on the response excerpt stored in chat_validations.response_excerpt.
VALIDATOR_RESPONSE_TRUNCATE = _env_int("VALIDATOR_RESPONSE_TRUNCATE", 4000)

# Hard cap on the query stored in chat_validations.query.
VALIDATOR_QUERY_TRUNCATE = _env_int("VALIDATOR_QUERY_TRUNCATE", 1000)

# Validator request timeout in seconds.
VALIDATOR_TIMEOUT_SECONDS = _env_int("VALIDATOR_TIMEOUT_SECONDS", 20)
