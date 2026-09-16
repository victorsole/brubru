"""is_sendable_address: addresses that can never receive mail must never be emailed.

Incident 16 September 2026: `joana-demo@demo.invalid` received the State of the Union
Brief and bounced, because reserved names were compared with the whole domain.
"""

import pytest

from services.daily_brief_email import is_sendable_address


@pytest.mark.parametrize("addr", [
    "joana-demo@demo.invalid",
    "someone@invalid",
    "fixture@api.test",
    "x@test",
    "x@box.localhost",
    "x@site.example",
    "v2_parl_1@example.com",
    "a@mail.example.org",
    "b@EXAMPLE.NET",
    "prospect+zeno-nl@brubru.beresol.eu",
    "prospect+someone@gmail.com",
    "info@brubru.beresol.eu",
    "trailing@demo.invalid.",
    "",
    None,
    "no-at-sign",
    "@nodomain.com",
    "nolocal@",
])
def test_unsendable(addr):
    assert is_sendable_address(addr) is False


@pytest.mark.parametrize("addr", [
    "hello@beresol.eu",
    "person@gmail.com",
    "Policy.Officer@Europarl.Europa.EU",
    "someone@testing.com",       # a real domain that merely starts with "test"
    "someone@contest.eu",        # ends in "test" without being the .test TLD
    "someone@example-firm.com",  # contains "example" but is not example.com
    "someone@invalidation.org",
])
def test_sendable(addr):
    assert is_sendable_address(addr) is True
