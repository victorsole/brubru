"""EUDA's firewall (Victor, 29 Oct 2026): detect the block and record it as a known break, degraded and never
red. Until 2 Nov 2026 the tender reader parsed the refusal page to nothing and the publication reader walked 35
refused sitemap pages to nothing, and the run said success. The imitation in news, events and topics is
Victor's exception of 2 Nov 2026 ("for now", EUDA only): this file also pins that it spreads no further."""
import importlib
import inspect
import pathlib

import pytest

from services.scrapers import agency_procurement, euda_content, euda_publications
from services.scrapers.economy_common import SourceBlocked, raise_if_blocked

BACKEND = pathlib.Path(__file__).resolve().parents[1]


class _Answer:
    def __init__(self, status, text=""):
        self.status_code, self.text = status, text


@pytest.mark.parametrize("status,text", [(403, ""), (429, ""), (200, "<h1>Sorry, you have been blocked</h1>")])
def test_a_refusal_is_named(status, text):
    with pytest.raises(SourceBlocked, match=f"page: HTTP {status}"):
        raise_if_blocked("page", status, text)


@pytest.mark.parametrize("status", [200, 404, 500, 502, 503])
def test_anything_else_is_not_a_block(status):
    raise_if_blocked("page", status, "<html>an ordinary page</html>")


def test_the_tender_reader_says_blocked_instead_of_parsing_nothing(monkeypatch):
    monkeypatch.setattr(agency_procurement.requests, "get", lambda *a, **k: _Answer(403, "Sorry, you have been blocked"))
    with pytest.raises(SourceBlocked, match="procurement page: HTTP 403"):
        agency_procurement.ingest_euda_tenders(fetch_bodies=False)


def test_the_sitemap_stops_at_a_block_on_the_way_in_and_not_after_it_has_urls():
    class Session:
        def __init__(self, answers):
            self.answers, self.calls = answers, 0

        def get(self, url, timeout=None):
            self.calls += 1
            return self.answers[min(self.calls - 1, len(self.answers) - 1)]

    refused = Session([_Answer(403)])
    with pytest.raises(SourceBlocked, match="sitemap page 1: HTTP 403"):
        euda_publications.sitemap_urls(refused, "/publications/")
    assert refused.calls == 1                       # not 35 pages at 40 s each (O99)

    page = "<loc>https://www.euda.europa.eu/publications/a_en</loc>"
    midway = Session([_Answer(200, page), _Answer(403)])
    assert euda_publications.sitemap_urls(midway, "/publications/") == ["https://www.euda.europa.eu/publications/a_en"]


def test_the_topics_reader_stops_at_the_first_refusal(monkeypatch):
    class Session:
        calls = 0

        def get(self, url, timeout=None):
            Session.calls += 1
            return _Answer(403)
    monkeypatch.setattr(euda_content, "_cffi_session", lambda: Session())
    with pytest.raises(SourceBlocked, match="topic page"):
        euda_content.ingest_euda_topics(fetch_bodies=False)
    assert Session.calls == 1


def _economy(monkeypatch, capsys, run_one):
    import sys
    sys.path.insert(0, str(BACKEND / "scripts"))
    se = importlib.import_module("sync_economy")
    monkeypatch.setattr(se, "_BLOCKED", [])

    class Db:
        def __init__(self, **kw):
            pass

        def rollback(self):
            pass

        def close(self):
            pass
    monkeypatch.setattr(se, "ChunkedDb", Db)
    monkeypatch.setattr(se, "_run_one", run_one)
    monkeypatch.setattr(se.sys, "argv", ["sync_economy.py", "--body", "euda", "--type", "all"])
    try:
        se.main()
    except SystemExit as stop:
        assert not stop.code
    return capsys.readouterr().out


def test_the_run_is_degraded_and_the_other_resources_still_run(monkeypatch, capsys):
    seen = []

    def run_one(db, body, itype, **kw):
        seen.append(itype)
        if itype in ("tender", "publication"):
            raise SourceBlocked("procurement page: HTTP 403")
        return 2
    out = _economy(monkeypatch, capsys, run_one)
    assert {"tender", "publication", "news", "event", "topic"} <= set(seen)
    assert "[SYNC_STATUS] degraded: blocked by the site (euda/tender: procurement page: HTTP 403" in out


def test_a_run_nothing_refused_has_no_status_line(monkeypatch, capsys):
    assert "[SYNC_STATUS]" not in _economy(monkeypatch, capsys, lambda db, body, itype, **kw: 1)


def test_the_imitation_stays_where_victor_allowed_it():
    assert "curl_cffi" not in inspect.getsource(agency_procurement.ingest_euda_tenders)
    assert "_cffi_session" not in inspect.getsource(euda_publications.ingest_euda_publications)
    assert "requests.Session()" in inspect.getsource(euda_publications.ingest_euda_publications)
    assert "Victor's decision of" in euda_content._cffi_session.__doc__
