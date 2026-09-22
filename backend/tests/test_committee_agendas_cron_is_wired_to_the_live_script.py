"""The warm-12h cron must feed the calendar from eMeeting, not from the dead scraper.

Incident (22 September 2026). `/news` reported the calendar as missing every EP
committee meeting for 28 September and 1 October. The cause was not the calendar:
`scripts/sync_committee_agendas.py` scrapes the EP "latest documents" HTML page,
and it has been dead for weeks. Measured that day it finished in 0.3 seconds with
added=0, updated=0, skipped=0, errors=0 and **exit code 0** -- nothing-fetched
reported as nothing-found, twice a day, on a green job.

Eight committee meetings were missing when it was found, including SANT on
28 September and AFCO, AFET, EMPL and INTA on 1 October.

`scripts/sync_calendar_from_emeeting_agendas.py` reads `ep_emeeting_agendas`,
which Brubru fills from the eMeeting open JSON API, so it does not depend on the
HTML page at all.

These tests are static: they read the source, touch no network and no database,
so they run anywhere and cannot themselves go quietly green.
"""

import os
import pathlib
import re
import sys

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

_CRON = pathlib.Path(_BACKEND) / "api" / "cron.py"


def _cron_source() -> str:
    return _CRON.read_text(encoding="utf-8")


def test_the_dead_html_scraper_is_not_invoked_by_any_cron_tier():
    """`sync_committee_agendas.py` must not be run on a schedule.

    Keeping it wired is worse than not running it at all: it returns success, so
    the tier is green and `sync_runs` records a healthy row while the calendar
    quietly empties.
    """
    src = _cron_source()
    invocations = re.findall(r'"scripts/sync_committee_agendas\.py"', src)
    assert not invocations, (
        "api/cron.py still invokes scripts/sync_committee_agendas.py. That script "
        "exits 0 having parsed nothing, so it reports success while the calendar "
        "loses every committee meeting."
    )


def test_committee_agendas_is_fed_from_the_emeeting_store():
    """The replacement must be wired, with --apply, or the cron is a dry run."""
    src = _cron_source()
    assert '"scripts/sync_calendar_from_emeeting_agendas.py"' in src, (
        "the warm tier no longer feeds committee meetings into the calendar at all"
    )

    # Find the argument list passed alongside the script and confirm --apply is in
    # it. Without --apply the script prints a dry run and changes nothing, which
    # would be the same silent failure with a different script name.
    idx = src.index('"scripts/sync_calendar_from_emeeting_agendas.py"')
    window = src[idx: idx + 400]
    assert '"--apply"' in window, (
        "sync_calendar_from_emeeting_agendas.py is wired WITHOUT --apply, so the "
        "cron only performs a dry run and writes nothing"
    )


def test_the_replacement_script_exists_and_reads_the_emeeting_store():
    """Guard against the cron pointing at a script that was renamed or removed."""
    script = pathlib.Path(_BACKEND) / "scripts" / "sync_calendar_from_emeeting_agendas.py"
    assert script.exists(), f"missing {script}"
    body = script.read_text(encoding="utf-8")
    assert "ep_emeeting_agendas" in body, (
        "the replacement no longer reads ep_emeeting_agendas, which is the whole "
        "reason it does not depend on the WAF-walled HTML page"
    )
