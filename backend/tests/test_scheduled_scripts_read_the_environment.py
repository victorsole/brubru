"""A scheduled script must read DATABASE_URL from the ENVIRONMENT, not from a .env file.

The Railway container ships no .env. A script whose `get_env` reads only that file
returns "" and dies on its first line, while working perfectly on a laptop. Five jobs
were scheduled on 28 Sep 2026 without one of them ever having been seen to succeed where
it runs; three died exactly this way.

The fourth, ingest_regdel_acts.py, was missed on 29 Sep because its visible failure was a
missing `pandas` import. Fixing the import revealed the DATABASE_URL fault underneath on
the very next tier run. This test exists so the class is checked once rather than
rediscovered one file at a time: 32 scripts read .env only, but only the SCHEDULED ones
are wrong, because the rest run by hand on a machine that has the file.
"""
import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _scheduled_scripts() -> set[str]:
    paths = set()
    for f in ("services/sync/source_registry.py", "api/cron.py"):
        text = (BACKEND / f).read_text(encoding="utf-8")
        paths |= set(re.findall(r'"(scripts/[a-z0-9_]+\.py)"', text))
    return paths


def _get_env_source(path: Path) -> str | None:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "get_env":
            return ast.get_source_segment(text, node)
    return None


def test_every_scheduled_script_reads_the_process_environment():
    offenders = []
    for rel in sorted(_scheduled_scripts()):
        p = BACKEND / rel
        if not p.exists():
            continue
        src = _get_env_source(p)
        if src is not None and "environ" not in src:
            offenders.append(rel)
    assert not offenders, (
        "these scheduled scripts read a .env file that does not exist in the container, "
        f"so they die on their first line: {offenders}"
    )


def test_the_check_can_actually_see_a_get_env():
    """Guard against the guard: if the scan stops finding get_env at all, the test above
    passes vacuously. It found 49 definitions on 30 Sep 2026."""
    found = sum(1 for p in (BACKEND / "scripts").glob("*.py") if _get_env_source(p) is not None)
    assert found >= 20, f"only {found} get_env definitions found; the scan is broken"
