"""What may be stored as an article body from a rendered Europa page, and what may not.

Validated against four real captures on 25 September 2026: a DG news page (6,501 characters
of article), the SEDIA funding portal (no matching container), a trade listing page (3,053
characters of index that scored well on length and opened with no consent banner), and an
unrendered Angular shell. The shapes below encode those four cases.
"""
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from backend.services.news.rendered_article import (  # noqa: E402
    extract_article, is_app_shell, looks_like_chrome, looks_like_listing,
)

ARTICLE = ("European consumers, suppliers and retailers of home appliances are set to "
           "benefit from simplified rules on labelling. " * 12)


def _page(inner, wrapper='<div class="ecl-col-12">'):
    return f"<html><body><nav>Home News Contact</nav>{wrapper}{inner}</div></body></html>"


def test_an_article_is_extracted():
    text, html, reason = extract_article(_page(f"<p>{ARTICLE}</p>"))
    assert reason is None
    assert text.startswith("European consumers")
    assert len(text) > 400 and html


def test_an_unrendered_shell_is_refused():
    shell = "<html><body><app-root></app-root></body></html>"
    assert is_app_shell(shell)
    text, _, reason = extract_article(shell)
    assert text is None and "did not render" in reason


def test_a_listing_page_is_never_stored_as_an_article():
    listing = _page(
        "<p>Showing results 1 to 10 of 696</p>"
        + "".join(f"<p>News article 25 September 2026 Headline {i}</p>" for i in range(10)))
    text, _, reason = extract_article(listing)
    assert text is None, "an index of ten headlines is not an article"
    assert reason


def test_repeated_item_furniture_reads_as_a_listing():
    assert looks_like_listing("News article one. News article two. Read more. Read more.")
    assert not looks_like_listing(ARTICLE)


def test_a_consent_banner_is_not_a_body():
    assert looks_like_chrome("This site uses cookies. Visit our cookies policy page.")
    assert looks_like_chrome("Skip to main content EN Select your language")
    assert not looks_like_chrome(ARTICLE)


def test_a_card_is_too_short_to_be_an_article():
    text, _, reason = extract_article(_page("<p>Read the full story on our website.</p>"))
    assert text is None and "not an article" in reason


def test_the_longest_non_chrome_container_wins():
    """A page carries both a teaser card and the article; the article must win."""
    page = ("<html><body>"
            '<div class="ecl-col-3"><p>Short teaser card text here.</p></div>'
            f'<div class="ecl-col-9"><p>{ARTICLE}</p></div>'
            "</body></html>")
    text, _, reason = extract_article(page)
    assert reason is None and text.startswith("European consumers")


def test_an_article_mentioning_cookies_mid_text_is_kept():
    """The chrome test looks at the OPENING only: an article may discuss cookies."""
    body = ("The Commission adopted new rules today. " * 10
            + "The guidance explains how this site uses cookies for analytics. " * 5)
    text, _, reason = extract_article(_page(f"<p>{body}</p>"))
    assert reason is None and text.startswith("The Commission adopted")


def test_the_better_extractor_wins_per_template():
    """Neither extractor is right for every Europa template.

    extract_article knows the component library and refuses furniture; extract_html reads
    templates it has no selector for. On a real FRA case-law page extract_article found 287
    characters and extract_html found the whole 2,703-character record, so the fetcher runs
    both and keeps the longer body that passes the furniture checks. Measured 25 September:
    the fra/case_law slice went from 287 to 6,521 characters average once it did.
    """
    import sys as _sys

    _sys.path.insert(0, str(pathlib.Path(_REPO_ROOT, "backend", "scripts")))
    from fetch_institutional_news_bodies import _best_extraction

    long_body = "The Court held that the measure was proportionate. " * 60
    # A template with no article/main/ecl-col container: only extract_html reads it.
    page = f"<html><body><div class='field-item'><p>{long_body}</p></div></body></html>"
    text, _, reason = _best_extraction(page)
    assert reason is None, f"neither extractor read the page: {reason}"
    assert len(text) > 1200, f"kept only {len(text)} characters of a long record"


def test_a_listing_is_still_refused_by_both_extractors():
    """The best-of-two must not become a way for page furniture to get in."""
    import sys as _sys

    _sys.path.insert(0, str(pathlib.Path(_REPO_ROOT, "backend", "scripts")))
    from fetch_institutional_news_bodies import _best_extraction

    listing = ("<html><body><div class='view-content'><p>Showing results 1 to 10 of 696</p>"
               + "".join(f"<p>News article 25 September 2026 Headline {i}</p>" for i in range(12))
               + "</div></body></html>")
    text, _, reason = _best_extraction(listing)
    assert text is None, "an index page must not be stored as a body by either extractor"
