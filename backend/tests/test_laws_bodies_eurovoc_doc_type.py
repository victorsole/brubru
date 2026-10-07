"""/laws: every law gets its body, and policy_area is EuroVoc, not a guess (7 Oct 2026).

GovClipping's window showed 45 laws with null bodies: 294 laws whose CELEX ends "(01)"
were excluded from the body drain (Cellar answers 404 to raw parentheses), and the drain
never ran on cron, so acts published after the 2 Oct backfill arrived without text.
policy_area came from Brubru's classifier: the decision electing the European Ombudsman
read "Energy". It is now the EuroVoc domain the Publications Office indexed.
"""
import importlib.util
import pathlib
import sys
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

_BACKEND = pathlib.Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, _BACKEND / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_parenthesised_celex_is_encoded_and_no_longer_skipped():
    f = _load("fetch_eu_law_bodies")
    assert f._cellar_url("32013D0377(01)").endswith("/celex/32013D0377%2801%29")
    assert "\\(" not in str(f.PICK)


def test_a_short_corrigendum_with_the_oj_masthead_is_a_body():
    f = _load("fetch_eu_law_bodies")
    corrigendum = "Official Journal of the European Union EN L series 2024/90389 Corrigendum " + "x" * 300
    assert not f._too_short(corrigendum)
    assert f._too_short("Access denied. " * 20)  # 300 characters, no masthead
    assert not f._too_short("a" * 600)


def test_primary_domain_ignores_geography_unless_it_is_the_only_one():
    ev = _load("sync_eu_law_eurovoc")
    t = lambda d: {"domain": d}
    protocol = [t("10 EUROPEAN UNION"), t("10 EUROPEAN UNION"), t("20 TRADE"),
                t("72 GEOGRAPHY"), t("72 GEOGRAPHY"), t("72 GEOGRAPHY")]
    assert ev.primary_domain(protocol) == "10 EUROPEAN UNION"
    assert ev.primary_domain([t("72 GEOGRAPHY")]) == "72 GEOGRAPHY"
    assert ev.primary_domain([t("52 ENVIRONMENT"), t("20 TRADE")]) == "20 TRADE"  # tie: lowest number
    assert ev.primary_domain([]) is None


def test_unknown_descriptors_are_left_out_never_labelled_by_guess():
    ev = _load("sync_eu_law_eurovoc")
    known = {"http://eurovoc.europa.eu/2140": ("European Ombudsman", "10 EUROPEAN UNION")}
    terms = ev.build_terms(["http://eurovoc.europa.eu/2140", "http://eurovoc.europa.eu/c_unknown"], known)
    assert terms == [{"id": "2140", "uri": "http://eurovoc.europa.eu/2140",
                      "label": "European Ombudsman", "domain": "10 EUROPEAN UNION"}]


def _law_row(**kw):
    base = dict(id=1, celex="32013D0377(01)", title="Decision electing the European Ombudsman",
                doc_type="Decision", doc_type_normalized="Decision", date=None, oj_reference=None,
                policy_area="Energy", legal_basis=[], created_at=None, updated_at=None,
                body_txt="text", body_html="<p>text</p>", eurovoc_domain="10 EUROPEAN UNION",
                eurovoc=[{"id": "2140", "uri": "http://eurovoc.europa.eu/2140",
                          "label": "European Ombudsman", "domain": "10 EUROPEAN UNION"}])
    base.update(kw)
    return SimpleNamespace(**base)


def test_policy_area_is_the_eurovoc_domain_not_the_classifier():
    from api.v1.laws import _law_item
    item = _law_item(_law_row())
    assert item.policy_area == "10 EUROPEAN UNION"
    assert item.eurovoc[0].label == "European Ombudsman"
    assert _law_item(_law_row(eurovoc=None, eurovoc_domain=None)).eurovoc == []


def test_policy_area_filter_takes_number_label_or_name():
    from api.v1.laws import _policy_area_filter
    sql = lambda v: str(_policy_area_filter(v).compile(dialect=postgresql.dialect(),
                                                       compile_kwargs={"literal_binds": True}))
    assert "LIKE '52 %%'" in sql("52") or "LIKE '52 %'" in sql("52")
    assert "'environment'" in sql("environment").lower()
    assert "'environment'" in sql("52 ENVIRONMENT").lower()


def test_v2_list_serves_stored_bodies_on_full_pages(monkeypatch):
    import asyncio
    from api.v2.legislative import eur_lex

    seen = {}

    async def fake_v1(request, **kw):
        seen.update(kw)
        return SimpleNamespace(data=[])

    monkeypatch.setattr(eur_lex._v1_laws, "list_laws", fake_v1)
    asyncio.run(eur_lex.list_laws(None, q=None, celex=None, doc_type=None, policy_area=None,
                                  published_from=None, published_to=None, published_end=None,
                                  updated_from=None, updated_to=None, updated_end=None,
                                  created_from=None, created_to=None,
                                  include_orphans=False, include_body=True, limit=100, page=1,
                                  user=None, db=None))
    assert seen["include_body"] is True and seen["limit"] == 100
    assert "created_from" in seen and "created_to" in seen


def test_the_hot_tier_fetches_bodies_and_eurovoc_after_the_law_sync():
    src = (_BACKEND / "api" / "cron.py").read_text()
    sync = src.index("scripts/sync_eu_laws_from_cellar.py")
    assert sync < src.index("scripts/fetch_eu_law_bodies.py")
    assert sync < src.index("scripts/sync_eu_law_eurovoc.py")


def test_oj_reference_patterns_cover_every_stored_shape():
    import re
    from api.v2.legislative.eur_lex import oj_reference_patterns

    def hits(series, year, number, ref):
        act, dated, issue = oj_reference_patterns(series, year, number)
        return [bool(re.search(p, ref)) for p in (act, dated, issue)]

    assert hits("L", 2024, "1689", "OJ L, 2024/1689, 12.7.2024")[0]          # the AI Act, missed until 7 Oct
    assert not any(hits("L", 2024, "168", "OJ L, 2024/1689, 12.7.2024"))
    assert hits("L", 2026, "1778", "OJ L, 2026/1778, 2026")[0]
    assert hits("L", 2023, "150", "OJ L 150, 9.6.2023, p. 40")[1]
    assert not hits("L", 2022, "150", "OJ L 150, 9.6.2023, p. 40")[1]
    assert hits("L", 2023, "130", "OJ L 130/52, 16.5.2023")[1]
    assert hits("R", 2011, "272", "OJ R 272, 2011-10-18")[1]
    assert hits("C", 2022, "25", "C 025/2")[2]                                # zero-padded issue
    assert hits("L", 2016, "11I", "L 011I/1")[2]                              # supplement issue
    assert not hits("L", 2016, "11", "L 011I/1")[2]                           # L 11 is not L 11 I
    assert not hits("L", 2016, "1", "L 119/1")[2]


def test_oj_route_rejects_a_malformed_reference():
    from fastapi.testclient import TestClient
    from api.v1._deps import api_user_with_rate_limit
    from main import app
    from models.user import User

    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="t@example.com", role="admin")
    try:
        r = TestClient(app).get("/api/v2/legislative/eur-lex/oj/L%7C/2024/1689")
    finally:
        app.dependency_overrides.pop(api_user_with_rate_limit, None)
    assert r.status_code == 422 and r.json()["reason_code"] == "invalid_oj_reference"


def test_laws_filters_on_created_and_rejects_an_inverted_window(monkeypatch):
    """created_from/created_to were ignored: /laws returned all 19,136 laws (7 Oct 2026)."""
    from fastapi.testclient import TestClient
    from sqlalchemy.dialects import postgresql
    from api.v1._deps import api_user_with_rate_limit
    from core.database import get_db
    from main import app
    from models.user import User

    class Q:
        def __init__(self): self.filters = []
        def filter(self, *a): self.filters += a; return self
        def count(self): return 0
        def order_by(self, *a): return self
        def offset(self, n): return self
        def limit(self, n): return self
        def all(self): return []

    q = Q()
    monkeypatch.setattr("api.v1.laws.stable", lambda query, *a: query)
    app.dependency_overrides[api_user_with_rate_limit] = lambda: User(email="t@example.com", role="admin")
    app.dependency_overrides[get_db] = lambda: type("DB", (), {"query": lambda self, m: q})()
    try:
        c = TestClient(app)
        r = c.get("/api/v2/legislative/eur-lex/laws?created_from=2026-09-15&created_to=2026-09-15")
        bad = c.get("/api/v2/legislative/eur-lex/laws?created_from=2026-09-16&created_to=2026-09-15")
    finally:
        app.dependency_overrides.pop(api_user_with_rate_limit, None)
        app.dependency_overrides.pop(get_db, None)
    assert r.status_code == 200, r.text
    sql = " ".join(str(f.compile(dialect=postgresql.dialect())) for f in q.filters)
    assert "eu_laws.created_at >=" in sql and "eu_laws.created_at <=" in sql
    assert bad.status_code == 422 and bad.json()["reason_code"] == "invalid_date_range"
