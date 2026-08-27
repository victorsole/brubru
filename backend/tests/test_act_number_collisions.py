"""
Regression tests for the acronym-collision family in answer post-processing.

Audit 27 Aug 2026 (P1/P2/P4). `_strip_contradicting_act_numbers` matched act
names with a RIGHT boundary only, so a short key fired inside a longer act name,
found the apposition belonging to the LONGER act, and deleted a TRUE act number.

The confirmed production case: "Resilience Act" (IMERA, 2024/2747) matching
inside "Cyber Resilience Act" (2024/2847), deleting 2024/2847 from every answer
that stated it -- fifteen days before CRA Article 14 starts applying.

Measured over all 546 entries with the production matching rule, twenty pairs
collide where the short and long names denote DIFFERENT acts. All twenty are
pinned here: this file exists so that re-widening the match, or adding a short
acronym that nests inside a longer one, fails loudly instead of silently
corrupting an answer.
"""

import pytest

from services.ai_service import AIService


# (short key, long act name, the long act's own number as the model would state it)
COLLISION_PAIRS = [
    ("Resilience Act", "Cyber Resilience Act", "2024/2847"),
    ("RIS", "ECRIS", "2019/884"),
    ("RIS", "ECRIS-TCN", "2019/816"),
    ("ECRIS", "ECRIS-TCN", "2019/816"),
    ("IAS", "ETIAS", "2018/1240"),
    ("IMA", "PRIMA", "2023/2848"),
    ("CLP", "SCLP", "2023/1719"),
    ("EMS", "PEMS", "2016/1718"),
    ("CMR", "ECMR", "2004/139"),
    ("ITS", "UCITS", "2024/911"),
    ("OTIF", "COTIF", "2018/1296"),
    ("ASAP", "BASAP", "2019/1727"),
    ("PAM", "IMDPAM", "2024/1331"),
    ("IPA", "IPA II", "2014/231"),
    ("IPA", "IPA III", "2021/1529"),
    ("SIS", "SIS II", "1987/2006"),
    ("ERIC", "DANUBIUS-ERIC", "2025/1238"),
    ("ERIC", "EMBRC-ERIC", "2018/272"),
    ("ERIC", "EHRI-ERIC", "2025/194"),
    ("ERIC", "MIRRI-ERIC", "2022/1204"),
]


@pytest.fixture(scope="module")
def svc():
    return AIService.__new__(AIService)


@pytest.mark.parametrize("short_key,long_name,true_number", COLLISION_PAIRS,
                         ids=[f"{s}-in-{l}" for s, l, _ in COLLISION_PAIRS])
def test_short_key_does_not_delete_the_longer_acts_true_number(
    svc, short_key, long_name, true_number
):
    """The long act's own, correct number must survive post-processing."""
    text = f"Under Article 14 of the {long_name} (Regulation (EU) {true_number}), obligations apply."
    out = svc._strip_contradicting_act_numbers(text)
    assert true_number in out, (
        f"{short_key!r} fired inside {long_name!r} and deleted its TRUE number "
        f"{true_number}. This is the Cyber Resilience Act defect class."
    )


def test_cra_the_confirmed_production_case(svc):
    """The exact sentence that shipped corrupted on 26 August 2026."""
    text = ("Under Article 14 of the Cyber Resilience Act (Regulation (EU) 2024/2847), "
            "manufacturers must report actively exploited vulnerabilities.")
    out = svc._strip_contradicting_act_numbers(text)
    assert "2024/2847" in out
    assert "2024/2747" not in out  # IMERA's number must never appear


def test_a_genuinely_contradicting_number_is_still_removed(svc):
    """P1 must not disarm the guard: a real contradiction is still stripped."""
    text = "The AI Act (Regulation (EU) 2019/785) sets out obligations."
    out = svc._strip_contradicting_act_numbers(text)
    assert "2019/785" not in out, "the invented apposition should have been dropped"
    assert "AI Act" in out


def test_linkifier_never_nests_a_link_inside_a_link_label(svc):
    """P4: an acronym inside an existing link LABEL must not be linked again."""
    already = ("Under Article 14 of the [Cyber Resilience Act]"
               "(https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32024R2847), "
               "manufacturers must report.")
    out = svc._linkify_legislation(already)
    import re
    nested = re.search(r'\[[^\]\[]*\[[^\]]+\]\([^)]+\)\s*\]\([^)]+\)', out)
    assert nested is None, f"nested link produced: {out[:200]}"
    assert out.count("](https://eur-lex.europa.eu") == 1


def test_full_pipeline_keeps_the_cra_number_and_links_the_right_act(svc):
    """End to end: strip then linkify, the shape a user actually receives."""
    text = ("Under Article 14 of the Cyber Resilience Act (Regulation (EU) 2024/2847), "
            "manufacturers must report.")
    out = svc._linkify_legislation(svc._strip_contradicting_act_numbers(text))
    assert "32024R2847" in out, "must link the Cyber Resilience Act"
    assert "32024R2747" not in out, "must never link IMERA here"


def test_citable_citations_bounds_to_the_named_set(svc):
    """P3: the orphan guard must bound against what the model was SHOWN."""
    citations = [{"id": i, "title": f"Source {i}"} for i in range(1, 64)]
    citable = svc._citable_citations(citations)
    assert len(citable) == svc._MAX_LISTED_SOURCES == 20

    # The 26 Aug witness: 63 citations, 20 named, the model cited [60].
    stripped = svc._strip_orphan_citations("The Council decides quotas [60].", citable)
    assert "[60]" not in stripped, "a marker above the named set must be stripped"


def test_sources_block_does_not_invite_uncited_sources(svc):
    """P3: the 'and N further source(s)' invitation must be gone."""
    citations = [{"id": i, "title": f"Source {i}"} for i in range(1, 64)]
    block = svc._format_sources_block(citations)
    assert "further source" not in block
    assert "not listed here" not in block
    assert block.count("\n") == svc._MAX_LISTED_SOURCES  # header + 20 lines


def test_a_second_bare_mention_is_not_claimed_by_a_shorter_acronym(svc):
    """
    The real mechanism behind the 26 August nested link, found by probing
    PRODUCTION after the first fix had already shipped and passed its tests.

    `count=1` links only the FIRST occurrence of an acronym, so a second mention
    of "Cyber Resilience Act" stays bare. The shorter key "Resilience Act" then
    matched that bare occurrence and linked it to IMERA. Masking existing links
    could not help: at that position there is no link to mask.

    A longer acronym now claims every span it matches, linked or not.
    """
    text = ("Under Article 14 of the Cyber Resilience Act, manufacturers must report. "
            "You can track the implementation of the Cyber Resilience Act in "
            "My Tracked Files.")
    out = svc._linkify_legislation(svc._strip_contradicting_act_numbers(text))
    assert "32024R2847" in out
    assert "32024R2747" not in out, "the second bare mention was claimed by 'Resilience Act'"
    assert out.count("](https://eur-lex.europa.eu") == 1, "count=1 semantics must survive"


@pytest.mark.parametrize("short_key,long_name,_num", COLLISION_PAIRS,
                         ids=[f"{s}-in-{l}" for s, l, _ in COLLISION_PAIRS])
def test_no_collision_pair_mislinks_a_repeated_mention(svc, short_key, long_name, _num):
    """Same trap, swept across all twenty pairs rather than the CRA alone."""
    text = f"The {long_name} matters. Later we mention the {long_name} again."
    out = svc._linkify_legislation(text)
    import re
    # Whatever gets linked, the label must never be the SHORT key standing alone
    # where the longer name is what the sentence actually says.
    for m in re.finditer(r'\[([^\]]+)\]\(https://eur-lex[^)]*\)', out):
        label = m.group(1).replace('**', '')
        if label == short_key and short_key != long_name:
            raise AssertionError(
                f"{short_key!r} linked inside a sentence naming {long_name!r}: {out[:180]}"
            )
