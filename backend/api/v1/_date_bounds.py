"""An upper time bound given as a bare date covers that whole day.

`updated_to` / `updated_end` are datetimes, for incremental sync. A caller who sends
`updated_to=2026-09-15` means "up to and including 15 September", but a bare date parses
as MIDNIGHT at the start of the day, so every row updated during that day was dropped:
the same boundary defect the date filters had (fixed 15 Sep 2026, 8c079852). A value
with a time of day keeps its exact meaning.
"""
from __future__ import annotations

import re
from datetime import datetime, time
from typing import Annotated, Any

from pydantic import BeforeValidator

_BARE_DATE = re.compile(r"^\s*(\d{4})-(\d{2})-(\d{2})\s*$")


def _end_of_day_if_bare_date(value: Any) -> Any:
    if isinstance(value, str):
        m = _BARE_DATE.match(value)
        if m:
            try:
                return datetime.combine(datetime(int(m[1]), int(m[2]), int(m[3])).date(), time.max)
            except ValueError:
                return value  # an impossible date: let normal validation reject it
    return value


UpperBoundDatetime = Annotated[datetime, BeforeValidator(_end_of_day_if_bare_date)]
