"""Council register documents discovered by reference on data.consilium (28 Sep 2026)."""
from scripts.discover_council_documents import parse

CM = ("CM 4293/26 1 EN Council of the European Union General Secretariat Brussels, 23 September 2026 "
      "CM 4293 /26 CCG COMMUNICATION NOTICE OF MEETING AND PROVISIONAL AGENDA Contact: x Subject: "
      "679th meeting of the Export Credits Group [afternoon only] Date: 14 October 2026 Time: 14:30 Venue: X")
ECOFIN = ("CM 4300/26 1 Contact: c EN Council of the European Union General Secretariat Brussels, 24 September 2026 "
          "CM 4300 /26 OJ CONS ECOFIN NOTICE OF MEETING AND PROVISIONAL AGENDA COUNCIL OF THE EUROPEAN UNION1 "
          "(Economic and Financial Affairs) ECCL, Luxembourg 9 October 2026 (10:00) Format 1+2+1")
COREPER = ("13105/26 1 GIP.CRP2 EN Council of the European Union Brussels, 18 September 2026 (OR. en ) 13105 /26 "
           "OJ CRP2 32 PROVISIONAL AGENDA PERMANENT REPRESENTATIVES COMMITTEE (Part 2) Europa building, "
           "Brussels 23 September 2026 (10:00) Format 1+2+1")
COMPET = ("PROVISIONAL AGENDA COUNCIL OF THE EUROPEAN UNION (Competitiveness ( Internal Market , Industry , "
          "Research and Space)) Europa building, Brussels 24 September 2026 (09:30)")


def test_working_party_notice_title_stops_before_date_and_keeps_meeting_date():
    m = parse("CM-4293-2026-INIT", CM)
    assert m["title"] == "679th meeting of the Export Credits Group [afternoon only]"
    assert str(m["published"]) == "2026-09-23" and str(m["meeting_date"]) == "2026-10-14"


def test_council_and_coreper_agendas_are_named():
    assert parse("CM-4300-2026-INIT", ECOFIN)["title"] == \
        "Provisional agenda: Council (Economic and Financial Affairs), 9 October 2026"
    c = parse("ST-13105-2026-INIT", COREPER)
    assert c["title"] == "Provisional agenda: Coreper (Part 2), 23 September 2026"
    assert str(c["meeting_date"]) == "2026-09-23"
    assert parse("X", COMPET)["title"].startswith("Provisional agenda: Council (Competitiveness (")


def test_unparseable_falls_back_to_the_reference():
    assert parse("WK-1-2026-INIT", "nothing useful")["title"] == "WK-1-2026-INIT"
