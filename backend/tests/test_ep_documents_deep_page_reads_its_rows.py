"""A deep page of /ep-documents reads only its own rows (17 Oct 2026).

The route merges amendment documents and committee work items in Python, so each branch must
fetch page*limit candidates. It fetched them as WHOLE rows, each amendment document with its
text (129 KB): page N read N*limit texts to serve limit of them, 35 GB from the database in four
days, and /council-documents, built the same way, took Supabase over its egress quota. The merge
now runs on (id, date) keys and only the page's rows are read in full.

Driven through FastAPI with a fake session that holds rows of both tables and answers the two
query shapes the route sends: keys (with_entities) and whole rows (filtered by id).
"""
from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.sql import operators  # noqa: E402

from core.database import get_db  # noqa: E402
from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from api.v1 import ep_entities  # noqa: E402
from models.committee_work import CommitteeWorkItem  # noqa: E402
from models.mep_amendment import AmendmentDocument  # noqa: E402

D0 = date(2026, 9, 1)
NOW = datetime(2026, 10, 17, 12, 0)


def _ad(n):
    # every 4th undated, pairs of documents sharing a date: the ties the id order must break
    return SimpleNamespace(
        id=uuid.UUID(int=10_000 + n * 7919 % 1000), document_type="PR", procedure_reference=f"2026/{n:04d}(COD)",
        committee_code="LIBE", pe_reference=f"PE{n}", rapporteur_name=None,
        # a timestamp at midnight, as the database returns it (the model says Date)
        document_date=None if n % 4 == 0 else datetime.combine(D0 + timedelta(days=n // 2), datetime.min.time()),
        doceo_url=f"https://ep/{n}",
        total_amendments=n, scraped_at=NOW, text_body=f"DRAFT REPORT {n} " + "x" * 50, body_html=f"<p>{n}</p>",
        updated_at=NOW)


def _cw(n):
    return SimpleNamespace(
        id=uuid.UUID(int=20_000 + n * 104729 % 1000), stage="in_committee", status=None, committee_code="ENVI",
        procedure_ref=f"2025/{n:04d}(INI)", title=f"Work item {n}", rapporteur_name=None,
        vote_date=datetime(2026, 9, 10 + n, 9, 0) if n % 3 == 0 else None, ep_page_url=f"https://ep/w{n}",
        source_url=None, eurlex_url=None, last_updated=NOW, committee_role=None, status_text=None,
        full_description=None, description=None, created_at=NOW)


ROWS = {"a": [_ad(n) for n in range(1, 38)], "c": [_cw(n) for n in range(1, 14)]}


def _sort_date(kind, r):
    v = r.document_date if kind == "a" else r.vote_date
    return v.date() if v else None


def _expected():
    """The documented order: date descending (a work item's vote date), then id ascending."""
    allrows = [(k, r) for k in ("a", "c") for r in ROWS[k]]
    allrows.sort(key=lambda kr: str(kr[1].id))
    allrows.sort(key=lambda kr: _sort_date(*kr) or date.min, reverse=True)
    return [str(r.id) for _, r in allrows]


class _Query:
    def __init__(self, db, entities, crit=(), lim=None):
        self.db, self.entities, self.crit, self.lim = db, entities, list(crit), lim

    def _kind(self):
        e = self.entities[0]
        cls = e if isinstance(e, type) else getattr(e, "class_", None)
        return {AmendmentDocument: "a", CommitteeWorkItem: "c"}.get(cls)

    def filter(self, *c):
        return _Query(self.db, self.entities, self.crit + list(c), self.lim)

    def with_entities(self, *e):
        return _Query(self.db, e, self.crit, self.lim)

    def order_by(self, *_):
        return self

    def limit(self, n):
        return _Query(self.db, self.entities, self.crit, n)

    def count(self):
        return len(ROWS[self._kind()]) if self._kind() else 0

    def all(self):
        kind = self._kind()
        if kind is None:  # legislative carriages for titles: none held
            return []
        rows = ROWS[kind]
        if not isinstance(self.entities[0], type):  # keys: (id, date), in the route's ORDER BY
            ordered = sorted(rows, key=lambda r: str(r.id))
            date_col = "document_date" if kind == "a" else "vote_date"
            ordered.sort(key=lambda r: (getattr(r, date_col) is not None, getattr(r, date_col) or 0), reverse=True)
            return [(r.id, getattr(r, date_col)) for r in ordered][: self.lim]
        ids = None
        for c in self.crit:
            if getattr(c, "operator", None) is operators.in_op:
                ids = {str(v) for v in c.right.value}
        out = [r for r in rows if ids is None or str(r.id) in ids][: self.lim]
        self.db.whole_rows += len(out)
        return out


class _Session:
    def __init__(self):
        self.whole_rows = 0

    def query(self, *entities):
        return _Query(self, entities)

    def execute(self, *_a, **_k):
        return SimpleNamespace(fetchall=lambda: [])


@pytest.fixture()
def client():
    app = FastAPI()
    app.include_router(ep_entities.ep_documents_router, prefix="/api/v1")
    holder = {}

    def _db():
        holder["db"] = _Session()
        yield holder["db"]
    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(role="admin", email="t@example.com")
    return TestClient(app), holder


@pytest.mark.parametrize("limit", [5, 7, 50])
def test_every_page_serves_the_documented_order_and_reads_only_its_rows(client, limit):
    api, holder = client
    expected = _expected()
    served = []
    page = 1
    while True:
        r = api.get("/api/v1/ep-documents", params={"limit": limit, "page": page})
        assert r.status_code == 200, r.text
        d = r.json()
        ids = [it["id"] for it in d["data"]]
        assert holder["db"].whole_rows == len(ids) <= limit, (
            f"page {page} read {holder['db'].whole_rows} whole rows to serve {len(ids)}")
        served += ids
        if not d["has_more"]:
            break
        page += 1
    assert d["total"] == len(expected) == 50
    assert served == expected


def test_a_page_keeps_each_items_body_and_date(client):
    api, _ = client
    d = api.get("/api/v1/ep-documents", params={"limit": 50}).json()
    by_id = {it["id"]: it for it in d["data"]}
    for r in ROWS["a"]:
        it = by_id[str(r.id)]
        assert it["body_txt"] == r.text_body and it["body_html"] == r.body_html
        assert it["document_date"] == (r.document_date.date().isoformat() if r.document_date else None)
    for r in ROWS["c"]:
        it = by_id[str(r.id)]
        assert it["document_date"] == (r.vote_date.date().isoformat() if r.vote_date else None)
        assert it["body_txt"].startswith(r.title)
