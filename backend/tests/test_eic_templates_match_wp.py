"""
The EIC Tender Docs templates state what the 2026 Work Programme and the official forms state.

Why (8 Oct 2026): Pathfinder templates carried a 45-page limit (WP: 22 for Open,
30 for Challenges) and the actual-cost grant agreement although 2026 Pathfinder
grants are lump sums; AIC stage 1 said 15 pages (WP: 11) and stage 2 said 30
(WP: 22); the full Accelerator proposal had no page limit (form V2.1: 20 pages
including the cover); four default topic ids did not exist on the Funding &
Tenders Portal. Sources: EIC Work Programme 2026, C(2026) 4080 of 17 June 2026;
forms "HE EIC Accelerator stage 1" V2.1 (12 June 2026) and "stage 2" V2.1
(9 July 2026); portal topic records read on 8 October 2026.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.funding_template_loader import TEMPLATES_DIR  # noqa: E402

LS_MGA = "https://ec.europa.eu/info/funding-tenders/opportunities/docs/2021-2027/common/agr-contr/ls-mga_en.pdf"

# (template id, document kind) -> page limit stated by the WP or the official form
PAGE_LIMITS = {
    ("eic-accelerator-stage-1", "tender_application_short"): 12,
    ("eic-accelerator-stage-2", "tender_application_full"): 20,
    ("eic-accelerator-stage-2", "tender_implementation_plan"): 10,
    ("eic-pathfinder-open", "tender_application_full"): 22,
    ("eic-pathfinder-challenges", "tender_application_full"): 30,
    ("eic-transition", "tender_application_full"): 22,
    ("eic-aic-stage-1", "tender_application_short"): 11,
    ("eic-aic-stage-2", "tender_application_full"): 22,
    ("eic-step-scale-up", "tender_application_full"): 50,
}

# topic ids as they exist on the Funding & Tenders Portal (search API, 8 Oct 2026)
PORTAL_TOPICS = {
    "eic-accelerator-stage-1": "HORIZON-EIC-2026-ACCELERATOR-01",
    "eic-accelerator-stage-2": "HORIZON-EIC-2026-ACCELERATOR-01",
    "eic-step-scale-up": "HORIZON-EIC-2026-STEP",
    "eic-pathfinder-open": "HORIZON-EIC-2026-PATHFINDEROPEN",
    "eic-transition": "HORIZON-EIC-2026-TRANSITIONOPEN",
}


def tpl(name):
    return json.loads((TEMPLATES_DIR / f"{name}.json").read_text())


def test_page_limits_match_the_work_programme_and_forms():
    for (tid, kind), limit in PAGE_LIMITS.items():
        docs = [d for d in tpl(tid)["documents"] if d.get("kind") == kind]
        assert docs, (tid, kind)
        assert docs[0].get("page_limit") == limit, (tid, kind, docs[0].get("page_limit"), limit)


def test_default_topic_ids_exist_on_the_portal():
    for tid, topic in PORTAL_TOPICS.items():
        assert tpl(tid).get("topic_id_default") == topic, tid
    assert tpl("eic-pathfinder-challenges")["topic_ids"] == [
        "HORIZON-EIC-2026-PATHFINDERCHALLENGES-01-01",
        "HORIZON-EIC-2026-PATHFINDERCHALLENGES-01-02",
        "HORIZON-EIC-2026-PATHFINDERCHALLENGES-01-03",
    ]
    assert tpl("eic-aic-stage-1")["topic_ids"] == ["HORIZON-EIC-2026-AIC-01", "HORIZON-EIC-2026-AIC-02"]


def test_lump_sum_grant_agreement_for_lump_sum_schemes():
    for tid in ("eic-pathfinder-open", "eic-pathfinder-challenges", "eic-transition", "eic-accelerator-stage-2"):
        assert tpl(tid)["model_grant_agreement_url"] == LS_MGA, tid


def test_accelerator_forms_are_the_v2_1_versions_with_the_civilian_and_defence_line():
    assert tpl("eic-accelerator-stage-1")["scaffold_version"] == "2.1-12.06.2026"
    assert tpl("eic-accelerator-stage-2")["scaffold_version"] == "2.1-09.07.2026"
    for tid in ("eic-accelerator-stage-1", "eic-accelerator-stage-2"):
        text = json.dumps(tpl(tid))
        assert "civilian and defence end-users" in text, tid


def test_page_budgets_fit_inside_the_page_limit():
    for path in sorted(TEMPLATES_DIR.glob("eic-*.json")):
        for d in json.loads(path.read_text())["documents"]:
            limit = d.get("page_limit")
            total = sum((s.get("page_budget") or 0) for s in d.get("sections") or [])
            if limit:
                assert total <= limit, (path.name, d.get("kind"), total, limit)
