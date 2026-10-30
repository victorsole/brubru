"""The EPRS "Legislation in progress" job finds a file it already holds, and fails on an empty page.

13 October 2026: the page prints three old files with a three-digit number (2013/403(COD)).
Brubru stores them as OEIL writes them (2013/0403(COD); OEIL answers the three-digit form with
a 404). The job did not find them, tried to create them again and the database refused the
duplicate id: one "Deploy Crashed" mail at every run, twice a day, from 8 October."""
import asyncio

from scripts import sync_eprs_legislation_in_progress as job
from services.eprs import legislation_in_progress_scraper as scraper_mod
from services.eprs.legislation_in_progress_scraper import LegislationInProgressScraper, canonical_procedure_ref

PAGE = """<html><body><table>
<tr><td><strong>International Trade</strong></td></tr>
<tr><td><a href="https://epthinktank.eu/2022/03/10/ipi/">International procurement instrument</a> 2012/060(COD)</td></tr>
<tr><td><a href="https://epthinktank.eu/2015/06/01/small-claims/">Reform of the European Small Claims Procedure</a> 2013/403(COD)</td></tr>
<tr><td><a href="https://epthinktank.eu/2021/05/01/ai-act/">Artificial intelligence act</a> 2021/0106(COD)</td></tr>
</table></body></html>"""


class _Response:
    def __init__(self, status, body):
        self.status, self._body = status, body

    async def text(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _Session:
    def __init__(self, status, body):
        self._response = _Response(status, body)

    def get(self, *_a, **_kw):
        return self._response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


def _scrape(monkeypatch, status, body):
    monkeypatch.setattr(scraper_mod.aiohttp, "ClientSession", lambda *a, **kw: _Session(status, body))
    return asyncio.run(LegislationInProgressScraper().get_procedures(force_refresh=True))


def test_a_reference_is_written_as_oeil_writes_it():
    assert canonical_procedure_ref("2013/403(COD)") == "2013/0403(COD)"
    assert canonical_procedure_ref("2012/060(COD)") == "2012/0060(COD)"
    assert canonical_procedure_ref("2021/0106(COD)") == "2021/0106(COD)"
    # Anything else is returned as read, never reshaped.
    assert canonical_procedure_ref("COM(2021) 206") == "COM(2021) 206"
    assert canonical_procedure_ref("") == ""


def test_the_page_s_three_digit_references_come_out_with_four(monkeypatch):
    refs = [p["procedure_ref"] for p in _scrape(monkeypatch, 200, PAGE)]
    assert refs == ["2012/0060(COD)", "2013/0403(COD)", "2021/0106(COD)"]


def test_the_same_file_printed_in_both_forms_is_read_once(monkeypatch):
    twice = PAGE.replace("</table>", '<tr><td><a href="https://epthinktank.eu/x/">Small claims again</a> '
                                     "2013/0403(COD)</td></tr></table>")
    refs = [p["procedure_ref"] for p in _scrape(monkeypatch, 200, twice)]
    assert refs.count("2013/0403(COD)") == 1


class _ReadOnlyDb:
    def close(self):
        pass


def test_a_refused_page_is_degraded_for_72_hours_after_the_last_good_run_then_fails(monkeypatch, capsys):
    """30 Oct 2026 (Victor): epthinktank.eu would not serve the page from 29 Oct, and the job made
    the cron red twice a day. A refusal is the site's state: degraded while the last good run is
    under 72 h old, failed after; it is never read as nothing to do, and nothing is written."""
    from datetime import datetime, timedelta, timezone
    import services.sync.freshness as freshness

    assert _scrape(monkeypatch, 403, "Forbidden") == []
    monkeypatch.setattr(scraper_mod.aiohttp, "ClientSession", lambda *a, **kw: _Session(403, "Forbidden"))
    opened = []
    monkeypatch.setattr(job, "SessionLocal", lambda: opened.append(1) or _ReadOnlyDb())
    for dry_run in (True, False):
        stats = asyncio.run(job.sync_legislation_in_progress(dry_run=dry_run))
        assert stats["total_scraped"] == 0 and stats["created"] == 0
        assert stats["refused"] and "HTTP 403" in stats["errors"][0]
    assert opened == []  # nothing is written from a refused page
    monkeypatch.setattr(job.sys, "argv", ["sync_eprs_legislation_in_progress.py"])
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(freshness, "last_success_at", lambda db, key: now - timedelta(hours=10))
    assert job.main() == 0
    assert "[SYNC_STATUS] degraded: source unreachable" in capsys.readouterr().out
    monkeypatch.setattr(freshness, "last_success_at", lambda db, key: now - timedelta(hours=80))
    assert job.main() == 1
    monkeypatch.setattr(freshness, "last_success_at", lambda db, key: None)
    assert job.main() == 1


def test_a_page_that_answers_but_lists_nothing_fails_at_once(monkeypatch):
    """A changed layout is a fault of ours, never a refusal."""
    monkeypatch.setattr(scraper_mod.aiohttp, "ClientSession",
                        lambda *a, **kw: _Session(200, "<html><body>New layout</body></html>"))
    stats = asyncio.run(job.sync_legislation_in_progress(dry_run=True))
    assert stats["refused"] is None and "listed no procedure" in stats["errors"][0]
    monkeypatch.setattr(job.sys, "argv", ["sync_eprs_legislation_in_progress.py"])
    assert job.main() == 1
