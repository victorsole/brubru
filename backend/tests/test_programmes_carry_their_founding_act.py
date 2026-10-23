"""Each funding programme is dated by the Official Journal publication of the act that established it (23 Oct 2026).

document_date was null on all 56 programmes. The F&T Portal gives programmes no date, only a
programming period, so the date is the founding act's publication, read at Cellar (SPARQL,
publication_general_date_publication of the OJ issue) and written into the config with the act's
CELEX and title; the programming period is served and filterable, as the portal groups them.
"""
import json
import pathlib
import re
import sys
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from api.v1._deps import api_user_with_rate_limit  # noqa: E402
from core.database import get_db  # noqa: E402

PROGRAMMES = json.loads((BACKEND / "config" / "funding_programmes.json").read_text(encoding="utf-8"))["programmes"]


def test_every_programme_but_the_cfsp_names_a_dated_founding_act():
    undated = [p["acronym"] for p in PROGRAMMES if not p.get("founding_act")]
    assert undated == ["CFSP"] and PROGRAMMES[[p["acronym"] for p in PROGRAMMES].index("CFSP")]["founding_act_note"]
    for p in PROGRAMMES:
        act = p.get("founding_act")
        if not act:
            continue
        assert re.fullmatch(r"3\d{4}[RLD]\d{4}", act["celex"]), p["acronym"]
        assert re.fullmatch(r"(19|20)\d\d-\d\d-\d\d", act["published"]), p["acronym"]
        year = act["celex"][1:5]
        assert act["published"][:4] == year or year in act["title"], p["acronym"]   # published the year it is numbered


def _client():
    from api.v2.funding import funding_programmes as fp
    app = FastAPI()
    app.include_router(fp.router, prefix="/api/v2/funding")
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[api_user_with_rate_limit] = lambda: SimpleNamespace(id=1, role="admin")
    return TestClient(app)


def test_the_list_serves_the_date_the_act_and_the_period():
    r = _client().get("/api/v2/funding/programmes", params={"period": "2021-2027", "include_body": "true", "limit": 200})
    assert r.status_code == 200, r.text
    items = {i["acronym"]: i for i in r.json()["data"]}
    assert len(items) == 56 and all(i["period"] == "2021-2027" for i in items.values())
    he = items["Horizon Europe"]
    assert he["document_date"].startswith("2021-05-12")
    assert "Regulation (EU) 2021/695" in he["body_txt"] and "2021-05-12" in he["body_txt"]
    assert items["CFSP"]["document_date"] is None and "Article 41 TEU" in items["CFSP"]["body_txt"]


def test_an_unknown_period_returns_nothing():
    r = _client().get("/api/v2/funding/programmes", params={"period": "2014-2020"})
    assert r.status_code == 200 and r.json()["total"] == 0
