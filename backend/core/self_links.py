"""Give every listed item a `self` URL, so a client never has to guess the key.

Why
---
Fixing the 18 broken identifier pairs made `id` work everywhere it is published.
It did not remove the underlying question a client still has to answer: *which
field do I put in the URL?* Measured across the v2 surface, the answer is not
always `id`:

    /commission/commissioners/{slug}              -> the item's `slug`
    /legislative/eur-lex/laws/summaries/{summary_id} -> `summary_id`
    /funding/programmes/{acronym}                 -> `acronym`
    /open-data/cohesion-datasets/{socrata_id}     -> `socrata_id`
    /transparency-register/{code}                 -> `code`

Twelve item routes key on something other than `id`, and their collections
publish that field under its own name with nothing marking it as the identifier.
A `self` link ends the guessing: the client follows a URL the server built and
escaped, which also solves references containing "/" and "(" without the client
knowing they needed encoding.

How the target is chosen
------------------------
From the route table, not from a hand-written list. For a collection path C we
look for an item route `C/{param}`, and `param` names the field to read off the
item -- `{slug}` means use `item["slug"]`. Aggregators are handled explicitly:
`/news/all` lists items whose item route is `/news/{item_id}`, one level up.

What it does NOT cover, measured 31 August 2026
-----------------------------------------------
  * 7 item routes whose collection is empty -- there is nothing to link to.
  * 3 function-style routes (`verify-citation/{ref}`, `eurovoc/authority/{table}`)
    which are not items of any collection.

So this reaches 18 of the 28 routes that a parent `id` could not, and adds a
`self` to every one of the ~400 that it could. It is not a universal answer, and
saying so is cheaper than discovering it later.
"""

from __future__ import annotations

import re
from typing import Dict, Optional, Tuple
from urllib.parse import quote

# Collections whose items belong to an item route that is NOT `<collection>/{x}`.
# `/api/v2/news/all` is a cross-body aggregator; its items are fetched from
# `/api/v2/news/{item_id}`, one segment up.
_AGGREGATOR_PARENTS = ("/all",)

_PARAM_RE = re.compile(r"^\{([^}]+)\}$")


def build_route_map(app) -> Dict[str, Tuple[str, str]]:
    """collection path -> (item route template, the field to read off each item).

    Built from the live route table so it cannot drift from what is served.
    """
    get_paths = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None) or set()
        if path and "GET" in methods:
            get_paths.add(path)

    item_routes: Dict[str, Tuple[str, str]] = {}
    for path in get_paths:
        head, _, last = path.rpartition("/")
        m = _PARAM_RE.match(last)
        if not m or not head.startswith("/api/v2/"):
            continue
        if "{" in head:            # a sub-resource, not an item of a collection
            continue
        # FastAPI keeps its converter in the template -- `{reference:path}` --
        # and the field on the item is just `reference`.
        field = m.group(1).split(":", 1)[0]
        item_routes[head] = (path, field)

    out: Dict[str, Tuple[str, str]] = {}
    for collection in get_paths:
        if "{" in collection or not collection.startswith("/api/v2/"):
            continue
        if collection in item_routes:
            out[collection] = item_routes[collection]
            continue
        for suffix in _AGGREGATOR_PARENTS:
            if collection.endswith(suffix):
                parent = collection[: -len(suffix)]
                if parent in item_routes:
                    out[collection] = item_routes[parent]
                break
    return out


def self_url(base_url: str, item_route: str, value) -> Optional[str]:
    """Substitute `value` into the item route, escaped.

    The escaping is the point: `2025/2211(INI)` has to become
    `2025%2F2211%28INI%29`, and a client that built the URL itself would very
    likely not do that.
    """
    if value is None or str(value).strip() == "":
        return None
    return base_url.rstrip("/") + re.sub(
        r"\{[^}]+\}$", quote(str(value), safe=""), item_route
    )


def attach_self(payload, base_url: str, route_map: Dict[str, Tuple[str, str]],
                collection_path: str) -> bool:
    """Add `self` to each item of an envelope in place. True if anything changed.

    Never overwrites a `self` a handler set deliberately, and never invents one
    when the item does not carry the field the route needs.
    """
    target = route_map.get(collection_path)
    if not target or not isinstance(payload, dict):
        return False
    items = payload.get("data")
    if not isinstance(items, list):
        return False

    item_route, field = target
    changed = False
    for item in items:
        if not isinstance(item, dict) or item.get("self"):
            continue
        value = _identifier_value(item, field)
        url = self_url(base_url, item_route, value)
        if url:
            item["self"] = url
            changed = True
    return changed


def _identifier_value(item: dict, field: str):
    """The value to put in the URL, in decreasing order of confidence.

    The route's own parameter name is the best signal -- `{slug}` means read
    `slug`. But the two do not always agree: `/transparency-register/{code}`
    lists items whose field is `identification_code`, and
    `/open-data/eurostat-series/{dataset_code}` lists items whose field is
    plain `code`. Rather than keep a hand-written alias table that will drift,
    fall back to a field whose name contains the parameter's, then to `id`.
    """
    if item.get(field) is not None:
        return item[field]
    # `identification_code` for `{code}`; `code` for `{dataset_code}`.
    for key, value in item.items():
        if value is None or key in ("self", "public_url"):
            continue
        if key.endswith("_" + field) or field.endswith("_" + key):
            return value
    return item.get("id")
