"""O241 (11 Nov 2026): the committees' amendment documents were guessed, not listed.

The nightly sync took the 120 newest draft reports and tried PE number +1 to +5 at doceo.
Committees number their amendment documents far from the report and table them weeks later,
so it held 15 of the 747 committee amendment documents EP Open Data lists for 2026, none dated
after 6 July, and said success every night; /parliament/amendments answered 0 new items for
three weeks. The 565 amendments of 22 Oct came out of one draft report.

Now: /documents?year=&work-type=AMENDMENT_LIST is the list (committee and joint-committee
identifiers; plenary amendments are another corpus), the nightly run reads at most
NIGHTLY_DOCUMENT_LIMIT open documents, newest first, and says how many it left; a run that
lists no amendment document fails. Proven live the same day without a database: 747 listed,
9 of 12 sampled parsed with date and procedure (the 3 newest were not at doceo yet: 404).
"""
import asyncio
import datetime as dt
from types import SimpleNamespace

import pytest

import services.api_clients.ep_open_data_client as ep_mod
from services.api_clients.ep_open_data_client import (
    EPOpenDataClient, EPOpenDataUpstreamError, WORK_TYPE_AMENDMENTS, WORK_TYPE_DRAFT_REPORTS)
from services.scrapers import bulk_amendment_sync_service as svc
from services.schedulers import amendment_sync_scheduler as sched


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    async def _sleep(seconds):
        return None
    monkeypatch.setattr(ep_mod.asyncio, "sleep", _sleep)


def _item(identifier):
    return {"identifier": identifier, "work_type": "def/ep-document-types/AMENDMENT_LIST", "label": ""}


def _listing_client(pages_by_year):
    """A client whose /documents list answers `pages_by_year[year]` (a list of pages)."""
    c, asked = EPOpenDataClient(), []

    async def _list(endpoint, offset=0, limit=100, filters=None, empty_ok=False):
        asked.append((endpoint, offset, dict(filters or {}), empty_ok))
        pages = pages_by_year.get((filters or {}).get("year"), [])
        i = offset // 100
        return pages[i] if i < len(pages) else []
    c._list_endpoint = _list
    return c, asked


def test_the_amendment_documents_come_from_the_list_committee_and_joint_only():
    full = [_item(f"ECON-AM-{780000 + i}") for i in range(98)] + [_item("A-10-2026-0001-AM-001-243"),
                                                                    _item("RC-10-2026-0114-AM-007-016")]
    c, asked = _listing_client({2026: [full, [_item("CJ13-AM-797588"), _item("ECON-AM-780000"), _item("TRAN-AM-797651")]]})
    docs = asyncio.run(c.list_amendment_documents([2026]))
    ids = [d["identifier"] for d in docs]
    assert len(ids) == 100 and len(set(ids)) == 100                      # the repeat is listed once
    assert "CJ13-AM-797588" in ids and not any(i.startswith(("A-10", "RC-10")) for i in ids)
    joint = next(d for d in docs if d["identifier"] == "CJ13-AM-797588")
    assert joint == {**joint, "committee_code": "CJ13", "document_type": "AM", "pe_reference": "PE797.588",
                     "doceo_url": "https://www.europarl.europa.eu/doceo/document/CJ13-AM-797588_EN.docx"}
    assert all(a[0] == "documents" and a[2] == {"year": 2026, "work-type": "AMENDMENT_LIST"} and a[3] for a in asked)
    assert [a[1] for a in asked] == [0, 100]


def test_every_year_asked_is_listed_and_a_year_with_nothing_is_not_a_fault():
    c, asked = _listing_client({2025: [[_item("JURI-AM-770001")]]})
    assert [d["identifier"] for d in asyncio.run(c.list_amendment_documents([2025, 2026]))] == ["JURI-AM-770001"]
    assert [a[2]["year"] for a in asked] == [2025, 2026]


def test_a_list_that_cannot_be_read_raises_and_is_never_a_short_list():
    c = EPOpenDataClient()

    async def _list(endpoint, offset=0, limit=100, filters=None, empty_ok=False):
        if offset:
            raise EPOpenDataUpstreamError("HTTP 500 on documents offset=100, still failing after 3 tries")
        return [_item(f"ECON-AM-{780000 + i}") for i in range(100)]
    c._list_endpoint = _list
    with pytest.raises(EPOpenDataUpstreamError):
        asyncio.run(c.list_amendment_documents([2026]))


class _Resp:
    def __init__(self, status_code, payload=None):
        self.status_code, self._payload, self.headers = status_code, payload, {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


def _http_client(response):
    c, seen = EPOpenDataClient(), []

    class _Fake:
        async def get(self, url, params=None):
            seen.append((url, params))
            return response

    async def _get():
        return _Fake()
    c._get_client = _get
    return c, seen


def test_the_filters_reach_the_request_and_an_empty_filtered_list_is_empty_only_when_allowed():
    c, seen = _http_client(_Resp(200, {"data": [{"identifier": "X"}]}))
    asyncio.run(c._list_endpoint("documents", offset=200, filters={"year": 2026, "work-type": "AMENDMENT_LIST"}))
    assert seen[0][1] == {"year": 2026, "work-type": "AMENDMENT_LIST", "offset": 200, "limit": 100}
    c, _ = _http_client(_Resp(204))
    assert asyncio.run(c._list_endpoint("documents", filters={"year": 2027}, empty_ok=True)) == []
    with pytest.raises(EPOpenDataUpstreamError):
        asyncio.run(c._list_endpoint("committee-documents"))            # the unfiltered list is never empty


def test_discovery_lists_and_no_longer_probes():
    c = EPOpenDataClient()
    called = []

    async def _list(years=None, progress_callback=None):
        called.append(years)
        return [c._stub_to_doc("ITRE-AM-788900")]
    c.list_amendment_documents = _list
    docs = asyncio.run(c.enumerate_all_documents(work_types=[WORK_TYPE_AMENDMENTS], years=[2026]))
    assert called == [[2026]] and [d["identifier"] for d in docs] == ["ITRE-AM-788900"]
    assert not hasattr(c, "_probe_am_documents")


def test_the_detail_of_an_amendment_document_gives_its_date_title_and_parent():
    raw = {"data": [{"identifier": "TRAN-AM-782201", "document_date": "2026-01-28",
                     "foresees_change_of": "eli/dl/doc/TRAN-PR-781387",
                     "title_dcterms": {"fr": "AMENDEMENTS", "en": "AMENDMENTS - 440 - 546 - Draft report - YYYY/NNNN(COD)"}}]}
    d = EPOpenDataClient()._parse_document_detail(raw, "TRAN-AM-782201")
    assert d["date"] == "2026-01-28" and d["parent_identifier"] == "TRAN-PR-781387"
    assert d["title"].startswith("AMENDMENTS - 440") and d["pe_reference"] == "PE782.201" and d["document_type"] == "AM"
    assert EPOpenDataClient()._parse_document_detail({"data": [{}]}, "ECON-PR-700001")["parent_identifier"] == ""


# ---- the run -------------------------------------------------------------------------

def _service(documents, settled=()):
    s = svc.BulkAmendmentSyncService.__new__(svc.BulkAmendmentSyncService)
    s._docx_cache, s._fetch_facts, read, warmed = {}, {}, [], []

    async def _enum(**k):
        return list(documents)

    async def _close():
        return None

    async def _prefetch(urls):
        warmed.extend(urls)

    async def _fetch(doc):
        read.append(doc["identifier"])
        return 3
    s.client = SimpleNamespace(enumerate_all_documents=_enum, close=_close)
    s._is_settled = lambda ep_id: ep_id in settled
    s._prefetch_walled_documents, s._fetch_and_parse_document = _prefetch, _fetch
    return s, read, warmed


def _docs(n, kind="AM", start=790000):
    c = EPOpenDataClient()
    return [c._stub_to_doc(f"ECON-{kind}-{start + i}") for i in range(n)]


def test_the_nightly_run_reads_the_newest_open_documents_up_to_its_limit_and_counts_the_rest():
    docs = _docs(10) + _docs(2, "PR", 700000)
    s, read, warmed = _service(docs, settled={"ECON-AM-790009", "ECON-PR-700000"})
    r = asyncio.run(s.sync_all(years=[2026], max_documents=4))
    assert read == ["ECON-AM-790005", "ECON-AM-790006", "ECON-AM-790007", "ECON-AM-790008"]   # newest open four
    assert len(warmed) == 4 and all(any(i in u for i in read) for u in warmed)                # only those are fetched
    assert (r.documents_discovered, r.documents_parsed, r.documents_skipped, r.documents_deferred) == (12, 4, 2, 6)
    assert r.documents_listed_by_type == {"AM": 10, "PR": 2} and r.amendments_stored == 12


def test_without_a_limit_every_open_document_is_read():
    s, read, _ = _service(_docs(5))
    r = asyncio.run(s.sync_all(years=[2026]))
    assert len(read) == 5 and r.documents_deferred == 0


def test_the_scheduled_run_is_limited_and_asks_for_amendment_documents():
    s, seen = svc.BulkAmendmentSyncService.__new__(svc.BulkAmendmentSyncService), {}

    async def _sync_all(**k):
        seen.update(k)
        return svc.BulkSyncResult()
    s.sync_all = _sync_all
    asyncio.run(s.sync_incremental())
    assert seen["max_documents"] == svc.NIGHTLY_DOCUMENT_LIMIT == 60 and seen["force_refetch"] is False
    assert seen["work_types"] == [WORK_TYPE_AMENDMENTS, WORK_TYPE_DRAFT_REPORTS] and seen["years"] == [dt.datetime.now().year]


def test_an_amendment_document_takes_its_date_from_documents_and_its_procedure_from_its_parent():
    s = svc.BulkAmendmentSyncService.__new__(svc.BulkAmendmentSyncService)
    url = "https://www.europarl.europa.eu/doceo/document/EMPL-AM-788901_EN.docx"
    s._docx_cache, s._fetch_facts, asked, parsed, recorded = {url: b"PK-docx"}, {}, [], {}, {}

    async def _detail(ep_id, endpoint="documents"):
        asked.append((ep_id, endpoint))
        return {"date": "2026-05-19", "procedure_reference": "", "parent_identifier": "EMPL-PA-786812"}
    s.client = SimpleNamespace(get_document_detail=_detail)
    s.parser = SimpleNamespace(parse_docx=lambda **k: parsed.update(k) or [])
    s._procedure_of = lambda ep_id: {"EMPL-PA-786812": "YYYY/NNNN(COD)"}.get(ep_id, "")
    s._upsert_document_record = lambda doc, **k: recorded.update(doc=dict(doc), **k)
    s.db = SimpleNamespace(commit=lambda: None)
    doc = EPOpenDataClient()._stub_to_doc("EMPL-AM-788901")
    assert asyncio.run(s._fetch_and_parse_document(doc)) == 0
    assert asked == [("EMPL-AM-788901", "documents")]
    assert parsed["procedure_ref"] == "YYYY/NNNN(COD)" and parsed["pe_reference"] == "PE788.901"
    assert recorded["doc"]["date"] == "2026-05-19" and recorded["doc"]["procedure_reference"] == "YYYY/NNNN(COD)"
    assert recorded["status"] == "parsed"


def test_a_draft_report_still_takes_its_date_from_committee_documents():
    s = svc.BulkAmendmentSyncService.__new__(svc.BulkAmendmentSyncService)
    url = "https://www.europarl.europa.eu/doceo/document/ECON-PR-700001_EN.docx"
    s._docx_cache, s._fetch_facts, asked = {url: b"PK-docx"}, {}, []

    async def _detail(ep_id, endpoint="documents"):
        asked.append(endpoint)
        return {"date": "2026-03-02"}
    s.client = SimpleNamespace(get_document_detail=_detail)
    s.parser = SimpleNamespace(parse_docx=lambda **k: [])
    s._procedure_of = lambda ep_id: ""
    s._upsert_document_record = lambda doc, **k: None
    s.db = SimpleNamespace(commit=lambda: None)
    asyncio.run(s._fetch_and_parse_document(EPOpenDataClient()._stub_to_doc("ECON-PR-700001")))
    assert asked == ["committee-documents"]


# ---- what the run says ---------------------------------------------------------------

def _scheduled(monkeypatch, result, today=dt.datetime(2026, 11, 11, 4, 0, tzinfo=dt.timezone.utc)):
    rows = []

    class _Service:
        def __init__(self, db):
            pass

        async def sync_incremental(self):
            return result

    class _Now(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return today
    monkeypatch.setattr(svc, "BulkAmendmentSyncService", _Service)
    monkeypatch.setattr(sched, "SessionLocal", lambda: SimpleNamespace(close=lambda: None))
    monkeypatch.setattr("services.sync.freshness.record_run", lambda db, **k: rows.append(k))
    monkeypatch.setattr(dt, "datetime", _Now)
    asyncio.run(sched._daily_amendment_sync())
    return rows[0]


def test_a_run_that_lists_no_amendment_document_fails(monkeypatch):
    r = svc.BulkSyncResult(documents_discovered=1180, documents_skipped=1180, documents_listed_by_type={"PR": 1180})
    row = _scheduled(monkeypatch, r)
    assert row["status"] == "failed" and "listed 0 amendment documents" in row["error"]


def test_in_the_first_weeks_of_a_year_no_amendment_document_is_not_a_failure(monkeypatch):
    r = svc.BulkSyncResult(documents_discovered=40, documents_skipped=40, documents_listed_by_type={"PR": 40})
    row = _scheduled(monkeypatch, r, today=dt.datetime(2027, 1, 20, 4, 0, tzinfo=dt.timezone.utc))
    assert row["status"] == "success" and row["error"] is None


def test_documents_left_for_the_next_run_are_written_on_the_run_row(monkeypatch):
    r = svc.BulkSyncResult(documents_discovered=2000, documents_parsed=60, amendments_stored=4100,
                           documents_deferred=672, documents_listed_by_type={"AM": 747, "PR": 1253})
    row = _scheduled(monkeypatch, r)
    assert row["status"] == "success" and row["items_added"] == 4100
    assert row["error"].startswith("672 listed document(s) not read yet") and "'AM': 747" in row["error"]


def test_a_document_that_failed_still_degrades_the_run(monkeypatch):
    r = svc.BulkSyncResult(documents_discovered=800, documents_failed=1, document_errors=["Failed ECON-AM-790001: x"],
                           documents_listed_by_type={"AM": 747, "PR": 53})
    assert _scheduled(monkeypatch, r)["status"] == "degraded"
