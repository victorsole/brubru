"""A failed child must never be recorded with an empty error (24 Sep 2026).

The Catalan OJ jobs exit 1 after printing "[ERROR] cannot deploy, not set: ..."
to STDOUT. `_run_script` kept stdout only on success, so four Railway runs in a
row landed in sync_runs with error NULL and nobody could see why.
"""
import os
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from api.cron import _failure_detail, _run_script  # noqa: E402


def _script(tmp_path, body: str) -> str:
    p = tmp_path / "child.py"
    p.write_text(body)
    return str(p)  # absolute: os.path.join(backend_root, abs) returns abs


def test_stdout_reason_survives_when_stderr_is_empty(tmp_path):
    s = _script(tmp_path, 'print("[ERROR] cannot deploy, not set: SITEGROUND_FTP_HOST")\n'
                          'raise SystemExit(1)\n')
    res = _run_script("probe", s, timeout=30)
    assert res["status"] == "failed"
    assert "SITEGROUND_FTP_HOST" in res["stderr_tail"]
    assert res["stderr_tail"].startswith("rc=1")


def test_stderr_still_wins_when_present(tmp_path):
    s = _script(tmp_path, 'import sys\nprint("noise")\n'
                          'sys.stderr.write("Traceback: boom\\n")\nraise SystemExit(2)\n')
    res = _run_script("probe", s, timeout=30)
    assert "boom" in res["stderr_tail"] and "noise" not in res["stderr_tail"]


def test_silent_failure_is_never_blank(tmp_path):
    s = _script(tmp_path, "raise SystemExit(3)\n")
    res = _run_script("probe", s, timeout=30)
    assert res["stderr_tail"] == "rc=3: (no output)"


def test_success_is_unchanged(tmp_path):
    s = _script(tmp_path, 'print("done")\n')
    assert _run_script("probe", s, timeout=30)["status"] == "success"


def test_detail_helper():
    assert _failure_detail("", "x" * 2000, 1).startswith("rc=1: [stdout] ")
    assert len(_failure_detail("", "x" * 2000, 1)) < 520
