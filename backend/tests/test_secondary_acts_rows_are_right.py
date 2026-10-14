"""secondary_acts rows say what their authorities say (14 Oct 2026).

The delegated-acts audit found: policy areas invented by splitting a department's name at
its commas (539 delegated acts under "Financial Stability" + "Financial Services and
Capital Markets Union"); 676 published acts marked 'adopted', two of them implementing acts
filed as delegated; two acts holding a corrigendum's CELEX; one act held twice; a CELEX
used as the reference on 91 rows; 11 planned rows the register no longer lists; and
published acts still titled as drafts."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from scripts import ingest_regdel_acts as job
from scripts import repair_secondary_acts as repair

BACKEND = Path(__file__).resolve().parents[1]
FEED = re.sub(r"\s+", " ", (BACKEND / "scripts" / "ingest_regdel_acts.py").read_text(encoding="utf-8"))


def _row(**kw):
    row = {"Complete title": "Commission Delegated Regulation (EU) 2014/1014 of 22 July 2014 supplementing x",
           "CCode": "C(2014)5033", "Celex number": "32014R1014R(03)",
           "Policy area": "Financial Stability, Financial Services and Capital Markets Union",
           "Leading Service Commission": "FISMA", "Delegated act status": "Published",
           "Planned adoption date": "", "Basic legislative act": "Regulation (EU) No 508/2014 of the x"}
    row.update(kw)
    return row


def test_the_policy_area_is_the_departments_whole_name():
    rec = job.normalise_row(_row(), "delegated")
    assert rec["policy_areas"] == ["Financial Stability, Financial Services and Capital Markets Union"]


def test_a_corrigendum_celex_from_the_register_becomes_the_acts_own():
    assert job.normalise_row(_row(), "delegated")["celex"] == "32014R1014"
    assert job.normalise_row(_row(**{"Celex number": "32024R1261"}), "delegated")["celex"] == "32024R1261"
    # Only the corrigendum form is cut: a CELEX with another suffix is left as it is.
    assert job.normalise_row(_row(**{"Celex number": "32014D0029(01)"}), "delegated")["celex"] == "32014D0029(01)"


def test_a_published_act_is_not_sent_back_by_a_register_that_lags():
    assert ("status = CASE WHEN secondary_acts.status = 'published' "
            "AND coalesce(secondary_acts.celex, '') <> '' "
            "AND EXCLUDED.status IN ('adopted', 'scrutiny_finished', 'notified') "
            "THEN secondary_acts.status ELSE EXCLUDED.status END") in FEED


def test_a_celex_used_as_reference_gives_way_to_the_c_number_only_if_free():
    assert "secondary_acts.reference = secondary_acts.celex" in FEED
    assert "NOT EXISTS (SELECT 1 FROM secondary_acts o WHERE o.reference = EXCLUDED.reference)" in FEED
    assert "WHEN \"\"\" + TAKES_C_NUMBER + \"\"\" THEN secondary_acts.merged_from" in FEED


def test_planned_rows_are_retired_only_after_a_full_read_of_a_full_export():
    assert "NOT (reference = ANY(%s))" in FEED and "WHERE reference LIKE 'PLANNED:%%'" in FEED
    assert "len(pipeline_refs) >= 0.9 * held_planned" in FEED
    assert "if args.limit: pass" in FEED


def test_the_floor_follows_the_adoption_date_the_row_keeps():
    blank = dict.fromkeys(job.SCRUTINY_EVENTS.values()) | {"extension_months": None}
    scrutiny = {"ep": dict(blank), "council": dict(blank)}
    assert job.objection_floor(date(2020, 8, 31), "2", scrutiny, "published") == date(2020, 10, 31)
    assert '"earliest": objection_floor(adoption, period,' in FEED


def test_the_repair_states_values_read_from_their_authority_and_guards_each_write():
    src = (BACKEND / "scripts" / "repair_secondary_acts.py").read_text(encoding="utf-8")
    assert repair.CORRIGENDUM_CELEX["C(2014)5033"] == ("32014R1014R(03)", "32014R1014", date(2014, 7, 22),
                                                       date(2014, 9, 27))
    assert repair.CORRIGENDUM_CELEX["C(2024)1454"][3] == date(2024, 5, 8)
    # Every write is conditional on the value it replaces, and a merge only takes a free CELEX.
    assert "IS NOT DISTINCT FROM :old" in src and "::text = :old" in src
    assert "WHERE id = :id AND coalesce(celex, '') = ''" in src
    # An act Cellar does not hold is left alone; its type comes from Cellar, not the title.
    assert "if not t:\n            continue" in src and "IMPLEMENTING_TYPES and not t & DELEGATED_TYPES" in src
