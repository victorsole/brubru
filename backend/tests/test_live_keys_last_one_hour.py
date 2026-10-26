"""The keys the live suites mint in production live one hour (register O52, 26 Oct 2026).

Interrupted runs left their throwaway users with usable keys: two "idnav" users (15 and 22 Sep),
later counted as an outside client, and nine more holding ten 180-day keys on 26 Oct.
"""
import ast
import pathlib
import sys
from datetime import datetime, timedelta, timezone

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from tests import live_keys  # noqa: E402


class _Db:
    def __init__(self, n):
        self.n, self.values, self.committed, self.closed = n, None, False, False

    def query(self, model):
        db = self

        class _Q:
            def filter(self, *a): return self
            def update(self, values): db.values = values; return db.n
        return _Q()

    def commit(self): self.committed = True
    def close(self): self.closed = True


def test_a_minted_key_is_cut_to_one_hour(monkeypatch):
    db = _Db(1)
    monkeypatch.setattr(live_keys, "SessionLocal", lambda: db)
    before = datetime.now(timezone.utc)
    live_keys.shorten_to_one_hour("5b0e2c9a-0000-0000-0000-000000000000")
    left = db.values["expires_at"] - before
    assert timedelta(minutes=59) < left <= timedelta(hours=1, seconds=5)
    assert db.committed and db.closed


def test_a_key_that_is_not_there_fails_the_run(monkeypatch):
    db = _Db(0)
    monkeypatch.setattr(live_keys, "SessionLocal", lambda: db)
    with pytest.raises(AssertionError):
        live_keys.shorten_to_one_hour("5b0e2c9a-0000-0000-0000-000000000000")
    assert db.closed


def test_every_suite_that_mints_through_the_endpoint_cuts_its_key():
    """A suite that POSTs /api/me/api-keys from a helper or fixture of its own must call
    shorten_to_one_hour in that same function; the endpoint's own tests (test_phase_a_api_keys,
    which check what the mint returns) are the exception."""
    missing = []
    for path in sorted((BACKEND / "tests").glob("test_*.py")):
        if path.name in ("test_phase_a_api_keys.py", pathlib.Path(__file__).name):
            continue
        tree = ast.parse(path.read_text())
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            src = ast.get_source_segment(path.read_text(), fn) or ""
            if '"/api/me/api-keys"' in src and ".post(" in src and "shorten_to_one_hour(" not in src:
                missing.append(f"{path.name}:{fn.name}")
    assert missing == []
