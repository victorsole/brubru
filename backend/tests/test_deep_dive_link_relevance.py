"""An appended deep-dive link must be about the question (24 Sep 2026).

_append_deep_dive_link() matched ANY slug token against the ANSWER, so
/european-innovation-act/ ("european") landed on EU-Israel and FDI answers and
the batteries canon on an End-of-Life Vehicles answer. The fixture holds the 27
real production answers that carried an appended link since 1 Aug 2026, each
labelled by hand: relevant to the question, or not.
"""
import json
from pathlib import Path

import pytest

from services.ai_service import AIService

CASES = json.loads(
    (Path(__file__).parent / "fixtures" / "deep_dive_link_cases_2026_09_24.json").read_text()
)


def _append(message, url, query):
    ctx = f"Brubru deep-dive: {url}"
    return AIService._append_deep_dive_link(None, message, ctx, query)


def test_no_irrelevant_link_is_appended_on_real_cases():
    wrong = [c["url"] + " <- " + c["query"][:60] for c in CASES
             if not c["relevant"] and c["url"] in _append(c["answer"], c["url"], c["query"])]
    assert wrong == []


def test_most_relevant_links_survive():
    kept = sum(1 for c in CASES
               if c["relevant"] and c["url"] in _append(c["answer"], c["url"], c["query"]))
    relevant = sum(1 for c in CASES if c["relevant"])
    assert kept >= relevant - 2, (kept, relevant)


@pytest.mark.parametrize("query,url,expect", [
    ("Has the European Commission proposed suspending the EU-Israel Association Agreement?",
     "https://brubru.beresol.eu/european-innovation-act/", False),
    ("What is the European Innovation Act?",
     "https://brubru.beresol.eu/european-innovation-act/", True),
    ("How many data points must a battery passport carry?",
     "https://brubru.beresol.eu/eucanon/2023-1542_batteries/index.html", True),
    ("What changed today for vehicles under the End-of-Life Vehicles Regulation?",
     "https://brubru.beresol.eu/eucanon/2023-1542_batteries/index.html", False),
    ("What does Article 10 of the Affordable Housing Act require?",
     "https://brubru.beresol.eu/affordable-housing-act/", True),
    ("What is EU Inc.?", "https://brubru.beresol.eu/eu-inc/index.html", True),
    ("Qu'est-ce que le règlement GDPR impose ?",
     "https://brubru.beresol.eu/eucanon/2016-679_gdpr/ca.html", True),
])
def test_targeted(query, url, expect):
    answer = ("The European Commission and the Council are involved. " + query
              + " The GDPR applies to personal data.")
    assert (url in _append(answer, url, query)) is expect


def test_non_english_question_falls_back_to_the_answer():
    url = "https://brubru.beresol.eu/affordable-housing-act/"
    ans = "La proposta d'Affordable Housing Act de la Comissió estableix..."
    assert url in _append(ans, url, "Què diu la llei d'habitatge assequible?")
    assert url not in _append("La Comissió ha proposat...", url,
                              "Què diu la llei d'habitatge assequible?")
