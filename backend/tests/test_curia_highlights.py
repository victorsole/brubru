"""The Court's #ECJHighlights post becomes dated lines, with the Mastodon spacing stripped (3 Nov 2026)."""
import datetime as dt
import pathlib
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
sys.path.insert(0, _REPO_ROOT + "/backend")
sys.path.insert(0, _REPO_ROOT + "/backend/scripts")

from sync_curia_highlights import parse_post  # noqa: E402

POST = ("# ECJHighlights ⚖️ 03/11 (O): Can # AI chatbots reproduce parts of news articles? 🇭🇺 (C-250/25) "
        "⚖️ 05/11 (J): Liquid detergent packaging that looks like a drink 🇸🇪 (C-395/25) "
        "⚖️ 05/11 (J): # CBD products and organic certification 🇫🇷 (C-495/25)")


def test_reads_every_line():
    rows = parse_post(POST, dt.date(2026, 10, 30))
    assert [(r["date"].isoformat(), r["kind"], r["case"]) for r in rows] == [
        ("2026-11-03", "O", "C-250/25"), ("2026-11-05", "J", "C-395/25"), ("2026-11-05", "J", "C-495/25")]
    assert rows[0]["what"] == "Can AI chatbots reproduce parts of news articles?"
    assert rows[2]["what"] == "CBD products and organic certification"


def test_a_january_line_posted_in_december_is_next_year():
    rows = parse_post("# ECJHighlights ⚖️ 08/01 (J): A case (C-1/26)", dt.date(2026, 12, 18))
    assert rows[0]["date"] == dt.date(2027, 1, 8)


def test_a_post_with_no_lines_gives_nothing():
    assert parse_post("Could your next career move be at the # ECJ ?", dt.date(2026, 11, 2)) == []
