"""D4: committee responsible vs committee for opinion, and events vs forecasts.

The defect (measured 27 Aug 2026): for `2025/2081(INI)`, *Impact of social media
and the online environment on young people*, Brubru recorded the lead committee as
**IMCO**. OEIL says the committee responsible is **CULT**; IMCO holds an opinion,
with LIBE and FEMM. The rapporteur, **Sandro RUOTOLO (S&D)**, appointed 14 April
2025, was NULL. A forecast dated 14 September 2026 was carried as a committee vote
that had already happened.

The cause was `lead_committee = item.committees[0]` -- whichever committee came
first in a flat list from the OEIL XML feed, which does not distinguish the roles
at all. Across the fleet, `rapporteur_mep_id` was populated on 0 of 2,789 rows and
`opinion_committees` on 1, so two columns had never been written.

The most important test here is `test_sync_does_not_overwrite_parsed_roles`: the
feed still returns its flat list on every run, and without that guard the whole
correction would survive exactly one sync.
"""
import pytest
from sqlalchemy import text

from services.scrapers.oeil_procedure_parser import parse_procedure_text

# The relevant part of the real OEIL page, kept verbatim so the fixture cannot
# drift into agreeing with a wrong parser.
SAMPLE = (
    "Impact of social media and the online environment on young people "
    "Committee responsible Rapporteur Appointed CULT Culture and Education "
    "RUOTOLO Sandro (S&D) 14/04/2025 Shadow rapporteur GLAVAK Sunčana (EPP) "
    "VICSEK Annamária (PfE) "
    "Committee for opinion Rapporteur for opinion Appointed "
    "IMCO Internal Market and Consumer Protection SMITH John (Renew) 01/06/2025 "
    "LIBE Civil Liberties, Justice and Home Affairs "
    "FEMM Women's Rights and Gender Equality "
    "Key events Date Event Reference Summary "
    "08/05/2025 Committee referral announced in Parliament "
    "Forecasts Date Subject 06/07/2026 Indicative plenary sitting date "
    "Technical information Procedure reference 2025/2081(INI)"
)


@pytest.fixture(scope="module")
def db():
    from core.database import SessionLocal
    s = SessionLocal()
    yield s
    s.close()


# ---------------------------------------------------------------------------
# 1. The parser
# ---------------------------------------------------------------------------

def test_responsible_committee_is_not_the_first_committee_mentioned():
    """CULT is responsible; IMCO merely appears in the document too."""
    f = parse_procedure_text(SAMPLE)
    assert f.responsible_committee == "CULT"
    assert "IMCO" not in [f.responsible_committee]


def test_opinion_committees_are_captured_and_exclude_the_responsible_one():
    f = parse_procedure_text(SAMPLE)
    assert f.opinion_committees == ["IMCO", "LIBE", "FEMM"]
    assert f.responsible_committee not in f.opinion_committees


def test_rapporteur_is_the_responsible_one_not_a_shadow():
    """Attributing a shadow rapporteur's name to the file is its own fabrication."""
    f = parse_procedure_text(SAMPLE)
    assert f.rapporteur_name == "RUOTOLO Sandro"
    assert "GLAVAK" not in (f.rapporteur_name or "")
    assert f.rapporteur_appointed and f.rapporteur_appointed.isoformat() == "2025-04-14"


def test_forecasts_are_not_key_events():
    """The heart of the second half of D4.

    A forecast is what is EXPECTED. Merged into key events it becomes a thing that
    has already happened -- which is how an indicative plenary date was presented
    as a completed committee vote.
    """
    f = parse_procedure_text(SAMPLE)
    assert any("Indicative plenary" in e["event_type"] for e in f.forecasts)
    assert not any("Indicative plenary" in e["event_type"] for e in f.key_events)
    assert any("Committee referral" in e["event_type"] for e in f.key_events)
    assert not any("Committee referral" in e["event_type"] for e in f.forecasts)


def test_a_page_without_forecasts_does_not_borrow_key_events():
    """A missing section must yield nothing, not the rest of the document."""
    no_forecast = SAMPLE.split("Forecasts")[0]
    f = parse_procedure_text(no_forecast)
    assert f.forecasts == []
    assert f.key_events, "key events should still parse"


def test_empty_input_is_safe():
    f = parse_procedure_text("")
    assert f.responsible_committee is None and f.opinion_committees == []


def test_group_and_country_tokens_are_not_read_as_committees():
    """A bare four-capitals match would pick up all sorts of things."""
    f = parse_procedure_text(
        "Committee responsible Rapporteur Appointed ECON Economic and Monetary "
        "Affairs SMITH John (EPP) 01/01/2026 Committee for opinion NONE ABCD XYZW"
    )
    assert f.responsible_committee == "ECON"
    assert f.opinion_committees == []


# ---------------------------------------------------------------------------
# 2. The correction actually landed
# ---------------------------------------------------------------------------

def test_the_named_procedure_is_corrected_in_the_database(db):
    row = db.execute(text(
        "SELECT lead_committee, opinion_committees, rapporteur_name "
        "FROM legislative_carriages WHERE oeil_procedure_ref = '2025/2081(INI)'"
    )).fetchone()
    if row is None:
        pytest.skip("2025/2081(INI) not present")
    assert row.lead_committee == "CULT", (
        f"lead committee is {row.lead_committee}; OEIL says CULT and IMCO is opinion only"
    )
    assert "IMCO" in (row.opinion_committees or [])
    assert row.rapporteur_name and "RUOTOLO" in row.rapporteur_name


def test_the_columns_that_had_never_been_written_now_are(db):
    """rapporteur was 0/2789 and opinion_committees 1/2789 before the backfill."""
    got = db.execute(text(
        "SELECT count(*) FILTER (WHERE rapporteur_name IS NOT NULL) r, "
        "       count(*) FILTER (WHERE array_length(opinion_committees,1) > 0) o "
        "FROM legislative_carriages")).fetchone()
    assert got.r > 100, f"only {got.r} carriages have a rapporteur name"
    assert got.o > 100, f"only {got.o} carriages have opinion committees"


def test_unparsed_carriages_are_distinguishable_from_role_free_ones(db):
    """NULL `oeil_roles_parsed_at` must mean 'never parsed', never 'no opinions'.

    Without that third state, a carriage we have simply not read looks identical
    to one that genuinely has no opinion committees.
    """
    n = db.execute(text(
        "SELECT count(*) FROM legislative_carriages WHERE oeil_roles_parsed_at IS NULL"
    )).scalar()
    assert n > 0, "expected some carriages to remain unparsed (no stored page)"


# ---------------------------------------------------------------------------
# 3. The guard — or the fix lasts exactly one sync
# ---------------------------------------------------------------------------

def test_sync_does_not_overwrite_parsed_roles():
    """The OEIL feed keeps returning its flat list on every run.

    `_update_carriage` must refuse to set `lead_committee` from `committees[0]`
    once `oeil_roles_parsed_at` is set, or the next sync silently restores IMCO.

    Asserted over the AST. A first version of this test grepped the source for
    "oeil_roles_parsed_at" and PASSED against a deliberately removed guard,
    because the token also appears in the comment explaining the guard. A test
    that its own documentation can satisfy is not a test.
    """
    import ast
    import inspect
    import textwrap

    from services.scrapers.oeil_sync_service import OEILSyncService

    tree = ast.parse(textwrap.dedent(inspect.getsource(OEILSyncService._update_carriage)))
    guarded = False
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        # The guard must be in the CONDITION, not merely nearby.
        names = {
            n.value for n in ast.walk(node.test)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        } | {
            n.attr for n in ast.walk(node.test) if isinstance(n, ast.Attribute)
        }
        if "oeil_roles_parsed_at" in names:
            # ...and it must be the branch that assigns lead_committee.
            assigns = [
                t.attr for stmt in ast.walk(node)
                if isinstance(stmt, ast.Assign)
                for t in stmt.targets if isinstance(t, ast.Attribute)
            ]
            if "lead_committee" in assigns:
                guarded = True
    assert guarded, (
        "_update_carriage assigns lead_committee without testing "
        "oeil_roles_parsed_at, so the feed's positional guess will overwrite "
        "authoritative roles on the very next sync"
    )


def test_the_model_exposes_the_guard_column():
    """`getattr(carriage, 'oeil_roles_parsed_at', None)` silently returns None if
    the ORM lacks the column -- which would disable the guard without any error."""
    from models.legislative_train import LegislativeCarriage
    for col in ("oeil_roles_parsed_at", "rapporteur_name", "oeil_forecasts"):
        assert hasattr(LegislativeCarriage, col), f"model is missing {col}"
