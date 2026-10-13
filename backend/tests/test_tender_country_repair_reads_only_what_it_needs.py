"""The nightly tender-country repair reads the XML of the rows that need it, and only those.

13 October 2026: it loaded every notice with its XML (49,701 rows, 1.25 GB) to look at each
country, and the platform killed it every night for eight nights (rc=-9, no output), one
"Deploy Crashed" mail each time. That day 260 rows had no valid country and 4 had any XML."""
from types import SimpleNamespace

from scripts import repair_tender_country as job

XML_CZ = '<cac:Country><cbc:IdentificationCode listName="country">CZE</cbc:IdentificationCode></cac:Country>'


class _Db:
    def __init__(self, rows, xml):
        self.rows, self.xml = rows, xml
        self.xml_asked, self.updates, self.commits = [], [], 0

    def execute(self, stmt, params=None):
        if stmt is job._COUNTRIES:
            return SimpleNamespace(all=lambda: self.rows)
        if stmt is job._XML:
            self.xml_asked.append(list(params["ids"]))
            return SimpleNamespace(all=lambda: [
                SimpleNamespace(id=i, xml_content=self.xml.get(i)) for i in params["ids"]])
        if stmt is job._SET:
            self.updates.append((params["id"], params["c"]))
            return None
        raise AssertionError(f"unexpected statement: {stmt}")

    def commit(self):
        self.commits += 1


def _row(i, country):
    return SimpleNamespace(id=i, publication_number=f"{i:06d}-2026", buyer_country=country)


def test_the_whole_table_is_read_without_its_xml():
    assert "xml_content" not in str(job._COUNTRIES)
    assert "ANY(:ids)" in str(job._XML)


def test_xml_is_fetched_only_for_rows_without_a_valid_country():
    db = _Db([_row(1, "FR"), _row(2, None), _row(3, "DE"), _row(4, "CS"), _row(5, "ES")],
             {2: XML_CZ, 4: "<notice>no country stated</notice>"})
    fixed, unresolved, already_valid = job.repair(db, apply=True)
    assert db.xml_asked == [[2, 4]]
    assert (fixed, unresolved, already_valid) == (1, 1, 3)
    assert db.updates == [(2, "CZ")]
    assert db.commits == 1


def test_a_dry_run_writes_nothing():
    db = _Db([_row(1, None)], {1: XML_CZ})
    assert job.repair(db, apply=False) == (1, 0, 0)
    assert db.updates == [] and db.commits == 0


def test_the_xml_is_read_in_small_batches():
    rows = [_row(i, None) for i in range(1, 251)]
    db = _Db(rows, {})
    fixed, unresolved, _ = job.repair(db, apply=True)
    assert [len(b) for b in db.xml_asked] == [100, 100, 50]
    assert (fixed, unresolved) == (0, 250)


def test_a_row_whose_xml_names_no_country_is_left_alone_never_guessed():
    db = _Db([_row(7, "DA")], {7: None})
    assert job.repair(db, apply=True) == (0, 1, 0)
    assert db.updates == []
