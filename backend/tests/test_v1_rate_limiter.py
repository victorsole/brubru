"""Unit tests for the per-API-key sliding-window rate limiter."""

import asyncio
import pytest

from services.rate_limiter.global_rate_limiter import GlobalRateLimiter


@pytest.mark.asyncio
async def test_first_60_requests_allowed():
    limiter = GlobalRateLimiter()
    key_id = "test-key-1"
    for i in range(60):
        allowed, retry = await limiter.check_api_key_limit(key_id)
        assert allowed is True
        assert retry == 0
    assert limiter.get_remaining_api_key_calls(key_id) == 0


@pytest.mark.asyncio
async def test_61st_request_denied_with_retry_after():
    limiter = GlobalRateLimiter()
    key_id = "test-key-2"
    for _ in range(60):
        await limiter.check_api_key_limit(key_id)
    allowed, retry = await limiter.check_api_key_limit(key_id)
    assert allowed is False
    assert retry >= 1


@pytest.mark.asyncio
async def test_separate_keys_have_independent_windows():
    limiter = GlobalRateLimiter()
    for _ in range(60):
        await limiter.check_api_key_limit("key-a")
    # key-a exhausted, key-b still fresh
    allowed, _ = await limiter.check_api_key_limit("key-b")
    assert allowed is True
    assert limiter.get_remaining_api_key_calls("key-b") == 59


@pytest.mark.asyncio
async def test_remaining_count_decreases():
    limiter = GlobalRateLimiter()
    key_id = "test-key-3"
    for expected_remaining in [59, 58, 57, 56, 55]:
        await limiter.check_api_key_limit(key_id)
        assert limiter.get_remaining_api_key_calls(key_id) == expected_remaining
