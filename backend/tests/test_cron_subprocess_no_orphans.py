"""The 19-22 September 2026 ingestion outage, as tests.

Root cause: `_run_script` used `subprocess.run(timeout=...)`, which SIGKILLs only
the DIRECT child. The sync scripts launch headless Chromium plus a Playwright
driver, so every timeout orphaned a process tree. After ten days of 7-11 timeouts
a day the container could no longer fork and every sync failed with a bare
`[Errno 11] Resource temporarily unavailable`.

Test 1 reproduces the orphan with a real grandchild process and asserts it dies.
Test 2 pins the dispatcher exit code, which is why nobody was told for 3.5 days.
"""

import os
import pathlib
import signal
import subprocess
import sys
import time

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)


def _alive(pid: int) -> bool:
    """True if the pid exists and is not a reaped zombie."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    # On Linux a killed-but-unreaped child lingers as a zombie; treat that as dead.
    if sys.platform.startswith("linux"):
        try:
            with open(f"/proc/{pid}/stat") as fh:
                return fh.read().rsplit(")", 1)[-1].split()[0] != "Z"
        except OSError:
            return False
    return True


@pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
def test_timeout_kills_the_whole_process_tree_not_just_the_child(tmp_path):
    """A script that spawns a long-lived grandchild and then hangs.

    This is Chromium in miniature. Before the fix the grandchild survived the
    timeout; that survivor, multiplied by ten days, is the outage.
    """
    from api.cron import _run_script

    marker = tmp_path / "grandchild.pid"
    script = tmp_path / "spawns_a_grandchild.py"
    script.write_text(
        "import subprocess, sys, pathlib, time\n"
        # Detached, long-lived grandchild -- stands in for the Chromium tree.
        "kid = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(300)'])\n"
        f"pathlib.Path(r'{marker}').write_text(str(kid.pid))\n"
        "time.sleep(300)\n"          # the parent hangs, so _run_script times out
    )

    result = _run_script("orphan-probe", os.path.relpath(script, _BACKEND), timeout=3)

    assert result["status"] == "failed"
    assert result["error"] == "timeout_3s"

    assert marker.exists(), "probe script never recorded its grandchild pid"
    grandchild = int(marker.read_text())

    # SIGKILL delivery is asynchronous; give it a bounded moment.
    for _ in range(50):
        if not _alive(grandchild):
            break
        time.sleep(0.1)

    assert not _alive(grandchild), (
        f"grandchild {grandchild} survived the timeout -- the process group was not "
        "killed, so Chromium would leak exactly as it did on 19 September 2026"
    )


@pytest.mark.skipif(os.name != "posix", reason="process groups are POSIX-only")
def test_child_runs_in_its_own_process_group_so_killpg_cannot_kill_the_backend():
    """`start_new_session=True` is load-bearing in both directions.

    Without it the child shares OUR process group, and the killpg that fixes the
    leak would take down the web server with it.
    """
    from api.cron import _run_script

    probe = pathlib.Path(_BACKEND) / "_pgid_probe.py"
    probe.write_text("import os; print(os.getpgrp())\n")
    try:
        result = _run_script("pgid-probe", "_pgid_probe.py", timeout=30)
        assert result["status"] == "success", result
        child_pgid = int(result["stdout_tail"].strip())
        assert child_pgid != os.getpgrp(), (
            "child shares the backend's process group; killpg would kill the backend"
        )
    finally:
        probe.unlink(missing_ok=True)


def test_dispatcher_exits_non_zero_when_every_job_in_a_tier_failed():
    """The exact shape that hid the outage.

    `/api/cron/sync/tier/fast` returns no top-level "status", so the dispatcher's
    success/failure counters matched neither and it exited 0 every hour while
    ingestion was dead.
    """
    sys.path.insert(0, os.path.join(_BACKEND, "scripts"))
    from cron_dispatch import _iter_job_statuses

    outage_payload = {
        "tier": "fast",
        "ran": {
            "news_dg": "failed", "news_ep": "failed", "news_bespoke": "failed",
            "news_ft": "failed", "oj": "failed", "oj_catalan": "failed",
            "votes_ep": "failed", "votes_council": "failed",
        },
        "stale_fast": [],
    }
    statuses = _iter_job_statuses(outage_payload)
    assert len(statuses) == 8
    assert all(s == "failed" for _, s in statuses)

    healthy = {"tier": "fast", "ran": {"news_dg": "success", "oj": "skipped"}}
    assert [s for _, s in _iter_job_statuses(healthy)] == ["success", "skipped"]

    economy = {"ok": 0, "failures": ["eea: [Errno 11] Resource temporarily unavailable",
                                     "efsa: [Errno 11] Resource temporarily unavailable"]}
    assert [j for j, _ in _iter_job_statuses(economy)] == ["eea", "efsa"]

    # A payload with nothing per-job in it must not invent failures.
    assert _iter_job_statuses({"status": "success"}) == []
    assert _iter_job_statuses(None) == []


def test_process_limits_gauge_is_three_state_and_never_reassures_blindly():
    """An unreadable counter must read 'unknown', never a comfortable number."""
    from api.sync_status import _process_limits

    out = _process_limits()
    assert "state" in out
    assert out["state"] in {"ok", "warn", "critical", "unknown"}
    if out["state"] == "unknown":
        assert out["pids_current"] is None
