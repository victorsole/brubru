"""EIB procurement: its own register, not TED (API audit, 1 Oct 2026, "Walk · EIB").

The old reader took TED notices still open on the day of a run (21 rows), stored the
deadline as the publication date and filled no procurement field. Fixtures are EIB
procedure pages saved that day: a corporate call (CFT-1747), a technical-assistance call
with an extended deadline (AA-010864-002) and a call for expression of interest
(CEOI-2512).
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.scrapers import agency_procurement as ap  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "eib"
NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _d(name):
    return ap._eib_detail((FIX / name).read_text())


def test_publication_date_is_the_contract_notice_not_the_latest_event():
    """The list's first date (28/08/2026) is the third modification notice; the call
    was published with its contract notice on 27/04/2026."""
    d = _d("call_cft_1747.html")
    assert d["published"] == datetime(2026, 4, 27, tzinfo=timezone.utc)
    assert d["deadline"] == datetime(2026, 9, 1, tzinfo=timezone.utc)
    kinds = [h["kind"] for h in d["history"]]
    assert kinds.count("Modification notice") == 4 and "Forecast Notice" in kinds
    cn = next(h for h in d["history"] if h["kind"] == "Contract notice")
    assert cn["ojeu"] == "2026/S 81-286898" and "NOTICE:286898-2026" in cn["url"]


def test_extended_deadline_and_award_are_read():
    d = _d("ta_aa_010864_002.html")
    assert d["published"] == datetime(2024, 12, 9, tzinfo=timezone.utc)
    assert d["deadline"] == datetime(2025, 3, 13, tzinfo=timezone.utc)
    assert d["history"][0]["kind"] == "Contract award notice"
    assert len(d["files"]) == 4 and all("/files/procurement/" in f for f in d["files"])


def test_eoi_issue_date_and_luxembourg_deadline():
    d = _d("eoi_ceoi_2512.html")
    assert d["published"] == datetime(2025, 12, 10, tzinfo=timezone.utc)
    # "09.03.2026 18:00 CET" is 17:00 UTC
    assert d["deadline"] == datetime(2026, 3, 9, 17, 0, tzinfo=timezone.utc)
    assert any(t.startswith("Issue of CEOI") for _k, t in d["blocks"])


def test_status_vocabulary():
    hist_cn = [{"kind": "Contract notice"}]
    hist_fc = [{"kind": "Forecast Notice"}]
    future, past = datetime(2026, 12, 1, tzinfo=timezone.utc), datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert ap._eib_status("On going", future, hist_cn, NOW) == "open"
    assert ap._eib_status("En cours", future, hist_cn, NOW) == "open"
    assert ap._eib_status("On going", past, hist_cn, NOW) == "closed"      # open only while ahead
    assert ap._eib_status("On going", None, hist_fc, NOW) == "forthcoming"
    assert ap._eib_status("Closed", future, hist_cn, NOW) == "closed"


def test_item_carries_eib_reference_and_publication_date():
    x = {"title": "CERBERUS - Provision of IT Security", "url": "cft-1747", "id": "a",
         "additionalInformation": ["Closed", "Calls for tenders", "CFT-1747", "28/08/2026", "01/09/2026"]}
    item = ap._eib_item("call", x, _d("call_cft_1747.html"), NOW)
    assert item.item_type == "tender"
    assert item.public_url == "https://www.eib.org/en/about/procurement/calls/all/cft-1747"
    assert item.extras["tender_reference"] == "CFT-1747" and item.extras["status"] == "closed"
    assert item.document_date == datetime(2026, 4, 27, tzinfo=timezone.utc)
    assert "Contract notice: OJEU 2026/S 81-286898 of 2026-04-27" in item.body_txt


def test_item_not_reread_sends_no_date_or_body():
    x = {"title": "t", "url": "ceoi-1", "id": "b",
         "additionalInformation": ["Closed", "ESIF", "CEOI-1", "01/01/2020", "02/02/2020"]}
    item = ap._eib_item("esif", x, None, NOW)
    assert item.item_type == "eoi_call" and item.document_date is None and not item.body_txt
    assert item.extras["deadline"] == datetime(2020, 2, 2, tzinfo=timezone.utc)


def test_list_pages_by_total_not_by_a_short_page(monkeypatch):
    """A page can come back one item short; stopping there lost 771 of 1,170 items."""
    pages = {0: [{"id": i} for i in range(100)], 1: [{"id": i} for i in range(100, 199)],
             2: [{"id": i} for i in range(199, 250)]}

    class R:
        def __init__(self, n):
            self.n = n

        def raise_for_status(self):
            pass

        def json(self):
            return {"valid": True, "totalItems": 250, "data": pages.get(self.n, [])}

    monkeypatch.setattr(ap.requests, "get", lambda url, params, **kw: R(params["pageNumber"]))
    assert len(ap._eib_list("call")) == 250


def _it(ref, title, url, date=None):
    from services.scrapers.economy_common import Item
    return Item(body_code="eib", item_type="tender", title=title, public_url=url, guid=ref,
                document_date=date, creation_date=NOW,
                extras={"tender_reference": ref, "status": "closed", "deadline": None})


def test_republished_procedure_keeps_the_newest_page():
    old = _it("AA-000998001", "Technical Environmental and Social Audits", "https://x/aa-000998001",
              datetime(2019, 7, 24, tzinfo=timezone.utc))
    new = _it("AA-000998001", "Technical Environmental and Social Audits", "https://x/aa-000998001-updated",
              datetime(2019, 12, 5, tzinfo=timezone.utc))
    assert ap._eib_one_reference_one_procedure([old, new]) == [new]


def test_a_mistyped_reference_stays_only_on_its_own_page():
    """EIB's page hl-875 states Reference: HL-975, the reference of page hl-975."""
    a = _it("HL-975", "Provision of security and safety services", "https://x/calls/all/hl-875")
    b = _it("HL-975", "Service providers for message handling activities", "https://x/calls/all/hl-975")
    out = ap._eib_one_reference_one_procedure([a, b])
    assert len(out) == 2
    assert a.extras["tender_reference"] is None and b.extras["tender_reference"] == "HL-975"


def test_a_title_or_a_bare_prefix_is_not_a_reference():
    for bad in (".", "HL-", "Consultancy - Financial Manager for the PIU"):
        x = {"title": "t", "url": "u", "id": "z", "additionalInformation": ["Closed", "Calls", bad, "", ""]}
        assert ap._eib_item("call", x, None, NOW).extras["tender_reference"] is None


def _notice(pn, form, date, title, proc="", deadline=None, buyers=1):
    return {"publication-number": pn, "form-type": form, "notice-type": form,
            "publication-date": f"{date}+02:00", "notice-title": {"eng": title},
            "internal-identifier-proc": [proc] if proc else None,
            "deadline-receipt-tender-date-lot": [f"{deadline}Z"] if deadline else None,
            "buyer-name": {"eng": ["European Investment Bank"] + ["Other body"] * (buyers - 1)}}


def test_ted_supplement_adds_only_what_the_register_lacks(monkeypatch):
    """CFT-1847 was open on TED and absent from EIB's register (1 Oct 2026)."""
    reg = _it("CFT-1747", "CERBERUS - Provision of IT Security Hardware and Software", "https://x/cft-1747")
    reg.body_txt = "Contract notice: OJEU 2026/S 81-286898 http://ted.europa.eu/udl?uri=TED:NOTICE:286898-2026:TEXT"
    notices = [
        _notice("286898-2026", "competition", "2026-04-27", "Luxembourg – IT – CERBERUS", "p1", "2026-09-01"),
        _notice("658350-2026", "competition", "2026-09-24", "Luxembourg – Training services – CFT-1847 Banking skills",
                "p2", "2026-11-16"),
        _notice("999999-2026", "competition", "2026-05-05", "Joint procurement", "p3", "2026-06-29", buyers=18),
        _notice("111111-2017", "planning", "2017-03-01", "Luxembourg – Old plan with no call", ""),
        _notice("222222-2025", "planning", "2025-01-10", "Luxembourg-Luxembourg: CERBERUS - Provision of IT Security "
                "Hardware and Software", ""),
    ]
    monkeypatch.setattr(ap, "_eib_ted_notices", lambda: notices)
    out = ap._eib_ted_supplement([reg], NOW)
    titles = {i.title: i for i in out}
    assert len(out) == 2                       # not the register's, not the joint one, not its plan
    new = next(i for i in out if "CFT-1847" in i.title)
    assert new.extras["status"] == "open" and new.extras["tender_reference"] == "p2"
    assert new.document_date == datetime(2026, 9, 24, tzinfo=timezone.utc)
    old_plan = next(i for i in out if "Old plan" in i.title)
    assert old_plan.extras["status"] == "closed"   # a 2017 plan with no call is not forthcoming


def test_ted_naming_a_register_reference_is_the_register_procedure(monkeypatch):
    """TED's procedure identifier for notice 37058-2025 is CFT-1788, a register reference."""
    reg = _it("CFT-1788", "Some register procedure", "https://x/cft-1788")
    reg.body_txt = "no notices listed"
    monkeypatch.setattr(ap, "_eib_ted_notices", lambda: [
        _notice("37058-2025", "competition", "2025-02-01", "Luxembourg – X – Other wording", "CFT-1788", "2025-03-01")])
    assert ap._eib_ted_supplement([reg], NOW) == []
