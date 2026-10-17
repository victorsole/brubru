"""Every target in legislation_acronyms.json must be the act its key names (17 Oct 2026).

The chat turns these keys into EUR-Lex links and, in its STEP 0, rewrites a link whose text is
an entry's full name to that entry's CELEX. A Cellar check of every CELEX found 68 that do not
exist: 'PACT Act' and 'TDI' made the chat rewrite correct links to the Packaging and Packaging
Waste Regulation and the Tax Dispute Resolution Directive into 404s, and 112 ECB act numbers
pointed at a CELEX derived from the OJ number or at the act they amend.
"""
import json
import re
from pathlib import Path
from unittest.mock import patch

import pytest

from services.ai_service import AIService

DB = Path(__file__).resolve().parents[1] / "knowledge_base" / "institutions" / "legislation_acronyms.json"
DATA = json.loads(DB.read_text())
ACRONYMS = DATA["acronyms"]
ECB_TAG = re.compile(r"\(ECB/\d{4}/\d+\)")
# issued by the ECB: "Decision (EU) 2015/286 of the European Central Bank ..." or, in older titles,
# "European Central Bank Regulation (EC) No 2157/1999 ..."
ECB_ACT = re.compile(r"^(?:European Central Bank (?:Decision|Regulation|Guideline|Recommendation)\b"
                     r"|(?:Decision|Regulation|Guideline|Recommendation|Opinion)"
                     r"(?: \((?:EU|EC)\))?(?: No)?[\s\d/]*of the European Central Bank)", re.I)


@pytest.fixture(scope="module")
def service():
    with patch.object(AIService, "__init__", lambda self: None):
        return AIService()


@pytest.mark.parametrize("key", ["PACT Act", "TDI", "ESMIG", "ECB/2020/33", "ECB/2014/13", "ECB/2014/19"])
def test_the_entries_with_no_act_behind_them_are_gone(key):
    assert key not in ACRONYMS


@pytest.mark.parametrize("name,celex", [
    ("Packaging and Packaging Waste Regulation", "32025R0040"),
    ("Tax Dispute Resolution Directive", "32017L1852"),
])
def test_a_correct_link_is_no_longer_rewritten_to_a_missing_act(service, name, celex):
    text = f"See the [{name}](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex})."
    assert service._linkify_legislation(text) == text


def test_every_ecb_number_points_at_the_ecb_act_that_carries_it():
    keys = [k for k in ACRONYMS if re.fullmatch(r"ECB/\d{4}/\d+", k)]
    assert len(keys) > 200
    wrong = []
    for k in keys:
        title = ACRONYMS[k]["full_title"].replace("\xa0", " ")
        tags = [t[1:-1] for t in ECB_TAG.findall(title)]
        # its own number is the last tag of the title; a few headings carry it first
        if not ECB_ACT.match(title) or k not in (tags[-1:] + tags[:1]):
            wrong.append((k, ACRONYMS[k]["celex"], title[-90:]))
    assert wrong == []


def test_ecb_numbers_do_not_share_an_act():
    seen = {}
    for k, v in ACRONYMS.items():
        if re.fullmatch(r"ECB/\d{4}/\d+", k):
            assert v["celex"] not in seen, f"{k} and {seen.get(v['celex'])} -> {v['celex']}"
            seen[v["celex"]] = k


def test_a_parenthesised_celex_survives_the_whole_post_processing(service):
    out = service._post_process_text("The ECB pays out banknote income under ECB/2014/49.", citations=[],
                                     context_str="", user_query="ECB banknote income")
    assert "(https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32014D0049(01))" in out


def test_the_entry_count_is_the_file_count():
    assert DATA["metadata"]["total_entries"] == len(ACRONYMS)
