"""The funding matches run only for the organisations still matched (30 Oct 2026): Terraqui's engagement
ended on 12 Oct, and Victor: "Cadence should not be matched again". Their profiles stay in the script for
the record; a run, its HTML header and its workbooks never include them."""
import importlib.util
import pathlib

SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"{name}_under_test", SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_retired_organisations_are_never_matched():
    fm = _load("build_funding_matches")
    assert set(fm.RETIRED) == {"terraqui", "cadence"}
    assert [p["slug"] for p in fm.PROFILES] == ["gbsb", "tas"]


def test_the_workbooks_are_built_for_the_same_organisations():
    fm, xl = _load("build_funding_matches"), _load("build_funding_matches_xlsx")
    assert set(xl.ORGS) == {p["slug"] for p in fm.PROFILES}
