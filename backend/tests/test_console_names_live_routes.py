"""Hard rule (Victor, 3 Nov 2026): an endpoint or datapoint change also updates the console frontend.

The console reads its catalogue from the live spec, but its start buttons, each bundle's starting route and its copy
are written by hand. A route renamed or retired, or a new bundle, must fail here rather than leave a dead button."""
import json
import pathlib
import re

import pytest

from services.api_keys.bundles import bundle_ids, bundles_of

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SERVICE = _REPO / "frontend/src/services/api_console.ts"
_PANEL = _REPO / "frontend/src/components/api_console/api_console.tsx"
_NAMED = re.compile(r"""['"](/api/v2/[a-z0-9/_-]+)['"]""")


def _bundle_start() -> dict:
    block = re.search(r"BUNDLE_START[^{]*\{(.*?)\n\}", _SERVICE.read_text(encoding="utf-8"), re.S).group(1)
    return {key: path for key, path in re.findall(r"""['"]?([a-z-]+)['"]?:\s*['"](/api/v2/[^'"]+)['"]""", block)}


def _live_get_routes() -> dict:
    from main import app
    return {r.path: r for r in app.routes if getattr(r, "path", "").startswith("/api/v2/") and "GET" in getattr(r, "methods", [])}


def test_every_route_the_console_names_is_live_and_not_retired():
    named = set(_NAMED.findall(_SERVICE.read_text(encoding="utf-8"))) | set(_NAMED.findall(_PANEL.read_text(encoding="utf-8")))
    assert len(named) >= 5, f"the console's named routes were not found: {named}"
    routes = _live_get_routes()
    missing = sorted(p for p in named if p not in routes)
    assert not missing, f"the console names routes the API no longer serves: {missing}"
    retired = sorted(p for p in named if routes[p].deprecated)
    assert not retired, f"the console starts on deprecated routes: {retired}"


def test_every_bundle_starts_on_a_route_inside_it():
    start = _bundle_start()
    assert set(start) == set(bundle_ids())
    for bundle, path in start.items():
        assert bundle in bundles_of(path), f"{bundle} starts on {path}, which is not in it"


def test_the_console_orders_exactly_the_bundles_the_api_has():
    block = re.search(r"BUNDLE_ORDER[^\[]*\[(.*?)\]", _SERVICE.read_text(encoding="utf-8"), re.S).group(1)
    assert re.findall(r"""['"]([a-z-]+)['"]""", block) == bundle_ids()


@pytest.mark.parametrize("lang", ["en", "es", "ca", "fr", "it", "nl"])
def test_every_bundle_has_its_words_in_every_language(lang):
    words = json.loads((_REPO / f"frontend/src/i18n/locales/{lang}.json").read_text(encoding="utf-8"))["api"]["bundles"]
    for bundle in bundle_ids():
        assert words[bundle]["name"] and words[bundle]["desc"], f"{lang}: {bundle}"
