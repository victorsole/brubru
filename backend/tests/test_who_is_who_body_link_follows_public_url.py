"""A who-is-who body links exactly the page public_url names, or none (6 Oct 2026).

The nightly sync kept a verified public_url but rebuilt body_html from the derived URL,
so 237 served bodies linked a page other than public_url (94 of them a 404 while
public_url was null). Both writers now rebuild the link from public_url.
"""
import importlib.util
import pathlib
import sys

from sqlalchemy.dialects import postgresql

_SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_the_sync_rebuilds_the_body_link_once_a_page_is_verified():
    sync = _load("sync_who_is_who")
    captured = {}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, stmt, *a, **k):
            compiled = stmt.compile(dialect=postgresql.dialect())
            captured["sql"], captured["params"] = str(compiled), compiled.params

    class Engine:
        def begin(self):
            return Conn()

    sync.engine = Engine()
    from models.who_is_who import WhoIsWhoOfficial as T
    row = {c.name: None for c in T.__table__.columns}
    row.update(official_key="k", name="n", body_html="<p>x</p>")
    sync._bulk(T.__table__, [row], "official_key")
    sql = captured["sql"]
    assert "body_html = CASE WHEN" in sql and "url_checked_at IS NULL" in sql
    assert "regexp_replace" in sql and "who_is_who_officials.public_url" in sql
    assert any("View on EU Who is Who" in str(v) for v in captured["params"].values())


def test_the_verifier_rewrites_or_drops_the_body_link():
    verify = _load("verify_who_is_who_urls")
    alive, dead = str(verify.RECORD_ALIVE), str(verify.RECORD_DEAD)
    assert "body_html = regexp_replace" in alive and ":url" in alive.split("body_html", 1)[1]
    assert "body_html = regexp_replace" in dead and "public_url = NULL" in dead
