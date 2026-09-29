"""A guessed item_type must never overwrite one that was read.

GovClipping saw the same item id served under kind=press_release on one run and
kind=news on another (23, 25 and 29 Sep 2026). kind is derived from item_type, and the
scraper always supplies a value: the item's own listing metadata when the regex matches,
the source's default_type when it does not. The listing markup differs between the httpx
and the browser fetch path (98 vs 148 type-bearing strings on the same page), so the same
row was typed from its metadata on one sync and from the default on the next, and the
writer overwrote unconditionally.

For a partner keying search documents on kind, a flip creates a second document that
nothing deletes, and their write is refused as an identity collision.
"""
import importlib.util
import pathlib

BACKEND = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "dg_news_scraper", BACKEND / "services" / "scrapers" / "dg_news_scraper.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_metadata_naming_a_type_is_certain():
    assert mod._item_type_is_certain("Press release") is True
    assert mod._item_type("Press release", "news") == "press"
    assert mod._item_type_is_certain("News article") is True
    assert mod._item_type("News article", "press") == "news"


def test_absent_or_unhelpful_metadata_is_NOT_certain():
    """This is the case that caused the flip: a default is a guess."""
    assert mod._item_type_is_certain(None) is False
    assert mod._item_type_is_certain("") is False
    assert mod._item_type_is_certain("Read more") is False
    # It still yields a value for a NEW row, it is simply not allowed to overwrite.
    assert mod._item_type(None, "news") == "news"


def test_the_writer_refuses_a_guess_and_accepts_a_reading():
    """Mirrors the branch in scripts/sync_dg_news.py."""
    class Row:
        item_type = "press"

    def write(existing, incoming):
        if (incoming.get("item_type") and incoming.get("item_type_certain")
                and existing.item_type != incoming["item_type"]):
            existing.item_type = incoming["item_type"]
            return True
        return False

    row = Row()
    assert write(row, {"item_type": "news", "item_type_certain": False}) is False
    assert row.item_type == "press", "a guess overwrote a stored reading"
    assert write(row, {"item_type": "news", "item_type_certain": True}) is True
    assert row.item_type == "news", "a genuine reclassification must still apply"
