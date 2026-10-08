"""D3: `/api/v2/parliament/resolutions` had 72 rows with no dates at all.

The defect (measured 27 Aug 2026): `adoption_date` was NULL on every one of the
72 rows, so date filtering could not work and the corpus was undatable.

Working it turned up a refinement worth keeping. "NULL on every row" is not one
fact but two:

  * 34 rows were genuinely MISSING a date. They are recoverable with no new
    fetching at all -- from `texts_adopted.adoption_date`, and from the "Decision
    by Parliament" event on the OEIL page Brubru already stores.
  * ~37 are NULL CORRECTLY. Their procedures are still TABLED or
    CLOSE_TO_ADOPTION, so no adoption date exists yet.

A fix that filled all 72 would have invented dates for resolutions the Parliament
has not adopted. So the endpoint states which is which, and a null now means NOT
YET ADOPTED rather than "unknown".
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.v1._deps import api_user_with_rate_limit
from main import app
from models.user import User

# Reads production data: runs locally, never in CI (6 Oct 2026).
pytestmark = pytest.mark.live


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
# 1. Dates exist now
# ---------------------------------------------------------------------------

def test_resolutions_are_no_longer_entirely_undated(db):
    n, dated = db.execute(text(
        "SELECT count(*), count(adoption_date) FROM ep_resolutions")).fetchone()
    assert dated > 0, "every resolution is still undated; date filtering cannot work"
    assert dated >= 30, f"only {dated} of {n} dated; the backfill under-ran"


def test_date_filtering_actually_narrows_the_result(client):
    """The user-visible consequence. With every date NULL this returned nothing
    for any window, which is indistinguishable from an empty corpus."""
    all_ = client.get("/api/v1/resolutions?limit=1").json()["total"]
    filtered = client.get(
        "/api/v1/resolutions?published_from=2026-01-01&limit=1").json()["total"]
    assert filtered > 0, "a date-filtered query still returns nothing"
    assert filtered < all_, "the date filter does not narrow anything"


def test_dates_agree_with_the_other_ep_surface(db):
    """Two EP surfaces must not quietly contradict each other about when the
    Parliament adopted a text."""
    bad = db.execute(text("""
        SELECT count(*) FROM ep_resolutions r
        JOIN texts_adopted t ON t.procedure_ref = r.procedure_ref
        WHERE r.adoption_date IS NOT NULL AND t.adoption_date IS NOT NULL
          AND r.adoption_date <> t.adoption_date::date
    """)).scalar()
    assert bad == 0, f"{bad} resolution(s) disagree with texts_adopted on the date"


# ---------------------------------------------------------------------------
# 2. The refinement: a NULL that is CORRECT
# ---------------------------------------------------------------------------

def test_undated_resolutions_are_genuinely_unadopted(db):
    """No date was invented. Every remaining NULL is either PENDING or CLOSED
    WITHOUT A RESOLUTION, and `status` says which.

    Until 8 Oct 2026 all 35 undated rows were declared "still tabled or close to
    adoption"; 25 were RSP debates or objections that OEIL records as completed
    with no text adopted. This test failed then, but runs only locally."""
    rows = db.execute(text("""
        SELECT r.procedure_ref, r.status, c.current_status::text cs,
               EXISTS (SELECT 1 FROM texts_adopted t WHERE t.procedure_ref = r.procedure_ref
                         AND t.ta_reference ~ '^P[0-9]+_TA') has_text
        FROM ep_resolutions r
        LEFT JOIN legislative_carriages c ON c.oeil_procedure_ref = r.procedure_ref
        WHERE r.adoption_date IS NULL
    """)).fetchall()
    if not rows:
        pytest.skip("no undated resolutions left")
    wrong = [
        (r.procedure_ref, r.status, r.cs) for r in rows
        if r.has_text
        or r.status not in ("pending", "closed_without_resolution")
        or (r.status == "pending") != ((r.cs or "").upper() != "COMPLETED")
    ]
    assert not wrong, f"undated rows with the wrong status: {wrong[:5]}"


def test_every_resolution_has_a_status(db):
    n = db.execute(text("SELECT count(*) FROM ep_resolutions WHERE status IS NULL")).scalar()
    assert n == 0, f"{n} resolution(s) have no status: run scripts/backfill_resolution_dates.py --apply"


@pytest.mark.parametrize("path", ["/api/v1/resolutions", "/api/v2/parliament/resolutions"])
def test_the_status_filter_matches_the_table(client, db, path):
    real = dict(db.execute(text(
        "SELECT status, count(*) FROM ep_resolutions GROUP BY 1")).fetchall())
    for st in ("adopted", "pending", "closed_without_resolution"):
        body = client.get(path, params={"status": st, "limit": 100}).json()
        assert body["total"] == real.get(st, 0), f"{path} status={st}: {body['total']} vs {real.get(st)}"
        assert all(i["status"] == st for i in body["data"]), f"{path} status={st} leaks other rows"
    assert client.get(path, params={"status": "nonsense"}).status_code == 422


def test_the_note_names_both_kinds_of_undated_row(client, db):
    note = client.get("/api/v1/resolutions?limit=1").json()["coverage_note"]
    real = dict(db.execute(text(
        "SELECT status, count(*) FROM ep_resolutions GROUP BY 1")).fetchall())
    assert f"{real.get('pending', 0)} are `pending`" in note, note
    assert f"{real.get('closed_without_resolution', 0)} are `closed_without_resolution`" in note, note
    assert "still tabled or close to adoption" not in note, "the old, false explanation is back"


def test_no_key_event_is_dated_with_brubrus_own_write_time(client):
    """key_events once held a synthetic "tracked" event dated with updated_at,
    which reads as something the Parliament did that day."""
    items = client.get("/api/v1/resolutions", params={
        "status": "closed_without_resolution", "limit": 100}).json()["data"]
    assert items, "no closed rows to check"
    tracked = [i["procedure_ref"] for i in items
               if any(e.get("event_type") == "tracked" for e in i["key_events"])]
    assert not tracked, f"synthetic 'tracked' events still served: {tracked[:3]}"
    with_end = [i for i in items
                if any(e.get("event_type") == "end_of_procedure_in_parliament" for e in i["key_events"])]
    assert len(with_end) >= len(items) - 1, (
        f"only {len(with_end)}/{len(items)} closed rows carry OEIL's 'End of procedure' event")


@pytest.mark.parametrize("path", [
    "/api/v1/resolutions?limit=1",
    "/api/v2/parliament/resolutions?limit=1",
])
def test_the_response_explains_what_a_null_date_means(client, path):
    """Without this, a caller reads a null adoption date as missing data and
    either discards the row or, worse, treats the resolution as never adopted."""
    body = client.get(path).json()
    note = (body.get("coverage_note") or "").lower()
    assert note, f"{path}: no coverage_note"
    assert "not yet adopted" in note or "not been adopted" in note, (
        f"{path}: coverage_note does not explain the null semantics: {note!r}"
    )


@pytest.mark.parametrize("path", [
    "/api/v1/resolutions?limit=1",
    "/api/v2/parliament/resolutions?limit=1",
])
def test_both_ep_resolution_surfaces_declare_coverage(client, path):
    body = client.get(path).json()
    assert body.get("coverage_from"), f"{path}: no coverage_from"
    assert body.get("coverage_to"), f"{path}: no coverage_to"


def test_coverage_counts_are_computed_not_hardcoded(client, db):
    """The note quotes "N of M". Both must come from the table, or they rot as
    the corpus grows."""
    import re
    note = client.get("/api/v1/resolutions?limit=1").json()["coverage_note"]
    m = re.search(r"(\d+) of (\d+)", note)
    assert m, f"coverage_note does not state the counts: {note!r}"
    dated, total = int(m.group(1)), int(m.group(2))
    real = db.execute(text(
        "SELECT count(adoption_date), count(*) FROM ep_resolutions")).fetchone()
    assert (dated, total) == (real[0], real[1]), (
        f"note claims {dated}/{total}, table holds {real[0]}/{real[1]}"
    )


# ---------------------------------------------------------------------------
# 3. Roles reused from D4 rather than left half-empty
# ---------------------------------------------------------------------------

def test_rapporteurs_were_filled_from_the_parsed_carriages(db):
    """D4 recovered rapporteur names for 331 carriages; the resolutions surface
    should not stay blank when the same procedure already has the answer."""
    n = db.execute(text(
        "SELECT count(rapporteur) FROM ep_resolutions")).scalar()
    assert n >= 16, f"only {n} resolutions carry a rapporteur"


# ---------------------------------------------------------------------------
# 4. The CORPUS, not just the dates
# ---------------------------------------------------------------------------

def test_the_resolution_corpus_was_backfilled_not_just_dated(db):
    """D3 said "72 rows with NULL dates". Fixing the dates answered half of it.

    The other half: 72 rows was never the corpus. Once `texts_adopted` reached
    703 rows, 157 resolution-typed texts had no row here at all. A surface can be
    perfectly consistent and still be missing most of its subject.
    """
    n = db.execute(text("SELECT count(*) FROM ep_resolutions")).scalar()
    assert n > 100, f"ep_resolutions holds only {n} rows; the corpus backfill has not run"


def test_no_own_initiative_or_topical_resolution_is_missing(db):
    """Every INI / RSP / INL adopted text must have a row here.

    That is this table's declared taxonomy, so a gap in it is a real gap --
    unlike COD/NLE/CNS, which are a different instrument.
    """
    missing = db.execute(text(r"""
        SELECT count(*) FROM texts_adopted t
        WHERE t.text_type::text IN ('resolution','legislative_resolution')
          AND t.procedure_ref IS NOT NULL
          AND substring(t.procedure_ref from '\(([A-Z]+)\)') IN ('INI','RSP','INL')
          AND NOT EXISTS (SELECT 1 FROM ep_resolutions r
                          WHERE r.procedure_ref = t.procedure_ref)
    """)).scalar()
    assert missing == 0, (
        f"{missing} INI/RSP/INL adopted text(s) have no ep_resolutions row -- run "
        "scripts/backfill_ep_resolutions_corpus.py --apply"
    )


def test_the_declared_type_matches_the_procedure_reference(db):
    """`resolution_type` is derived from the procedure suffix, so a mismatch means
    a row was typed by guesswork rather than from its own reference."""
    bad = db.execute(text(r"""
        SELECT count(*) FROM ep_resolutions
        WHERE substring(procedure_ref from '\(([A-Z]+)\)') IS NOT NULL
          AND resolution_type::text <> substring(procedure_ref from '\(([A-Z]+)\)')
    """)).scalar()
    assert bad == 0, f"{bad} row(s) whose resolution_type contradicts their procedure_ref"


def test_vote_tallies_are_internally_consistent(db):
    """A total that is not the sum of its parts is a fabricated tally."""
    bad = db.execute(text(
        "SELECT count(*) FROM ep_resolutions WHERE vote_total IS NOT NULL "
        "AND vote_total <> vote_for + vote_against + vote_abstention")).scalar()
    assert bad == 0, f"{bad} resolution(s) have a vote_total that does not add up"


def test_the_endpoint_declares_what_it_does_not_cover(client):
    """Legislative-procedure texts are absent BY SCOPE. Without saying so, a
    caller reads their absence as the Parliament not having acted."""
    note = client.get("/api/v1/resolutions?limit=1").json()["coverage_note"].lower()
    assert "texts-adopted" in note or "texts_adopted" in note, (
        "coverage_note does not point at where legislative texts actually live"
    )


def test_resolutions_serve_their_own_adopted_text_not_the_procedure_page(client, db):
    """`body_txt` should be the resolution the Parliament adopted.

    This surface used to serve the OEIL PROCEDURE PAGE as the body -- real
    content, but a description of the file rather than its text. Now that
    texts_adopted holds 703/703 bodies, the actual text takes precedence and OEIL
    is the fallback for procedures with no adopted text yet.
    """
    items = []
    for page in (1, 2):
        items += client.get(f"/api/v1/resolutions?limit=100&page={page}").json().get("data") or []
    assert items, "no resolutions returned"
    procedure_page = sum(1 for i in items
                         if (i.get("body_txt") or "").startswith("Basic information"))
    real = len(items) - procedure_page
    assert real > procedure_page, (
        f"only {real} of {len(items)} resolutions serve their own text; "
        f"{procedure_page} still serve the OEIL procedure page"
    )


def test_a_committee_report_is_never_served_as_the_adopted_text(client, db):
    """texts_adopted also holds committee REPORTS (`A10/YYYY/NNNN`) under the same
    procedure_ref as the adopted text. Until 8 Oct 2026 whichever row came last
    won, so the draft report reached clients as the resolution for
    2025/2039(INI) and 2025/2210(INI). Checks every procedure that has a report."""
    refs = [r[0] for r in db.execute(text("""
        SELECT DISTINCT ta.procedure_ref FROM texts_adopted ta
        JOIN ep_resolutions r ON r.procedure_ref = ta.procedure_ref
        WHERE ta.ta_reference !~ '^P[0-9]+_TA'
    """)).fetchall()]
    assert refs, "no procedure has a report row: the check has nothing to test"
    served_report = []
    for ref in refs:
        items = client.get("/api/v1/resolutions", params={"procedure_ref": ref}).json().get("data") or []
        if items and (items[0].get("body_txt") or "").lstrip().upper().startswith("REPORT"):
            served_report.append(ref)
    assert not served_report, f"committee report served as the adopted text: {served_report}"


def test_no_resolution_points_at_a_sittings_table_of_contents(client, db):
    """`text_url` / `public_url` must be the resolution's own page. The writers
    copied texts_adopted.source_url, which is where the scraper FOUND the text:
    the sitting's table of contents (219 of 353 rows until 8 Oct 2026)."""
    n = db.execute(text("SELECT count(*) FROM ep_resolutions WHERE text_url ~ '-TOC_'")).scalar()
    assert n == 0, f"{n} resolution(s) store a table-of-contents page as text_url"
    items = client.get("/api/v1/resolutions", params={"status": "adopted", "limit": 100}).json()["data"]
    toc = [i["procedure_ref"] for i in items if "-TOC_" in (i.get("public_url") or "")]
    assert not toc, f"public_url is a table of contents: {toc[:3]}"


def test_no_summary_is_a_committee_report(db):
    """The summary rule joined committee REPORTS too (2025/2210(INI), 2026/2023(INL))."""
    bad = [r[0] for r in db.execute(text("""
        SELECT r.procedure_ref FROM ep_resolutions r
        WHERE r.summary ~* '^[[:space:]]*REPORT'
          AND EXISTS (SELECT 1 FROM texts_adopted a WHERE a.procedure_ref = r.procedure_ref
                        AND a.ta_reference !~ '^P[0-9]+_TA')
    """)).fetchall()]
    assert not bad, f"summary taken from a committee report: {bad}"


def test_an_uncounted_vote_is_null_never_zero(client, db):
    """The vote columns defaulted to 0: 72 rows said "0 for, 0 against" for
    resolutions nobody had counted, 35 of them never voted at all (8 Oct 2026)."""
    zeros = db.execute(text("SELECT count(*) FROM ep_resolutions WHERE vote_total = 0")).scalar()
    assert zeros == 0, f"{zeros} resolution(s) claim a 0-vote tally"
    items = client.get("/api/v1/resolutions", params={"status": "pending", "limit": 5}).json()["data"]
    assert items and all(i["vote_for"] is None and i["vote_total"] is None for i in items), (
        "an uncounted vote is not served as null")


def test_every_tally_is_the_final_plenary_vote(db):
    """ep_roll_call_votes also holds the committee's final vote and votes on single
    amendments under the same ta_reference; 21 of 88 tallies were one of those
    (P10_TA(2026)0247 read "rejected 41-137" for a text plenary adopted 501-61)."""
    import importlib.util, pathlib
    path = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "enrich_ep_texts_and_resolutions.py"
    spec = importlib.util.spec_from_file_location("_enrich", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    wrong = [r[0] for r in db.execute(text("""
        SELECT r.procedure_ref FROM ep_resolutions r
        WHERE r.vote_total IS NOT NULL AND NOT EXISTS (
            SELECT 1 FROM texts_adopted t JOIN ep_roll_call_votes v ON v.ta_reference = t.ta_reference
            WHERE t.procedure_ref = r.procedure_ref AND t.ta_reference ~ '^P[0-9]+_TA'
              AND v.level = 'plenary' AND v.subject ~* :fv
              AND v.votes_for = r.vote_for AND v.votes_against = r.vote_against
              AND v.votes_abstention = r.vote_abstention)
    """), {"fv": mod._FINAL_VOTE}).fetchall()]
    assert not wrong, f"tally is not the final plenary vote: {wrong[:5]}"


def test_the_followup_flag_is_read_from_ep_open_data(client, db):
    """has_commission_followup was never computed: the column default made all 353
    rows read "no follow-up" while 143 had one in ep_external_documents (8 Oct 2026).
    Same match as the writer and the API (one definition)."""
    from services.matching.resolution_followups import FOLLOWUP_MATCH
    wrong = db.execute(text("""
        SELECT count(*) FROM ep_resolutions r
        JOIN texts_adopted t ON t.procedure_ref = r.procedure_ref AND t.ta_reference ~ '^P[0-9]+_TA'
        WHERE r.followup_checked_at IS NOT NULL
          AND r.has_commission_followup IS DISTINCT FROM EXISTS (
              SELECT 1 FROM ep_external_documents f WHERE """ + FOLLOWUP_MATCH + """)
    """)).scalar()
    assert wrong == 0, f"{wrong} follow-up flag(s) disagree with ep_external_documents"
    real = db.execute(text(
        "SELECT count(*) FROM ep_resolutions WHERE has_commission_followup AND followup_checked_at IS NOT NULL"
    )).scalar()
    body = client.get("/api/v1/resolutions", params={"has_commission_followup": "true", "limit": 100}).json()
    assert body["total"] == real and real > 0
    item = body["data"][0]
    events = [e for e in item["key_events"] if e["event_type"] == "commission_followup"]
    assert events and all(e["date"] for e in events), f"{item['procedure_ref']}: follow-up not dated in key_events"


def test_no_followup_predates_the_text_it_answers(client):
    """EP's answers_to metadata is wrong for ~1 in 10 follow-ups: it attached the
    drones follow-up (26 May 2026) to the 28th-regime resolution adopted 9 July 2026.
    Matching on the document's own reference line fixed it; a follow-up dated before
    the adoption is the tell."""
    early = []
    for page in (1, 2, 3, 4):
        for i in client.get("/api/v1/resolutions", params={"limit": 100, "page": page}).json()["data"]:
            for e in i["key_events"]:
                if e["event_type"] == "commission_followup" and i["adoption_date"] and e["date"] < i["adoption_date"]:
                    early.append((i["procedure_ref"], i["adoption_date"], e["date"]))
    assert not early, f"follow-up dated before the adoption it answers: {early[:3]}"
    flags = {ref: client.get(f"/api/v1/resolutions/{ref}").json()["has_commission_followup"]
             for ref in ("2025/2088(INI)", "2025/2211(INI)")}
    assert flags == {"2025/2088(INI)": True, "2025/2211(INI)": False}, flags


@pytest.mark.parametrize("base", ["/api/v1/resolutions", "/api/v2/parliament/resolutions"])
def test_a_resolution_reads_the_same_from_the_list_and_on_its_own(client, base):
    """Until 8 Oct 2026 the detail route served the OEIL procedure page as the
    body (~2k chars) while the list served the adopted text (~19k)."""
    listed = client.get(base, params={"limit": 30}).json()["data"]
    assert listed
    differ = []
    for item in listed:
        one = client.get(f"{base}/{item['id']}").json()
        # `self` is added to LISTED items only (core/self_links.py): the detail
        # response is the item the link points at.
        diff = sorted(k for k in item if k != "self" and item[k] != one.get(k))
        if diff:
            differ.append((item["procedure_ref"], diff))
    assert not differ, f"list and detail disagree: {differ[:3]}"


def test_unknown_classification_and_followup_are_null_not_empty(client):
    items = client.get("/api/v1/resolutions", params={"limit": 100}).json()["data"]
    assert all(i["eurovoc_codes"] is None or i["eurovoc_codes"] for i in items), (
        "eurovoc_codes served as [] (reads as 'no subject') instead of null")


def test_no_resolution_body_is_navigation_chrome(client):
    """doceo hides a language picker in `.ep_hidden`; 47 stored bodies once OPENED
    with "Choisissez la langue de votre document" -- navigation saved as the text
    of an adopted act, which passes every length and non-null check."""
    items = client.get("/api/v1/resolutions?limit=100").json().get("data") or []
    bad = [i["procedure_ref"] for i in items
           if "Choisissez la langue" in (i.get("body_txt") or "")[:400]]
    assert not bad, f"{len(bad)} resolution body/bodies are the language picker: {bad[:3]}"


def test_every_resolution_has_both_body_datapoints(client):
    items = []
    for page in (1, 2):
        items += client.get(f"/api/v1/resolutions?limit=100&page={page}").json().get("data") or []
    missing_txt = [i["procedure_ref"] for i in items if not (i.get("body_txt") or "").strip()]
    missing_html = [i["procedure_ref"] for i in items if not (i.get("body_html") or "").strip()]
    assert not missing_txt, f"{len(missing_txt)} without body_txt"
    assert not missing_html, f"{len(missing_html)} without body_html"
