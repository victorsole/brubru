"""About 10% of the CELEX values we served did not exist (GovClipping, 25 Sep 2026).

They checked the CELEX values we publish against the Publications Office and found 9.8%
that Cellar does not have; our own audit of all 19,081 distinct values found 1,897 (9.9%).
`derive_celex()` in the OJ scraper BUILDS a CELEX from the OJ number and a letter looked up
from the parsed act type, so a Directive read as a Regulation becomes 32023R2413 when the
real RED III is 32023L2413, and a corrigendum's OJ number becomes a CELEX that never
existed. The EUR-Lex links on those records led to documents that do not exist.

1,074 were corrected, each one passing three independent checks, because a candidate that
merely EXISTS in Cellar may belong to a different act:
  * exactly one alternative letter resolves in Cellar
  * the candidate is not already held by another of our rows (27 were: our 32005L0649 is a
    Commission Decision, Cellar's 32005D0649 is EP/Council Decision 649/2005)
  * Cellar's title for the candidate matches ours (this rejected 88 more: our 31049D2001
    is an EU-OSHA Administrative Board decision, Cellar's 32001R1049 is the Regulation on
    public access to documents)

Needs the database.
"""
from __future__ import annotations

import pathlib
import sys

import pytest
from sqlalchemy import text

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from core.database import SessionLocal  # noqa: E402


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.mark.parametrize("celex,gone", [
    ("32023L2413", "32023R2413"),   # RED III is a Directive
    ("32015L1535", "32015R1535"),   # the TRIS Directive
    ("32014R1229", "31229R2014"),   # year and number transposed
])
def test_the_corrected_celex_is_the_one_that_exists(db, celex, gone):
    assert db.execute(text("SELECT count(*) FROM eu_laws WHERE celex = :c"),
                      {"c": celex}).scalar() >= 1, f"{celex} missing"
    assert db.execute(text("SELECT count(*) FROM eu_laws WHERE celex = :c"),
                      {"c": gone}).scalar() == 0, f"{gone} does not exist in Cellar but we serve it"


def test_two_acts_no_longer_share_one_celex(db):
    """32013D0377 returned the Ombudsman election decision; in EUR-Lex it is Decision
    No 377/2013/EU. The Ombudsman decision is 32013D0377(01)."""
    rows = dict(db.execute(text(
        # Not truncated: "Ombudsman" sits past the 60th character of that title.
        "SELECT celex, coalesce(title,'') FROM eu_laws "
        "WHERE celex IN ('32013D0377','32013D0377(01)','32013L0377')")).fetchall())
    assert "32013L0377" not in rows, "a Decision is still stored under a Directive letter"
    assert "Decision No 377/2013/EU" in rows.get("32013D0377", "")
    assert "Ombudsman" in rows.get("32013D0377(01)", "")


def test_no_celex_is_held_by_two_rows(db):
    """A correction must not merge two laws onto one identifier."""
    n = db.execute(text(
        "SELECT count(*) FROM (SELECT celex FROM eu_laws WHERE celex IS NOT NULL "
        "GROUP BY celex HAVING count(*) > 1) z")).scalar()
    assert n == 0, f"{n} CELEX value(s) are held by more than one law"


def test_laws_expose_a_permanent_id(db):
    """A corrected CELEX reads to a client as a new record unless there is an id that does
    not move. eu_laws has an integer primary key that the API never exposed."""
    from api.v1.laws import LawItem

    assert "id" in LawItem.model_fields, "LawItem has no id"
    src = (BACKEND / "api" / "v1" / "laws.py").read_text(encoding="utf-8")
    assert src.count("id=r.id,") >= 2, "the id is declared but not populated on both routes"


def test_the_correction_was_recorded_for_the_client():
    """A changed CELEX looks like a new record downstream, so the mapping is handed over."""
    import json

    files = sorted((BACKEND.parent / "docs" / "backups").glob("eu_laws_celex_corrections_*.json"))
    assert files, "no old -> new mapping was written"
    rows = json.loads(files[-1].read_text(encoding="utf-8"))
    assert len(rows) > 1000
    assert {"id", "old_celex", "new_celex", "title"} <= set(rows[0])


# ------------------------------------------------------------------ the parser that caused it
def test_the_formex_parser_no_longer_assumes_every_act_is_a_regulation():
    """`doc_type_code = 'R'  # Default to Regulation` under a comment that said "Guess
    document type from title", which it never did. Every Directive and Decision parsed
    through that path got a Regulation CELEX."""
    src = (BACKEND / "services" / "parsers" / "formex_parser.py").read_text(encoding="utf-8")
    code = "\n".join(l.split("#")[0] for l in src.splitlines())
    assert "doc_type_code = 'R'" not in code, "the parser still defaults the type letter to R"
    assert "type_code = 'R'" not in code, "the second derivation still defaults to R"


def test_the_parser_leaves_celex_unset_when_it_cannot_know_the_type():
    """No CELEX is better than one that resolves to nothing, or to a different act."""
    from services.parsers.formex_parser import _CELEX_TYPE_LETTER, ParsedLaw

    assert _CELEX_TYPE_LETTER["Directive"] == "L"
    assert _CELEX_TYPE_LETTER["Decision"] == "D"
    assert _CELEX_TYPE_LETTER["Regulation"] == "R"
    assert ParsedLaw().celex is None


def test_there_is_a_scheduled_check_that_the_celex_we_publish_exist():
    """We learned about 9.9% invalid CELEX from a customer. Something has to ask."""
    cron = (BACKEND / "api" / "cron.py").read_text(encoding="utf-8")
    assert "scripts/audit_celex_exists.py" in cron, "nothing checks whether our CELEX exist"
    block = cron.split('"celex_exists_audit"')[-1][:300]
    assert "--record" in block, "the audit runs but records no verdict, so nobody hears it"


def test_the_audit_fails_rather_than_reporting_a_clean_run_on_an_error():
    """A batch that errors must not be counted as 'all of these exist' or 'all missing'."""
    src = (BACKEND / "scripts" / "audit_celex_exists.py").read_text(encoding="utf-8")
    assert "raise" in src.split("except Exception as exc:")[1][:260], (
        "a failed Cellar batch is swallowed, so a broken check would look like a clean corpus")
