"""Unit tests for the ApiKey model (no DB required)."""

import re
import uuid

from models.api_key import ApiKey, KEY_PREFIX


def test_generate_returns_plaintext_and_instance():
    user_id = uuid.uuid4()
    plaintext, instance = ApiKey.generate(user_id, name="test")

    assert plaintext.startswith(KEY_PREFIX)
    assert len(plaintext) == len(KEY_PREFIX) + 48
    assert re.fullmatch(r"brubru_live_[0-9a-f]{48}", plaintext)

    assert instance.user_id == user_id
    assert instance.name == "test"
    assert instance.key_prefix == plaintext[len(KEY_PREFIX):len(KEY_PREFIX) + 4]
    assert len(instance.key_hash) == 64
    assert instance.revoked_at is None
    assert instance.is_active is True


def test_generate_produces_unique_keys():
    user_id = uuid.uuid4()
    plaintexts = {ApiKey.generate(user_id, name=f"k{i}")[0] for i in range(50)}
    assert len(plaintexts) == 50


def test_hash_is_sha256_hex():
    hashed = ApiKey.hash_plaintext("brubru_live_deadbeef")
    assert re.fullmatch(r"[0-9a-f]{64}", hashed)
    # Stable
    assert ApiKey.hash_plaintext("brubru_live_deadbeef") == hashed


def test_verify_plaintext_constant_time_match():
    plaintext, instance = ApiKey.generate(uuid.uuid4(), name="x")
    assert ApiKey.verify_plaintext(plaintext, instance.key_hash) is True
    assert ApiKey.verify_plaintext(plaintext + "extra", instance.key_hash) is False
    assert ApiKey.verify_plaintext("brubru_live_wrong", instance.key_hash) is False
