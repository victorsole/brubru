"""A rendered single-page app hands back the whole portal before the article.

All 788 Funding & Tenders Portal rows came back as ~2,300 characters that opened with
a cookie banner and the portal's left navigation, then the piece. That passes every
length check while being furniture, which is the failure this repo has hit before: a
length check is not a content check.

Chasing each portal's nav labels does not generalise, and the match is a prefix test,
so a token like "en" would eat "Energy...". The row's own title is the reliable marker.
"""
from scripts.fetch_institutional_news_bodies import _cut_to_headline

TITLE = "Horizon Europe info day - Cluster 5: Climate, Energy and Mobility"
FURNITURE = (". Visit our cookies policy page or click the link in any footer.\n"
             "Accept all cookies\nAccept only essential cookies\n"
             "EU Funding & Tenders Portal\nSign in\nEN\nHome\nFunding\n")


def test_the_portal_furniture_is_dropped():
    body = (FURNITURE + TITLE + "\n24 September 2026\n\n"
            + "The programme will include real prose and plenty of it. " * 8)
    out = _cut_to_headline(body, TITLE)
    assert out.startswith(TITLE)
    assert "Accept all cookies" not in out


def test_the_last_occurrence_wins_so_a_breadcrumb_does_not_keep_the_nav():
    body = ("Home\n" + TITLE + "\nSign in\n" + TITLE + "\n"
            + "The real article follows here with plenty of genuine text. " * 8)
    out = _cut_to_headline(body, TITLE)
    assert out.startswith(TITLE)
    assert "Sign in" not in out


def test_a_page_that_only_repeats_its_title_is_not_emptied():
    body = FURNITURE + TITLE
    assert _cut_to_headline(body, TITLE) == body


def test_a_body_without_its_title_is_untouched():
    body = "An article whose headline never appears in the extracted text at all, " * 5
    assert _cut_to_headline(body, TITLE) == body


def test_no_title_is_untouched():
    assert _cut_to_headline("some body text", None) == "some body text"


def test_a_short_title_is_not_used_as_a_marker():
    """Too short a needle would cut at a coincidence."""
    body = "News\nand then a long article body that must survive entirely intact here."
    assert _cut_to_headline(body, "News") == body
