"""Check F must flag an 'Upcoming' canon marker whose date has passed (5 Oct 2026)."""
import importlib.util
import pathlib
import sys
from datetime import date, timedelta

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT + "/backend")


def _radar():
    spec = importlib.util.spec_from_file_location("lawdrop_radar", f"{_REPO_ROOT}/backend/scripts/lawdrop_radar.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _page(tmp, slug, date_text):
    d = tmp / slug
    d.mkdir()
    (d / "index.html").write_text(
        '<div class="timeline"><div class="timeline__item timeline__item--upcoming">'
        f'<div class="timeline__date">{date_text} <span class="pill">Upcoming</span></div>'
        '<div class="timeline__text">Something happens.</div></div></div>', encoding="utf-8")


def _fmt(d):
    return f"{d.day} {d.strftime('%B %Y')}"


def test_passed_date_is_stale_future_is_not_and_garbage_is_unread(tmp_path, monkeypatch):
    r = _radar()
    monkeypatch.setattr(r, "CANON_DIR", str(tmp_path))
    _page(tmp_path, "past", _fmt(date.today() - timedelta(days=3)))
    _page(tmp_path, "future", _fmt(date.today() + timedelta(days=90)))
    _page(tmp_path, "garbage", "sometime soon")
    out = {x["page"]: x["state"] for x in r.check_stale_canon_pages()}
    assert out == {"past": "STALE", "garbage": "UNREAD"}
