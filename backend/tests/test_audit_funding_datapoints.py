"""The funding output audit judges values, not presence (Victor, 30 Oct 2026). Each rule on a page that
breaks it, and a clean page that breaks none."""
from datetime import datetime, timezone

from scripts.audit_funding_datapoints import audit_items, audit_status, empty_fields

NOW = datetime(2026, 10, 30, 15, 0, tzinfo=timezone.utc)
BODY = "A call for tenders for evaluation services. " * 10


def _item(i, **kw):
    base = {"id": i, "self": f"https://h/api/v2/funding/x/{i}", "public_url": f"https://agency.europa.eu/tenders/{i}",
            "title": f"Tender {i}", "summary": "Evaluation services", "body_txt": BODY, "body_html": f"<p>{BODY}</p>",
            "document_date": "2026-10-01", "creation_date": "2026-10-02T08:00:00Z", "updated_date": "2026-10-03T08:00:00Z"}
    base.update(kw)
    return base


def test_a_clean_page_has_no_finding():
    found, _ = audit_items([_item(i) for i in range(5)], NOW)
    assert not found


def test_each_rule_catches_its_value():
    items = [
        _item(1, public_url=None, body_txt=None, body_html=None),
        _item(2, public_url="https://agency.europa.eu/", body_txt="Tender 2", body_html="<p>Tender 2</p>"),
        _item(3, public_url="https://agency.europa.eu/list", document_date="2027-10-07"),
        _item(4, public_url="https://agency.europa.eu/list", body_txt=BODY + " We use cookies.", document_date="1970-01-01"),
        _item(5, public_url="https://agency.europa.eu/list", creation_date="2026-10-05T08:00:00Z"),
        _item(6, updated_date="2026-10-03T08:00:00", body_html="<p>short</p>"),
        _item(6, body_txt=BODY + " Ã©"),
    ]
    found, examples = audit_items(items, NOW)
    expected = {
        "public_url_missing": 1, "body_txt_missing": 1, "body_html_missing": 1, "public_url_home_page": 1,
        "body_txt_stub_under_200": 1, "body_is_title_or_summary": 1, "public_url_shared_by_3_or_more": 3,
        "document_date_in_future": 1, "document_date_before_1990": 1, "body_banner_or_javascript_text": 1,
        "creation_after_updated": 1, "naive_datetime": 1, "body_txt_and_html_differ_in_length": 1,
        "id_repeated_on_page": 2, "body_mojibake": 1,
    }
    assert dict(found) == expected, dict(found)
    assert examples["public_url_missing"] == ["1"]


def test_one_batch_stamp_for_many_items_is_not_a_source_date():
    items = [_item(i, document_date="2017-07-27T10:41:12") for i in range(6)] + [_item(9)]
    found, _ = audit_items(items, NOW)
    assert found["document_date_one_stamp_for_many"] == 6
    midnight = [_item(i, document_date="2026-10-01T00:00:00") for i in range(6)]
    assert "document_date_one_stamp_for_many" not in audit_items(midnight, NOW)[0]
    # 30 Oct 2026: TED notices of one publication day all read 2026-10-30T01:00:00Z: a day, not a batch stamp
    one_day = [_item(i, document_date="2026-10-30T01:00:00Z") for i in range(6)]
    assert "document_date_one_stamp_for_many" not in audit_items(one_day, NOW)[0]


def test_a_field_empty_on_every_item_is_listed():
    items = [_item(1, deadline=None, cpv=[]), _item(2, deadline="", cpv=[])]
    assert empty_fields(items) == ["cpv", "deadline"]


def test_a_status_is_read_against_the_items_own_dates():
    now = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    found, examples = audit_status([
        {"id": 1, "status": "open", "opening_date": "2027-10-07", "deadline": "2028-01-20"},          # 2 Nov 2026: 247 of these
        {"id": 2, "status": "forthcoming", "opening_date": "2027-10-07", "deadline": "2028-01-20"},   # fine
        {"id": 3, "status": "open", "opening_date": "2026-09-01", "deadline": "2026-10-01"},          # past its deadline
        {"id": 4, "status": "open", "deadline": "2026-10-01", "deadline_secondary": "2027-01-01"},    # a second stage ahead: fine
        {"id": 5, "status": "forthcoming", "opening_date": "2026-09-01", "deadline": "2027-01-01"},   # opened, still forthcoming
        {"id": 6, "status": "closed", "opening_date": "2027-10-07", "deadline": "2028-01-20"},        # a source may close early
        {"id": 7, "status": "open"},                                                                  # no date to judge by
    ], now)
    assert dict(found) == {"status_open_before_opening": 1, "status_open_past_deadline": 1,
                           "status_forthcoming_after_opening": 1}
    assert examples["status_open_before_opening"] == ["1"] and examples["status_forthcoming_after_opening"] == ["5"]


def test_an_outage_page_and_a_share_menu_in_a_body_are_flagged():
    outage = "Server inaccessibility\nbg\nСървърът е временно недостъпен\n" + "Please try again later. " * 20
    share = "Share\nFacebook\nLinkedIn\nX\nWhatsapp\nPRINT\nA tender for legal services.\n" + BODY
    found, _ = audit_items([_item(1, body_txt=outage, body_html=f"<p>{outage}</p>"),
                            _item(2, body_txt=share, body_html=f"<p>{share}</p>")], NOW)
    assert found["body_is_outage_page"] == 1 and found["body_share_menu"] == 1


def test_a_files_address_in_the_text_does_not_make_the_two_bodies_differ():
    url = "https://ec.europa.eu/info/funding-tenders/opportunities/docs/annex-" + "x" * 300 + ".pdf"
    txt = BODY + "\n" + "\n".join(f"Document: Annex {i} (PDF) {url}" for i in range(4))
    htm = f"<p>{BODY}</p><h2>Documents</h2><ul>" + "".join(f'<li><a href="{url}">Annex {i}</a> · PDF</li>' for i in range(4)) + "</ul>"
    found, _ = audit_items([_item(1, body_txt=txt, body_html=htm)], NOW)
    assert not found["body_txt_and_html_differ_in_length"]
    # text the html really lacks is still flagged
    found, _ = audit_items([_item(2, body_txt=BODY * 4, body_html=f"<p>{BODY}</p>")], NOW)
    assert found["body_txt_and_html_differ_in_length"] == 1


def test_a_date_tomorrow_is_in_the_future_and_today_in_another_time_zone_is_not():
    found, _ = audit_items([_item(1, document_date="2026-10-31T12:00:00Z")], NOW)     # 21 hours ahead
    assert found["document_date_in_future"] == 1
    found, _ = audit_items([_item(2, document_date="2026-10-31T00:00:00Z")], NOW)     # 9 hours ahead
    assert not found["document_date_in_future"]
