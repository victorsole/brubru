"""Unit tests for the F&T (SEDIA) ingest: language, programme, status, tenders.

No network, no database. The record shapes are trimmed copies of real SEDIA
search results read on 15 Sep 2026.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import ingest_funding_sedia as sedia  # noqa: E402

TODAY = dt.date(2026, 9, 15)


def _grant(**md):
    base = {
        "identifier": ["HORIZON-EIC-2026-STEP"],
        "title": ["EIC STEP Scale Up"],
        "type": ["1"],
        "language": ["en"],
        "status": ["31094502"],
        "frameworkProgramme": ["43108390"],
        "programmePeriod": ["2021 - 2027"],
        "startDate": ["2025-11-06T00:00:00.000+0000"],
        "deadlineDate": ["2026-11-25T00:00:00.000+0000"],
        "callIdentifier": ["HORIZON-EIC-2026-STEP"],
    }
    base.update(md)
    return {"metadata": base}


def _tender(**md):
    base = {
        "identifier": ["2165b13f-8c71-42ff-bb32-2af76fb84fb3-CN"],
        "title": ["Provision of services of interim workers (temporary agency workers)"],
        "type": ["0"],
        "language": ["en"],
        "status": ["31094502"],
        "programmePeriod": ["2014 - 2020", "2021 - 2027"],
        "frameworkProgramme": [],
        "startDate": ["2026-09-15T00:00:00.000+0000"],
        "deadlineDate": ["2026-10-26T23:30:59.000+0000"],
        "contractType": ["31095498"],
        "cftEstimatedOverallContractAmount": ["2000000"],
        "cftEstimatedOverallContractCurrency": ["EUR"],
        "cftLeadContractingAuthorityCode": [
            '[{"name":"European Union Agency for Fundamental Rights","link":"https://fra.europa.eu/","isLeadAuthority":true}]'
        ],
        "description": ["Framework contract for interim workers."],
    }
    base.update(md)
    return {"metadata": base}


# --- programme -------------------------------------------------------------

def test_programme_is_the_programme_name_not_the_period():
    row = sedia.normalise_row(_grant(), today=TODAY)
    assert row["programme"] == "Horizon Europe (HORIZON)"
    assert not sedia.is_programme_period(row["programme"])


def test_programme_falls_back_to_identifier_prefix_never_the_period():
    row = sedia.normalise_row(_grant(frameworkProgramme=[], identifier=["LIFE-2026-SAP-ENV"]),
                              today=TODAY)
    assert "LIFE" in row["programme"]
    unknown = sedia.normalise_row(_grant(frameworkProgramme=[], identifier=["ZZZ-2026-X"]),
                                  today=TODAY)
    assert unknown["programme"] is None


def test_clean_facet_label_decodes_sedia_artefacts():
    assert sedia.clean_facet_label("Research Fund for Coal %26 Steel (RFCS)") == \
        "Research Fund for Coal & Steel (RFCS)"
    assert sedia.clean_facet_label("Erasmus  (ERASMUS )") == "Erasmus+ (ERASMUS+)"
    assert sedia.clean_facet_label("European Social Fund   (ESF) ") == \
        "European Social Fund+ (ESF+)"


@pytest.mark.parametrize("value,expected", [
    ("2021 - 2027", True), ("2014 - 2020", True), ("Horizon Europe (HORIZON)", False),
    (None, False), ("", False),
])
def test_is_programme_period(value, expected):
    assert sedia.is_programme_period(value) is expected


# --- status and deadlines ----------------------------------------------------

def test_dates_override_a_lagging_forthcoming_status():
    """A topic opening today is open even if SEDIA still says forthcoming."""
    row = sedia.normalise_row(_grant(status=["31094501"],
                                     startDate=["2026-09-15T00:00:00.000+0000"]), today=TODAY)
    assert row["status"] == "open"


def test_passed_deadline_closes_an_open_call():
    row = sedia.normalise_row(_grant(deadlineDate=["2026-09-14T00:00:00.000+0000"]), today=TODAY)
    assert row["status"] == "closed"


def test_deadline_today_is_still_open():
    """SEDIA stores the day at 00:00 while the real cut-off is 17:00 Brussels."""
    row = sedia.normalise_row(_grant(deadlineDate=["2026-09-15T00:00:00.000+0000"]), today=TODAY)
    assert row["status"] == "open"


def test_future_opening_is_forthcoming():
    row = sedia.normalise_row(_grant(status=["31094502"],
                                     startDate=["2026-12-08T00:00:00.000+0000"],
                                     deadlineDate=["2027-04-06T00:00:00.000+0000"]), today=TODAY)
    assert row["status"] == "forthcoming"


def test_multi_cutoff_topic_takes_next_deadline_not_the_first():
    """ERASMUS-EDU-2022-ECHE-CERT-FP: open, deadlines 2022 ... 2027."""
    row = sedia.normalise_row(_grant(
        identifier=["ERASMUS-EDU-2022-ECHE-CERT-FP"], frameworkProgramme=["43353764"],
        startDate=["2022-02-23T00:00:00.000+0000"],
        deadlineDate=["2022-05-03T17:00:00.000+0000", "2026-01-27T17:00:00.000+0000",
                      "2027-01-26T17:00:00.000+0000"]), today=TODAY)
    assert row["deadline"].date() == dt.date(2027, 1, 26)
    assert row["status"] == "open"


def test_prior_information_notice_without_deadline_stays_forthcoming():
    row = sedia.normalise_row(_tender(identifier=["538149d7-ac8e-46f4-88ec-22b5318e2c90-PIN"],
                                      status=["31094501"], deadlineDate=[]), today=TODAY)
    assert row["is_tender"] and row["status"] == "forthcoming"


def test_no_status_and_no_dates_stays_unknown():
    row = sedia.normalise_row(_grant(status=[], deadlineDate=[], startDate=[]), today=TODAY)
    assert row["status"] == "unknown"


# --- tenders -------------------------------------------------------------------

def test_tender_contracting_authority_is_the_buyer_not_the_period():
    row = sedia.normalise_row(_tender(), today=TODAY)
    assert row["is_tender"] is True
    assert sedia.is_call_for_tenders(row)
    assert row["contracting_authority"] == "European Union Agency for Fundamental Rights"
    assert row["contract_type"] == "Services"
    assert row["indicative_budget"] == 2_000_000
    assert "/tender-details/" in row["source_url"]
    assert row["programme"] is None


def test_tender_without_authority_gets_none_never_a_period():
    row = sedia.normalise_row(_tender(cftLeadContractingAuthorityCode=[]), today=TODAY)
    assert row["contracting_authority"] is None


def test_grant_is_not_a_tender():
    row = sedia.normalise_row(_grant(), today=TODAY)
    assert row["is_tender"] is False
    assert not sedia.is_call_for_tenders(row)


def test_prefer_keeps_the_record_with_a_status_and_later_deadline():
    older = sedia.normalise_row(_grant(deadlineDate=["2026-01-27T17:00:00.000+0000"]), today=TODAY)
    newer = sedia.normalise_row(_grant(deadlineDate=["2027-01-26T17:00:00.000+0000"]), today=TODAY)
    assert sedia.prefer(older, newer) is newer
    assert sedia.prefer(newer, older) is newer


# --- language -----------------------------------------------------------------

def test_fetch_asks_sedia_for_english_by_default(monkeypatch):
    captured = {}

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"results": []}'

    def fake_urlopen(req, timeout=0):
        captured["body"] = req.data
        captured["ctype"] = req.headers.get("Content-type")
        return _Resp()

    monkeypatch.setattr(sedia.urllib_request, "urlopen", fake_urlopen)
    sedia.fetch_sedia_page(1, query={"bool": {"must": [{"terms": {"type": ["1"]}}]}})
    assert captured["ctype"].startswith("multipart/form-data")
    assert b'name="languages"' in captured["body"] and b'["en"]' in captured["body"]
    assert b'"type": ["1"]' in captured["body"]


# --- entrepreneur-instruments classifier ---------------------------------------

def _family(topic_id):
    from api.v2.funding.entrepreneur_instruments import _FAMILIES
    for pat, programme, family, _ in _FAMILIES:
        if fnmatch.fnmatch(topic_id.upper(), pat.upper().replace("%", "*")):
            return programme, family
    return None


def test_erasmus_charter_is_not_erasmus_for_young_entrepreneurs():
    assert _family("ERASMUS-EDU-2022-ECHE-CERT-FP") is None


@pytest.mark.parametrize("topic_id", ["COS-EYE-2019-4-01", "SMP-COSME-2026-EYE-01"])
def test_eye_topics_classify_as_eye(topic_id):
    assert _family(topic_id)[1] == "Erasmus for Young Entrepreneurs"
