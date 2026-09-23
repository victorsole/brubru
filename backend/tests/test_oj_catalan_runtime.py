"""The My OJ Catalan drivers must run where there is no backend/.env (Railway).

Until 23 September 2026 both drivers opened backend/.env unconditionally, so
every Railway run died with FileNotFoundError before doing any work, while
every local run passed. These tests pin the environment-first lookup and the
refusal to translate without upload credentials.
"""
import importlib.util
import pathlib
import sys

import pytest

_SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"


@pytest.fixture()
def runtime(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("_oj_catalan_runtime", _SCRIPTS / "_oj_catalan_runtime.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # A backend dir with NO .env, like the Railway container.
    monkeypatch.setattr(mod, "BACKEND", tmp_path)
    for key in ("DATABASE_URL", "SITEGROUND_FTP_HOST", "SITEGROUND_FTP_USER",
                "SITEGROUND_FTP_PASS", "SITEGROUND_FTP_PORT"):
        monkeypatch.delenv(key, raising=False)
    return mod


def test_database_url_comes_from_the_environment_without_a_dotenv(runtime, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://env-host/db")
    assert runtime.database_url() == "postgresql://env-host/db"


def test_database_url_falls_back_to_dotenv_for_local_runs(runtime, tmp_path):
    (tmp_path / ".env").write_text("OTHER=1\nDATABASE_URL=postgresql://file-host/db\n")
    assert runtime.database_url() == "postgresql://file-host/db"


def test_environment_wins_over_dotenv(runtime, monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("DATABASE_URL=postgresql://file-host/db\n")
    monkeypatch.setenv("DATABASE_URL", "postgresql://env-host/db")
    assert runtime.database_url() == "postgresql://env-host/db"


def test_no_database_url_anywhere_raises_rather_than_guessing(runtime):
    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        runtime.database_url()


def test_missing_ftp_settings_are_named(runtime, monkeypatch):
    monkeypatch.setenv("SITEGROUND_FTP_HOST", "ftp.example")
    assert runtime.missing_ftp_settings() == ["SITEGROUND_FTP_USER", "SITEGROUND_FTP_PASS"]


@pytest.mark.parametrize("driver", ["translate_oj_daily_acts", "translate_oj_c_series"])
def test_driver_refuses_to_translate_without_upload_credentials(driver, runtime, monkeypatch, capsys):
    """No FTP credentials -> exit 1 before any DB read or translation."""
    monkeypatch.syspath_prepend(str(_SCRIPTS))
    sys.modules["_oj_catalan_runtime"] = runtime
    spec = importlib.util.spec_from_file_location(driver, _SCRIPTS / f"{driver}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "missing_ftp_settings", runtime.missing_ftp_settings)

    def _no_db(*a, **k):
        raise AssertionError("must not touch the database without upload credentials")

    monkeypatch.setattr(mod, "_pending", _no_db)
    assert mod.run(1, None) == 1
    assert "cannot deploy, not set: SITEGROUND_FTP_HOST" in capsys.readouterr().out


def test_run_bounded_kills_the_grandchild_too(runtime, tmp_path):
    """A timeout must take down what the child spawned (headless Chromium in
    production), not only the child: orphans exhausted the container's process
    table from 19 to 21 September 2026."""
    import os
    import subprocess
    import time as _t

    pidfile = tmp_path / "grandchild.pid"
    # The grandchild must NOT hold the output pipe: if it did, communicate()
    # would wait for it to exit on its own and the test could never fail
    # (measured: a child-only kill passed the first version of this test).
    script = (f"import subprocess,time; p=subprocess.Popen(['sleep','300'], stdout=subprocess.DEVNULL, "
              f"stderr=subprocess.DEVNULL); open(r'{pidfile}','w').write(str(p.pid)); time.sleep(300)")
    with pytest.raises(subprocess.TimeoutExpired):
        runtime.run_bounded([sys.executable, "-c", script], cwd=tmp_path, timeout=2)
    grandchild = int(pidfile.read_text())
    _t.sleep(0.3)
    try:
        os.kill(grandchild, 0)
        alive = True
    except ProcessLookupError:
        alive = False
    if alive:
        os.kill(grandchild, 9)
    assert not alive, "grandchild survived the timeout"


def test_run_bounded_returns_output_like_subprocess_run(runtime, tmp_path):
    p = runtime.run_bounded([sys.executable, "-c", "print('ok'); import sys; sys.exit(3)"], cwd=tmp_path, timeout=10)
    assert p.returncode == 3 and p.stdout.strip() == "ok"


def test_cooldown_reads_old_timestamps_and_new_records(runtime):
    import time as _t
    now = _t.time()
    fails = {"old_recent": now - 3600, "old_stale": now - 5 * 3600}
    assert runtime.in_cooldown(fails, "old_recent", 3)
    assert not runtime.in_cooldown(fails, "old_stale", 3)
    runtime.record_failure(fails, "timed_out", 72)
    fails["timed_out"]["ts"] = now - 10 * 3600
    assert runtime.in_cooldown(fails, "timed_out", 3), "a 72h timeout cooldown must outlast the 3h default"
    assert not runtime.in_cooldown(fails, "never_failed", 3)


def test_budget_caps_each_act_and_the_run(runtime):
    b = runtime.ActBudget(total_s=100, per_act_max_s=900)
    assert b.act_timeout() <= 70  # the run budget, less the 30s reserve, wins over 900
    assert runtime.ActBudget(total_s=5000, per_act_max_s=900).act_timeout() == 900
