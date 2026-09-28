"""Consultation stances get the chat chain's open-model lanes (28 Sep 2026).

10,947 substantive responses sat at 'pending' because Qwen direct had no key, HF no
credits and neither local model loads on Railway: the Stakeholder Map coloured none.
"""
import asyncio

import services.positions.stance_extractor as se


class _Resp:
    def __init__(self, message):
        self.message = message


def _provider(name, ok, calls):
    class P:
        is_available = True

        async def generate(self, **_):
            calls.append(name)
            if not ok:
                raise RuntimeError("429")
            return _Resp('{"stance": "amend", "summary": "Asks for an SME exemption."}')
    P.__name__ = name
    return P


def _patch(monkeypatch, behaviour, calls):
    import services.ai.multi_provider_service as mps
    for name, ok in behaviour.items():
        monkeypatch.setattr(mps, name, _provider(name, ok, calls))
    monkeypatch.setenv("SKIP_HF_STANCE", "1")
    monkeypatch.delenv("QWEN_API_KEY", raising=False)


TEXT = "We welcome the proposal but ask that SMEs be exempted from the reporting obligation."


def test_free_lanes_first_then_paid(monkeypatch):
    calls = []
    _patch(monkeypatch, {"CerebrasProvider": False, "GeminiProvider": False,
                         "MistralProvider": False, "ScalewayProvider": True}, calls)
    r = asyncio.run(se.extract_stance(TEXT, "SMEunited", "EU Inc", local=False))
    assert r["stance"] == "amend" and r["engine"] == "Scaleway"
    assert calls == ["CerebrasProvider", "GeminiProvider", "MistralProvider", "ScalewayProvider"]


def test_free_only_never_calls_the_paid_lane(monkeypatch):
    calls = []
    _patch(monkeypatch, {"CerebrasProvider": False, "GeminiProvider": False,
                         "MistralProvider": False, "ScalewayProvider": True}, calls)
    r = asyncio.run(se.extract_stance(TEXT, "SMEunited", "EU Inc", allow_paid=False, local=False))
    assert r["stance"] == "pending" and "ScalewayProvider" not in calls


def test_first_free_success_stops_the_chain(monkeypatch):
    calls = []
    _patch(monkeypatch, {"CerebrasProvider": True, "GeminiProvider": True,
                         "MistralProvider": True, "ScalewayProvider": True}, calls)
    r = asyncio.run(se.extract_stance(TEXT, "SMEunited", "EU Inc", local=False))
    assert r["engine"] == "Cerebras" and calls == ["CerebrasProvider"]


def test_unparseable_output_is_not_a_stance(monkeypatch):
    assert se._parse_llm("I think they support it") is None
    assert se._parse_llm('{"stance": "loves it"}') is None
