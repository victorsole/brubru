"""fetch_x keeps an account's own timeline entries, never the tweets nested inside them (3 Nov 2026)."""
import json
import pathlib
import sys
from unittest import mock

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT + "/backend")

from services.social import post_fetcher  # noqa: E402


def _page(entries):
    data = {"props": {"pageProps": {"timeline": {"entries": entries}}}}
    return ('<script id="__NEXT_DATA__" type="application/json">' + json.dumps(data) + "</script>").encode()


def _tweet(tid, text, user, **extra):
    return {"id_str": tid, "full_text": text, "user": {"screen_name": user},
            "created_at": "Mon Nov 02 09:29:00 +0000 2026", "lang": "pl", "favorite_count": 10, "retweet_count": 1,
            "reply_count": 0, **extra}


def _fetch(entries):
    resp = mock.MagicMock()
    resp.read.return_value = _page(entries)
    with mock.patch("urllib.request.urlopen", return_value=resp):
        return post_fetcher.fetch_x("BZdrojewski", n=20)


def test_retweet_keeps_only_the_outer_row_flagged_with_its_author():
    inner = _tweet("111", "Rozwiazanie konfliktu", "donaldtusk")
    outer = _tweet("222", "RT @donaldtusk: Rozwiazanie konfliktu", "BZdrojewski", retweeted_status=inner)
    rows = _fetch([{"content": {"tweet": outer}}])
    assert [r["platform_post_id"] for r in rows] == ["222"]
    assert rows[0]["is_repost"] is True
    assert rows[0]["original_author"] == "donaldtusk"


def test_a_quoted_tweet_is_not_stored_as_this_accounts_post():
    quoted = _tweet("333", "Someone else said this", "someone")
    outer = _tweet("444", "My comment on it", "BZdrojewski", quoted_status=quoted, is_quote_status=True)
    rows = _fetch([{"content": {"tweet": outer}}])
    assert [r["platform_post_id"] for r in rows] == ["444"]
    assert rows[0]["is_repost"] is False


def test_an_own_post_stays_own():
    rows = _fetch([{"content": {"tweet": _tweet("555", "My own words", "BZdrojewski")}}])
    assert rows[0]["is_repost"] is False and rows[0]["original_author"] is None
