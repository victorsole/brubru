"""A register document is completed by the cron, not by a script someone remembers to run.

13 October 2026: the 100 newest documents on /commission-register-documents served no text, and
82 of them no date and no link. A document arrives as a reference and a title; its CELEX, date
and text came from scripts run by hand, last on 2 October, so 110 of the 111 documents that
arrived after 5 October had no text."""
import datetime as dt
import pathlib
import re
from types import SimpleNamespace

from scripts import complete_commission_documents as job

BACKEND = pathlib.Path(__file__).resolve().parents[1]
SINCE = dt.datetime(2026, 9, 13, tzinfo=dt.timezone.utc)
TEXT = ("<p>Council Decision</p>", "Council Decision (CFSP) 2026/2285 " * 40)


class _Result:
    def __init__(self, rows=(), scalar=0, rowcount=1):
        self.rows, self.scalar, self.rowcount = list(rows), scalar, rowcount

    def __iter__(self):
        return iter(self.rows)

    def scalar_one(self):
        return self.scalar


class _Engine:
    """Answers each of the job's statements; records every write."""

    def __init__(self, no_celex=(), taken=(), no_date=(), laws_have=0, no_text=(), no_title=()):
        self.reads = {id(job.NO_CELEX): no_celex, id(job.TAKEN): [(c,) for c in taken],
                      id(job.NO_DATE): no_date, id(job.NO_TEXT): no_text, id(job.NO_TITLE): no_title}
        self.laws_have, self.writes = laws_have, []

    def execute(self, stmt, params=None):
        if id(stmt) in self.reads:
            return _Result(self.reads[id(stmt)])
        if stmt is job.LAWS_HAVE:
            return _Result(scalar=self.laws_have)
        self.writes.append((stmt, params))
        return _Result(rowcount=self.laws_have if stmt is job.FROM_LAWS else 1)

    def connect(self):
        return self

    begin = connect

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _cellar(monkeypatch, exists="200", dates=None, titles=None, text=TEXT):
    def raises(*_a):
        raise TimeoutError("Cellar did not answer")
    monkeypatch.setattr(job.time, "sleep", lambda _s: None)
    monkeypatch.setattr(job._celex, "_exists", lambda celex, ctx: exists)
    monkeypatch.setattr(job._date, "_dates", raises if dates is None else lambda celexes, ctx: dates)
    monkeypatch.setattr(job, "_titles", raises if titles is None else lambda celexes, ctx: titles)
    monkeypatch.setattr(job._laws, "_fetch", lambda celex, ctx: text)


def _doc(i, **kw):
    kw.setdefault("portal_url", None)
    return SimpleNamespace(id=i, **kw)


def test_the_cron_runs_it_after_the_documents_and_the_law_texts_arrive():
    src = (BACKEND / "api" / "cron.py").read_text(encoding="utf-8")
    hot = src[src.index('@router.post("/sync/hot-6h")'):src.index("hot-6h tier sync complete")]
    line = next(ln for ln in hot.splitlines() if "complete_commission_documents.py" in ln)
    assert '"--apply"' in line
    assert hot.index('results["commission_docs"] =') < hot.index(line)
    assert hot.index('results["eu_laws_bodies"] =') < hot.index(line)


def test_a_row_gets_the_celex_it_states_only_once_cellar_confirms_it(monkeypatch):
    row = _doc(1, reference="32026D2285", title="Council Decision (CFSP) 2026/2285 of 12 October 2026")
    _cellar(monkeypatch, exists="200", dates={}, titles={})
    db = _Engine(no_celex=[row])
    job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == [(job.SET_CELEX, {"rid": 1, "v": "32026D2285"})]

    _cellar(monkeypatch, exists="404", dates={}, titles={})
    db = _Engine(no_celex=[row])
    work, reached, n = job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == [] and n["celex"] == 0
    assert (work, reached) == (1, 1)  # Cellar answered: it does not hold it yet


def test_a_staff_working_document_with_a_real_title_states_its_celex_in_its_link(monkeypatch):
    _cellar(monkeypatch, dates={}, titles={})
    row = _doc(1, reference="SWD(2026) 315", title="COMMISSION STAFF WORKING DOCUMENT Evaluation",
               portal_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52026SC0315")
    db = _Engine(no_celex=[row])
    job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == [(job.SET_CELEX, {"rid": 1, "v": "52026SC0315"})]
    # A tentative College agenda states none anywhere: nothing is asked and nothing is written.
    db = _Engine(no_celex=[_doc(2, reference="SEC(2026)2564", title="Tentative agenda for forthcoming Commission meetings",
                                portal_url="https://ec.europa.eu/transparency/documents-register/detail?ref=SEC(2026)2564")])
    work, _, _ = job.complete(db, None, SINCE, apply=True, limit=60)
    assert work == 0 and db.writes == []


def test_a_celex_another_row_holds_is_never_given_twice(monkeypatch):
    _cellar(monkeypatch, dates={}, titles={})
    db = _Engine(no_celex=[_doc(1, reference="SWD(2026) 702", title="SWD document 52026SC0702")],
                 taken=["52026SC0702"])
    job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == []


def test_date_text_and_title_are_what_cellar_states(monkeypatch):
    _cellar(monkeypatch, dates={"52026SC0702": {"2026-10-02"}},
            titles={"52026SC0702": {"COMMISSION STAFF WORKING DOCUMENT Third River Basin Management Plans"}})
    db = _Engine(no_date=[_doc(1, celex="52026SC0702")], no_text=[_doc(1, celex="52026SC0702")],
                 no_title=[_doc(1, celex="52026SC0702", title="SWD document 52026SC0702")])
    work, reached, n = job.complete(db, None, SINCE, apply=True, limit=60)
    assert db.writes == [
        (job.SET_DATE, {"rid": 1, "v": dt.date(2026, 10, 2)}),
        (job.SET_TEXT, {"rid": 1, "txt": TEXT[1], "html": TEXT[0]}),
        (job.SET_TITLE, {"rid": 1, "v": "COMMISSION STAFF WORKING DOCUMENT Third River Basin Management Plans"}),
    ]
    assert (work, reached) == (3, 3)
    assert n == {"celex": 0, "date": 1, "text_from_laws": 0, "text_from_cellar": 1, "title": 1}


def test_an_act_s_text_is_copied_from_the_laws_table_before_cellar_is_asked(monkeypatch):
    _cellar(monkeypatch, dates={}, titles={})
    db = _Engine(laws_have=7)
    _, _, n = job.complete(db, None, SINCE, apply=True, limit=60)
    assert [w[0] for w in db.writes] == [job.FROM_LAWS] and n["text_from_laws"] == 7
    # Cellar is asked only for a text the laws table does not hold.
    assert "NOT EXISTS (SELECT 1 FROM eu_laws" in str(job.NO_TEXT)


def test_a_dry_run_writes_nothing(monkeypatch):
    _cellar(monkeypatch, dates={"32026D2285": {"2026-10-12"}}, titles={})
    db = _Engine(no_celex=[_doc(1, reference="32026D2285", title="Council Decision")],
                 no_date=[_doc(2, celex="32026D2285")], laws_have=3, no_text=[_doc(2, celex="32026D2285")])
    _, _, n = job.complete(db, None, SINCE, apply=False, limit=60)
    assert db.writes == []
    assert (n["celex"], n["date"], n["text_from_laws"], n["text_from_cellar"]) == (1, 1, 3, 1)


def test_a_backlog_is_worked_through_over_several_runs(monkeypatch):
    asked = []
    _cellar(monkeypatch, dates={}, titles={})
    monkeypatch.setattr(job._celex, "_exists", lambda celex, ctx: asked.append(celex) or "200")
    rows = [_doc(i, reference=f"32026D{2000 + i}", title="Council Decision") for i in range(5)]
    job.complete(_Engine(no_celex=rows), None, SINCE, apply=True, limit=2)
    assert asked == ["32026D2000", "32026D2001"]


def test_cellar_refusing_us_is_not_read_as_no_text(monkeypatch):
    assert job.answered(TEXT) and job.answered("http_404") and job.answered("too_short_212")
    for wall in ("http_403", "http_429", "http_503", "URLError", "TimeoutError", "pdf_PdfReadError", "empty"):
        assert not job.answered(wall), wall
    # Every source down: the run fails instead of reporting that nothing needed doing.
    _cellar(monkeypatch, exists="URLError", text="http_503")
    db = _Engine(no_celex=[_doc(1, reference="32026D2285", title="Council Decision")],
                 no_date=[_doc(2, celex="32026R2269")], no_text=[_doc(2, celex="32026R2269")],
                 no_title=[_doc(3, celex="52026SC0702", title="SWD document 52026SC0702")])
    work, reached, _ = job.complete(db, None, SINCE, apply=True, limit=60)
    assert (work, reached) == (4, 0) and db.writes == []
    assert job.verdict(work, reached, []) == (1, None)


def test_documents_still_incomplete_after_three_days_are_named_not_hidden():
    code, line = job.verdict(5, 5, [f"52026PC0{n}" for n in range(500, 511)])
    assert code == 0
    assert line.startswith("11 register documents older than 3 days still lack a date or a text: 52026PC0500, ")
    assert line.endswith("and 3 more")
    assert job.verdict(5, 5, []) == (0, None)
    assert job.verdict(0, 0, []) == (0, None)  # nothing to do is not a failure
    # A document that arrived yesterday is not yet late: Cellar can lag two days.
    assert "first_seen < :settled" in str(job.STILL)


def test_an_empty_or_disputed_answer_is_never_stored():
    assert job.one_title({""}) is None                      # Cellar returned an empty title for one SWD
    assert job.one_title({"SWD/2026/119 final"}) is None    # the short form is not the title
    assert job.one_title({"Report on the Recovery Facility", "Annual report on the Facility"}) is None
    assert job.one_title({"  COMMISSION STAFF  WORKING DOCUMENT\nEvaluation "}) == "COMMISSION STAFF WORKING DOCUMENT Evaluation"
    assert job.one_title(None) is None
    assert job.one_date({"2026-10-02", "2026-10-03"}) is None
    assert job.one_date({"2026-10-02"}) == dt.date(2026, 10, 2)
    assert job.one_date(None) is None


def test_a_corrigendum_filed_under_the_act_it_corrects_is_left_alone():
    # "CELEX:32011L0089R(02)" is stored under 32011L0089: that act's 2011 date and text are not its own.
    for title in ("CELEX:32011L0089R(02)", "CELEX:32024L2841R(01): Corrigendum to Directive (EU) 2024/2841",
                  "CELEX:32026R1107R(01):   Rectificatif au règlement d'exécution"):
        assert re.search(job.CORRIGENDUM, title), title
    for title in ("Council Decision (CFSP) 2026/2285 of 12 October 2026", "SWD document 52026SC0702",
                  "Regulation (EU) 2026/2269 of the European Parliament and of the Council"):
        assert not re.search(job.CORRIGENDUM, title), title
    for stmt in (job.NO_CELEX, job.NO_DATE, job.NO_TEXT, job.FROM_LAWS, job.LAWS_HAVE, job.STILL):
        assert job.CORRIGENDUM in str(stmt), stmt


def test_only_an_empty_cell_is_written():
    assert "coalesce(celex, '') = ''" in str(job.SET_CELEX)
    assert "publication_date IS NULL" in str(job.SET_DATE)
    assert "coalesce(text_body, '') = ''" in str(job.SET_TEXT)
    assert "coalesce(d.text_body, '') = ''" in str(job.FROM_LAWS)
    # A real title is never replaced: only the placeholder the feed reader wrote.
    assert f"title ~ '{job.PLACEHOLDER}'" in str(job.SET_TITLE)
    assert re.search(job.PLACEHOLDER, "SWD document 52026SC0702")
    assert not re.search(job.PLACEHOLDER, "COMMISSION STAFF WORKING DOCUMENT Evaluation")
