"""Runtime plumbing shared by the two My OJ Catalan full-text drivers.

`translate_oj_daily_acts.py` (L-series) and `translate_oj_c_series.py`
(C-series) run in two places: on this Mac, and on Railway from the `fast` tier
(`services/sync/source_registry.py`, keys `oj_acts_ca` / `oj_c_ca`).

WHY THIS EXISTS (23 September 2026). Both drivers were put on the Railway cron
on 28 August and had not produced a single page there. Every run failed on
its first line of real work, `open(BACKEND / ".env")`, because a Railway
container has no `.env`: the platform injects DATABASE_URL as an environment
variable. Locally the file exists, so every manual run looked healthy.

Reading the environment first was not enough on its own. The drivers wrote the
page to `data/legislacio-ue-catala/` and registered it UNDEPLOYED, leaving the
upload to `deploy_catalan_backlog.py`, which only ever runs on this Mac and
uploads from this Mac's disk. A page generated inside a Railway container
would have been registered, then lost at the next redeploy, and the local loop
would have found a row whose file it does not have. So each page is now
uploaded to SiteGround by the run that produced it, the remote size is checked
against the local one, and only then is `deployed_at` stamped. My OJ links a
card to the Catalan page only when `deployed_at` is set (`api/oj.py`), so a
failed upload leaves the reader on the EUR-Lex link rather than a dead one.
"""
from __future__ import annotations

import ftplib
import os
import signal
import subprocess
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
REMOTE_BASE = "brubru.beresol.eu/public_html/legislacio-ue-catala"
_FTP_KEYS = ("SITEGROUND_FTP_HOST", "SITEGROUND_FTP_USER", "SITEGROUND_FTP_PASS")


def _dotenv_value(name: str) -> str | None:
    """Value of `name` in backend/.env, or None when there is no such file (Railway)."""
    env_file = BACKEND / ".env"
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith(f"{name}="):
            return line.split("=", 1)[1].strip()
    return None


def setting(name: str) -> str | None:
    """Environment first (Railway), backend/.env second (local runs)."""
    return os.environ.get(name) or _dotenv_value(name)


def database_url() -> str:
    url = setting("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is set neither in the environment nor in backend/.env")
    return url


def missing_ftp_settings() -> list[str]:
    return [k for k in _FTP_KEYS if not setting(k)]


def _connect() -> ftplib.FTP:
    ftp = ftplib.FTP()
    ftp.connect(setting("SITEGROUND_FTP_HOST"), int(setting("SITEGROUND_FTP_PORT") or "21"), timeout=60)
    ftp.login(setting("SITEGROUND_FTP_USER"), setting("SITEGROUND_FTP_PASS"))
    return ftp


def upload_page(key: str, html_path: Path) -> tuple[bool, str]:
    """Upload one page to /legislacio-ue-catala/{key}/index.html and verify it.

    Returns (ok, detail). ok is True only when the remote size equals the local
    size. Directory handling avoids nlst(): the server caps listings at 10k
    entries, so a directory missing from a listing may still exist (the same
    rule as deploy_catalan_backlog.deploy_one).
    """
    local = html_path.stat().st_size
    last = "no attempt"
    for attempt in range(1, 4):
        ftp = None
        try:
            ftp = _connect()
            target = f"/{REMOTE_BASE}/{key}"
            try:
                ftp.cwd(target)
            except ftplib.error_perm:
                ftp.cwd(f"/{REMOTE_BASE}")
                try:
                    ftp.mkd(key)
                except ftplib.error_perm as exc:
                    if "550" not in str(exc):  # anything but "already exists" is real
                        raise
                ftp.cwd(target)
            with open(html_path, "rb") as fh:
                ftp.storbinary("STOR index.html", fh)
            remote = ftp.size("index.html")
            if remote == local:
                return True, f"{local} bytes, remote size matches"
            last = f"remote {remote} bytes != local {local} bytes"
        except Exception as exc:  # noqa: BLE001 -- retried, then reported
            last = f"{type(exc).__name__}: {str(exc)[:120]}"
        finally:
            if ftp is not None:
                try:
                    ftp.quit()
                except Exception:  # noqa: BLE001
                    pass
    return False, f"upload failed after 3 attempts ({last})"


def stamp_deployed(conn, key: str) -> None:
    """Mark the row deployed. Keyed like the deploy loop: COALESCE(celex, oj_id)."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE catalan_translations SET deployed_at = now(), updated_at = now() "
        "WHERE COALESCE(celex, oj_id) = %s",
        (key,),
    )
    if cur.rowcount == 0:
        raise RuntimeError(f"no catalan_translations row for {key} to stamp")
    conn.commit()


# --- time budget (23 September 2026) -----------------------------------------
# The fast tier gives each driver 1800s (`source_registry.py`) while a single
# act was allowed 3600s. The first live test after the .env fix sat on one act,
# Decision (CFSP) 2026/2161 (a long sanctions list), for more than 50 CPU-minutes.
# On Railway that act would have got the whole job killed at 1800s on every
# run, with no failure recorded, and newest-first ordering would have put it
# back at the head of the queue each time. Nothing behind it would ever ship.


class ActBudget:
    """A whole-run deadline plus a per-act ceiling."""

    def __init__(self, total_s: int, per_act_max_s: int = 900):
        self.deadline = time.monotonic() + total_s
        self.per_act_max_s = per_act_max_s

    def remaining(self) -> float:
        return self.deadline - time.monotonic()

    def act_timeout(self) -> int:
        # Keep 30s back so the loop can record the outcome before the tier kill.
        return int(max(1, min(self.per_act_max_s, self.remaining() - 30)))


def run_bounded(cmd: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess:
    """subprocess.run(capture_output, text) that kills the child's whole group.

    `subprocess.run(timeout=...)` SIGKILLs only the direct child. The fallbacks
    start headless Chromium, and orphaned Chromium is what exhausted the web
    container's process table from 19 to 21 September 2026. Raises
    subprocess.TimeoutExpired, like subprocess.run.
    """
    proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError, OSError):
            proc.kill()
        proc.communicate()
        raise
    return subprocess.CompletedProcess(cmd, proc.returncode, out, err)


def record_failure(fails: dict, key: str, hours: float) -> None:
    fails[key] = {"ts": time.time(), "h": hours}


def in_cooldown(fails: dict, key: str, default_h: float) -> bool:
    """Values are a bare timestamp (the pre-23-Sep format) or {"ts", "h"}."""
    v = fails.get(key)
    if not v:
        return False
    ts, h = (v, default_h) if isinstance(v, (int, float)) else (v.get("ts"), v.get("h", default_h))
    return bool(ts) and (time.time() - ts) < h * 3600
