"""In-app schedulers start on Railway only, unless overridden (16 Oct 2026).

A local backend started for chat probes ran the production schedulers: on 15 Oct a
local tender digest ran beside Railway's and 5 users received two digests.
"""
import ast
import pathlib

import pytest

from services.sync.freshness import in_app_schedulers_enabled

RAILWAY_VARS = ("RAILWAY_ENVIRONMENT", "RAILWAY_SERVICE_NAME", "BRUBRU_RUNNER", "ENABLE_IN_APP_SCHEDULERS")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for v in RAILWAY_VARS:
        monkeypatch.delenv(v, raising=False)


def test_off_on_a_laptop_by_default():
    assert in_app_schedulers_enabled() is False


def test_on_when_railway_says_so(monkeypatch):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    assert in_app_schedulers_enabled() is True


@pytest.mark.parametrize("flag,expected", [("true", True), ("1", True), ("false", False), ("0", False)])
def test_explicit_flag_wins(monkeypatch, flag, expected):
    monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
    monkeypatch.setenv("ENABLE_IN_APP_SCHEDULERS", flag)
    assert in_app_schedulers_enabled() is expected


def test_every_scheduler_start_in_main_sits_under_the_gate():
    """No start_*_scheduler() call in the lifespan may run outside `if _schedulers_on:`
    (the RSS scheduler keeps its own ENABLE_RSS_SCHEDULER opt-in)."""
    src = (pathlib.Path(__file__).resolve().parents[1] / "main.py").read_text()
    tree = ast.parse(src)
    gated, ungated = [], []

    def visit(node, under_gate):
        for child in ast.iter_child_nodes(node):
            g = under_gate or (isinstance(child, ast.If) and isinstance(child.test, ast.Name)
                               and child.test.id == "_schedulers_on")
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) \
                    and child.func.id.startswith("start_") and child.func.id.endswith("scheduler"):
                (gated if under_gate else ungated).append(child.func.id)
            visit(child, g)

    visit(tree, False)
    assert sorted(gated) == ["start_amendment_sync_scheduler", "start_email_scheduler",
                             "start_notification_scheduler", "start_tender_match_scheduler"]
    assert ungated == ["start_scheduler"]  # RSS, opt-in via its own flag
