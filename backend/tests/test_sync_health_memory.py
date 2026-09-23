"""/api/sync/health reports container memory and browser RSS (23 Sep 2026)."""
import builtins
import io
import os

from api.sync_status import _memory_usage

FAKE = {
    "/sys/fs/cgroup/memory.current": "1258291200\n",   # 1200 MB
    "/sys/fs/cgroup/memory.max": "max\n",
    "/proc/10/comm": "chromium\n", "/proc/10/status": "Name:\tchromium\nVmRSS:\t 204800 kB\n",
    "/proc/11/comm": "headless_shell\n", "/proc/11/status": "VmRSS:\t 102400 kB\n",
    "/proc/12/comm": "python3.11\n", "/proc/12/status": "VmRSS:\t 409600 kB\n",
}


def test_reads_cgroup_memory_and_sums_browser_rss(monkeypatch):
    real_open = builtins.open

    def fake_open(path, *a, **k):
        if path in FAKE:
            return io.StringIO(FAKE[path])
        if str(path).startswith(("/proc/", "/sys/")):
            raise OSError(path)
        return real_open(path, *a, **k)

    monkeypatch.setattr(builtins, "open", fake_open)
    monkeypatch.setattr(os, "listdir", lambda p: ["10", "11", "12", "self"] if p == "/proc" else [])
    monkeypatch.setattr(os, "getpid", lambda: 12)

    m = _memory_usage()
    assert m["state"] == "ok"
    assert m["container_mb"] == 1200.0 and m["container_max_mb"] is None
    assert m["web_process_rss_mb"] == 400.0
    assert m["browser_processes"] == {"count": 2, "rss_mb": 300.0}


def test_unreadable_counters_are_unknown_not_zero(monkeypatch):
    def no_files(path, *a, **k):
        raise OSError(path)

    monkeypatch.setattr(builtins, "open", no_files)
    assert _memory_usage()["state"] == "unknown"
