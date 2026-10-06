"""secondary_acts: CELEX is the identity, the C-number is a label.

GovClipping found 80 CELEX values held by two rows each, and 1,137 acts with no
adoption date. Both trace to one line in scripts/ingest_regdel_acts.py:

    ON CONFLICT (reference) DO UPDATE ...

`reference` is the Commission's C(YYYY)NNNN number. It is a LABEL: the same act can
carry a different C-number in a later RegDel export, and then the upsert sees no
conflict and inserts a second row for a CELEX we already hold. The identity is the
CELEX. This is the same mistake recorded in feedback_upsert_on_the_identity_not_a_label
and it was repeated here.

The 80 pairs are two different things, and the difference decides the merge rule:

  Class A (73 pairs) -- the same act at two lifecycle stages. One row is the published
    OJ version (dated, reference = the CELEX); the other is the pre-publication draft
    (undated, reference = C(YYYY)NNNN, title still reads "(EU) .../..."). The FULL TEXT
    sits on the DRAFT row: 32024R0870 holds 120,902 characters there and zero on the
    published row. Deleting the undated row destroys the body on 32 of these 73 pairs,
    which is why the merge is field-wise and not a DELETE.

  Class B (7 pairs) -- two conflicting C-numbers for one CELEX. Three of the seven have
    a PRE-EXISTING row whose C-number year contradicts its own adoption date, while the
    newer row agrees with it (32014R0182 was adopted 17 Dec 2013 and the old row says
    C(2014)5833; the new row says C(2013)9133). A C-number is issued at College
    adoption, so its year must match. We do not guess which is right: both are kept,
    the loser's in merged_from.

The dates are NOT the same defect. The RegDel export's only date column is
"Planned adoption date" and its value is a quarter string ("Q3 2026"), so the source
cannot supply an adoption or publication date at all. 406 undated rows have a CELEX and
Cellar has their date (5 of 5 spot-checked matched their dated twin independently); the
other 731 have no CELEX because the act is adopted-but-unpublished or still draft, and
NULL is the correct value there.
"""
from __future__ import annotations

import os
import re
import pathlib

import pytest
from sqlalchemy import create_engine, text

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_SCRIPT = pathlib.Path(_REPO_ROOT) / "backend" / "scripts" / "ingest_regdel_acts.py"


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    env = pathlib.Path(_REPO_ROOT) / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                return line.split("=", 1)[1].strip()
    return ""


@pytest.fixture(scope="module")
def db():
    url = _db_url()
    if not url:
        pytest.skip("DATABASE_URL not available")
    engine = create_engine(url)
    with engine.connect() as conn:
        yield conn


# --------------------------------------------------------------------------
# The code fix: the upsert must key on the identity, never on the label.
# --------------------------------------------------------------------------

def test_regdel_upsert_keys_on_celex():
    """A row that has a CELEX must conflict on the CELEX."""
    src = _SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"ON CONFLICT\s*\(\s*celex\s*\)", src), (
        "ingest_regdel_acts.py must resolve conflicts on celex for rows that have one."
    )


def test_regdel_routes_celex_rows_away_from_the_reference_key():
    """The defect is not the string 'ON CONFLICT (reference)'. It is USING it for a
    row that has a CELEX.

    An earlier version of this test banned the string outright and failed on a correct
    fix, because the 731 acts with no CELEX legitimately still key on the C-number.
    What has to hold is the DISPATCH: celex present -> the celex statement; celex
    absent -> the reference statement.
    """
    src = _SCRIPT.read_text(encoding="utf-8")
    assert re.search(r"SQL_BY_CELEX\s+if\s+r\.get\(\s*[\"']celex[\"']\s*\)\s+else\s+SQL_BY_REFERENCE", src), (
        "the upsert must choose the CELEX statement for rows that carry a CELEX and "
        "the reference statement only for rows that do not"
    )
    by_celex = src.split("SQL_BY_CELEX = ", 1)[1].split("SQL_BY_REFERENCE = ", 1)[0]
    assert "ON CONFLICT (reference)" not in by_celex, (
        "the CELEX path must never fall back to conflicting on the C-number"
    )


def test_regdel_still_handles_rows_with_no_celex():
    """731 acts have no CELEX yet (adopted-unpublished, or draft). They still need a key.

    A CELEX-only upsert would insert a new row for the same draft act on every run.
    """
    src = _SCRIPT.read_text(encoding="utf-8")
    assert "SQL_BY_REFERENCE" in src and "ON CONFLICT (reference)" in src, (
        "the no-CELEX path must still be keyed on reference, or drafts duplicate daily"
    )


def test_regdel_never_blanks_a_value_it_already_holds():
    """An empty cell in a later export must not erase a good value.

    The old statement assigned `celex = EXCLUDED.celex` directly, so a single blank
    cell would have wiped a CELEX we already had.
    """
    src = _SCRIPT.read_text(encoding="utf-8")
    assert "COALESCE(EXCLUDED.celex, secondary_acts.celex)" in src, (
        "celex must be COALESCEd on update, never assigned from EXCLUDED directly"
    )
    assert "COALESCE(EXCLUDED.title, secondary_acts.title)" in src, (
        "title must be COALESCEd on update"
    )


def test_regdel_maps_every_status_the_register_uses():
    """RegDel uses 10 status values; mapping 6 sent 356 acts to a default of 'draft'.

    The values are counted from the live exports on 30 Sep 2026. If the register adds
    one, the ingest stores 'unknown' and says so; it must never resolve to 'draft'.
    """
    src = _SCRIPT.read_text(encoding="utf-8")
    for regdel_value in ("Published", "Adopted", "Planned", "Objected", "Cancelled",
                         "Withdrawn", "On hold", "Notified", "Scrutiny finished",
                         "Adopted (urgency procedure)"):
        assert f'"{regdel_value}"' in src, f"RegDel status {regdel_value!r} is not mapped"
    assert '_STATUS_MAP.get(key)' in src and 'status = "unknown"' in src, (
        "an unmapped status must become 'unknown' and be reported, never 'draft'"
    )
    assert '.get(str(raw_status).strip(), "draft")' not in src, (
        "the silent 'draft' default is what mislabelled 356 acts"
    )


def test_published_is_not_collapsed_into_adopted():
    """`Adopted` and `Published` are different stages and must stay different.

    The gap between them is the scrutiny window, when an objection is still possible.
    """
    src = _SCRIPT.read_text(encoding="utf-8")
    assert '"Published": "published"' in src, (
        "RegDel 'Published' must map to 'published', not 'adopted'"
    )


@pytest.mark.live
def test_status_enum_mirrors_the_database(db):
    """Every value the Python enum can produce must exist in the database enum.

    A value in one and not the other fails on the first row that uses it, which is how
    8 withdrawn acts were rejected for months.
    """
    import sys as _sys
    _sys.path.insert(0, str(pathlib.Path(_REPO_ROOT) / "backend"))
    from models.w4_entities import SecondaryActStatusEnum

    in_db = {r[0] for r in db.execute(text(
        "SELECT e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
        "WHERE t.typname = 'secondary_act_status_enum'")).fetchall()}
    in_py = {m.value for m in SecondaryActStatusEnum}
    assert in_py <= in_db, f"in Python but not in the database enum: {sorted(in_py - in_db)}"


def test_regdel_exit_code_reaches_the_scheduler():
    """A script that returns 1 but exits 0 is a failure recorded as a success."""
    src = _SCRIPT.read_text(encoding="utf-8")
    assert "sys.exit(main())" in src, (
        "__main__ must pass main()'s return value to sys.exit"
    )


def test_regdel_does_not_invent_dates():
    """RegDel's only date column is a quarter string; it must not become a date."""
    src = _SCRIPT.read_text(encoding="utf-8")
    if "Planned adoption date" in src:
        assert "adoption_date" not in src.split("Planned adoption date")[1][:400], (
            "'Planned adoption date' holds values like 'Q3 2026'. It is not an "
            "adoption date and must never be written to adoption_date."
        )


# --------------------------------------------------------------------------
# The data invariants. These are the acceptance set for the merge.
# --------------------------------------------------------------------------

@pytest.mark.live
def test_no_celex_is_held_by_two_rows(db):
    n = db.execute(text(
        "SELECT count(*) FROM (SELECT celex FROM secondary_acts "
        "WHERE celex IS NOT NULL AND celex <> '' "
        "GROUP BY celex HAVING count(*) > 1) z")).scalar()
    assert n == 0, f"{n} CELEX value(s) still held by more than one row"


@pytest.mark.live
def test_merge_conserved_every_character_of_text(db):
    """The merge moves bodies between rows; it must never drop one.

    Measured before the merge on 30 Sep 2026: 219,407,572 chars of text_body and
    622,974,370 of body_html across 5,053 bodied rows. The merge deletes 80 rows, so a
    naive DELETE would lose the 32 Class A bodies that live on the row being removed.
    """
    chars, html, bodied = db.execute(text(
        "SELECT coalesce(sum(length(text_body)),0), "
        "       coalesce(sum(length(body_html)),0), "
        "       count(*) FILTER (WHERE text_body IS NOT NULL AND length(text_body) > 0) "
        "FROM secondary_acts")).fetchone()
    assert chars >= 219_407_572, f"text_body lost characters: {chars} < 219,407,572"
    assert html >= 622_974_370, f"body_html lost characters: {html} < 622,974,370"
    assert bodied >= 5_053, f"bodied rows fell from 5,053 to {bodied}"


@pytest.mark.live
def test_no_act_lost_its_celex(db):
    """7,301 distinct CELEX before the merge; merging rows must not drop a value."""
    n = db.execute(text(
        "SELECT count(DISTINCT celex) FROM secondary_acts "
        "WHERE celex IS NOT NULL AND celex <> ''")).scalar()
    assert n >= 7_301, f"distinct CELEX fell from 7,301 to {n}"


@pytest.mark.live
def test_undated_rows_are_only_those_with_no_celex(db):
    """After the Cellar backfill, an undated row must be one Cellar cannot date.

    RED ON PURPOSE until the Cellar backfill runs. This is the acceptance check for
    that step, written before it, and it currently fails at 441.

    Cellar holds a work_date_document for these (5 of 5 spot-checked on 30 Sep matched
    their dated twin independently), so after the backfill the only undated rows left
    should be the ~738 with no CELEX to look up, plus any the authority genuinely has
    nothing for.

    The count is NOT a fixed 406: RegDel hands us new acts that carry a CELEX but no
    date, so this population grows on every ingest. An earlier version of this test
    pinned 406 and failed on 35 legitimate new arrivals. The bound is therefore what
    the backfill must achieve, not what the table happened to hold one afternoon.
    """
    with_celex = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE adoption_date IS NULL AND celex IS NOT NULL AND celex <> ''")).scalar()
    assert with_celex <= 20, (
        f"{with_celex} act(s) have a CELEX but no adoption date. Cellar can date them: "
        f"run the Cellar backfill. Only rows Cellar has nothing for may remain."
    )


@pytest.mark.live
def test_no_date_was_invented(db):
    """A stored adoption date must be plausible: no act predates the ECSC treaty."""
    bad = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE adoption_date IS NOT NULL "
        "  AND (adoption_date < DATE '1951-04-18' "
        "       OR adoption_date > CURRENT_DATE + 365)")).scalar()
    assert bad == 0, f"{bad} row(s) carry an impossible adoption_date"


@pytest.mark.live
def test_adoption_never_after_publication(db):
    """An act cannot be published in the OJ before it was adopted."""
    bad = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE adoption_date IS NOT NULL AND publication_date IS NOT NULL "
        "  AND adoption_date > publication_date")).scalar()
    assert bad == 0, f"{bad} row(s) are published before they were adopted"


@pytest.mark.live
def test_merged_rows_kept_the_reference_they_replaced(db):
    """A merge that discards the loser's C-number destroys evidence.

    Class B is 7 pairs where we cannot tell which C-number is right. Both must
    survive: the winner in `reference`, the loser in `merged_from`.

    783 rows already carried merged_from before this run. That is not history, it is
    the SAME defect: this table was de-duplicated once for ON CONFLICT (reference)
    and the root cause was left in place, so it came back as these 80. A bare
    `>= 80` therefore passes on the old cleanup alone and proves nothing.

    Counting rows-with-merged_from is also the wrong measure: 5 of the 80 survivors
    already held an entry, so the row count rose by 75, not 80, and a floor of 863
    would fail on a correct merge. The discriminating assertion is how many rows
    record THIS defect.
    """
    this_run = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE merged_from::text LIKE '%%ingest_regdel_acts.py%%'")).scalar()
    assert this_run == 80, (
        f"{this_run} row(s) record the duplicate-CELEX merge; expected exactly 80"
    )


@pytest.mark.live
def test_no_merge_history_was_discarded(db):
    """Absorbing a row must never shorten another row's merge chain.

    The earlier cleanup left 783 entries. This run added 80. Nothing may drop out:
    a survivor that already had history keeps it and gains an entry.
    """
    entries = db.execute(text(
        "SELECT coalesce(sum(jsonb_array_length(merged_from)), 0) "
        "FROM secondary_acts WHERE merged_from IS NOT NULL")).scalar()
    assert entries >= 863, (
        f"only {entries} merge entries survive; expected at least 783 from the earlier "
        f"cleanup plus 80 from this one"
    )


@pytest.mark.live
def test_a_celex_bearing_row_cannot_be_inserted_twice(db):
    """The schema, not just the script, must refuse a second row for one CELEX.

    A guard that lives only in one script is a guard one other writer walks past.
    """
    got = db.execute(text(
        "SELECT count(*) FROM pg_indexes "
        "WHERE tablename = 'secondary_acts' AND indexdef ILIKE '%UNIQUE%' "
        "  AND indexdef ILIKE '%celex%'")).scalar()
    assert got >= 1, (
        "no unique index on secondary_acts.celex: nothing stops the next writer "
        "re-creating the duplicates by hand"
    )


# --------------------------------------------------------------------------
# Pipeline rows: acts the Commission has ANNOUNCED but not adopted.
# 322 of them (207 Planned, 109 Cancelled, 6 On hold) never reached the database
# because normalise_row() requires a CCode, and a C-number only exists once the
# College has adopted the act.
# --------------------------------------------------------------------------

@pytest.mark.live
def test_synthetic_reference_can_never_be_read_as_a_c_number(db):
    """A pipeline row's reference is invented. It must be obviously invented.

    `reference` is where a real Commission C(YYYY)NNNN lives. Putting a value there
    that LOOKS like one is how a derived identifier gets mistaken for a real one and
    ends up in front of a subscriber as fact.
    """
    bad = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE reference LIKE 'PLANNED:%' AND reference ~ 'C\\(\\d{4}\\)'")).scalar()
    assert bad == 0, f"{bad} synthetic reference(s) look like a Commission C-number"

    malformed = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE reference LIKE 'PLANNED:%' AND reference !~ '^PLANNED:[0-9a-f]{16}$'")).scalar()
    assert malformed == 0, f"{malformed} synthetic reference(s) are not PLANNED:<16 hex>"


@pytest.mark.live
def test_pipeline_rows_never_carry_an_invented_celex_or_date(db):
    """A planned act has not been adopted, so it has no CELEX and no adoption date."""
    bad = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE reference LIKE 'PLANNED:%' "
        "  AND (celex IS NOT NULL OR adoption_date IS NOT NULL)")).scalar()
    assert bad == 0, f"{bad} pipeline row(s) carry a CELEX or an adoption date"


@pytest.mark.live
def test_pipeline_row_does_not_shadow_a_real_act(db):
    """7 of the 322 are the same act already held under a real C-number.

    Storing both would hand a subscriber the same act twice, once as 'planned' and
    once as 'published'.
    """
    dupes = db.execute(text("""
        SELECT count(*) FROM secondary_acts p
        WHERE p.reference LIKE 'PLANNED:%'
          AND EXISTS (
            SELECT 1 FROM secondary_acts r
            WHERE r.reference NOT LIKE 'PLANNED:%'
              AND r.act_type = p.act_type
              AND lower(regexp_replace(r.title, '\\s+', ' ', 'g'))
                = lower(regexp_replace(p.title, '\\s+', ' ', 'g')))
    """)).scalar()
    assert dupes == 0, f"{dupes} pipeline row(s) duplicate an act we already hold"


@pytest.mark.live
def test_planned_period_keeps_the_registers_own_precision(db):
    """The register states its indicative timing at THREE different precisions.

    Measured across all 3,099 populated rows on 30 Sep 2026:

        Q3 2026      quarter    2,155
        18/10/2013   full date    611
        06/2019      month        333

    An earlier version of this test accepted only the quarter form and failed on the
    other 944. The column is text precisely because the precision varies and is itself
    information: 'Q3 2026' is a much weaker commitment than '18/10/2013', and coercing
    either into adoption_date would assert a day the College has not sat on.

    Anything outside these three shapes is a format the register has newly introduced
    and we should look at it rather than absorb it silently.
    """
    bad = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE planned_adoption_period IS NOT NULL "
        "  AND planned_adoption_period !~ '^(Q[1-4] [0-9]{4}|[0-9]{4}|"
        "[0-9]{2}/[0-9]{4}|[0-9]{2}/[0-9]{2}/[0-9]{4})$'")).scalar()
    assert bad == 0, f"{bad} planned period(s) are in a shape the register did not use before"


@pytest.mark.live
def test_planned_period_never_became_an_adoption_date(db):
    """A plan is not an event. No pipeline row may carry an adoption date."""
    bad = db.execute(text(
        "SELECT count(*) FROM secondary_acts "
        "WHERE reference LIKE 'PLANNED:%' AND adoption_date IS NOT NULL")).scalar()
    assert bad == 0, f"{bad} announced act(s) were given an adoption date they do not have"


@pytest.mark.live
def test_pipeline_ingest_is_idempotent(db):
    """The ingest runs daily. A second run must match these rows, not re-insert them.

    This is the check the whole synthetic-key design exists to satisfy: the key is a
    deterministic hash of act_type + normalised title, so the same announcement
    resolves to the same row every day.
    """
    total, distinct = db.execute(text(
        "SELECT count(*), count(DISTINCT reference) FROM secondary_acts "
        "WHERE reference LIKE 'PLANNED:%'")).fetchone()
    assert total == distinct, (
        f"{total - distinct} duplicate synthetic reference(s): the ingest is inserting "
        f"where it should be updating"
    )


@pytest.mark.live
def test_no_row_asserts_a_published_act_without_any_evidence(db):
    """A title claiming "(EU) 2026/289" asserts that a specific act exists.

    Three rows inserted on 2026-04-25 did exactly that and none of them was real:

        'Implementing Regulation (EU) 2026/289 on AML reporting templates for the AMLA'
            -> 2026/289 is a DECISION of 3 Feb 2026 on emergency measures, unrelated
        'Implementing Decision (EU) 2025/2701 establishing the EU Critical Raw Materials...'
            -> no act of any type carries that number
        'Implementing Regulation (EU) 2026/498 on common technical specifications...'
            -> no act of any type carries that number

    They reached the API on the exact subjects clients query (AMLA, critical raw
    materials, IVDR). Their shared signature is the cheap thing to test for: the row
    names a numbered, published act but carries no CELEX and no regdel_id, so nothing
    in the record ties the claim to a source.

    A row with no CELEX is fine when it does not claim to be published -- a planned act
    reads '(EU) .../...' precisely because the number does not exist yet.
    """
    # The number must be the act's OWN designation, which sits immediately after the
    # instrument name at the start of the title. An unanchored search matches the PARENT
    # act instead -- 'amending Regulation (EU) No 1178/2011' -- and flagged 373 perfectly
    # good rows on the first attempt. Those are adopted-but-unpublished acts whose own
    # designation is still the placeholder '(EU) .../...', which is exactly right: the
    # number does not exist until the act reaches the Official Journal.
    rows = db.execute(text(r"""
        SELECT reference, left(title, 90) FROM secondary_acts
        WHERE celex IS NULL
          AND regdel_id IS NULL
          AND reference NOT LIKE 'PLANNED:%'
          AND title ~* '^(commission|council)\s+(implementing\s+|delegated\s+)?'
                       '(regulation|decision|directive)\s+\(EU\)\s*(No\s*)?[0-9]{4}/[0-9]+'
    """)).fetchall()
    assert not rows, (
        "row(s) name a specific published act but hold no CELEX and no regdel_id, so "
        "nothing connects the claim to a source: "
        + "; ".join(f"{r[0]} {r[1]!r}" for r in rows[:5])
    )


@pytest.mark.live
def test_planned_period_reaches_the_api_not_just_the_table(db):
    """A column in the database is not a field the API serves.

    planned_adoption_period was added by migration 260 and documented in the Postman
    collection on the same day, but it was served by nothing: the ORM model had no
    such attribute, so the response builder's getattr() returned None forever, and the
    Pydantic schema had no field to put it in anyway. The documentation would have sent
    a subscriber looking for a key that never appears.

    Four links have to agree, and this asserts the three that live in code.
    """
    import sys as _sys
    _sys.path.insert(0, str(pathlib.Path(_REPO_ROOT) / "backend"))
    from models.w4_entities import SecondaryAct
    from api.v1.w4_endpoints import SecondaryActItem

    in_db = db.execute(text(
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'secondary_acts' "
        "  AND column_name = 'planned_adoption_period'")).scalar()
    assert in_db == 1, "migration 260 has not been applied to this database"
    assert hasattr(SecondaryAct, "planned_adoption_period"), (
        "the ORM model cannot read the column, so the API will serve None for every row"
    )
    assert "planned_adoption_period" in SecondaryActItem.model_fields, (
        "the response schema has no field for it, so it is dropped on the way out"
    )
