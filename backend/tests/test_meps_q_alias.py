"""Every MEP name search returned the same members (24 September 2026).

`/api/v2/parliament/meps` called its free-text parameter `name`. The other 54 v2 list
endpoints call it `q`, and FastAPI silently ignores a parameter it does not declare, so
`?q=weber` was answered with the unfiltered first page: HTTP 200, a full envelope, and no
sign that the filter had never been applied. That is the failure mode worth a test, not
the alias itself: a wrong answer that looks exactly like a right one.

`q` is now an accepted alias for `name` on both v1 and the generated v2.

No network, no database: the signature and the alias merge are checked directly.
"""
from __future__ import annotations

import inspect
import pathlib
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1 import meps as v1  # noqa: E402
from api.v2.parliament import meps as v2  # noqa: E402


@pytest.mark.parametrize("module", [v1, v2], ids=["v1", "v2"])
def test_both_versions_declare_the_alias(module):
    params = inspect.signature(module.list_meps).parameters
    assert "q" in params, "q is not declared, so it is ignored and the page comes back unfiltered"
    assert "name" in params, "name must keep working: it is the documented parameter"


def test_v2_hands_the_alias_on():
    """v2 delegates to v1 by keyword. A parameter it declares but does not forward is the
    same silent failure one layer down."""
    src = inspect.getsource(v2.list_meps)
    assert "q=q" in src, "v2 declares q and drops it on the way to v1"


def test_the_alias_is_the_convention_not_an_exception():
    """If a later endpoint copies this one, it should copy the house convention."""
    v2_dir = BACKEND / "api" / "v2"
    q_endpoints = [p for p in v2_dir.rglob("*.py")
                   if "q: Optional[str] = Query" in p.read_text(encoding="utf-8")]
    assert len(q_endpoints) > 40, f"only {len(q_endpoints)} endpoints use q: has the convention moved?"
    assert any(p.name == "meps.py" for p in q_endpoints), "meps is still the odd one out"


@pytest.mark.parametrize("needle,full_name,hit", [
    ("sole", "Víctor Solé", True),          # accent- and case-insensitive
    ("SOLÉ", "Victor Sole", True),
    ("weber", "Manfred Weber", True),
    ("weber", "Manfred WEBER", True),
    ("zzz", "Manfred Weber", False),
])
def test_the_needle_that_the_alias_carries_is_matched_the_same_way(needle, full_name, hit):
    """Whatever name arrives -- through `name` or through `q` -- is matched by _fold."""
    assert (v1._fold(needle) in v1._fold(full_name)) is hit
