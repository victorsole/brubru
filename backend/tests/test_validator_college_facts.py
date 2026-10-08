"""
The validator is grounded in the College of Commissioners (audit 8 Oct 2026).

A3: the judge scored a CORRECT answer critical because the context named the
refinery-dialogue chairs by surname ("Jorgensen and Kubilius") and the answer
added their given names and portfolios. A4: a generator "corrected" the guide's
Agriculture Commissioner Hansen into Wojciechowski. Both come from the judge
having no reference for who sits in the College.

The deterministic half (the reference is built, rendered and cited by the
prompt) runs everywhere. The judge itself is an LLM, so its verdicts are
`live` tests: run them locally with `pytest -m live tests/test_validator_college_facts.py`.
"""

import asyncio
import json
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from services.ai import response_validator as rv  # noqa: E402


def test_college_facts_cover_the_whole_college():
    facts = rv._college_facts()
    college = json.loads((BACKEND / "knowledge_base/institutions/commissioners.json").read_text())["college"]
    expected = 1 + len(college["executive_vice_presidents"]) + len(college["commissioners"])
    assert facts.count("\n") + 1 == expected == 27
    for line in (
        "Christophe Hansen (Luxembourg): Agriculture and Food",
        "Dan Jørgensen (Denmark): Energy and Housing",
        "Andrius Kubilius (Lithuania): Defence and Space",
    ):
        assert line in facts


def test_user_message_carries_the_college_and_the_system_prompt_cites_it():
    msg = rv._build_user_message("q", "ctx", "resp")
    assert "EU COMMISSION COLLEGE" in msg
    assert "Andrius Kubilius (Lithuania)" in msg
    # the rule that makes the list usable in BOTH directions
    assert "COLLEGE FACTS ARE GROUND TRUTH" in rv._VALIDATOR_SYSTEM
    assert "DIFFERENT person for a portfolio" in rv._VALIDATOR_SYSTEM


def test_college_facts_fail_soft(monkeypatch):
    monkeypatch.setattr(rv, "_COLLEGE_FACTS_CACHE", None)
    monkeypatch.setattr(rv, "Path", lambda *a, **k: (_ for _ in ()).throw(OSError("unreadable")))
    assert rv._college_facts() == ""
    assert "EU COMMISSION COLLEGE" not in rv._build_user_message("q", "ctx", "resp")
    monkeypatch.setattr(rv, "_COLLEGE_FACTS_CACHE", None)  # do not leak the empty cache


_GUIDE_CTX = (
    "Von der Leyen announced a strategic dialogue on European refineries chaired by Commissioners "
    "Jørgensen and Kubilius. Agriculture Commissioner Hansen said attacks on shipping in the Black Sea "
    "threaten grain exports."
)
_Q_REF = "What did von der Leyen announce on refineries?"
_Q_BS = "What has the EU said about the attacks on ships in the Black Sea?"
_CASES = [
    # (label, query, response, must_be_clean)
    ("given names and portfolios added to surnames the context gives", _Q_REF,
     "She announced a dialogue chaired by Dan Jørgensen (Energy) and Andrius Kubilius (Defence and Space).", True),
    ("given name added to Hansen", _Q_BS,
     "Agriculture Commissioner Christophe Hansen said attacks on shipping in the Black Sea threaten grain exports.", True),
    ("a different surname replaces the one the context gives", _Q_BS,
     "Agriculture Commissioner Janusz Wojciechowski said attacks on shipping in the Black Sea threaten grain exports.", False),
    ("listed Commissioners with swapped portfolios", _Q_REF,
     "She announced a dialogue chaired by Dan Jørgensen (Defence and Space) and Andrius Kubilius (Energy).", False),
    ("a former Commissioner presented as a current chair", _Q_REF,
     "She announced a dialogue chaired by Frans Timmermans (Climate Action) and Andrius Kubilius.", False),
]


@pytest.mark.live
def test_judge_verdicts_with_the_college():
    """All five cases in ONE event loop: the provider clients are bound to the loop that
    created them, so one asyncio.run per case turns every later case into connection
    errors, which the validator fails soft into a clean-looking pass."""
    validator = rv.ResponseValidator()
    if not validator.is_available:
        pytest.skip("no AI provider configured")

    async def run_all():
        return [await validator.validate(q, _GUIDE_CTX, response) for _, q, response, _ in _CASES]

    results = asyncio.run(run_all())
    problems = []
    for (label, _, _, must_be_clean), result in zip(_CASES, results):
        # An unjudged result is not a verdict: it must never count as a pass.
        if result.error:
            problems.append(f"NOT JUDGED ({result.error}): {label}")
        elif must_be_clean and result.severity == "critical":
            problems.append(f"false positive: {label}: {result.violations}")
        elif not must_be_clean and result.severity != "critical":
            problems.append(f"missed a wrong-person claim: {label}")
    assert not problems, "\n".join(problems)
