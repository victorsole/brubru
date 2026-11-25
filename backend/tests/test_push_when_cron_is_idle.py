"""The push gate (25 Nov 2026): wait while the running tier progresses, stop when it looks hung, never push blind."""
import json
import pathlib
import shutil
import subprocess

import pytest

_GATE = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "push_when_cron_is_idle.sh"
NOW = "2026-11-25T16:01:39+00:00"
WARM = "/api/cron/sync/tier/warm"

pytestmark = pytest.mark.skipif(shutil.which("zsh") is None, reason="the gate is a zsh script")


def _state(tmp_path, payload):
    path = tmp_path / "payload.json"
    path.write_text(payload if isinstance(payload, str) else json.dumps(payload))
    done = subprocess.run(["zsh", str(_GATE), "--state"], capture_output=True, text=True, timeout=30,
                          env={"PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "PUSH_GATE_PAYLOAD_FILE": str(path)})
    assert done.returncode == 0, done.stderr
    return done.stdout.strip()


def test_an_idle_fleet_reads_idle(tmp_path):
    assert _state(tmp_path, {"now": NOW, "in_flight": [], "background": [], "runs": []}) == "IDLE"


def test_a_tier_finishing_sources_is_progressing(tmp_path):
    # 25 Nov 16:01 UTC, read live: warm in flight 6,720 s, its last source finished at 15:57:53.
    payload = {"now": NOW, "in_flight": [WARM], "in_flight_seconds": {WARM: 6720}, "background": [],
               "runs": [{"finished_at": "2026-11-25T15:57:53+00:00"}, {"finished_at": "2026-11-25T15:32:25+00:00"}]}
    assert _state(tmp_path, payload) == f"BUSY:{WARM}|3"


def test_a_tier_with_nothing_finished_for_long_shows_how_long(tmp_path):
    payload = {"now": NOW, "in_flight": [WARM], "in_flight_seconds": {WARM: 6720}, "background": [],
               "runs": [{"finished_at": "2026-11-25T15:10:00+00:00"}]}
    assert _state(tmp_path, payload) == f"BUSY:{WARM}|51"


def test_a_tier_that_just_started_is_not_called_hung(tmp_path):
    payload = {"now": NOW, "in_flight": [WARM], "in_flight_seconds": {WARM: 600}, "background": [], "runs": []}
    assert _state(tmp_path, payload) == f"BUSY:{WARM}|10"


def test_no_sign_of_progress_at_all_reads_none(tmp_path):
    assert _state(tmp_path, {"now": NOW, "in_flight": [WARM], "background": [], "runs": []}) == f"BUSY:{WARM}|NONE"


def test_a_background_batch_alone_cannot_be_judged(tmp_path):
    assert _state(tmp_path, {"now": NOW, "in_flight": [], "background": ["economy"], "runs": []}) == "BUSY:economy|BG"


@pytest.mark.parametrize("payload", ["not json", "", json.dumps({"runs": []})])
def test_an_answer_it_cannot_read_is_never_idle(tmp_path, payload):
    assert _state(tmp_path, payload) == "UNREADABLE"
