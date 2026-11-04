"""The values some filters accept, for a person choosing from a list (4 Nov 2026). Public and free, like /pricing and
/bundles: the API Console reads it on load, and a read on load must not spend a visitor's free calls."""
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.v1.metadata import EP_COMMITTEES_FULL
from core.database import get_db
from services.economy.body_families import CALENDAR_ONLY_BODY_NAMES, FAMILIES

router = APIRouter(tags=["v2-docs"])

_CACHE_SECONDS = 3600
_cache: Dict[str, object] = {"at": 0.0, "bodies": []}


def _bodies(db: Session) -> List[dict]:
    """Code and name of every EU body with a feed. A small table, read at most once an hour."""
    if time.monotonic() - float(_cache["at"]) < _CACHE_SECONDS and _cache["bodies"]:
        return _cache["bodies"]  # type: ignore[return-value]
    names = dict(CALENDAR_ONLY_BODY_NAMES)
    for row in db.execute(text("SELECT code, name FROM economy_bodies")).fetchall():
        names.setdefault(row.code, row.name)
    bodies = sorted(({"code": code, "name": name or code} for code, name in names.items()), key=lambda b: b["name"].casefold())
    _cache.update(at=time.monotonic(), bodies=bodies)
    return bodies


@router.get(
    "/pick-lists",
    summary="The values some filters accept: EU bodies, policy families, committees",
    description="""**What it does**
Lists the values three common filters accept, each with its plain name: the codes of the EU bodies (`body`), the policy families (`family`) and Parliament's committees (`committee`).

**When to use it**
To offer a person a list of names instead of asking them to know a code, as the API Console does. Send the code, show the name.

**Input**
None. No API key is needed and the call is free.

**Try it**
`GET /api/v2/pick-lists`

**You get back**
`bodies` (`code`, `name`), `families` (`slug`, `label`) and `committees` (`code`, `name`). Which bodies have items differs from feed to feed, so a body on this list can answer no rows on one of them.""",
)
def api_pick_lists(response: Response, db: Session = Depends(get_db)) -> dict:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return {
        "bodies": _bodies(db),
        "families": sorted(({"slug": slug, "label": f["label"]} for slug, f in FAMILIES.items()), key=lambda f: f["label"].casefold()),
        "committees": [{"code": c.get("code"), "name": c.get("name")} for c in EP_COMMITTEES_FULL],
    }
