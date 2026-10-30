"""A provider that answers 402 (no credits) is skipped, not retried (27 Oct 2026: HF Qwen answered 402
three times per dossier, with 5 s and 10 s pauses, before every fallback: 9 minutes for one analysis,
and the precompute call outlived the edge, so the cron run went red)."""
import asyncio
import types

from services.analysis import legislative_journey_service as js


class _Hf:
    def __init__(self):
        self.calls, self.last_status = 0, None

    async def chat_completion(self, **kw):
        self.calls += 1
        self.last_status = 402
        return None


class _Gemini:
    name, MODEL, is_available = "Gemini", "gemini-test", True

    async def generate(self, **kw):
        return types.SimpleNamespace(message='{"summary": "ok"}')


def test_a_402_is_not_retried_and_hf_is_skipped_for_the_rest_of_the_run(monkeypatch):
    import services.ai.huggingface_service as hfmod
    import services.ai.multi_provider_service as mp
    hf = _Hf()
    monkeypatch.setattr(hfmod, "get_huggingface_service", lambda: hf)
    monkeypatch.setattr(js, "_build_messages", lambda *a, **k: ("system", [{"role": "user", "content": "x"}]))
    monkeypatch.setattr(js, "_parse_json", lambda raw: {"summary": "ok"} if raw else None)
    monkeypatch.setattr(js, "_HF_SKIP_UNTIL", 0.0)
    slept = []

    async def no_sleep(s):
        slept.append(s)
    monkeypatch.setattr(js.asyncio, "sleep", no_sleep)
    for name in ("GeminiProvider", "ScalewayProvider", "CerebrasProvider", "MistralProvider", "OpenAIProvider"):
        monkeypatch.setattr(mp, name, _Gemini)
    parsed, engine, _, err = asyncio.run(js._call_llm("2026/0001(COD)", True, []))
    assert (parsed, engine, err) == ({"summary": "ok"}, "Gemini", None)
    assert hf.calls == 1 and slept == []          # one call, no backoff
    asyncio.run(js._call_llm("2026/0002(COD)", True, []))
    assert hf.calls == 1                           # skipped on the next dossier
