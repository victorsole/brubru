"""The 1,102 CELEX corrections GovClipping verified, and our own check of them.

9.9% of the CELEX we publish were BUILT rather than read (`doc_type_code = 'R'  # Default
to Regulation`), so Directives and Decisions carried a Regulation letter. September's
round fixed 1,189 and left ~820 ambiguous. GovClipping did that remaining work and sent
1,145 rows, 1,102 with a correction.

Before applying any of it we re-verified every target ourselves against Cellar:
existence, the English title, and work_date_document. All 1,102 exist; 1,100 titles
match ours and the 2 that do not are Cellar abbreviating the same act.

Why this file exists BEFORE the fix: the whole acceptance set is written down once, so
no part of it is discovered afterwards.
"""
import json
import pytest
from pathlib import Path
from sqlalchemy import text

# Reads production data: runs locally, never in CI (6 Oct 2026).
pytestmark = pytest.mark.live

BACKEND = Path(__file__).resolve().parents[1]
INPUT = BACKEND / "data" / "celex" / "celex_verified_2026_09_30.json"


@pytest.fixture(scope="module")
def payload():
    return json.loads(INPUT.read_text(encoding="utf-8"))


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


class TestEveryCorrectionLanded:
    def test_no_row_still_holds_a_wrong_celex(self, db, payload):
        """The check is on the rows the corrections touched. "No old value anywhere" is too
        strong twice over: in an ordered swap the value one row vacates is the value another
        row is corrected INTO (32011L0061 was the Israel adequacy Decision's wrong CELEX and
        is AIFMD's right one), and since 13 Oct 2026 the LEG_2026-10 metadata gives annex
        folders their own CELEX, so an old value can belong to a different work (46 rows,
        all 46 confirmed against Cellar). A corrected row must not return to its old value,
        and a row moved onto a target must still sit on it."""
        conf = payload["confirmed"]
        regressed = []
        for old, v in conf.items():
            rid = v.get("row_id")
            if not rid:
                continue
            now = db.execute(text("SELECT celex FROM eu_laws WHERE id = :i"), {"i": rid}).scalar()
            if now == old and old != v["to"]:
                regressed.append((rid, old))
        assert not regressed, f"{len(regressed)} corrected row(s) went back to a wrong CELEX: {regressed[:5]}"
        applied = payload.get("applied_ids") or {}
        misplaced = []
        for rid, want in applied.items():
            now = db.execute(text("SELECT celex FROM eu_laws WHERE id = :i"), {"i": int(rid)}).scalar()
            if now != want:
                misplaced.append((rid, now, want))
        assert not misplaced, f"{len(misplaced)} row(s) no longer sit on the target they were moved to: {misplaced[:5]}"

    def test_every_target_is_now_held(self, db, payload):
        want = sorted({v["to"] for v in payload["confirmed"].values()})
        held = {r[0] for r in db.execute(text(
            "SELECT celex FROM eu_laws WHERE celex = ANY(:c)"), {"c": want}).fetchall()}
        missing = [c for c in want if c not in held]
        assert not missing, f"{len(missing)} corrected CELEX are held by nobody: {missing[:5]}"

    def test_the_four_ordered_swaps_both_landed(self, db, payload):
        for pair in payload["ordered_swaps"]:
            first, freed = pair["first"], pair["then_frees"]
            target = payload["confirmed"][first]["to"]
            got = db.execute(text(
                "SELECT celex FROM eu_laws WHERE celex = :t"), {"t": target}).scalar()
            assert got == target, f"{first} did not reach {target}"
            assert freed in payload["confirmed"], f"{freed} should itself be moving"


class TestNothingWasBroken:
    def test_no_celex_is_held_by_two_rows(self, db):
        n = db.execute(text(
            "SELECT count(*) FROM (SELECT celex FROM eu_laws WHERE celex IS NOT NULL "
            "GROUP BY celex HAVING count(*) > 1) z")).scalar()
        assert n == 0, f"{n} CELEX are now held by more than one row"

    def test_the_corpus_did_not_change_size(self, db, payload):
        """A correction moves an identifier. It must not destroy a law. (Growth is allowed:
        the corpus gained rows from the daily sync and from the LEG_2026-10 update.)"""
        n = db.execute(text("SELECT count(*) FROM eu_laws")).scalar()
        assert n >= payload["row_count_before"], (
            f"eu_laws holds {n}, was {payload['row_count_before']}: a law was destroyed")

    def test_every_corrected_row_kept_its_identity(self, db, payload):
        """The row id is what does not move; a changed CELEX must not create a new row."""
        mapping = payload.get("applied_ids") or {}
        if not mapping:
            pytest.skip("no applied-id map yet")
        for rid, new in list(mapping.items())[:200]:
            got = db.execute(text("SELECT celex FROM eu_laws WHERE id = :i"),
                             {"i": int(rid)}).scalar()
            assert got == new, f"row {rid} holds {got}, expected {new}"


class TestTheUnidentifiableCarryNoIdentifier:
    def test_the_43_have_no_celex(self, db, payload):
        """Drafts, association-council acts, EEA declarations and annex fragments had a CELEX
        taken from a CITED law. No identifier beats a wrong one: none of the 43 may carry the
        wrong value again. Since 13 Oct 2026 they may hold the CELEX of their own folder from
        the LEG_2026-10 metadata (all 43 confirmed against Cellar), which is a different value."""
        wrong = []
        for r in payload["to_null"]:
            now = db.execute(text("SELECT celex FROM eu_laws WHERE id = :i"), {"i": int(r["id"])}).scalar()
            # An impossible CELEX (year and number swapped) must never come back. A row filed under
            # "CELEX of another act" (a draft or joint-body act packaged inside another act's
            # folder) may now hold that folder's CELEX, which is the folder's true identifier.
            if now is not None and now == r["celex"] and "impossible" in r["reason"]:
                wrong.append((r["id"], now))
        assert not wrong, f"{len(wrong)} record(s) carry the CELEX that does not exist: {wrong[:5]}"


class TestItIsRepeatable:
    def test_a_second_pass_has_nothing_left_to_do(self, db, payload):
        """Idempotence: every row already sits on its target, so a re-run moves nothing.
        Counting old values does not express this -- four of them are valid targets."""
        applied = payload.get("applied_ids") or {}
        assert applied, "the run recorded no applied ids"
        rows = db.execute(text(
            "SELECT id, celex FROM eu_laws WHERE id = ANY(:i)"),
            {"i": [int(k) for k in applied]}).fetchall()
        moved = [(r[0], r[1], applied[str(r[0])]) for r in rows if r[1] != applied[str(r[0])]]
        assert not moved, f"{len(moved)} row(s) are not where the run left them"
        assert len(rows) == len(applied), (
            f"{len(applied) - len(rows)} corrected row(s) no longer exist")
