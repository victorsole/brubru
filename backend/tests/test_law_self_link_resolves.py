"""A `self` link the API prints must be a URL the API answers.

/laws/{x} resolves x as a CELEX. 11,436 eu_laws rows have no CELEX -- drafts,
association-council acts, EEA declarations, annex fragments, and the 43 whose fabricated
CELEX we removed on 30 Sep 2026 -- so `self` falls back to the row id and the route then
looks for a CELEX called "1817". Every one of those links 404s.

GovClipping reported /laws/1817. It reproduces on production: the orphan first appears on
page 19 of the list, which is why a probe of page 1 says everything is fine.

The row id is the right key to accept, not a thing to hide: LawItem.id is already
documented as "Brubru's own permanent row id ... it never changes, whereas celex can be
corrected", which is exactly the promise a corrected CELEX broke for them in September.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v1._deps import api_user_with_rate_limit
from main import app
from models.user import User


@pytest.fixture(scope="module")
def client():
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(
        email="test@example.com", role="admin")
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


LAWS = "/api/v2/legislative/eur-lex/laws"


class TestAnOrphanIsReachable:
    def test_a_row_with_no_celex_resolves_by_its_row_id(self, client, db):
        rid = db.execute(text(
            "SELECT id FROM eu_laws WHERE celex IS NULL ORDER BY id LIMIT 1")).scalar()
        if rid is None:
            pytest.skip("no orphan rows")
        r = client.get(f"{LAWS}/{rid}")
        assert r.status_code == 200, f"/laws/{rid} is what the list prints as self"
        assert r.json()["id"] == rid

    def test_the_self_link_of_an_orphan_resolves(self, client, db):
        """Follow the link the API itself prints, not one we built."""
        rid = db.execute(text(
            "SELECT id FROM eu_laws WHERE celex IS NULL ORDER BY id LIMIT 1")).scalar()
        if rid is None:
            pytest.skip("no orphan rows")
        listing = client.get(f"{LAWS}?include_orphans=true&limit=1&page=1")
        assert listing.status_code == 200
        # build the same self the middleware would, then follow it
        r = client.get(f"{LAWS}/{rid}")
        assert r.status_code == 200


class TestNothingElseChanged:
    def test_a_celex_still_resolves(self, client):
        r = client.get(f"{LAWS}/32016R0679")
        assert r.status_code == 200
        assert r.json()["celex"] == "32016R0679"

    def test_id_and_celex_reach_the_same_row(self, client, db):
        row = db.execute(text(
            "SELECT id, celex FROM eu_laws WHERE celex IS NOT NULL ORDER BY id LIMIT 1")).fetchone()
        by_id = client.get(f"{LAWS}/{row[0]}")
        by_celex = client.get(f"{LAWS}/{row[1]}")
        assert by_id.status_code == 200 and by_celex.status_code == 200
        assert by_id.json()["id"] == by_celex.json()["id"] == row[0]

    def test_an_unknown_key_still_404s(self, client):
        assert client.get(f"{LAWS}/99999999").status_code == 404
        assert client.get(f"{LAWS}/32999R9999").status_code == 404


class TestTheKeyIsUnambiguous:
    def test_no_celex_is_purely_numeric(self, db):
        """What makes a bare integer safe to read as a row id. If this ever fails the
        route must stop guessing and take an explicit prefix instead."""
        n = db.execute(text(
            "SELECT count(*) FROM eu_laws WHERE celex ~ '^[0-9]+$'")).scalar()
        assert n == 0, f"{n} CELEX are all digits, so a path segment is ambiguous"


class TestDetailCarriesItsOwnSelf:
    def test_a_detail_response_fills_self(self, client, db):
        """A schema that declares `self` and always returns null is a broken promise."""
        rid = db.execute(text(
            "SELECT id FROM eu_laws WHERE celex IS NOT NULL ORDER BY id LIMIT 1")).scalar()
        r = client.get(f"{LAWS}/{rid}")
        assert r.status_code == 200
        got = r.json().get("self")
        assert got and got.endswith(f"{LAWS}/{rid}"), f"self was {got!r}"

    def test_an_orphan_detail_fills_self_too(self, client, db):
        rid = db.execute(text(
            "SELECT id FROM eu_laws WHERE celex IS NULL ORDER BY id LIMIT 1")).scalar()
        if rid is None:
            pytest.skip("no orphan rows")
        r = client.get(f"{LAWS}/{rid}")
        assert r.status_code == 200 and r.json().get("self")


class TestItIsDocumented:
    def test_self_is_in_the_law_schema(self):
        from api.v1.laws import LawItem
        assert "self" in LawItem.model_fields, (
            "GovClipping asked for `self` to be documented and told whether it is stable")
