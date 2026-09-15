"""The Wikidata MEP loader must never store a bare QID as entity_name.

Regression for 15 Sep 2026: an "en"-only WDQS label service returns the QID itself for
people whose name lives only in the `mul` label, and 18 social_accounts rows (8 MEPs)
were named 'Q65437' etc.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
pytest.importorskip("sqlalchemy")
from services.social import wikidata_mep_loader as w  # noqa: E402


def _b(qid, label=None, epid=None, x="handle"):
    b = {"mep": {"value": f"http://www.wikidata.org/entity/{qid}"}, "x": {"value": x}}
    if label is not None:
        b["mepLabel"] = {"value": label}
    if epid:
        b["epid"] = {"value": epid}
    return b


def test_bare_qid_label_is_not_a_name():
    rows = w._rows_from_binding(_b("Q65437", label="Q65437"))
    assert rows and rows[0]["entity_name"] is None


def test_ep_directory_fallback_via_p1186():
    rows = w._rows_from_binding(_b("Q65437", label="Q65437", epid="1909"),
                                ep_names={"1909": "Bernd Lange"})
    assert rows[0]["entity_name"] == "Bernd Lange"


def test_real_label_wins():
    assert w.binding_name(_b("Q1", label="Chloé Ridel", epid="256904"),
                          {"256904": "Other"}) == "Chloé Ridel"


def test_pick_label_order():
    assert w.pick_label({"mul": {"value": "Bernd Lange"}}) == ("Bernd Lange", "mul")
    assert w.pick_label({"en": {"value": "A"}, "mul": {"value": "B"}}) == ("A", "en")
    assert w.pick_label({"hu": {"value": "Magyar Péter"}, "de": {"value": "Péter Magyar"}},
                        own_lang="hu") == ("Magyar Péter", "hu")
    assert w.pick_label({"xx": {"value": "Q5"}}) == (None, None)


def test_label_service_requests_mul():
    assert w.LABEL_LANGS[:2] == ["en", "mul"]


def test_needs_name_fallback():
    assert w.needs_name_fallback([_b("Q1", label="Q1")])
    assert not w.needs_name_fallback([_b("Q1", label="Bernd Lange")])


def test_ep_display_name():
    assert w.ep_display_name({"givenName": "Bernd", "familyName": "Lange",
                              "label": "Bernd LANGE"}) == "Bernd Lange"
