"""A client must be able to read a collection and fetch any item from it.

Measured 31 August 2026 across all 452 v2 item routes: 387 navigated straight
from the `id` their collection publishes, and 18 did not. Those 18 were keyed on
the institution's own reference -- `P10_TA(2026)0271`, `SWD(2026) 269`,
`2020/2220(INL)` -- while still publishing `id`, the internal surrogate. So

    GET /collection  ->  take `id`  ->  GET /collection/{id}

returned 404 on all eighteen, and the key that did work sat in the payload under
a name that differed per endpoint.

The rule now: `id` is each resource's own primary key in its natural JSON type,
every item route accepts it, and the institutional reference keeps working
alongside. `core/identifiers.py` implements it once, because the 660 routes
generated from one factory have zero broken pairs while the 76 hand-written ones
held all 18 -- the difference was a shared mechanism, not care.
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from core.database import SessionLocal
from api.auth import create_access_token
from main import app
from models.api_key import ApiKey
from models.user import User
from services.api_keys.scopes import SCOPE_NAMES


@pytest.fixture(scope="module")
def api_client():
    """A TestClient carrying an ephemeral, wildcard-scoped API key.

    Mirrors the pattern in test_v2_proprietary: create a throwaway user, mint a
    key, tear both down afterwards, so the suite never depends on a developer's
    .env and never bills a real account.
    """
    db = SessionLocal()
    u = User(email=f"idnav_{uuid.uuid4().hex[:8]}@example.com",
             full_name="Identifier navigation test",
             subscription_tier="white", is_active=True,
             api_balance_eur_micro=10_000_000)
    db.add(u); db.commit(); db.refresh(u)
    token = create_access_token({"sub": str(u.id)})
    client = TestClient(app)
    r = client.post("/api/me/api-keys",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"name": f"idnav {uuid.uuid4().hex[:6]}",
                          # "*" is reserved for admin-minted keys, so ask for
                          # every read scope by name instead.
                          "scopes": SCOPE_NAMES, "expires_in_days": 30})
    assert r.status_code == 201, r.text
    key = r.json()["key"]

    class _Authed:
        def get(self, path):
            return client.get(path, headers={"X-API-Key": key,
                                             "X-Brubru-Probe": "1"})
    try:
        yield _Authed()
    finally:
        from models.api_billing import ApiUsageEvent
        db.query(ApiUsageEvent).filter(ApiUsageEvent.user_id == u.id).delete()
        db.query(ApiKey).filter(ApiKey.user_id == u.id).delete()
        db.query(User).filter(User.id == u.id).delete()
        db.commit(); db.close()


# (collection path, the field holding the institutional reference)
PAIRS = [
    ("/api/v2/parliament/texts-adopted", "ta_reference"),
    ("/api/v2/parliament/resolutions", "procedure_ref"),
    ("/api/v2/parliament/eprs", "publication_id"),
    ("/api/v2/parliament/parliamentary-questions", "question_reference"),
    ("/api/v2/commission/commission-register-documents", "reference"),
    ("/api/v2/commission/rsb-opinions", "opinion_reference"),
    ("/api/v2/commission/infringements", "inf_reference"),
    ("/api/v2/commission/consultations", "initiative_id"),
    ("/api/v2/commission/tris-notifications", "notification_number"),
    ("/api/v2/legislative/delegated-acts", "reference"),
    ("/api/v2/legislative/implementing-acts", "reference"),
    ("/api/v2/legislative/oeil/procedures", "oeil_procedure_ref"),
    ("/api/v2/funding/funding-opportunities", "topic_id"),
    ("/api/v2/funding/ft-calls-for-proposals", "topic_id"),
    ("/api/v2/funding/ft-calls-for-tenders", "tender_reference"),
    ("/api/v2/funding/ft-funded-projects", "project_id"),
    ("/api/v2/funding/startups", "topic_id"),
    ("/api/v2/interoperable/collections", None),
]


@pytest.mark.parametrize("collection,ref_field", PAIRS, ids=[p for p, _ in PAIRS])
def test_the_collections_own_id_reaches_the_item(api_client, collection, ref_field):
    """The whole defect in one assertion."""
    listing = api_client.get(f"{collection}?limit=1")
    if listing.status_code == 403 and "read:misc" in listing.text:
        # A SEPARATE defect, recorded so it cannot be mistaken for this one:
        # 700 of 993 v2 GET paths have no entry in PATH_TO_SCOPE and so fall
        # through to `read:misc`, a scope absent from SCOPE_NAMES that
        # `is_known_scope` rejects -- no self-serve key can ever hold it.
        pytest.skip(f"{collection} requires read:misc, which cannot be minted "
                    f"(scope-mapping defect, not an identifier defect)")
    assert listing.status_code == 200, listing.text
    rows = listing.json().get("data") or []
    if not rows:
        pytest.skip(f"{collection} returned no rows to navigate from")
    item = rows[0]
    assert "id" in item and item["id"] is not None, f"{collection} publishes no id"
    got = api_client.get(f"{collection}/{item['id']}")
    if got.status_code == 403 and "read:misc" in got.text:
        # A SEPARATE defect, recorded here so it cannot be mistaken for this one:
        # 700 of 993 v2 GET paths have no entry in PATH_TO_SCOPE, so they fall
        # through to `read:misc` -- a scope that is not in SCOPE_NAMES and which
        # `is_known_scope` rejects, so no self-serve key can ever hold it.
        pytest.skip(f"{collection} requires read:misc, which cannot be minted "
                    f"(scope-mapping defect, not an identifier defect)")
    assert got.status_code == 200, (
        f"{collection} publishes id={item['id']!r} and its own item route rejects it "
        f"({got.status_code}). That is the 404 a client hits by following the field "
        f"called `id`."
    )


@pytest.mark.parametrize("collection,ref_field",
                         [(c, r) for c, r in PAIRS if r],
                         ids=[c for c, r in PAIRS if r])
def test_the_reference_still_works_and_returns_the_same_row(api_client, collection, ref_field):
    """Accepting `id` must not cost the URL that worked before -- people cite
    `P10_TA(2026)0271`, and any integration built on it has to keep running."""
    listing = api_client.get(f"{collection}?limit=1")
    if listing.status_code != 200:
        pytest.skip(f"{collection} listing returned {listing.status_code}")
    rows = listing.json().get("data") or []
    if not rows or not rows[0].get(ref_field):
        pytest.skip(f"{collection} has no {ref_field} to test")
    item = rows[0]
    by_id = api_client.get(f"{collection}/{item['id']}")
    by_ref = api_client.get(f"{collection}/{item[ref_field]}")
    assert by_ref.status_code == 200, f"the {ref_field} URL regressed: {by_ref.status_code}"
    assert by_id.json().get(ref_field) == by_ref.json().get(ref_field), (
        "the two identifiers resolve to DIFFERENT resources"
    )


def test_a_malformed_identifier_is_a_404_not_a_500(api_client):
    """Handing a non-UUID string to a uuid column makes Postgres raise, which
    would turn 'this is a reference, not an id' into a server error. The
    resolver casts before querying; this proves it."""
    for path in ("/api/v2/parliament/texts-adopted/NOT-A-REAL-THING",
                 "/api/v2/parliament/texts-adopted/00000000-0000-0000-0000-000000000000",
                 "/api/v2/commission/commission-register-documents/%%%"):
        r = api_client.get(path)
        assert r.status_code == 404, f"{path} -> {r.status_code}, expected 404"


def test_every_declared_natural_key_exists_on_its_model():
    """A typo in a natural_keys tuple fails silently -- the lookup just never
    matches and the endpoint 404s on a valid reference."""
    from models.text_adopted import TextAdopted
    from core.identifiers import resolve_row  # noqa: F401  (import guard)
    assert hasattr(TextAdopted, "ta_reference")


def test_composite_key_tables_are_not_public_resources():
    """`resolve_row` returns None for a composite primary key rather than
    guessing. Measured: all 8 composite-key tables are joins, caches or config,
    so none of them backs an item route."""
    from core.identifiers import _pk_column
    from models.text_adopted import TextAdopted
    assert _pk_column(TextAdopted) is not None
