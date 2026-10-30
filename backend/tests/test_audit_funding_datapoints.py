"""The funding output audit judges values, not presence (Victor, 30 Oct 2026). Each rule on a page that
breaks it, and a clean page that breaks none."""
from datetime import datetime, timezone

from scripts.audit_funding_datapoints import audit_items, empty_fields

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
