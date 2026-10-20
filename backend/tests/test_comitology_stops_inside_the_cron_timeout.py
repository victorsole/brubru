"""The comitology job stops itself inside the cron's 900 s timeout (20 Oct 2026).

The cron runs `backfill_eu_comitology.py --apply --limit 100 --max-seconds 720` with a 900 s
timeout. The 720 s budget started AFTER the committee pass, which had grown to 631
committees (~4 minutes at the measured 0.13-0.19 s a fetch, 0.15 s throttle, one upsert
each): on 20 Oct the run was killed at page 884 (`timeout_900s`) instead of stopping and
saying where it stopped. This runs main() on a simulated clock at the measured rates.
"""
import importlib
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))

CRON_TIMEOUT = 900
COMMITTEES = 631


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def monotonic(self):
        return self.now

    def sleep(self, s):
        self.now += s


class _Db:
    """ChunkedDb as the job uses it: one round trip per statement."""
    def __init__(self, clock, cursor_page):
        self.clock, self.cursor_page, self.cursor_writes = clock, cursor_page, []
        self._row = None

    def execute(self, sql, params=None):
        self.clock.now += 0.06
        if "SELECT cursor_value" in sql:
            self._row = (str(self.cursor_page),)
        elif "INSERT INTO job_cursors" in sql:
            self.cursor_writes.append(int(params["v"]))

    def fetchone(self):
        return self._row

    def commit(self):
        self.clock.now += 0.05

    def rollback(self):
        pass

    def close(self):
        pass


def _run(monkeypatch, capsys, committees=COMMITTEES, page_fetch_s=8.0):
    mod = importlib.import_module("backfill_eu_comitology")
    clock = _Clock()
    db = _Db(clock, cursor_page=884)
    monkeypatch.setattr(mod.time, "monotonic", clock.monotonic)
    monkeypatch.setattr(mod.time, "sleep", clock.sleep)
    monkeypatch.setattr(mod, "ChunkedDb", lambda: db)

    def get_json(url):
        clock.now += 0.17
        if url.endswith("/committees/codes"):
            return [f"C{n:05d}" for n in range(committees)]
        return {"committeeTitles": [{"title": "A committee"}], "dg": {"code": "GROW"}}

    def post_json(url, body):
        clock.now += page_fetch_s
        page = int(url.split("page=")[1].split("&")[0])
        rows = [{"documentReference": f"D{page}-{n}", "title": "Agenda"} for n in range(100)]
        return {"totalElements": 115_661, "content": rows, "last": False}

    monkeypatch.setattr(mod, "get_json", get_json)
    monkeypatch.setattr(mod, "post_json", post_json)
    monkeypatch.setattr(sys, "argv", ["backfill_eu_comitology.py", "--apply", "--limit", "100",
                                      "--max-seconds", "720"])
    start = clock.now
    mod.main()
    return clock.now - start, db, capsys.readouterr().out


def test_the_whole_run_ends_before_the_cron_kills_it(monkeypatch, capsys):
    elapsed, db, out = _run(monkeypatch, capsys)
    assert elapsed < CRON_TIMEOUT - 60, f"ran {elapsed:.0f}s against a {CRON_TIMEOUT}s timeout"
    assert "[SYNC_STATUS] degraded: stopped at page" in out
    assert db.cursor_writes and db.cursor_writes[-1] > 884   # it moved on and said where


def test_slow_pages_still_end_before_the_timeout(monkeypatch, capsys):
    # A deep page took 7.8 s on 20 Oct; one at the 120 s read timeout must not overrun either.
    elapsed, _, out = _run(monkeypatch, capsys, page_fetch_s=60.0)
    assert elapsed < CRON_TIMEOUT - 30
    assert "[SYNC_STATUS] degraded" in out


def test_a_committee_pass_that_uses_the_budget_skips_the_documents_and_says_so(monkeypatch, capsys):
    elapsed, db, out = _run(monkeypatch, capsys, committees=5_000)
    assert elapsed < CRON_TIMEOUT - 60
    assert "committee pass used the time budget" in out
    assert db.cursor_writes == []   # the cursor stays where the documents stopped last time
