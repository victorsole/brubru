"""`cd backend && pytest` ran ZERO tests, and had for as long as two files sat in tests/.

`test_dpp_mcp.py` and `test_dpp_endpoints.py` were end-to-end CHECK SCRIPTS: their work
ran at module level and they finished with `sys.exit(1 if failed else 0)`. pytest imports
every module it collects, so:

  * `pytest --collect-only` alone executed them, minted a real API key against the live
    database, revoked it, and took 39 seconds;
  * the `sys.exit()` then surfaced as a collection ERROR, and pytest stops the session on
    a collection error, so on 24 September 2026 the documented command collected 2,456
    tests and ran none of them.

Both moved to `scripts/check_dpp_*.py`, where a script belongs. These tests keep the door
shut, and they check the SHAPE of every collected file rather than trying to run it: a
file whose import has side effects cannot be caught by importing it.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

TESTS_DIR = pathlib.Path(__file__).resolve().parent
# What pytest collects by default, which is exactly the set that gets imported.
COLLECTED = sorted(p for p in TESTS_DIR.rglob("test_*.py"))


def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_there_is_something_to_collect():
    assert len(COLLECTED) > 100, "the discovery itself is broken if this is small"


@pytest.mark.parametrize("path", COLLECTED, ids=lambda p: p.name)
def test_no_collected_file_calls_sys_exit(path):
    """`sys.exit()` in a collected module ends the whole pytest session, not just the file."""
    offenders = []
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Call):
            f = node.func
            if (getattr(f, "attr", None) == "exit"
                    and getattr(getattr(f, "value", None), "id", "") == "sys"):
                offenders.append(node.lineno)
    assert not offenders, (
        f"{path.name} calls sys.exit at line(s) {offenders}. A check script belongs in "
        f"scripts/, not tests/: pytest imports what it collects, so this aborts the run."
    )


@pytest.mark.parametrize("path", COLLECTED, ids=lambda p: p.name)
def test_every_collected_file_actually_defines_tests(path):
    """A `test_*.py` that defines no test is a script in the wrong folder, and its work
    runs at import. That is the shape of the defect this file exists for."""
    tree = _tree(path)
    has_test = any(
        isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test_")
        for n in ast.walk(tree)
    )
    assert has_test, (
        f"{path.name} is collected by pytest but defines no test function, so importing "
        f"it is the only thing that happens. Move it to scripts/ and give it a main()."
    )


def test_the_two_scripts_are_where_scripts_live():
    """Named explicitly: a later 'tidy-up' that moves them back re-breaks the suite."""
    scripts = TESTS_DIR.parent / "scripts"
    for name in ("check_dpp_mcp.py", "check_dpp_endpoints.py"):
        assert (scripts / name).is_file(), f"{name} should live in backend/scripts/"
        assert not (TESTS_DIR / name.replace("check_", "test_")).exists(), \
            f"{name} is back under tests/ and will abort collection again"
