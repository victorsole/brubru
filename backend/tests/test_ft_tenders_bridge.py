"""EU-institution contract notices bridged into `tenders` look native to the
matcher and screens (29 Sep 2026)."""
import importlib.util
import pathlib

_p = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "bridge_ft_tenders_to_tenders.py"
_spec = importlib.util.spec_from_file_location("bridge_ft", _p)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


def _row(**kw):
    base = {"tender_reference": "e9e1e866-CN", "contracting_authority": "European Border and Coast Guard Agency (FRONTEX)",
            "title": " Dynamic Purchasing System (DPS) for Technical Equipment ", "description": "",
            "contract_type": "Supplies", "estimated_value": 12000000, "value_currency": "EUR",
            "deadline": None, "source_url": "https://portal/tender-details/e9e1e866-CN", "documents_url": None,
            "cpv_codes": [], "published_at": None}
    base.update(kw)
    return base


def test_identity_nature_and_link():
    r = bridge.to_row(_row())
    assert r["pub"] == "FT-e9e1e866-CN" and r["ref"] == "e9e1e866-CN"
    assert r["nature"] == "supplies"                    # TED rows are lower case
    assert r["title"].startswith("Dynamic") and not r["title"].endswith(" ")
    assert r["description"] is None                     # empty stays empty, never ""
    assert r["cpv"] is None and r["cpv_main"] is None   # [] means no signal, not a code
    assert r["submission_url"] == "https://portal/tender-details/e9e1e866-CN"
    assert r["documents_url"] == r["submission_url"]    # falls back to the notice page


def test_cpv_codes_carry_through():
    r = bridge.to_row(_row(cpv_codes=["35000000", None, "38000000"]))
    assert r["cpv"] == ["35000000", "38000000"] and r["cpv_main"] == "35000000"


def test_unknown_contract_type_is_null_not_invented():
    assert bridge.to_row(_row(contract_type="Mixed"))["nature"] is None
