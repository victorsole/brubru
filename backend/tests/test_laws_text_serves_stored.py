"""/laws/{celex}/text serves the stored text (Victor's go, 20 Oct 2026).

It read the act from Cellar on every call and kept the page's <head>, so GDPR's text began with Cellar's file name
"L_2016119EN.01000101.xml" (a 25-character prefix on the stored body_txt). Now: the stored column asked for, only
that one read; Cellar only for a law whose text is not stored yet, its <head> left out.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.orm import Query, Session  # noqa: E402

GDPR_TXT = "4.5.2016 EN Official Journal of the European Union L 119/1 REGULATION (EU) 2016/679 ..."
CELLAR_PAGE = ('<?xml version="1.0"?><html><head><title>L_2016119EN.01000101.xml</title>'
               '<style>p{}</style></head><body><p>4.5.2016 EN</p><p>REGULATION (EU) 2016/679</p></body></html>')


def _row(**kw):
    base = dict(id=1, celex="32016R0679", title="GDPR", doc_type="Regulation", doc_type_normalized="Regulation",
                date=None, created_at=datetime(2025, 11, 14), updated_at=datetime(2026, 10, 13))
    return SimpleNamespace(**{**base, **kw})


def _db(row, sent):
    class _Q(Query):
        def first(self):
            sent.append(str(self.statement.compile(dialect=postgresql.dialect())))
            return row
    return Session(query_cls=_Q)


def _no_cellar(monkeypatch):
    import httpx

    class _Boom:
        def __init__(self, *a, **k):
            raise AssertionError("Cellar was called although the text is stored")
    monkeypatch.setattr(httpx, "AsyncClient", _Boom)


@pytest.mark.parametrize("fmt,col,other,value", [("plain", "body_txt", "body_html", GDPR_TXT),
                                                 ("xml", "body_html", "body_txt", "<p>4.5.2016 EN</p>")])
def test_the_stored_text_is_served_and_only_its_column_is_read(monkeypatch, fmt, col, other, value):
    from api.v1.laws import get_law_text
    _no_cellar(monkeypatch)
    sent = []
    r = asyncio.run(get_law_text("32016r0679", format=fmt, user=None, db=_db(_row(**{col: value}), sent)))
    assert r.content == value and r.content_length == len(value) and r.format == fmt
    assert (r.body_txt if fmt == "plain" else r.body_html) == value
    assert f"eu_laws.{col}" in sent[0] and f"eu_laws.{other}" not in sent[0], sent[0][:300]


def test_a_text_not_stored_yet_is_read_from_cellar_without_the_page_head(monkeypatch):
    import httpx
    from api.v1.laws import get_law_text
    asked = []

    class _Client:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def get(self, url, headers=None):
            asked.append(url)
            return SimpleNamespace(status_code=200, text=CELLAR_PAGE)
    monkeypatch.setattr(httpx, "AsyncClient", _Client)
    r = asyncio.run(get_law_text("32016R0679", format="plain", user=None, db=_db(_row(body_txt=None), [])))
    assert r.content == "4.5.2016 EN REGULATION (EU) 2016/679"
    assert "L_2016119EN" not in r.content and asked == ["https://publications.europa.eu/resource/celex/32016R0679"]
    r = asyncio.run(get_law_text("32013D0377(01)", format="xml", user=None, db=_db(_row(celex="32013D0377(01)", body_html=""), [])))
    assert r.content == CELLAR_PAGE and asked[-1].endswith("32013D0377%2801%29")  # brackets encoded, as Cellar needs


def test_an_unknown_celex_is_a_404(monkeypatch):
    from fastapi import HTTPException
    from api.v1.laws import get_law_text
    with pytest.raises(HTTPException) as e:
        asyncio.run(get_law_text("39999R9999", format="plain", user=None, db=_db(None, [])))
    assert e.value.status_code == 404 and e.value.detail["reason_code"] == "not_found"
