"""The egress alert (Victor, 3 Nov 2026): warn before the quota runs out, and never let a failed reading look like quiet."""
import importlib.util
import json
import pathlib
import urllib.error
from datetime import date, datetime, timedelta, timezone

import pytest

_PATH = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "check_supabase_egress.py"
_spec = importlib.util.spec_from_file_location("check_supabase_egress", _PATH)
egress = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(egress)

GB = 1e9
T0 = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def sends(monkeypatch):
    """Nothing here reaches a real Mac or a real mailbox."""
    sent = {"mail": [], "mac": []}
    monkeypatch.setattr(egress, "send_mail", lambda env, subject, body: sent["mail"].append((subject, body)))
    monkeypatch.setattr(egress, "notify_mac", lambda title, message: sent["mac"].append((title, message)))
    return sent


def _reads(*steps):
    """A state after hourly readings, each step being the GB sent in that hour."""
    state, counter, now = {}, 1000 * GB, T0
    state = egress.advance(state, counter, now)
    for gb in steps:
        counter += gb * GB
        now += timedelta(hours=1)
        state = egress.advance(state, counter, now)
    return state, now


def test_it_reads_every_device_but_the_loopback():
    feed = 'node_network_transmit_bytes_total{device="ens5",x="y"} 4.0e+11\nnode_network_transmit_bytes_total{device="lo"} 9e+11\nother 1\n'
    assert egress.parse_counter(feed) == 4e11


def test_a_feed_without_the_counter_is_a_failure_not_a_zero():
    with pytest.raises(ValueError):
        egress.parse_counter('node_network_receive_bytes_total{device="ens5"} 3\n')


@pytest.mark.parametrize("day,start", [(date(2026, 11, 3), date(2026, 10, 4)), (date(2026, 11, 4), date(2026, 11, 4)),
                                       (date(2026, 11, 30), date(2026, 11, 4)), (date(2027, 1, 2), date(2026, 12, 4))])
def test_the_cycle_starts_on_the_fourth(day, start):
    assert egress.cycle_start(datetime(day.year, day.month, day.day, 8, tzinfo=timezone.utc)) == start


def test_the_cycle_length_follows_the_month():
    assert egress.cycle_days(date(2026, 10, 4)) == 31 and egress.cycle_days(date(2026, 11, 4)) == 30 and egress.cycle_days(date(2027, 2, 4)) == 28


def test_a_first_reading_counts_nothing_it_did_not_see():
    state = egress.advance({}, 500 * GB, T0)
    assert state["cycle_bytes"] == 0 and state["cycle_from"] == T0.isoformat()


def test_a_restarted_counter_is_a_fresh_count_not_a_negative_one():
    state = egress.advance({}, 500 * GB, T0)
    state = egress.advance(state, 2 * GB, T0 + timedelta(hours=1))
    assert state["cycle_bytes"] == 2 * GB


def test_a_new_cycle_starts_from_zero():
    day_before = datetime(2026, 11, 3, 23, tzinfo=timezone.utc)
    state = egress.advance({}, 100 * GB, day_before)
    state = egress.advance(state, 101 * GB, day_before + timedelta(minutes=30))
    assert state["cycle_bytes"] == 1 * GB
    state = egress.advance(state, 103 * GB, day_before + timedelta(hours=2))
    assert state["cycle"] == "2026-11-04" and state["cycle_bytes"] == 2 * GB and state["cycle_from"] == "2026-11-04"


def test_a_normal_day_raises_nothing():
    state, now = _reads(*[0.06] * 24)
    assert egress.alerts(state, now) == []


def test_a_spike_like_the_fifteenth_of_october_is_urgent():
    state, now = _reads(0.05, 150)
    assert "urgent-spike" in [reason for reason, _ in egress.alerts(state, now)]


def test_hours_of_sleep_are_not_called_a_spike():
    state = egress.advance({}, 100 * GB, T0)
    now = T0 + timedelta(hours=9)
    state = egress.advance(state, 103 * GB, now)
    assert "urgent-spike" not in [reason for reason, _ in egress.alerts(state, now)]


def test_a_heavy_day_warns():
    state, now = _reads(*[0.5] * 24)
    assert "warn-day" in [reason for reason, _ in egress.alerts(state, now)]


@pytest.mark.parametrize("gb,reason", [(130, "warn-cycle"), (210, "high-cycle")])
def test_the_cycle_total_warns_then_turns_urgent(gb, reason):
    state, now = _reads()
    state["cycle_bytes"] = gb * GB
    assert reason in [r for r, _ in egress.alerts(state, now)]


def test_the_pace_warns_before_the_quota_is_gone():
    state, now = _reads()
    state["cycle_bytes"] = 60 * GB      # Six days into the cycle: about 300 GB by its end.
    assert "warn-projected" in [r for r, _ in egress.alerts(state, now)]


def test_the_pace_says_nothing_in_the_first_days():
    state = egress.advance({}, 1 * GB, datetime(2026, 11, 4, 2, tzinfo=timezone.utc))
    state["cycle_bytes"] = 20 * GB
    assert "warn-projected" not in [r for r, _ in egress.alerts(state, datetime(2026, 11, 4, 3, tzinfo=timezone.utc))]


def test_an_alert_goes_once_a_day_for_each_reason(sends, tmp_path):
    path = tmp_path / "state.json"
    counter = [1000 * GB]

    def reader(env):
        counter[0] += 100 * GB
        return counter[0]
    assert egress.run({}, path, T0, reader=reader) == 0
    assert egress.run({}, path, T0 + timedelta(hours=1), reader=reader) == 1
    first = len(sends["mail"])
    assert first >= 1
    egress.run({}, path, T0 + timedelta(hours=2), reader=reader)
    subjects = [s for s, _ in sends["mail"]]
    assert len([s for s in subjects if "URGENT: 100.0 GB" in s]) == 1


def test_the_next_day_it_warns_again(sends, tmp_path):
    state, now = _reads(150)
    assert egress.raise_alert({}, state, "urgent-spike", "x", now)
    assert egress.raise_alert({}, state, "urgent-spike", "x", now + timedelta(hours=1))
    assert len(sends["mail"]) == 1
    egress.raise_alert({}, state, "urgent-spike", "x", now + timedelta(days=1))
    assert len(sends["mail"]) == 2


@pytest.mark.parametrize("error", [urllib.error.HTTPError("u", 401, "refused", {}, None), urllib.error.URLError("down"), TimeoutError(), ValueError("no counter")])
def test_a_failed_reading_alerts_and_does_not_pass_for_quiet(sends, tmp_path, error):
    path = tmp_path / "state.json"

    def reader(env):
        raise error
    assert egress.run({}, path, T0, reader=reader) == 2
    assert len(sends["mail"]) == 1 and "not watching" in sends["mail"][0][0] + sends["mail"][0][1]
    assert "LAST READ FAILED" in egress.status_line(json.loads(path.read_text()), T0)


def test_a_failed_mail_is_kept_and_retried_on_the_next_run(monkeypatch, sends, tmp_path):
    def broken(env, subject, body):
        raise OSError("smtp down")
    monkeypatch.setattr(egress, "send_mail", broken)
    state, now = _reads(150)
    assert egress.raise_alert({}, state, "urgent-spike", "x", now) is False
    assert "last_mail_error" in state and any("NOT mailed" in title for title, _ in sends["mac"])
    monkeypatch.setattr(egress, "send_mail", lambda env, subject, body: sends["mail"].append(subject))
    assert egress.raise_alert({}, state, "urgent-spike", "x", now + timedelta(hours=1)) is True
    assert len(sends["mail"]) == 1 and "last_mail_error" not in state


def test_a_run_whose_mail_failed_exits_three(monkeypatch, sends, tmp_path):
    def broken(env, subject, body):
        raise OSError("smtp down")
    monkeypatch.setattr(egress, "send_mail", broken)
    path = tmp_path / "state.json"
    counter = [1000 * GB]

    def reader(env):
        counter[0] += 100 * GB
        return counter[0]
    egress.run({}, path, T0, reader=reader)
    assert egress.run({}, path, T0 + timedelta(hours=1), reader=reader) == 3


def test_an_alert_that_has_stopped_running_says_so():
    state = egress.advance({}, 1 * GB, T0)
    assert "STALE" in egress.status_line(state, T0 + timedelta(hours=30))
    assert "STALE" not in egress.status_line(state, T0 + timedelta(hours=2))
    assert "never run" in egress.status_line({}, T0)


def test_a_dry_run_writes_and_sends_nothing(sends, tmp_path):
    path = tmp_path / "state.json"
    assert egress.run({}, path, T0, dry_run=True, reader=lambda env: 1 * GB) == 0
    assert not path.exists() and not sends["mail"] and not sends["mac"]


def test_the_state_holds_no_secret(sends, tmp_path):
    path = tmp_path / "state.json"
    env = {"SUPABASE_SERVICE_KEY": "sekret-value", "SMTP_PASSWORD": "other-sekret"}
    egress.run(env, path, T0, reader=lambda e: 1 * GB)
    assert "sekret" not in path.read_text()


def test_the_readings_do_not_grow_for_ever():
    state, now = _reads(*[0.05] * 80)
    assert len(state["readings"]) <= egress.KEEP_READINGS_HOURS + 1


# --- 25 Nov 2026: disk, the upper-bound label, the spend cap off -------------------------------------------------

_FEED = (
    'node_network_transmit_bytes_total{device="ens5"} 9.08e10\n'
    'node_filesystem_size_bytes{device="/dev/nvme0n1p2",fstype="ext4",mountpoint="/"} 1.036e10\n'
    'node_filesystem_avail_bytes{device="/dev/nvme0n1p2",fstype="ext4",mountpoint="/"} 2.86e9\n'
    'node_filesystem_size_bytes{device="/dev/nvme1n1",fstype="ext4",mountpoint="/data"} 2.842e10\n'
    'node_filesystem_avail_bytes{device="/dev/nvme1n1",fstype="ext4",mountpoint="/data"} 7.08e9\n'
)


def test_the_disk_is_the_data_filesystem_not_the_root_one():
    assert egress.parse_disk(_FEED) == (2.842e10, 7.08e9)


def test_a_feed_without_the_disk_is_a_failure_not_a_zero():
    with pytest.raises(ValueError):
        egress.parse_disk('node_network_transmit_bytes_total{device="ens5"} 3\n')


def test_the_provisioned_size_matches_the_dashboard():
    # 25 Nov 2026: the dashboard said 27 GB provisioned; the filesystem was 28.42e9 bytes (26.5 GiB).
    assert egress.provisioned_gb(2.842e10) == 27
    assert egress.disk_cost_a_month(27) == pytest.approx(2.375)
    assert egress.disk_cost_a_month(8) == 0


def test_one_fetch_feeds_both_the_counter_and_the_disk(sends, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(egress, "read_feed", lambda env: calls.append(1) or _FEED)
    path = tmp_path / "state.json"
    assert egress.run({}, path, T0) == 0
    assert len(calls) == 1
    line = egress.status_line(json.loads(path.read_text()), T0)
    assert "about 27 GB provisioned" in line and "$2.38 a month over" in line and "upper bound" in line


def test_a_disk_growth_is_reported_once_with_its_cost(sends, tmp_path):
    path = tmp_path / "state.json"
    size = [2.842e10]
    egress.run({}, path, T0, reader=lambda env: 1000 * GB, disk_reader=lambda env: (size[0], 7e9))
    size[0] = 3.4e10    # 32 GiB filesystem: 32 GB provisioned
    assert egress.run({}, path, T0 + timedelta(hours=1), reader=lambda env: 1000 * GB, disk_reader=lambda env: (size[0], 1.2e10)) == 1
    egress.run({}, path, T0 + timedelta(hours=2), reader=lambda env: 1000 * GB, disk_reader=lambda env: (size[0], 1.2e10))
    grew = [b for s, b in sends["mail"] if "grew from 27 to 32 GB" in s]
    assert len(grew) == 1 and "$3.00 a month" in grew[0]


def test_a_nearly_full_disk_is_urgent():
    state, now = _reads()
    state = egress.note_disk(state, 30e9, 2e9, now)
    assert "urgent-disk" in [r for r, _ in egress.alerts(state, now)]
    state = egress.note_disk(state, 30e9, 10e9, now)
    assert "urgent-disk" not in [r for r, _ in egress.alerts(state, now)]


def test_a_disk_that_cannot_be_read_does_not_fail_the_egress_reading(sends, tmp_path):
    path = tmp_path / "state.json"

    def broken(env):
        raise ValueError("no disk")
    assert egress.run({}, path, T0, reader=lambda env: 1000 * GB, disk_reader=broken) == 0
    assert "Disk: not read" in egress.status_line(json.loads(path.read_text()), T0)


def test_a_cycle_total_mail_goes_once_a_cycle_not_every_day(sends, tmp_path):
    state, now = _reads()
    state["cycle_bytes"] = 130 * GB
    for day in range(3):
        for reason, sentence in egress.alerts(state, now + timedelta(days=day)):
            egress.raise_alert({}, state, reason, sentence, now + timedelta(days=day))
    assert len([s for s, _ in sends["mail"] if "upper bound 130 GB" in s]) == 1


def test_the_mail_says_the_spend_cap_is_off_and_the_figure_is_an_upper_bound(sends):
    state, now = _reads(150)
    egress.raise_alert({}, state, "urgent-spike", "x", now)
    body = sends["mail"][0][1]
    assert "spend cap is off" in body and "UPPER BOUND" in body and "402" not in body
