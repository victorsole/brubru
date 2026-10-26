"""API keys the live tests mint in the production database live one hour.

The live suites create a throwaway user, mint a key through /api/me/api-keys and delete both in
their teardown. A run stopped before the teardown leaves both behind: on 23 Oct 2026 two such
"idnav" users still held unrevoked keys and had been counted as an outside client (register O52),
and on 26 Oct nine more held ten usable 180-day keys. The mint offers 30, 90, 180 or 365 days
(api/me_api_keys.ALLOWED_EXPIRY_DAYS), so each key is shortened to one hour here, before its
first use: an interrupted run leaves nothing usable.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.database import SessionLocal
from models.api_key import ApiKey


def shorten_to_one_hour(key_id) -> None:
    db = SessionLocal()
    try:
        n = (db.query(ApiKey).filter(ApiKey.id == key_id)
             .update({"expires_at": datetime.now(timezone.utc) + timedelta(hours=1)}))
        db.commit()
        assert n == 1, f"key {key_id} not found to shorten"
    finally:
        db.close()
