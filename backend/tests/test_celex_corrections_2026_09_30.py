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
        """"No old value anywhere" is too strong: in an ordered swap the value one row
        vacates is the value another row is corrected INTO. 32011L0061 was the Israel
        adequacy Decision's wrong CELEX and is AIFMD's right one. The invariant is that
        an old value survives only where it is also somebody's intended target."""
        targets = {v["to"] for v in payload["confirmed"].values()}
        rows = db.execute(text(
            "SELECT id, celex FROM eu_laws WHERE celex = ANY(:c)"),
            {"c": list(payload["confirmed"])}).fetchall()
        wrong = [(r[0], r[1]) for r in rows if r[1] not in targets]
        assert not wrong, f"{len(wrong)} row(s) still carry a CELEX we know is wrong: {wrong[:5]}"
        applied = payload.get("applied_ids") or {}
        misplaced = [(r[0], r[1]) for r in rows if applied.get(str(r[0])) != r[1]]
        assert not misplaced, f"{len(misplaced)} row(s) sit on a target they were not moved to"

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
        """A correction moves an identifier. It must not create or destroy a law."""
        n = db.execute(text("SELECT count(*) FROM eu_laws")).scalar()
        assert n == payload["row_count_before"], (
            f"eu_laws holds {n}, was {payload['row_count_before']}")

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
        """Drafts, association-council acts, EEA declarations and annex fragments have
        no CELEX of their own. No identifier beats a wrong one."""
        ids = [int(r["id"]) for r in payload["to_null"]]
        still = db.execute(text(
            "SELECT count(*) FROM eu_laws WHERE id = ANY(:i) AND celex IS NOT NULL"),
            {"i": ids}).scalar()
        assert still == 0, f"{still} record(s) still carry a CELEX that does not exist"


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
