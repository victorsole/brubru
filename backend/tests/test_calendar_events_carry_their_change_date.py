"""Calendar events carry updated_date, list and item (15 Oct 2026).

updated_from filters on last_updated, but the v1 item never carried it, so v2's
updated_date was null on all 5,853 events GovClipping walked; the envelope did not echo
the window; and the detail route lacked first_seen too (creation_date null)."""
import asyncio
import inspect
import uuid
from datetime import date, datetime

from sqlalchemy.orm import Query

from api.v1 import calendar as v1
from models.eu_calendar import EUCalendarEvent  # noqa: F401  (resolved below if moved)


class _Rows:
    def __init__(self, q, rows):
        self.q, self.rows = q, rows

    def __getattr__(self, name):
        attr = getattr(self.q, name)
        if name in ("filter", "order_by", "offset", "limit", "filter_by", "options"):
            return lambda *a, **k: _Rows(attr(*a, **k), self.rows)
        return attr

    def count(self):
        return len(self.rows)

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None


class _DB:
    def __init__(self, rows):
        self.rows = rows

    def query(self, *models):
        return _Rows(Query(models), self.rows)


def _event():
    return EUCalendarEvent(id=uuid.uuid4(), institution="EP", event_type="plenary_session", title="Plenary",
                           start_date=date(2026, 10, 19), all_day=True, policy_areas=[], procedure_refs=[],
                           source_url="https://www.europarl.europa.eu/plenary/en/home.html",
                           first_seen=datetime(2026, 9, 1, 4), last_updated=datetime(2026, 10, 14, 8))


def _call(fn, **given):
    kwargs = {n: given.get(n) for n in inspect.signature(fn).parameters}
    kwargs.update(given)
    return asyncio.run(fn(**kwargs))


def test_the_list_carries_updated_date_and_echoes_the_window():
    from api.v2.calendar import list_calendar_events
    env = _call(list_calendar_events, request=None, db=_DB([_event()]), limit=50, page=1, include_body=True,
                updated_from=datetime(2026, 10, 1), updated_to=datetime(2026, 10, 15))
    item = env.data[0]
    assert item.updated_date == datetime(2026, 10, 14, 8) and item.creation_date == datetime(2026, 9, 1, 4)
    assert env.updated_from == datetime(2026, 10, 1) and env.updated_to == datetime(2026, 10, 15)


def test_every_builder_sets_last_updated_and_first_seen():
    src = inspect.getsource(v1)
    builders = src.count("CalendarEventItem(") - 1
    assert src.count('last_updated=getattr(r, "last_updated", None)') == builders
    assert src.count('first_seen=getattr(r, "first_seen", None)') == builders
