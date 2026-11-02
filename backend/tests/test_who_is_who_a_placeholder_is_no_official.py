"""The EU directory lists one unnamed post as a person, given name "." and family name "..." (ECHA, register O142,
2 Nov 2026). A name with no letters is nobody: the sync takes no such row, so the nightly sweep marks a stored one
removed, and the list stops opening on it."""
from services.scrapers import who_is_who_ingest as wiw


def _row(name, person):
    def v(x):
        return {"value": x}
    return {"name": v(name), "entity": v("ECHA.E"), "orgLabel": v("Directorate E"), "person": v(person),
            "CorporateBody": v("http://publications.europa.eu/resource/authority/corporate-body/ECHA")}


def test_a_name_with_no_letters_is_no_official_and_real_names_stay(monkeypatch):
    monkeypatch.setattr(wiw, "fetch_rows", lambda *a, **k: [
        _row(". ...", "http://publications.europa.eu/resource/directory/person/UNDEFINED_NRE529256"),
        _row("A. DRAKOU", "http://publications.europa.eu/resource/directory/person/EDPS_1"),
        _row("Šarūnas Ñáñez", "http://publications.europa.eu/resource/directory/person/ECHA_2"),
        _row("Li 李", "http://publications.europa.eu/resource/directory/person/ECHA_3"),
    ])
    _, officials = wiw.build()
    assert sorted(o["name"] for o in officials) == ["A. DRAKOU", "Li 李", "Šarūnas Ñáñez"]
