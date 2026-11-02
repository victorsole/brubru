"""The Commission's outage page is never stored as a document's text (16 Oct 2026)."""
from scripts.remove_stored_outage_pages import strip_outage
from services.scrapers.economy_common import error_body_reason, is_outage_page

OUTAGE = ("Server inaccessibility\nbg\nбългарски\nСървърът е временно недостъпен\n"
          "Извиняваме се за неудобството. Моля, опитайте пак по-късно.\nsv\nsvenska\n"
          "Servern är inte tillgänglig för tillfället\nVi ber om ursäkt för besväret. Försök igen senare.")


def test_the_reader_refuses_it():
    assert error_body_reason(OUTAGE) == "ec_server_inaccessible"
    assert error_body_reason("A real article about server capacity in the EU, long enough. " * 3) is None


def test_an_attachment_block_goes_and_the_rest_stays():
    text = ("Description\nInitiative 2052.\n\nFull description\n\nCOM(2019)3 (MAIN): " + OUTAGE +
            "\n\nCOM(2019)3 (ANNEX): The annex lists the amendments.")
    out = strip_outage(text)
    assert "Server inaccessibility" not in out and "Försök" not in out
    assert out.startswith("Description") and out.endswith("The annex lists the amendments.")


# The forms EEAS serves: no language names, and with or without the heading (30 rows, 2 Nov 2026; O72).
SHORT = "Server inaccessibility\nbg\nСървърът е временно недостъпен\nИзвиняваме се за неудобството.\ncs\nServer je dočasně nedostupný"
BARE = "bg\nСървърът е временно недостъпен\nИзвиняваме се за неудобството.\ncs\nServer je dočasně nedostupný"


def test_every_form_of_the_page_is_refused():
    for form in (OUTAGE, SHORT, BARE):
        assert error_body_reason(form) == "ec_server_inaccessible"
        assert is_outage_page(form)
    assert not is_outage_page("A tender for server maintenance at the Delegation.") and not is_outage_page(None)


def test_the_store_never_keeps_it_and_keeps_a_real_body():
    from types import SimpleNamespace

    from scripts.sync_economy import _drop_furniture_bodies
    # Sent as NULL, the upsert keeps what is stored; 2,770 characters would otherwise win on length.
    for txt, html in ((SHORT, "<main>" + SHORT + "</main>"), ("Real text of the tender. " * 5, "<h1>Server inaccessibility</h1>" + BARE)):
        it = SimpleNamespace(body_txt=txt, body_html=html)
        _drop_furniture_bodies(it)
        assert it.body_txt is None and it.body_html is None
    real = SimpleNamespace(body_txt="Real text of the tender. " * 5, body_html="<p>Real text of the tender.</p>")
    _drop_furniture_bodies(real)
    assert real.body_txt and real.body_html
