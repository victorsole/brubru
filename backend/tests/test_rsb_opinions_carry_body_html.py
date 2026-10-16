"""An RSB opinion carries body_html: its text in paragraphs (16 Oct 2026; null on all 487)."""
from datetime import date, datetime
from types import SimpleNamespace

from api.v1.w4_endpoints import rsb_item


def test_the_opinion_text_is_served_as_html_too():
    r = SimpleNamespace(id=1, opinion_reference="SEC(2026)780", title="Opinion on the impact assessment",
                        target_initiative="Digital Networks Act", target_dg="CNECT", procedure_ref=None,
                        opinion_type="impact_assessment", verdict="positive_with_reservations",
                        opinion_date=date(2026, 1, 20), summary="Positive with reservations.",
                        pdf_url="https://ec.europa.eu/x.pdf", source_url="https://ec.europa.eu/transparency/documents-register/detail?ref=SEC(2026)780",
                        full_text="Opinion\n\nThe Board gives a positive opinion with reservations.",
                        first_seen=datetime(2026, 10, 15), last_updated=datetime(2026, 10, 15),
                        updated_at=datetime(2026, 10, 15), policy_areas=[])
    item = rsb_item(r)
    assert item.body_html and "The Board gives a positive opinion with reservations." in item.body_html
    assert item.body_txt.startswith("Opinion")
