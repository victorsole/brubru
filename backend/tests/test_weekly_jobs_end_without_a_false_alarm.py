"""Two weekly jobs that turned the cron red every Sunday (20 Oct 2026).

* council_art: the Council serves Railway a browser challenge. We never work around one, so
  the job failed every week from 27 Sep, "twice in a row" each time. A challenge is now
  recorded `degraded` and named; a listing that parses to nothing is still a failure.
* fta: `--apply --limit 20` re-read all ~1,650 trade agreements (--limit capped dry runs
  only) and the 1,800 s timeout killed its first scheduled run on 18 Oct ("no good run on
  record"). A run now reads the new agreements plus the 20 refreshed longest ago, inside a
  budget.
"""
import importlib
import pathlib
import re
import sys
from datetime import datetime, timezone

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "scripts"))


def _run_art(monkeypatch, capsys, scrape):
    art = importlib.import_module("scripts.sync_council_art")
    fresh = importlib.import_module("services.sync.freshness")
    rows = []
    monkeypatch.setattr(art, "scrape", scrape)
    monkeypatch.setattr(art, "SessionLocal", lambda: type("S", (), {"close": lambda self: None})())
    monkeypatch.setattr(fresh, "record_run", lambda db, **kw: rows.append(kw))
    monkeypatch.setattr(sys, "argv", ["sync_council_art.py", "--apply"])
    rc = art.main()
    return rc, rows, capsys.readouterr().out, art


def test_a_council_challenge_is_recorded_degraded_and_exits_cleanly(monkeypatch, capsys):
    art = importlib.import_module("scripts.sync_council_art")

    def challenged():
        raise art.FetchBlocked("consilium served a browser challenge for the ART listing")
    rc, rows, out, _ = _run_art(monkeypatch, capsys, challenged)
    assert rc == 0
    assert rows[-1]["status"] == "degraded" and "browser challenge" in rows[-1]["error"]
    assert "[SYNC_STATUS] degraded: blocked:" in out
    from services.sync.freshness import BUDGET_STOP
    assert not rows[-1]["error"].startswith(BUDGET_STOP)


def test_a_listing_that_parses_to_nothing_is_still_a_failure(monkeypatch, capsys):
    rc, rows, out, _ = _run_art(monkeypatch, capsys, lambda: [])
    assert rc == 1 and rows[-1]["status"] == "failed"


def test_the_fta_week_reads_new_agreements_then_the_oldest_refreshed():
    fta = importlib.import_module("backfill_eu_trade_agreements")
    t = lambda d: datetime(2026, 10, d, tzinfo=timezone.utc)  # noqa: E731
    universe = [{"celex": f"22026A{n:04d}", "date": f"2026-0{1 + n % 9}-01"} for n in range(30)]
    held = {u["celex"]: t(1 + n % 28) for n, u in enumerate(universe) if n >= 3}
    held["22026A0029"] = None                       # never stamped: refreshed first
    picked = fta.weekly_slice(universe, held, 5)
    new = [u["celex"] for u in universe[:3]]
    assert [p["celex"] for p in picked[:3]] == sorted(new, key=lambda c: universe[int(c[-4:])]["date"], reverse=True)
    assert len(picked) == 8
    assert picked[3]["celex"] == "22026A0029"
    stamps = [held[p["celex"]] for p in picked[4:]]
    assert stamps == sorted(stamps)                 # the longest ago first


def test_the_scheduled_fta_run_has_a_budget_inside_its_timeout():
    cron = (BACKEND / "api" / "cron.py").read_text(encoding="utf-8")
    call = re.search(r'"fta", "scripts/backfill_eu_trade_agreements\.py",\s*\[(.*?)\],\s*timeout=(\d+)', cron, re.S)
    assert call, "the scheduled fta call was not found"
    budget = re.search(r'"--max-seconds", "(\d+)"', call.group(1))
    assert budget and int(budget.group(1)) + 240 <= int(call.group(2))
