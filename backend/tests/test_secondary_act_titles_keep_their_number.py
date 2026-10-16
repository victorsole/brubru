"""A published act's title, once it carries the act's own number, is never replaced by
a draft title, whichever title the register export happens to send that day.

Measured 16 Oct 2026 by sending GovClipping's implementing-acts request twice, 14 hours
apart: 17 titles had flipped overnight between the Official Journal title ("Commission
Implementing Decision (EU) 2024/2638 of 9 October 2024 on ...") and the register's draft
("COMMISSION IMPLEMENTING DECISION on ...", "COMMISSION REGULATION (EU)  / amending ..."),
in BOTH directions. One writer does it, scripts/ingest_regdel_acts.py: the export serves
the draft one day and the final the next, and the guard of 14 Oct only knew drafts spelt
"(EU) …/...". The rule is now: a title that names the act's own number outranks one that
does not. The decision lives in SQL (the upsert's CASE) and in title_outranks(), its
Python twin on the same regex; the test holds the twin on the 17 real pairs and checks
the SQL embeds the same regex, so the two cannot drift.
"""
import importlib
import re
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
mod = importlib.import_module("scripts.ingest_regdel_acts")
title_outranks = mod.title_outranks

OJ = {
    "32024D2638": "Commission Implementing Decision (EU) 2024/2638 of 9 October 2024 on the harmonised standards drafted in support",
    "32024D2210": "Commission Implementing Decision (EU) 2024/2210 of 5 September 2024 amending Implementing Decision (EU) 2020/1550",
    "32024R0234": "Commission Regulation (EU) 2024/234 of 15 January 2024 amending Annex I to Regulation (EC) No 1334/2008 of the",
    "32023R0923": "Commission Regulation (EU) 2023/923 of 3 May 2023 amending Annex XVII to Regulation (EC) No 1907/2006 of the E",
    "32023D0600": "Commission Implementing Decision (EU) 2023/600 of 13 March 2023 amending Implementing Decision (EU) 2019/1956",
    "32023R0266": "Commission Implementing Regulation (EU) 2023/266 of 9 February 2023 laying down technical information for the",
    "32023R0150": "Commission Implementing Regulation (EU) 2023/150 of 20 January 2023 amending certain Annexes to Implementing R",
    "32022D2191": "Commission Implementing Decision (EU) 2022/2191 of 8 November 2022 on the harmonised standards for radio equip",
    "32022D1655": "Commission Implementing Decision (EU) 2022/1655 of 26 September 2022 recognising the report including informat",
    "32022R0978": "Commission Implementing Regulation (EU) 2022/978 of 23 June 2022 amending Implementing Regulation (EU) 2019/15",
    "32022D0910": "Commission Implementing Decision (EU) 2022/910 of 9 June 2022 amending Implementing Decision (EU) 2019/1326 as",
    "32021D2273": "Commission Implementing Decision (EU) 2021/2273 of 20 December 2021 amending Implementing Decision (EU) 2019/1",
    "32020D2127": "Commission Implementing Decision (EU) 2020/2127 of 16 December 2020 amending Commission Implementing Decision",
    "32019D0419": "Commission Implementing Decision (EU) 2019/419 of 23 January 2019 pursuant to Regulation (EU) 2016/679 of the",
    "32018D2046": "Commission Implementing Decision (EU) 2018/2046 of 19 December 2018 authorising the placing on the market of p",
}
DRAFT = {
    "32024D2638": "COMMISSION IMPLEMENTING DECISION on the harmonised standards drafted in support of Commission Regulation (EU)",
    "32024D2210": "COMMISSION IMPLEMENTING DECISION amending Implementing Decision (EU) 2020/1550 by updating the multiannual pro",
    "32024R0234": "COMMISSION REGULATION (EU)  / amending Annex I to Regulation (EC) No 1334/2008 of the European Parliament and",
    "32023R0923": "COMMISSION REGULATION (EU) No  /.. amending Annex XVII to Regulation (EC) No 1907/2006 of the European Parliam",
    "32023D0600": "COMMISSION IMPLEMENTING DECISION amending Implementing Decision (EU) 2019/1956 as regards harmonised standards",
    "32023R0266": "COMMISSION IMPLEMENTING REGULATION (EU)  /... laying down technical information for the calculation of technic",
    "32023R0150": "COMMISSION IMPLEMENTING REGULATION (EU)  /... amending certain Annexes to Implementing Regulation (EU) 2021/62",
    "32022D2191": "COMMISSION IMPLEMENTING DECISION on the harmonised standards for radio equipment drafted in support of Directi",
    "32022D1655": "COMMISSION IMPLEMENTING DECISION recognising the report including information on the typical greenhouse gas em",
    "32022R0978": "COMMISSION IMPLEMENTING REGULATION (EU)  /... amending Commission Implementing Regulation (EU) 2019/159 imposi",
    "32022D0910": "COMMISSION IMPLEMENTING DECISION amending Implementing Decision (EU) 2019/1326 as regards the harmonised stand",
    "32021D2273": "COMMISSION IMPLEMENTING DECISION amending Implementing Decision (EU) 2019/1956 as regards harmonised standards",
    "32020D2127": "COMMISSION IMPLEMENTING DECISION amending Commission Implementing Decision (EU) 2019/541 on the equivalence of",
    "32019D0419": "COMMISSION IMPLEMENTING DECISION pursuant to Regulation (EU) 2016/679 of the European Parliament and of the Co",
    "32018D2046": "COMMISSION IMPLEMENTING DECISION authorising the placing on the market of products containing, consisting of o",
}


class TestTheSeventeenRealPairs:
    @pytest.mark.parametrize("celex", sorted(OJ))
    def test_a_draft_never_replaces_the_numbered_title(self, celex):
        assert title_outranks(OJ[celex], DRAFT[celex]) == OJ[celex]

    @pytest.mark.parametrize("celex", sorted(OJ))
    def test_the_numbered_title_replaces_a_held_draft(self, celex):
        assert title_outranks(DRAFT[celex], OJ[celex]) == OJ[celex]


class TestTheRegexKnowsItsOwnNumberFromACitedOne:
    def test_an_amending_draft_citing_another_acts_number_is_not_numbered(self):
        # "(EC) No 1334/2008" is the amended act, not this one: the head has no number.
        assert not mod._NUMBERED.search(DRAFT["32024R0234"])
        assert not mod._NUMBERED.search(DRAFT["32024D2210"])

    @pytest.mark.parametrize("title", [
        "Commission Delegated Regulation (EU) 2026/1563 of 3 July 2026 amending Delegated Regulation (EU) 2023/2772",
        "Commission Regulation (EU) No 234/2014 of 15 January 2014 amending Annex I",
        "COMMISSION IMPLEMENTING REGULATION (EU) 2026/2299 of 15 October 2026 amending Annexes II and III",
        "Council Decision (EU, Euratom) 2024/1234 of 1 January 2024 on something",
        "2012/67/EU: Commission Implementing Decision of 3 February 2012 amending Decision 2002/...",
        "2013/51/EU: Commission Implementing Decision of 23 January 2013 on the a",
    ])
    def test_numbered_forms(self, title):
        assert mod._NUMBERED.search(title)

    @pytest.mark.parametrize("title", [
        "COMMISSION DELEGATED REGULATION (EU) …/... amending Regulation (EU) 2021/821",
        "COMMISSION IMPLEMENTING REGULATION (EU)  /... laying down",
        "COMMISSION REGULATION (EU) No  /.. amending Annex XVII",
        "COMMISSION IMPLEMENTING DECISION on the harmonised standards",
    ])
    def test_draft_forms(self, title):
        assert not mod._NUMBERED.search(title)


class TestTheOtherRules:
    def test_spacing_only_difference_keeps_the_held_title(self):
        held = "Commission Regulation (EU) 2024/234 of 15 January 2024 amending Annex I"
        assert title_outranks(held, "Commission  Regulation (EU) 2024/234 of 15 January 2024 amending Annex I ") == held

    def test_a_new_numbered_title_replaces_an_old_numbered_one(self):
        # A corrected final title (e.g. after a corrigendum) still wins over the held one.
        held = "Commission Regulation (EU) 2024/234 of 15 January 2024 amending Annex I"
        new = "Commission Regulation (EU) 2024/234 of 15 January 2024 amending Annexes I and II"
        assert title_outranks(held, new) == new

    def test_an_empty_export_title_never_blanks_a_held_one(self):
        assert title_outranks("Commission Regulation (EU) 2024/234 of 15 January 2024", None).startswith("Commission")
        assert title_outranks("COMMISSION IMPLEMENTING DECISION on x", None) == "COMMISSION IMPLEMENTING DECISION on x"

    def test_the_old_numbered_form_is_not_replaced_by_the_cellar_title_without_it(self):
        # Pre-2015 decisions: EUR-Lex puts the number first; Cellar's title drops it.
        held = "2012/67/EU: Commission Implementing Decision of 3 February 2012 amending Decision 2002/1"
        assert title_outranks(held, "Commission Implementing Decision of 3 February 2012 amending Decision 2002/1") == held

    def test_a_draft_replaces_nothing_and_fills_an_empty_row(self):
        assert title_outranks(None, DRAFT["32024D2638"]) == DRAFT["32024D2638"]


class TestTheSqlUsesTheSameRegex:
    def test_the_upsert_embeds_numbered_title_twice_and_not_a_copy(self):
        src = (BACKEND / "scripts" / "ingest_regdel_acts.py").read_text()
        assert src.count("'%(numbered)s'") == 2, "the SQL CASE must test both the held and the incoming title"
        assert 'replace("%(numbered)s", NUMBERED_TITLE)' in src
        # the regex itself appears once, as the constant; the SQL does not carry a second spelling
        assert src.count("delegated\\s+|implementing\\s+") == 1

    def test_the_regex_is_valid_for_both_engines(self):
        # PostgreSQL ARE and Python re share this subset: no lookarounds, no \b, no named groups.
        for forbidden in ("(?<", "(?=", "(?!", r"\b", "(?P<"):
            assert forbidden not in mod.NUMBERED_TITLE
        re.compile(mod.NUMBERED_TITLE, re.I)
