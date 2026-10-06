"""Council Watch shows the Council's own register (28 Sep 2026)."""
import asyncio
from types import SimpleNamespace

import pytest

import api.council_watch as cw
from core.database import SessionLocal
from models.user import User


@pytest.fixture(scope="module")
def db():
    s = SessionLocal()
    yield s
    s.close()


def _user(db, email):
    u = db.query(User).filter(User.email.ilike(email)).first()
    if not u:
        pytest.skip(f"{email} not in this database")
    return u


@pytest.mark.live
def test_lens_is_selective_and_differs_by_user(db):
    everything = cw._register_items(db, None, False, None)
    if len(everything) < 100:
        pytest.skip("too few register documents to judge selectivity")
    a = cw._register_items(db, _user(db, "m.pazicky@aurubis.com"), True, None)
    b = cw._register_items(db, _user(db, "planaguma@connecteurope.org"), True, None)
    assert 0 < len(a) < 0.6 * len(everything)          # was 100% before the fix ("sme" in "assessment")
    assert {x["reference"] for x in a} != {x["reference"] for x in b}


@pytest.mark.live
def test_titles_carry_no_page_furniture(db):
    for it in cw._register_items(db, None, False, None):
        assert "Also available in" not in it["title"]


def test_summary_falls_back_when_hugging_face_fails(monkeypatch):
    async def hf_fails(*a, **k):
        raise RuntimeError("402")
    monkeypatch.setattr("services.ai.huggingface_service.get_huggingface_service",
                        lambda: SimpleNamespace(chat_completion=hf_fails))
    import services.ai.multi_provider_service as mps

    class Lane:
        is_available = True
        async def generate(self, **k):
            return SimpleNamespace(message="A working party meets on CBAM downstream goods.")
    monkeypatch.setattr(mps, "CerebrasProvider", Lane)
    cw._SUM_CACHE.clear()
    r = asyncio.run(cw.summarise(cw.SummariseRequest(title="AHWP CBAM", kind="register", lang="en"),
                                 user=SimpleNamespace(subscription_tier="blue", role="user")))
    assert "CBAM" in r["summary"]
