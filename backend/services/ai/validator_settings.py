"""
Environment-driven settings for the response validator.

Defaults are conservative: validator is OFF in production until VALIDATOR_ENABLED
is explicitly set to "true", and even when ON it ships in shadow mode (logs
violations, does not regenerate the response).

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


# Top-level kill switch. When false, the validator is a no-op and no chat_validations
# rows are written. Set to "true" in Railway env vars when ready to measure.
VALIDATOR_ENABLED = _env_bool("VALIDATOR_ENABLED", False)

# Shadow mode: validate + log, but never modify the shipped response. This is
# the first-phase rollout per project_chat_ai_architecture_evolution.md decision
# locked 12 May 2026. After ~7 days of shadow-mode data we flip this to false
# to enable regeneration on critical violations.
VALIDATOR_SHADOW_MODE = _env_bool("VALIDATOR_SHADOW_MODE", True)

# Maximum regeneration retries on critical violation. Only consulted when
# VALIDATOR_SHADOW_MODE=false. Default cap=1 per design decision.
VALIDATOR_MAX_RETRIES = _env_int("VALIDATOR_MAX_RETRIES", 1)

# Validator model. Default Haiku 4.5 (cheap, fast, sufficient for bounded
# fact-checking task). Override only for experiments.
VALIDATOR_MODEL = os.environ.get("VALIDATOR_MODEL", "claude-haiku-4-5-20251001")

# Hard cap on the context fed to the validator. The generator's context_str
# can reach 32k chars; Haiku 4.5 has 200k context but we keep the prompt
# small to bound latency.
VALIDATOR_CONTEXT_CHAR_CAP = _env_int("VALIDATOR_CONTEXT_CHAR_CAP", 80_000)

# Hard cap on the response excerpt stored in chat_validations.response_excerpt.
VALIDATOR_RESPONSE_TRUNCATE = _env_int("VALIDATOR_RESPONSE_TRUNCATE", 4000)

# Hard cap on the query stored in chat_validations.query.
VALIDATOR_QUERY_TRUNCATE = _env_int("VALIDATOR_QUERY_TRUNCATE", 1000)

# Validator request timeout in seconds.
VALIDATOR_TIMEOUT_SECONDS = _env_int("VALIDATOR_TIMEOUT_SECONDS", 20)
