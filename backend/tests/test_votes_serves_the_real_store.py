"""/parliament/votes must serve the roll-call store, and never the seeded 15.

Two pipelines were built for votes and the reader was never moved. The v1 endpoint
shipped 13 May 2026 reading `ep_votes`; migration 098 on 4 June created
`ep_roll_call_votes` + `ep_roll_call_records` from doceo and said in writing "there is a
dormant HowTheyVote-shaped ep_votes table ... we deliberately do NOT touch it". That was
decided from the writer's side; nobody asked who was READING ep_votes.

Worse, its 15 rows are a hardcoded VOTES_SEED in scripts/ingest_ep_votes.py, written
because the real HowTheyVote importer is blocked on an ep_political_groups.short_label
varchar(20) collision. Its docstring says "Each vote is real (P10_TA references match
Texts Adopted in our DB)" -- but P10_TA(2026)0104 is "Global Gateway", not the "AI Act
delegated regulation" the seed calls it. The reference was checked for EXISTENCE, not
IDENTITY, so invented titles and invented tallies were pinned to real unrelated
references and served to a paying client as the EP vote feed.

The contract is kept deliberately: the field NAMES a client already polls stay, and the
roll-call store is mapped onto them. Nothing breaks for GovClipping; they go from 15 rows
to 465 with committee votes included.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v1._deps import api_user_with_rate_limit
from main import app
from models.user import User

VOTES = "/api/v2/parliament/votes"
SEED_TITLES = [
    "AI Act delegated regulation on high-risk classification",
    "Critical Raw Materials Act - implementing regulation",
    "Digital Fairness Act - first reading",
]


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


@pytest.fixture(autouse=True)
def _clean(db):
    yield
    db.rollback()


class TestItServesTheRealStore:
    @pytest.mark.live
    def test_the_total_is_the_roll_call_store_not_fifteen(self, client, db):
        """EP levels only: the table also holds Council QMV votes."""
        real = db.execute(text(
            "SELECT count(*) FROM ep_roll_call_votes "
            "WHERE level IN ('plenary','committee')")).scalar()
        got = client.get(f"{VOTES}?limit=1").json()["total"]
        assert got == real, f"served {got}, EP roll-call store holds {real}"
        assert got > 15

    @pytest.mark.live
    def test_no_council_vote_is_served_as_a_parliament_vote(self, client, db):
        council = db.execute(text(
            "SELECT count(*) FROM ep_roll_call_votes WHERE level = 'council'")).scalar()
        if not council:
            pytest.skip("no council votes stored")
        total = client.get(f"{VOTES}?limit=1").json()["total"]
        allrows = db.execute(text("SELECT count(*) FROM ep_roll_call_votes")).scalar()
        assert total == allrows - council, (
            "Council QMV votes are being attributed to the Parliament")

    @pytest.mark.live
    def test_every_served_vote_has_a_date(self, client, db):
        """`timestamp` is required by the contract, so a dateless row would 500 the
        endpoint rather than be skipped."""
        n = db.execute(text(
            "SELECT count(*) FROM ep_roll_call_votes WHERE level IN ('plenary','committee') "
            "AND vote_date IS NULL AND sitting_date IS NULL")).scalar()
        assert n == 0, f"{n} EP vote(s) carry no date at all"

    @pytest.mark.live
    def test_committee_votes_are_served_too(self, client, db):
        """The old store was plenary tallies only. The doceo store has both."""
        n = db.execute(text(
            "SELECT count(*) FROM ep_roll_call_votes WHERE level = 'committee'")).scalar()
        if not n:
            pytest.skip("no committee votes stored")
        got = client.get(f"{VOTES}?limit=100").json()
        assert got["total"] > 0


class TestTheFabricatedRowsAreGone:
    @pytest.mark.live
    def test_no_seeded_row_is_served(self, client):
        data = client.get(f"{VOTES}?limit=100").json().get("data") or []
        titles = " | ".join((i.get("display_title") or "") for i in data)
        for t in SEED_TITLES:
            assert t not in titles, f"a fabricated seed row is still served: {t}"

    @pytest.mark.live
    def test_the_seed_rows_are_deleted_from_the_database(self, db):
        n = db.execute(text(
            "SELECT count(*) FROM ep_votes WHERE htv_id BETWEEN 180001 AND 180015")).scalar()
        assert n == 0, f"{n} fabricated rows still in ep_votes"


class TestTheContractDidNotBreak:
    @pytest.mark.live
    def test_every_field_the_client_polls_is_still_present(self, client):
        data = client.get(f"{VOTES}?limit=1").json().get("data") or []
        assert data, "no votes served"
        item = data[0]
        for f in ("id", "timestamp", "display_title", "procedure_reference", "result",
                  "count_for", "count_against", "count_abstention",
                  "public_url", "body_txt", "body_html", "document_date", "creation_date"):
            assert f in item, f"the contract lost `{f}`"

    @pytest.mark.live
    def test_the_tallies_are_integers_not_null(self, client):
        item = (client.get(f"{VOTES}?limit=1").json().get("data") or [{}])[0]
        for f in ("count_for", "count_against", "count_abstention"):
            assert isinstance(item.get(f), int), f"{f} is {item.get(f)!r}"

    @pytest.mark.live
    def test_public_url_points_at_the_real_source(self, client):
        item = (client.get(f"{VOTES}?limit=1").json().get("data") or [{}])[0]
        url = item.get("public_url") or ""
        assert url and "howtheyvote.eu" not in url, (
            f"public_url still points at the dormant HowTheyVote path: {url!r}")


class TestIncrementalSyncWorks:
    @pytest.mark.live
    def test_updated_from_filters_instead_of_annihilating(self, client, db):
        """GovClipping's complaint: ?updated_from= returned 0 for every date, because
        not one row had updated_at."""
        n = db.execute(text(
            "SELECT count(*) FROM ep_roll_call_votes WHERE updated_at IS NOT NULL")).scalar()
        assert n > 0, "no roll-call row carries updated_at"
        total = client.get(f"{VOTES}?limit=1").json()["total"]
        old = client.get(f"{VOTES}?limit=1&updated_from=2000-01-01T00:00:00Z").json()["total"]
        assert old == total, f"a 2000 lower bound returned {old} of {total}"


class TestAJobThatStoresNothingFails:
    def test_the_sync_reports_a_status(self):
        """440 successful runs while the served table stood still. A job that can store
        nothing must be able to say so."""
        import inspect
        from scripts import sync_ep_votes
        src = inspect.getsource(sync_ep_votes)
        assert "sys.exit" in src or "return 1" in src, (
            "sync_ep_votes never returns a failing status, so cron cannot tell")


class TestTheItemRoutesFollowTheList:
    """The list now hands out roll-call ids. If detail and records still read the old
    table, every id the list publishes 404s -- the exact identity break we spent this
    week removing, introduced by the fix for it."""

    @pytest.mark.live
    def test_every_id_the_list_returns_resolves(self, client):
        data = client.get(f"{VOTES}?limit=5").json().get("data") or []
        assert data, "no votes served"
        for item in data:
            r = client.get(f"{VOTES}/{item['id']}")
            assert r.status_code == 200, f"{item['id']} 404s on the detail route"
            assert r.json()["id"] == item["id"]

    @pytest.mark.live
    def test_records_serve_the_per_mep_breakdown(self, client, db):
        vid = db.execute(text(
            "SELECT vote_id::text FROM ep_roll_call_records LIMIT 1")).scalar()
        if not vid:
            pytest.skip("no roll-call records")
        r = client.get(f"{VOTES}/{vid}/records?limit=5")
        assert r.status_code == 200, r.text[:200]
        data = r.json().get("data") or []
        assert data, "records route returned nothing for a vote that has records"
        for row in data:
            assert row["position"] in ("FOR", "AGAINST", "ABSTENTION"), row["position"]
            assert row["member_id"]

    @pytest.mark.live
    def test_position_filter_uses_the_published_vocabulary(self, client, db):
        vid = db.execute(text(
            "SELECT vote_id::text FROM ep_roll_call_records LIMIT 1")).scalar()
        if not vid:
            pytest.skip("no roll-call records")
        ok = client.get(f"{VOTES}/{vid}/records?position=FOR&limit=3")
        assert ok.status_code == 200
        assert all(x["position"] == "FOR" for x in (ok.json().get("data") or []))
        bad = client.get(f"{VOTES}/{vid}/records?position=NOPE")
        assert bad.status_code == 422, "an unservable value must say so, not return all"
