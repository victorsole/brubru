"""Council press releases are read from the Council's RSS feed (14 Oct 2026).

/council-documents held 57 releases, 14 August to 28 September 2026, and none after: the
reader used the listing page, which answers Railway with a browser check. The RSS feed on
the same host answers 200 from the Railway container (measured that day)."""
from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from scripts import sync_council_press_releases as job

FEED = b"""<?xml version="1.0" encoding="utf-8"?><rss xmlns:a10="http://www.w3.org/2005/Atom" version="2.0">
<channel><title>Council of the EU</title>
<item><guid isPermaLink="false">151183</guid>
<link>https://www.consilium.europa.eu/en/press/press-releases/2026/10/14/media-advisory-tripartite-social-summit-of-14-october-2026/</link>
<title>Media advisory - Tripartite Social Summit of 14 October 2026</title>
<description>Main agenda items, approximate timing, public sessions and press opportunities.</description>
<a10:updated>2026-10-14T09:30:00Z</a10:updated><category>Social policy</category></item>
<item><guid isPermaLink="false">151103</guid>
<link>https://www.consilium.europa.eu/en/press/press-releases/2026/10/13/enlargement-eu-and-moldova-start-negotiations/</link>
<title>Enlargement: EU and Moldova start negotiations &amp; more</title>
<description>&lt;p&gt;The EU and Moldova opened negotiations.&lt;/p&gt;</description>
<a10:updated>2026-10-13T21:22:00Z</a10:updated></item>
<item><guid isPermaLink="false">150999</guid><link></link><title>No link</title></item>
</channel></rss>"""


def test_each_release_is_named_by_its_dated_path_as_the_listing_reader_named_it():
    out = job.parse_feed(FEED)
    assert len(out) == 2
    doc, desc = out[0]
    assert doc.external_id == "PR-20261014-media-advisory-tripartite-social-summit-of-14-october-2026"
    assert doc.published == date(2026, 10, 14) and doc.category == "press_release"
    assert doc.subject_matters == ["Social policy"]
    assert desc == "Main agenda items, approximate timing, public sessions and press opportunities."
    doc2, desc2 = out[1]
    assert doc2.title == "Enlargement: EU and Moldova start negotiations & more"
    assert desc2 == "The EU and Moldova opened negotiations."     # markup removed
    assert doc2.subject_matters == []


def test_an_unreadable_or_empty_feed_fails_the_run(monkeypatch, capsys):
    def broken(*a, **k):
        raise TimeoutError("read timed out")
    monkeypatch.setattr(job.httpx, "get", broken)
    assert job.main([]) == 1
    empty = SimpleNamespace(content=b"<rss><channel></channel></rss>", raise_for_status=lambda: None)
    monkeypatch.setattr(job.httpx, "get", lambda *a, **k: empty)
    assert job.main([]) == 1
    assert "listed no release" in capsys.readouterr().out


class _Conn:
    def __init__(self, stored, writes):
        self.stored, self.writes = stored, writes

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params):
        return SimpleNamespace(fetchall=lambda: list(self.stored.items()))


class _Engine:
    def __init__(self, stored, writes):
        self.c = _Conn(stored, writes)

    def connect(self):
        return self.c

    def begin(self):
        return self.c


def test_a_longer_stored_text_is_never_replaced_by_the_feed_paragraph(monkeypatch):
    writes = []
    ok = SimpleNamespace(content=FEED, raise_for_status=lambda: None)
    monkeypatch.setattr(job.httpx, "get", lambda *a, **k: ok)
    held = "PR-20261013-enlargement-eu-and-moldova-start-negotiations"
    monkeypatch.setattr(job, "_engine", lambda: _Engine({held: 4200}, writes))
    monkeypatch.setattr(job, "_persist", lambda conn, doc, source, body: writes.append((doc.external_id, body)) or True)
    assert job.main(["--apply"]) == 0
    assert dict(writes)[held] is None                                  # COALESCE keeps the 4,200 characters
    assert dict(writes)["PR-20261014-media-advisory-tripartite-social-summit-of-14-october-2026"].startswith("Main agenda")
