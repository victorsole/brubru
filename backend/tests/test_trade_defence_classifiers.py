"""Half the China measures were filed under a different country (24 September 2026).

`eu_trade_defence_measures` classifies each act from its title. Three defects were in the
corpus, and each of them is the kind that reads as a complete answer:

  * 193 rows kept the whole trailing clause in `target_country` ("People's Republic of
    China following an expiry review pursuant to Article 11(2)..."). The cut pattern that
    fixes this landed on 15 September and only reaches a row when the Cellar walk next
    passes it, which at ~33 seconds per row is a nine-hour lap.
  * 715 China rows were split across two apostrophes, 403 curly against 312 straight,
    because the OJ uses both. A filter on the straight spelling returned 312 of 715
    measures and looked like the whole corpus. This is the one worth remembering: the
    query did not fail, it answered confidently with 43% of the rows.
  * 53 acts that INITIATE a review also order registration of the imports concerned, and
    the registration branch (added for the 2026 regulations) sat above the review
    branches, so they were about to be labelled by their ancillary step.

`scripts/reclassify_trade_defence_from_titles.py` applies these to the stored titles
without the network, and imports these same functions so the two cannot drift.

No network.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

import pytest

BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

_spec = importlib.util.spec_from_file_location(
    "_bftd", BACKEND / "scripts" / "backfill_eu_trade_defence.py")
tdm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tdm)

CURLY = "’"


# ------------------------------------------------------------------ target country
@pytest.mark.parametrize("title,expected", [
    # the 193: a clause after the country
    ("...duty on imports of furfuraldehyde originating in the People's Republic of China "
     "following an expiry review pursuant to Article 11(2) of Regulation (EC) No 384/96",
     "People's Republic of China"),
    ("...duty on imports of X originating in Japan by imports of the same product assembled in Y",
     "Japan"),
    ("...originating in the People's Republic of China subject to registration with a view to "
     "allowing the levy of anti-dumping duties", "People's Republic of China"),
    # a producer-specific clause is not part of the country
    ("...imports of ironing boards originating in the People's Republic of China, manufactured "
     "by Foshan Shunde Yongjian Housewares and Hardware Co. Ltd", "People's Republic of China"),
    ("...originating in India, re-imposing the duty", "India"),
    ("...originating in certain third countries, (EEC) No 701/84 fixing countervailing charges",
     "certain third countries"),
])
def test_only_the_country_survives_the_clause(title, expected):
    assert tdm.extract_target_country(title) == expected


def test_the_oj_apostrophe_does_not_split_a_country_in_two():
    """403 rows used this apostrophe and 312 the straight one. Same country."""
    curly = f"...originating in the People{CURLY}s Republic of China following an expiry review"
    straight = "...originating in the People's Republic of China following an expiry review"
    assert tdm.extract_target_country(curly) == tdm.extract_target_country(straight)
    assert CURLY not in tdm.extract_target_country(curly)


def test_a_country_list_is_not_cut_at_its_commas():
    """Several measures target a group of countries; the comma is data, not a clause."""
    title = ("...duty on imports of X originating in Brazil, the Czech Republic, Japan, "
             "the People's Republic of China, the Republic of Korea")
    assert tdm.extract_target_country(title) == (
        "Brazil, the Czech Republic, Japan, the People's Republic of China, the Republic of Korea")


def test_a_title_without_the_canonical_phrase_yields_nothing():
    assert tdm.extract_target_country("Commission Regulation fixing import duties") is None


def test_the_product_is_normalised_too():
    assert CURLY not in (tdm.extract_product(
        f"...duty on imports of women{CURLY}s footwear originating in Vietnam") or "")


# ------------------------------------------------------------------ duty status
@pytest.mark.parametrize("title,expected", [
    # what the act DOES, not the registration it also orders
    ("Commission Regulation (EC) No 802/98 initiating a 'new exporter' review of Council "
     "Regulation (EC) No 1950/97 ... and making such imports subject to registration",
     "initiation"),
    ("Commission Implementing Regulation (EU) 2026/1925 initiating an investigation concerning "
     "possible circumvention ... and making such imports subject to registration", "initiation"),
    # a real registration regulation opens by making imports subject to registration
    ("Commission Implementing Regulation (EU) 2026/2049 making imports of primary cells "
     "originating in the People's Republic of China subject to registration", "registration"),
    ("Council Regulation imposing a definitive anti-dumping duty following an expiry review",
     "expiry_review"),
    ("Council Regulation imposing a definitive anti-dumping duty on imports of X", "definitive"),
    ("Council Regulation imposing a provisional anti-dumping duty on imports of X", "provisional"),
    ("Commission Regulation terminating the anti-dumping proceeding concerning imports of X",
     "termination"),
])
def test_the_act_is_filed_under_what_it_does(title, expected):
    assert tdm.classify_duty_status(title) == expected


# ------------------------------------------------------------------ the corpus itself
@pytest.mark.filterwarnings("ignore")
def test_no_measure_in_the_corpus_carries_a_clause_as_its_country():
    """The classifier can be right while the rows stay wrong: they are only rewritten when
    the walk passes them. This asserts the CORPUS, which is what the API serves."""
    from sqlalchemy import text

    from core.database import SessionLocal

    db = SessionLocal()
    try:
        bad = db.execute(text(
            "SELECT count(*) FROM eu_trade_defence_measures WHERE target_country ~* "
            "'following|pursuant|review|expiry|imports|duty|duties|Regulation|Article|No [0-9]'"
        )).scalar()
        assert bad == 0, f"{bad} measure(s) hold a clause in target_country"
        curly = db.execute(text(
            "SELECT count(*) FROM eu_trade_defence_measures "
            "WHERE target_country LIKE '%' || chr(8217) || '%'")).scalar()
        assert curly == 0, f"{curly} measure(s) use the curly apostrophe: a filter on the "
    finally:
        db.close()


def test_every_status_the_data_uses_is_documented():
    """`registration` was a real value in 30 rows and absent from the endpoint's docs, so a
    caller filtering by the documented list could not reach them and had no way to know
    they existed. The docs are what the API promises; the data is what it holds."""
    import re

    from sqlalchemy import text

    from core.database import SessionLocal

    doc = (BACKEND / "api" / "v1" / "specialised_trade_defence.py").read_text(encoding="utf-8")
    line = next(l for l in doc.splitlines() if l.lstrip().startswith("- `duty_status`"))
    documented = set(re.findall(r"`([a-z_]+)`", line)) - {"duty_status", "string", "optional"}

    db = SessionLocal()
    try:
        used = {r[0] for r in db.execute(text(
            "SELECT DISTINCT duty_status FROM eu_trade_defence_measures "
            "WHERE duty_status IS NOT NULL")).fetchall()}
    finally:
        db.close()
    assert not (used - documented), f"undocumented duty_status value(s) in the data: {used - documented}"


# Measured 24 September 2026 over a real 25-measure batch: 354s wall, 25/25 hydrated from
# Cellar XHTML, 0 errors -> 14.2s each. Rounded up, because a slow Cellar day is the one
# that overruns.
SECONDS_PER_MEASURE = 15


def test_the_body_backfill_is_bounded_by_time_not_by_a_guessed_rate():
    """A slice sized from a measured rate assumes the rate holds. It does not: the newest
    acts come from Cellar XHTML in ~14s and the older ones fall back to a PDF fetch, and
    the backlog is made of the older ones. A run that overruns is killed, so the ledger
    records a timeout instead of the measures it did hydrate. The bound has to be the
    clock the caller is holding."""
    import re

    cron = (BACKEND / "api" / "cron.py").read_text(encoding="utf-8")
    block = cron.split('results["trade_defence_bodies"]')[1][:500]
    budget = int(re.search(r'"--max-seconds", "(\d+)"', block).group(1))
    timeout = int(re.search(r"timeout=(\d+)", block).group(1))
    assert budget < timeout * 0.75, (
        f"a {budget}s budget does not leave room inside a {timeout}s timeout")
    # The count stays as a cap, and must not be the real limit: at the fast rate it should
    # not be reachable within the budget, or it silently becomes the bound again.
    slice_n = int(re.search(r'"--fill-missing-bodies", "(\d+)"', block).group(1))
    assert slice_n * SECONDS_PER_MEASURE > budget, (
        f"{slice_n} measures would finish inside {budget}s: the count is the real bound")


def test_the_script_stops_between_measures_not_mid_fetch():
    """Stopping mid-fetch would leave the measure half-written; the check sits at the top
    of the loop, before the metadata call."""
    src = (BACKEND / "scripts" / "backfill_eu_trade_defence.py").read_text(encoding="utf-8")
    assert "args.max_seconds" in src
    loop = src.split("for i, row in enumerate(universe, 1):")[1][:900]
    assert loop.index("args.max_seconds") < loop.index("hydrate_metadata"), (
        "the budget is checked after the fetch has already been paid for")
