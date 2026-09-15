"""
TED ingest completeness (FD1, 15 Sep 2026).

The daily cron stored EXACTLY 400 notices a day for 8-11 Sep 2026 while TED
published 1,124-1,305 matching notices on those days: `--max-results 400` plus a
50-per-page loop capped at 10 pages. These tests pin the replacement:
  * TEDClient.fetch_all_notices scans a query to exhaustion with ITERATION
    pagination and reports `complete` against TED's own totalNoticeCount;
  * TenderFetcher queries ONE publication day at a time, uncapped, and flags a
    day it could not fetch in full;
  * a 429 on the XML endpoint is retried, not stored as "no XML".
No network and no database.
"""
import sys
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import httpx
import pytest

from services.tenders.ted_client import TEDClient, ProcedureType

_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from scripts import fetch_tenders as ft  # noqa: E402


def _resp(payload):
    r = Mock(spec=httpx.Response)
    r.status_code = 200
    r.json.return_value = payload
    return r


def _notices(start, n):
    return [{"ND": f"{i}-2026", "PD": "2026-09-14+02:00"} for i in range(start, start + n)]


# ---------------------------------------------------------------------------
# TEDClient.fetch_all_notices
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_all_notices_follows_iteration_token_to_the_end():
    client = TEDClient()
    pages = [
        _resp({"notices": _notices(0, 250), "totalNoticeCount": 600, "iterationNextToken": "t1"}),
        _resp({"notices": _notices(250, 250), "totalNoticeCount": 600, "iterationNextToken": "t2"}),
        _resp({"notices": _notices(500, 100), "totalNoticeCount": 600, "iterationNextToken": None}),
    ]
    with patch.object(client, "post", new_callable=AsyncMock, side_effect=pages) as post:
        out = await client.fetch_all_notices("PD=20260914", pause_seconds=0)
    assert out["total"] == 600 and out["distinct"] == 600 and len(out["notices"]) == 600
    assert out["complete"] is True
    bodies = [c.kwargs["json"] for c in post.call_args_list]
    assert all(b["paginationMode"] == "ITERATION" and b["limit"] == 250 for b in bodies)
    assert "iterationNextToken" not in bodies[0]
    assert bodies[1]["iterationNextToken"] == "t1" and bodies[2]["iterationNextToken"] == "t2"


@pytest.mark.asyncio
async def test_fetch_all_notices_short_of_total_is_incomplete():
    client = TEDClient()
    pages = [_resp({"notices": _notices(0, 400), "totalNoticeCount": 1185, "iterationNextToken": None})]
    with patch.object(client, "post", new_callable=AsyncMock, side_effect=pages):
        out = await client.fetch_all_notices("PD=20260911", pause_seconds=0)
    assert out["complete"] is False


@pytest.mark.asyncio
async def test_fetch_all_notices_timed_out_is_incomplete():
    client = TEDClient()
    pages = [_resp({"notices": _notices(0, 5), "totalNoticeCount": 5,
                    "iterationNextToken": None, "timedOut": True})]
    with patch.object(client, "post", new_callable=AsyncMock, side_effect=pages):
        out = await client.fetch_all_notices("PD=20260911", pause_seconds=0)
    assert out["timed_out"] is True and out["complete"] is False


@pytest.mark.asyncio
async def test_fetch_all_notices_batch_cap_is_incomplete_not_success():
    client = TEDClient()
    pages = [_resp({"notices": _notices(i * 10, 10), "totalNoticeCount": 1000,
                    "iterationNextToken": f"t{i}"}) for i in range(3)]
    with patch.object(client, "post", new_callable=AsyncMock, side_effect=pages):
        out = await client.fetch_all_notices("*", pause_seconds=0, max_batches=3)
    assert out["distinct"] == 30 and out["complete"] is False


@pytest.mark.asyncio
async def test_fetch_all_notices_dedupes_repeated_notices():
    client = TEDClient()
    dup = _notices(0, 3)
    pages = [
        _resp({"notices": dup, "totalNoticeCount": 3, "iterationNextToken": "t"}),
        _resp({"notices": dup[:1], "totalNoticeCount": 3, "iterationNextToken": None}),
    ]
    with patch.object(client, "post", new_callable=AsyncMock, side_effect=pages):
        out = await client.fetch_all_notices("*", pause_seconds=0)
    assert len(out["notices"]) == 3 and out["complete"] is True


def test_page_size_is_capped_at_ted_maximum():
    # TED v3 answers HTTP 400 to limit=251 (measured 15 Sep 2026).
    assert TEDClient.MAX_PAGE_SIZE == 250


def test_build_query_single_day_window():
    q = TEDClient._build_query(procedure_types=[ProcedureType.OPEN],
                               publication_date_from=date(2026, 9, 14),
                               publication_date_to=date(2026, 9, 14),
                               deadline_from=date(2026, 9, 29))
    assert q == '(PR="open") AND PD>=20260914 AND PD<=20260914 AND DT>=20260929'


# ---------------------------------------------------------------------------
# TenderFetcher: per-day, uncapped, fails loudly
# ---------------------------------------------------------------------------

def _fetcher(**kw):
    with patch.object(ft, "SessionLocal", return_value=MagicMock()):
        f = ft.TenderFetcher(dry_run=True, **kw)
    return f


class _FakeClient:
    _build_query = staticmethod(TEDClient._build_query)

    def __init__(self, per_day):
        self.per_day = per_day  # {"20260911": (notices, total)}
        self.queries = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def fetch_all_notices(self, query_string, **kw):
        self.queries.append(query_string)
        day = query_string.split("PD>=")[1][:8]
        notices, total = self.per_day.get(day, ([], 0))
        return {"notices": notices, "total": total, "distinct": len(notices),
                "complete": len(notices) >= total, "timed_out": False}


@pytest.mark.asyncio
async def test_fetcher_queries_each_day_separately_and_takes_everything():
    fake = _FakeClient({"20260910": (_notices(0, 1305), 1305),
                        "20260911": (_notices(2000, 1297), 1297)})
    f = _fetcher()
    f._process_day = AsyncMock()
    with patch.object(ft, "TEDClient", return_value=fake):
        stats = await f.fetch_tenders(dates=[date(2026, 9, 10), date(2026, 9, 11)])
    assert len(fake.queries) == 2
    assert all("PD>=%s AND PD<=%s" % (d, d) in q for d, q in zip(["20260910", "20260911"], fake.queries))
    assert stats["fetched"] == 2602          # not 400
    assert stats["incomplete_days"] == []
    assert stats["days"]["2026-09-10"] == {"ted_total": 1305, "fetched": 1305, "complete": True}
    assert f._process_day.await_count == 2


@pytest.mark.asyncio
async def test_fetcher_reports_incomplete_day():
    fake = _FakeClient({"20260911": (_notices(0, 400), 1185)})
    f = _fetcher()
    f._process_day = AsyncMock()
    with patch.object(ft, "TEDClient", return_value=fake):
        stats = await f.fetch_tenders(dates=[date(2026, 9, 11)])
    assert stats["incomplete_days"] == ["2026-09-11"]


@pytest.mark.asyncio
async def test_explicit_cap_truncates_and_is_reported_incomplete():
    fake = _FakeClient({"20260911": (_notices(0, 1185), 1185)})
    f = _fetcher()
    f._process_day = AsyncMock()
    with patch.object(ft, "TEDClient", return_value=fake):
        stats = await f.fetch_tenders(dates=[date(2026, 9, 11)], max_results=400)
    assert stats["fetched"] == 400 and stats["incomplete_days"] == ["2026-09-11"]


@pytest.mark.asyncio
async def test_search_failure_marks_run_failed():
    class Boom(_FakeClient):
        async def fetch_all_notices(self, *a, **k):
            raise httpx.ConnectError("down")
    f = _fetcher()
    with patch.object(ft, "TEDClient", return_value=Boom({})):
        stats = await f.fetch_tenders(dates=[date(2026, 9, 11)])
    assert stats["failed"] is True


def test_default_cli_cap_is_none():
    # The default must be "no cap", or the cron regresses to a fixed ceiling.
    src = (_BACKEND / "scripts" / "fetch_tenders.py").read_text()
    assert 'default=0,\n        help="Cap on notices' in src
    cron = (_BACKEND / "api" / "cron.py").read_text()
    assert '"--max-results", "400"' not in cron


@pytest.mark.asyncio
async def test_xml_429_is_retried_not_stored_as_missing():
    f = _fetcher(xml_rate=0)
    req = httpx.Request("GET", "https://ted.europa.eu/en/notice/1-2026/xml")
    rate_limited = httpx.HTTPStatusError(
        "429", request=req, response=httpx.Response(429, headers={"Retry-After": "0"}, request=req))
    client = Mock()
    client.get_notice_xml = AsyncMock(side_effect=[rate_limited, "<xml/>"])
    out = await f._fetch_xml_batch(["1-2026"], client)
    assert out == {"1-2026": "<xml/>"}
    assert f.stats.get("xml_rate_limited") == 1 and not f.stats.get("xml_failed")
    assert client.get_notice_xml.await_args.kwargs["raise_on_rate_limit"] is True


def test_date_range_is_inclusive():
    assert ft._date_range("2026-09-08", "2026-09-10") == [date(2026, 9, 8), date(2026, 9, 9), date(2026, 9, 10)]
    assert ft._date_range(None, None) is None


@pytest.mark.asyncio
async def test_process_day_releases_connection_before_xml_downloads():
    # 15 Sep 2026: the Session sat idle through ~10 min of XML downloads and the
    # day's commit died with "SSL connection has been closed unexpectedly".
    f = _fetcher()
    order = []
    f.db = MagicMock()
    f.db.query.return_value.filter.return_value.all.return_value = []
    f.db.rollback.side_effect = lambda: order.append("rollback")

    async def xml_batch(pubs, client):
        order.append("xml")
        return {p: None for p in pubs}

    f._fetch_xml_batch = xml_batch
    f._process_notice = AsyncMock()
    await f._process_day(_notices(0, 2), client=Mock())
    assert order == ["rollback", "xml"]
    assert f._process_notice.await_count == 2
