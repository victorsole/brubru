"""scripts/backfill_eu_trade_defence.py: delta window + title classifiers.

15 Sep 2026: eu_trade_defence_measures stopped at 12 May 2026 (no 2026/2049
alkaline batteries registration) because the only mode re-walked 1995-now and
re-hydrated every known act inside a 30-minute cron timeout.
"""
import importlib.util
from datetime import date
from pathlib import Path

import pytest

_P = Path(__file__).resolve().parents[1] / "scripts" / "backfill_eu_trade_defence.py"
_spec = importlib.util.spec_from_file_location("backfill_eu_trade_defence", _P)
td = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(td)


def test_delta_is_one_window_ending_today():
    w = td.discovery_windows(21, today=date(2026, 9, 15))
    assert w == [(date(2026, 8, 25), date(2026, 9, 15), "2026-08-25..2026-09-15")]


def test_full_walk_reaches_the_current_year_not_a_hardcoded_one():
    w = td.discovery_windows(None, today=date(2028, 3, 1))
    assert w[0][0] == date(1995, 1, 1)
    assert w[-1][:2] == (date(2028, 1, 1), date(2028, 12, 31))


ALKALINE = ("Commission Implementing Regulation (EU) 2026/2049 of 14 September 2026 making imports "
            "of primary cells and primary batteries of alkaline manganese dioxide originating in "
            "People’s Republic of China subject to registration with a view to allowing the levy of "
            "anti-dumping duties on the imports subject to registration")


def test_registration_regulation_2026_phrasing():
    assert td.is_trade_defence(ALKALINE)
    assert td.classify_duty_status(ALKALINE) == "registration"
    assert td.extract_target_country(ALKALINE) == "People’s Republic of China"


@pytest.mark.parametrize("title,expected", [
    ("Implementing Regulation imposing a definitive anti-dumping duty on imports of X originating in the "
     "People's Republic of China following an expiry review pursuant to Article 11(2)",
     "People's Republic of China"),
    ("... on imports of Y originating in, or consigned from the People's Republic of China for the period 2020",
     None),  # 'in,' does not match the pattern: unchanged behaviour
    ("... imports of steel originating in Brazil, the Czech Republic, Japan and the Republic of Korea",
     "Brazil, the Czech Republic, Japan"),
    ("... imports of Z originating in India, amending Council Implementing Regulation (EU) No 861/2013",
     "India"),
    ("... imports of W originating in the People’s Republic of China for three Chinese exporting producers",
     "People’s Republic of China"),
    ("... imports of V originating in Canada or not, for the purposes of determining an exemption",
     "Canada"),
])
def test_target_country_stops_at_the_clause(title, expected):
    assert td.extract_target_country(title) == expected
