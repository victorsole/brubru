"""D2: adopted texts must reach back past 20 January 2026, and must say how far.

The defect (measured 27 Aug 2026): `texts_adopted` held 251 rows opening on
20 January 2026. The single most important EP text on protecting minors online --
the resolution adopted **26 November 2025**, 483 votes to 92 -- fell before the
corpus began, so every search for it returned a clean zero, indistinguishable
from "no such text exists".

The root cause was not "the backfill was never run". `get_plenary_dates` returned
**0 dates** because europarl.europa.eu answers a plain fetch with an HTTP 202 and
a ~2.4KB JS shell: nothing raised, nothing was logged, and the scraper reported no
plenary dates as though that were a fact about the Parliament.

Two halves are tested, and the second matters as much as the first:
  1. the corpus reaches the November 2025 session, and
  2. every response DECLARES its own bounds, so a zero can be read honestly.
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
        email="test@example.com", role="admin"
    )
    yield TestClient(app)
    app.dependency_overrides.pop(api_user_with_rate_limit, None)


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


# ---------------------------------------------------------------------------
# 1. The corpus
# ---------------------------------------------------------------------------

def test_the_corpus_reaches_before_2026(db):
    """20 January 2026 was the floor. Anything earlier was unreachable."""
    earliest = db.execute(
        text("SELECT min(adoption_date)::date FROM texts_adopted")).scalar()
    assert earliest is not None, "texts_adopted is empty"
    assert earliest.year < 2026 or earliest.month < 1 or earliest < __import__(
        "datetime").date(2026, 1, 20), (
        f"corpus still opens on {earliest}; the pre-2026 term is still missing"
    )


def test_the_november_2025_minors_resolution_is_present(db):
    """The acceptance case: the text the API could not see.

    Adopted 26 November 2025, rapporteur Christel Schaldemose, calling for an EU
    digital minimum age of 16.
    """
    row = db.execute(text(
        "SELECT ta_reference, adoption_date::date d, title FROM texts_adopted "
        "WHERE title ILIKE '%minors online%' AND adoption_date < '2026-01-01' "
        "ORDER BY adoption_date DESC LIMIT 1")).fetchone()
    assert row is not None, (
        "the 26 Nov 2025 resolution on protecting minors online is still absent"
    )
    assert row.d.year == 2025


def test_it_is_reachable_through_the_api_not_just_the_table(client):
    """A row nobody can query is not coverage."""
    body = client.get("/api/texts-adopted/items?search=minors&limit=10").json()
    assert body["total"] > 0, "?search=minors returns nothing from the endpoint"
    refs = [i.get("ta_reference") for i in body.get("items", [])]
    assert any(r and "2025" in r for r in refs), (
        f"no 2025 text among the matches: {refs}"
    )


# ---------------------------------------------------------------------------
# 2. Honest bounds — the half that converts a false negative into a true one
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,kind", [
    ("/api/texts-adopted/items?limit=1", "items"),
    ("/api/v1/texts-adopted?limit=1", "v1"),
])
def test_every_list_response_declares_its_coverage(client, path, kind):
    body = client.get(path).json()
    assert body.get("coverage_from"), f"{kind}: no coverage_from"
    assert body.get("coverage_to"), f"{kind}: no coverage_to"
    assert body.get("coverage_note"), f"{kind}: no coverage_note"


def test_coverage_note_warns_that_the_floor_is_not_the_term_start(client):
    """The whole point: `coverage_from` is what we HOLD, not when the EP began.

    Without that sentence a caller reads the floor as the start of the
    parliamentary term and treats an empty earlier window as real absence.
    """
    note = client.get("/api/texts-adopted/items?limit=1").json()["coverage_note"].lower()
    assert "not the bounds" in note or "not the start" in note or "does not reach" in note, (
        f"coverage_note does not distinguish held-corpus from term: {note!r}"
    )


def test_coverage_is_computed_from_the_data_not_hardcoded(client, db):
    """A hardcoded floor rots the moment the backfill extends."""
    from datetime import date
    api_lo = date.fromisoformat(
        client.get("/api/texts-adopted/items?limit=1").json()["coverage_from"])
    db_lo = db.execute(text("SELECT min(adoption_date)::date FROM texts_adopted")).scalar()
    assert api_lo == db_lo, f"declared {api_lo} but the corpus actually starts {db_lo}"


# ---------------------------------------------------------------------------
# 3. The instrument that produced the false zero
# ---------------------------------------------------------------------------

def test_the_scraper_refuses_to_read_a_js_shell_as_an_empty_page():
    """europarl answers a plain fetch with ~2.4KB of JS shell and HTTP 202.

    The scraper must treat an implausibly small body as a FETCH FAILURE and go
    to a browser, never return it as a page with no links -- which is exactly how
    "0 plenary dates" became a statement about the Parliament.
    """
    from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper
    assert TextsAdoptedScraper._MIN_PLAUSIBLE_BYTES >= 5000
    src = __import__("inspect").getsource(TextsAdoptedScraper._fetch)
    assert "waf_browser_fetcher" in src, "no browser fallback on the fetch path"
    assert "raise RuntimeError" in src, (
        "a failed fetch must raise, not return an empty page that reads as no data"
    )


@pytest.mark.asyncio
async def test_plenary_date_discovery_actually_returns_dates():
    """It returned 0 for months. A live check, because this is the exact failure."""
    from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper
    dates = await TextsAdoptedScraper().get_plenary_dates(10)
    assert len(dates) > 0, (
        "get_plenary_dates returned nothing again -- the index fetch is broken, "
        "which is not the same as the Parliament having no sittings"
    )


def test_explicit_date_backfill_is_available():
    """The index lists only the CURRENT year, so earlier sittings are reachable
    only by explicit date. Without this path the corpus can never be extended."""
    import inspect
    from services.scrapers.texts_adopted_sync_service import TextsAdoptedSyncService
    assert hasattr(TextsAdoptedSyncService, "sync_dates")
    src = inspect.getsource(TextsAdoptedSyncService.sync_dates)
    assert "dates_with_no_texts" in src, (
        "dates that yielded nothing are not reported, so a failed fetch and an "
        "empty sitting look identical"
    )
