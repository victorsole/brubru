"""A Funding & Tenders Portal tender's status comes from its own dates (29 Oct 2026, O97).

Of 2,178 portal tenders, 689 carried no deadline and kept the portal's flag, which goes stale:
48 ex-ante notices still "forthcoming" after their registration deadline, a 2023 tender "open".
The dates the portal holds decide (an ex-ante notice's registration deadline, a prior information
notice's planned date), and a contract notice's deadline is read on its TED notice, where a call
for expressions of interest states the end of that period instead of a tender deadline.
"""
from __future__ import annotations

import importlib
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone

S = importlib.import_module("scripts.ingest_funding_sedia")
TODAY = date(2026, 10, 29)
UTC = timezone.utc

_EOI_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PriorInformationNotice xmlns="urn:oasis:names:specification:ubl:schema:xsd:PriorInformationNotice-2"
 xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
 xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
 xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
 xmlns:efac="http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1"
 xmlns:efext="http://data.europa.eu/p27/eforms-ubl-extensions/1">
 <cac:ProcurementProjectLot><cac:TenderingProcess><ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
  <efext:EformsExtension><efac:InterestExpressionReceptionPeriod>
   <cbc:EndDate>2029-12-03+01:00</cbc:EndDate><cbc:EndTime>00:00:59+01:00</cbc:EndTime>
  </efac:InterestExpressionReceptionPeriod></efext:EformsExtension>
 </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions></cac:TenderingProcess></cac:ProcurementProjectLot>
</PriorInformationNotice>"""


def _record(ref, status_code, **fields):
    md = {"identifier": [ref], "title": [f"Tender {ref}"], "type": ["0"],
          "startDate": ["2024-11-26T00:00:00.000+0000"]}
    if status_code:
        md["status"] = [status_code]
    md.update({k: [v] for k, v in fields.items()})
    return {"metadata": md}


def test_the_eforms_parser_reads_the_end_of_the_period_for_expressions_of_interest():
    from services.tenders.eforms_parser import EFormsParser
    got = EFormsParser()._extract_dates(ET.fromstring(_EOI_XML.encode()))["submission_deadline"]
    assert got == datetime(2029, 12, 3, 0, 0, 59, tzinfo=timezone(timedelta(hours=1)))   # as the notice states it


def test_portal_days_and_ted_links_are_read_as_the_portal_writes_them():
    assert S.parse_portal_day("2024-12-08+01:00 Europe/Brussels") == datetime(2024, 12, 8, tzinfo=UTC)
    assert S.parse_portal_day("22/09/2025") == datetime(2025, 9, 22, tzinfo=UTC)
    assert S.parse_portal_day("not a day") is None and S.parse_portal_day(None) is None
    assert S.ted_notice_number({"cftContractNoticeLink": ['["253106-2024","84/2024","2024-04-29"]']}) == "253106-2024"
    assert S.ted_notice_number({"cftContractNoticeLink": ['["84/2024"]']}) is None
    assert S.ted_notice_number({}) is None


def test_a_tenders_dates_decide_and_its_flag_only_closes():
    pub = datetime(2024, 11, 26, tzinfo=UTC)
    assert S.tender_status("forthcoming", pub, datetime(2024, 12, 8, tzinfo=UTC), None, TODAY) == "closed"
    assert S.tender_status("forthcoming", pub, datetime(2026, 12, 8, tzinfo=UTC), None, TODAY) == "open"
    assert S.tender_status("open", pub, None, datetime(2024, 6, 24, tzinfo=UTC), TODAY) == "closed"
    assert S.tender_status("forthcoming", pub, None, datetime(2026, 11, 4, tzinfo=UTC), TODAY) == "forthcoming"
    assert S.tender_status("open", pub, None, None, TODAY) == "unknown"
    assert S.tender_status("forthcoming", pub, None, None, TODAY) == "unknown"
    assert S.tender_status("closed", pub, None, None, TODAY) == "closed"


def test_each_kind_of_portal_tender_is_dated_from_its_own_fields():
    exa = S.normalise_row(_record("a-EXA", "31094501", cftEXARegistrationDeadline="2024-12-08+01:00 Europe/Brussels",
                                  cftPlannedDate="2024-12-09+01:00 Europe/Brussels"), today=TODAY)
    assert (exa["status"], exa["deadline"]) == ("closed", datetime(2024, 12, 8, tzinfo=UTC))
    pin = S.normalise_row(_record("b-PIN", "31094502", cftPlannedDate="24/06/2024",
                                  cftContractNoticeLink='["370415-2024","121/2024","2024-06-24"]'), today=TODAY)
    assert (pin["status"], pin["deadline"], pin["_planned"]) == ("closed", None, datetime(2024, 6, 24, tzinfo=UTC))
    cn = S.normalise_row(_record("c-CN", "31094502", cftContractNoticeLink='["143088-2026","42/2026","2026-03-02"]'), today=TODAY)
    assert (cn["status"], cn["deadline"], cn["ted_notice"]) == ("unknown", None, "143088-2026")
    shut = S.normalise_row(_record("d", "31094503"), today=TODAY)
    assert shut["status"] == "closed"
    dated = S.normalise_row(_record("e-CN", "31094501", deadlineDate="2026-11-30T00:00:00.000+0000"), today=TODAY)
    assert (dated["status"], dated["deadline"]) == ("open", datetime(2026, 11, 30, tzinfo=UTC))


def test_an_undated_contract_notice_is_dated_from_its_ted_notice_once():
    rows = {r["topic_id"]: r for r in (
        S.normalise_row(_record("c-CN", "31094502", cftContractNoticeLink='["143088-2026","42/2026","2026-03-02"]'), today=TODAY),
        S.normalise_row(_record("k-CN", "31094502", cftContractNoticeLink='["142782-2026","42/2026","2026-03-02"]'), today=TODAY),
        S.normalise_row(_record("p-PIN", "31094501", cftPlannedDate="04/11/2026",
                                cftContractNoticeLink='["559518-2026","1/2026","2026-09-01"]'), today=TODAY),
        S.normalise_row(_record("n-CN", "31094502"), today=TODAY))}
    asked = []

    def fetch(number):
        asked.append(number)
        return _EOI_XML
    counts = S.fill_tender_deadlines_from_ted(rows, {"k-CN": datetime(2027, 1, 31)}, TODAY, fetch=fetch, pause=0)
    assert asked == ["143088-2026"]          # the stored one is not read again, the PIN never
    assert rows["c-CN"]["status"] == "open" and rows["c-CN"]["deadline"].date() == date(2029, 12, 3)
    assert rows["k-CN"]["status"] == "open" and rows["k-CN"]["deadline"] == datetime(2027, 1, 31, tzinfo=UTC)
    assert rows["p-PIN"]["status"] == "forthcoming" and rows["p-PIN"]["deadline"] is None
    assert rows["n-CN"]["status"] == "unknown"
    assert counts == {"stored": 1, "ted_read": 1, "ted_dated": 1, "ted_undated": 0}


def test_a_tenders_unknown_replaces_a_stale_status_but_never_a_ted_notices():
    import re

    class Cur:
        sql = None

        def execute(self, sql, params=None):
            Cur.sql = sql
    S.upsert_ft_tenders(Cur(), {"topic_id": "c-CN", "status": "unknown", "deadline": None})
    status = re.search(r"\n\s+status = (CASE .*?END),", Cur.sql, re.S).group(1)
    assert "'unknown'" not in status
    assert re.match(r"CASE WHEN ft_calls_for_tenders\.source_url LIKE '%%ted\.europa\.eu%%'\s+OR EXCLUDED\.status IS NULL\s+"
                    r"THEN ft_calls_for_tenders\.status ELSE EXCLUDED\.status END", status)
