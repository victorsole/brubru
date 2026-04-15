"""Unit tests for the canonical v1 response envelope."""

from api.v1._envelope import build_envelope, PaginatedResponse


def test_single_page_when_total_equals_limit():
    env = build_envelope([1, 2, 3], total=3, page=1, limit=3)
    assert env.total == 3
    assert env.pages == 1
    assert env.page == 1
    assert env.has_more is False
    assert env.next_page is None
    assert env.remaining_pages == 0


def test_multi_page_middle():
    env = build_envelope([1] * 10, total=95, page=3, limit=10)
    assert env.pages == 10
    assert env.has_more is True
    assert env.next_page == 4
    assert env.remaining_pages == 7


def test_last_page():
    env = build_envelope([1, 2, 3, 4, 5], total=95, page=10, limit=10)
    assert env.pages == 10
    assert env.has_more is False
    assert env.next_page is None
    assert env.remaining_pages == 0


def test_empty_result():
    env = build_envelope([], total=0, page=1, limit=20)
    assert env.pages == 0
    assert env.has_more is False
    assert env.data == []


def test_meta_attribution_is_present():
    env = build_envelope([1], total=1, page=1, limit=20)
    assert env.meta.powered_by == "Brubru"
    assert env.meta.source == "brubru.beresol.eu"


def test_filters_echoed_back():
    from datetime import date, datetime

    env = build_envelope(
        [1], total=1, page=1, limit=20,
        published_from=date(2026, 1, 1),
        published_to=date(2026, 1, 31),
        updated_from=datetime(2026, 1, 1, 0, 0, 0),
    )
    assert env.published_from.isoformat() == "2026-01-01"
    assert env.published_to.isoformat() == "2026-01-31"
    assert env.updated_from is not None
