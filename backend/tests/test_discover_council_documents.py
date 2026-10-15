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


def test_a_text_with_lone_surrogates_or_nul_is_stored_without_them(monkeypatch):
    """WK 15919/2025 (970,017 characters) carried '\\udd00' 18 times; the driver could not
    encode it and the 2025 backfill stopped there (14 Oct 2026). Through the real store():
    every value written must encode, and the text loses only the bad characters."""
    import io
    import sys
    from contextlib import contextmanager

    import scripts.discover_council_documents as dcd
    written = []

    class _Conn:
        def execute(self, sql, params=None):
            written.append(params or {})
            for v in (params or {}).values():
                if isinstance(v, str):
                    v.encode("utf-8")  # what psycopg2 does before sending
                    assert "\x00" not in v

            class _R:
                def fetchone(self):
                    return type("Row", (), {"inserted": True})()
            return _R()

    class _Engine:
        @contextmanager
        def begin(self):
            yield _Conn()

    raw = "WK 15919/2025 Subject: Working document \udd00 on fisheries\x00 " + "x" * 300
    monkeypatch.setattr(dcd, "fetch_document_text", lambda doc, max_chars=0: raw)
    # A terminal or log file is strict UTF-8; pytest's capture would hide the crash.
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(io.BytesIO(), encoding="utf-8", errors="strict"))
    assert dcd.store(_Engine(), "WK-15919-2025-INIT", apply=True) is True
    body = written[0]["body"]
    assert body == raw.replace("\udd00", "").replace("\x00", "")
    assert written[0]["summary"] == body[:900]
