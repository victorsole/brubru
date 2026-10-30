"""/funding/all and /funding/entrepreneur-instruments items carry `self` (20 Oct 2026).

Neither list has an item route of its own, so the self-link middleware had nothing to point at.
/funding/all now links each row to the route that serves it, read from the live route table;
entrepreneur instruments link their call on ft-calls-for-proposals.
"""
import pathlib
import sys

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))


def test_every_type_the_consolidated_lists_link_has_a_live_item_route():
    """/opportunities and /budgets point each row at the route that serves it, read from the live route
    table (it served /funding/all's rows until that list became an alias of /opportunities, 30 Oct 2026)."""
    from main import app
    from api.v2.funding._standard import item_routes
    routes = item_routes(app)
    assert routes[("euaa", "eoi_call")] == "/api/v2/funding/euaa-calls/{item_id}"
    assert routes[("erdf", "cohesion_allocation")] == "/api/v2/funding/erdf/{row_id}"
    assert routes[("eusf", "solidarity_case")] == "/api/v2/funding/eusf/{row_id}"
    assert routes[("eagf", "cap_payment")] == "/api/v2/funding/eagf/{row_id}"


def test_an_entrepreneur_instrument_links_its_call():
    from api.v2.funding import entrepreneur_instruments as ei
    item = ei.EntrepreneurInstrumentItem(id="1", topic_id="HORIZON-EIC-2026-ACCELERATOR-01", title="EIC Accelerator",
                                         source_url="https://ec.europa.eu/info/funding-tenders/x")
    assert ei._with_self(item, "https://x").self == "https://x/api/v2/funding/ft-calls-for-proposals/HORIZON-EIC-2026-ACCELERATOR-01"
