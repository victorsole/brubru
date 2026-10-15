"""A news body is the article, not the site's cookie banner (15 Oct 2026).

67 stored institutional news bodies held a cookie banner (EUIPO 34, Commission 13): the
sites put it inside the page's main content, which the extractor keeps."""
from scripts.fetch_institutional_news_bodies import _cut_cookie_banner


def test_the_commission_banner_goes_even_across_line_breaks():
    page = ("An official website of the European Union How do you know?\nThis site uses cookies. Visit our\n"
            "cookies policy page\nor click the link in any footer for more information and to change your "
            "preferences.\nAccept all cookies\nAccept only essential cookies\nRecord low coal share in EU electricity")
    assert _cut_cookie_banner(page) == "Record low coal share in EU electricity"


def test_the_euipo_and_eib_banners_go_and_the_article_stays():
    euipo = ("The modernised EU design framework applies. This site uses cookies to offer you a better browsing "
             "experience, including for anonymized analytics. Find out more about how we use cookies. No thanks, "
             "only essential cookies Accept all cookies")
    assert _cut_cookie_banner(euipo) == "The modernised EU design framework applies."
    eib = ("The EIB signs a loan. This form is protected by reCAPTCHA and the Google Privacy Policy and Terms of "
           "Service apply. Our website uses anonymised cookies to give you the best browser experience and to "
           "collect aggregated statistics. This does not include online advertising cookies. Accept all cookies "
           "Refuse non essential cookiesManage cookies")
    assert _cut_cookie_banner(eib).startswith("The EIB signs a loan.") and "cookies" not in _cut_cookie_banner(eib)


def test_an_article_about_cookies_keeps_its_words():
    txt = "The Commission fined a firm for accepting cookies without consent; users could accept all cookies."
    assert _cut_cookie_banner(txt) == txt
