"""An MEP's group and memberships are served by name, not by EP id (16 Oct 2026).

/api/v2/parliament/meps served group "org/7150" on all 719 MEPs and a membership history of
bare ids ("MEMBER_SUBSTITUTE @ 6577"). The labels come from EP Open Data's corporate bodies."""
from __future__ import annotations

from api.v1.meps import MEPItem, _compose_mep_body, group_acronym, org_label

PROFILE = {"hasHonorificPrefix": "http://publications.europa.eu/resource/authority/human-sex/F",
           "hasMembership": [
               {"organization": "org/ep-10", "role": "def/ep-roles/MEMBER_PARLIAMENT",
                "memberDuring": {"startDate": "2024-07-16"}},
               {"organization": "org/7150", "membershipClassification": "def/ep-entities/EU_POLITICAL_GROUP",
                "memberDuring": {"startDate": "2024-07-16"}},
               {"organization": "org/6586", "role": "def/ep-roles/MEMBER_SUBSTITUTE",
                "membershipClassification": "def/ep-entities/COMMITTEE_PARLIAMENTARY_STANDING",
                "memberDuring": {"startDate": "2024-07-19"}},
               {"organization": "org/6737", "role": "def/ep-roles/MEMBER",
                "membershipClassification": "def/ep-entities/NATIONAL_POLITICAL_GROUP",
                "memberDuring": {"startDate": "2024-07-16"}}]}


def test_the_group_is_its_acronym_and_the_id_is_kept_beside_it():
    item = MEPItem(id="28150", full_name="Kinga GÁL", group="org/7150")
    assert (item.group, item.group_id) == ("PfE", "org/7150")
    assert MEPItem(group="http://data.europarl.europa.eu/org/7018").group == "EPP"   # EP label "PPE"
    assert MEPItem(group="org/7028").group == "Greens/EFA"                          # EP label "Verts/ALE"
    assert MEPItem(group="Renew").group == "Renew"
    assert group_acronym("org/999999999") is None and org_label("org/6586") == "LIBE"


def test_the_body_names_the_group_and_every_membership():
    body, _html, _date = _compose_mep_body(PROFILE, "Kinga GÁL", "HUN", "org/7150", "MEMBER")
    assert "Active political group: PfE (Patriots)" in body
    assert "MEMBER_SUBSTITUTE @ LIBE (committee)" in body
    assert "MEMBER @ PfE (political group)" in body
    assert "MEMBER @ Fidesz-KDNP (national party)" in body
    assert "MEMBER_PARLIAMENT @ European Parliament, term 10" in body
    assert "org/" not in body and "@ 6586" not in body
