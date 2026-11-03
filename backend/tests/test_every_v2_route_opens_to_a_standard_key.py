"""A standard read key opens every v2 route (Victor, 3 Nov 2026; register O141). 752 GET routes fell to read:misc,
which no self-serve key can hold, and the audits never saw it because they hold wildcard keys."""
import re

from services.api_keys.scopes import all_self_serve_scopes, resolve_required_scope
from services.billing.api_meter import resolve_cost_micro


def _v2_paths():
    from main import app
    # The spec, its page and the price list are public: the gate never asks them for a scope.
    return sorted({r.path for r in app.routes if getattr(r, "path", "").startswith("/api/v2")}
                  - {"/api/v2/docs", "/api/v2/openapi.json", "/api/v2/pricing"})


def test_no_v2_route_needs_a_scope_a_standard_key_cannot_hold():
    held = set(all_self_serve_scopes())
    closed = [p for p in _v2_paths() if resolve_required_scope(re.sub(r"\{[^}]+\}", "1", p)) not in held | {None}]
    assert not closed, f"{len(closed)} v2 routes have no scope a standard key holds, e.g. {closed[:5]}"
    assert len(_v2_paths()) > 1000


def test_each_folder_lands_on_its_own_scope():
    for path, scope in (("/api/v2/funding/opportunities", "read:commission"), ("/api/v2/funding/awards", "read:commission"),
                        ("/api/v2/hadea/calls", "read:publications"), ("/api/v2/ema/medicines/1", "read:publications"),
                        ("/api/v2/dpp/registry", "read:knowledge"), ("/api/v2/predictions/2025-0001/outcome", "read:procedures"),
                        ("/api/v2/parliament/mep-assistants", "read:ep"), ("/api/v2/commission/meetings", "read:calendar"),
                        ("/api/v2/parliament/webstreams", "read:calendar")):
        assert resolve_required_scope(path) == scope, path


def test_an_uncatalogued_path_still_stays_closed():
    assert resolve_required_scope("/api/v2/a-folder-nobody-catalogued") == "read:misc"
    assert resolve_required_scope("/api/v1/a-folder-nobody-catalogued") == "read:misc"


def test_opening_the_predictions_keeps_their_price():
    assert resolve_cost_micro("/api/v2/predictions/2025-0001/outcome")[0] == resolve_cost_micro("/api/v1/predictions/2025-0001/outcome")[0] == 5000
