"""The values some filters accept, for a person choosing from a list (4 Nov 2026). Public and free, like /pricing and
/bundles: the API Console reads it on load, and a read on load must not spend a visitor's free calls."""
import datetime as dt
import logging
import time
from typing import Dict, List

from fastapi import APIRouter, Depends, Response
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.v1.metadata import EP_COMMITTEES_FULL
from api.v2.consultations.consultations_all import _HYS_BODY
from core.database import get_db
from services.economy.body_families import CALENDAR_ONLY_BODY_NAMES, FAMILIES

logger = logging.getLogger(__name__)
router = APIRouter(tags=["v2-docs"])

_CACHE_SECONDS = 3600
_cache: Dict[str, object] = {"at": 0.0, "bodies": [], "consultations_at": 0.0, "consultations": None, "oj_days_at": 0.0, "oj_days": None}
# Runs consultations but has no feed of its own, so economy_bodies does not name it.
_NAMES_OUTSIDE_THE_FEEDS = {"jrc": "Joint Research Centre"}


def _names(db: Session) -> Dict[str, str]:
    names = dict(CALENDAR_ONLY_BODY_NAMES)
    for row in db.execute(text("SELECT code, name FROM economy_bodies")).fetchall():
        names.setdefault(row.code, row.name)
    return names


def _bodies(db: Session) -> List[dict]:
    """Code and name of every EU body with a feed. A small table, read at most once an hour."""
    if time.monotonic() - float(_cache["at"]) < _CACHE_SECONDS and _cache["bodies"]:
        return _cache["bodies"]  # type: ignore[return-value]
    bodies = sorted(({"code": code, "name": name or code} for code, name in _names(db).items()), key=lambda b: b["name"].casefold())
    _cache.update(at=time.monotonic(), bodies=bodies)
    return bodies


def _consultation_scope(db: Session) -> dict:
    """The bodies and families that have consultations: 14 of the 87 bodies on 4 Nov 2026, so a form offering all of them
    spends a visitor's free search on an empty answer. The two sources /consultations/all reads, by the same rules. If this
    cannot be read, the form offers the full list as before, and the next visitor tries again."""
    cached = _cache["consultations"]
    if cached and time.monotonic() - float(_cache["consultations_at"]) < _CACHE_SECONDS:
        return cached  # type: ignore[return-value]
    try:
        codes = {row[0] for row in db.execute(text(f"SELECT DISTINCT {_HYS_BODY} FROM public_consultations")).fetchall()}
        codes |= {row[0] for row in db.execute(text(
            "SELECT DISTINCT lower(body_code) FROM economy_items WHERE item_type IN ('consultation','public_consultation')")).fetchall()}
        codes.discard(None)
        names = {**_NAMES_OUTSIDE_THE_FEEDS, **_names(db)}
    except Exception as exc:
        db.rollback()
        logger.error("[ERROR] pick-lists could not read which bodies have consultations: %s", exc)
        return {"bodies": [], "families": []}
    scope = {
        "bodies": sorted(({"code": c, "name": names.get(c) or c.upper()} for c in codes), key=lambda b: b["name"].casefold()),
        "families": sorted(
            ({"slug": slug, "label": f["label"]} for slug, f in FAMILIES.items() if codes & set(f["bodies"])),
            key=lambda f: f["label"].casefold(),
        ),
    }
    _cache.update(consultations_at=time.monotonic(), consultations=scope)
    return scope


def _oj_days(db: Session) -> List[str]:
    """The last days the Official Journal came out, newest first. A holiday has no issue (2 Nov 2026), so a form that works
    out a recent working day from the calendar spends a visitor's free search on an empty answer. Read from the daily OJ
    sync, which held the same days as /oj/daily on 5 Nov 2026. If this cannot be read, the form works out the day as before,
    and the next visitor tries again."""
    cached = _cache["oj_days"]
    if cached and time.monotonic() - float(_cache["oj_days_at"]) < _CACHE_SECONDS:
        return cached  # type: ignore[return-value]
    today = dt.date.today()
    try:
        rows = db.execute(text(
            "SELECT DISTINCT oj_date FROM oj_entries WHERE series = 'L' AND oj_date >= :since AND oj_date <= :today "
            "ORDER BY oj_date DESC LIMIT 4"
        ), {"since": today - dt.timedelta(days=21), "today": today}).fetchall()
    except Exception as exc:
        db.rollback()
        logger.error("[ERROR] pick-lists could not read the days the Official Journal came out: %s", exc)
        return []
    days = [str(row[0])[:10] for row in rows]
    _cache.update(oj_days_at=time.monotonic(), oj_days=days)
    return days


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
`bodies` (`code`, `name`), `families` (`slug`, `label`) and `committees` (`code`, `name`). Which bodies have items differs from feed to feed, so a body on this list can answer no rows on one of them. `consultations` (`bodies`, `families`) holds only the ones that have public consultations. `oj_days` holds the last four days the Official Journal came out, newest first, so a form can offer a day that has acts.""",
)
def api_pick_lists(response: Response, db: Session = Depends(get_db)) -> dict:
    response.headers["Cache-Control"] = "public, max-age=3600"
    return {
        "bodies": _bodies(db),
        "families": sorted(({"slug": slug, "label": f["label"]} for slug, f in FAMILIES.items()), key=lambda f: f["label"].casefold()),
        "committees": [{"code": c.get("code"), "name": c.get("name")} for c in EP_COMMITTEES_FULL],
        "consultations": _consultation_scope(db),
        "oj_days": _oj_days(db),
    }
