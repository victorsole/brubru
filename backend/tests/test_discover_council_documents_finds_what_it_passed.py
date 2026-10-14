"""The Council discovery job asks again for what it passed, and for later versions.

14 October 2026: asking only for the numbers after the highest one held found about half
of what data.consilium serves. Every number was probed that day: CM 4301-4608, 217 served
and 112 held; ST 13600-14436, 204 served and 80 held. A document published after the job
had passed its number was never asked for again, and REV, ADD and COR versions never at
all. The job's notes promised exit 1 when data.consilium answered nothing; it returned 0.

The network and the database are faked here: the job's own loop runs against them."""
from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

from scripts import discover_council_documents as job

LIST_A = ("CM 4604/26 1 Contact: coreper.2@consilium.europa.eu EN Council of the European Union General "
          "Secretariat Brussels, 13 October 2026 CM 4604 /26 PTS A LIST OF ADOPTED 'A' ITEMS COUNCIL OF THE "
          "EUROPEAN UNION (General Affairs) ECCL, Luxembourg 13 October 2026 Non-legislative activities")
PROVISIONAL_A = ("CM 4333/26 1 EN Council of the European Union General Secretariat Brussels, 25 September 2026 "
                 "CM 4333 /26 PTS A PROVISIONAL LIST OF 'A' ITEMS COUNCIL OF THE EUROPEAN UNION (Competitiveness "
                 "( Internal Market, Industry , Research and Space)) Europa building, Brussels 24 September 2026")
SCA = ("13358/26 1 LIFE EN Council of the European Union Brussels, 24 September 2026 (OR. en ) 13358 /26 CRS "
       "CSA 18 SUMMARY RECORD SPECIAL COMMITTEE ON AGRICULTURE 21 September 2026 13358/26 2 LIFE EN SUMMARY")
OLD_SPACING = ("12371/24 JUR.7 EN Council of the European Union Brussels , 19 July 2024 12371 / 24 JUR 355 "
               "ELARG 109 NOTE Subject: Accession of Iceland")


def test_headings_without_a_subject_line_name_the_document():
    a = job.parse("CM-4604-2026-INIT", LIST_A)
    assert a["title"] == "List of adopted 'A' items: Council (General Affairs), 13 October 2026"
    assert a["published"] == date(2026, 10, 13) and a["meeting_date"] == date(2026, 10, 13)
    p = job.parse("CM-4333-2026-INIT", PROVISIONAL_A)
    assert p["title"] == ("Provisional list of 'A' items: Council (Competitiveness (Internal Market, "
                          "Industry, Research and Space)), 24 September 2026")
    s = job.parse("ST-13358-2026-INIT", SCA)
    assert s["title"] == "Summary record: Special Committee on Agriculture, 21 September 2026"
    assert s["published"] == date(2026, 9, 24) and s["meeting_date"] == date(2026, 9, 21)


def test_the_printed_date_is_read_whatever_the_spacing_before_the_comma():
    m = job.parse("ST-12371-2024-INIT", OLD_SPACING)
    assert m["published"] == date(2024, 7, 19) and m["title"] == "Accession of Iceland"


def test_the_next_versions_are_the_first_ones_not_held():
    refs = {"ST-14398-2026-INIT", "ST-14398-2026-ADD-1", "ST-14398-2026-ADD-2", "ST-14398-2026-REV-1"}
    assert job.next_versions(refs, "ST", 14398, 2026) == [
        "ST-14398-2026-REV-2", "ST-14398-2026-ADD-3", "ST-14398-2026-COR-1"]


def test_each_run_of_the_day_asks_a_different_third():
    slots = {job.slot_now(datetime(2026, 10, 14, h, 5, tzinfo=timezone.utc)) for h in (7, 13, 19)}
    assert slots == {0, 1, 2}


# ---- the loop itself, against a fake data.consilium and a fake table ----

class FakeConn:
    def __init__(self, held):
        self.held = held

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, stmt, params):
        series_year = params["rx"][1:].split("-[0-9]+-")
        s, y = series_year[0], series_year[1].rstrip("-")
        return SimpleNamespace(scalars=lambda: [r for r in self.held if r.startswith(f"{s}-") and f"-{y}-" in r])


class FakeEngine:
    def __init__(self, held):
        self.held = held

    def connect(self):
        return FakeConn(self.held)


class FakeClient:
    def __init__(self, served, broken=False, **kw):
        self.served, self.broken, self.asked = served, broken, []

    def get(self, url, headers=None):
        ref = url.split("/document/")[1].split("/")[0]
        self.asked.append(ref)
        if self.broken:
            raise TimeoutError("read timed out")
        if ref in self.served:
            return SimpleNamespace(status_code=206, content=b"%PDF")
        return SimpleNamespace(status_code=404, content=b"")

    def close(self):
        pass


@pytest.fixture
def run(monkeypatch):
    def _run(held, served, argv, broken=False):
        stored = []
        client = FakeClient(served, broken)
        monkeypatch.setattr(job, "_engine", lambda: FakeEngine(set(held)))
        monkeypatch.setattr(job.httpx, "Client", lambda **kw: client)
        monkeypatch.setattr(job, "store", lambda engine, ref, apply: stored.append(ref) or apply)
        monkeypatch.setattr(job.time, "sleep", lambda s: None)
        rc = job.main(argv)
        return rc, stored, client.asked
    return _run


def test_a_number_passed_before_it_was_published_is_asked_again(run):
    held = [f"CM-{n}-2026-INIT" for n in range(100, 121) if n != 105]
    served = set(held) | {"CM-105-2026-INIT", "CM-102-2026-ADD-1"}
    rc, stored, asked = run(held, served, ["--series", "CM", "--year", "2026", "--slot", str(105 % 3), "--apply"])
    assert rc == 0
    assert "CM-105-2026-INIT" in stored                   # the gap, found on its slot
    assert "CM-102-2026-ADD-1" in stored                  # a later version of a held document
    assert "CM-102-2026-ADD-2" in asked                   # and the one after it is asked for
    assert "CM-104-2026-INIT" not in asked                # a held number is never asked again
    forward = [r for r in asked if r.endswith("INIT") and int(r.split("-")[1]) > 120]
    assert len(forward) == job.MISS_LIMIT["CM"]          # forward stops after a run of misses


def test_a_sweep_asks_every_unheld_number_in_its_range_with_versions(run):
    rc, stored, asked = run(["ST-3-2025-INIT"], {"ST-5-2025-INIT", "ST-5-2025-REV-1"},
                            ["--sweep", "--series", "ST", "--year", "2025", "--from-number", "1",
                             "--to-number", "8", "--max-seconds", "0", "--apply"])
    assert rc == 0
    assert stored == ["ST-5-2025-INIT", "ST-5-2025-REV-1"]
    assert [r for r in asked if r.endswith("INIT")] == [f"ST-{n}-2025-INIT" for n in (1, 2, 4, 5, 6, 7, 8)]
    assert "ST-5-2025-REV-2" in asked and "ST-5-2025-ADD-1" in asked and "ST-5-2025-COR-1" in asked


def test_a_source_that_answers_nothing_fails_the_run(run, capsys):
    rc, stored, asked = run(["WK-10-2026-INIT"], set(), ["--series", "WK", "--year", "2026", "--slot", "0"],
                            broken=True)
    assert asked and not stored
    assert rc == 1
    assert "answered none" in capsys.readouterr().out


def test_404s_are_answers_not_failures(run, capsys):
    rc, stored, asked = run(["WK-10-2026-INIT"], set(), ["--series", "WK", "--year", "2026", "--slot", "0"])
    assert rc == 0 and "degraded" not in capsys.readouterr().out


def test_a_date_whose_letters_the_pdf_split_is_still_read():
    for text, want in (("Council of the European Union Brus sels , 22 July 2024 (OR. en )", date(2024, 7, 22)),
                       ("Council of the European Union Brussels , 23 July 20 24 (OR. en )", date(2024, 7, 23)),
                       ("Council of the European Union Brussels , 22 Jul y 2024 (OR. en )", date(2024, 7, 22)),
                       ("Council of the European Union Brussels , 2 2 July 2024 (OR. en )", date(2024, 7, 22))):
        assert job.parse("ST-1-2024-INIT", text)["published"] == want, text


def test_draft_minutes_are_named_from_their_heading():
    m = job.parse("ST-12520-2024-INIT", "12520/24 1 GIP EN Council of the European Union Brussels , 3 September "
                  "2024 (OR. en ) 12520 / 24 PV CONS 44 RELEX 1031 DRAFT MINUTES COUNCIL OF THE EUROPEAN UNION "
                  "(Foreign Affairs) 22 July 2024 12520/24 2 GIP EN 1. Adoption of the agenda")
    assert m["title"] == "Draft minutes: Council (Foreign Affairs), 22 July 2024"
    assert m["published"] == date(2024, 9, 3) and m["meeting_date"] == date(2024, 7, 22)
