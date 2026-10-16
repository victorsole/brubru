"""Every authenticated request records presence, at most once an hour (16 Oct 2026).

last_seen_at was NULL for 147 of 147 users: its writers were /auth/me (never called
by the app) and /auth/refresh (called only after a 401, when it fails too).
"""
import asyncio
import datetime as dt
from types import SimpleNamespace

import api.auth as auth


class _Query:
    def __init__(self, user):
        self.user = user

    def filter(self, *_a, **_k):
        return self

    def first(self):
        return self.user


class _DB:
    def __init__(self, user):
        self.user, self.commits = user, 0

    def query(self, *_a):
        return _Query(self.user)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


def _token(uid):
    return auth.create_access_token(data={"sub": uid, "email": "x@y.eu"})


def test_get_current_user_stamps_last_seen_at():
    user = SimpleNamespace(id="u1", is_active=True, last_seen_at=None)
    db = _DB(user)
    got = asyncio.run(auth.get_current_user(token=_token("u1"), db=db))
    assert got is user
    assert user.last_seen_at is not None and db.commits == 1


def test_second_request_within_the_hour_does_not_write_again():
    recent = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=5)
    user = SimpleNamespace(id="u1", is_active=True, last_seen_at=recent)
    db = _DB(user)
    asyncio.run(auth.get_current_user(token=_token("u1"), db=db))
    assert user.last_seen_at == recent and db.commits == 0


def test_after_an_hour_it_writes_again():
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)
    user = SimpleNamespace(id="u1", is_active=True, last_seen_at=old)
    db = _DB(user)
    asyncio.run(auth.get_current_user(token=_token("u1"), db=db))
    assert user.last_seen_at > old and db.commits == 1
