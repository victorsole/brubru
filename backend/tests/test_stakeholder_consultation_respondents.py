"""Organisations that answered the Commission's consultation appear on the file's map.

25 Sep 2026: the map showed only organisations that met MEPs, so the 41 trade
unions that answered the EU Inc. consultation were invisible. Real database;
depends on sync_consultation_feedback having stored EU Inc. (initiative 14674).
"""
import pytest

from core.database import SessionLocal
from models.legislative_train import LegislativeCarriage
from services.strategy import stakeholder_map as sm

EU_INC = "2026/0074(COD)"


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    yield s
    s.close()


def test_file_map_carries_respondents_across_types(db):
    c = db.query(LegislativeCarriage).filter_by(oeil_procedure_ref=EU_INC).first()
    g = sm.build_file_graph(db, c, [], deep=True)
    fnode = next(n for n in g.nodes.values() if n["type"] == "file")
    assert fnode["consultation"]["respondents"] > 1000
    resp = [n for n in g.nodes.values() if (n.get("meta") or {}).get("kind") == "consultation"]
    assert 0 < len(resp) <= sm._MAX_RESPONDENTS
    assert "Trade union" in {n["sublabel"] for n in resp}
    assert len({n["sublabel"] for n in resp}) >= 5          # round-robin across types
    assert all(n.get("stance") in (None, "support", "oppose", "amend", "mixed") for n in resp)
    rels = {e["rel"] for e in g.edges if e["source"] in {n["id"] for n in resp}}
    assert rels == {"responded_to_consultation"}


def test_overview_mode_leaves_respondents_out(db):
    c = db.query(LegislativeCarriage).filter_by(oeil_procedure_ref=EU_INC).first()
    g = sm.build_file_graph(db, c, [], deep=False)
    assert not any((n.get("meta") or {}).get("kind") == "consultation" for n in g.nodes.values())


def test_count_label():
    assert sm._count_label(3, "Company") == "3 companies"
    assert sm._count_label(1, "Trade union") == "1 trade union"
    assert sm._count_label(71, "NGO") == "71 NGOs"
    assert sm._count_label(23, "Public authority") == "23 public authorities"
