"""The Position Analysis rapporteur comes from the roles-owned column.

Before 25 Sep 2026 all 43 snapshots showed no rapporteur: the aggregator read
only the raw OEIL blob, which never carries one.
"""
from types import SimpleNamespace

import pytest

from services.positions.position_aggregator import PositionAggregator as PA


def _c(raps, lead=None, name=None, blob=None):
    return SimpleNamespace(rapporteurs=raps, lead_committee=lead,
                           rapporteur_name=name, oeil_procedure_data=blob)


def test_lead_committee_rapporteur_wins_on_joint_file():
    c = _c([{"name": "CAVAZZINI Anna", "group": "Greens/EFA", "committee": "INTA"},
            {"name": "JOUVET Pierre", "group": "S&D", "committee": "IMCO"}], lead="IMCO")
    assert PA._rapporteur_name(PA, c) == "JOUVET Pierre"
    assert PA._rapporteur_group(PA, c) == "S&D"


@pytest.mark.parametrize("raw,expected", [
    ("PPE", "EPP"), ("Verts/ALE", "Greens/EFA"), ("GUE/NGL", "The Left"),
    ("ALDE", "Renew"), ("EPP", "EPP"), ("ID", None), ("EFDD", None), (None, None),
])
def test_group_normalised_to_a_current_group(raw, expected):
    c = _c([{"name": "X", "group": raw, "committee": "ENVI"}], lead="ENVI")
    assert PA._rapporteur_group(PA, c) == expected


def test_falls_back_to_name_column_then_blob():
    assert PA._rapporteur_name(PA, _c(None, name="LIESE Peter")) == "LIESE Peter"
    assert PA._rapporteur_name(PA, _c(None, blob={"rapporteur": "Y"})) == "Y"
    assert PA._rapporteur_name(PA, _c(None)) is None
