"""A social drip must not wait silently on another drip's row locks.

25 Sep 2026: a manual /social-eu run sat 14 minutes at 0% CPU holding only its
database connection. Real DB: a second session holds a row lock on the oldest
account; the run must skip it within the lock timeout and still finish.
"""
import threading
import time

import pytest
from sqlalchemy import text

from core.database import SessionLocal
import services.social.post_fetcher as pf


def test_locked_account_is_skipped_not_waited_on(monkeypatch):
    holder = SessionLocal()
    victim = holder.execute(text(
        "SELECT id, platform FROM social_accounts WHERE content_fetch_enabled AND platform='bluesky' "
        "ORDER BY last_checked_at ASC NULLS FIRST LIMIT 1")).first()
    if victim is None:
        pytest.skip("no bluesky account")
    holder.execute(text("SELECT 1 FROM social_accounts WHERE id=:i FOR UPDATE"), {"i": victim.id})
    monkeypatch.setattr(pf, "fetch_for_account", lambda *a, **k: ([], None))
    db = SessionLocal()
    try:
        db.execute(text("SET lock_timeout = '1s'"))
        # run() sets 30s; shorten it for the test by patching the statement text
        orig = db.execute
        def patched(stmt, *a, **k):
            if "lock_timeout" in str(stmt):
                return orig(text("SET lock_timeout = '1s'"))
            return orig(stmt, *a, **k)
        monkeypatch.setattr(db, "execute", patched)
        t0 = time.monotonic()
        stats = pf.run(db, platforms=("bluesky",), limit_accounts=1, pace=0)
        assert stats["lock_skipped"] == 1
        assert time.monotonic() - t0 < 20
    finally:
        db.rollback(); db.close()
        holder.rollback(); holder.close()
