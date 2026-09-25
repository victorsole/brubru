"""The eMeeting/research AI chains: non-Anthropic, open models first, paid OpenAI last.

25 Sep 2026: OpenAI ran out of credits and Mistral was rate-limited, and these
chains knew only those two (plus Hugging Face), so every legislative journey
failed in production while the chat chain's free lanes were idle.
"""
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
FILES = ["services/analysis/legislative_journey_service.py",
         "services/analysis/minutes_summary_service.py",
         "services/research/document_summariser.py"]


@pytest.mark.parametrize("path", FILES)
def test_chain_is_open_first_paid_last_no_anthropic(path):
    src = (BACKEND / path).read_text()
    m = re.search(r"for Provider in \(([^)]*)\)", src)
    assert m, f"{path}: no provider chain found"
    chain = [p.strip() for p in m.group(1).split(",") if p.strip()]
    assert "AnthropicProvider" not in chain
    assert chain[0] == "GeminiProvider"
    assert chain[-1] == "OpenAIProvider"
    assert len(chain) >= 4
