"""A Commissioner's meeting names its host, not the register's link text (16 Oct 2026)."""
from scripts.ingest_transparency_meetings import department_name, member_name


def test_the_member_is_named_without_the_boilerplate_or_the_role():
    assert member_name("Information on meetings held by Commissioner Jessika Roswall") == "Jessika Roswall"
    assert member_name("Information on meetings held by Executive Vice-President Teresa Ribera Rodríguez") \
        == "Teresa Ribera Rodríguez"
    assert member_name("Information on meetings held by President Ursula von der Leyen") == "Ursula von der Leyen"
    assert member_name("Information on meetings held by High Representative of the Union for Foreign Affairs "
                       "and Security Policy and Vice-President Kaja Kallas") == "Kaja Kallas"


def test_a_department_keeps_its_name():
    assert department_name("Information on meetings held by Directorate-General for Trade") == \
        "Directorate-General for Trade"


def test_a_cabinet_is_named_as_a_cabinet():
    from scripts.ingest_transparency_meetings import cabinet_name
    assert cabinet_name("Information on meetings held by Executive Vice-President Raffaele Fitto") == \
        "Cabinet of Executive Vice-President Raffaele Fitto"
    assert cabinet_name("Information on meetings held by Executive Vice-President Stéphane Séjourné's cabinet") == \
        "Cabinet of Executive Vice-President Stéphane Séjourné"


def test_the_high_representatives_cabinet_fits_its_column():
    from scripts.ingest_transparency_meetings import cabinet_name
    got = cabinet_name("Information on meetings held by High Representative of the Union for Foreign Affairs and "
                       "Security Policy and Vice-President Kaja Kallas's cabinet")
    assert got == "Cabinet of High Representative and Vice-President Kaja Kallas" and len(got) <= 100
