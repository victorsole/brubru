"""A Commissioner's agenda never stores another College member's events (16 Oct 2026).

On 5-6 June 2026 every Commissioner's calendar page served the whole College's agenda, so
each event was stored once per Commissioner, with that Commissioner's page and DG: 504
copies, "Commissioner Dombrovskis meets ..." filed under Tzitzikostas with DG MOVE."""
from __future__ import annotations

from services.scrapers.eu_calendar_sync_service import names_another_commissioner

COLLEGE = ["valdis-dombrovskis", "apostolos-tzitzikostas", "marta-kos", "dan-jorgensen", "kaja-kallas",
           "teresa-ribera-rodriguez", "maros-sefcovic", "president", "henna-virkkunen"]


def _others(own):
    return [s for s in COLLEGE if s != own]


def test_an_event_opening_with_another_members_name_is_not_this_agendas():
    t = "Commissioner Dombrovskis participates in the High-level Breakfast hosted by the Ministry of Finance of Latvia"
    assert names_another_commissioner(t, "apostolos-tzitzikostas", _others("apostolos-tzitzikostas"))
    assert not names_another_commissioner(t, "valdis-dombrovskis", _others("valdis-dombrovskis"))


def test_accents_and_roles_are_read():
    assert not names_another_commissioner("Commissioner Jørgensen hosts an implementation dialogue",
                                          "dan-jorgensen", _others("dan-jorgensen"))
    assert names_another_commissioner("Commissioner Šefčovič receives Ms Nadia Calviño",
                                      "marta-kos", _others("marta-kos"))
    assert names_another_commissioner("High Representative/Vice-President Kallas meets the Foreign Minister",
                                      "henna-virkkunen", _others("henna-virkkunen"))
    assert not names_another_commissioner("Executive Vice-President Ribera speaks at COP31",
                                          "teresa-ribera-rodriguez", _others("teresa-ribera-rodriguez"))


def test_the_president_and_a_second_member_named_later():
    t = "President von der Leyen meets Prime Minister Frieden"
    assert names_another_commissioner(t, "marta-kos", _others("marta-kos"))
    assert not names_another_commissioner(t, "president", _others("president"))
    later = "Commissioner Kos speaks at the Moldova Digital Summit together with President von der Leyen"
    assert not names_another_commissioner(later, "marta-kos", _others("marta-kos"))
    assert not names_another_commissioner("Visit to the FN Herstal site", "marta-kos", _others("marta-kos"))
