"""Legislative-file keyword matching in the chat context (30 Sep 2026).

Production answered "Why did the EU sanction Russian judges over Yabloko?" with
the legal basis of a DIFFERENT listing adopted the same day (the Ukrainian
children decision), because "over" matched "s-over-eignty" in that act's title
and the files were then ordered by last_updated, not relevance.
"""
import re

from services.ai.context_builder import carriage_query_patterns, carriage_relevance

STOP = {"what", "about", "over", "status"}

YABLOKO_2192 = ("Council Decision (CFSP) 2026/2192 of 28 September 2026 amending Decision "
                "(CFSP) 2024/1484 concerning restrictive measures in view of the situation in Russia")
CHILDREN_2185 = ("Council Decision (CFSP) 2026/2185 of 28 September 2026 amending Decision "
                 "2014/145/CFSP concerning restrictive measures in respect of actions undermining "
                 "or threatening the territorial integrity, sovereignty and independence of Ukraine")
BURUNDI_2197 = ("Council Decision (CFSP) 2026/2197 of 28 September 2026 amending Decision (CFSP) "
                "2015/1763 concerning restrictive measures in view of the situation in Burundi")


def _pg_to_py(patterns):
    """The SQL filter uses PostgreSQL \\y; check the same pattern in Python."""
    return [re.compile(p.replace(r"\y", r"\b"), re.IGNORECASE) for p in patterns]


def test_word_inside_another_word_does_not_match():
    # "over" is a stopword now, and even a non-stopword must match a word START.
    pats = carriage_query_patterns("over", set())  # not a stopword here
    assert pats, "the word must still produce a term"
    assert not any(rx.search("territorial integrity, sovereignty") for rx in _pg_to_py(pats[0]))
    assert carriage_relevance("territorial integrity, sovereignty", pats) == 0
    assert carriage_relevance("overseas countries", pats) == 1


def test_punctuation_is_stripped():
    pats = carriage_query_patterns("yabloko?", set())
    assert pats[0][0] == r"\y" + "yablok"


def test_demonym_matches_country():
    pats = carriage_query_patterns("russian ukrainian", set())
    assert carriage_relevance("the situation in Russia", pats) == 1
    assert carriage_relevance("independence of Ukraine", pats) == 1


def test_sanction_matches_restrictive_measures():
    pats = carriage_query_patterns("sanctions", set())
    assert carriage_relevance(YABLOKO_2192, pats) == 1


def test_yabloko_query_ranks_the_russia_act_above_the_ukraine_act():
    pats = carriage_query_patterns("why did the eu sanction russian judges over yabloko?", STOP)
    assert carriage_relevance(YABLOKO_2192, pats) > carriage_relevance(CHILDREN_2185, pats)
    # and the Ukraine act no longer matches the SQL filter through "over"
    only_over = carriage_query_patterns("over", STOP)
    assert only_over == []


def test_children_query_ranks_the_ukraine_act_first():
    pats = carriage_query_patterns(
        "why did the eu sanction people over the deportation of ukrainian children?", STOP)
    assert carriage_relevance(CHILDREN_2185, pats) > carriage_relevance(YABLOKO_2192, pats)


def test_burundi_query_ranks_burundi_first():
    pats = carriage_query_patterns("what sanctions did the council adopt against burundi?", STOP)
    scores = {n: carriage_relevance(t, pats) for n, t in
              [("burundi", BURUNDI_2197), ("russia", YABLOKO_2192), ("ukraine", CHILDREN_2185)]}
    assert max(scores, key=scores.get) == "burundi"


def test_short_and_stop_words_produce_no_terms():
    assert carriage_query_patterns("what is the status of the ai act?", STOP) == []
