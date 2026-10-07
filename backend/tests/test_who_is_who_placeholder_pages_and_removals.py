"""Who-is-who: placeholder ids have pages; a page verified gone removes the official (7 Oct 2026).

575 officials with an UNDEFINED_ person id were served with no public_url, read as "no page
exists". Victor found their pages under the institution's code (UNDEFINED_EMA_I1014 ->
EMEA_EMA_I1014), 25/25 verified. An official whose page the publisher took down is no
longer served: removed_date is set, and the nightly sync must not bring them back.
"""
import importlib.util
import pathlib
import sys

from sqlalchemy.dialects import postgresql

from services.scrapers import who_is_who_ingest as wi

_SCRIPTS = pathlib.Path(__file__).resolve().parents[1] / "scripts"
CB = "http://publications.europa.eu/resource/authority/corporate-body/"
PERSON = "http://publications.europa.eu/resource/directory/person/"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_a_placeholder_id_takes_the_institution_code():
    assert wi.undefined_page_id("UNDEFINED_EMA_I1014", CB + "EMEA") == "EMEA_EMA_I1014"
    assert wi.undefined_page_id("UNDEFINED_NRE525717", CB + "EUROFOUND") == "EUROFOUND_NRE525717"
    assert wi.undefined_page_id("UNDEFINED_NRE525717", None) is None


def test_the_ingest_serves_the_placeholder_page():
    url = wi._person_page(PERSON + "UNDEFINED_NRE533266", None, CB + "EUSPA")
    assert url == wi.PERSON_PAGE.format(person_id="EUSPA_NRE533266")
    assert wi._person_page(PERSON + "UNDEFINED_NRE533266", None) is None  # no institution, no guess


def test_the_verifier_asks_about_the_url_actually_served():
    verify = _load("verify_who_is_who_urls")
    eeas = "https://www.eeas.europa.eu/delegations/guyana/about-ambassador_en"
    assert verify._url_for(PERSON + "EEAS_00003AA24742", CB + "EEAS", eeas) == eeas
    assert verify._url_for(PERSON + "UNDEFINED_EMA_I2671", CB + "EMEA").endswith("/EMEA_EMA_I2671")


def test_a_dead_page_removes_the_official_and_a_live_one_gets_its_link():
    verify = _load("verify_who_is_who_urls")
    assert "removed_at = coalesce(removed_at, now())" in str(verify.RECORD_DEAD)
    assert "replace(body_html, '</article>'" in str(verify.RECORD_ALIVE)


def test_the_sync_keeps_a_verified_dead_page_removed():
    sync = _load("sync_who_is_who")
    captured = {}

    class Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, stmt, *a, **k):
            captured["sql"] = str(stmt.compile(dialect=postgresql.dialect()))

    class Engine:
        def begin(self):
            return Conn()

    sync.engine = Engine()
    from models.who_is_who import WhoIsWhoOfficial as T
    row = {c.name: None for c in T.__table__.columns}
    row.update(official_key="k", name="n", body_html="<p>x</p>")
    sync._bulk(T.__table__, [row], "official_key")
    removed = captured["sql"].split("removed_at = ", 1)[1]
    assert removed.startswith("CASE WHEN (who_is_who_officials.url_status =")
    assert "coalesce(who_is_who_officials.removed_at, now())" in removed
