"""U4 (10 Sep 2026): the founder's own accounts are not customers.

`victor@hellobo.eu` (Victor Solé Ferioli, CEO of Hellobo 2025 SL) and
`vsoleferioli@gmail.com` are the founder's. Hellobo 2025 SL is his own company.

The finding that prompted this was PARTLY WRONG and the correction matters: the
morning's analysis reported that victor@hellobo.eu "counts as a customer with 107
tracked items". It did not -- it was already internal via `is_trainer IS TRUE`.
The defect was in the hand-typed ad-hoc filter used for that analysis, and was
misattributed to the report. What the domain rule really adds is the three other
hellobo.eu rows, which are seeded test users.
"""
import pathlib
import re
import sys

import pytest

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
BACKEND = pathlib.Path(_REPO_ROOT) / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from scripts.user_activity_report import (  # noqa: E402
    INTERNAL_USER_SQL,
    SEEDED_TEST_USER_EMAILS_PENDING_DECISION,
)


def test_founder_accounts_are_internal():
    assert "'%@hellobo.eu'" in INTERNAL_USER_SQL
    assert "vsoleferioli@gmail.com" in INTERNAL_USER_SQL


def test_filter_does_not_swallow_real_customer_domains():
    """A blunt filter that caught a paying domain would erase real usage. These
    are live client domains and must never appear in the internal predicate."""
    for domain in ("terraqui.com", "ferrmed.com", "efpia.eu", "urv.cat",
                   "plataforma-llengua.cat", "downside-up.net", "gbsb.global",
                   "kinetiximpact.com"):
        assert domain not in INTERNAL_USER_SQL, (
            f"{domain} is a real client domain and must not be filtered as internal"
        )


def test_pending_test_users_are_really_in_the_seed_script():
    """The pending list must be DERIVED from the seed script, not invented.

    An allowlist typed from memory is not a check. If a name here is not actually
    seeded, the comment beside it is fiction and the decision it asks Victor for
    is based on nothing.
    """
    seed = BACKEND / "scripts" / "seed_test_users.py"
    if not seed.exists():
        pytest.fail("seed_test_users.py is missing; the pending list cannot be verified")
    seeded = set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                            seed.read_text(encoding="utf-8")))
    unseeded = [e for e in SEEDED_TEST_USER_EMAILS_PENDING_DECISION if e not in seeded]
    assert not unseeded, (
        f"these are listed as seeded test users but appear nowhere in "
        f"seed_test_users.py: {unseeded}"
    )


def test_pending_list_excludes_anything_already_filtered():
    """A pending decision about an account that is ALREADY internal is noise, and
    would have Victor decide something that is not in question."""
    for email in SEEDED_TEST_USER_EMAILS_PENDING_DECISION:
        assert email not in INTERNAL_USER_SQL, (
            f"{email} is already caught by the internal filter; it is not pending"
        )
        assert not email.endswith("@hellobo.eu"), (
            f"{email} is caught by the hellobo.eu domain rule; it is not pending"
        )
