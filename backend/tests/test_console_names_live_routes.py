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


def _tasks() -> list:
    """The console's starting cards, as written in the service: id, route, bundle and the fields each names."""
    block = re.search(r"export const TASKS[^=]*=\s*\[(.*?)\n\];", _SERVICE.read_text(encoding="utf-8"), re.S).group(1)
    tasks = []
    for chunk in re.split(r"\n  \},?\n?", block):
        task_id = re.search(r"id: '([a-z-]+)'", chunk)
        if not task_id:
            continue
        names = set(re.findall(r"'([a-z_]+)'", re.search(r"main: \[(.*?)\]", chunk, re.S).group(1)))
        for key in ("prefill", "examples", "options"):
            found = re.search(key + r": \{(.*?)\},?\n", chunk, re.S)
            if found:
                names |= set(re.findall(r"(?:^|[\s,{])([a-z_]+):", found.group(1)))
        tasks.append({
            "id": task_id.group(1),
            "path": re.search(r"path: '([^']+)'", chunk).group(1),
            "bundle": re.search(r"bundle: '([^']+)'", chunk).group(1),
            "names": names,
        })
    return tasks


def test_the_cards_are_found_and_each_opens_inside_its_bundle():
    tasks = _tasks()
    assert len(tasks) >= 8, tasks
    for task in tasks:
        assert task["bundle"] in bundles_of(task["path"]), f"{task['id']}: {task['path']} is not in {task['bundle']}"


def test_every_field_a_card_names_is_a_field_of_its_route():
    from main import app
    paths = app.openapi()["paths"]
    for task in _tasks():
        fields = {p["name"] for p in paths[task["path"]]["get"].get("parameters", [])}
        missing = sorted(task["names"] - fields)
        assert not missing, f"{task['id']} names fields {task['path']} does not take: {missing}"


def _words(lang: str) -> dict:
    return json.loads((_REPO / f"frontend/src/i18n/locales/{lang}.json").read_text(encoding="utf-8"))["api"]["console"]


def _flat(tree: dict, prefix: str = "") -> dict:
    out = {}
    for key, value in tree.items():
        if isinstance(value, dict):
            out.update(_flat(value, f"{prefix}{key}."))
        else:
            out[f"{prefix}{key}"] = value
    return out


@pytest.mark.parametrize("lang", ["en", "es", "ca", "fr", "it", "nl"])
def test_every_card_has_its_words(lang):
    words = _words(lang)["tasks"]
    for task in _tasks():
        assert words[task["id"]]["title"] and words[task["id"]]["desc"], f"{lang}: {task['id']}"


@pytest.mark.parametrize("lang", ["es", "ca", "fr", "it", "nl"])
def test_the_console_says_the_same_things_in_every_language(lang):
    english, other = _flat(_words("en")), _flat(_words(lang))
    assert set(english) == set(other), sorted(set(english) ^ set(other))[:10]
    placeholder = re.compile(r"\{\{(\w+)\}\}")
    for key, text in english.items():
        assert set(placeholder.findall(text)) == set(placeholder.findall(other[key])), f"{lang}: {key}"
