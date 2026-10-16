"""The Commission's outage page is never stored as a document's text (16 Oct 2026)."""
from scripts.remove_stored_outage_pages import strip_outage
from services.scrapers.economy_common import error_body_reason

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
