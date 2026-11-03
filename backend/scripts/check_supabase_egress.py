"""Warn before Supabase's egress quota runs out (Victor, 3 Nov 2026).

Going over the quota again means restriction, not a bill: the spend cap stays on and there is no second grace
period, so the next excess can answer 402 on every request. The dashboard's figure has no public route, so this reads
the network counter in Supabase's metrics feed: `node_network_transmit_bytes_total`, what the database machine has
sent. It ran at about 1.1 GB a day against the dashboard's 1.1 over a short sample on 3 Nov: compare a full day
with the dashboard before trusting the absolute figure. It sees one project; brubru is 610.8 of the organisation's
611 GB.

It runs hourly because the spike of 15 Oct 2026 spent about 300 GB in two hours. It runs on the Mac because mail
cannot leave Railway (Hobby plan). An alert is a Mac notification and one mail to the address below, at most once a
day for each reason. A reading that fails is an alert too: silence must never read as "all fine".

Run:
    python3.12 scripts/check_supabase_egress.py            # read, update the state, alert if needed
    python3.12 scripts/check_supabase_egress.py --status   # print the state; reads nothing, sends nothing
    python3.12 scripts/check_supabase_egress.py --dry-run  # read and print; writes and sends nothing
    python3.12 scripts/check_supabase_egress.py --test-notification   # one Mac notification, no mail

Environment: BRUBRU_ENV_FILE points at the .env holding SUPABASE_URL, SUPABASE_SERVICE_KEY and SMTP_*.
EGRESS_STATE_FILE and EGRESS_ALERT_TO override the state file and the recipient.

Exit: 0 fine, 1 an alert is standing, 2 the reading failed, 3 an alert could not be mailed.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import smtplib
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Dict, List, Optional, Tuple

GB = 1e9
QUOTA_GB = 250.0
CYCLE_DAY = 4                # The billing cycle runs from the 4th to the 4th.
EVEN_PACE_GB_A_DAY = 8.0     # 250 GB over 31 days: more than this in a day, every day, uses up the quota.
SPIKE_GB_AN_HOUR = 5.0
SPIKE_MIN_GB = 2.0           # So that a small reading over a few minutes is not called a spike.
CYCLE_WARN_GB = 125.0
CYCLE_URGENT_GB = 200.0
PROJECT_AFTER_DAYS = 3
STALE_AFTER_HOURS = 26
KEEP_READINGS_HOURS = 49
COUNTER = "node_network_transmit_bytes_total"
DEFAULT_TO = "hello@beresol.eu"
USAGE_PAGE = "https://supabase.com/dashboard/org/_/usage"


def state_path() -> pathlib.Path:
    return pathlib.Path(os.environ.get("EGRESS_STATE_FILE") or pathlib.Path.home() / ".brubru_tools" / "egress_state.json")


def load_env() -> Dict[str, str]:
    """The named .env, else the repo's own, with the process's environment on top."""
    root = pathlib.Path(__file__).resolve().parents[2]
    found: Dict[str, str] = {}
    for candidate in (os.environ.get("BRUBRU_ENV_FILE"), root / "backend" / ".env", root / ".env"):
        if candidate and pathlib.Path(candidate).exists():
            for line in pathlib.Path(candidate).read_text(errors="ignore").splitlines():
                if "=" in line and not line.lstrip().startswith("#"):
                    name, value = line.split("=", 1)
                    found.setdefault(name.strip(), value.strip().strip('"').strip("'"))
    found.update({k: v for k, v in os.environ.items() if k.startswith(("SUPABASE_", "SMTP_"))})
    return found


def parse_counter(text: str) -> float:
    """Bytes sent over every network device but the loopback. A feed without the counter is a failure, not a zero."""
    total, seen = 0.0, False
    for line in text.splitlines():
        if line.startswith(COUNTER) and 'device="lo"' not in line:
            total += float(line.rsplit(" ", 1)[1])
            seen = True
    if not seen:
        raise ValueError(f"the metrics feed has no {COUNTER}")
    return total


def read_counter(env: Dict[str, str]) -> float:
    url = env.get("SUPABASE_URL", "").rstrip("/")
    key = env.get("SUPABASE_SERVICE_KEY", "")
    if not url or not key:
        raise ValueError("SUPABASE_URL or SUPABASE_SERVICE_KEY is not set")
    token = base64.b64encode(f"service_role:{key}".encode()).decode()
    request = urllib.request.Request(f"{url}/customer/v1/privileged/metrics", headers={"Authorization": f"Basic {token}"})
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        context = ssl.create_default_context()
    with urllib.request.urlopen(request, context=context, timeout=60) as response:
        return parse_counter(response.read().decode("utf-8", "replace"))


def cycle_start(now: datetime) -> date:
    day = now.date()
    if day.day >= CYCLE_DAY:
        return day.replace(day=CYCLE_DAY)
    return (day.replace(day=1) - timedelta(days=1)).replace(day=CYCLE_DAY)


def cycle_days(start: date) -> int:
    following = (start.replace(day=28) + timedelta(days=8)).replace(day=CYCLE_DAY)
    return (following - start).days


def advance(state: dict, counter: float, now: datetime) -> dict:
    """The state after one reading. The counter restarts with the machine, so a lower reading is a fresh count."""
    last = state.get("counter")
    delta = 0.0 if last is None else (counter - last if counter >= last else counter)
    start = cycle_start(now).isoformat()
    if state.get("cycle") != start:
        state["cycle"] = start
        state["cycle_bytes"] = 0.0
        # A first reading after the cycle began cannot know what came before it.
        state["cycle_from"] = now.isoformat() if now.date().isoformat() != start or last is None else start
    state["cycle_bytes"] = state.get("cycle_bytes", 0.0) + delta
    state["all_bytes"] = state.get("all_bytes", 0.0) + delta
    state["counter"] = counter
    state["last_read"] = now.isoformat()
    readings = state.get("readings", []) + [[now.isoformat(), state["all_bytes"]]]
    cutoff = now - timedelta(hours=KEEP_READINGS_HOURS)
    state["readings"] = [r for r in readings if datetime.fromisoformat(r[0]) >= cutoff]
    state.pop("last_error", None)
    return state


def last_hours_gb(state: dict, now: datetime, hours: float) -> float:
    readings = state.get("readings", [])
    inside = [r for r in readings if datetime.fromisoformat(r[0]) >= now - timedelta(hours=hours)]
    return (readings[-1][1] - inside[0][1]) / GB if inside else 0.0


def latest_rate(state: dict) -> Tuple[float, float]:
    """GB and GB an hour between the last two readings. The Mac may have slept in between, so this is a rate."""
    readings = state.get("readings", [])
    if len(readings) < 2:
        return 0.0, 0.0
    hours = (datetime.fromisoformat(readings[-1][0]) - datetime.fromisoformat(readings[-2][0])).total_seconds() / 3600
    gb = (readings[-1][1] - readings[-2][1]) / GB
    return gb, gb / max(hours, 0.25)


def alerts(state: dict, now: datetime) -> List[Tuple[str, str]]:
    """(reason, sentence) for each threshold passed. An urgent one is named so; the rest are warnings."""
    found: List[Tuple[str, str]] = []
    gb, rate = latest_rate(state)
    if gb >= SPIKE_MIN_GB and rate >= SPIKE_GB_AN_HOUR:
        found.append(("urgent-spike", f"URGENT: {gb:.1f} GB in the last reading, {rate:.1f} GB an hour. On 15 Oct a spike like this spent about 300 GB in two hours."))
    cycle_gb = state.get("cycle_bytes", 0.0) / GB
    if cycle_gb >= CYCLE_URGENT_GB:
        found.append(("urgent-cycle", f"URGENT: {cycle_gb:.0f} GB of {QUOTA_GB:.0f} GB used this cycle."))
    elif cycle_gb >= CYCLE_WARN_GB:
        found.append(("warn-cycle", f"{cycle_gb:.0f} GB of {QUOTA_GB:.0f} GB used this cycle."))
    day_gb = last_hours_gb(state, now, 24)
    if day_gb >= EVEN_PACE_GB_A_DAY:
        found.append(("warn-day", f"{day_gb:.1f} GB in the last 24 hours; {EVEN_PACE_GB_A_DAY:.0f} GB a day would use up the quota."))
    start = date.fromisoformat(state["cycle"]) if state.get("cycle") else cycle_start(now)
    elapsed = (now.date() - start).days + now.hour / 24
    if elapsed >= PROJECT_AFTER_DAYS:
        projected = cycle_gb / elapsed * cycle_days(start)
        if projected >= QUOTA_GB and cycle_gb < CYCLE_URGENT_GB:
            found.append(("warn-projected", f"At this pace the cycle ends near {projected:.0f} GB, over the {QUOTA_GB:.0f} GB quota."))
    return found


def status_line(state: dict, now: datetime) -> str:
    if not state.get("last_read"):
        if state.get("last_error"):
            return f"Egress: no reading yet. LAST READ FAILED: {state['last_error']}"
        return "Egress: no reading yet. The alert has never run."
    age =(now - datetime.fromisoformat(state["last_read"])).total_seconds() / 3600
    start = state.get("cycle_from") or state.get("cycle")
    line = (f"Egress: {last_hours_gb(state, now, 24):.2f} GB in the last 24 h, {state.get('cycle_bytes', 0.0) / GB:.1f} of "
            f"{QUOTA_GB:.0f} GB this cycle (counted from {str(start)[:10]}). Last read {age:.1f} h ago.")
    if age > STALE_AFTER_HOURS:
        line += " STALE: the alert has not run for over a day, so no alert does not mean all is fine."
    if state.get("last_error"):
        line += f" LAST READ FAILED: {state['last_error']}"
    return line


def notify_mac(title: str, message: str) -> None:
    script = 'display notification (item 2 of argv) with title (item 1 of argv)\n'
    subprocess.run(["osascript", "-e", f"on run argv\n{script}end run", title, message[:220]], check=False, capture_output=True, timeout=30)


def send_mail(env: Dict[str, str], subject: str, body: str) -> None:
    message = EmailMessage()
    sender = env["SMTP_USER"]
    message["From"] = f"{env.get('SMTP_FROM_NAME', 'Brubru')} <{sender}>"
    message["To"] = os.environ.get("EGRESS_ALERT_TO") or DEFAULT_TO
    message["Subject"] = subject
    message.set_content(body)
    with smtplib.SMTP(env["SMTP_HOST"], int(env.get("SMTP_PORT", 587)), timeout=30) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        smtp.login(sender, env["SMTP_PASSWORD"])
        smtp.send_message(message)


def not_sent_today(state: dict, reason: str, now: datetime) -> bool:
    today = now.date().isoformat()
    sent = state.setdefault("sent", {})
    for day in [d for d in sent if d != today]:
        del sent[day]
    return reason not in sent.get(today, [])


def mark_sent(state: dict, reason: str, now: datetime) -> None:
    state.setdefault("sent", {}).setdefault(now.date().isoformat(), []).append(reason)


def raise_alert(env: Dict[str, str], state: dict, reason: str, sentence: str, now: datetime) -> bool:
    """Notification and mail, once a day for each reason. False when the mail did not go, which is kept and retried."""
    if not not_sent_today(state, reason, now):
        return True
    notify_mac("Brubru: Supabase egress", sentence)
    body = (f"{sentence}\n\n{status_line(state, now)}\n\nThe quota is {QUOTA_GB:.0f} GB a cycle and the spend cap is on, so going over "
            f"can restrict the projects, with a 402 on every request, until the next cycle.\n\nThe real figure: {USAGE_PAGE}\n"
            "The figure here is what the database machine sent, read from Supabase's metrics feed.\n"
            "Who is calling: api_usage_events by key, and Railway's logs by address.\n")
    try:
        send_mail(env, f"Brubru: {sentence[:90]}", body)
    except Exception as error:  # noqa: BLE001 - any mail failure must reach the operator, not the log alone.
        notify_mac("Brubru: egress alert NOT mailed", f"{type(error).__name__}. {sentence}")
        state["last_mail_error"] = f"{now.isoformat()} {type(error).__name__}"
        return False
    state.pop("last_mail_error", None)
    mark_sent(state, reason, now)
    return True


def load_state(path: pathlib.Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(path: pathlib.Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=1))
    temporary.replace(path)


def run(env: Dict[str, str], path: pathlib.Path, now: datetime, dry_run: bool = False, reader=read_counter) -> int:
    state = load_state(path)
    try:
        counter = reader(env)
    except (urllib.error.URLError, OSError, ValueError, KeyError) as error:
        detail = f"HTTP {error.code}" if isinstance(error, urllib.error.HTTPError) else type(error).__name__
        state["last_error"] = f"{now.isoformat()} {detail}"
        print(f"[ERROR] the egress reading failed: {detail}")
        if not dry_run:
            raise_alert(env, state, "read-failed", f"The egress alert could not read Supabase's metrics ({detail}), so it is not watching. A rotated service key causes this.", now)
            save_state(path, state)
        return 2
    state = advance(state, counter, now)
    standing = alerts(state, now)
    print(f"[OK] {status_line(state, now)}" if not standing else f"[ALERT] {status_line(state, now)}")
    for _, sentence in standing:
        print(f"  {sentence}")
    if dry_run:
        return 1 if standing else 0
    mailed = all([raise_alert(env, state, reason, sentence, now) for reason, sentence in standing])
    save_state(path, state)
    if not mailed:
        return 3
    return 1 if standing else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--status", action="store_true", help="print the state; reads nothing, sends nothing")
    parser.add_argument("--dry-run", action="store_true", help="read and print; writes and sends nothing")
    parser.add_argument("--test-notification", action="store_true", help="one Mac notification, no mail")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    path = state_path()
    if args.status:
        print(status_line(load_state(path), now))
        return 0
    if args.test_notification:
        notify_mac("Brubru: Supabase egress", "Test: the egress alert can reach this Mac.")
        print("[OK] notification sent")
        return 0
    return run(load_env(), path, now, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
